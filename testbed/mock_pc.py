"""LabSense mock client PC — one simulated lab machine, driven by scenarios.

Unlike ``agent/mock_agent.py`` (five PCs sending random telemetry), each
instance of this script is a single PC whose behaviour you choose and can
change while it runs, so a test can say "pc-3 locks its screen" or "pc-2
suspends" and check exactly what the dashboard does.

Only the *telemetry source* is simulated.  Framing and message construction
come from ``labsense_agent.protocol`` — the same module the production agent
uses — so the bytes on the wire are the real agent's bytes.

Scenarios (what the simulated user is doing):

    in-use      at the keyboard: fresh input, moderate CPU      -> IN_USE
    idle        logged in but walked away 10+ minutes ago       -> AVAILABLE
    locked      screen locked, stepped out                      -> IN_USE
                (until the backend's LOCK_RESERVE_SECONDS, 15 min, expires)
    cpu-busy    long job running, nobody at the keyboard        -> IN_USE
                (after CPU_WINDOW_HEARTBEATS consecutive busy heartbeats)
    logged-out  sitting at the login screen                     -> AVAILABLE

Power actions (what happens to the machine):

    sleep       clean suspend: GOING_TO_SLEEP is sent, then the link drops
                -> AVAILABLE_SLEEP, and the staleness timer does not apply
    power-off   abrupt power loss: link dropped, nothing sent
                -> AVAILABLE after the 15 s grace period
    hang        frozen OS / stalled network: socket stays open, nothing sent
                -> AVAILABLE after the 15 s grace period
    wake        (alias: power-on) resume heartbeats, reconnecting if needed

Control API (HTTP on --control-port, JSON responses)::

    curl localhost:7001/status
    curl -X POST localhost:7001/scenario/idle
    curl -X POST localhost:7001/sleep
    curl -X POST localhost:7001/wake
    curl -X POST localhost:7001/software      # resend SOFTWARE_REPORT now

``testbed/pcctl`` wraps these by PC name.

Configuration uses the real agent's environment variable names where one
exists (``LABSENSE_SERVER_HOST``, ``LABSENSE_SERVER_PORT``, ``LABSENSE_PC_ID``,
``LABSENSE_HEARTBEAT_INTERVAL``) plus ``MOCK_PC_*`` for the simulation.  CLI
flags override the environment.  Standard library only.

Usage::

    python testbed/mock_pc.py --pc-id lab-a-pc-1 --server-host localhost \\
        --scenario in-use --control-port 7001
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import sys
import time
from pathlib import Path
from typing import Any

# Use the production agent's wire protocol.  Works from a checkout
# (testbed/../agent) and in the testbed containers, which mount the agent
# package at /agent next to /testbed.
_AGENT_DIR = Path(__file__).resolve().parent.parent / 'agent'
if _AGENT_DIR.is_dir():
    sys.path.insert(0, str(_AGENT_DIR))

from labsense_agent.protocol import (  # noqa: E402
    create_going_to_sleep,
    create_heartbeat,
    create_software_report,
    encode_message,
    read_message,
)

logger = logging.getLogger('mock_pc')

SCENARIOS: dict[str, str] = {
    'in-use': 'at the keyboard',
    'idle': 'logged in, walked away',
    'locked': 'screen locked, stepped out',
    'cpu-busy': 'long job running, nobody at the keyboard',
    'logged-out': 'at the login screen',
}

# A plausible lab image.  Each PC reports these plus its MOCK_PC_SOFTWARE
# extras, so a search for a shared package hits every PC and a search for an
# extra hits only the PCs that have it.
BASE_SOFTWARE = [
    'build-essential', 'curl', 'firefox', 'g++', 'gcc', 'git',
    'libreoffice-core', 'make', 'openssh-client', 'python3',
    'python3-pip', 'vim',
]

_MAX_BACKOFF = 60.0


def simulate_telemetry(scenario: str, elapsed: float) -> dict[str, Any]:
    """Telemetry a real agent would report for ``scenario``.

    ``elapsed`` is seconds since the scenario started; idle time keeps
    counting up from a starting offset, as it would on a real machine.
    """
    elapsed = int(elapsed)
    if scenario == 'in-use':
        return dict(session_active=True, screen_locked=False,
                    idle_seconds=random.randint(0, 20),
                    cpu_percent=random.uniform(8.0, 40.0))
    if scenario == 'idle':
        return dict(session_active=True, screen_locked=False,
                    idle_seconds=600 + elapsed,
                    cpu_percent=random.uniform(0.5, 3.0))
    if scenario == 'locked':
        return dict(session_active=True, screen_locked=True,
                    idle_seconds=120 + elapsed,
                    cpu_percent=random.uniform(0.5, 3.0))
    if scenario == 'cpu-busy':
        return dict(session_active=True, screen_locked=False,
                    idle_seconds=900 + elapsed,
                    cpu_percent=random.uniform(70.0, 99.0))
    if scenario == 'logged-out':
        return dict(session_active=False, screen_locked=False,
                    idle_seconds=1800 + elapsed,
                    cpu_percent=random.uniform(0.2, 2.0))
    raise ValueError(f'unknown scenario {scenario!r}')


class MockPC:
    """One simulated lab PC: a heartbeat loop plus a control surface."""

    def __init__(self, pc_id: str, host: str, port: int, scenario: str,
                 software: list[str], interval: float) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f'unknown scenario {scenario!r}')
        self.pc_id = pc_id
        self.host = host
        self.port = port
        self.interval = interval
        self.software = sorted(set(BASE_SOFTWARE) | set(software))

        self.scenario = scenario
        self._scenario_started = time.monotonic()
        self.power = 'on'  # on | asleep | off | hung

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._backoff = interval
        # Set by control actions so the loop reacts now, not next tick.
        self._nudge = asyncio.Event()

        self.heartbeats_sent = 0
        self.last_heartbeat: dict[str, Any] | None = None
        self.last_error: str | None = None
        self.rejected = False

    # -- connection ---------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def _connect(self) -> bool:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=10.0)
        except (OSError, asyncio.TimeoutError) as exc:
            self.last_error = f'connect failed: {exc or type(exc).__name__}'
            logger.warning('%s: cannot reach %s:%d (%s)', self.pc_id,
                           self.host, self.port, self.last_error)
            self._writer = None
            return False
        logger.info('%s: connected to %s:%d', self.pc_id, self.host, self.port)
        self.rejected = False
        self.last_error = None
        self._backoff = self.interval
        self._reader_task = asyncio.create_task(self._read_loop())
        return True

    async def _read_loop(self) -> None:
        """Consume server->agent control messages (the server sends REJECTED
        for an unregistered pc_id, then hangs up)."""
        try:
            while True:
                msg = await read_message(self._reader)
                if msg.get('type') == 'REJECTED':
                    self.rejected = True
                    self.last_error = f"REJECTED: {msg.get('reason')}"
                    logger.error('%s: server rejected this pc_id (%s)',
                                 self.pc_id, msg.get('reason'))
                else:
                    logger.info('%s: server says %s', self.pc_id, msg)
        except asyncio.CancelledError:
            raise
        except Exception:
            # EOF or reset.  While hung we are deliberately silent, so a
            # server-side close is the only way we'd notice; either way the
            # main loop reconnects once it next needs the link.
            self._drop_link(abort=True)

    def _drop_link(self, abort: bool) -> None:
        if self._reader_task is not None and self._reader_task is not asyncio.current_task():
            self._reader_task.cancel()
        self._reader_task = None
        if self._writer is not None:
            if abort:
                # No FIN handshake, no flush — the closest a process can get
                # to a machine losing power.
                self._writer.transport.abort()
            else:
                self._writer.close()
        self._writer = None
        self._reader = None

    async def _send(self, msg: dict[str, Any]) -> bool:
        if not self.connected:
            return False
        try:
            self._writer.write(encode_message(msg))
            await self._writer.drain()
            return True
        except (ConnectionError, OSError) as exc:
            self.last_error = f'send failed: {exc}'
            logger.warning('%s: %s', self.pc_id, self.last_error)
            self._drop_link(abort=True)
            return False

    # -- messages -----------------------------------------------------------

    async def send_heartbeat(self) -> bool:
        elapsed = time.monotonic() - self._scenario_started
        telemetry = simulate_telemetry(self.scenario, elapsed)
        msg = create_heartbeat(pc_id=self.pc_id, **telemetry)
        if not await self._send(msg):
            return False
        self.heartbeats_sent += 1
        self.last_heartbeat = {k: msg[k] for k in (
            'session_active', 'screen_locked', 'idle_seconds', 'cpu_percent', 'timestamp')}
        logger.debug('%s: heartbeat #%d %s', self.pc_id, self.heartbeats_sent, telemetry)
        return True

    async def send_software_report(self) -> bool:
        ok = await self._send(create_software_report(self.pc_id, self.software))
        if ok:
            logger.info('%s: SOFTWARE_REPORT sent (%d packages)', self.pc_id, len(self.software))
        return ok

    # -- control actions ----------------------------------------------------

    def set_scenario(self, scenario: str) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f'unknown scenario {scenario!r}')
        self.scenario = scenario
        self._scenario_started = time.monotonic()
        logger.info('%s: scenario -> %s (%s)', self.pc_id, scenario, SCENARIOS[scenario])
        self._nudge.set()

    async def sleep(self) -> bool:
        """Clean suspend.  Returns whether GOING_TO_SLEEP reached the socket."""
        sent = await self._send(create_going_to_sleep(self.pc_id))
        self.power = 'asleep'
        self._drop_link(abort=False)
        logger.info('%s: suspended (GOING_TO_SLEEP %s)', self.pc_id,
                    'sent' if sent else 'NOT sent - was not connected')
        return sent

    def power_off(self) -> None:
        self.power = 'off'
        self._drop_link(abort=True)
        logger.info('%s: powered off (link dropped, nothing sent)', self.pc_id)

    def hang(self) -> None:
        self.power = 'hung'
        logger.info('%s: hung (socket open, sending nothing)', self.pc_id)

    def wake(self) -> None:
        previous, self.power = self.power, 'on'
        logger.info('%s: %s -> on', self.pc_id, previous)
        self._nudge.set()

    def status(self) -> dict[str, Any]:
        return {
            'pc_id': self.pc_id,
            'server': f'{self.host}:{self.port}',
            'scenario': self.scenario,
            'scenario_description': SCENARIOS[self.scenario],
            'power': self.power,
            'connected': self.connected,
            'rejected': self.rejected,
            'heartbeats_sent': self.heartbeats_sent,
            'last_heartbeat': self.last_heartbeat,
            'last_error': self.last_error,
            'software_count': len(self.software),
        }

    # -- main loop ----------------------------------------------------------

    async def _pause(self, seconds: float) -> None:
        """Sleep, but return early if a control action nudges us.

        Cleared after waiting, not before, so a nudge that lands while a
        heartbeat is being sent still cuts the next wait short.
        """
        try:
            await asyncio.wait_for(self._nudge.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
        self._nudge.clear()

    async def run(self) -> None:
        while True:
            if self.power != 'on':
                await self._pause(3600)
                continue

            if not self.connected:
                if not await self._connect():
                    await self._pause(self._backoff)
                    self._backoff = min(self._backoff * 2, _MAX_BACKOFF)
                    continue
                # Like the real agent's startup scan: inventory on (re)boot.
                await self.send_software_report()

            if not await self.send_heartbeat():
                continue  # link dropped mid-send; reconnect immediately
            await self._pause(self.interval)

    async def close(self) -> None:
        self._drop_link(abort=False)


# -- control API ------------------------------------------------------------

_REASONS = {200: 'OK', 400: 'Bad Request', 404: 'Not Found', 405: 'Method Not Allowed'}


async def _dispatch(pc: MockPC, method: str, path: str) -> tuple[int, dict[str, Any]]:
    parts = [p for p in path.split('?', 1)[0].split('/') if p]

    if parts in ([], ['status']):
        return 200, pc.status()
    if method != 'POST':
        return 405, {'error': f'use POST for /{"/".join(parts)}'}

    action = parts[0]
    if action == 'scenario' and len(parts) == 2:
        try:
            pc.set_scenario(parts[1])
        except ValueError as exc:
            return 400, {'error': str(exc), 'scenarios': list(SCENARIOS)}
    elif action == 'sleep' and len(parts) == 1:
        sent = await pc.sleep()
        return 200, {**pc.status(), 'going_to_sleep_sent': sent}
    elif action in ('wake', 'power-on') and len(parts) == 1:
        pc.wake()
    elif action == 'power-off' and len(parts) == 1:
        pc.power_off()
    elif action == 'hang' and len(parts) == 1:
        pc.hang()
    elif action == 'software' and len(parts) == 1:
        sent = await pc.send_software_report()
        return 200, {**pc.status(), 'software_report_sent': sent}
    else:
        return 404, {'error': f'unknown endpoint /{"/".join(parts)}',
                     'endpoints': ['GET /status', 'POST /scenario/<name>', 'POST /sleep',
                                   'POST /wake', 'POST /power-on', 'POST /power-off',
                                   'POST /hang', 'POST /software'],
                     'scenarios': list(SCENARIOS)}
    return 200, pc.status()


async def _handle_http(pc: MockPC, reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter) -> None:
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        while True:  # headers are irrelevant; skip to the blank line
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if line in (b'\r\n', b'\n', b''):
                break
        method, path, _ = request_line.decode('latin-1').split(' ', 2)
        status, body = await _dispatch(pc, method.upper(), path)
    except (ValueError, asyncio.TimeoutError):
        status, body = 400, {'error': 'malformed HTTP request'}

    payload = (json.dumps(body, indent=2) + '\n').encode()
    head = (f'HTTP/1.1 {status} {_REASONS[status]}\r\n'
            f'Content-Type: application/json\r\n'
            f'Content-Length: {len(payload)}\r\n'
            f'Connection: close\r\n\r\n')
    try:
        writer.write(head.encode() + payload)
        await writer.drain()
    finally:
        writer.close()


# -- entry point ------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    env = os.environ.get
    p = argparse.ArgumentParser(
        description='Simulated LabSense lab PC (see module docstring for the control API).')
    p.add_argument('--pc-id', default=env('LABSENSE_PC_ID'),
                   help='registered pc_id to report as (env LABSENSE_PC_ID)')
    p.add_argument('--server-host', default=env('LABSENSE_SERVER_HOST', 'localhost'))
    p.add_argument('--server-port', type=int, default=int(env('LABSENSE_SERVER_PORT', '9000')))
    p.add_argument('--interval', type=float,
                   default=float(env('LABSENSE_HEARTBEAT_INTERVAL', '5')),
                   help='seconds between heartbeats (default 5, like the real agent)')
    p.add_argument('--scenario', default=env('MOCK_PC_SCENARIO', 'in-use'), choices=list(SCENARIOS))
    p.add_argument('--software', default=env('MOCK_PC_SOFTWARE', ''),
                   help='comma-separated packages reported on top of the base image')
    p.add_argument('--control-host', default=env('MOCK_PC_CONTROL_HOST', '0.0.0.0'))
    p.add_argument('--control-port', type=int, default=int(env('MOCK_PC_CONTROL_PORT', '7000')),
                   help='HTTP control API port; 0 disables it')
    p.add_argument('--log-level', default=env('LABSENSE_LOG_LEVEL', 'INFO'))
    args = p.parse_args(argv)
    if not args.pc_id:
        p.error('--pc-id (or LABSENSE_PC_ID) is required')
    return args


async def _main(args: argparse.Namespace) -> None:
    pc = MockPC(
        pc_id=args.pc_id,
        host=args.server_host,
        port=args.server_port,
        scenario=args.scenario,
        software=[s.strip() for s in args.software.split(',') if s.strip()],
        interval=args.interval,
    )

    control = None
    if args.control_port:
        control = await asyncio.start_server(
            lambda r, w: _handle_http(pc, r, w), args.control_host, args.control_port)
        logger.info('%s: control API on %s:%d', pc.pc_id, args.control_host, args.control_port)

    logger.info('%s: starting, scenario=%s, server=%s:%d, interval=%.1fs',
                pc.pc_id, pc.scenario, pc.host, pc.port, pc.interval)

    # SIGTERM (docker stop) behaves like stopping the real agent's service:
    # the connection closes cleanly with no GOING_TO_SLEEP.
    main_task = asyncio.current_task()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, main_task.cancel)
        except NotImplementedError:  # Windows
            pass

    try:
        await pc.run()
    except asyncio.CancelledError:
        logger.info('%s: stopping', pc.pc_id)
    finally:
        await pc.close()
        if control is not None:
            control.close()


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )
    try:
        asyncio.run(_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
