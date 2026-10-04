#!/usr/bin/env bash
# ==============================================================================
# LabSense Agent — Linux Automated Deployment Script (with Virtual Environment)
# ==============================================================================
# Usage:
#   sudo ./deploy_agent.sh [--server-host <IP>] [--server-port <PORT>] [--pc-id <PC_ID>]
# ==============================================================================

set -e

# Defaults
SERVER_HOST=""
SERVER_PORT="9000"
PC_ID=""
LOG_LEVEL="INFO"
INSTALL_DIR="/opt/labsense-agent"
VENV_DIR="$INSTALL_DIR/.venv"

# Colors for formatting
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}======================================================"
echo "       LabSense Agent Linux Deployment Setup"
echo -e "======================================================${NC}"

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run this deployment script as root or with sudo.${NC}"
    echo "Example: sudo $0 --server-host 192.168.1.100 --pc-id lab-a-pc-1"
    exit 1
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --server-host)
            SERVER_HOST="$2"
            shift 2
            ;;
        --server-port)
            SERVER_PORT="$2"
            shift 2
            ;;
        --pc-id)
            PC_ID="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: sudo $0 [--server-host <IP>] [--server-port <PORT>] [--pc-id <PC_ID>] [--log-level DEBUG|INFO]"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Prompt for Server Host if not provided
if [ -z "$SERVER_HOST" ]; then
    read -rp "Enter LabSense Backend Server IP/Host [e.g., 192.168.1.100]: " SERVER_HOST
    if [ -z "$SERVER_HOST" ]; then
        echo -e "${RED}Server Host IP is required.${NC}"
        exit 1
    fi
fi

# Prompt for PC ID if not provided
if [ -z "$PC_ID" ]; then
    DEFAULT_HOSTNAME=$(hostname)
    read -rp "Enter PC ID (must match database record) [default: $DEFAULT_HOSTNAME]: " PC_ID
    PC_ID=${PC_ID:-$DEFAULT_HOSTNAME}
fi

echo -e "\n${YELLOW}Deployment Configuration:${NC}"
echo "  - Install Directory : $INSTALL_DIR"
echo "  - Virtual Environment: $VENV_DIR"
echo "  - Server Host       : $SERVER_HOST"
echo "  - Server Port       : $SERVER_PORT"
echo "  - PC Identifier     : $PC_ID"
echo "  - Log Level         : $LOG_LEVEL"
echo ""
echo -e "${YELLOW}NOTE:${NC} the PC Identifier must already exist in the server's 'pcs' table."
echo "      Heartbeats from an unregistered pc_id are rejected by the server."
echo ""

# 1. Create installation directory
echo -e "${CYAN}[1/6] Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 2. Copy agent code to /opt/labsense-agent
echo -e "${CYAN}[2/6] Copying agent codebase to $INSTALL_DIR...${NC}"
cp -r "$SCRIPT_DIR/labsense_agent" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/probe_telemetry.py" "$INSTALL_DIR/"

# 3. Create Virtual Environment & Install dependencies inside it
echo -e "${CYAN}[3/6] Setting up Python virtual environment at $VENV_DIR...${NC}"

export DEBIAN_FRONTEND=noninteractive
APT_UPDATED=0

# Install apt packages, refreshing the package index once per run.
apt_install() {
    if ! command -v apt-get &>/dev/null; then
        echo -e "${RED}Error: apt-get not found. Install these packages manually, then re-run: $*${NC}"
        exit 1
    fi
    if [ "$APT_UPDATED" -eq 0 ]; then
        apt-get update -qq
        APT_UPDATED=1
    fi
    apt-get install -y -qq "$@"
}

if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}  Installing python3...${NC}"
    apt_install python3
fi

# Debian/Ubuntu ship the venv *module* with python3 itself, so
# `python3 -m venv --help` succeeds on a stock install. What is missing is
# ensurepip, which lives in python3.X-venv — without it venv creation fails
# with "ensurepip is not available". So test for ensurepip directly.
if ! python3 -c 'import ensurepip' &>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    echo -e "${YELLOW}  Installing python${PY_VER}-venv package...${NC}"
    # The versioned package matches whichever python3 is on PATH; the generic
    # one only follows the distro's default interpreter.
    apt_install "python${PY_VER}-venv" || apt_install python3-venv || true
    if ! python3 -c 'import ensurepip' &>/dev/null; then
        echo -e "${RED}Error: python3 still cannot create virtual environments.${NC}"
        echo "Install it manually, then re-run: sudo apt install python${PY_VER}-venv"
        exit 1
    fi
fi

# An earlier failed run leaves a venv with no pip in it; rebuild that from
# scratch. A working venv is kept, so a redeploy doesn't reinstall everything.
if ! "$VENV_DIR/bin/python3" -m pip --version &>/dev/null; then
    python3 -m venv --clear "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# 4. Create system user for LabSense
echo -e "${CYAN}[4/6] Setting up 'labsense' system user...${NC}"
if ! id "labsense" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin labsense
fi
# 'input' lets the agent timestamp keyboard/mouse events for idle time. The
# event bytes are discarded unread — only *when* input happened is recorded.
usermod -aG input labsense
chown -R labsense:labsense "$INSTALL_DIR"

# 5. Create systemd service file using venv python3
echo -e "${CYAN}[5/6] Configuring systemd service...${NC}"
SERVICE_FILE="/etc/systemd/system/labsense-agent.service"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=LabSense PC Monitoring Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=labsense
# Read access to /dev/input/event* for precise idle time (timing only).
SupplementaryGroups=input
Environment=LABSENSE_SERVER_HOST=$SERVER_HOST
Environment=LABSENSE_SERVER_PORT=$SERVER_PORT
Environment=LABSENSE_PC_ID=$PC_ID
Environment=LABSENSE_LOG_LEVEL=$LOG_LEVEL
ExecStart=$VENV_DIR/bin/python3 -m labsense_agent.main
WorkingDirectory=$INSTALL_DIR
# 'always', not 'on-failure': a clean exit(0) is still an agent that stopped
# reporting, and a PC silently vanishing from the dashboard is the failure
# mode this service exists to prevent.
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "$SERVICE_FILE"

# 6. Enable and start systemd service
echo -e "${CYAN}[6/6] Reloading systemd and starting service...${NC}"
systemctl daemon-reload
systemctl enable labsense-agent
systemctl restart labsense-agent

echo ""
echo -e "${GREEN}======================================================"
echo "    LabSense Agent Successfully Deployed & Started!"
echo -e "======================================================${NC}"
echo ""
echo -e "Useful Commands:"
echo -e "  • Check service status  : ${YELLOW}sudo systemctl status labsense-agent${NC}"
echo -e "  • Watch live logs       : ${YELLOW}sudo journalctl -u labsense-agent -f${NC}"
echo -e "  • Restart service       : ${YELLOW}sudo systemctl restart labsense-agent${NC}"
echo -e "  • Stop service          : ${YELLOW}sudo systemctl stop labsense-agent${NC}"
echo -e "  • Check telemetry probes: ${YELLOW}sudo -u labsense $VENV_DIR/bin/python3 $INSTALL_DIR/probe_telemetry.py${NC}"
echo ""
echo -e "Note: the 'labsense' user is in the 'input' group so it can measure idle"
echo -e "time. It records only when input happened, never which keys were pressed."
echo ""
