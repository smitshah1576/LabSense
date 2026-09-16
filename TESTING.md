# LabSense — Test Procedure

Ordered so each test depends only on the ones before it. **Run T1–T3 before touching the real
agent** — together they tell you whether a problem is in the network, the protocol, or the agent,
which is otherwise the hardest thing to distinguish in this system.

Throughout, `10.234.237.199` is the Windows server's LAN IP — substitute your own (Phase 0.1 of
[`SETUP_WINDOWS_SERVER.md`](SETUP_WINDOWS_SERVER.md)).

---

## T1 — LAN reachability

**Run on:** Ubuntu · **Prerequisite:** backend running

```bash
nc -vz 10.234.237.199 9000
```

**Pass:** `succeeded`.
**Fail → `Connection refused`:** host reachable, nothing listening. Backend not started, or bound to
`127.0.0.1` — check `netstat -ano | findstr ":9000"` on Windows.
**Fail → hangs/times out:** packets are being dropped. Windows Firewall rule missing (Phase 0.4), or
Wi-Fi client isolation (Phase 0.8).

---

## T2 — Raw protocol probe (no agent involved)

**Run on:** Ubuntu · **This is the single most useful test in this file.**

```bash
python3 agent/test_heartbeat.py 10.234.237.199
```

It opens a raw TCP connection, sends exactly one length-prefixed JSON `HEARTBEAT` for `lab-a-pc-1`,
and reports whatever comes back.

**Pass:** `SENT, no reply — the server accepted it`, and the `lab-a-pc-1` card on the dashboard turns
**IN_USE** within a second, then falls back to **Available** about 15 s later when the staleness
timer fires.

If T2 passes, the network, the wire protocol, the state manager, the database and the WebSocket push
are all working — any remaining problem is in the agent. If it fails, nothing downstream is worth
debugging yet.

---

## T3 — Unregistered `pc_id` is reported, not swallowed

**Run on:** Ubuntu

```bash
python3 agent/test_heartbeat.py 10.234.237.199 bogus-pc
```

**Pass:** the script prints a `REJECTED` reply and explains how to register the PC; the backend logs
`Rejecting unregistered pc_id 'bogus-pc'` at ERROR.

This is worth running once deliberately. Before this was fixed the server discarded these silently,
so a mistyped `--pc-id` produced an agent that logged successful sends every five seconds while
nothing ever reached the dashboard — the exact failure that is hardest to diagnose from the agent
side.

---

## T4 — Mock agent, five PCs

**Run on:** Ubuntu or Windows

```bash
python3 agent/mock_agent.py 10.234.237.199 9000
```

**Pass:** all five cards in Lab A update, each at roughly 5 s intervals, with plausible CPU/idle
values and states flipping between IN_USE and Available.

---

## T5 — Real agent

**Run on:** Ubuntu, after deploying per Phase 4

```bash
sudo journalctl -u labsense-agent -f
```

**Pass:** `Connected to backend at 10.234.237.199:9000 (pc_id=lab-a-pc-1)`, then `Heartbeat #1 sent
(cpu=…, idle=…s, active=…, locked=…)`, then about one heartbeat line per minute.
`systemctl status labsense-agent` stays `active (running)`.

**No heartbeat lines at all?** Redeploy with `--log-level DEBUG` to see every send. If `Connected`
appears but no heartbeats follow, the telemetry probes are hanging — see the `xprintidle` caveat in
Phase 4.

---

## T6 — Heartbeat staleness / the 15-second grace period

**Run on:** Ubuntu

```bash
sudo systemctl stop labsense-agent
```

**Pass:** the card flips to **Available** roughly 15 s later (not instantly, not never), the backend
logs `heartbeat stale after 15s`, and exactly one new row appears in `state_transitions` — a single
transition, not a flapping sequence.

Restart the agent and confirm the card recovers.

```sql
SELECT pc_id, from_state, to_state, transitioned_at
FROM state_transitions ORDER BY transitioned_at DESC LIMIT 10;
```

