"""How fast does this machine run the LabSense server's per-heartbeat work?

A scale test measures one machine. To translate its result to another - in
particular the Windows laptop that will be the real server - run this on
both and compare the scores: a laptop scoring 0.8x the testbed can be
expected to handle roughly 0.8x the PCs, all else equal.

It drives the real PCStateManager from backend/app (no network, no
database): for each heartbeat it decodes a frame, applies the state rules,
restarts the staleness timer, reads the live state back and encodes the
dashboard broadcast - the same steps backend/app/tcp/server.py performs. It
runs on Python's default event loop, which on Windows is the same Proactor
loop the server uses there.

Usage (from the repository root, with the backend's dependencies installed):
    python testbed/loadtest/calibrate.py
    backend\\.venv\\Scripts\\python testbed\\loadtest\\calibrate.py      (Windows)
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.state.pc_state_manager import PCStateManager  # noqa: E402

PCS = 1000
ROUND_SECONDS = 3.0
ROUNDS = 3


def cpu_model() -> str:
    if sys.platform.startswith('linux'):
        try:
            for line in Path('/proc/cpuinfo').read_text().splitlines():
                if line.startswith('model name'):
                    return line.split(':', 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


async def one_round() -> float:
    sm = PCStateManager()

    async def on_transition(pc_id, old, new):  # the server writes to the DB here
        pass

    sm.set_transition_callback(on_transition)
    frames = []
    for i in range(PCS):
        payload = json.dumps({
            'type': 'HEARTBEAT', 'pc_id': f'pc{i:04d}', 'session_active': True,
            'screen_locked': False, 'idle_seconds': i % 250, 'cpu_percent': 20.0,
            'timestamp': '2026-10-01T10:00:00+00:00'}).encode()
        frames.append(struct.pack('>I', len(payload)) + payload)

    loop = asyncio.get_running_loop()
    done = 0
    end = loop.time() + ROUND_SECONDS
    started = time.perf_counter()
    while loop.time() < end:
        for frame in frames:
            (length,) = struct.unpack('>I', frame[:4])
            msg = json.loads(frame[4:4 + length])
            await sm.handle_heartbeat(
                pc_id=msg['pc_id'], session_active=msg['session_active'],
                screen_locked=msg['screen_locked'], idle_seconds=msg['idle_seconds'],
                cpu_percent=msg['cpu_percent'])
            live = await sm.get_state(msg['pc_id'])
            json.dumps({'type': 'pc_update', 'pc_id': msg['pc_id'],
                        'state': live.current_state.value,
                        'session_active': live.session_active,
                        'screen_locked': live.screen_locked,
                        'idle_seconds': live.idle_seconds,
                        'cpu_percent': live.cpu_percent})
            done += 1
        await asyncio.sleep(0)  # let cancelled staleness timers be reaped
    elapsed = time.perf_counter() - started
    for state in sm._states.values():
        if state.staleness_task:
            state.staleness_task.cancel()
    await asyncio.sleep(0)
    return done / elapsed


def main() -> int:
    scores = [asyncio.run(one_round()) for _ in range(ROUNDS)]
    best = max(scores)
    loop = type(asyncio.new_event_loop()).__name__
    print(f'LabSense calibration score: {best:,.0f} heartbeats/s on one core')
    print(f'  rounds:   {", ".join(f"{s:,.0f}" for s in scores)}')
    print(f'  python:   {platform.python_version()} ({platform.python_implementation()}), loop {loop}')
    print(f'  platform: {platform.system()} {platform.release()}')
    print(f'  cpu:      {cpu_model()} ({os.cpu_count()} logical CPUs)')
    print('Compare with the score recorded in a scale-test report to scale its PC '
          'capacity to this machine.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
