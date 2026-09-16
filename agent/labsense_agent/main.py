"""LabSense Agent — main entry point.

Orchestrates the single-threaded asyncio event loop with three long-running
tasks:

1. **Heartbeat Task** — periodic telemetry collection and HEARTBEAT message
   sending every ``HEARTBEAT_INTERVAL`` seconds.
2. **D-Bus Task** — ``LogindMonitor.connect_and_listen()`` subscribing to
   systemd-logind signals (sleep, shutdown, lock/unlock).
3. **Software Scan Task** — periodic ``scan_all_software()`` and
   ``SOFTWARE_REPORT`` sending every ``SOFTWARE_SCAN_INTERVAL`` seconds.

Critical sleep/shutdown flow:

1.  At startup, an ``InhibitorLock`` is acquired.  This **delays** (not
    blocks) the OS from suspending until we release it.
2.  On ``PrepareForSleep(True)``: send ``GOING_TO_SLEEP``, drain the TCP
    writer, *then* release the inhibitor lock.  The OS may now suspend.
3.  On ``PrepareForSleep(False)`` (resume): re-acquire the inhibitor lock
    for the next sleep cycle.

Usage::

    python -m labsense_agent.main
"""

from __future__ import annotations

import asyncio
import functools
import logging
import signal
import sys

from . import config
from .dbus_monitor import LogindMonitor
from .heartbeat import HeartbeatClient
from .inhibitor import InhibitorLock
from .software_scan import scan_all_software
from .telemetry import get_cpu_percent, get_idle_seconds, get_screen_locked, get_session_active

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared mutable state — written by D-Bus callbacks, read by heartbeat loop
# ---------------------------------------------------------------------------
_screen_locked: bool = False


# ---------------------------------------------------------------------------
# D-Bus signal callbacks
# ---------------------------------------------------------------------------

async def _on_prepare_sleep(
    going_to_sleep: bool,
    heartbeat_client: HeartbeatClient,
    inhibitor: InhibitorLock,
) -> None:
    """Handle ``PrepareForSleep`` signal from logind.

    When ``going_to_sleep`` is ``True``:
    1. Send ``GOING_TO_SLEEP`` over the TCP connection.
    2. Await ``drain()`` — guarantees bytes are in the kernel send buffer.
    3. Release the inhibitor lock — the OS may now actually suspend.

    When ``going_to_sleep`` is ``False`` (resume from sleep):
    1. Re-acquire the inhibitor lock for the next sleep cycle.
    2. Re-establish the TCP connection (the NIC was down during sleep).
    """
    if going_to_sleep:
        logger.info('System preparing to sleep — sending GOING_TO_SLEEP')
        await heartbeat_client.send_going_to_sleep()
        await inhibitor.release()
        logger.info('Inhibitor lock released — OS may suspend now')
    else:
        logger.info('System resumed from sleep — re-acquiring inhibitor lock')
        await inhibitor.acquire()
        # The TCP connection is likely dead after sleep; reconnect.
        await heartbeat_client.close()
        await heartbeat_client.connect()


async def _on_prepare_shutdown(
    going_to_shutdown: bool,
    heartbeat_client: HeartbeatClient,
    inhibitor: InhibitorLock,
) -> None:
    """Handle ``PrepareForShutdown`` signal from logind."""
    if going_to_shutdown:
        logger.info('System shutting down — sending GOING_TO_SLEEP')
        await heartbeat_client.send_going_to_sleep()
        await inhibitor.release()
        await heartbeat_client.close()
        logger.info('Shutdown cleanup complete')


async def _on_lock() -> None:
    """Handle ``Lock`` signal from logind."""
    global _screen_locked
    _screen_locked = True
    logger.info('Screen locked')


async def _on_unlock() -> None:
    """Handle ``Unlock`` signal from logind."""
    global _screen_locked
    _screen_locked = False
    logger.info('Screen unlocked')


# ---------------------------------------------------------------------------
# Long-running task coroutines
# ---------------------------------------------------------------------------

async def _heartbeat_loop(client: HeartbeatClient) -> None:
    """Periodically gather telemetry and send HEARTBEAT messages.

    Runs indefinitely.  On connection loss, reconnects with exponential
    back-off before resuming the heartbeat cadence.
    """
    # Prime the CPU percentage tracker (first call always returns 0.0).
    get_cpu_percent()

    while True:
        try:
            if not await client.ensure_connected():
                await client.reconnect_with_backoff()
                continue

            # Gather telemetry — all non-blocking.
            cpu = get_cpu_percent()
            session_active = get_session_active()
            screen_locked = await get_screen_locked() or _screen_locked
            idle_seconds = await get_idle_seconds()

            ok = await client.send_heartbeat(
                session_active=session_active,
                screen_locked=screen_locked,
                idle_seconds=idle_seconds,
                cpu_percent=cpu,
            )
            if not ok:
                # Connection failed mid-send; will reconnect next iteration.
                await client.reconnect_with_backoff()
                continue

        except asyncio.CancelledError:
            logger.info('Heartbeat task cancelled')
            raise
        except Exception:
            logger.exception('Unexpected error in heartbeat loop')

        await asyncio.sleep(config.HEARTBEAT_INTERVAL)


