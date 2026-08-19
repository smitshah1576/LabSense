import asyncio
import json
import struct
import logging
from typing import Optional
from ..state.pc_state_manager import PCStateManager
from ..ws.manager import ConnectionManager
from ..models.enums import PCState

logger = logging.getLogger(__name__)

def encode_message(msg: dict) -> bytes:
    payload = json.dumps(msg).encode('utf-8')
    length = len(payload)
    return struct.pack('>I', length) + payload

async def read_message(reader: asyncio.StreamReader) -> Optional[dict]:
    try:
        length_bytes = await reader.readexactly(4)
        length = struct.unpack('>I', length_bytes)[0]
        payload = await reader.readexactly(length)
        return json.loads(payload.decode('utf-8'))
    except asyncio.IncompleteReadError:
        return None
    except Exception as e:
        logger.error(f"Error reading message: {e}")
        return None

async def handle_agent_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                                  state_manager: PCStateManager, ws_manager: ConnectionManager, pool):
    addr = writer.get_extra_info('peername')
    logger.info(f"New agent connection from {addr}")
    pc_id = None
    try:
        while True:
            msg = await read_message(reader)
            if msg is None:
                break
                
            msg_type = msg.get("type")
            pc_id = msg.get("pc_id")
            
            if not pc_id:
                continue
                
            if msg_type == "HEARTBEAT":
                await state_manager.handle_heartbeat(
                    pc_id=pc_id,
                    session_active=msg.get("session_active", False),
                    screen_locked=msg.get("screen_locked", False),
                    idle_seconds=msg.get("idle_seconds", 0),
                    cpu_percent=msg.get("cpu_percent", 0.0)
                )
            elif msg_type == "GOING_TO_SLEEP":
                await state_manager.handle_going_to_sleep(pc_id)
            elif msg_type == "SOFTWARE_REPORT":
                packages = msg.get("packages", [])
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE pcs SET installed_software = $1::jsonb WHERE pc_id = $2",
                        json.dumps(packages), pc_id
                    )
    except Exception as e:
        logger.error(f"Error handling agent connection {addr}: {e}")
    finally:
        logger.info(f"Agent connection closed: {addr}")
        writer.close()
        await writer.wait_closed()

async def start_tcp_server(state_manager: PCStateManager, ws_manager: ConnectionManager, pool, host: str, port: int):
    async def handler(reader, writer):
        await handle_agent_connection(reader, writer, state_manager, ws_manager, pool)
        
    server = await asyncio.start_server(handler, host, port)
    logger.info(f"TCP server listening on {host}:{port}")
    return server
