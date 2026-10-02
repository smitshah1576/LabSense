import asyncio
import logging
from collections import deque
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
    # Telemetry is None whenever no heartbeats are arriving (never reported,
    # stale, asleep, shut down) so a silent PC never shows old readings.
    session_active: Optional[bool] = None
    screen_locked: Optional[bool] = None
    idle_seconds: Optional[int] = None
    cpu_percent: Optional[float] = None
    last_heartbeat_at: Optional[datetime] = None
    staleness_task: Optional[asyncio.Task] = None
    # Recent CPU samples; CPU only counts when *all* of them exceed the threshold.
    cpu_samples: deque = field(default_factory=lambda: deque(maxlen=max(settings.CPU_WINDOW_HEARTBEATS, 1)))
    # When the screen went from unlocked to locked; None while unlocked.
    locked_since: Optional[datetime] = None

    def record_telemetry(self, session_active: bool, screen_locked: bool,
                         idle_seconds: int, cpu_percent: float, now: datetime) -> None:
        # Keyed on locked_since rather than the previous screen_locked, which
        # clear_telemetry() wipes: a PC that wakes still locked must not get a
        # fresh lock reserve.
        if not screen_locked:
            self.locked_since = None
        elif self.locked_since is None:
            self.locked_since = now
        self.session_active = session_active
        self.screen_locked = screen_locked
        self.idle_seconds = idle_seconds
        self.cpu_percent = cpu_percent
        self.cpu_samples.append(cpu_percent)
        self.last_heartbeat_at = now

    def clear_telemetry(self) -> bool:
        """Drop the displayed readings once the PC stops reporting.

        Returns True if there was anything to clear. ``last_heartbeat_at`` and
        the CPU/lock history are kept: they are still true, the readings aren't.
        """
        had_telemetry = self.cpu_percent is not None
        self.session_active = None
        self.screen_locked = None
        self.idle_seconds = None
        self.cpu_percent = None
        return had_telemetry

    def is_in_use(self, now: datetime) -> bool:
        """IN_USE = session_active AND (recent input OR sustained CPU OR recently locked).

        Sustained CPU means every one of the last CPU_WINDOW_HEARTBEATS samples
        is above the threshold (~15s at the default window), so a single spike
        from apt/snapd/indexing never marks an empty PC as in use, while a
        long-running job keeps a PC busy even with nobody touching it.
        """
        if not self.session_active:
            return False
        recent_input = self.idle_seconds < settings.IDLE_THRESHOLD_SECONDS
        busy_cpu = (
            len(self.cpu_samples) == self.cpu_samples.maxlen
            and min(self.cpu_samples) > settings.CPU_THRESHOLD_PERCENT
        )
        lock_reserve = (
            self.screen_locked
            and self.locked_since is not None
            and (now - self.locked_since).total_seconds() < settings.LOCK_RESERVE_SECONDS
        )
        return recent_input or busy_cpu or lock_reserve

class PCStateManager:
    def __init__(self):
        self._states: dict[str, PCLiveState] = {}
        self._lock = asyncio.Lock()
        self._on_transition: Optional[Callable] = None  # callback for state changes
        self._on_telemetry_cleared: Optional[Callable] = None  # callback when a PC stops reporting

    def set_transition_callback(self, callback: Callable[[str, PCState, PCState], Awaitable[None]]):
        """Set callback called on state transitions: callback(pc_id, old_state, new_state)"""
        self._on_transition = callback

    def set_telemetry_cleared_callback(self, callback: Callable[[str, PCState], Awaitable[None]]):
        """Set callback called when a PC's telemetry is cleared: callback(pc_id, current_state)"""
        self._on_telemetry_cleared = callback

    async def restore_maintenance(self, pc_ids: list[str]) -> None:
        """Seed the store with PCs flagged for maintenance in the database.

        Called once at startup. Maintenance is a manual flag, so it must
        outlive the in-memory store: without this the first heartbeat after a
        restart would recompute the state and silently drop it.
        """
        async with self._lock:
            for pc_id in pc_ids:
                self._states[pc_id] = PCLiveState(pc_id=pc_id, current_state=PCState.MAINTENANCE)

    async def _notify_cleared(self, cleared: bool, pc_id: str, state: PCState) -> None:
        """Fire the telemetry-cleared callback. Like ``_notify``, called outside the lock."""
        if cleared and self._on_telemetry_cleared:
            await self._on_telemetry_cleared(pc_id, state)

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
            now = datetime.now(timezone.utc)
            # Telemetry (and the CPU/lock history) is kept current even in
            # maintenance, so the rule is accurate the moment maintenance ends.
            state.record_telemetry(session_active, screen_locked, idle_seconds, cpu_percent, now)

            # If in MAINTENANCE, suppress all automatic transitions
            if state.current_state == PCState.MAINTENANCE:
                self._reset_staleness_timer(pc_id)
                return None

            old_state = state.current_state
            new_state = PCState.IN_USE if state.is_in_use(now) else PCState.AVAILABLE
            
            state.current_state = new_state
            self._reset_staleness_timer(pc_id)

            transition = (old_state, new_state) if old_state != new_state else None

        await self._notify(transition, pc_id)
        return transition

    async def handle_going_to_sleep(self, pc_id: str) -> Optional[tuple[PCState, PCState]]:
        """Process a GOING_TO_SLEEP message (clean suspend)."""
        return await self._go_offline(pc_id, PCState.AVAILABLE_SLEEP)

    async def handle_shutting_down(self, pc_id: str) -> Optional[tuple[PCState, PCState]]:
        """Process a SHUTTING_DOWN message (clean power-off or reboot).

        A PC that is off is simply free, so it maps to AVAILABLE — the same
        outcome as the staleness timeout, just without the 15s wait.
        """
        return await self._go_offline(pc_id, PCState.AVAILABLE)

    async def _go_offline(self, pc_id: str, new_state: PCState) -> Optional[tuple[PCState, PCState]]:
        """The agent announced it is about to stop reporting."""
        async with self._lock:
            if pc_id not in self._states:
                self._states[pc_id] = PCLiveState(pc_id=pc_id)

            state = self._states[pc_id]

            # Cancel staleness timer — the silence that follows is expected
            if state.staleness_task:
                state.staleness_task.cancel()
                state.staleness_task = None

            cleared = state.clear_telemetry()

            old_state = state.current_state
            # MAINTENANCE suppresses the transition, not the telemetry reset
            if old_state != PCState.MAINTENANCE:
                state.current_state = new_state
            current = state.current_state

            transition = (old_state, current) if old_state != current else None

        await self._notify(transition, pc_id)
        await self._notify_cleared(cleared, pc_id, current)
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
            cleared = False
            current = None
            async with self._lock:
                state = self._states.get(pc_id)
                if state:
                    # The readings are history in every state, MAINTENANCE included
                    cleared = state.clear_telemetry()
                    if state.current_state not in (PCState.MAINTENANCE, PCState.AVAILABLE_SLEEP):
                        old_state = state.current_state
                        state.current_state = PCState.AVAILABLE
                        logger.warning(f'PC {pc_id} heartbeat stale after {settings.HEARTBEAT_TIMEOUT_SECONDS}s, marking AVAILABLE')
                        if old_state != PCState.AVAILABLE:
                            transition = (old_state, PCState.AVAILABLE)
                    current = state.current_state

            await self._notify(transition, pc_id)
            await self._notify_cleared(cleared, pc_id, current)
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
