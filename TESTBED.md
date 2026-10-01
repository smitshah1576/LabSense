# LabSense — E2E Testbed

The whole system on one machine: server, database, dashboard and **five client PCs** on their own
simulated lab LAN, ready for end-to-end testing. It runs in a cloud dev container and on
any Linux/macOS machine with Docker.

```bash
testbed/testbed.sh up        # ~10 s once images are cached
testbed/testbed.sh test      # automated E2E suite, ~55 s
testbed/pcctl status         # what each PC is doing vs. what the server made of it
testbed/testbed.sh down      # --wipe to also reset the database to the seed
testbed/testbed.sh wifi poor # put the fleet behind emulated Wi-Fi (good | campus | poor | off)
testbed/testbed.sh scale     # scale test against a laptop-sized server (testbed/loadtest/README.md)
```

The testbed is laid out like the real deployment, a Windows server and Ubuntu lab PCs on one Wi-Fi.
The same code runs unchanged in both; see [How close is this to the real lab?](#how-close-is-this-to-the-real-lab).

---

## Topology

```
 host = the server (LAN IP 172.28.0.1)            Docker network labsense-lan 172.28.0.0/24
 ┌──────────────────────────────────────┐         ┌──────────────────────────────────────────────┐
 │ frontend  vite --host 0.0.0.0 :5173  │         │ lab-wifi    172.28.0.2   Wi-Fi emulator (opt)│
 │ backend   uvicorn 0.0.0.0     :8000 ◄┼── WS    │ lab-a-pc-1  172.28.0.11  mock   ctl :7001    │
 │           TCP heartbeats      :9000 ◄┼─────────┤ lab-a-pc-2  172.28.0.12  mock   ctl :7002    │
 │ database  labsense-db (Docker) :5432 │         │ lab-a-pc-3  172.28.0.13  mock   ctl :7003    │
 └──────────────────────────────────────┘         │ lab-a-pc-4  172.28.0.14  mock   ctl :7004    │
                                                  │ lab-a-pc-5  172.28.0.15  REAL AGENT          │
                                                  └──────────────────────────────────────────────┘
```

- **Database:** the repo's own `docker-compose.yml` (`labsense-db`, seeded from `docker/init.sql`).
- **Backend and frontend:** host processes, started with the commands `SETUP_WINDOWS_SERVER.md` uses
  (`--host 0.0.0.0`). Two additions:
  - `--loop asyncio`, so Linux runs the same stock asyncio event loop as Windows rather than uvloop.
  - `--env-file testbed/server.env`, the testbed's `backend\.env`.

  The dev backend also runs with `--reload`, so edits under `backend/app/` take effect without
  restarting the testbed. In-memory PC state resets on each reload; the fleet repopulates it within
  one heartbeat. `testbed.sh scale` runs it without `--reload`, exactly as on the Windows server.
- **The server's LAN address is 172.28.0.1**, the host's address on the lab network. The PCs are
  pointed at it the way `deploy_agent.sh --server-host` points real PCs at the server's Wi-Fi IP,
  and the dashboard can be opened at `http://172.28.0.1:5173` the way a teammate on the Wi-Fi opens
  `http://<server IP>:5173`.
- **Client PCs:** `testbed/compose.yml`. Each PC is its own container with its own hostname and IP, and
  the backend logs each connection from that IP.
  - `lab-a-pc-1..4` run `testbed/mock_pc.py`, a scenario-driven mock. It uses the real agent's
    `labsense_agent.protocol`, so its bytes on the wire are the agent's.
  - `lab-a-pc-5` runs the **unmodified agent** (`agent/Dockerfile`). A container has no logind, no
    system D-Bus and no `/dev/input`, so the agent runs in its degraded mode: session from utmp (none,
    so the PC reads Available), D-Bus listener retrying under supervision, and real `dpkg`/`pip`
    software scans every 60 s.
- **Wi-Fi (optional):** `testbed.sh wifi <profile>` starts `lab-wifi`, which stands where the access
  point would be, and re-points the fleet at it. See [Wi-Fi emulation](#wi-fi-emulation).

Seed logins: `admin@labsense.dev`, `prof@labsense.dev`, `student@labsense.dev`, all with password
`password123`.

---

## The fleet

| PC | Default scenario | Server state | Extra software |
|---|---|---|---|
| lab-a-pc-1 | `in-use`: at the keyboard | IN_USE | code, nodejs, npm, python3-venv |
| lab-a-pc-2 | `idle`: logged in, walked away 10 min ago | AVAILABLE | openjdk-17-jdk, eclipse, maven |
| lab-a-pc-3 | `locked`: screen locked, stepped out | IN_USE (until the 15 min lock reserve expires) | octave, r-base, python3-numpy, python3-pandas, jupyter-notebook |
| lab-a-pc-4 | `cpu-busy`: long job, nobody there | IN_USE after 3 busy heartbeats (~15 s) | blender, gimp, nvidia-cuda-toolkit, python3-numpy |
| lab-a-pc-5 | real agent | AVAILABLE (no session in a container) | whatever `dpkg -l` / `pip list` find |

Every mock also reports a shared base image (`python3`, `gcc`, `git`, `firefox`, …). A search for
`firefox` therefore hits all four mocks, and a search for `eclipse` hits only pc-2.

### Driving a PC — `testbed/pcctl`

`<pc>` can be `3`, `pc-3`, `lab-a-pc-3`, or `all` (every mock).

| Command | What it simulates | Expected on the dashboard |
|---|---|---|
| `pcctl 3 scenario idle` | user behaviour change (`in-use`, `idle`, `locked`, `cpu-busy`, `logged-out`) | new state within a second |
| `pcctl 3 sleep` | clean suspend: `GOING_TO_SLEEP`, then the link drops | **Asleep** immediately, and it stays Asleep |
| `pcctl 3 power-off` | power loss: link dropped, nothing sent | In use for 15 s, then **Available** |
| `pcctl 3 hang` | frozen OS: socket open, nothing sent | In use for 15 s, then **Available** |
| `pcctl 3 wake` / `power-on` | resume heartbeats | back to the scenario's state |
| `pcctl 3 unplug` / `replug` | pull the network cable (`docker network disconnect`) | Available after 15 s; recovers on replug, usually on the same TCP connection |
| `pcctl 5 stop` / `start` | stop/start the whole machine or agent service | Available after 15 s |
| `pcctl 3 software` | resend the SOFTWARE_REPORT now | — |

The mock PCs' control APIs can also be called directly: `curl -X POST localhost:7003/sleep`,
`curl localhost:7003/status`.

---

## Automated E2E suite — `testbed/testbed.sh test`

`testbed/tests/`, pytest, run from `backend/.venv`. It drives the running system from the outside,
the way agents and the dashboard do. Raw TCP frames go in, and the suite checks REST, WebSocket
pushes and the database.

- **`test_server.py`** registers its own throwaway lab and PCs through the admin API (never touching
  Lab A) and deletes them afterwards:
  - auth and RBAC for all three roles, plus WebSocket token rejection
  - PC registration and pc_id convention, `REJECTED` for unknown or deregistered PCs (T3)
  - heartbeat → REST, WebSocket and DB (T2); write-on-transition only
  - the IN_USE rule: idle threshold, sustained-CPU window, lock reserve, no-session override
  - dirty disconnect vs. the 15 s grace period (T6); `GOING_TO_SLEEP` → AVAILABLE_SLEEP, which
    survives the timer (T7)
  - maintenance override and permissions (T8); damage-report approve/dismiss
  - lab state OPEN → OCCUPIED → cancelled → OPEN, and CLOSED over everything (T9)
  - software search, global and per lab, including the JSONB-as-string regression (T10)
  - WebSocket fan-out to several dashboards, and the initial snapshot (T11)
- **`test_fleet.py`** checks the containers:
  - every PC is reporting, and default scenarios land on the expected states
  - the real agent's dpkg and pip inventory is searchable
  - sleep/wake, scenario switches and cable pull/replug work through `pcctl`

Useful subsets:

```bash
testbed/testbed.sh test -m "not slow"     # skip the three 15 s grace-period waits (~5 s total)
testbed/testbed.sh test -m fleet          # just the client containers
testbed/testbed.sh test -k lab_state -v
```

**Known backend bug, tracked by strict `xfail` tests.** `PUT /pcs/{id}/maintenance` and approving
a damage report each insert a `state_transitions` row after `set_maintenance()` has already inserted
one through the transition callback. The result is that every maintenance change is recorded twice.
`test_maintenance_changes_are_recorded_once` and `test_approved_report_is_recorded_once` document
it. Once it's fixed they will XPASS, which strict mode reports as a failure; delete the markers then.

The rule parameters the tests assume are the backend defaults in `app/config.py`. If you run the
backend with different `LABSENSE_*` values, export the same variables when running the tests.

---

## How close is this to the real lab?

The code doesn't change between the testbed and the lab: the backend, frontend and agent run from
this repository as they are. The differences are configuration, which the lab sets once by
following `SETUP_WINDOWS_SERVER.md`, and the operating system and radio, which a container can't
reproduce.

**Same as the lab**

| | Testbed | Lab |
|---|---|---|
| Server start | `uvicorn app.main:app --host 0.0.0.0 --port 8000`, stock asyncio loop | same (asyncio's default loop on Windows) |
| Server settings | `testbed/server.env` | `backend\.env` |
| Where PCs connect | server's LAN IP `172.28.0.1:9000`, one TCP connection per PC, each from its own IP | server's Wi-Fi IP `:9000` |
| Where dashboards connect | `http://172.28.0.1:5173`, which calls the API at `:8000` on the same host | `http://<server IP>:5173` |
| CORS | the LAN origin must be in `LABSENSE_CORS_ORIGINS` (the E2E suite checks it is allowed and others aren't) | same |
| Agent | the unmodified agent, plus mocks that use its protocol module | the agent |
| Wi-Fi | emulated latency, retransmission stalls and dropouts | real |

**Not reproduced here; check these in the lab**

- **Windows itself.** Its event loop (Proactor), its TCP stack (buffer sizes, how long it keeps
  retrying a peer that vanished) and Windows Defender Firewall (Phase 0.4 of the guide) differ
  from Linux. The Python code paths are the same, but behaviour under heavy load may not be. Run
  `testbed/loadtest` against the real server to measure it there.
- **The real network:** access-point client isolation (Phase 0.8), DHCP giving the server a new IP,
  roaming between access points.
- **Python version:** the testbed backend runs Python 3.11. The Windows guide notes that 3.14 works.
- **Desktop telemetry:** logind sessions, input idle time, screen locks and the sleep inhibitor need a
  real Ubuntu desktop (see the end of [Manual E2E](#manual-e2e-against-testingmd)).

**Lab settings the testbed already has, and the lab must set**

- `LABSENSE_CORS_ORIGINS` in `backend\.env` must include `http://<server IP>:5173`.
  `testbed/server.env` shows the format.
- Open the dashboard by **IP address**, not by the laptop's hostname. Vite's dev server refuses
  requests for host names it doesn't know (it allows IP addresses and `localhost`).
- **Don't add `--reload` or `--workers`** to the Windows server command:
  - With either, uvicorn on Windows switches to the selector event loop, which handles at most 512
    sockets (about 500 PCs and dashboards combined).
  - `--workers` would also split the in-memory PC state across processes.

---

## Wi-Fi emulation

```bash
testbed/testbed.sh wifi campus   # good | campus | poor | off
testbed/testbed.sh status        # the wi-fi row shows the active profile
```

`testbed/wifi_proxy.py` runs as `lab-wifi` (172.28.0.2) and relays the server's ports. Kernel traffic
shaping isn't available in the cloud sandbox, so it works at the TCP level: every chunk of data gets
the profile's latency and jitter, a "lost" chunk costs a retransmission stall that holds back
everything behind it, and now and then a device's link freezes for a few seconds without
disconnecting. Byte order is kept, as TCP keeps it.

| Profile | One-way latency | Loss → stall | Dropouts per device |
|---|---|---|---|
| `good` | 3 ± 2 ms | 0.1 % | none |
| `campus` | 15 ± 10 ms | 1 % | 1–4 s, every ~30 min |
| `poor` | 60 ± 40 ms | 4 % | 2–8 s, every ~5 min |
| `off` | — | — | the emulator stops; PCs go straight to the server |

Switching profiles restarts the fleet pointed at the emulator, or back at the server for `off`. The
dashboard can be opened through it too, at `http://172.28.0.2:5173`. The fleet tests
(`testbed.sh test -m fleet`) pass under `poor`. The 15 s grace period absorbs its stalls, though its
longest dropouts, plus the 5 s between heartbeats, come within a few seconds of it.

---

## Scale testing

`testbed/testbed.sh scale` runs `testbed/loadtest/loadgen.py`: thousands of simulated PCs and a set of
live dashboards, against the backend restarted as a **student-laptop-sized server** (one CPU core,
no `--reload`, PostgreSQL on its own core with 1 GB). It reports heartbeat-to-dashboard latency,
false offline flips, REST latency and server CPU/memory per step. The same load generator runs
against the real Windows server from any Linux machine on the Wi-Fi.

How to run it, in the testbed and in the lab: [`testbed/loadtest/README.md`](testbed/loadtest/README.md).
Baseline results and the bottlenecks they point to: [`testbed/loadtest/BASELINE.md`](testbed/loadtest/BASELINE.md).

---

## Manual E2E against TESTING.md

`TESTING.md` is written for the real topology (a Windows or Ubuntu server plus physical Ubuntu lab
PCs). On the testbed, the server is `localhost`:

| TESTING.md | On the testbed |
|---|---|
| T1 reachability | `nc -vz localhost 9000` |
| T2 raw probe | `pcctl 1 stop`, then `python3 agent/test_heartbeat.py localhost lab-a-pc-1` (IN_USE, then Available 15 s later); `pcctl 1 start` afterwards |
| T3 unregistered pc_id | `python3 agent/test_heartbeat.py localhost bogus-pc` |
| T4 mock agent | covered by the fleet; `agent/mock_agent.py localhost` still works but fights the fleet for lab-a-pc-1..5 |
| T5 real agent | `testbed/testbed.sh logs lab-a-pc-5` |
| T6 grace period | `pcctl 1 power-off`, or `pcctl 1 unplug` for the "pull the cable" demo |
| T7 clean suspend | `pcctl 1 sleep` (mock). The real inhibitor lock needs a real Ubuntu desktop. |
| T8–T11 | browser at `:5173`, or the automated tests above |
| DB queries | `docker exec -it labsense-db psql -U labsense -d labsense` |

**Not covered by the testbed:** T5b and T7 against the *real* agent. Telemetry from logind, input
devices and screen locks, and the sleep inhibitor, all need a real Ubuntu desktop session. The mocks
exercise the same protocol path on the server side.

---

## Cloud environment notes

- **Session setup:** run `testbed/bootstrap.sh` (backend venv + `npm install`) and
  `testbed/testbed.sh prepare` (starts Docker, pulls images, builds the agent image) once when a new
  environment starts. Neither starts any services.
- **No systemd** in the sandbox: `testbed.sh` starts `dockerd` itself when it isn't running (log in
  `testbed/.run/dockerd.log`).
- **Proxy:** outbound HTTPS goes through a TLS-intercepting proxy on `127.0.0.1`, which containers
  can't reach. The agent image is built with `--network host`, the proxy passed as a build arg, and
  the proxy CA passed as the optional BuildKit secret `pip_ca`. Runtime containers need no internet.
- **Seeing the dashboard:** container ports aren't exposed to your browser. Open it in
  the preinstalled headless Chromium (Playwright) and take screenshots. External Google Fonts fail
  TLS there, so the UI falls back to system fonts. That's cosmetic.
- **WebSocket clients and the proxy:** the sandbox sets `HTTPS_PROXY`, and the `websockets` library
  honours it. Python's `no_proxy` handling ignores CIDR ranges, so a connection to `172.28.0.1` is sent
  to the proxy, which refuses it with 403. Test code passes `proxy=None` to `websockets.connect`.
- **Ephemeral:** the container and its database go away with the session. Nothing is persisted
  outside git.

---

## Troubleshooting

| Symptom | Look at |
|---|---|
| `up` fails at backend/frontend | `testbed/testbed.sh logs backend` (or `frontend`); the last lines are also printed on failure |
| A PC shows `REJECT` in `pcctl status` | its pc_id isn't in `pcs`, e.g. after a lab was deleted. Run `testbed/testbed.sh down --wipe && testbed/testbed.sh up` |
| Stale or odd data after experiments | `down --wipe` re-seeds from `docker/init.sql` |
| Port 5432/8000/9000/5173/7001–7004 busy | another stack is running. `up` reuses a healthy backend/frontend it didn't start |
| `172.28.0.0/24` clashes with your network | change the subnet in `testbed/compose.yml` and the IPs in `testbed/pcctl` |
| Everything else | `testbed/testbed.sh status`, `testbed/testbed.sh logs lab-a-pc-N` |
