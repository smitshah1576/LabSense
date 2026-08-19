"""Wire protocol for LabSense agent-to-server communication.

Implements length-prefixed JSON messaging over raw TCP streams.
Each message consists of a 4-byte big-endian unsigned integer indicating the length
of the payload, followed by the UTF-8 encoded JSON payload.
"""

from __future__ import annotations

import asyncio
import json
import struct
from datetime import datetime, timezone
from typing import Any, Dict, List


def encode_message(msg: Dict[str, Any]) -> bytes:
    """Serialize a message dict to length-prefixed JSON bytes.

    Args:
        msg: The message dictionary to serialize.

    Returns:
        Bytes containing 4-byte big-endian length prefix followed by UTF-8 JSON payload.
    """
    payload = json.dumps(msg).encode('utf-8')
    length = struct.pack('!I', len(payload))
    return length + payload


async def read_message(reader: asyncio.StreamReader) -> Dict[str, Any]:
    """Read one length-prefixed JSON message from the stream.

    Args:
        reader: The asyncio StreamReader to read from.

    Returns:
        The decoded message dictionary.

    Raises:
        ConnectionError: If EOF is reached or the stream is closed prematurely.
        ValueError: If the message payload exceeds 1MB sanity check.
    """
    try:
        length_bytes = await reader.readexactly(4)
    except asyncio.IncompleteReadError as err:
        raise ConnectionError("Connection closed before reading complete message header") from err

    length = struct.unpack('!I', length_bytes)[0]
    if length > 1_000_000:  # 1MB sanity check
        raise ValueError(f'Message too large: {length} bytes')

    try:
        payload = await reader.readexactly(length)
    except asyncio.IncompleteReadError as err:
        raise ConnectionError(
            f"Connection closed while reading message payload ({length} bytes expected, got {len(err.partial)})"
        ) from err

    return json.loads(payload.decode('utf-8'))


def create_heartbeat(
    pc_id: str,
    session_active: bool,
    screen_locked: bool,
    idle_seconds: int,
    cpu_percent: float,
) -> Dict[str, Any]:
    """Create a HEARTBEAT message.

    Args:
        pc_id: Unique identifier of the PC.
        session_active: Whether a user session is active.
        screen_locked: Whether the user screen is locked.
        idle_seconds: Seconds of user inactivity.
        cpu_percent: Current CPU utilization percentage.

    Returns:
        Dictionary representation of the HEARTBEAT message.
    """
    return {
        'type': 'HEARTBEAT',
        'pc_id': pc_id,
        'session_active': session_active,
        'screen_locked': screen_locked,
        'idle_seconds': idle_seconds,
        'cpu_percent': round(cpu_percent, 1),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


def create_going_to_sleep(pc_id: str) -> Dict[str, Any]:
    """Create a GOING_TO_SLEEP message.

    Args:
        pc_id: Unique identifier of the PC.

    Returns:
        Dictionary representation of the GOING_TO_SLEEP message.
    """
    return {
        'type': 'GOING_TO_SLEEP',
        'pc_id': pc_id,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


def create_software_report(pc_id: str, packages: List[str]) -> Dict[str, Any]:
    """Create a SOFTWARE_REPORT message.

    Args:
        pc_id: Unique identifier of the PC.
        packages: List of installed package names/identifiers.

    Returns:
        Dictionary representation of the SOFTWARE_REPORT message.
    """
    return {
        'type': 'SOFTWARE_REPORT',
        'pc_id': pc_id,
        'packages': packages,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
