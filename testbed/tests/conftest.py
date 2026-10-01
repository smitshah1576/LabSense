"""Shared fixtures for the LabSense end-to-end suite.

These tests drive the *running* system — backend, database, WebSocket push and
(for test_fleet.py) the client containers — from the outside, the way the
dashboard and the agents do.  Start it first with ``testbed/testbed.sh up``.

Server tests never touch the seeded Lab A PCs (the fleet owns those).  Each
test registers its own PC in a throwaway lab through the admin API, and the
lab is deleted at the end of the session.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import struct
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg
import httpx
import pytest
from websockets.sync.client import connect as ws_connect

# The raw-protocol client uses the production agent's framing code.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'agent'))
from labsense_agent.protocol import (  # noqa: E402
    create_going_to_sleep,
    create_heartbeat,
    create_software_report,
    encode_message,
)

API = os.environ.get('LABSENSE_API', 'http://localhost:8000').rstrip('/')
WS_URL = API.replace('http', 'ws', 1) + '/ws'
TCP_HOST = os.environ.get('LABSENSE_TCP_HOST', 'localhost')
TCP_PORT = int(os.environ.get('LABSENSE_TCP_PORT', '9000'))
DATABASE_URL = os.environ.get(
    'LABSENSE_DATABASE_URL', 'postgresql://labsense:labsense_dev@localhost:5432/labsense')

# Backend rule parameters (app/config.py defaults; override to match the backend).
HEARTBEAT_TIMEOUT = int(os.environ.get('LABSENSE_HEARTBEAT_TIMEOUT_SECONDS', '15'))
IDLE_THRESHOLD = int(os.environ.get('LABSENSE_IDLE_THRESHOLD_SECONDS', '300'))
CPU_THRESHOLD = float(os.environ.get('LABSENSE_CPU_THRESHOLD_PERCENT', '5.0'))
CPU_WINDOW = int(os.environ.get('LABSENSE_CPU_WINDOW_HEARTBEATS', '3'))
TIMEZONE = os.environ.get('LABSENSE_TIMEZONE', 'Asia/Kolkata')
# The dashboard as a teammate on the Wi-Fi opens it: http://<server LAN IP>:5173.
LAN_ORIGIN = os.environ.get('LABSENSE_LAN_ORIGIN', 'http://172.28.0.1:5173')

PASSWORD = 'password123'
USERS = {
    'admin': 'admin@labsense.dev',
    'professor': 'prof@labsense.dev',
    'student': 'student@labsense.dev',
}
TEST_LAB_PREFIX = 'e2e'


# -- small utilities ----------------------------------------------------------

def wait_until(predicate, timeout: float = 5.0, interval: float = 0.1, desc: str = 'condition'):
    """Poll ``predicate`` until it returns a truthy value; return that value."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f'timed out after {timeout}s waiting for {desc} (last: {last!r})')


def local_now() -> datetime:
    """Now in the backend's lab timezone — lab hours and timetables use it."""
    return datetime.now(ZoneInfo(TIMEZONE))


def db_fetch(sql: str, *args) -> list[dict]:
    async def run():
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            return [dict(r) for r in await conn.fetch(sql, *args)]
        finally:
            await conn.close()
    return asyncio.run(run())


def transitions(pc_id: str) -> list[tuple[str, str]]:
    rows = db_fetch(
        'SELECT from_state, to_state FROM state_transitions WHERE pc_id = $1 ORDER BY id', pc_id)
    return [(r['from_state'], r['to_state']) for r in rows]


class RawAgent:
    """A bare TCP protocol client — no agent code beyond the wire format.

    The programmatic twin of agent/test_heartbeat.py: send exactly the
    messages a test needs, when it needs them.
    """

    def __init__(self, pc_id: str):
        self.pc_id = pc_id
        self.sock = socket.create_connection((TCP_HOST, TCP_PORT), timeout=5)

    def send(self, msg: dict) -> None:
        self.sock.sendall(encode_message(msg))

    def heartbeat(self, session_active=True, screen_locked=False, idle_seconds=5,
                  cpu_percent=20.0) -> None:
        self.send(create_heartbeat(self.pc_id, session_active, screen_locked,
                                   idle_seconds, cpu_percent))

    def going_to_sleep(self) -> None:
        self.send(create_going_to_sleep(self.pc_id))

    def software_report(self, packages: list[str]) -> None:
        self.send(create_software_report(self.pc_id, packages))

    def recv(self, timeout: float = 3.0) -> dict | None:
        """Next server->agent message, or None on EOF.  Raises on timeout."""
        self.sock.settimeout(timeout)
        header = self._read_exactly(4)
        if header is None:
            return None
        body = self._read_exactly(struct.unpack('>I', header)[0])
        return None if body is None else json.loads(body)

    def _read_exactly(self, n: int) -> bytes | None:
        buf = b''
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def close(self) -> None:
        self.sock.close()


