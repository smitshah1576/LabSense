# LabSense — Progress Snapshot

*Living document — update as implementation moves forward rather than rewriting wholesale. Flag what changed and what was dropped when editing.*

## Confirmed / Locked
- Agent stack: Python `asyncio`, unprivileged systemd service, `dbus-next` + `psutil`.
- Networking: custom raw TCP heartbeat, no abstraction libraries.
- Backend: FastAPI, single uvicorn worker, in-process `PCStateManager`, `asyncpg`, plain WebSockets, JWT RBAC.
- Database: PostgreSQL, write-on-transition only.
- Frontend: React, JWT RBAC, role-differentiated views (student/professor/admin).
- PC state model: 4 states (Available, In Use, Available/Sleep, Maintenance) with the composite "In Use" condition (session + idle/CPU/lock).
- No Redis, no socket.io, Python retained over Go/Rust — all with settled rationale (see `rules.md`).
- Windows Fast Startup does **not** send sleep signals to the agent — earlier documentation on this was wrong and has been corrected. (The agent process is already dead before the kernel hibernates.) Windows support is reference-only anyway, so this mainly matters for not repeating the error in the report.
- Remote Wake-on-LAN feature explicitly removed after being designed in detail.
- Software discovery & search re-added to MVP scope (previously deferred) — **now both global (all labs) and lab-wise search**, reversing the earlier lab-local-only restriction. Virtual environments are explicitly not scanned (system packages + global `pip` only).
- Lab State (Open/Occupied/Closed) added to MVP scope — driven by master timetable + weekly cancellations, narrower than full ad-hoc booking (still deferred).
- Maintenance permission model confirmed: Admin/Professor can directly tag/clear Maintenance; Student can only submit a damage report, routed to Admin for review.
- Heartbeat staleness detection: 15-second grace period (~3 missed heartbeats), falls back to Available. **Now implemented and verified** in `backend/app/state/pc_state_manager.py` (`_reset_staleness_timer` / `_staleness_timeout`) — a heartbeat at T+0 producing IN_USE was followed by an automatic IN_USE→AVAILABLE transition at exactly T+15s, with one `state_transitions` row written. Previously listed under Not Started; that entry was stale.

## In Progress
- Agent implementation (D-Bus event handling, telemetry loop) — running, but see Known Gaps below for the parts that don't yet behave as designed.
- Custom TCP protocol — implemented, now bidirectional: the server replies `REJECTED` when a `pc_id` isn't registered, instead of discarding the message.
- Backend state manager and WebSocket push — working end-to-end.
- Database schema — implemented in `docker/init.sql`; still not formally signed off with the team.
- Frontend dashboard — working; the "Available PCs" and "Campus Capacity" tiles read fields the API doesn't return (`capacity`, `available_pcs`) and are permanently 0.

## Setup & Testing Docs
- `SETUP_UBUNTU.md` — all-in-one Ubuntu deployment.
- `SETUP_WINDOWS_SERVER.md` — **backend/DB/frontend on Windows, agents on Ubuntu** (the current demo topology), including the network-reachability checks that distinguish a broken agent from blocked packets.
- `TESTING.md` — ordered test procedure T1–T11. `agent/test_heartbeat.py` sends one raw protocol frame with no agent involved, which is the fastest way to tell a network problem from an agent problem.

## Not Started
- Nothing from the original list remains wholly unstarted. Heartbeat staleness, software discovery & search, Lab State and the damage-report flow all now have working implementations end-to-end (verified against a live Postgres + backend + agent chain). What remains is the correctness work in Known Gaps below, plus hardening.

## Known Gaps (implemented, but not trustworthy yet)
These are all in the agent, all Linux-specific, and all invisible from the dashboard — which is exactly why they need checking before the demo rather than after.

