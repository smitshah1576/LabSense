"""End-to-end tests of the server: TCP protocol -> state rules -> DB -> REST/WS.

Test IDs in brackets refer to TESTING.md.  Every test uses its own freshly
registered PC, so tests are independent and never disturb the fleet.
"""

from __future__ import annotations

import time
import uuid

import httpx
import pytest
from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect as ws_connect

from conftest import (
    CPU_WINDOW, HEARTBEAT_TIMEOUT, IDLE_THRESHOLD, LAN_ORIGIN, WS_URL,
    db_fetch, local_now, transitions, wait_until,
)


# -- plumbing -------------------------------------------------------------------

def test_backend_and_frontend_are_served(client):
    assert client.get('/health').json() == {'status': 'ok'}
    page = httpx.get('http://localhost:5173/', trust_env=False, timeout=10)
    assert page.status_code == 200 and '<div id="root">' in page.text


# -- auth & RBAC ----------------------------------------------------------------

def test_every_seed_role_can_log_in(client):
    for email, role in [('admin@labsense.dev', 'ADMIN'), ('prof@labsense.dev', 'PROFESSOR'),
                        ('student@labsense.dev', 'STUDENT')]:
        body = client.post('/auth/login', json={'email': email, 'password': 'password123'}).json()
        assert body['user']['role'] == role and body['access_token']


def test_wrong_password_is_401(client):
    resp = client.post('/auth/login', json={'email': 'admin@labsense.dev', 'password': 'nope'})
    assert resp.status_code == 401


def test_api_requires_a_token(api):
    assert api.get('/labs', as_=None).status_code == 401


def _preflight(client, origin):
    return client.options('/auth/login', headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    })


def test_dashboard_opened_from_the_lan_may_call_the_api(client):
    """A teammate on the Wi-Fi opens http://<server LAN IP>:5173, so the browser
    sends that Origin. Unless it is in LABSENSE_CORS_ORIGINS every API call
    fails in the browser - the most likely "works on my machine" failure."""
    resp = _preflight(client, LAN_ORIGIN)
    assert resp.status_code == 200 and resp.headers.get('access-control-allow-origin') == LAN_ORIGIN, (
        f'{LAN_ORIGIN} is not an allowed origin: add it to LABSENSE_CORS_ORIGINS '
        f'(testbed/server.env here, backend\\.env on the Windows server)')


def test_unlisted_origins_are_refused(client):
    resp = _preflight(client, 'http://evil.example:5173')
    assert resp.status_code == 400 and 'access-control-allow-origin' not in resp.headers


def test_websocket_rejects_bad_tokens():
    for token in ('not-a-jwt', ''):
        with pytest.raises(InvalidStatus) as err:
            with ws_connect(f'{WS_URL}?token={token}', open_timeout=5, proxy=None):
                pass
        assert err.value.response.status_code in (401, 403)


def test_only_admin_can_register_pcs(api, lab):
    for role in ('student', 'professor'):
        assert api.post('/admin/pcs', as_=role, json={'lab_id': lab}).status_code == 403


def test_registered_pc_ids_follow_lab_convention(api, lab):
    first = api.ok('POST', '/admin/pcs', json={'lab_id': lab})['pc_id']
    second = api.ok('POST', '/admin/pcs', json={'lab_id': lab})['pc_id']
    assert first.startswith(lab) and second.startswith(lab)
    assert int(second[len(lab):]) == int(first[len(lab):]) + 1


# -- wire protocol ----------------------------------------------------------------

def test_unregistered_pc_is_rejected_loudly(agent_for):
    """[T3] An unknown pc_id gets a REJECTED reply and a hang-up, not silence."""
    agent = agent_for(f'bogus-{uuid.uuid4().hex[:6]}')
    agent.heartbeat()
    reply = agent.recv()
    assert reply['type'] == 'REJECTED' and reply['pc_id'] == agent.pc_id
    assert agent.recv() is None  # server closed the connection


def test_deregistered_pc_is_rejected(api, pc, agent_for):
    api.ok('DELETE', f'/admin/pcs/{pc}')
    agent = agent_for(pc)
    agent.heartbeat()
    assert agent.recv()['type'] == 'REJECTED'


