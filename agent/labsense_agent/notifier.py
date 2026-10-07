"""LabSense desktop notifier — tells the person at the PC about maintenance.

Runs inside each graphical login session (started by the XDG autostart entry
``/etc/xdg/autostart/labsense-notifier.desktop``), as the logged-in user.
The agent service cannot do this itself: it runs as the ``labsense`` system
user, with no access to the user's display or session bus.

It polls the status file the agent publishes (see ``maintenance_state``) and
talks to the desktop's notification server over the session bus
(``org.freedesktop.Notifications``):

- status becomes ``True`` — including the first check after login, so the
  notice is shown again after every boot until the PC is returned to
  service — show a critical notice that stays until dismissed;
- status goes ``True`` → ``False`` — close that notice and say the PC is
  back in service;
- file missing (agent not yet told by the server) — do nothing.

Usage::

    python -m labsense_agent.notifier
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Optional

from dbus_next import BusType, Message, MessageType, Variant
from dbus_next.aio import MessageBus

from . import config, maintenance_state

logger = logging.getLogger(__name__)

_NOTIFY_DEST = 'org.freedesktop.Notifications'
_NOTIFY_PATH = '/org/freedesktop/Notifications'
_NOTIFY_IFACE = 'org.freedesktop.Notifications'

_URGENCY_NORMAL = 1
_URGENCY_CRITICAL = 2

_MAINTENANCE_SUMMARY = 'This PC is under maintenance'
_MAINTENANCE_BODY = (
    'Lab staff have marked this workstation as out of service. '
    'Please save your work and move to another PC.'
)
_SERVICE_SUMMARY = 'This PC is back in service'
_SERVICE_BODY = 'Lab staff have cleared the maintenance flag on this workstation.'


class Notifier:
    """Shows and withdraws the maintenance notice for one desktop session."""

    def __init__(self, bus: MessageBus) -> None:
        self._bus = bus
        # Last status a notice was successfully shown for (None = nothing yet).
        self._shown: Optional[bool] = None
        # Id of the on-screen maintenance notice, so it can be withdrawn.
        self._notice_id = 0

    async def _notify(self, summary: str, body: str, urgency: int, resident: bool) -> Optional[int]:
        reply = await self._bus.call(
            Message(
                destination=_NOTIFY_DEST,
                path=_NOTIFY_PATH,
                interface=_NOTIFY_IFACE,
                member='Notify',
                signature='susssasa{sv}i',
                body=[
                    'LabSense',
                    0,
                    'dialog-warning' if urgency == _URGENCY_CRITICAL else 'dialog-information',
                    summary,
                    body,
                    [],
                    {
                        'urgency': Variant('y', urgency),
                        'resident': Variant('b', resident),
                    },
                    -1,
                ],
            )
        )
        if reply.message_type == MessageType.ERROR:
            # Typically the notification server isn't up yet right after
            # login; the next poll retries.
            logger.debug('Notify failed: %s %s', reply.error_name, reply.body)
            return None
        return reply.body[0]

    async def _close(self, notice_id: int) -> None:
        await self._bus.call(
            Message(
                destination=_NOTIFY_DEST,
                path=_NOTIFY_PATH,
                interface=_NOTIFY_IFACE,
                member='CloseNotification',
                signature='u',
                body=[notice_id],
            )
        )

    async def check(self) -> None:
        """Compare the published status with what is on screen and act."""
        status = maintenance_state.read_status()
        if status is None or status == self._shown:
            return

        if status:
            notice_id = await self._notify(
                _MAINTENANCE_SUMMARY, _MAINTENANCE_BODY, _URGENCY_CRITICAL, resident=True
            )
            if notice_id is None:
                return
            self._notice_id = notice_id
            logger.info('Showed maintenance notice')
        elif self._shown is True:
            if self._notice_id:
                await self._close(self._notice_id)
                self._notice_id = 0
            if await self._notify(
                _SERVICE_SUMMARY, _SERVICE_BODY, _URGENCY_NORMAL, resident=False
            ) is None:
                return
            logger.info('Showed back-in-service notice')
        # status False with nothing shown yet: the PC is simply in service.

        self._shown = status


async def _run() -> None:
    try:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
    except Exception as exc:
        # Not inside a desktop session (no DBUS_SESSION_BUS_ADDRESS).
        logger.error('Cannot connect to the session bus: %s', exc)
        sys.exit(1)

    notifier = Notifier(bus)
    disconnected = asyncio.ensure_future(bus.wait_for_disconnect())
    logger.info('LabSense notifier watching %s', maintenance_state.status_path())

    # The session bus only goes away when the session ends, so that is the
    # signal to exit.
    while not disconnected.done():
        try:
            await notifier.check()
        except Exception:
            logger.exception('Error checking maintenance status')
        await asyncio.wait({disconnected}, timeout=config.NOTIFIER_POLL_INTERVAL)

    logger.info('Session bus closed — notifier exiting')


def main() -> None:
    """Synchronous entry point."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
