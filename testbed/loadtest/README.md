# LabSense scale testing

How many lab PCs and open dashboards can one server handle, and what breaks first? These tools
measure it against the real Windows server from another machine on the lab Wi-Fi, so a code change
can be measured before and after on identical terms.

| File | What it does | Runs on |
|---|---|---|
| `loadgen.py` | Simulates N lab PCs (one TCP connection each, the real agent wire protocol) and M dashboards (WebSockets), ramps through `--steps`, measures and writes a report | any Linux machine on the lab Wi-Fi |
| `server_monitor.py` | Samples the server process's CPU (as % of **one** core) and memory | the Windows server |
| `calibrate.py` | Scores how fast a machine runs the server's per-heartbeat work, so results from one machine can be scaled to another | both machines you want to compare |
| `results/` | One folder per run: `report.md`, `report.json`, optional py-spy flame graphs | |

Baseline numbers and what they show: [`BASELINE.md`](BASELINE.md). They were measured in a cloud test
environment that isn't part of this repository; the comment in `.gitignore` says how to restore it.

---

## What the simulated fleet does

So results can be read against a real lab:

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

`loadgen.py --help` lists every option.

Load-test PCs are registered in their own labs, `lt01`, `lt02`, … (`--lab-size` PCs each). Existing
labs aren't touched. The load-test labs are deleted when the run ends, and any left over from an
interrupted run are deleted before the next one starts. That way the database holds exactly this
run's PCs. `--keep-labs` keeps them, for example to look at the dashboard afterwards.

---

## Running it against the lab server

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

The default admin and student seed logins are used; pass `--admin-email`, `--student-email` and
`--password` if yours differ.

Options that need more than the network:

- `--monitor-pid`, `--db-container`, `--profile` and `--freeze-server` need the server on the same
  machine as the load generator. In the lab, use `server_monitor.py` on the server instead.
- `--dead-dashboards` needs Linux, root and nftables, and only works when the load generator runs
  on the server's own machine. In the lab, the equivalent test is to shut a
  real laptop's lid with the dashboard open while the load runs.
- One load generator machine can simulate a few thousand PCs. If the report warns that the load
  generator was overloaded (its own event-loop lag p95 over 100 ms), the latencies it reports are
  partly its own. Split the load across two machines.

### Comparing machines

`calibrate.py` prints a score in heartbeats per second on one core. Results scale roughly with it.
For example, if a machine that scores 42,000 runs 6,000 PCs at 40 % CPU, a laptop scoring 21,000
would be expected to run the same load at ~80 % CPU. `BASELINE.md` records the score of the machine
it was measured on. That estimate covers the server's own
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

1. Run `loadgen.py` with the steps you care about and `--label before`, with `server_monitor.py`
   running on the server.
2. Make the change and restart the server.
3. Run the same command with `--label after`, and compare the two `report.md` files and monitor
   summaries.

Use the same server, the same Wi-Fi and the same time of day for both runs. If the server's
`calibrate.py` score changed in between, scale the results by it before comparing.
