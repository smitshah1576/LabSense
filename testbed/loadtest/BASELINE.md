# Scale baseline — 1 October 2026

What a student-laptop-sized LabSense server handled in the testbed **before any scale work**, and
what to change first. Every number links to a run in `results/`. To check a change, re-run the
same command and compare the reports.

## Setup

- **Server.** The backend is pinned to one core of an Intel Xeon @ 2.1 GHz (cloud VM). It is started
  as on the Windows server: no `--reload`, stock asyncio loop.
  - `calibrate.py` scored 38,000–43,000 heartbeats/s across runs. Run it on the real laptop to see
    how that laptop compares.
  - PostgreSQL runs in Docker on its own core with 1 GB.
- **Fleet.** Each PC sends a heartbeat every 5 s, plus a 1,500-package software report at boot and
  every 300 s, as the agent does.
  - 50 % of PCs are in use, 30 % idle and 20 % logged out, and each changes every ~30 min.
  - Labs have 60 PCs.
  - PCs come online at up to 50 per second.
- **Watching.** 10 dashboards are open, 3 of them timing every heartbeat. REST probes run the way
  people using the dashboard do, including a software search every 10 s.

## Headline

Run: [`results/20261001-184541-baseline`](results/20261001-184541-baseline/report.md)

```
testbed/testbed.sh scale --steps 1000,2000,4000,6000 --storm --freeze-server 12 --profile --lab-size 60
```

| PCs | server CPU (avg / max, % of one core) | server memory | heartbeat → dashboard p95 / p99 | software search p95 | `/labs` p95 | DB CPU | result |
|---:|---|---:|---|---:|---:|---:|---|
| 1,000 | 12 % / 20 % | 204 MB | 2.4 / 6.3 ms | 0.9 s | 238 ms | 13 % | PASS |
| 2,000 | 19 % / 25 % | 334 MB | 3.7 / 9.0 ms | **1.9 s** | 229 ms | 21 % | FAIL |
| 4,000 | 31 % / 46 % | 591 MB | 7.4 / 38 ms | **3.6 s** | 350 ms | 31 % | FAIL |
| 6,000 | 43 % / 80 % | 851 MB | 36 / 222 ms | **6.3 s** | 485 ms | 44 % | FAIL |

- **By the SLOs, the server handles 1,000 PCs.** The first thing over its limit is software search,
  which takes more than a second from 2,000 PCs (finding 2).
- **Heartbeats themselves are not the problem.** At 6,000 PCs the server used under half of one
  core, and every heartbeat reached every dashboard. A lab of 60 PCs is a small fraction of that.
- **PCs reconnecting all at once is fine.** All 6,000 connections were dropped at once, like an
  access point rebooting. The server ran flat out for a few seconds (CPU p95 98 %), but every PC was
  back within 8.9 s (median 7.6 s), with no false flips.
- **What breaks before throughput is correctness when something goes wrong:** a dashboard that
  vanishes (finding 1), or a server that stalls (finding 3). Each comes with a command that
  reproduces it, which must pass once it's fixed.

## Findings, most important first

### 1. One dashboard that vanishes can freeze the whole server (from about 1,000 PCs)

Someone opens the dashboard on a laptop and shuts the lid, or walks out of Wi-Fi range. Shortly
afterwards, **every** dashboard stops updating and the server stops processing heartbeats. 15 s
later, the server's live state, which is what the REST API returns, has every in-use PC as
Available. The matching broadcasts and database writes are stuck behind the same send.

| Run | PCs | Heartbeats delivered | In-use PCs shown Available |
|---|---:|---:|---:|
| [`sleeping-laptop`](results/20261001-182335-sleeping-laptop/report.md) | 500 | 100 % | 0 |
| | 1,000 | 37 % | 24 of the probed lab's in-use PCs |

```
testbed/testbed.sh scale --steps 500,1000 --dead-dashboards 1 --lab-size 60
```

The 1,000-PC step failed the same way in all four runs made while investigating (36–40 %
delivered). In one of them, the dashboard that counts flips happened to be served before the dead
one, and it received 495 flip messages, one for nearly every in-use PC.

Why it happens:

1. `ConnectionManager.broadcast` (`backend/app/ws/manager.py`) awaits `send_text` on each dashboard
   in turn, and the TCP handler awaits the broadcast on every heartbeat (`backend/app/tcp/server.py`).
