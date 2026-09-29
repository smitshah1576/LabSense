# LabSense — Software Engineering Lab Diagrams

PlantUML sources for the SE lab experiments, drawn from how LabSense actually works: the code in
`agent/`, `backend/` and `frontend/`, and the rules in `PC_STATE_RULES.txt`. Rendered PNGs are in
[`rendered/`](rendered/). The supporting tables each lab manual asks for are below each experiment.

| Exp | Diagram | Source |
|---|---|---|
| 2 | Use case diagram | [`exp2-use-case.puml`](exp2-use-case.puml) |
| 3 | Class diagram: domain model + server | [`exp3-class-diagram.puml`](exp3-class-diagram.puml) |
| 3 | Class diagram: lab PC agent | [`exp3-class-diagram-agent.puml`](exp3-class-diagram-agent.puml) |
| 4 | Sequence: heartbeat to live dashboard | [`exp4-sequence-heartbeat.puml`](exp4-sequence-heartbeat.puml) |
| 4 | Sequence: clean suspend (GOING_TO_SLEEP) | [`exp4-sequence-clean-suspend.puml`](exp4-sequence-clean-suspend.puml) |
| 4 | Communication diagram (same interaction as the heartbeat sequence) | [`exp4-communication-heartbeat.puml`](exp4-communication-heartbeat.puml) |
| 5 | Activity: processing a heartbeat (swimlanes) | [`exp5-activity-heartbeat.puml`](exp5-activity-heartbeat.puml) |
| 5 | Activity: agent lifecycle (fork/join) | [`exp5-activity-agent.puml`](exp5-activity-agent.puml) |
| 6 | DFD level 0 (context diagram) | [`exp6-dfd-level0.puml`](exp6-dfd-level0.puml) |
| 6 | DFD level 1 | [`exp6-dfd-level1.puml`](exp6-dfd-level1.puml) |
| 7 | Work breakdown structure | [`exp7-wbs.puml`](exp7-wbs.puml) (generated) |
| 7 | Activity network with CPM values | [`exp7-activity-network.puml`](exp7-activity-network.puml) (generated) |
| 7 | Gantt chart | [`exp7-gantt.puml`](exp7-gantt.puml) (generated) |
| 7 | CPM table | [`exp7-cpm-table.md`](exp7-cpm-table.md) (generated) |
| UML | State machine: PC state | [`uml-state-machine-pc.puml`](uml-state-machine-pc.puml) |
| UML | Deployment diagram | [`uml-deployment.puml`](uml-deployment.puml) |

## Rendering