def test_heartbeat_reaches_rest_websocket_and_db(api, lab, pc, agent_for, ws_for):
    """[T2] One heartbeat: IN_USE on REST and WS, persisted as one transition."""
    ws = ws_for('admin')
    agent = agent_for(pc)
    agent.heartbeat(session_active=True, idle_seconds=7, cpu_percent=42.0)

    live = api.wait_state(lab, pc, 'IN_USE')
    assert (live['idle_seconds'], live['cpu_percent'], live['session_active']) == (7, 42.0, True)
    assert live['last_heartbeat_at'] is not None

    # A transition pushes a bare {pc_id, state} first, then the telemetry snapshot.
    pushed = ws.wait_for(lambda m: m.get('type') == 'pc_update' and m.get('pc_id') == pc
                         and 'cpu_percent' in m)
    assert pushed['state'] == 'IN_USE' and pushed['cpu_percent'] == 42.0

    wait_until(lambda: transitions(pc) == [('AVAILABLE', 'IN_USE')], desc='transition row')
    row = db_fetch('SELECT current_state, last_heartbeat_at FROM pcs WHERE pc_id = $1', pc)[0]
    assert row['current_state'] == 'IN_USE' and row['last_heartbeat_at'] is not None


def test_only_transitions_are_persisted(api, lab, pc, agent_for):
    """Write-on-transition: ten identical heartbeats write one row, not ten."""
    agent = agent_for(pc)
    for i in range(10):
        agent.heartbeat(cpu_percent=20.0 + i)  # distinct values show when #10 lands
    wait_until(lambda: api.pc(lab, pc)['cpu_percent'] == 29.0, desc='all ten heartbeats processed')
    assert api.pc(lab, pc)['current_state'] == 'IN_USE'
    wait_until(lambda: transitions(pc) == [('AVAILABLE', 'IN_USE')], desc='exactly one row')
    time.sleep(0.5)  # give any stray extra writes time to land
    assert transitions(pc) == [('AVAILABLE', 'IN_USE')]


def test_silent_registered_pc_reads_available(api, lab, pc):
    live = api.pc(lab, pc)
    assert live['current_state'] == 'AVAILABLE' and live['last_heartbeat_at'] is None


# -- the IN_USE rule ----------------------------------------------------------------

def test_idle_session_is_available(api, lab, pc, agent_for):
    """Logged in but hands-off past the idle threshold, low CPU -> AVAILABLE."""
    agent = agent_for(pc)
    agent.heartbeat(idle_seconds=IDLE_THRESHOLD + 300, cpu_percent=1.0)
    wait_until(lambda: api.pc(lab, pc)['last_heartbeat_at'], desc='heartbeat processed')
    assert api.pc(lab, pc)['current_state'] == 'AVAILABLE'
    assert transitions(pc) == []


def test_fresh_input_counts_until_idle_threshold(api, lab, pc, agent_for):
    agent = agent_for(pc)
    agent.heartbeat(idle_seconds=IDLE_THRESHOLD - 1, cpu_percent=1.0)
    api.wait_state(lab, pc, 'IN_USE')
    agent.heartbeat(idle_seconds=IDLE_THRESHOLD, cpu_percent=1.0)
    api.wait_state(lab, pc, 'AVAILABLE')


def test_no_session_means_available_whatever_else(api, lab, pc, agent_for):
    """Greeter/login screen: no session outranks input, CPU and lock."""
    agent = agent_for(pc)
    for _ in range(CPU_WINDOW + 1):
        agent.heartbeat(session_active=False, screen_locked=True, idle_seconds=0, cpu_percent=95.0)
    wait_until(lambda: api.pc(lab, pc)['cpu_percent'] == 95.0, desc='heartbeats processed')
    assert api.pc(lab, pc)['current_state'] == 'AVAILABLE'


