"""Precise user idle time from kernel input devices.

The agent runs as a systemd service under its own system user, so it has no
X display and no session bus — ``xprintidle`` and the compositor's idle
monitor are out of reach, and neither works on Wayland from outside the
session anyway.  The kernel's evdev nodes (``/dev/input/event*``) are the one
source that sees every keystroke and mouse movement regardless of display
server or who is logged in.

We only record *when* an event arrived.  The bytes read from the device are
discarded unparsed — key codes are never decoded, stored or sent anywhere.

Requires read access to the event nodes: the ``input`` group
(``SupplementaryGroups=input`` in the systemd unit) or root.
"""

from __future__ import annotations

import asyncio
import errno
import logging
import os
import time

logger = logging.getLogger(__name__)

_SYS_INPUT = '/sys/class/input'
_UDEV_DATA = '/run/udev/data'

# udev tags that identify devices a human uses.  Anything else (power button,
# lid switch, "Video Bus", accelerometers) can emit events on its own and
# would make an empty room look busy.
_HUMAN_INPUT_TAGS = (
    'ID_INPUT_KEYBOARD',
    'ID_INPUT_MOUSE',
    'ID_INPUT_TOUCHPAD',
    'ID_INPUT_TOUCHSCREEN',
    'ID_INPUT_TABLET',
)

_RESCAN_INTERVAL = 30.0


def _is_human_input(event_name: str) -> bool:
    """Return True if udev tagged this event device as keyboard/mouse/etc."""
    try:
        with open(os.path.join(_SYS_INPUT, event_name, 'dev')) as fh:
            major, minor = fh.read().strip().split(':')
        with open(os.path.join(_UDEV_DATA, f'c{major}:{minor}')) as fh:
            props = fh.read()
    except (OSError, ValueError):
        return False
    return any(f'E:{tag}=1' in props for tag in _HUMAN_INPUT_TAGS)


def _device_name(event_name: str) -> str:
    try:
        with open(os.path.join(_SYS_INPUT, event_name, 'device', 'name')) as fh:
            return fh.read().strip()
    except OSError:
        return event_name


class InputIdleTracker:
    """Timestamps the most recent keyboard/mouse/touch event on this machine."""

    def __init__(self) -> None:
        self._fds: dict[str, int] = {}  # event name -> fd
        self._last_input: float | None = None  # time.monotonic()
        self._rescan_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._warned_permission = False

    @property
    def device_count(self) -> int:
        return len(self._fds)

    def idle_seconds(self) -> int | None:
        """Seconds since the last input event, or None if unknown.

        None means no device could be opened or nothing has been touched since
        the agent started — the caller should fall back to another source.
        """
        if not self._fds or self._last_input is None:
            return None
        return max(int(time.monotonic() - self._last_input), 0)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._scan(initial=True)
        self._rescan_task = asyncio.create_task(self._rescan_loop(), name='input-rescan')

    async def stop(self) -> None:
        if self._rescan_task:
            self._rescan_task.cancel()
            self._rescan_task = None
        for name in list(self._fds):
            self._close(name)

    # ------------------------------------------------------------------

    async def _rescan_loop(self) -> None:
        while True:
            await asyncio.sleep(_RESCAN_INTERVAL)
            try:
                self._scan(initial=False)
            except Exception:
                logger.exception('Input device rescan failed')

    def _scan(self, initial: bool) -> None:
        try:
            present = sorted(n for n in os.listdir(_SYS_INPUT) if n.startswith('event'))
        except OSError as exc:
            if initial:
                logger.warning('Input idle: cannot list %s (%s) — using fallback idle source', _SYS_INPUT, exc)
            return

        # Drop devices that vanished (reader callback usually catches this first).
        for name in list(self._fds):
            if name not in present:
                self._close(name)

        opened: list[str] = []
        denied = 0
        for name in present:
            if name in self._fds or not _is_human_input(name):
                continue
            try:
                fd = os.open(f'/dev/input/{name}', os.O_RDONLY | os.O_NONBLOCK)
            except PermissionError:
                denied += 1
                continue
            except OSError:
                continue
            self._fds[name] = fd
            self._loop.add_reader(fd, self._on_readable, name)
            opened.append(_device_name(name))

        if denied and not self._fds and not self._warned_permission:
            self._warned_permission = True
            logger.warning(
                'Input idle: permission denied on %d input device(s). Add the agent '
                "user to the 'input' group (SupplementaryGroups=input) for precise "
                'idle time; falling back to logind IdleHint.', denied,
            )

        if opened:
            logger.info(
                'Input idle: watching %d device(s)%s: %s',
                len(self._fds), '' if initial else ' (hotplug)', ', '.join(opened),
            )
        elif initial and not self._fds and not denied:
            logger.warning('Input idle: no keyboard/mouse devices found — using fallback idle source')

    def _on_readable(self, name: str) -> None:
        fd = self._fds.get(name)
        if fd is None:
            return
        try:
            # Drain and discard — only the arrival time matters.
            while os.read(fd, 4096):
                pass
        except BlockingIOError:
            pass
        except OSError as exc:
            if exc.errno == errno.ENODEV:
                logger.info('Input idle: device %s removed', name)
            else:
                logger.debug('Input idle: read error on %s: %s', name, exc)
            self._close(name)
            return
        self._last_input = time.monotonic()

    def _close(self, name: str) -> None:
        fd = self._fds.pop(name, None)
        if fd is None:
            return
        if self._loop is not None:
            try:
                self._loop.remove_reader(fd)
            except Exception:
                pass
        try:
            os.close(fd)
        except OSError:
            pass
