"""LabSense Mock Agent for Demonstration.

Simulates periodic agent heartbeats from Windows to test state transitions
and real-time dashboard updates without needing a Linux VM or D-Bus.
"""

import asyncio
import json
import random
import struct
import sys
from datetime import datetime, timezone

SERVER_HOST = "localhost"
SERVER_PORT = 9000
PC_IDS = ["lab-a-pc-1", "lab-a-pc-2", "lab-a-pc-3", "lab-a-pc-4", "lab-a-pc-5"]


def encode_message(msg: dict) -> bytes:
    payload = json.dumps(msg).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


async def run_mock_pc(pc_id: str):
    """Simulates a single PC sending telemetry heartbeats."""
    while True:
        try:
            print(f"[{pc_id}] Connecting to backend {SERVER_HOST}:{SERVER_PORT}...")
            reader, writer = await asyncio.open_connection(SERVER_HOST, SERVER_PORT)
            print(f"[{pc_id}] Connected!")

            # Simulate state scenarios
            while True:
                # Randomize realistic telemetry
                session_active = random.choice([True, True, False])
                screen_locked = random.choice([False, False, True]) if session_active else False
                cpu_percent = round(random.uniform(1.0, 45.0) if session_active else random.uniform(0.1, 3.0), 1)
                idle_seconds = random.randint(0, 120) if session_active else random.randint(300, 1200)

                msg = {
                    "type": "HEARTBEAT",
                    "pc_id": pc_id,
                    "session_active": session_active,
                    "screen_locked": screen_locked,
                    "idle_seconds": idle_seconds,
                    "cpu_percent": cpu_percent,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                writer.write(encode_message(msg))
                await writer.drain()

                state_desc = "IN_USE" if session_active and (idle_seconds < 300 or cpu_percent > 5.0 or screen_locked) else "AVAILABLE"
                print(f"[{pc_id}] Heartbeat sent -> State: {state_desc} (CPU: {cpu_percent}%, Session: {session_active})")

                await asyncio.sleep(5.0)

        except (ConnectionRefusedError, OSError):
            print(f"[{pc_id}] Backend not reachable, retrying in 5s...")
            await asyncio.sleep(5.0)
        except Exception as e:
            print(f"[{pc_id}] Error: {e}, reconnecting...")
            await asyncio.sleep(5.0)


async def main():
    print("=" * 60)
    print(" LabSense Mock PC Agent Simulator")
    print(f" Simulating 5 PCs sending heartbeats to {SERVER_HOST}:{SERVER_PORT}")
    print("=" * 60)
    tasks = [run_mock_pc(pc_id) for pc_id in PC_IDS]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
