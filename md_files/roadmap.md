# LabSense — Roadmap

Target: live mentor demo within a ~3-week window, followed by viva defense.

## Phase 1 — Design (mostly complete)
- Architecture decisions locked: no Redis, no socket.io, Python retained, FastAPI + single uvicorn worker, raw TCP protocol, 4-state PC model, 3-state Lab model.
- Course mapping finalized (CS204, CS206, CS208, CE102).
- Deferred-feature boundary drawn (ad-hoc booking, audio/video detection, scaling, WoL, full multi-lab dashboard UI).

## Phase 2 — Core Implementation (current)
- Agent: D-Bus subscription (`dbus-next`) for session/lock/sleep events, `psutil` telemetry loop, systemd service packaging.
- Custom TCP protocol: heartbeat sender/receiver, `GOING_TO_SLEEP` message.
- Backend: `PCStateManager`, FastAPI routes, `asyncpg` wiring, WebSocket push.
- Database: schema creation (`pcs`, `labs`, `state_transitions`, `master_timetables`, `slot_cancellations`, `users`, `damage_reports`), transition-write logic.
- Frontend: basic dashboard rendering live PC cards.
- Software discovery: agent scan logic (`dpkg`/`pip list`, no venv scanning), `installed_software` storage, global + lab-wise backend filter endpoints, frontend search bars.
- Lab State: timetable/cancellation-driven Open/Occupied/Closed computation.
- Damage report flow: student submission → admin review → Maintenance tag.

## Phase 3 — Integration & Hardening
- **Heartbeat staleness detection** — implement the confirmed 15-second grace period (~3 missed heartbeats) as server-side timer logic. Priority item; currently the biggest gap between design and implementation.
- JWT RBAC wired end-to-end (REST + WebSocket), including the confirmed Maintenance permission split (Admin/Professor direct tag, Student damage-report-only).
- Resolve the open question on heartbeat authentication/integrity (or explicitly document it as accepted risk).
- Test full transition chain on real or VM'd machines: In Use → Available → Available/Sleep → wake → In Use, plus Maintenance override, plus Lab State transitions across a timetable boundary.

## Phase 4 — Demo Prep
- Script a repeatable demo across 4–5 machines: idle/active toggling, sleep/wake, dirty disconnect, maintenance tag/clear.
- Verify UI updates land within the heartbeat interval with no flicker on brief disconnects.

## Phase 5 — Viva Prep
- Written justification for each confirmed decision in `rules.md` / `memory.md` (no Redis, no socket.io, Python over Go/Rust, single uvicorn worker, write-on-transition DB).
- Rehearse the D-Bus subscriber framing and the in-memory-state-store terminology — these are the two most likely places to get tripped up on wording.
- Prepare an answer for the heartbeat auth gap, whichever way it's resolved.

## Post-MVP Roadmap (only if time/scope allows after core demo)
1. Heartbeat authentication (HMAC or similar) if not already folded into Phase 3.
2. Ad-hoc lab booking outside the timetable, with row-level locking (`SELECT ... FOR UPDATE`) for double-booking prevention.
3. Audio/video-aware idle detection (PipeWire/PulseAudio).
4. Multi-process scaling (would require revisiting the single-process `PCStateManager` decision).
5. Full multi-lab dashboard UI (browsing/comparing many labs at once, beyond the global search already in scope).
