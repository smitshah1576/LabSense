"""Registry of connected agents, for server-to-agent pushes.

The TCP link is opened by the agent, so the only way to reach a PC is over the
connection it already holds. Each validated connection registers its writer
here under its pc_id; REST routes look the writer up to push control messages
(currently only MAINTENANCE_STATUS).
"""

import asyncio
import logging
from datetime import datetime, timezone

from .server import encode_message

logger = logging.getLogger(__name__)


def maintenance_status_message(pc_id: str, is_maintenance: bool) -> dict:
    """Build the MAINTENANCE_STATUS control message sent to an agent."""
    return {
        "type": "MAINTENANCE_STATUS",
        "pc_id": pc_id,
        "is_maintenance": is_maintenance,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class AgentRegistry:
    """Maps pc_id to the StreamWriter of that PC's live agent connection."""

    def __init__(self):
        self._writers: dict[str, asyncio.StreamWriter] = {}

    def register(self, pc_id: str, writer: asyncio.StreamWriter) -> None:
        # A reconnect replaces the old entry; the old connection's cleanup
        # then leaves the new one alone (see unregister).
        self._writers[pc_id] = writer

    def unregister(self, pc_id: str, writer: asyncio.StreamWriter) -> None:
        if self._writers.get(pc_id) is writer:
            del self._writers[pc_id]

    async def send(self, pc_id: str, msg: dict) -> bool:
        """Push a message to a PC's agent. Returns False if it isn't connected.

        An offline PC loses nothing: the server sends the current maintenance
        status every time an agent connects.
        """
        writer = self._writers.get(pc_id)
        if writer is None or writer.is_closing():
            logger.info("Agent for %s not connected; %s will be sent on its next connect",
                        pc_id, msg.get("type"))
            return False
        try:
            writer.write(encode_message(msg))
            await writer.drain()
            return True
        except (ConnectionError, OSError) as e:
            logger.warning("Failed to push %s to %s: %s", msg.get("type"), pc_id, e)
            return False

    async def send_maintenance_status(self, pc_id: str, is_maintenance: bool) -> bool:
        """Tell a PC's agent whether it is under maintenance."""
        return await self.send(pc_id, maintenance_status_message(pc_id, is_maintenance))