def test_cpu_counts_only_when_sustained(api, lab, pc, agent_for):
    """A CPU spike is ignored; CPU_WINDOW consecutive busy heartbeats mean IN_USE."""
    agent = agent_for(pc)
    idle = IDLE_THRESHOLD + 600
    for i in range(1, CPU_WINDOW):
        agent.heartbeat(idle_seconds=idle + i, cpu_percent=90.0)
        wait_until(lambda: api.pc(lab, pc)['idle_seconds'] == idle + i, desc=f'heartbeat {i}')
        assert api.pc(lab, pc)['current_state'] == 'AVAILABLE', f'IN_USE after only {i} busy heartbeat(s)'

    agent.heartbeat(idle_seconds=idle + CPU_WINDOW, cpu_percent=90.0)
    api.wait_state(lab, pc, 'IN_USE')

    agent.heartbeat(idle_seconds=idle + CPU_WINDOW + 1, cpu_percent=1.0)  # the job finished
    api.wait_state(lab, pc, 'AVAILABLE')


def test_locked_screen_holds_the_pc(api, lab, pc, agent_for):
    """Stepped out with the screen locked -> still IN_USE; unlocked and idle -> AVAILABLE."""
    agent = agent_for(pc)
    agent.heartbeat(screen_locked=True, idle_seconds=IDLE_THRESHOLD + 60, cpu_percent=1.0)
    live = api.wait_state(lab, pc, 'IN_USE')
    assert live['screen_locked'] is True
    agent.heartbeat(screen_locked=False, idle_seconds=IDLE_THRESHOLD + 65, cpu_percent=1.0)
    api.wait_state(lab, pc, 'AVAILABLE')


# -- sleep and the grace period ---------------------------------------------------------

@pytest.mark.slow
def test_dirty_disconnect_waits_out_the_grace_period(api, lab, pc, agent_for):
    """[T6] Silence -> still IN_USE inside the grace period, AVAILABLE after, one row."""
    agent = agent_for(pc)
    agent.heartbeat()
    api.wait_state(lab, pc, 'IN_USE')
    went_silent = time.monotonic()  # socket stays open: a hung PC, not a clean close

    time.sleep(HEARTBEAT_TIMEOUT - 5)
    assert api.pc(lab, pc)['current_state'] == 'IN_USE', 'flipped before the grace period ended'

    api.wait_state(lab, pc, 'AVAILABLE', timeout=10)
    assert time.monotonic() - went_silent >= HEARTBEAT_TIMEOUT - 1
    wait_until(lambda: transitions(pc) == [('AVAILABLE', 'IN_USE'), ('IN_USE', 'AVAILABLE')],
               desc='one row per transition, no flapping')

    agent.heartbeat()  # it comes back
    api.wait_state(lab, pc, 'IN_USE')


@pytest.mark.slow
def test_clean_suspend_is_available_sleep_and_survives_the_timer(api, lab, pc, agent_for):
    """[T7] GOING_TO_SLEEP -> AVAILABLE_SLEEP, which the staleness timer leaves alone."""
    agent = agent_for(pc)
    agent.heartbeat()
    api.wait_state(lab, pc, 'IN_USE')
    agent.going_to_sleep()
    agent.close()  # the NIC goes down
    api.wait_state(lab, pc, 'AVAILABLE_SLEEP')

    time.sleep(HEARTBEAT_TIMEOUT + 2)
    assert api.pc(lab, pc)['current_state'] == 'AVAILABLE_SLEEP'
    assert transitions(pc) == [('AVAILABLE', 'IN_USE'), ('IN_USE', 'AVAILABLE_SLEEP')]


# -- maintenance and damage reports -----------------------------------------------------

def test_maintenance_overrides_the_agent(api, lab, pc, agent_for):
    """[T8] Professor tags MAINTENANCE; heartbeats can't undo it; clearing resumes."""
    agent = agent_for(pc)
    agent.heartbeat(cpu_percent=10.0)
    api.wait_state(lab, pc, 'IN_USE')

    assert api.put(f'/pcs/{pc}/maintenance', as_='student',
                   json={'is_maintenance': True}).status_code == 403
    api.ok('PUT', f'/pcs/{pc}/maintenance', as_='professor', json={'is_maintenance': True})
    assert api.pc(lab, pc)['current_state'] == 'MAINTENANCE'

    agent.heartbeat(cpu_percent=77.0)
    wait_until(lambda: api.pc(lab, pc)['cpu_percent'] == 77.0, desc='telemetry still updating')
    assert api.pc(lab, pc)['current_state'] == 'MAINTENANCE'
    agent.going_to_sleep()
    time.sleep(0.3)
    assert api.pc(lab, pc)['current_state'] == 'MAINTENANCE'
    assert db_fetch('SELECT is_maintenance FROM pcs WHERE pc_id = $1', pc)[0]['is_maintenance']

    api.ok('PUT', f'/pcs/{pc}/maintenance', as_='admin', json={'is_maintenance': False})
    assert api.pc(lab, pc)['current_state'] == 'AVAILABLE'
    agent.heartbeat()
    api.wait_state(lab, pc, 'IN_USE')


