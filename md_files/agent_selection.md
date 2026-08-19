# Antigravity Model Distribution — LabSense Implementation

Guiding principle: Opus 4.6 (Thinking) burns roughly 4x the credits of Gemini models due to hidden reasoning tokens, so it's reserved for tasks where correctness is load-bearing and cheap models would risk silent bugs. Everything repetitive/mechanical goes to Gemini Flash.

| Task | Model | Why |
|---|---|---|
| Agent core: asyncio event loop, dbus-next signal handling, inhibitor locks, systemd unit + crash recovery | **Claude Opus 4.6 (Thinking)** — sparingly | Race-condition-prone, low margin for silent bugs (missed `PrepareForSleep` = wrong state forever). This is exactly the "hard problem with many competing constraints" tier. |
| Backend: FastAPI state engine, WebSocket push, JWT RBAC, asyncpg queries, HMAC verification | **Claude Sonnet 4.6 (Thinking)** | Needs correctness and structure but isn't as adversarial as the agent's OS-signal races. Default workhorse for anything with real logic. |
| PC state transition logic (the 4-state cascade) | **Sonnet 4.6**, escalate to Opus only if a transition bug survives one debug pass | This is the crux of the viva defense — get it right the first time rather than patching later. |
| Postgres schema, migrations, JSONB+GIN indexing | **Sonnet 4.6** for the initial schema (must match locked architecture exactly), **Gemini Flash** for repetitive migration files after | Schema correctness is a one-shot cost; migrations after that are mechanical. |
| React frontend: PC/lab cards, live status grid, software search UI | **Gemini 3.6/3.5 Flash (High)** | Repetitive component work, high token volume, low reasoning depth. Antigravity's Chromium subagent for visual verification pairs naturally with Flash here. |
| Boilerplate: REST route scaffolding, Pydantic models, config files, `.env` setup | **Gemini Flash (Medium/Low)** | Pure pattern-matching, no design decisions. |
| Debugging a specific failing test/traceback | **Sonnet 4.6** first pass, **Opus 4.6** only if Sonnet loops without resolving | Most bugs are local; only escalate when the model is visibly stuck. |
| Docs, syllabus mapping writeup, viva prep notes | **Gemini Flash (Low)** | Zero reasoning load, pure text generation. |