class Api:
    """Thin authenticated wrapper over the REST API."""

    def __init__(self, client: httpx.Client, tokens: dict[str, str]):
        self.client = client
        self.tokens = tokens

    def request(self, method: str, path: str, as_: str = 'admin', **kw) -> httpx.Response:
        headers = {'Authorization': f'Bearer {self.tokens[as_]}'} if as_ else {}
        return self.client.request(method, path, headers=headers, **kw)

    def get(self, path, as_='admin', **kw):
        return self.request('GET', path, as_, **kw)

    def post(self, path, as_='admin', **kw):
        return self.request('POST', path, as_, **kw)

    def put(self, path, as_='admin', **kw):
        return self.request('PUT', path, as_, **kw)

    def delete(self, path, as_='admin', **kw):
        return self.request('DELETE', path, as_, **kw)

    def ok(self, method: str, path: str, as_: str = 'admin', **kw):
        resp = self.request(method, path, as_, **kw)
        assert resp.is_success, f'{method} {path} as {as_} -> {resp.status_code}: {resp.text}'
        return resp.json()

    def pc(self, lab_id: str, pc_id: str) -> dict:
        pcs = self.ok('GET', f'/labs/{lab_id}/pcs')
        return next(p for p in pcs if p['pc_id'] == pc_id)

    def wait_state(self, lab_id: str, pc_id: str, state: str, timeout: float = 5.0) -> dict:
        return wait_until(
            lambda: (pc := self.pc(lab_id, pc_id))['current_state'] == state and pc,
            timeout=timeout, desc=f'{pc_id} to be {state}')


class WsListener:
    """A logged-in dashboard's WebSocket, as the frontend opens it."""

    def __init__(self, ws):
        self.ws = ws
        self.initial = json.loads(ws.recv(timeout=5))

    def wait_for(self, pred, timeout: float = 5.0) -> dict:
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                msg = json.loads(self.ws.recv(timeout=remaining))
            except TimeoutError:
                break
            if pred(msg):
                return msg
        raise AssertionError(f'no matching WebSocket message within {timeout}s')



# -- fixtures -----------------------------------------------------------------

@pytest.fixture(scope='session')
def client():
    # trust_env=False: never send local testbed traffic through an HTTP proxy.
    with httpx.Client(base_url=API, trust_env=False, timeout=10) as c:
        try:
            c.get('/health').raise_for_status()
        except httpx.HTTPError as exc:
            pytest.exit(f'backend not reachable at {API} ({exc}) — run: testbed/testbed.sh up',
                        returncode=2)
        yield c


@pytest.fixture(scope='session')
def tokens(client) -> dict[str, str]:
    out = {}
    for role, email in USERS.items():
        resp = client.post('/auth/login', json={'email': email, 'password': PASSWORD})
        assert resp.status_code == 200, f'login as {email} failed: {resp.text}'
        out[role] = resp.json()['access_token']
    return out


@pytest.fixture(scope='session')
def api(client, tokens) -> Api:
    return Api(client, tokens)


def _create_lab(api: Api, start='00:00:00', end='23:59:59') -> str:
    lab_id = f'{TEST_LAB_PREFIX}{uuid.uuid4().hex[:4]}'
    api.ok('POST', '/admin/labs', json={
        'lab_id': lab_id, 'lab_name': f'E2E {lab_id}',
        'operating_start_time': start, 'operating_end_time': end,
    })
    return lab_id


@pytest.fixture(scope='session')
def make_lab(api):
    """Factory for throwaway labs; all are deleted at session end."""
    # Sweep labs left behind by an interrupted earlier run.
    for lab in api.ok('GET', '/labs'):
        if lab['lab_id'].startswith(TEST_LAB_PREFIX):
            api.delete(f'/admin/labs/{lab["lab_id"]}')

    created: list[str] = []

    def factory(start='00:00:00', end='23:59:59') -> str:
        lab_id = _create_lab(api, start, end)
        created.append(lab_id)
        return lab_id

    yield factory
    for lab_id in created:
        api.delete(f'/admin/labs/{lab_id}')


@pytest.fixture(scope='session')
def lab(make_lab) -> str:
    """A lab that is open around the clock, so lab state is never CLOSED."""
    return make_lab()


@pytest.fixture
def pc(api, lab) -> str:
    """A freshly registered PC with no history."""
    return api.ok('POST', '/admin/pcs', json={'lab_id': lab})['pc_id']


@pytest.fixture
def agent_for():
    """Factory for RawAgent connections, closed after the test."""
    agents: list[RawAgent] = []

    def factory(pc_id: str) -> RawAgent:
        agent = RawAgent(pc_id)
        agents.append(agent)
        return agent

    yield factory
    for agent in agents:
        agent.close()


@pytest.fixture
def ws_for(tokens):
    """Factory for dashboard WebSocket listeners, closed after the test."""
    with contextlib.ExitStack() as stack:
        def factory(role: str = 'admin') -> WsListener:
            ws = stack.enter_context(ws_connect(f'{WS_URL}?token={tokens[role]}', open_timeout=5,
                                                proxy=None))
            return WsListener(ws)

        yield factory
