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
SOFTWARE_SCAN_INTERVAL: float = float(os.environ.get('LABSENSE_SOFTWARE_SCAN_INTERVAL', '300.0'))

# Unique identifier for this PC; defaults to machine hostname if not specified
PC_ID: str = os.environ.get('LABSENSE_PC_ID', socket.gethostname())

# Delay in seconds to wait before attempting to reconnect after connection loss
RECONNECT_DELAY: float = float(os.environ.get('LABSENSE_RECONNECT_DELAY', '5.0'))
