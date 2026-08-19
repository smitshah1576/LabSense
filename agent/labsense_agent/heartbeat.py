"""Heartbeat TCP client for LabSense agent.

Maintains a persistent TCP connection to the LabSense backend server and
provides methods for sending protocol messages (HEARTBEAT, GOING_TO_SLEEP,
SOFTWARE_REPORT).

Connection management:
- Uses ``asyncio.open_connection()`` (non-blocking).
- Reconnects automatically with exponential back-off on failure.
- ``send_going_to_sleep()`` explicitly drains the write buffer so the
  inhibitor lock can be released with a guarantee that bytes hit the wire.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from . import config
from .protocol import (
    create_going_to_sleep,
    create_heartbeat,
    create_software_report,
    encode_message,
)

logger = logging.getLogger(__name__)


class HeartbeatClient:
    """Manages the TCP connection and sends protocol messages to the backend."""

    _MAX_BACKOFF: float = 60.0  # ceiling for exponential back-off

    def __init__(
        self,
        host: str = config.SERVER_HOST,
        port: int = config.SERVER_PORT,
        pc_id: str = config.PC_ID,
    ) -> None:
        self._host = host
        self._port = port
        self._pc_id = pc_id
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._backoff: float = config.RECONNECT_DELAY

    @property
    def connected(self) -> bool:
        """Whether the client currently holds an open connection."""
        return self._connected

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish a TCP connection to the backend server.

        On failure, logs the error but does NOT raise — the caller is
        expected to retry.
        """
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
            self._connected = True
            self._backoff = config.RECONNECT_DELAY  # reset on success
            logger.info(
                'Connected to backend at %s:%d', self._host, self._port
            )
        except OSError as exc:
            self._connected = False
            logger.error(
                'Failed to connect to %s:%d — %s', self._host, self._port, exc
            )

    async def ensure_connected(self) -> bool:
        """Ensure the connection is alive, reconnecting if necessary.

        Returns ``True`` if the connection is (now) open.
        """
        if self._connected and self._writer is not None:
            # Quick liveness check — if the transport is closing, reconnect.
            if self._writer.is_closing():
                self._connected = False

        if not self._connected:
            await self.connect()

        return self._connected

    async def reconnect_with_backoff(self) -> None:
        """Wait for the current back-off interval, then reconnect.

        Doubles the interval after each failure (capped at ``_MAX_BACKOFF``).
        """
        logger.info(
            'Reconnecting in %.1fs …', self._backoff
        )
        await asyncio.sleep(self._backoff)
        self._backoff = min(self._backoff * 2, self._MAX_BACKOFF)
        await self.connect()

    # ------------------------------------------------------------------
    # Sending messages
    # ------------------------------------------------------------------

    async def _send(self, msg: Dict[str, Any]) -> bool:
        """Serialise and write a message to the TCP stream.

        Returns ``True`` on success, ``False`` if the write failed (in which
        case the connection is marked as disconnected).
        """
        if self._writer is None or not self._connected:
            logger.warning('Cannot send — not connected')
            return False

        try:
            data = encode_message(msg)
            self._writer.write(data)
            await self._writer.drain()
            return True
        except (ConnectionError, OSError) as exc:
            logger.error('Send failed: %s', exc)
            self._connected = False
            return False

    async def send_heartbeat(
        self,
        session_active: bool,
        screen_locked: bool,
        idle_seconds: int,
        cpu_percent: float,
    ) -> bool:
        """Build and send a HEARTBEAT message.

        Returns ``True`` on success.
        """
        msg = create_heartbeat(
            pc_id=self._pc_id,
            session_active=session_active,
            screen_locked=screen_locked,
            idle_seconds=idle_seconds,
            cpu_percent=cpu_percent,
        )
        ok = await self._send(msg)
        if ok:
            logger.debug(
                'Heartbeat sent (cpu=%.1f%%, idle=%ds, active=%s, locked=%s)',
                cpu_percent,
                idle_seconds,
                session_active,
                screen_locked,
            )
        return ok

    async def send_going_to_sleep(self) -> bool:
        """Send GOING_TO_SLEEP and explicitly flush the write buffer.

        This method is called from the ``PrepareForSleep`` callback.  The
        inhibitor lock is released AFTER this returns, so the OS cannot
        suspend until the bytes are on the wire.

        Returns ``True`` on success.
        """
        if self._writer is None or not self._connected:
            logger.warning('Cannot send GOING_TO_SLEEP — not connected')
            return False

        msg = create_going_to_sleep(self._pc_id)
        try:
            data = encode_message(msg)
            self._writer.write(data)
            await self._writer.drain()  # ensure bytes hit the kernel buffer
            logger.info('GOING_TO_SLEEP sent and flushed')
            return True
        except (ConnectionError, OSError) as exc:
            logger.error('Failed to send GOING_TO_SLEEP: %s', exc)
            self._connected = False
            return False

    async def send_software_report(self, packages: List[str]) -> bool:
        """Build and send a SOFTWARE_REPORT message.

        Returns ``True`` on success.
        """
        msg = create_software_report(self._pc_id, packages)
        ok = await self._send(msg)
        if ok:
            logger.info(
                'SOFTWARE_REPORT sent (%d packages)', len(packages)
            )
        return ok

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Gracefully close the TCP connection."""
        self._connected = False
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
                logger.info('TCP connection closed')
            except Exception as exc:
                logger.warning('Error closing connection: %s', exc)
            finally:
                self._writer = None
                self._reader = None