async def _dbus_supervisor(monitor: LogindMonitor) -> None:
    """Keep the D-Bus listener alive for the lifetime of the agent.

    ``connect_and_listen()`` returns whenever the bus disconnects and raises if
    it can't connect at all (no logind, D-Bus restarted, running on a machine
    without a system bus).  Neither case should take the agent down with it —
    losing sleep/lock events is a degradation, but losing the heartbeat is a
    PC vanishing from the dashboard.  So supervise and retry indefinitely.
    """
    backoff = config.RECONNECT_DELAY

    while True:
        try:
            await monitor.connect_and_listen()
            # Returned normally — the bus disconnected.
            logger.warning('D-Bus listener stopped; restarting in %.1fs', backoff)
        except asyncio.CancelledError:
            logger.info('D-Bus supervisor cancelled')
            raise
        except Exception as exc:
            logger.error(
                'D-Bus listener failed (%s) — retrying in %.1fs. '
                'Sleep/lock events are unavailable until it recovers; '
                'heartbeats are unaffected.',
                exc, backoff,
            )

        await monitor.disconnect()
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60.0)


async def _software_scan_loop(client: HeartbeatClient) -> None:
    """Periodically scan installed software and send SOFTWARE_REPORT.

    Runs every ``SOFTWARE_SCAN_INTERVAL`` seconds.  An initial scan fires
    immediately on startup.
    """
    while True:
        try:
            if client.connected:
                packages = await scan_all_software()
                await client.send_software_report(packages)
            else:
                logger.debug(
                    'Skipping software scan — not connected'
                )
        except asyncio.CancelledError:
            logger.info('Software scan task cancelled')
            raise
        except Exception:
            logger.exception('Unexpected error in software scan loop')

        await asyncio.sleep(config.SOFTWARE_SCAN_INTERVAL)


# ---------------------------------------------------------------------------
# Shutdown handling
# ---------------------------------------------------------------------------

def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    shutdown_event: asyncio.Event,
) -> None:
    """Install SIGTERM / SIGINT handlers that set the shutdown event.

    On Windows or when ``loop.add_signal_handler`` is unavailable, falls back
    to ``signal.signal()`` (less clean but functional for development).
    """
    def _trigger_shutdown(signame: str) -> None:
        logger.info('Received %s — initiating graceful shutdown', signame)
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(
                sig,
                functools.partial(_trigger_shutdown, sig.name),
            )
        except NotImplementedError:
            # Windows or unsupported platform — use old-style handler.
            signal.signal(
                sig,
                lambda s, _f, _name=sig.name: _trigger_shutdown(_name),
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _run() -> None:
    """Core async entry point."""
    logger.info(
        'LabSense Agent starting (pc_id=%s, server=%s:%d)',
        config.PC_ID,
        config.SERVER_HOST,
        config.SERVER_PORT,
    )

    # --- Initialise components ---
    heartbeat_client = HeartbeatClient()
    inhibitor = InhibitorLock()

    logind_monitor = LogindMonitor(
        on_prepare_sleep=functools.partial(
            _on_prepare_sleep,
            heartbeat_client=heartbeat_client,
            inhibitor=inhibitor,
        ),
        on_prepare_shutdown=functools.partial(
            _on_prepare_shutdown,
            heartbeat_client=heartbeat_client,
            inhibitor=inhibitor,
        ),
        on_lock=_on_lock,
        on_unlock=_on_unlock,
    )

    # --- Acquire inhibitor lock (before first sleep event) ---
    try:
        await asyncio.wait_for(inhibitor.acquire(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning(
            'Inhibitor lock acquisition timed out after 5s — '
            'continuing without sleep inhibitor (D-Bus may be unresponsive)'
        )
    except Exception:
        logger.exception('Failed to acquire inhibitor lock — continuing without it')

    # --- Establish initial TCP connection ---
    await heartbeat_client.connect()

    # --- Shutdown plumbing ---
    shutdown_event = asyncio.Event()
    _install_signal_handlers(asyncio.get_running_loop(), shutdown_event)

    # --- Launch long-running tasks ---
    heartbeat_task = asyncio.create_task(
        _heartbeat_loop(heartbeat_client), name='heartbeat'
    )
    dbus_task = asyncio.create_task(
        _dbus_supervisor(logind_monitor), name='dbus-monitor'
    )
    software_task = asyncio.create_task(
        _software_scan_loop(heartbeat_client), name='software-scan'
    )
    shutdown_task = asyncio.create_task(
        shutdown_event.wait(), name='shutdown-wait'
    )

    logger.info('All tasks started — agent is running')

    # Only the heartbeat task and an explicit shutdown are terminal.  The
    # D-Bus and software-scan tasks are supervised and expected to outlive
    # transient failures; letting either end the agent was how a D-Bus hiccup
    # turned into a silent exit(0) that systemd's Restart=on-failure ignored.
    done, pending = await asyncio.wait(
        [heartbeat_task, shutdown_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Fold the supervised tasks back in so the cleanup below cancels them.
    pending |= {dbus_task, software_task}

    # --- Graceful cleanup ---
    logger.info('Shutting down …')

    # Cancel remaining tasks.
    for task in pending:
        task.cancel()

    # Wait for cancellation to propagate (with a timeout).
    if pending:
        await asyncio.wait(pending, timeout=5.0)

    # Log any unexpected exits.
    for task in done:
        if task.get_name() != 'shutdown-wait' and task.exception():
            logger.error(
                'Task %s exited with error: %s',
                task.get_name(),
                task.exception(),
            )

    # Release resources.
    await logind_monitor.disconnect()
    await heartbeat_client.close()
    await inhibitor.close()

    logger.info('LabSense Agent stopped')


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
        logger.info('Interrupted — exiting')
        sys.exit(0)


if __name__ == '__main__':
    main()
