# LabSense — Architecture

## System Diagram
```
Agent (per PC) --custom TCP heartbeat--> Backend (FastAPI, 1 uvicorn worker) --WebSocket--> Frontend (React)
                                                  |
                                              asyncpg
                                                  |
                                             PostgreSQL
```
One agent process runs per lab PC. All agents talk to a single backend instance. The backend holds live state in memory and persists only transitions to Postgres, then pushes updates to connected browsers over WebSockets.

## 1. Agent
- **Language/runtime:** Python, single-threaded `asyncio` event loop — not a multi-threaded design.
- **Deployment:** unprivileged **systemd service**, one instance per lab PC. Linux is the actual target platform.
- **Session/lock state:** subscribes to **systemd-logind** D-Bus signals via `dbus-next` (not `dbus-python` — `dbus-next` is asyncio-native, so it runs as a coroutine on the same event loop instead of needing its own thread/GLib mainloop) — specifically `PrepareForSleep`, `PrepareForShutdown`, and session/lock events.
  - **Viva-relevant distinction:** the agent is a *subscriber* to logind's broadcast signals. It does not implement its own session-tracking logic. Get this framing right — it's the difference between "we built session detection" (wrong) and "we correctly integrated with the OS's existing session broker" (right, and more defensible).
- **Telemetry:** `psutil` for CPU% and peripheral idle time.
- **Windows:** a `pywin32`-based approach exists as documented reference only — it is not implemented. Don't present it as working in the report.
- **Pre-suspend handling:** on `PrepareForSleep`, the agent sends a `GOING_TO_SLEEP` message before the connection drops. This is what lets the backend distinguish a clean suspend from a dead/disconnected heartbeat — without it, sleep and network failure look identical to the server.

### Concurrency Model
One process, one thread, one event loop, two long-running `asyncio` Tasks:
- **Heartbeat Task** — every ~5s, gathers `psutil` telemetry and writes it over the raw TCP connection via `asyncio` streams.
- **D-Bus Task** — `dbus-next` connection awaiting `PrepareForSleep` / `PrepareForShutdown` / lock signals, coexisting with the heartbeat task on the same loop.

This replaces an earlier three-OS-thread design (one thread each for the socket client, the polling loop, and the OS power-message pump) that made sense for blocking libraries like `dbus-python`, but is unnecessary once every library in use is asyncio-native.

**Suspend guarantee:** the agent takes a **systemd-logind inhibitor lock** (`Inhibit("sleep", ...)`) at startup. On `PrepareForSleep(true)`, it writes `GOING_TO_SLEEP`, awaits the flush, then releases the lock — the OS cannot proceed to suspend until the lock is released, so there's no race between the network write and the OS tearing down the interface. (An earlier version of this design tried to win that race by using a synchronous call instead of an async one; that doesn't actually provide a guarantee — the inhibitor lock is what does.)

**Known risk — don't block the loop:** cooperative scheduling means nothing else runs until the current coroutine hits an `await`. The natural way to write the CPU check, `psutil.cpu_percent(interval=1)`, blocks the entire loop for a full second on every call — including the D-Bus task, which stops listening for the sleep signal for that second. Use `psutil.cpu_percent(interval=None)` (compares against the last call instead of sleeping) or offload to `loop.run_in_executor()` if a blocking call is unavoidable. This has to be a deliberate line in the agent code, not the default first draft.

### Linux idle-time detection — implementation options
- **X11 desktops:** `xprintidle` or the XScreenSaver extension.
- **Non-X11 / headless / minimal window manager:** read raw input events from `/dev/input/event*`, or fall back to session presence checks (`who` / `w`).
- Confirm with the team which of these matches what the demo lab machines actually run before committing to one.

## 2. Network Protocol
- **Custom raw TCP.** No socket.io, no WebSocket library, no abstraction layer at the agent layer. This is a deliberate requirement to earn CS208 credit — the socket handling has to be visibly hand-rolled, not delegated to a library.
- Heartbeat sent every ~5 seconds. Payload carries:
  - session state
  - lock state
  - idle time
  - CPU %
- Special message: `GOING_TO_SLEEP`, sent pre-suspend for graceful disconnection (see above).
- **Open question — not yet decided:** the protocol as currently scoped has no described authentication or integrity check on heartbeat payloads. On a shared lab LAN this is a plausible viva question ("what stops another machine from spoofing a heartbeat?"). Worth a deliberate decision — even "out of scope, here's why" is a defensible answer — rather than leaving it unaddressed.

