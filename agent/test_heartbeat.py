"""Single-shot heartbeat probe — tests the wire protocol with no agent involved.

This is the fastest way to answer "is it the network, the protocol, or the
agent?".  It opens a raw TCP connection to the backend, sends exactly one
length-prefixed JSON HEARTBEAT, and reports anything the server sends back.

Usage:
    python test_heartbeat.py <SERVER_HOST> [PC_ID] [PORT]

Examples:
    python test_heartbeat.py 10.234.237.199                  # defaults to lab-a-pc-1:9000
    python test_heartbeat.py 10.234.237.199 lab-a-pc-3
    python test_heartbeat.py 10.234.237.199 bogus-pc         # expect a REJECTED reply

What the outcomes mean:
    "Connection refused"     backend isn't running, or isn't listening on 0.0.0.0
    "timed out"              firewall dropping the packets, or Wi-Fi client isolation
    "SENT, no reply"         accepted — check the dashboard for the PC turning IN_USE
    "REJECTED"               pc_id isn't registered in the pcs table; heartbeats
                             from it are discarded
"""

import json
import socket
import struct
import sys
from datetime import datetime, timezone

CONNECT_TIMEOUT = 10.0
REPLY_TIMEOUT = 3.0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0

    host = sys.argv[1]
    pc_id = sys.argv[2] if len(sys.argv) > 2 else "lab-a-pc-1"
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 9000

    msg = {
        "type": "HEARTBEAT",
        "pc_id": pc_id,
        "session_active": True,
        "screen_locked": False,
        "idle_seconds": 5,
        "cpu_percent": 42.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload = json.dumps(msg).encode("utf-8")
    frame = struct.pack(">I", len(payload)) + payload

    print(f"Connecting to {host}:{port} as pc_id={pc_id} ...")
    try:
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT) as sock:
            print("  connected")
            sock.sendall(frame)
            print(f"  sent {len(frame)} bytes ({len(payload)}-byte payload)")

            # The server only replies to say something is wrong, so a timeout
            # here is the success case.
            sock.settimeout(REPLY_TIMEOUT)
            try:
                header = sock.recv(4)
            except socket.timeout:
                print("\nSENT, no reply - the server accepted it.")
                print(f"Now check the dashboard: '{pc_id}' should read IN_USE,")
                print("then fall back to Available after the 15s grace period.")
                return 0

            if not header:
                print("\nServer closed the connection without replying.")
                return 1

            length = struct.unpack(">I", header)[0]
            body = b""
            while len(body) < length:
                chunk = sock.recv(length - len(body))
                if not chunk:
                    break
                body += chunk

            reply = json.loads(body.decode("utf-8"))
            print(f"\nServer replied: {reply}")
            if reply.get("type") == "REJECTED":
                print(f"\npc_id '{pc_id}' is NOT registered - its heartbeats are discarded.")
                print("Register it (POST /admin/pcs) or use an existing pc_id:")
                print('  docker exec -it labsense-db psql -U labsense -d labsense '
                      '-c "SELECT pc_id FROM pcs;"')
            return 1

    except ConnectionRefusedError:
        print(f"\nConnection REFUSED by {host}:{port}.")
        print("The host is reachable but nothing is listening. Is the backend running?")
        print("On the server:  netstat -ano | findstr \":9000\"")
        return 1
    except (socket.timeout, TimeoutError):
        print(f"\nConnection to {host}:{port} TIMED OUT.")
        print("Packets are being dropped, not refused. Usual causes:")
        print("  - Windows Defender Firewall has no inbound rule for port 9000")
        print("  - the Wi-Fi network isolates clients from each other")
        print("  - the two machines are on different subnets")
        return 1
    except OSError as exc:
        print(f"\nNetwork error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