This also exercises the agent-supervision fix: a deliberate stop and a crashed D-Bus listener used to
look identical, because either one ended the whole agent process with exit code 0.

---

## T7 — `GOING_TO_SLEEP` and the clean-suspend distinction

**Run on:** an Ubuntu client with a real desktop session

```bash
sudo systemctl suspend
```

**Pass:** the card reads **Available/Sleep**, *not* plain Available. That difference is the whole
point of the pre-suspend message: it is what lets the server tell a clean suspend from a dead
network link.

**If it reads plain Available,** the `GOING_TO_SLEEP` message did not arrive before the NIC went
down. The likely cause is the sleep inhibitor lock never actually being held — see the note in
`md_files/progress.md`. Verify by logging `reply.unix_fds` alongside `reply.body` in
`agent/labsense_agent/inhibitor.py`. **Check this before the demo**, since the suspend guarantee is
one of the architecture's headline claims.

---

## T8 — Maintenance override

**Run on:** browser, as `admin@labsense.dev`

Tag a PC as Maintenance while its agent is still sending heartbeats.

**Pass:** the state stays **MAINTENANCE** regardless of what the agent reports, and no automatic
transitions are written. Telemetry (CPU, idle) still updates underneath. Clearing maintenance returns
it to Available, and normal transitions resume.

Also confirm the permission split: a professor can tag/clear; a student cannot, and only sees the
damage-report path.

---

## T9 — Lab state across a timetable boundary

**Run on:** browser + database

Insert a timetable row that spans *right now* in local time (not UTC):

```sql
INSERT INTO master_timetables (lab_id, day_of_week, start_time, end_time, course_code)
VALUES ('lab-a', EXTRACT(ISODOW FROM CURRENT_DATE)::int, '00:00', '23:59', 'TEST');
```

**Pass:** Lab A reads **OCCUPIED**. Cancelling that slot for today (as professor or admin) flips it
to **OPEN**, and next week's recurring slot is untouched.

Then set the lab's operating hours to a window that excludes now, and confirm **CLOSED** wins over
everything else.

Remember to delete the test row afterwards.

---

## T10 — Software discovery and search

**Run on:** browser, after an agent has been connected for one scan interval (300 s by default)

Search for `python3` in both the campus-wide bar and the single-lab bar.

**Pass:** real package names come back (`python3`, `python3-minimal`, …). If you see single
characters instead, the JSONB column is being read as a string — that indicates the pool's jsonb
codec is not registered.

To avoid waiting five minutes during a rehearsal, set `LABSENSE_SOFTWARE_SCAN_INTERVAL=30` on the
agent.

---

## T11 — WebSocket fan-out

**Run on:** two browsers (ideally two different machines)

Log in on both, then change one PC's state.

**Pass:** both update within the heartbeat interval without a refresh, and neither flickers during a
brief agent restart.

---

## Database queries worth having ready

Recent transitions — the audit trail behind the dashboard:

```sql
SELECT pc_id, from_state, to_state, transitioned_at
FROM state_transitions ORDER BY transitioned_at DESC LIMIT 20;
```

Current persisted state per PC:

```sql
SELECT pc_id, lab_id, current_state, last_heartbeat_at FROM pcs ORDER BY pc_id;
```

Proof that writes happen on transition, not per heartbeat — leave an agent running for five minutes
(≈60 heartbeats) and confirm the transition count has grown by only a handful:

```sql
SELECT count(*) FROM state_transitions;
```

---

## Demo rehearsal

Running T1 → T11 cleanly in one sitting, against at least two Ubuntu agents, is the demo rehearsal
called for in `md_files/roadmap.md` Phase 4. The sequence worth showing live is: idle→active
toggling, sleep/wake, a dirty disconnect (pull the network cable rather than stopping the service —
it exercises the grace period rather than a clean shutdown), and a maintenance tag/clear.
