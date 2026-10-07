"""LabSense Agent Configuration.

Reads configuration settings from environment variables prefixed with LABSENSE_
with sensible defaults for development and local testing.
"""

import os
import socket

# Host address / IP of the LabSense central server
SERVER_HOST: str = os.environ.get('LABSENSE_SERVER_HOST', 'localhost')

# TCP port number on which the LabSense central server is listening
SERVER_PORT: int = int(os.environ.get('LABSENSE_SERVER_PORT', '9000'))

# Interval in seconds between periodic heartbeat telemetry messages
HEARTBEAT_INTERVAL: float = float(os.environ.get('LABSENSE_HEARTBEAT_INTERVAL', '5.0'))

# Interval in seconds between full software package inventory scans
SOFTWARE_SCAN_INTERVAL: float = float(os.environ.get('LABSENSE_SOFTWARE_SCAN_INTERVAL', '900.0'))

# Unique identifier for this PC; defaults to machine hostname if not specified
PC_ID: str = os.environ.get('LABSENSE_PC_ID', socket.gethostname())

# Delay in seconds to wait before attempting to reconnect after connection loss
RECONNECT_DELAY: float = float(os.environ.get('LABSENSE_RECONNECT_DELAY', '5.0'))

# Root logging level. Set to DEBUG to see every individual heartbeat; at the
# default INFO level only the first heartbeat after each (re)connect and a
# periodic keep-alive summary are logged.
LOG_LEVEL: str = os.environ.get('LABSENSE_LOG_LEVEL', 'INFO').upper()

# Number of heartbeats between periodic INFO-level "still alive" log lines.
# At the default 5s interval, 12 heartbeats is roughly one line per minute.
HEARTBEAT_LOG_EVERY: int = int(os.environ.get('LABSENSE_HEARTBEAT_LOG_EVERY', '12'))

# Directory where the agent publishes this PC's maintenance status for the
# per-user desktop notifier. systemd creates it (RuntimeDirectory=labsense);
# being under /run, it starts empty on every boot.
STATE_DIR: str = os.environ.get('LABSENSE_STATE_DIR', '/run/labsense')

# Seconds between the desktop notifier's checks of the maintenance status file.
NOTIFIER_POLL_INTERVAL: float = float(os.environ.get('LABSENSE_NOTIFIER_POLL_INTERVAL', '5.0'))
