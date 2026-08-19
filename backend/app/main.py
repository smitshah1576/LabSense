from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging

from .config import settings
from .database import create_pool, get_pool, close_pool
from .state.pc_state_manager import PCStateManager
from .ws.manager import ConnectionManager
from .tcp.server import start_tcp_server

from .routes import auth, labs, pcs, software, timetable, damage_reports, ws

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up LabSense API...")
    
    # 1. Create DB pool
    pool = await create_pool()
    
    # 2. Initialize Managers
    state_manager = PCStateManager()
    ws_manager = ConnectionManager()
    
    app.state.pc_state_manager = state_manager
    app.state.ws_manager = ws_manager
    app.state.db_pool = pool
    
    # 3. Setup transition callback
    async def on_transition(pc_id: str, old_state, new_state):
        try:
            # Broadcast to WS
            await ws_manager.broadcast_pc_update(pc_id, new_state)
            
            # Write to DB
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO state_transitions (pc_id, from_state, to_state)
                    VALUES ($1, $2, $3)
                    """,
                    pc_id, 
                    old_state.value if hasattr(old_state, 'value') else str(old_state),
                    new_state.value if hasattr(new_state, 'value') else str(new_state)
                )
        except Exception as e:
            logger.error(f"Error in transition callback for PC {pc_id}: {e}")
            
    state_manager.set_transition_callback(on_transition)
    
    # 4. Start TCP Server
    tcp_server = await start_tcp_server(
        state_manager=state_manager,
        ws_manager=ws_manager,
        pool=pool,
        host=settings.TCP_HOST,
        port=settings.TCP_PORT
    )
    app.state.tcp_server = tcp_server
    
    yield
    
    # Shutdown
    logger.info("Shutting down LabSense API...")
    
    if hasattr(app.state, "tcp_server"):
        app.state.tcp_server.close()
        await app.state.tcp_server.wait_closed()
        
    await close_pool()

app = FastAPI(title="LabSense API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(labs.router)
app.include_router(pcs.router)
app.include_router(software.router)
app.include_router(timetable.router)
app.include_router(damage_reports.router)
app.include_router(ws.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