Every file is standalone, so you can paste it into [plantuml.com](https://www.plantuml.com/plantuml),
the VS Code *PlantUML* extension or any PlantUML tool. To regenerate all the PNGs (needs Java and
Graphviz; tested with PlantUML 1.2026.8):

```bash
docs/diagrams/render.sh            # uses `plantuml` if installed, else $PLANTUML_JAR
```

The Exp 7 files are generated from one task list. Change a duration or a dependency in
[`exp7_schedule.py`](exp7_schedule.py), then run `python3 docs/diagrams/exp7_schedule.py`. The
script recomputes the critical path and rewrites the WBS, network, Gantt and CPM table.

---

## System description

LabSense monitors campus computer labs in real time. A lightweight **agent** on every lab PC sends
a heartbeat every 5 s over a custom TCP protocol with its session state, screen lock, idle time and
CPU load. The **server** turns each heartbeat into one of four PC states (Available, In use,
Asleep, Maintenance), stores only the *transitions* in PostgreSQL, and pushes updates over
WebSockets to a **React dashboard**. Students use the dashboard to find a free PC or a lab with the
software they need. Professors can take a PC out of service or cancel a scheduled class. Admins
register labs and PCs, maintain the timetable and act on damage reports.

---

## Exp 2 — Use case model

**Actors**

| Actor | Kind | Role |
|---|---|---|
| Campus User | primary (abstract) | Anyone signed in: views labs, searches software, reports damage |
| Student | primary | Campus User |
| Professor | primary | Campus User who can also tag/clear maintenance and cancel a slot |
| Admin | primary | Professor who can also manage labs, PCs and the timetable, and resolve reports |
| Lab PC Agent | system | Sends heartbeats, sleep notices and software inventory |
| systemd-logind | secondary (OS) | Tells the agent that the PC is about to sleep or resume |
| Heartbeat Timer | time | Fires when a PC has been silent for 15 s |

The actor generalization mirrors the app's role checks: `isProfessor()` is also true for `ADMIN`.

**Use case specifications**

| | UC-01 View Labs & Live PC Status |
|---|---|
| Actors | Campus User |
| Description | See every lab's state (Open/Occupied/Closed) and every PC's live state and telemetry. |
| Pre-condition | User is logged in (includes *Log In*). |
| Main flow | 1. User opens the dashboard. 2. System loads labs, computing each lab's state from operating hours, today's timetable slots and cancellations. 3. System opens a WebSocket and sends a snapshot of all live PC states (includes *Receive Live Updates*). 4. User opens a lab and sees one card per PC. 5. Each heartbeat or state change updates the card without a page reload. |
| Alternate flow | 4a. User filters PCs by state (*Filter PCs by State* extends this use case). 3a. Token invalid or expired: requests and the WebSocket are refused (HTTP 401) and the user is returned to the login page. |
| Post-condition | The dashboard shows live state until the user leaves. |

| | UC-02 Send Heartbeat Telemetry |
|---|---|
| Actors | Lab PC Agent |
| Description | Report what is happening on a lab PC so the server can decide its state. |
| Pre-condition | Agent is running and the PC is registered. |
| Main flow | 1. Every 5 s the agent samples CPU %, session, lock and idle time. 2. Agent sends a length-prefixed JSON `HEARTBEAT`. 3. System checks the `pc_id` is registered (once per connection). 4. System applies the in-use rule (includes *Update PC State*): `IN_USE` if a session is active and input < 300 s, or CPU > 5 % for 3 heartbeats, or the screen has been locked < 15 min; otherwise `AVAILABLE`. 5. On a change, system writes a `state_transitions` row and pushes the update. 6. System restarts the PC's 15 s staleness timer. |
| Alternate flow | 3a. `pc_id` not registered: system replies `REJECTED` and closes the connection; the agent logs the error and retries with back-off. 4a. PC is in `MAINTENANCE`: telemetry is recorded but the state does not change. |
| Post-condition | The PC's live state reflects the latest telemetry. |

| | UC-03 Notify Clean Suspend |
|---|---|
| Actors | Lab PC Agent (primary), systemd-logind (secondary) |
| Description | Let the server tell a clean suspend apart from a dead network link. |
| Pre-condition | Agent holds a logind sleep-inhibitor lock. |
| Main flow | 1. logind signals `PrepareForSleep(true)`. 2. Agent sends `GOING_TO_SLEEP` and drains the socket. 3. Agent releases the inhibitor lock; the OS suspends. 4. System sets the PC to `AVAILABLE_SLEEP` and cancels its staleness timer. |
| Alternate flow | 4a. PC is in `MAINTENANCE`: the message is ignored. |
| Post-condition | Dashboard shows the PC as *Asleep*, not as a PC that silently vanished. |

| | UC-04 Report Damaged PC |
|---|---|
| Actors | Campus User (typically Student) |
| Main flow | 1. User chooses a PC and describes the problem. 2. System stores the report as `PENDING` with the reporter's id. |
| Alternate flow | 1a. PC does not exist: system returns *PC not found*. |
| Post-condition | Report is waiting in the admin's review queue. |

| | UC-05 Resolve Damage Report |
|---|---|
| Actors | Admin |
| Main flow | 1. Admin opens the pending reports. 2. Admin approves or dismisses a report. 3. System records the decision, resolver and time. |
| Extension | On approval, *Tag PC Maintenance* runs: the PC moves to `MAINTENANCE`, which suppresses automatic changes until cleared. |
| Post-condition | Report is `APPROVED` or `DISMISSED`. |

| | UC-06 Tag / Clear PC Maintenance |
|---|---|
| Actors | Professor, Admin |
| Main flow | 1. User toggles maintenance on a PC. 2. System sets the PC to `MAINTENANCE` (or back to `AVAILABLE`), updates the `pcs` row and pushes the change. |
| Alternate flow | 1a. A Student tries it: HTTP 403, *Operation not permitted*. |

---

## Exp 3 — Class specifications

| Class | Purpose | Key operations |
|---|---|---|
| `User` | A signed-in person with one role | `login()`, `hasRole()` |
| `Lab` | A computer lab with operating hours | `computeState(now)`: CLOSED outside hours, OCCUPIED during an uncancelled slot, else OPEN |
| `PC` | A registered workstation and its persisted state | `setMaintenance()`, `updateSoftware()`, `matchingPackages()` |
| `StateTransition` | Audit row written only when a PC's state changes | — |
| `TimetableSlot` | A weekly recurring class in a lab | `isActiveAt(now)`, `cancelFor(date, by)` |
| `SlotCancellation` | Cancels one slot for one date only | — |
| `DamageReport` | A user's report about a faulty PC | `approve()`, `dismiss()` |
| `HeartbeatServer` | Accepts agent TCP connections and decodes frames | `handleConnection()`, `isRegistered()`, `reject()` |
| `PCStateManager` | In-memory store of live PC states; applies the rules | `handleHeartbeat()`, `handleGoingToSleep()`, `setMaintenance()` |
| `PCLiveState` | One PC's live telemetry and rule inputs | `recordTelemetry()`, `isInUse(now)` |
| `ConnectionManager` | Fans updates out to every dashboard WebSocket | `broadcastPcUpdate()`, `broadcastPcHeartbeat()` |
| `AgentMessage` and subclasses | Wire-protocol messages: `Heartbeat`, `GoingToSleep`, `SoftwareReport`, `Rejected` | `encode()`, `decode()` |
| `HeartbeatClient` (agent) | The agent's TCP connection to the server | `sendHeartbeat()`, `sendGoingToSleep()`, `reconnectWithBackoff()` |
| `LogindMonitor` (agent) | Subscribes to logind sleep/shutdown/lock signals | `connectAndListen()`, `getSessionHints()` |
| `InhibitorLock` (agent) | Holds the logind sleep-delay lock | `acquire()`, `release()` |
| `InputIdleTracker` (agent) | Idle time from `/dev/input` event timing | `idleSeconds()` |

**How each relationship type is used**
- **Composition:** used where the database cascades deletes. `Lab`◆`PC`, `Lab`◆`TimetableSlot`, `TimetableSlot`◆`SlotCancellation`, `PC`◆`StateTransition`, `PC`◆`DamageReport`. `PCStateManager`◆`PCLiveState` too, since live states exist only inside the manager.
- **Aggregation:** `ConnectionManager`◇`DashboardSession`. Browser sessions exist independently of the manager.
- **Inheritance:** the four protocol message types specialise `AgentMessage`.
- **Dependency:** the transition callback: `PCStateManager` ⇢ `StateTransition` («creates») and ⇢ `ConnectionManager` («notifies»).

---

## Exp 4 — Interaction diagrams

**Participants (heartbeat sequence)**

| Participant | Type | Responsibility |
|---|---|---|
| Lab PC Agent | actor | Samples telemetry and sends heartbeats |
| `:HeartbeatServer` | boundary | Reads frames, validates the `pc_id`, rejects unknown PCs |
| `:PCStateManager` | control | Applies the in-use rule, grace period and maintenance override |
| `:PCLiveState` | entity | Holds one PC's telemetry, CPU window and lock time |
| `:ConnectionManager` | control | Broadcasts to every open dashboard |
| PostgreSQL | data store | `pcs` and `state_transitions` tables |
| Dashboard | actor | Renders live PC cards |

**Message table (main success path; numbers match the rendered sequence diagram)**

| No. | Sender | Receiver | Message | Purpose |
|---|---|---|---|---|
| 2 | Lab PC Agent | HeartbeatServer | `HEARTBEAT(pc_id, telemetry)` | Report the PC's current activity |
| 3 | HeartbeatServer | PostgreSQL | `SELECT 1 FROM pcs WHERE pc_id = ?` | Validate the PC (once per connection) |
| 5 | HeartbeatServer | Lab PC Agent | `REJECTED(pc_id, reason)` | Tell a misconfigured agent why it is ignored |
| 7 | HeartbeatServer | PCStateManager | `handleHeartbeat(pc_id, telemetry)` | Start state evaluation |
| 8 | PCStateManager | PCLiveState | `recordTelemetry(telemetry, now)` | Update telemetry, CPU window and lock time |
| 10 | PCStateManager | PCLiveState | `isInUse(now)` | Evaluate the in-use rule |
| 13 | PCStateManager | ConnectionManager | `broadcastPcUpdate(pc_id, newState)` | Push the state change |
| 15 | PCStateManager | PostgreSQL | `INSERT state_transitions; UPDATE pcs` | Persist the change (only on a change) |
| 19 | HeartbeatServer | ConnectionManager | `broadcastPcHeartbeat(pc_id, state, telemetry)` | Push fresh telemetry |
| 20 | ConnectionManager | Dashboard | `pc_update {…}` | Update the PC card live |
| 22 | PCStateManager | PCStateManager | `stalenessTimeout(pc_id)` | After 15 s of silence, fall back to AVAILABLE |

The communication diagram shows the same interaction as a network of objects. Its nested numbers
(1, 1.2, 1.2.3, 1.2.3.1 …) show which call triggers which.

---

## Exp 5 — Activity diagrams

**Swimlane responsibilities (heartbeat processing)**

| Swimlane | Activities |
|---|---|
| Lab PC Agent | Collect telemetry, send heartbeat, log rejection, wait 5 s |
| Heartbeat Server | Read frame, validate `pc_id`, send REJECTED, broadcast telemetry |
| PC State Manager | Record telemetry, apply maintenance override and in-use rule, restart 15 s timer |
| Database | Look up `pc_id`, insert transition, update `pcs.current_state` |
| Dashboard | Receive `pc_update`, re-render the PC card |

**Decision table**

| Registered? | Maintenance? | Session active? | Input < 300 s, or CPU > 5 % ×3, or locked < 15 min? | Action | Outcome |
|---|---|---|---|---|---|
| No | – | – | – | Send REJECTED, close connection | Heartbeat discarded |
| Yes | Yes | – | – | Record telemetry only | Stays MAINTENANCE |
| Yes | No | No | – | Evaluate rule | AVAILABLE |
| Yes | No | Yes | Yes | Evaluate rule | IN_USE |
| Yes | No | Yes | No | Evaluate rule | AVAILABLE |

The agent-lifecycle diagram uses fork/join because those tasks really are concurrent: the agent
runs its heartbeat, D-Bus and software-scan tasks as parallel asyncio tasks, plus a shutdown
watcher. The join is an **or**: the agent stops when the heartbeat task ends or a stop signal
arrives, then cancels the rest. In the server-side diagram the database write and the broadcast run
one after the other in the code, so they are drawn in sequence rather than as a fork.

---

## Exp 6 — Data flow diagrams

**External entities (level 0)**

| Entity | Data into LabSense | Data out of LabSense |
|---|---|---|
| Lab PC Agent | Heartbeat telemetry every 5 s, sleep notice before suspend, software inventory every 5 min | Rejection notice if its `pc_id` is not registered |
| Student | Login credentials, software search queries, damage reports | Auth token, live lab and PC status, software search results |
| Professor | Login credentials, maintenance toggles, slot cancellations | Auth token, live lab and PC status, lab timetable |
| Admin | Login credentials, lab & PC registration, timetable entries, report decisions, maintenance toggles | Auth token, live lab and PC status, pending damage reports |

**Level 1 processes**

| Process | Function |
|---|---|
| 1.0 Authenticate User | Check credentials against D1 and issue a JWT carrying the user's role |
| 2.0 Ingest Agent Messages | Decode TCP frames, reject unregistered PCs, store software inventory |
| 3.0 Determine PC State | Apply the in-use rule, 15 s grace period, sleep and maintenance; record transitions |
| 4.0 Publish Live Lab & PC Status | Compute lab state and push live PC states to dashboards |
| 5.0 Administer Labs, PCs & Timetable | Register labs/PCs, maintain the weekly timetable, record one-off cancellations |
| 6.0 Manage Damage Reports & Maintenance | Accept reports, record admin decisions, apply maintenance |
| 7.0 Search Software | Find PCs (campus-wide or per lab) that have a package installed |

The diagrams balance: every level-0 flow for each entity appears at level 1.

**Data dictionary**

Notation: `=` is composed of, `+` and, `[a | b]` one of, `{x}` zero or more, `( )` optional.

| Name | Type | Definition |
|---|---|---|
| heartbeat telemetry | flow | `type="HEARTBEAT" + pc_id + session_active + screen_locked + idle_seconds + cpu_percent + timestamp` |
| sleep notice | flow | `type="GOING_TO_SLEEP" + pc_id + timestamp` |
| software inventory | flow | `type="SOFTWARE_REPORT" + pc_id + {package_name} + timestamp` |
| rejection notice | flow | `type="REJECTED" + pc_id + reason` |
| frame | flow | `length (4-byte big-endian unsigned int) + UTF-8 JSON payload` |
| login credentials | flow | `email + password` |
| auth token | flow | `JWT = sub(email) + user_id + role + exp` (60 min) |
| live lab & PC status | flow | `{lab_id + lab_name + lab_state} + {pc_id + pc_state + cpu_percent + idle_seconds + session_active + screen_locked + last_heartbeat_at}` |
| software query | flow | `q (≥ 2 characters) + (lab_id)` |
| software search results | flow | `{pc_id + lab_id + lab_name + {matching_package}}` |
| damage report | flow | `pc_id + issue_description` |
| report decision | flow | `report_id + [APPROVED \| DISMISSED]` |
| maintenance toggle | flow | `pc_id + is_maintenance` |
| slot cancellation | flow | `timetable_id + cancelled_for_date` |
| lab & PC registration | flow | `lab_id + lab_name + operating_start + operating_end`, or `lab_id` (the PC id is generated) |
| timetable entries | flow | `lab_id + day_of_week (1–7) + start_time + end_time + (course_code)` |
| pc_state | element | `[AVAILABLE \| IN_USE \| AVAILABLE_SLEEP \| MAINTENANCE]` |
| lab_state | element | `[OPEN \| OCCUPIED \| CLOSED]` |
| role | element | `[STUDENT \| PROFESSOR \| ADMIN]` |
| D1 Users | store | `@user_id + email + password_hash + full_name + role` |
| D2 Labs | store | `@lab_id + lab_name + operating_start_time + operating_end_time` |
| D3 PCs | store | `@pc_id + lab_id + current_state + is_maintenance + last_heartbeat_at + {installed_software}` |
| D4 State Transitions | store | `@id + pc_id + from_state + to_state + transitioned_at` |
| D5 Master Timetable | store | `@timetable_id + lab_id + day_of_week + start_time + end_time + course_code` |
| D6 Slot Cancellations | store | `@cancellation_id + timetable_id + cancelled_for_date + cancelled_by` |
| D7 Damage Reports | store | `@report_id + pc_id + reported_by + issue_description + status + created_at + (resolved_by + resolved_at)` |
| M1 Live PC State | store (memory) | `{pc_id + pc_state + telemetry + cpu_samples(last 3) + locked_since + last_heartbeat_at}` |

---

## Exp 7 — WBS, activity network, CPM and Gantt

The plan starts on **27 Jul 2026** and is anchored to the repository's real history. Integration
(task P) ends on 21 Sep, the "state transition fixes" commit. The E2E testbed (task Q) ends on
28 Sep, the day it was committed. The Gantt chart marks today (29 Sep 2026) and shades finished work.

- **Critical path:** A → B → C → D → J → L → P → Q → R → S → T → W → V
- **Project duration:** 95 days, 27 Jul to 29 Oct 2026
- **Largest slack:** G, UML & DFD modelling (71 days); N, timetable & lab state (26 days)

The full table with ES, EF, LS, LF and slack for every task is in
[`exp7-cpm-table.md`](exp7-cpm-table.md).

---

## Extra UML diagrams

- **State machine (PC state):** the four states, with guards taken from `PCStateManager`. The
  *Automatic* superstate shows that maintenance overrides every agent-driven state, and that only
  an explicit "clear maintenance" leaves it.
- **Deployment:** which process runs where (lab PCs, lab server, browsers), and the protocol and
  port on every link.