## 3. Backend
- **FastAPI**, single **uvicorn worker** — deliberate, not a shortcut (see `rules.md` for why multi-worker was rejected).
- **Live state cache:** `PCStateManager` — a plain Python `dict` guarded by an `asyncio.Lock`.
  - **Terminology matters:** in report/viva contexts, call this an "in-memory state store," "application-level cache," or "single-process in-memory cache." Never call it "Redis" or imply a distributed cache — that invites a question you don't want ("why not just use Redis then?") when the honest answer is you deliberately didn't need it.
- **DB access:** `asyncpg` (non-blocking).
- **Frontend push:** plain **WebSockets** — no socket.io on this side either.
- **Auth:** JWT-based RBAC enforced on both REST and WebSocket endpoints.

## 4. Database
- **PostgreSQL.**
- Writes triggered **only on state transitions**, not on every 5-second heartbeat tick. Write volume scales with actual events, not polling frequency — worth stating explicitly in the report as a deliberate performance decision.
- **Proposed schema** (not finalized — confirm with team before implementing):
```sql
CREATE TYPE pc_state_enum AS ENUM ('AVAILABLE', 'IN_USE', 'AVAILABLE_SLEEP', 'MAINTENANCE');
CREATE TYPE lab_state_enum AS ENUM ('OPEN', 'OCCUPIED', 'CLOSED');
CREATE TYPE user_role_enum AS ENUM ('STUDENT', 'PROFESSOR', 'ADMIN');
CREATE TYPE damage_report_status_enum AS ENUM ('PENDING', 'APPROVED', 'DISMISSED');

CREATE TABLE users (
    user_id  SERIAL PRIMARY KEY,
    role     user_role_enum NOT NULL
    -- auth fields (email/password hash/etc.) as needed
);

CREATE TABLE labs (
    lab_id                TEXT PRIMARY KEY,
    lab_name              TEXT NOT NULL,
    operating_start_time  TIME NOT NULL DEFAULT '08:00:00',
    operating_end_time    TIME NOT NULL DEFAULT '20:00:00'
);

CREATE TABLE pcs (
    pc_id             TEXT PRIMARY KEY,
    lab_id            TEXT REFERENCES labs(lab_id),
    current_state     pc_state_enum NOT NULL DEFAULT 'AVAILABLE',
    is_maintenance    BOOLEAN NOT NULL DEFAULT FALSE,
    last_heartbeat_at TIMESTAMPTZ,
    installed_software JSONB NOT NULL DEFAULT '[]'::jsonb
);

-- Speeds up "which PCs have X installed" filter queries (both global and lab-wise)
CREATE INDEX idx_pcs_software ON pcs USING GIN (installed_software);

CREATE TABLE state_transitions (
    id               SERIAL PRIMARY KEY,
    pc_id            TEXT REFERENCES pcs(pc_id),
    from_state       pc_state_enum,
    to_state         pc_state_enum,
    transitioned_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Master recurring weekly schedule
CREATE TABLE master_timetables (
    timetable_id  SERIAL PRIMARY KEY,
    lab_id        TEXT REFERENCES labs(lab_id) ON DELETE CASCADE,
    day_of_week   INT CHECK (day_of_week BETWEEN 1 AND 7),
    start_time    TIME NOT NULL,
    end_time      TIME NOT NULL,
    course_code   TEXT
);

-- One-off cancellations of a recurring slot for a specific week,
-- made by a professor or admin. Presence of a row here overrides
-- the matching master_timetables slot for that date only.
CREATE TABLE slot_cancellations (
    cancellation_id     SERIAL PRIMARY KEY,
    timetable_id        INT REFERENCES master_timetables(timetable_id) ON DELETE CASCADE,
    cancelled_for_date  DATE NOT NULL,
    cancelled_by        INT REFERENCES users(user_id)
);

-- Student damage reports, reviewed by Admin before a PC is tagged Maintenance
CREATE TABLE damage_reports (
    report_id           SERIAL PRIMARY KEY,
    pc_id                TEXT REFERENCES pcs(pc_id) ON DELETE CASCADE,
    reported_by          INT REFERENCES users(user_id),
    issue_description     TEXT,
    status                damage_report_status_enum NOT NULL DEFAULT 'PENDING',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_by           INT REFERENCES users(user_id),
    resolved_at           TIMESTAMPTZ
);
```

