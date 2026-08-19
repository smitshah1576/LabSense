import json
import logging
from typing import Set
from fastapi import WebSocket
from ..models.enums import LabState

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        msg_str = json.dumps(message)
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_str)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                dead_connections.add(connection)
                
        for dead in dead_connections:
            self.disconnect(dead)

    async def broadcast_pc_update(self, pc_id: str, state_data):
        state_str = state_data.value if hasattr(state_data, 'value') else str(state_data)
        message = {
            "type": "pc_update",
            "pc_id": pc_id,
            "state": state_str
        }
        await self.broadcast(message)

    async def broadcast_lab_update(self, lab_id: str, lab_state: LabState):
        message = {
            "type": "lab_update",
            "lab_id": lab_id,
            "state": lab_state.value if hasattr(lab_state, 'value') else str(lab_state)
        }
        await self.broadcast(message)
