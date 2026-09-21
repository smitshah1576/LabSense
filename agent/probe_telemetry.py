#!/usr/bin/env python3
"""Print every telemetry value the agent would send, with the source it came from.

Use this on a lab PC to check each probe without the backend involved.
Run it as the same user the service runs as, so the permissions match:

    sudo -u labsense /opt/labsense-agent/.venv/bin/python3 /opt/labsense-agent/probe_telemetry.py

Then, while it runs:
    - move the mouse / type         -> idle drops to 0, source [input]
    - press Super+L                 -> locked=True [logind] within ~2s
    - log out to the login screen   -> session=False

Options: --seconds N (default 60), --interval S (default 2).
It can run alongside the service; input devices are read non-exclusively.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from labsense_agent.dbus_monitor import LogindMonitor  # noqa: E402
from labsense_agent.input_idle import InputIdleTracker  # noqa: E402
from labsense_agent.telemetry import (  # noqa: E402
    get_cpu_percent,
    get_idle_seconds,
    get_screen_locked,
    get_session_active,
)


async def _noop(*_args) -> None:
    pass


async def main(seconds: float, interval: float) -> None:
    monitor = LogindMonitor(_noop, _noop, _noop, _noop)
    listener = asyncio.create_task(monitor.connect_and_listen())
    tracker = InputIdleTracker()
    await tracker.start()

    # Give the D-Bus connection a moment to come up.
    for _ in range(20):
        if monitor._bus is not None or listener.done():
            break
        await asyncio.sleep(0.1)

    print(f'Running as uid={os.getuid()}  input devices watched: {tracker.device_count}')
    print('Move the mouse, type, lock the screen (Super+L) and watch the values.\n')

    get_cpu_percent()  # prime
    loop = asyncio.get_running_loop()
    end = loop.time() + seconds
    try:
        while loop.time() < end:
            await asyncio.sleep(interval)
            hints = await monitor.get_session_hints()
            session, s_src = get_session_active(hints)
            locked, l_src = await get_screen_locked(hints)
            idle, i_src = await get_idle_seconds(hints, tracker)
            cpu = get_cpu_percent()
            user = f" user={hints.get('user')}" if hints and hints.get('present') else ''
            print(
                f'session={str(session):5} [{s_src}]{user}  '
                f'locked={str(locked):5} [{l_src}]  '
                f'idle={idle:>5}s [{i_src}]  '
                f'cpu={cpu:5.1f}%'
            )
    finally:
        await tracker.stop()
        listener.cancel()
        await monitor.disconnect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seconds', type=float, default=60.0)
    parser.add_argument('--interval', type=float, default=2.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='  (%(levelname)s %(name)s: %(message)s)')
    try:
        asyncio.run(main(args.seconds, args.interval))
    except KeyboardInterrupt:
        pass
