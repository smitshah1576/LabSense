"""Systemd-logind sleep inhibitor lock management.

The inhibitor lock prevents the OS from suspending until we've had a chance to
send ``GOING_TO_SLEEP`` and flush the network write.  This is the mechanism
that **guarantees** the backend receives the sleep notification before the
network interface goes down.

Without this lock there is a race between our network write and the kernel
tearing down the interface.  An earlier design tried to win this race with
synchronous calls — that does not provide a guarantee.  The inhibitor lock is
what actually does.

Usage pattern::

    lock = InhibitorLock()
    await lock.acquire()        # at startup
    # ... on PrepareForSleep(True):
    await heartbeat_client.send_going_to_sleep()
    await writer.drain()
    await lock.release()        # NOW the OS may suspend
    # ... on PrepareForSleep(False) — waking up:
    await lock.acquire()        # re-arm for next sleep
"""

from __future__ import annotations

import logging
import os

from dbus_next import BusType, Message, MessageType
from dbus_next.aio import MessageBus

logger = logging.getLogger(__name__)


class InhibitorLock:
    """Manages a systemd-logind sleep inhibitor lock.

    The lock prevents the OS from suspending until we've had a chance to
    send ``GOING_TO_SLEEP`` and flush the network write.  This is the
    mechanism that guarantees the backend receives the sleep notification
    before the network interface goes down.

    Without this lock, there's a race between our network write and the OS
    tearing down the interface.  An earlier design tried to win this race
    with synchronous calls — that doesn't provide a guarantee.  The
    inhibitor lock is what actually does.
    """

    _LOGIND_DEST = 'org.freedesktop.login1'
    _LOGIND_PATH = '/org/freedesktop/login1'
    _MANAGER_IFACE = 'org.freedesktop.login1.Manager'

    def __init__(self) -> None:
        self._fd: int | None = None  # Unix file descriptor for the lock
        self._bus: MessageBus | None = None

    @property
    def held(self) -> bool:
        """Whether the inhibitor lock is currently held."""
        return self._fd is not None

    async def acquire(self) -> None:
        """Acquire the inhibitor lock.

        Connects to the system D-Bus (if not already connected) and calls
        ``org.freedesktop.login1.Manager.Inhibit("sleep", ...)``.  The
        returned Unix file descriptor represents the lock — closing it
        releases the lock.
        """
        if self._fd is not None:
            logger.warning('Inhibitor lock already held (fd=%d), skipping acquire', self._fd)
            return

        try:
            if self._bus is None:
                self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

            reply = await self._bus.call(
                Message(
                    destination=self._LOGIND_DEST,
                    path=self._LOGIND_PATH,
                    interface=self._MANAGER_IFACE,
                    member='Inhibit',
                    signature='ssss',
                    body=[
                        'sleep',                                       # what
                        'LabSense Agent',                              # who
                        'Need to send sleep notification to server',   # why
                        'delay',                                       # mode
                    ],
                )
            )

            if reply.message_type == MessageType.ERROR:
                logger.error(
                    'Failed to acquire inhibitor lock: %s %s',
                    reply.error_name,
                    reply.body,
                )
                return

            if reply.body:
                self._fd = reply.body[0]
                logger.info('Acquired sleep inhibitor lock (fd=%d)', self._fd)
            else:
                logger.error(
                    'Inhibit() returned empty body — lock not acquired'
                )

        except Exception:
            logger.exception('Exception while acquiring inhibitor lock')

    async def release(self) -> None:
        """Release the inhibitor lock after GOING_TO_SLEEP is flushed.

        Closing the file descriptor is what actually releases the lock —
        this is a kernel-level guarantee.
        """
        if self._fd is None:
            logger.debug('No inhibitor lock to release')
            return

        try:
            os.close(self._fd)
            logger.info('Released sleep inhibitor lock (fd=%d)', self._fd)
        except OSError as exc:
            logger.warning('Error closing inhibitor fd %d: %s', self._fd, exc)
        finally:
            self._fd = None

    async def close(self) -> None:
        """Clean up — release the lock and disconnect from D-Bus."""
        await self.release()
        if self._bus is not None:
            try:
                self._bus.disconnect()
                logger.debug('Inhibitor D-Bus connection closed')
            except Exception as exc:
                logger.warning('Error disconnecting inhibitor bus: %s', exc)
            finally:
                self._bus = None
