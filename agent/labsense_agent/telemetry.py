"""System telemetry collection for LabSense agent.

Collects CPU usage, session state, screen-lock status, and user idle time.
All functions are non-blocking — subprocess calls use asyncio.create_subprocess_exec
to avoid stalling the single-threaded event loop.

The agent normally runs as a systemd service under a dedicated system user,
with no X display and no session bus.  Per-user tools (``xprintidle``,
``xdg-screensaver``, ``dbus-send --session``) therefore fail in production, so
each value is read from a source that works from a system service first:

- session / lock / coarse idle  → systemd-logind hints on the *system* bus
  (``LogindMonitor.get_session_hints()``)
- precise idle                  → kernel input devices (``InputIdleTracker``)

The per-user tools remain only as fallbacks for running the agent by hand
inside a desktop session.

Each ``get_*`` function returns ``(value, source)``; the source string is what
``probe_telemetry.py`` prints, so each probe can be checked on real hardware.

Platform: Linux (X11/Wayland).
"""

from __future__ import annotations

import asyncio
import logging
import time

import psutil

from .input_idle import InputIdleTracker

logger = logging.getLogger(__name__)

_warned_no_idle = False


def get_cpu_percent() -> float:
    """Return instantaneous CPU utilisation percentage.

    Uses ``psutil.cpu_percent(interval=None)`` which returns a value based on
    the delta since the previous call.  The very first call after process start
    will return ``0.0``; subsequent calls give meaningful values.

    CRITICAL: ``interval`` MUST be ``None`` — a non-zero interval would
    **block** the event loop for that many seconds.
    """
    return psutil.cpu_percent(interval=None)


async def _run(*argv: str, timeout: float = 5.0) -> tuple[int, str] | None:
    """Run a short command, returning (returncode, stdout) or None on failure.

    Kills the child on timeout so a hung probe can't leak a process per
    heartbeat.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except (FileNotFoundError, PermissionError):
        return None
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.debug('%s timed out', argv[0])
        return None
    return proc.returncode, stdout.decode(errors='replace').strip()


def get_session_active(hints: dict | None) -> tuple[bool, str]:
    """Is a user logged in at the physical seat?

    logind's active session on seat0 with ``Class == 'user'`` — the GDM
    greeter (class ``greeter``) and SSH logins (no seat) do not count.
    Falls back to ``psutil.users()`` (utmp) when logind is unreachable.
    """
    if hints is not None:
        if not hints.get('present'):
            return False, 'logind:seat0 empty'
        active = hints.get('class') == 'user' and hints.get('active', False)
        return active, f"logind:seat0 {hints.get('id')} {hints.get('class')}"

    try:
        return len(psutil.users()) > 0, 'utmp'
    except Exception as exc:
        logger.warning('Failed to query user sessions: %s', exc)
        return False, 'none'


async def get_screen_locked(hints: dict | None) -> tuple[bool, str]:
    """Is the seat's session showing the lock screen?

    1. logind ``LockedHint`` — authoritative; set by GNOME/KDE lock screens.
    2. ``org.freedesktop.ScreenSaver.GetActive`` on the session bus — only
       reachable when the agent runs inside the user's session.

    (``xdg-screensaver status`` was removed: it reports whether the
    screensaver is *enabled*, not whether the screen is locked.)
    """
    if hints is not None:
        return bool(hints.get('present') and hints.get('locked')), 'logind'

    result = await _run(
        'dbus-send', '--session', '--dest=org.freedesktop.ScreenSaver',
        '--type=method_call', '--print-reply',
        '/org/freedesktop/ScreenSaver',
        'org.freedesktop.ScreenSaver.GetActive',
    )
    if result and result[0] == 0:
        return 'boolean true' in result[1], 'screensaver-dbus'

    return False, 'none'


async def get_idle_seconds(
    hints: dict | None,
    tracker: InputIdleTracker | None,
) -> tuple[int, str]:
    """Seconds since the last keyboard/mouse/touch input on this machine.

    1. ``InputIdleTracker`` — exact, from /dev/input event timing.
    2. logind ``IdleHint``/``IdleSinceHint`` — coarse: reads 0 until the
       desktop's own idle delay (GNOME default 5 min) passes, then the true
       idle time.
    3. ``xprintidle`` — only works inside an X11 session.

    If nothing works, returns 0 (treated as "active") and warns once.
    """
    global _warned_no_idle

    if tracker is not None:
        idle = tracker.idle_seconds()
        if idle is not None:
            return idle, 'input'

    if hints is not None:
        if hints.get('present') and hints.get('idle_hint') and hints.get('idle_since_us'):
            idle = int(time.time() - hints['idle_since_us'] / 1_000_000)
            return max(idle, 0), 'logind'
        return 0, 'logind'

    result = await _run('xprintidle')
    if result and result[0] == 0:
        try:
            return int(result[1]) // 1000, 'xprintidle'
        except ValueError:
            pass

    if not _warned_no_idle:
        _warned_no_idle = True
        logger.warning('Idle time unavailable from every source — reporting 0')
    return 0, 'none'
