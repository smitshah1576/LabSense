"""System telemetry collection for LabSense agent.

Collects CPU usage, session state, screen-lock status, and user idle time.
All functions are non-blocking — subprocess calls use asyncio.create_subprocess_exec
to avoid stalling the single-threaded event loop.

Platform: Linux (X11/Wayland with graceful fallbacks).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

import psutil

logger = logging.getLogger(__name__)


def get_cpu_percent() -> float:
    """Return instantaneous CPU utilisation percentage.

    Uses ``psutil.cpu_percent(interval=None)`` which returns a value based on
    the delta since the previous call.  The very first call after process start
    will return ``0.0``; subsequent calls give meaningful values.

    CRITICAL: ``interval`` MUST be ``None`` — a non-zero interval would
    **block** the event loop for that many seconds.
    """
    return psutil.cpu_percent(interval=None)


def get_session_active() -> bool:
    """Check whether at least one interactive user session is logged in.

    Uses ``psutil.users()`` which reads utmp records — cheap and non-blocking.
    """
    try:
        users = psutil.users()
        return len(users) > 0
    except Exception as exc:
        logger.warning('Failed to query user sessions: %s', exc)
        return False


async def get_screen_locked() -> bool:
    """Attempt to detect whether the screen is currently locked.

    Strategy (tried in order):
    1. ``xdg-screensaver status`` — returns "enabled" (blanked / locked) or
       "disabled" (not locked).  Works on most X11 desktops.
    2. D-Bus query to ``org.freedesktop.ScreenSaver.GetActive`` — works on
       KDE, some GNOME versions, and other FreeDesktop-compliant desktops.

    If neither method succeeds, returns ``False`` and logs a warning once.
    """
    # --- Method 1: xdg-screensaver status ---
    try:
        proc = await asyncio.create_subprocess_exec(
            'xdg-screensaver', 'status',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        status = stdout.decode().strip().lower()
        if status in ('enabled', 'disabled'):
            return status == 'enabled'
    except FileNotFoundError:
        logger.debug('xdg-screensaver not found, trying D-Bus fallback')
    except asyncio.TimeoutError:
        logger.debug('xdg-screensaver timed out')
    except Exception as exc:
        logger.debug('xdg-screensaver failed: %s', exc)

    # --- Method 2: D-Bus org.freedesktop.ScreenSaver.GetActive ---
    try:
        proc = await asyncio.create_subprocess_exec(
            'dbus-send', '--session', '--dest=org.freedesktop.ScreenSaver',
            '--type=method_call', '--print-reply',
            '/org/freedesktop/ScreenSaver',
            'org.freedesktop.ScreenSaver.GetActive',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        output = stdout.decode().strip()
        # Output looks like: "   boolean true" or "   boolean false"
        return 'boolean true' in output
    except FileNotFoundError:
        logger.debug('dbus-send not found')
    except asyncio.TimeoutError:
        logger.debug('D-Bus ScreenSaver query timed out')
    except Exception as exc:
        logger.debug('D-Bus ScreenSaver query failed: %s', exc)

    logger.debug('Screen lock detection unavailable — defaulting to False')
    return False


async def get_idle_seconds() -> int:
    """Return the number of seconds since the last user input event.

    Strategy (tried in order):
    1. ``xprintidle`` — gives milliseconds since last X11 input event.
       Extremely lightweight, but requires the package to be installed.
    2. ``/dev/input/event*`` — stat the most recently modified input device
       file and compute seconds since that timestamp.  Requires read
       permission on device files (the ``input`` group, or running as root).

    If both methods fail, returns ``0`` (assumes active) and logs a warning.
    """
    # --- Method 1: xprintidle ---
    try:
        proc = await asyncio.create_subprocess_exec(
            'xprintidle',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        if proc.returncode == 0:
            idle_ms = int(stdout.decode().strip())
            return idle_ms // 1000
    except FileNotFoundError:
        logger.debug('xprintidle not found, trying /dev/input fallback')
    except asyncio.TimeoutError:
        logger.debug('xprintidle timed out')
    except (ValueError, Exception) as exc:
        logger.debug('xprintidle failed: %s', exc)

    # --- Method 2: /dev/input/event* modification times ---
    try:
        input_dir = '/dev/input'
        if os.path.isdir(input_dir):
            latest_mtime = 0.0
            for entry in os.listdir(input_dir):
                if entry.startswith('event'):
                    path = os.path.join(input_dir, entry)
                    try:
                        st = os.stat(path)
                        if st.st_mtime > latest_mtime:
                            latest_mtime = st.st_mtime
                    except OSError:
                        continue
            if latest_mtime > 0.0:
                idle = int(time.time() - latest_mtime)
                return max(idle, 0)
    except Exception as exc:
        logger.debug('/dev/input idle detection failed: %s', exc)

    logger.debug('Idle time detection unavailable — defaulting to 0')
    return 0
