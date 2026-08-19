# LabSense — Rules & Conventions

Constraints and conventions for anyone (human or AI) working on this project. Feasibility and viva-defensibility are the primary filters for every decision — not just "does it work," but "can the team explain why they built it this way."

## Architecture Constraints
- **No Redis.** Single-process architecture eliminates the multi-process state-sharing problem Redis exists to solve. Adding it would introduce a failure mode without a corresponding benefit — don't reintroduce it without a reason that changes this premise (e.g., actually going multi-process).
- **No socket.io / no WebSocket abstraction at the agent layer.** Raw TCP is a deliberate requirement to earn CS208 (socket programming) credit. Don't substitute a library "for convenience" — it removes the thing being demonstrated.
- **Python only, no Go/Rust.** The team must debug and defend all code in the viva. AI-generated code in a language the team doesn't fluently read is indefensible under examination, regardless of any performance argument for switching.
- **Single uvicorn worker, not multi-worker.** Keeps the in-process state manager valid; going multi-worker would silently break the "no Redis" reasoning above.
- **Never block the agent's event loop.** The agent is single-threaded `asyncio` — the D-Bus pre-sleep listener only runs between `await` points, so any blocking call anywhere stalls it too. Concretely: use `psutil.cpu_percent(interval=None)`, not `interval=1`, which blocks the whole loop for a full second on every call. If a blocking call can't be avoided, offload it with `loop.run_in_executor()` rather than calling it inline. See `architecture.md` §1 for the full concurrency model.

## Documentation & Viva Conventions
- **Scope discipline.** Every feature is either explicitly in-scope (MVP) or explicitly future work. Never mix the two lists — see `mvp.md`. Mixing them is what creates confusion in reports and under viva questioning.
- **Terminology for `PCStateManager`:** call it an "in-memory state store," "application-level cache," or "single-process in-memory cache." Never imply it's Redis or a distributed cache.
- **D-Bus/logind framing:** the agent is a *subscriber* to logind's broadcast signals, not the implementer of its own session tracking. State this precisely — it's a common point of confusion and an easy correctness check for an examiner.
- **Incremental updates over full rewrites.** When revising these docs, change only the affected section and note what changed and what was dropped, rather than regenerating a file wholesale.
- **Composite idle definition is the source of truth for "In Use":** session active AND (peripheral idle below threshold OR CPU above threshold OR screen locked). Audio/video-based detection is a known gap, explicitly deferred — don't fold it into the MVP definition without a scope decision.

## Working Style (for AI assistants on this project)
- Default to short, direct, technically precise answers — no filler, no unnecessary scaffolding.
- Once a direction is chosen, give full execution detail (real code, real schema, concrete steps) rather than general guidance.
- Present options broadly when a decision is still open; narrow to one recommendation once it's settled.
- Flag gaps and inconsistencies directly rather than smoothing over them — this team wants to know where the design is weak before a viva examiner finds it.
