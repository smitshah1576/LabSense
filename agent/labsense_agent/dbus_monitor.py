"""D-Bus subscription to systemd-logind signals.

Uses dbus-next (asyncio-native) to subscribe to the following broadcast
signals from ``systemd-logind``:

- ``PrepareForSleep``   — emitted *before* suspend (arg ``True``) and
                          *after* resume  (arg ``False``)
- ``PrepareForShutdown``— emitted *before* shutdown/reboot (``True``)
                          and if the shutdown is cancelled (``False``)
- ``Lock`` / ``Unlock`` — emitted when a session's screen lock state changes

IMPORTANT DESIGN PRINCIPLE: this class is a **subscriber** to logind's
broadcast signals — we do NOT implement our own session tracking.
``systemd-logind`` is the session broker; we merely listen and relay events
to our backend.

This module runs as a long-lived coroutine on the SAME asyncio event loop as
the heartbeat task.  ``dbus-next`` is asyncio-native, so no threads are
needed.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from dbus_next import BusType, Message, MessageType
from dbus_next.aio import MessageBus

logger = logging.getLogger(__name__)


class LogindMonitor:
    """Subscribes to systemd-logind D-Bus signals for sleep/shutdown/lock events.

    This is a SUBSCRIBER to logind's broadcast signals — we do not implement
    our own session tracking.  logind is the session broker; we listen.
    """

    # D-Bus well-known names / interfaces
    _LOGIND_BUS_NAME = 'org.freedesktop.login1'
    _MANAGER_IFACE = 'org.freedesktop.login1.Manager'
    _SESSION_IFACE = 'org.freedesktop.login1.Session'
    _MANAGER_PATH = '/org/freedesktop/login1'

    def __init__(
        self,
        on_prepare_sleep: Callable[[bool], Awaitable[None]],
        on_prepare_shutdown: Callable[[bool], Awaitable[None]],
        on_lock: Callable[[], Awaitable[None]],
        on_unlock: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialise with callback coroutines for each event type.

        Args:
            on_prepare_sleep:    called with ``True`` when entering sleep,
                                 ``False`` on resume.
            on_prepare_shutdown: called with ``True`` before shutdown.
            on_lock:             called when the session screen is locked.
            on_unlock:           called when the session screen is unlocked.
        """
        self._on_prepare_sleep = on_prepare_sleep
        self._on_prepare_shutdown = on_prepare_shutdown
        self._on_lock = on_lock
        self._on_unlock = on_unlock
        self._bus: MessageBus | None = None

    async def connect_and_listen(self) -> None:
        """Connect to the system D-Bus and subscribe to logind signals.

        This coroutine runs until the bus is disconnected (i.e. forever under
        normal operation).  It should be launched as one of the long-running
        tasks in ``asyncio.gather()``.
        """
        try:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        except Exception as exc:
            logger.error('Failed to connect to system D-Bus: %s', exc)
            raise

        # --- Add match rules for the signals we care about ---
        match_rules = [
            (
                "type='signal',"
                f"sender='{self._LOGIND_BUS_NAME}',"
                f"interface='{self._MANAGER_IFACE}',"
                "member='PrepareForSleep'"
            ),
            (
                "type='signal',"
                f"sender='{self._LOGIND_BUS_NAME}',"
                f"interface='{self._MANAGER_IFACE}',"
                "member='PrepareForShutdown'"
            ),
            # Lock / Unlock are emitted on per-session objects, but we
            # subscribe to all of them without specifying a path.
            (
                "type='signal',"
                f"sender='{self._LOGIND_BUS_NAME}',"
                f"interface='{self._SESSION_IFACE}',"
                "member='Lock'"
            ),
            (
                "type='signal',"
                f"sender='{self._LOGIND_BUS_NAME}',"
                f"interface='{self._SESSION_IFACE}',"
                "member='Unlock'"
            ),
        ]

        for rule in match_rules:
            try:
                reply = await self._bus.call(
                    Message(
                        destination='org.freedesktop.DBus',
                        path='/org/freedesktop/DBus',
                        interface='org.freedesktop.DBus',
                        member='AddMatch',
                        signature='s',
                        body=[rule],
                    )
                )
                if reply.message_type == MessageType.ERROR:
                    logger.warning(
                        'AddMatch failed for rule %s: %s', rule, reply.body
                    )
            except Exception as exc:
                logger.warning('Failed to add match rule %s: %s', rule, exc)

        # --- Install the message handler ---
        self._bus.add_message_handler(self._handle_message)

        logger.info('LogindMonitor connected and listening for signals')

        # Block until the bus is disconnected.
        await self._bus.wait_for_disconnect()
        logger.warning('LogindMonitor: D-Bus connection lost')

    def _handle_message(self, msg: Message) -> None:
        """Route incoming D-Bus signals to the appropriate callback.

        This is invoked synchronously by the dbus-next event loop integration.
        We schedule the async callbacks as tasks so they can ``await`` without
        blocking the handler dispatch.
        """
        if msg.message_type != MessageType.SIGNAL:
            return

        member = msg.member
        body = msg.body

        if member == 'PrepareForSleep' and body:
            going_to_sleep: bool = body[0]
            logger.info(
                'Received PrepareForSleep(%s)', going_to_sleep
            )
            asyncio.create_task(
                self._safe_callback(self._on_prepare_sleep, going_to_sleep)
            )

        elif member == 'PrepareForShutdown' and body:
            going_to_shutdown: bool = body[0]
            logger.info(
                'Received PrepareForShutdown(%s)', going_to_shutdown
            )
            asyncio.create_task(
                self._safe_callback(self._on_prepare_shutdown, going_to_shutdown)
            )

        elif member == 'Lock':
            logger.info('Received Lock signal')
            asyncio.create_task(self._safe_callback(self._on_lock))

        elif member == 'Unlock':
            logger.info('Received Unlock signal')
            asyncio.create_task(self._safe_callback(self._on_unlock))

    @staticmethod
    async def _safe_callback(coro_fn: Callable, *args) -> None:
        """Invoke a callback coroutine with exception logging.

        Exceptions in signal callbacks must not crash the monitor — they are
        logged and swallowed so the bus listener stays alive.
        """
        try:
            await coro_fn(*args)
        except Exception:
            logger.exception('Error in LogindMonitor callback %s', coro_fn)

    async def disconnect(self) -> None:
        """Disconnect from the system D-Bus."""
        if self._bus is not None:
            try:
                self._bus.disconnect()
                logger.info('LogindMonitor disconnected from D-Bus')
            except Exception as exc:
                logger.warning('Error disconnecting from D-Bus: %s', exc)
            finally:
                self._bus = None