2. uvicorn's `send` waits while a connection's outgoing buffer is above 64 KiB. A laptop that has
   gone away never acknowledges anything, so that buffer never drains.
3. uvicorn's keepalive ping notices the dead peer after 20–40 s and closes the connection. But the
   close waits for the buffer to flush, so the waiting `send` isn't woken until the operating
   system gives up on the connection. On Linux that is ~15 min (`tcp_retries2`); on Windows it is
   set by its own retransmission limit.
4. The heartbeat handlers are all stuck behind that one `send`, so after 15 s the staleness timers
   mark every in-use PC Available.

Whether it triggers is a race. The dead connection's backlog (the kernel's send buffer plus
uvicorn's 64 KiB) has to fill before the keepalive closes it:

- Every heartbeat goes to every dashboard, so the backlog grows with the number of PCs.
- At 500 PCs (100 messages/s) the keepalive won. At 1,000 PCs (200/s) the backlog won.
- A dashboard that had been open for minutes before going silent did not freeze the server even at
  6,000 PCs. Linux had grown its send buffer by then. A freshly opened one is the worst case, and
  that is what `--dead-dashboards` simulates.
- Windows sizes its buffers differently. The real threshold needs a lab test: shut a laptop's lid
  with the dashboard open while `loadgen.py` runs 1,000 PCs.

A tab that stays connected but stops reading (a frozen browser) is harmless. Its machine keeps
acknowledging data, so nothing backs up on the server:
[`frozen-tab`](results/20261001-182701-frozen-tab/report.md) at 6,000 PCs delivered every heartbeat,
with no flips and the same server CPU as the baseline.

**Directions:**

- Never let one client's socket hold up the others or the heartbeat path. Give each dashboard its
  own bounded queue and sender task, and drop the dashboard when the queue is full.
- At minimum, wrap each send in `asyncio.wait_for(..., timeout)` and drop the dashboard on timeout.
- Then `--dead-dashboards 1` should pass at any step.

### 2. Software search reads every PC's whole inventory on every search

| PCs | `/software/search` p95 |
|---:|---:|
| 1,000 | 0.9 s |
| 2,000 | 1.9 s |
| 4,000 | 3.6 s |
| 6,000 | 6.3 s |

Search time grows in step with the number of PCs, and it is what limits the baseline to 1,000 PCs.
It is also most of the database's CPU (13–44 %).

`search_software_global` (`backend/app/routes/software.py`) runs `ILIKE` over
`jsonb_array_elements_text(installed_software)` for every PC: 9 million package names at 6,000 PCs.
No index can help that query. It then returns each matching PC's **whole** inventory, and Python
filters it again on the event loop. That is cheap when one lab matches, as in the probe. A search
for something every PC has, such as `firefox`, moves every inventory through Python and holds up
heartbeats meanwhile: 5.4 s end to end at 6,000 PCs, against 4.6 s for the SQL alone. The per-lab
search works the same way within a lab.

The E2E suite's search test waits 5 s, so it times out when thousands of load-test PCs are left in
the database. Load-test runs now delete their labs.

**Directions:**

- Store installed software as rows (`pc_id`, `package`) with a trigram index (`pg_trgm`), so
  `ILIKE '%term%'` uses the index.
- Or keep a table of distinct package names with a trigram index and join from it.
- Either way, return only the matching names.

### 3. A server stall makes PCs flip to Available even though their heartbeats arrived

The server process was paused while the PCs kept sending. Their heartbeats waited in the sockets,
none of them late.

| Run | PCs | Paused | In-use PCs flipped to Available on resume |
|---|---:|---:|---:|
| [`baseline`](results/20261001-184541-baseline/report.md) | 6,000 | 12 s | 1,710 of ~3,000 |
| [`server-freeze`](results/20261001-183459-server-freeze/report.md) | 1,000 | 12 s | 222 of ~500 |

```
testbed/testbed.sh scale --steps 1000 --freeze-server 12 --lab-size 60
```

Why it happens:

- Staleness is a 15 s `asyncio.sleep` per PC (`_staleness_timeout` in
  `backend/app/state/pc_state_manager.py`).
- After a stall, the timers that came due during it run before the backlog of waiting heartbeats is
  worked through. So every PC whose timer expired flips, then flips back a moment later. Each flip
  is broadcast and written to `state_transitions`.
