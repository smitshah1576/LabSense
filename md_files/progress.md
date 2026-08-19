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
- Heartbeat staleness detection design confirmed: 15-second grace period (~3 missed heartbeats), falls back to Available. Implementation still outstanding — see Not Started.

## In Progress
- Agent implementation (D-Bus event handling, telemetry loop).
- Custom TCP protocol implementation.
- Backend state manager and WebSocket push.
- Database schema (proposed version in `architecture.md`, not yet finalized with the team).
- Frontend dashboard.

## Not Started
- **Heartbeat staleness checking** — the server-side timer logic implementing the confirmed 15-second grace period. This is called out repeatedly as critical and is currently the biggest design-to-implementation gap.
- **Software discovery & search** — agent scan logic (`dpkg`/`pip list`, no venv scanning), `installed_software` DB column, backend filter endpoints (global + lab-wise), frontend search bars at both levels.
- **Lab State** — `labs`, `master_timetables`, `slot_cancellations` tables; the Open/Occupied/Closed computation logic; frontend lab-state display.
- **Damage report flow** — `damage_reports` table, student submission UI, admin review/approval UI.

## Open Questions / Risks
1. **Heartbeat authentication.** The raw TCP protocol has no described auth/integrity check. Worth a deliberate decision before the viva, since "how do you stop a spoofed heartbeat on the lab LAN" is a plausible question either way.
2. **Locked-state duration.** The current "In Use" rule treats "screen locked" as an unconditional trigger alongside idle-time and CPU thresholds. Worth confirming with the team whether a screen that's been locked for a long time should eventually roll over to Available (as idle time does), or stay In Use indefinitely — the current definition doesn't specify.

## Recent Corrections
- Windows Fast Startup / sleep-signal behavior (see above) — corrected after being documented incorrectly earlier.