1. **Idle-time detection does not work under the packaged systemd service.** `deploy_agent.sh` runs the agent as the unprivileged `labsense` system user, which has no `DISPLAY`/`XAUTHORITY`, so `xprintidle` cannot reach the logged-in user's X session. The `/dev/input/event*` fallback stats device-node mtimes, which do **not** update on input — it effectively reports seconds since boot. Net effect: the composite "In Use" rule degenerates to `session_active AND (cpu > threshold OR screen locked)`, and the idle-threshold half of the CS206 story does not hold as deployed. Running the agent in the foreground as your own user behaves differently (and better), so test whichever way you intend to demo.
2. **Screen-lock detection is probably inert.** `get_screen_locked()` needs a session bus the system user doesn't have. The logind `Lock`/`Unlock` signals only fire when something calls `LockSession`; GNOME's UI lock sets the session's `LockedHint` property instead. Verify by comparing `loginctl lock-session` against locking from the desktop UI. Robust fix is subscribing to `PropertiesChanged` on `LockedHint`.
3. **The sleep inhibitor lock may never actually be held.** `inhibitor.py` builds its `MessageBus` without `negotiate_unix_fd=True`; dbus-next only receives Unix file descriptors when that is negotiated, and `Inhibit()` returns its lock *as* an FD. `release()` then calls `os.close()` on whatever integer came back — an array index rather than a real descriptor would mean closing fd 0. Since the suspend guarantee is the most load-bearing claim in `architecture.md` §1, verify it directly: log `reply.unix_fds` alongside `reply.body`, then run test T7 in `TESTING.md` and confirm the card reads Available/Sleep rather than Available.
4. **Telemetry probes leak child processes.** The three `asyncio.wait_for(proc.communicate(), timeout=5)` calls in `telemetry.py` never `kill()` the subprocess on timeout. Worst case all three time out, making a heartbeat cycle ~15s against a 15s server grace period — enough to make cards flicker.

## Open Questions / Risks
1. **Heartbeat authentication.** The raw TCP protocol has no auth or integrity check on payloads. The server now validates that a `pc_id` is registered and rejects it otherwise, which stops accidental misconfiguration but is **not** a security control — anything on the LAN can still impersonate a registered PC. Worth a deliberate decision before the viva; "out of scope, and here's why" is defensible, leaving it unaddressed is not.
2. **Locked-state duration.** The current "In Use" rule treats "screen locked" as an unconditional trigger alongside idle-time and CPU thresholds. Worth confirming with the team whether a screen that's been locked for a long time should eventually roll over to Available (as idle time does), or stay In Use indefinitely — the current definition doesn't specify.
3. **Two `pc_id` conventions coexist.** Seed data uses `lab-a-pc-N`; `POST /admin/pcs` generates `<lab_id padded to 3><seq 2>` (e.g. `40801`). Both are currently live in the database. Pick one before the demo — an agent deployed against the wrong convention is now rejected loudly rather than silently, but it still won't report.
4. **The GIN index on `installed_software` is not used by the search queries.** `EXISTS (… jsonb_array_elements_text … ILIKE …)` cannot use it, so both search endpoints are sequential scans. `architecture.md` §6 claims the index backs them. Either correct the claim or switch exact-name lookups to the `@>` containment operator, which can use the index.

## Recent Corrections
- Windows Fast Startup / sleep-signal behavior (see above) — corrected after being documented incorrectly earlier.
- Heartbeat staleness was listed as "Not Started" long after it was implemented; corrected above.
- **Lab State was computed in UTC** against local wall-clock operating hours and timetable slots, so every lab read CLOSED for the entire working day (09:00 IST = 03:30 UTC) and no timetable slot ever matched. Fixed — the clock now comes from `settings.TIMEZONE` (`Asia/Kolkata`). Requires the `tzdata` package when the backend runs on Windows.
- **Unregistered `pc_id`s were dropped silently** by the TCP server. An agent with a mistyped or defaulted `pc_id` logged successful sends every 5 seconds while nothing reached the dashboard. The server now replies `REJECTED` and closes; the agent logs it as an error.
- **The agent exited with code 0 if its D-Bus task ended**, which `Restart=on-failure` ignores — so a D-Bus hiccup silently stopped heartbeats and left the service reading `inactive (dead)`. The D-Bus listener is now supervised and retried, only the heartbeat task is terminal, and the unit uses `Restart=always`.