- With a heartbeat every 5 s, about 40 % of the PCs have their 15 s run out during a 12 s stall
  itself. More run out while the server works through the backlog, which is bigger with more PCs.
- 12 s is shorter than the grace period, so none of these PCs was ever really silent for 15 s.
- The same race decides how the server degrades when it falls behind for any other reason: a CPU
  spike, finding 1, or a laptop that was briefly asleep. Instead of updates arriving late, PCs flip.

**Direction:** before declaring a PC stale, let pending input be processed first. One way is to
re-check once the event loop has caught up. Another is a periodic sweep that skips a round when
the loop has been lagging. Then `--freeze-server 12` should pass.

### 4. Every heartbeat is sent to every dashboard

**Cost.** Broadcasting is most of the server's work: about 53 % of the event loop's time at 1,000 PCs
and 77 % at 6,000, from the `--profile` flame graphs. Most of that is compressing (permessage-deflate)
and writing each heartbeat once per dashboard. The state logic itself (`handle_heartbeat`) is ~8 %,
and reading and parsing incoming messages 7–9 %.

**Dashboards matter as much as PCs.** The cost grows with PCs × dashboards:
[`50-dashboards`](results/20261001-183304-50-dashboards/report.md) at 1,000 PCs used 29 % of a core
(p95 6.3 ms), against 12 % with the baseline's 10 dashboards. That is 10,000 messages/s against
2,000.

**The browser pays too.** Each open tab receives PCs ÷ 5 messages per second, 1,200/s at 6,000 PCs,
whichever lab it is showing. The tab's own CPU isn't measured here.

**Directions:**

- Send each dashboard only the lab it is viewing (subscribe per lab).
- Send telemetry only when it changes, or batch it into one message per dashboard per second.
- Either also shrinks the backlog behind finding 1.

### 5. `GET /labs` makes three queries per lab

After search, `/labs` is the slowest REST call: p95 229–485 ms with the test's 100 labs, against
under 50 ms for `/labs/{lab}/pcs`.

`_enrich_lab` (`backend/app/routes/labs.py`) runs three queries per lab, one after another:
timetable, cancellations and PC list. That is 301 round trips for 100 labs. It also computes an
available-PC count that `LabResponse` doesn't include.

**Direction:** load the timetables, cancellations and PCs of all labs in three queries in total.
Either drop the unused count or return it.

### 6. Memory: each connection keeps its last software list alive (~120 KB per PC)

RSS grows linearly: 204 MB at 1,000 PCs to 851 MB at 6,000, about 130 KB per PC. Almost all of it
is software reports, although they are stored in PostgreSQL, not in memory:

| Run | PCs | Server RSS |
|---|---:|---:|
| [`baseline`](results/20261001-184541-baseline/report.md) | 2,000 | 334 MB |
| [`no-software-reports`](results/20261001-183047-no-software-reports/report.md) (`--packages 0`) | 2,000 | 92 MB |

That is about 120 KB per PC for the reports. Parsing one 1,500-package report produces 107 KB of
Python objects.

`handle_agent_connection` (`backend/app/tcp/server.py`) assigns `packages = msg.get("packages", [])`
and never releases it. The variable lives as long as the connection, so every connected PC holds its
last software list until the next report replaces it.

**Direction:** don't keep the list in a local. Pass `msg.get("packages", [])` straight to
`execute`, or `del packages` after it. Expect ~10 KB per PC afterwards. Affordable either way
on an 8 GB laptop, but it is a one-line fix.

### 7. Windows-only limits (not measurable here)

- **Socket limit.** `--reload` or `--workers` switch uvicorn on Windows to the selector event loop,
  which can't handle more than 512 sockets. That is about 500 PCs and dashboards combined.
  `SETUP_WINDOWS_SERVER.md` now says not to use them on the server.
- **Finding 1 on Windows.** How soon finding 1 triggers, and how long it lasts, depend on Windows'
  TCP buffers and retransmission limit. Test it in the lab, as described under finding 1.

## Fine so far

- **PostgreSQL** apart from search: the server writes only state transitions and software reports.
- **PCs coming online:** 50 per second, each sending its software report, caused no flips and no
  errors.
- **Reconnect storm:** see the headline.
- **The load generator** stayed far from its own limits: event-loop lag p95 under 3 ms at 6,000 PCs
  on two cores.
