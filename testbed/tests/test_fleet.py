"""The containerised client fleet is reporting, and each PC can be driven.

These run against the long-lived Lab A fleet from testbed/compose.yml
(lab-a-pc-1..4 mock PCs, lab-a-pc-5 the real agent), and put every mock PC
back in its default scenario afterwards.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from conftest import HEARTBEAT_TIMEOUT, wait_until

pytestmark = pytest.mark.fleet

PCCTL = Path(__file__).resolve().parents[1] / 'pcctl'
LAB = 'lab-a'
# Mirrors testbed/compose.yml: control port and default scenario -> expected state.
MOCKS = {
    'lab-a-pc-1': (7001, 'in-use', 'IN_USE'),
    'lab-a-pc-2': (7002, 'idle', 'AVAILABLE'),
    'lab-a-pc-3': (7003, 'locked', 'IN_USE'),
    'lab-a-pc-4': (7004, 'cpu-busy', 'IN_USE'),
}
REAL_AGENT = 'lab-a-pc-5'


def control(pc_id: str, path: str) -> dict:
    port = MOCKS[pc_id][0]
    resp = httpx.post(f'http://127.0.0.1:{port}/{path}', trust_env=False, timeout=5)
    resp.raise_for_status()
    return resp.json()


def pcctl(*args: str) -> str:
    out = subprocess.run([sys.executable, str(PCCTL), *args], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, f'pcctl {" ".join(args)} failed: {out.stderr}'
    return out.stdout


def restore_defaults() -> None:
    for pc_id, (_port, scenario, _state) in MOCKS.items():
        control(pc_id, 'wake')
        control(pc_id, f'scenario/{scenario}')


@pytest.fixture(scope='module', autouse=True)
def fleet():
    for pc_id, (port, *_rest) in MOCKS.items():
        try:
            httpx.get(f'http://127.0.0.1:{port}/status', trust_env=False, timeout=2).raise_for_status()
        except httpx.HTTPError:
            pytest.skip(f'{pc_id} control API not reachable on :{port} — run: testbed/testbed.sh up')
    restore_defaults()
    yield
    restore_defaults()


def _age(pc: dict) -> float:
    then = datetime.fromisoformat(pc['last_heartbeat_at'].replace('Z', '+00:00'))
    return (datetime.now(timezone.utc) - then).total_seconds()


def test_every_fleet_pc_is_reporting(api):
    pcs = {p['pc_id']: p for p in api.ok('GET', f'/labs/{LAB}/pcs')}
    for pc_id in [*MOCKS, REAL_AGENT]:
        assert pcs[pc_id]['last_heartbeat_at'], f'{pc_id} has never sent a heartbeat'
        assert _age(pcs[pc_id]) < HEARTBEAT_TIMEOUT, f'{pc_id} heartbeat is stale'


def test_default_scenarios_land_on_expected_states(api):
    for pc_id, (_port, scenario, expected) in MOCKS.items():
        # cpu-busy needs CPU_WINDOW_HEARTBEATS busy samples (~15 s) after a reset.
        api.wait_state(LAB, pc_id, expected, timeout=25)


def test_real_agent_reports_from_its_container(api):
    """lab-a-pc-5 runs the unmodified agent.  With no logind in a container it
    falls back to utmp, finds no session, and so reads AVAILABLE."""
    pc = api.pc(LAB, REAL_AGENT)
    assert pc['session_active'] is False and pc['current_state'] == 'AVAILABLE'


@pytest.mark.parametrize('source, package', [('dpkg -l', 'coreutils'), ('pip list', 'psutil')])
def test_real_agent_inventories_its_software(api, source, package):
    hits = api.ok('GET', f'/labs/{LAB}/software/search', params={'q': package})
    assert REAL_AGENT in {h['pc_id'] for h in hits}, \
        f'{package!r} ({source}) missing from the real agent\'s SOFTWARE_REPORT'


def test_mock_software_differs_per_pc(api):
    def who_has(q):
        return {h['pc_id'] for h in api.ok('GET', f'/labs/{LAB}/software/search', params={'q': q})}
    assert who_has('eclipse') == {'lab-a-pc-2'}
    assert who_has('python3-numpy') == {'lab-a-pc-3', 'lab-a-pc-4'}
    assert set(MOCKS) <= who_has('firefox')


def test_scenario_switch_is_reflected_immediately(api):
    pcctl('1', 'scenario', 'logged-out')
    api.wait_state(LAB, 'lab-a-pc-1', 'AVAILABLE', timeout=3)
    pcctl('1', 'scenario', 'in-use')
    api.wait_state(LAB, 'lab-a-pc-1', 'IN_USE', timeout=3)


def test_mock_pc_suspends_and_resumes(api):
    pcctl('2', 'scenario', 'in-use')
    api.wait_state(LAB, 'lab-a-pc-2', 'IN_USE', timeout=3)
    assert 'GOING_TO_SLEEP sent' in pcctl('2', 'sleep')
    api.wait_state(LAB, 'lab-a-pc-2', 'AVAILABLE_SLEEP', timeout=3)
    assert control('lab-a-pc-2', 'status')['power'] == 'asleep'
    pcctl('2', 'wake')
    api.wait_state(LAB, 'lab-a-pc-2', 'IN_USE', timeout=5)


@pytest.mark.slow
def test_unplugged_pc_goes_available_then_recovers(api):
    """The demo's dirty disconnect: pull the cable rather than stop the service."""
    api.wait_state(LAB, 'lab-a-pc-1', 'IN_USE', timeout=5)
    pcctl('1', 'unplug')
    try:
        wait_until(lambda: _age(api.pc(LAB, 'lab-a-pc-1')) > HEARTBEAT_TIMEOUT - 5,
                   timeout=HEARTBEAT_TIMEOUT, desc='heartbeats to stop arriving')
        assert api.pc(LAB, 'lab-a-pc-1')['current_state'] == 'IN_USE', 'no grace period'
        api.wait_state(LAB, 'lab-a-pc-1', 'AVAILABLE', timeout=12)
    finally:
        pcctl('1', 'replug')
    api.wait_state(LAB, 'lab-a-pc-1', 'IN_USE', timeout=20)
