# LabSense scale testing

How many lab PCs and open dashboards can one server handle, and what breaks first? This folder
answers that the same way in the testbed and in the real lab, so a code change can be measured
before and after on identical terms.

| File | What it does | Runs on |
|---|---|---|
| `loadgen.py` | Simulates N lab PCs (one TCP connection each, the real agent wire protocol) and M dashboards (WebSockets), ramps through `--steps`, measures and writes a report | testbed host, or any Linux machine on the lab Wi-Fi |
| `server_monitor.py` | Samples the server process's CPU (as % of **one** core) and memory | the server (testbed host or the Windows laptop) |
| `calibrate.py` | Scores how fast a machine runs the server's per-heartbeat work, so results from one machine can be scaled to another | both machines you want to compare |
| `results/` | One folder per run: `report.md`, `report.json`, optional py-spy flame graphs | |

Baseline numbers and what they show: [`BASELINE.md`](BASELINE.md).

---

## In the testbed — `testbed/testbed.sh scale`

```bash
testbed/testbed.sh up                                   # if it isn't running
testbed/testbed.sh scale                                # 100, 250, 500, 1000 PCs, 10 dashboards
testbed/testbed.sh scale --steps 500,1000,2000,4000 --lab-size 60 --profile
testbed/testbed.sh scale --steps 1000 --storm           # finish with every PC reconnecting at once
testbed/testbed.sh scale --steps 1000 --dead-dashboards 1   # a dashboard laptop's lid is shut
testbed/testbed.sh scale --steps 1000 --freeze-server 12    # the server stalls for 12 s
```

What the simulated fleet does, so results can be read against a real lab:

- **PCs** behave like the agent. Each has its own TCP connection and sends a heartbeat every 5 s,
  from a random phase.
  - It sends a software report of `--packages` names (default 1,500) when it boots, then every
    `--software-interval` s (default 300, the agent's `LABSENSE_SOFTWARE_SCAN_INTERVAL`). It sends
    no extra report on reconnect.
  - Half the PCs are in use, 30 % idle and 20 % logged out, and each changes every
    `--churn-minutes` on average.
- **Dashboards** (`--dashboards`, default 10) are open WebSockets. `--measured` of them (default 3)
  time every heartbeat. `--stalled-dashboards` stay connected but stop reading, like a frozen tab.
  `--dead-dashboards` open in each step and then go silent without closing, like a laptop whose lid
  was shut.
- **REST probes** poll `/health` and one lab's PCs every 2 s, and `/labs` every 10 s. Every 10 s
  they also search all software for a package only one lab has, like "which lab has MATLAB?". Each
  lab's PCs report a shared inventory plus one package of their own.
- `--storm` drops every PC's connection at once after the last step, like an access point
  rebooting.
- `--freeze-server` then pauses the server process (SIGSTOP) while the PCs keep sending.

Every option after `scale` goes to `loadgen.py` (`--help` lists them). `scale` first turns the host
into a **student-laptop-sized server** and puts everything back afterwards:

| Piece | During `scale` | Why |
|---|---|---|
| Backend | restarted exactly as `SETUP_WINDOWS_SERVER.md` runs it (no `--reload`, stock asyncio loop, `testbed/server.env`), pinned to **one CPU core** | the backend is one asyncio event loop, so one core is all it can use on any machine |
| PostgreSQL | its own core, 1 GB RAM | Docker Desktop on a laptop |
| Load generator | the remaining cores | so it never competes with the server it measures |

It also runs `calibrate.py` on the server's core and records the score in the report. The dev
backend (with `--reload`) comes back when the run ends or is interrupted, and the laptop-mode
server's log is kept as `testbed/.run/backend-scale.log`. PostgreSQL gets all cores back but keeps
its 1 GB memory cap until the next `testbed.sh down`.

Knobs (environment variables):

| Variable | Default | Meaning |
|---|---|---|
| `SCALE_SERVER_CPUS` | `0` | cores for the backend (`taskset` list) |
| `SCALE_SERVER_CPU_QUOTA` | unset | cap the backend at this fraction of its core (cgroup CPU quota) to stand in for a slower laptop: its `calibrate.py` score ÷ this host's, e.g. `0.5` |
| `SCALE_DB_CPUS` / `SCALE_DB_MEMORY` | `1` / `1g` | PostgreSQL's cores and memory |
| `SCALE_LOADGEN_CPUS` | `2`–last | cores for the load generator |

Load-test PCs are registered in their own labs, `lt01`, `lt02`, … (`--lab-size` PCs each). Lab A
and the fleet aren't touched. The labs are deleted when the run ends, and any left over from an
interrupted run are deleted before the next one starts. That way the database holds exactly this
run's PCs. `--keep-labs` keeps them, for example to look at the dashboard afterwards. Thousands of
leftover PCs slow down software search enough to make the E2E suite's search test time out.

### Wi-Fi conditions

`testbed/testbed.sh wifi good|campus|poor|off` routes the fleet through the Wi-Fi emulator
(`testbed/wifi_proxy.py`: latency, jitter, retransmission stalls, dropouts). To run a load test over
it, point the load generator at the emulator instead of the server:

```bash
testbed/testbed.sh wifi campus
testbed/testbed.sh scale --steps 500 --server 172.28.0.2
```

The emulator is one Python process, so it becomes the bottleneck long before the server does. Use it
for hundreds of PCs, not thousands.

---

## In the real lab

The same tools, against the Windows server, from another machine on the lab Wi-Fi.

**1. On the Windows server**, with the server running as usual
(`uvicorn app.main:app --host 0.0.0.0 --port 8000`, **no** `--reload`):

```bat
cd LabSense
backend\.venv\Scripts\pip install psutil
backend\.venv\Scripts\python testbed\loadtest\calibrate.py
backend\.venv\Scripts\python testbed\loadtest\server_monitor.py --match uvicorn --csv load.csv
```

Leave the monitor running, and press Ctrl-C after the test for its CPU and memory summary. If the
server is on battery, plug it in; power-saving modes can halve the score.

**2. On a Linux machine on the same Wi-Fi** (an Ubuntu lab PC is fine), from a checkout of the repo:

```bash
python3 -m venv ~/lt && ~/lt/bin/pip install 'websockets>=13'
ulimit -n 65535       # one socket per simulated PC; the default limit of 1024 stops at ~1000 PCs
~/lt/bin/python testbed/loadtest/loadgen.py --server <server LAN IP> --steps 100,250,500
```

The run adds labs `lt01`, `lt02`, … to the real database and deletes them again when it finishes.
If a run is interrupted, the next run deletes them first. The default admin and student seed logins
are used; pass `--admin-email`, `--student-email` and `--password` if yours differ.

What carries over from the testbed, and what doesn't:

- Everything over the network does: same protocol, same server code, same reports, and the Wi-Fi
  is real.
- `--monitor-pid`, `--db-container` and `--profile` need the server on the same machine. Use
  `server_monitor.py` on the server instead.
- `--dead-dashboards` needs Linux, root and nftables on the machine running the load generator.
  `--freeze-server` needs the server on the same machine. In the lab, the equivalent test is to
  shut a real laptop's lid with the dashboard open while the load runs.
- One load generator machine can simulate a few thousand PCs. If the report warns that the load
  generator was overloaded (its own event-loop lag p95 over 100 ms), the latencies it reports are
  partly its own. Split the load across two machines.

### Comparing machines

`calibrate.py` prints a score in heartbeats per second on one core. Results scale roughly with it.
For example, if the testbed scores 42,000 and passes 6,000 PCs at 40 % CPU, a laptop scoring 21,000
would be expected to run the same load at ~80 % CPU. That estimate covers the server's own
processing. It doesn't cover the network, the database disk, or anything else running on the laptop.

---

## Reading a report

Each step's row in `report.md`:

| Column | Meaning | SLO (default) |
|---|---|---|
| heartbeats/s, dashboard msgs/s | load offered: PCs ÷ 5 s, and what every dashboard together received | |
| latency p50 / p95 / p99 / max | from a simulated PC sending a heartbeat to a dashboard showing it | p95 ≤ 1 s, p99 ≤ 3 s |
| delivered | share of heartbeats every timing dashboard received | ≥ 97 % |
| false flips: dashboard / REST (while connecting) | in-use PCs the server marked Available although they kept sending heartbeats. "dashboard" counts the flip messages a dashboard received. "REST" counts in-use PCs that `/labs/{lab}/pcs` reported as Available, which still works while broadcasts are stuck. The bracket repeats both for the time that step's PCs were connecting. | 0 |
| REST p95 | `/health`, `/labs/{lab}/pcs`, `/software/search`, `/labs`, polled the way people using the dashboard do | ≤ 1 s |
| server CPU avg / max | % of **one** core: 100 % means the event loop is saturated, whatever the core count | ≤ 80 % |
| server RSS, DB CPU | memory of the backend; PostgreSQL CPU from `docker stats` | |

The largest step meeting every SLO is the run's capacity. With `--profile`, `flame-<N>pcs.svg` shows
where the backend spent its time at that step (open it in a browser and click to zoom). It's the
place to start before changing code for scale.

### Before and after a code change

1. `testbed/testbed.sh scale --steps <the steps you care about> --profile --label before`
2. Make the change. The dev backend reloads it.
3. Run the same command with `--label after`, and compare the two `report.md` files.

Repeated runs on the cloud testbed agreed on server CPU to within a few percent, but the host's own
speed varied by up to ~10 % between runs (it is a shared machine). That's why every report records
the `calibrate.py` score: if it moved, scale the results by it before comparing.
