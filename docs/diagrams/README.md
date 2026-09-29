# LabSense — SE Lab Diagrams

High-level PlantUML diagrams for the Software Engineering lab experiments, one per diagram type.
Rendered images are in [`rendered/`](rendered/).

| Exp | Diagram | Source |
|---|---|---|
| 2 | Use case diagram | [`exp2-use-case.puml`](exp2-use-case.puml) |
| 3 | Class diagram | [`exp3-class-diagram.puml`](exp3-class-diagram.puml) |
| 4 | Sequence diagram | [`exp4-sequence-diagram.puml`](exp4-sequence-diagram.puml) |
| 4 | Communication diagram | [`exp4-communication-diagram.puml`](exp4-communication-diagram.puml) |
| 5 | Activity diagram | [`exp5-activity-diagram.puml`](exp5-activity-diagram.puml) |
| 6 | DFD level 0 (context diagram) | [`exp6-dfd-level0.puml`](exp6-dfd-level0.puml) |
| 6 | DFD level 1 | [`exp6-dfd-level1.puml`](exp6-dfd-level1.puml) |
| 7 | Gantt chart | [`exp7-gantt-chart.puml`](exp7-gantt-chart.puml) |
| — | State diagram (PC status) | [`uml-state-diagram.puml`](uml-state-diagram.puml) |

Each file is standalone: paste it into [plantuml.com](https://www.plantuml.com/plantuml) or the VS
Code PlantUML extension, or run `docs/diagrams/render.sh` (needs PlantUML, Java and Graphviz).

## The system

LabSense shows, in real time, which computers in the campus labs are free. An agent on each lab PC
sends a heartbeat every 5 seconds. The server works out whether the PC is Available, In use, Asleep
or under Maintenance and pushes that to a web dashboard. Students find free PCs and search for
installed software. Professors mark PCs for maintenance and cancel timetable slots. Admins manage
labs and PCs and review damage reports.

## Diagram notes

- **Use case:** four actors. The Lab PC Agent is a system actor. Admin inherits every Professor
  use case. *View Live Lab & PC Status* includes *Log In*; *Tag PC for Maintenance* extends
  *Review Damage Reports* when a report is approved.
- **Class:** Student, Professor and Admin specialise User. A Lab contains PCs (aggregation) and
  owns its timetable slots (composition). The Agent monitors one PC and sends Heartbeats.
- **Sequence / communication:** the same scenario in both. A student opens a lab page, then live
  heartbeats keep the PC cards up to date. Unregistered PCs are rejected.
- **Activity:** how one heartbeat becomes a status update, in three swimlanes (Agent, Server,
  Dashboard), with decisions for registration, maintenance and whether someone is using the PC.
- **DFD:** level 0 shows LabSense with its four external entities. Level 1 splits it into six
  processes and four data stores, and balances with level 0.
- **Gantt:** nine tasks across four phases, from 27 Jul to the final demo on 29 Oct 2026, with
  today (29 Sep) marked.
- **State diagram:** the four PC states and what moves a PC between them.

## Data dictionary (DFD)

| Name | Contents |
|---|---|
| PC status | PC id + CPU usage + idle time + session active + screen locked |
| rejection notice | PC id + reason |
| login details | email + password |
| live lab status | lab name + lab state + each PC's status |
| software search / search results | package name / matching PCs and labs |
| damage report | PC id + problem description |
| maintenance request | PC id + on/off |
| slot cancellation | timetable slot + date |
| lab & PC details | lab name + opening hours, or a new PC for a lab |
| report decision | report id + approved / dismissed |
| D1 Users | name + email + password + role |
| D2 PCs | PC id + lab + status + installed software |
| D3 Labs & Timetable | lab id + name + opening hours + weekly slots + cancellations |
| D4 Damage Reports | report id + PC id + description + status |
