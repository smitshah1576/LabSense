import asyncio
import json
import struct
import logging
from typing import Optional, TYPE_CHECKING
from ..state.pc_state_manager import PCStateManager
from ..ws.manager import ConnectionManager
from ..models.enums import PCState

if TYPE_CHECKING:
    from .registry import AgentRegistry

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
                                  state_manager: PCStateManager, ws_manager: ConnectionManager, pool,
                                  agent_registry: "AgentRegistry"):
    addr = writer.get_extra_info('peername')
    logger.info(f"New agent connection from {addr}")
    pc_id = None
    # Cache of validated pc_ids for this connection — one DB lookup per pc_id,
    # not per message.  True = registered, False = rejected.
    validated_pcs: dict[str, bool] = {}
    # pc_ids registered with agent_registry by this connection, for cleanup.
    registered_pcs: set[str] = set()
    try:
        while True:
            msg = await read_message(reader)
            if msg is None:
                break
                
            msg_type = msg.get("type")
            pc_id = msg.get("pc_id")
            
            if not pc_id:
                continue

            # ── Validate pc_id against DB on first encounter ──
            if pc_id not in validated_pcs:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT is_maintenance FROM pcs WHERE pc_id = $1", pc_id
                    )
                validated_pcs[pc_id] = row is not None

                if row is not None:
                    # Register for pushes, then tell the agent where it
                    # stands. Sending on every connect is what re-shows the
                    # maintenance notice after each boot until it is cleared.
                    agent_registry.register(pc_id, writer)
                    registered_pcs.add(pc_id)
                    await agent_registry.send_maintenance_status(
                        pc_id, bool(row["is_maintenance"])
                    )

            if not validated_pcs[pc_id]:
                # Tell the agent why, then hang up. Dropping these silently
                # made a misconfigured pc_id indistinguishable from a healthy
                # connection on the agent side — it logged a successful send
                # every 5s while nothing reached the dashboard.
                logger.error(
                    "Rejecting unregistered pc_id '%s' from %s - "
                    "register it via POST /admin/pcs first",
                    pc_id, addr,
                )
                writer.write(encode_message({
                    "type": "REJECTED",
                    "pc_id": pc_id,
                    "reason": "pc_id is not registered in the pcs table",
                }))
                await writer.drain()
                break

            if msg_type == "HEARTBEAT":
                transition = await state_manager.handle_heartbeat(
                    pc_id=pc_id,
                    session_active=msg.get("session_active", False),
                    screen_locked=msg.get("screen_locked", False),
                    idle_seconds=msg.get("idle_seconds", 0),
                    cpu_percent=msg.get("cpu_percent", 0.0)
                )
                # Broadcast full telemetry to all WS clients on every heartbeat
                live = await state_manager.get_state(pc_id)
                if live:
                    await ws_manager.broadcast_pc_heartbeat(
                        pc_id=pc_id,
                        state=live.current_state.value,
                        session_active=live.session_active,
                        screen_locked=live.screen_locked,
                        idle_seconds=live.idle_seconds,
                        cpu_percent=live.cpu_percent,
                    )
            elif msg_type == "GOING_TO_SLEEP":
                await state_manager.handle_going_to_sleep(pc_id)
            elif msg_type == "SHUTTING_DOWN":
                await state_manager.handle_shutting_down(pc_id)
            elif msg_type == "SOFTWARE_REPORT":
                packages = msg.get("packages", [])
                async with pool.acquire() as conn:
                    # The pool registers a jsonb codec (see database.py), so
                    # the list is encoded here — passing a pre-dumped string
                    # would double-encode it.
                    await conn.execute(
                        "UPDATE pcs SET installed_software = $1::jsonb WHERE pc_id = $2",
                        packages, pc_id
                    )
    except Exception as e:
        logger.error(f"Error handling agent connection {addr}: {e}")
    finally:
        logger.info(f"Agent connection closed: {addr}")
        for registered in registered_pcs:
            agent_registry.unregister(registered, writer)
        writer.close()
        await writer.wait_closed()

async def start_tcp_server(state_manager: PCStateManager, ws_manager: ConnectionManager, pool,
                           agent_registry: "AgentRegistry", host: str, port: int):
    async def handler(reader, writer):
        await handle_agent_connection(reader, writer, state_manager, ws_manager, pool, agent_registry)
        
    server = await asyncio.start_server(handler, host, port)
    logger.info(f"TCP server listening on {host}:{port}")
    return server