_DOUBLE_WRITE = (
    'Known backend bug: PUT /pcs/{id}/maintenance and PUT /damage-reports/{id}/resolve '
    'insert a state_transitions row themselves after PCStateManager.set_maintenance() '
    'has already fired the transition callback, which inserts one too - so every '
    'maintenance change is recorded twice. Remove this marker once fixed.')


@pytest.mark.xfail(strict=True, reason=_DOUBLE_WRITE)
def test_maintenance_changes_are_recorded_once(api, lab, pc, agent_for):
    agent = agent_for(pc)
    agent.heartbeat()
    api.wait_state(lab, pc, 'IN_USE')
    api.ok('PUT', f'/pcs/{pc}/maintenance', json={'is_maintenance': True})
    api.ok('PUT', f'/pcs/{pc}/maintenance', json={'is_maintenance': False})
    time.sleep(0.5)
    assert transitions(pc) == [
        ('AVAILABLE', 'IN_USE'), ('IN_USE', 'MAINTENANCE'), ('MAINTENANCE', 'AVAILABLE')]


@pytest.mark.xfail(strict=True, reason=_DOUBLE_WRITE)
def test_approved_report_is_recorded_once(api, lab, pc):
    report = api.ok('POST', '/damage-reports', as_='student',
                    json={'pc_id': pc, 'issue_description': 'E2E: audit trail check'})
    api.ok('PUT', f'/damage-reports/{report["report_id"]}/resolve', json={'status': 'APPROVED'})
    time.sleep(0.5)
    assert transitions(pc) == [('AVAILABLE', 'MAINTENANCE')]


def test_damage_report_flow(api, lab, pc):
    """Student reports; only admin sees and resolves; approval tags MAINTENANCE."""
    report = api.ok('POST', '/damage-reports', as_='student',
                    json={'pc_id': pc, 'issue_description': 'E2E: keyboard missing keys'})
    assert report['status'] == 'PENDING'

    assert api.get('/damage-reports/pending', as_='student').status_code == 403
    pending = api.ok('GET', '/damage-reports/pending')
    assert report['report_id'] in [r['report_id'] for r in pending]

    assert api.put(f'/damage-reports/{report["report_id"]}/resolve', as_='professor',
                   json={'status': 'APPROVED'}).status_code == 403
    resolved = api.ok('PUT', f'/damage-reports/{report["report_id"]}/resolve',
                      json={'status': 'APPROVED'})
    assert resolved['status'] == 'APPROVED' and resolved['resolved_by'] is not None
    assert api.pc(lab, pc)['current_state'] == 'MAINTENANCE'


def test_dismissed_report_leaves_pc_alone(api, lab, pc):
    report = api.ok('POST', '/damage-reports', as_='student',
                    json={'pc_id': pc, 'issue_description': 'E2E: false alarm'})
    api.ok('PUT', f'/damage-reports/{report["report_id"]}/resolve', json={'status': 'DISMISSED'})
    assert api.pc(lab, pc)['current_state'] == 'AVAILABLE'


# -- lab state ---------------------------------------------------------------------------

def _lab_state(api, lab_id) -> str:
    return api.ok('GET', f'/labs/{lab_id}/state')['state']


