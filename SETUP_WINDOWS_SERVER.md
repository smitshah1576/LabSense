# LabSense — Windows Server + Ubuntu Agents Setup Guide

This guide covers the split deployment: **database, backend and frontend on a Windows PC; agents on
Ubuntu lab machines.** If everything runs on a single Ubuntu box instead, use
[`SETUP_UBUNTU.md`](SETUP_UBUNTU.md) — that guide is still correct for the all-in-one case.

The difference matters more than it looks. In this topology the agents have to cross a real network
to reach the server, and two things stand between them that are invisible in the single-machine
setup: Windows Defender Firewall, and the Wi-Fi access point itself. **Phase 0 exists to rule those
out before you debug anything else.**

---

## Component & Port Summary

| Component | Runs on | Port | Notes |
|---|---|---|---|
| PostgreSQL | Windows (Docker Desktop) | `5432` | Schema + seed data from `docker/init.sql` |
| pgAdmin *(optional)* | Windows (Docker Desktop) | `5050` | `admin@labsense.dev` / `admin` |
| Backend REST + WebSocket | Windows (uvicorn) | `8000` | Must bind `0.0.0.0`, not `127.0.0.1` |
| Backend TCP heartbeat server | Windows (asyncio) | `9000` | This is the port the agents connect to |
| Frontend | Windows (Vite) | `5173` | |
| Agent | Ubuntu lab PCs | — | Outbound only, to the Windows PC's port `9000` |

---

## Phase 0 — Network reachability (run this first, every session)

Do not skip this. It takes two minutes and it is the difference between "the agent is broken" and
"the packets never arrived."

### 0.1 — Find the server's LAN IP (Windows)

```bash
ipconfig
```

Use the IPv4 address of the adapter that is actually connected — for this machine it is the **Wi-Fi**
adapter, currently `10.234.237.199`. **Ignore any `169.254.x.x` address**: that is APIPA, meaning the
adapter failed to get a DHCP lease and is not usable.

### 0.2 — Confirm both machines are on the same subnet (Ubuntu)

```bash
ip -4 addr show
```

The Ubuntu address should be on the same network as the server (e.g. both `10.234.x.x` with the same
mask). If they differ, this is a routing problem, not a firewall problem — no firewall rule will fix
it.

### 0.3 — Check the Windows network profile

```powershell
Get-NetConnectionProfile
```

If `NetworkCategory` is **Public**, Windows blocks all unsolicited inbound traffic by default. Either
set the profile to Private, or add the explicit rules in 0.4 (which work on any profile).

### 0.4 — Open the firewall ports (Windows, admin PowerShell)

```powershell
New-NetFirewallRule -DisplayName "LabSense TCP 9000" -Direction Inbound -LocalPort 9000 -Protocol TCP -Action Allow
```

```powershell
New-NetFirewallRule -DisplayName "LabSense API 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

```powershell
New-NetFirewallRule -DisplayName "LabSense UI 5173" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow
```

Verify with `Get-NetFirewallRule -DisplayName "LabSense*"`.

### 0.5 — Confirm the backend is actually listening on all interfaces (Windows)

After starting the backend (Phase 2), run:

```bash
netstat -ano | findstr ":9000"
```

You want `0.0.0.0:9000 … LISTENING`. If it says `127.0.0.1:9000`, `LABSENSE_TCP_HOST` is wrong and no
remote machine can ever connect.

### 0.6 — The definitive reachability test (Ubuntu)

```bash
nc -vz 10.234.237.199 9000
```

No `nc` installed? Bash can do it directly:

```bash
timeout 5 bash -c '</dev/tcp/10.234.237.199/9000' && echo OPEN || echo BLOCKED
```

`succeeded` / `OPEN` means the path is clear. This needs no agent and no ICMP, which is why it is the
test that counts.

### 0.7 — Ping is *not* a reliable test

```bash
ping 10.234.237.199
```

Windows blocks inbound ICMP by default, so a failed ping alongside a passing 0.6 is perfectly normal.
Never conclude "the network is down" from ping alone here.

### 0.8 — Ruling out Wi-Fi client isolation

If 0.6 fails but the Ubuntu machine reaches the internet fine, test the gateway:

```bash
ip route | grep default          # find the gateway, then:
ping <gateway-ip>
```

**Gateway reachable but the Windows peer is not = AP client isolation.** Many campus and guest
networks deliberately block traffic between wireless clients. No code change or firewall rule can
work around this. Options:

- Put both machines on a phone hotspot (simplest for a demo).
- Use a wired switch or a dedicated router.
- Ask for both devices to be placed on a network segment without isolation.

---

## Phase 1 — Database (Windows, Docker Desktop)

Start **Docker Desktop** and wait for it to report "Engine running" — `docker compose` fails with a
`dockerDesktopLinuxEngine` pipe error until it does.

```bash
docker compose up -d
```

Verify the containers and the seed data:

```bash
docker compose ps
```

```bash
docker exec -it labsense-db psql -U labsense -d labsense -c "SELECT pc_id, lab_id, current_state FROM pcs;"
```

You should see `lab-a-pc-1` … `lab-a-pc-5`. **Note these IDs — Phase 4 depends on them.**

> **The seed only runs once.** `docker/init.sql` is executed by Postgres only on the *first*
> initialisation of the `pgdata` volume. If the tables or seed rows are missing, or you have edited
> `init.sql`, you must destroy the volume to re-run it:
>
> ```bash
> docker compose down -v
> ```
>
> This **permanently deletes all database data**, including any labs, PCs and reports you created
> through the UI. Then `docker compose up -d` to re-create and re-seed.

---

## Phase 2 — Backend (Windows)

```bash
cd backend
```

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

Python 3.14 is fine — every dependency (`asyncpg`, `httptools`, `bcrypt`, `pydantic-core`) ships a
`win_amd64` wheel, so no compiler is needed. The `tzdata` package in `requirements.txt` is
**required on Windows**: without it `zoneinfo` cannot resolve `Asia/Kolkata` and lab-state
calculations fall back to the server's own clock.

Check `backend\.env` — in particular `LABSENSE_CORS_ORIGINS` must list every origin the dashboard
will be opened from, including the server's LAN IP if teammates will browse to it.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` is not optional here: the default binds localhost only. Verify:

- <http://localhost:8000/health> → `{"status":"ok"}`
- <http://localhost:8000/docs> → interactive API docs
- `netstat -ano | findstr ":9000"` → step 0.5 above

---

## Phase 3 — Frontend (Windows)

In a second terminal:

```bash
cd frontend
```

```bash
npm install
```

```bash
npm run dev -- --host 0.0.0.0
```

Open <http://localhost:5173>. The dashboard defaults to talking to port 8000 on whatever host served
it, so browsing from another machine via `http://10.234.237.199:5173` works without configuration —
provided that origin is in `LABSENSE_CORS_ORIGINS`. To point the UI at a backend on a *different*
host, copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_URL` / `VITE_WS_URL`.

Seed logins (all `password123`): `admin@labsense.dev`, `prof@labsense.dev`, `student@labsense.dev`.

---

## Phase 4 — Agent (Ubuntu lab PCs)

> **The `--pc-id` must already exist in the server's `pcs` table.** The server rejects heartbeats
> from unregistered PCs. Check the list with the `psql` command in Phase 1, or register a new PC
> through `POST /admin/pcs` as an admin. If you omit `--pc-id` it defaults to the machine's
> hostname, which almost certainly does not match.

```bash
sudo apt install -y python3-venv xprintidle
```

```bash
cd agent
```

```bash
sudo ./deploy_agent.sh --server-host 10.234.237.199 --server-port 9000 --pc-id lab-a-pc-1
```

Watch it run:

```bash
sudo journalctl -u labsense-agent -f
```

A healthy agent logs `Connected to backend at …`, then `Heartbeat #1 sent …`, then roughly one
heartbeat line per minute. For every single heartbeat, redeploy with `--log-level DEBUG`.

If the server rejects the `pc_id`, the agent now logs an explicit `Server rejected pc_id …` error
rather than appearing healthy.

### Running the agent in the foreground instead

For quick testing without installing a service:

```bash
cd agent && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

```bash
LABSENSE_SERVER_HOST=10.234.237.199 LABSENSE_PC_ID=lab-a-pc-1 LABSENSE_LOG_LEVEL=DEBUG python3 -m labsense_agent.main
```

Note this behaves *differently* from the systemd deployment: run this way it inherits your desktop
session, so `xprintidle` can read real idle time. The packaged service runs as the unprivileged
`labsense` system user with no `DISPLAY`, where idle detection is unreliable — see the caveat in
`md_files/progress.md`.

### Useful commands

```bash
sudo systemctl status labsense-agent
```

```bash
sudo systemctl restart labsense-agent
```

---

## Phase 5 — Daily start-up order

1. Start **Docker Desktop**, wait for "Engine running".
2. `docker compose up -d`
3. Backend: `cd backend && .venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. Frontend: `cd frontend && npm run dev -- --host 0.0.0.0`
5. Agents: `sudo systemctl start labsense-agent` on each Ubuntu PC.

If the Windows PC's IP changed (Wi-Fi DHCP often reassigns), re-run Phase 0.1 and update the agents
— `deploy_agent.sh` writes the address into the systemd unit, so it does not follow a moving IP.

---

## Testing

See [`TESTING.md`](TESTING.md) for the full ordered test procedure, including the standalone
protocol probe that isolates network problems from agent problems.
