# LabSense — MVP Feature Set

Features are split into **In Scope** and **Deferred / Future Work**. Do not mix these two lists in the report or viva — a feature that's future work presented as done (or vice versa) is exactly the kind of inconsistency a viva examiner will catch.

## In Scope (MVP)

### Agent
- Per-PC background agent (Python, `asyncio`, systemd service).
- Session/lock state via D-Bus subscription to `systemd-logind` (`PrepareForSleep`, `PrepareForShutdown`, lock events).
- CPU% and peripheral idle time via `psutil`.
- Graceful pre-suspend disconnection: `GOING_TO_SLEEP` message sent before the OS suspends.

### Networking
- Custom raw TCP heartbeat protocol (hand-rolled, no socket.io/abstraction library).
- ~5-second heartbeat interval carrying session state, lock state, idle time, CPU%.
- Heartbeat staleness detection: server-side, independent of event-triggered transitions. **Confirmed design:** a 15-second grace period (~3 missed heartbeats at the 5s interval) debounces minor drops; if no heartbeat arrives and reconnects within that window, the PC is treated as Powered Off/Disconnected and mapped to Available. **Not yet implemented** — see `progress.md`.

### Backend
- FastAPI, single uvicorn worker.
- In-process `PCStateManager` (dict + `asyncio.Lock`) as the live state cache.
- `asyncpg` for non-blocking Postgres access.
- Plain WebSocket push to frontend.
- JWT-based RBAC on REST and WebSocket endpoints.

### Database
- PostgreSQL.
- Schema covering machine state + transition history.
- Writes on state transitions only, not per heartbeat.

### Frontend
- React dashboard.
- Real-time PC state cards for a single lab (4–5 machines).
- Role-differentiated views: student, professor, admin.

### Lab State
- The lab itself (not just individual PCs) has 3 states: **Open**, **Occupied**, **Closed**.
- Determined primarily by the **master weekly timetable**, then overridden by **weekly cancellations** made by a professor or admin (a cancelled slot reopens the lab for that week without touching the underlying recurring timetable).
- This is narrower than full ad-hoc lab booking — see the Deferred table below for what's still out.

### PC State Model
- 4 states: **Available**, **In Use**, **Available/Sleep**, **Maintenance**.
- Maintenance is manual-only and suppresses automatic transitions while active. Two paths in:
  - **Admin or Professor** can directly tag/clear a PC as Maintenance.
  - **Student** can submit a damage report (not a direct tag); it routes to **Admin**, who reviews it and, if valid, sets the PC to Maintenance.

### Software Discovery & Search
- Agent scans each PC's installed software on a slower cadence than the heartbeat loop (software inventory doesn't need 5-second freshness).
- Software list stored per-machine in the database.
- **Both global (across all monitored labs) and lab-wise (within one lab) search are in scope** — reverses the earlier lab-local-only restriction; see `memory.md` for the history.
- Backend exposes filter/search endpoints at both levels; frontend has a corresponding search bar at both the all-labs view and the single-lab view.
- **Virtual environments are not scanned.** Only system-wide package managers (`dpkg`) and the global `pip` are checked — a package installed only inside a project-specific venv/conda env won't show up in search results. This is a stated, accepted limitation, not an oversight.
- *Re-added to scope* — was previously listed as deferred/out of scope; see `memory.md` for the history.

## Deferred / Future Work

These were explored in earlier design discussion (`abstract.md`, the Gemini transcript) but are **not** part of the current confirmed scope. Mentioning them in the report as "future work" is fine and expected; presenting them as implemented is not.

| Feature | Status | Note |
|---|---|---|
| Ad-hoc lab booking (outside the timetable) | Deferred | Timetable + weekly cancellation (see Lab State above) is in scope; a professor booking an *unallocated* slot on demand, with double-booking prevention, is not. Row-level locking (`SELECT ... FOR UPDATE`) already identified as the right approach when this is picked up |
| Audio/video idle detection | Deferred | Would extend the "In Use" composite condition via PipeWire/PulseAudio to catch silent-viewing edge cases |
| Multi-process horizontal scaling | Deferred | Current single-process `PCStateManager` design intentionally doesn't need this yet |
| Remote Wake-on-LAN | **Explicitly removed** | Was designed in detail, then deliberately cut — do not reintroduce without a fresh decision |
| Full multi-lab dashboard UI | Not yet specified | The data model now supports multiple labs (needed for Lab State + global search), and global search across labs is in scope — but a dedicated "browse all labs" landing page/UI beyond that hasn't been scoped |