def test_lab_state_follows_timetable_and_cancellations(api, make_lab):
    """[T9] OPEN -> OCCUPIED by a slot spanning now -> OPEN when cancelled today."""
    lab_id = make_lab()
    assert _lab_state(api, lab_id) == 'OPEN'

    today = local_now()
    slot = api.ok('POST', f'/labs/{lab_id}/timetable', json={
        'lab_id': lab_id, 'day_of_week': today.isoweekday(),
        'start_time': '00:00:00', 'end_time': '23:59:59', 'course_code': 'E2E101'})
    assert _lab_state(api, lab_id) == 'OCCUPIED'

    cancel = {'timetable_id': slot['timetable_id'], 'cancelled_for_date': today.date().isoformat()}
    assert api.post(f'/timetable/{slot["timetable_id"]}/cancel', as_='student',
                    json=cancel).status_code == 403
    api.ok('POST', f'/timetable/{slot["timetable_id"]}/cancel', as_='professor', json=cancel)
    assert _lab_state(api, lab_id) == 'OPEN'
    assert api.post(f'/timetable/{slot["timetable_id"]}/cancel', as_='professor',
                    json=cancel).status_code == 400

    # Cancelling is per date: the recurring slot itself is untouched.
    assert [e['timetable_id'] for e in api.ok('GET', f'/labs/{lab_id}/timetable')] == [slot['timetable_id']]
    assert [c['cancelled_for_date'] for c in api.ok('GET', f'/labs/{lab_id}/cancellations')] \
        == [today.date().isoformat()]


def test_closed_outranks_everything(api, make_lab):
    """[T9] Outside operating hours the lab is CLOSED, even with a slot running."""
    now = local_now()
    start, end = ('13:00:00', '23:00:00') if now.hour < 12 else ('01:00:00', '11:00:00')
    lab_id = make_lab(start=start, end=end)
    api.ok('POST', f'/labs/{lab_id}/timetable', json={
        'lab_id': lab_id, 'day_of_week': now.isoweekday(),
        'start_time': '00:00:00', 'end_time': '23:59:59', 'course_code': 'E2E102'})
    assert _lab_state(api, lab_id) == 'CLOSED'


# -- software discovery ------------------------------------------------------------------

def test_software_report_is_searchable(api, lab, pc, agent_for):
    """[T10] SOFTWARE_REPORT -> JSONB array -> global and lab-wise search."""
    marker = f'e2e-marker-{uuid.uuid4().hex[:6]}'
    agent = agent_for(pc)
    agent.software_report(['python3', 'python3-numpy', marker])

    hits = wait_until(lambda: api.ok('GET', '/software/search', params={'q': marker}),
                      desc='software report stored')
    assert [(h['pc_id'], h['lab_id'], h['matching_packages']) for h in hits] == [(pc, lab, [marker])]

    in_lab = api.ok('GET', f'/labs/{lab}/software/search', params={'q': 'numpy'})
    assert {h['pc_id']: h['matching_packages'] for h in in_lab}[pc] == ['python3-numpy']
    assert api.ok('GET', '/labs/lab-a/software/search', params={'q': marker}) == []

    # Stored as a real array — a double-encoded string made search return
    # single characters.
    kind = db_fetch('SELECT jsonb_typeof(installed_software) AS t FROM pcs WHERE pc_id = $1', pc)
    assert kind[0]['t'] == 'array'
    assert api.get('/software/search', params={'q': 'p'}).status_code == 422


# -- WebSocket fan-out ---------------------------------------------------------------------

def test_updates_fan_out_to_every_dashboard(api, lab, pc, agent_for, ws_for):
    """[T11] Two logged-in dashboards (admin and student) both get the push."""
    admin, student = ws_for('admin'), ws_for('student')
    assert admin.initial['type'] == student.initial['type'] == 'initial_state'

    agent = agent_for(pc)
    agent.heartbeat(cpu_percent=33.0)
    for listener in (admin, student):
        msg = listener.wait_for(lambda m: m.get('pc_id') == pc and 'cpu_percent' in m)
        assert (msg['state'], msg['cpu_percent']) == ('IN_USE', 33.0)

    # A dashboard that connects later gets the PC in its initial snapshot.
    late = ws_for('professor')
    snapshot = {p['pc_id']: p for p in late.initial['pcs']}
    assert snapshot[pc]['state'] == 'IN_USE'
