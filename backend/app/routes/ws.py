from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, Request
from ..auth.jwt_handler import verify_token
from ..database import get_pool
from fastapi import HTTPException

router = APIRouter(tags=["ws"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Verify JWT manually for websocket
    user = verify_token(token)
    if not user:
        await websocket.close(code=1008, reason="Invalid token")
        return
        
    ws_manager = websocket.app.state.ws_manager
    state_manager = websocket.app.state.pc_state_manager
    
    await ws_manager.connect(websocket)
    
    try:
        # Send initial full state snapshot
        states = await state_manager.get_all_states()
        snapshot = {
            "type": "initial_state",
            "pcs": [
                {
                    "pc_id": pc_id,
                    "state": state.current_state.value if hasattr(state.current_state, 'value') else str(state.current_state),
                    "session_active": state.session_active,
                    "screen_locked": state.screen_locked,
                    "cpu_percent": state.cpu_percent,
                    "idle_seconds": state.idle_seconds
                }
                for pc_id, state in states.items()
            ]
        }
        await websocket.send_json(snapshot)
        
        while True:
            # keep connection open, optionally receive messages from client
            data = await websocket.receive_text()
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        ws_manager.disconnect(websocket)
