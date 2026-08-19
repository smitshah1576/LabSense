# LabSense — Project Overview

## Identity
- **Name:** Smart Campus Lab Resource Allocator and Live Monitor ("LabSense")
- **Type:** Third-year CSE academic mini-project (Mumbai-area engineering college)
- **Team:** 3 members
- **Assessment:** Marks + viva defense. Every technical decision must be independently explainable under examination, not just functional — this is the primary design constraint on top of "does it work."

## Problem Statement
Small computer labs (4–5 machines) give students and staff no live signal of which machines are actually free. Without walking over and checking physically, there's no way to tell whether a PC is genuinely available, actively in use, asleep, or broken. LabSense closes that gap: a lightweight background agent on each lab PC reports live state to a central server over a custom network protocol, and a web dashboard shows real-time status.

## Course Mapping (confirmed)
| Feature | Course | Concept |
|---|---|---|
| Session/lock state monitoring via OS calls | CS206 | System calls, process/session state |
| Custom TCP heartbeat protocol | CS208 | Socket programming, fault tolerance |
| DB schema for machine state/history | CS204 | Relational schema design, indexing |
| System architecture (agent/server/client) | CE102 | OOP, backend architecture |

`abstract.md` (the original problem statement draft) referenced a much broader course list — CS201, CS202, CS203, CS207, CS301, CS302 in addition to the four above. That broader list was narrowed once the mentor-approved direction was locked in. **Use only the four courses above in report and viva materials.**

## Stakeholders
- **Mentor** — approved the current direction after rejecting an earlier idea as too easy.
- **Team (3)** — uses AI for code generation but must independently understand, debug, and defend every design decision in the viva.
- **Viva examiners** — every architectural choice needs a standalone justification, not just "it works."

## Project History / Pivots
1. Lecture summarizer — abandoned.
2. E-commerce price manipulation detector — abandoned.
3. Real-time scene sonification system for visually impaired users — scoped down, then dropped entirely once the college mandated syllabus-mapped projects.
4. → Landed on LabSense, explicitly mapped to CS204 / CS206 / CS208 / CE102.

## Scope Note — Read Before Using the Other Docs
Early ideation with Gemini (`Lab_Management_System_Design_-_Google_Gemini.md`) and the original `abstract.md` explored a much larger system: campus-wide, multi-lab, software/library search across machines, timetable-driven lab booking with row-locking, role-based booking permissions, and remote Wake-on-LAN. **That scope narrowed considerably, then partially expanded back.** The current confirmed architecture (see `architecture.md`) covers: live PC-state monitoring, lab-level state (Open/Occupied/Closed, driven by timetable + weekly cancellations — not full ad-hoc booking), and software/library search at both the lab and global (cross-lab) level. Remote Wake-on-LAN stays removed, and full ad-hoc booking with double-booking prevention stays deferred. See `memory.md` for the back-and-forth on exactly what moved where and why.

Treat the Gemini transcript and `abstract.md` as historical design exploration, not current spec. `mvp.md` draws a hard line between what's actually in scope now and what was explored earlier but is future work or dropped.
