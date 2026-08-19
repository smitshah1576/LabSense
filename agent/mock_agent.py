"""LabSense Mock Agent for Demonstration.

Simulates periodic agent heartbeats from Windows (or any OS) to test
state transitions and real-time dashboard updates without needing
a Linux VM or D-Bus.

Usage:
    python mock_agent.py <SERVER_HOST> [SERVER_PORT]

Examples:
    python mock_agent.py 192.168.1.100          # remote backend, port 9000
    python mock_agent.py 192.168.1.100 9001     # remote backend, custom port
    python mock_agent.py localhost               # local backend (same machine)

Or via environment variables:
    LABSENSE_SERVER_HOST=192.168.1.100 python mock_agent.py
"""

import asyncio
import json
import os
import random
import struct
import sys
from datetime import datetime, timezone

# Resolve server address: CLI args > env vars > defaults
SERVER_HOST = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LABSENSE_SERVER_HOST", "localhost")
SERVER_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("LABSENSE_SERVER_PORT", "9000"))
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
            print(f"[{pc_id}] Backend not reachable at {SERVER_HOST}:{SERVER_PORT}, retrying in 5s...")
            await asyncio.sleep(5.0)
        except Exception as e:
            print(f"[{pc_id}] Error: {e}, reconnecting...")
            await asyncio.sleep(5.0)


async def main():
    print("=" * 60)
    print("  LabSense Mock PC Agent Simulator")
    print(f"  Target: {SERVER_HOST}:{SERVER_PORT}")
    print(f"  Simulating {len(PC_IDS)} PCs: {', '.join(PC_IDS)}")
    print("=" * 60)
    tasks = [run_mock_pc(pc_id) for pc_id in PC_IDS]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
