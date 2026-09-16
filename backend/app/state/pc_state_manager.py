import asyncio
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

from ..models.enums import PCState
from ..config import settings

logger = logging.getLogger(__name__)

@dataclass
class PCLiveState:
    pc_id: str
    current_state: PCState = PCState.AVAILABLE
    session_active: bool = False
    screen_locked: bool = False
    idle_seconds: int = 0
    cpu_percent: float = 0.0
    last_heartbeat_at: Optional[datetime] = None
    staleness_task: Optional[asyncio.Task] = None

class PCStateManager:
    def __init__(self):
        self._states: dict[str, PCLiveState] = {}
        self._lock = asyncio.Lock()
        self._on_transition: Optional[Callable] = None  # callback for state changes
    
    def set_transition_callback(self, callback: Callable[[str, PCState, PCState], Awaitable[None]]):
        """Set callback called on state transitions: callback(pc_id, old_state, new_state)"""
        self._on_transition = callback
    
    async def _notify(self, transition: Optional[tuple[PCState, PCState]], pc_id: str) -> None:
        """Fire the transition callback, if any.

        Deliberately called *after* releasing ``self._lock``: the callback
        writes to Postgres and fans out to every connected WebSocket, and one
        slow browser must not stall heartbeat processing for every other PC.
        """
        if transition and self._on_transition:
            old_state, new_state = transition
            await self._on_transition(pc_id, old_state, new_state)

    async def handle_heartbeat(self, pc_id: str, session_active: bool, screen_locked: bool,
                                idle_seconds: int, cpu_percent: float) -> Optional[tuple[PCState, PCState]]:
        """Process a heartbeat. Returns (old_state, new_state) if a transition occurred, else None."""
        async with self._lock:
            if pc_id not in self._states:
                self._states[pc_id] = PCLiveState(pc_id=pc_id)
            
            state = self._states[pc_id]
            
            # If in MAINTENANCE, suppress all automatic transitions
            if state.current_state == PCState.MAINTENANCE:
                state.last_heartbeat_at = datetime.now(timezone.utc)
                state.session_active = session_active
                state.screen_locked = screen_locked
                state.idle_seconds = idle_seconds
                state.cpu_percent = cpu_percent
                self._reset_staleness_timer(pc_id)
                return None
            
            # Update telemetry
            state.session_active = session_active
            state.screen_locked = screen_locked
            state.idle_seconds = idle_seconds
            state.cpu_percent = cpu_percent
            state.last_heartbeat_at = datetime.now(timezone.utc)
            
            # Derive new state using the composite condition:
            # IN_USE = session_active AND (idle < threshold OR cpu > threshold OR screen_locked)
            old_state = state.current_state
            if session_active and (idle_seconds < settings.IDLE_THRESHOLD_SECONDS 
                                    or cpu_percent > settings.CPU_THRESHOLD_PERCENT 
                                    or screen_locked):
                new_state = PCState.IN_USE
            else:
                new_state = PCState.AVAILABLE
            
            state.current_state = new_state
            self._reset_staleness_timer(pc_id)

            transition = (old_state, new_state) if old_state != new_state else None

        await self._notify(transition, pc_id)
        return transition

    async def handle_going_to_sleep(self, pc_id: str) -> Optional[tuple[PCState, PCState]]:
        """Process a GOING_TO_SLEEP message."""
        async with self._lock:
            if pc_id not in self._states:
                self._states[pc_id] = PCLiveState(pc_id=pc_id)
            
            state = self._states[pc_id]
            if state.current_state == PCState.MAINTENANCE:
                return None

            old_state = state.current_state
            state.current_state = PCState.AVAILABLE_SLEEP

            # Cancel staleness timer — sleep is a known state
            if state.staleness_task:
                state.staleness_task.cancel()
                state.staleness_task = None

            transition = (
                (old_state, PCState.AVAILABLE_SLEEP)
                if old_state != PCState.AVAILABLE_SLEEP else None
            )

        await self._notify(transition, pc_id)
        return transition

    async def set_maintenance(self, pc_id: str, is_maintenance: bool) -> Optional[tuple[PCState, PCState]]:
        """Toggle maintenance mode."""
        async with self._lock:
            if pc_id not in self._states:
                self._states[pc_id] = PCLiveState(pc_id=pc_id)
            
            state = self._states[pc_id]
            old_state = state.current_state
            
            if is_maintenance:
                state.current_state = PCState.MAINTENANCE
            else:
                # When clearing maintenance, default to AVAILABLE
                state.current_state = PCState.AVAILABLE

            transition = (
                (old_state, state.current_state)
                if old_state != state.current_state else None
            )

        await self._notify(transition, pc_id)
        return transition

    def _reset_staleness_timer(self, pc_id: str):
        """Reset the heartbeat staleness timer for a PC."""
        state = self._states.get(pc_id)
        if not state:
            return
        
        if state.staleness_task:
            state.staleness_task.cancel()
        
        state.staleness_task = asyncio.create_task(self._staleness_timeout(pc_id))
    
    async def _staleness_timeout(self, pc_id: str):
        """After HEARTBEAT_TIMEOUT_SECONDS without a heartbeat, mark PC as AVAILABLE."""
        try:
            await asyncio.sleep(settings.HEARTBEAT_TIMEOUT_SECONDS)

            transition = None
            async with self._lock:
                state = self._states.get(pc_id)
                if state and state.current_state not in (PCState.MAINTENANCE, PCState.AVAILABLE_SLEEP):
                    old_state = state.current_state
                    state.current_state = PCState.AVAILABLE
                    logger.warning(f'PC {pc_id} heartbeat stale after {settings.HEARTBEAT_TIMEOUT_SECONDS}s, marking AVAILABLE')
                    if old_state != PCState.AVAILABLE:
                        transition = (old_state, PCState.AVAILABLE)

            await self._notify(transition, pc_id)
        except asyncio.CancelledError:
            pass  # Timer was reset by a new heartbeat
    
    async def remove_pc(self, pc_id: str) -> None:
        """Remove a PC from in-memory state and cancel its staleness timer."""
        async with self._lock:
            state = self._states.pop(pc_id, None)
            if state and state.staleness_task:
                state.staleness_task.cancel()

    async def get_state(self, pc_id: str) -> Optional[PCLiveState]:
        async with self._lock:
            return self._states.get(pc_id)
    
    async def get_all_states(self) -> dict[str, PCLiveState]:
        async with self._lock:
            return dict(self._states)
    
    async def get_lab_states(self, pc_ids: list[str]) -> dict[str, PCLiveState]:
        async with self._lock:
            return {pid: self._states[pid] for pid in pc_ids if pid in self._states}