## 5. Frontend
- **React.**
- JWT-based RBAC middleware.
- Role-differentiated views for **student, professor, admin**.
  - **Maintenance permissions (confirmed):** Admin and Professor can directly tag/clear a PC as Maintenance. Student can only submit a damage report, which routes to Admin for review and action.

## 6. Software Discovery & Search
- The agent scans installed software on a periodic, slower cadence than the 5-second heartbeat loop (e.g. every few minutes) — software inventory doesn't need the same freshness as session state, so it shouldn't ride the same fast loop or protocol message.
- Scan sources (Linux target):
  - System packages: `dpkg -l` (or `rpm -qa` if the lab image is RPM-based).
  - Python libraries: **global `pip list` only.**
  - **Virtual environments (venv, conda, etc.) are explicitly not scanned.** A package installed only inside a project-specific env won't be detected. This is a stated, accepted limitation — flag it as such if asked in viva, don't present it as a gap that was missed.
  - Anything installed to a non-standard path outside the above won't be picked up either — if that matters for the demo machines, it needs an explicit config file listing extra paths to check rather than trying to guess install locations.
- Scan results are sent to the backend and written to `pcs.installed_software` (JSONB — see Database section), independent of the heartbeat stream.
- **Search is available at two levels:**
  - **Global** — across all labs in the `labs` table (relevant once more than one lab is registered).
  - **Lab-wise** — within a single lab's machines.
  - Both are backed by the same GIN index on `installed_software`; the only difference is whether the query filters by `lab_id`.
- Frontend has a search bar at both the all-labs view and the single-lab view.

## 7. Lab State
- 3 states: **Open**, **Occupied**, **Closed** — a property of the lab as a whole, separate from individual PC states.
- **Priority logic:**
  1. **Closed** if the current time falls outside `labs.operating_start_time`–`operating_end_time`.
  2. **Occupied** if within operating hours AND a `master_timetables` row matches the current day/time AND there's no matching `slot_cancellations` row for today's date.
  3. **Open** otherwise — within operating hours, with no active (or a cancelled) timetable slot.
- Cancellations are professor/admin-only, apply to a single date, and don't touch the underlying recurring `master_timetables` row — next week's slot is unaffected.
- Deliberately narrower than full booking: there's no path here for a professor to reserve a lab outside the timetable. See `mvp.md` for that boundary.

## PC State Model (4 states — confirmed)
| State | Definition |
|---|---|
| **Available** | No active session, or session idle beyond threshold, or PC off/asleep past the 15-second grace period (see Fault Tolerance below) |
| **In Use** | Session active **AND** at least one of: peripheral idle time below threshold, CPU above threshold, screen locked |
| **Available/Sleep** | Agent sent `GOING_TO_SLEEP` before disconnecting — this is what distinguishes a clean suspend from a dead/disconnected heartbeat |
| **Maintenance** | Manual-only flag. Suppresses all automatic agent-driven transitions until cleared |

A richer "composite idle" condition was explored early on (detecting audio/video playback via PipeWire/PulseAudio, to catch the "watching a lecture with zero peripheral input" edge case). That's a real gap in the definition above but is **explicitly deferred to future work** — don't fold it into the MVP condition.

## Fault Tolerance
**Confirmed design — 15-second grace period.** The server independently tracks heartbeat freshness, separate from event-triggered transitions (a heartbeat arriving, or a `GOING_TO_SLEEP` message arriving). If a PC misses its expected heartbeat (~3 missed ticks at the 5s interval, i.e. ~15 seconds) and hasn't reconnected in that window, it's treated as Powered Off/Disconnected and mapped to **Available** — same outcome as a clean shutdown, since for a student looking for a free seat, the distinction doesn't matter. If the last signal received *was* `GOING_TO_SLEEP`, the PC is already in Available/Sleep and this fallback doesn't apply.

This debounces the failure mode that matters most in practice: a 2–3 second Wi-Fi/LAN stutter shouldn't flip a card's state and flip it back. The grace period is what keeps a real disconnect distinguishable from that kind of noise.

**Not yet implemented** — the timer logic itself still needs building; the design (15s / 3 missed heartbeats / maps to Available) is confirmed. This remains the biggest design-to-implementation gap and a likely direct viva probe.
