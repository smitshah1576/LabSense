# LabSense — Ubuntu / Linux PC Complete Setup Guide

This guide provides end-to-end instructions for installing and running the entire **LabSense** stack (Database, Backend API + TCP Server, Frontend Web App, and Lab Client Agent) on a fresh **Ubuntu (22.04 / 24.04 LTS)** machine.

---

## Architecture & Port Summary

| Component | Technology | Default Port | Description |
|---|---|---|---|
| **PostgreSQL Database** | Docker (Postgres 16) | `5432` | Relational DB with schema & seed data |
| **pgAdmin** *(optional)* | Docker (pgadmin4) | `5050` | Web UI for PostgreSQL management |
| **Backend API & WebSockets** | FastAPI / Uvicorn | `8000` | REST API + WebSocket broadcaster |
| **Backend TCP Server** | Python AsyncIO Streams | `9000` | Ingests agent telemetry & heartbeats |
| **Frontend** | React 18 + Vite | `5173` | Lab management dashboard |
| **Client PC Agent** | Python / systemd | N/A (client) | Sends heartbeats to server port `9000` |

---

## Phase 1: System Prerequisites & Dependencies

Open a terminal on your Ubuntu machine and run:

```bash
# 1. Update package index and system packages
sudo apt update && sudo apt upgrade -y

# 2. Install essential build tools, Git, and Python
sudo apt install -y git curl wget build-essential \
  python3 python3-pip python3-venv python3-dev \
  net-tools ufw
```

### Install Node.js (v20 LTS) & npm
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify versions
node -v   # Should be v20.x.x
npm -v    # Should be v10.x.x
```

### Install Docker & Docker Compose
```bash
# Add Docker's official GPG key:
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up Docker repository:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine and Compose Plugin:
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow running Docker without sudo (requires logout/login or newgrp):
sudo usermod -aG docker $USER
newgrp docker

# Verify Docker is running
docker --version
docker compose version
```

---

## Phase 2: Clone Repository & Project Structure

```bash
# Clone the repository (if not already cloned)
git clone https://github.com/smitshah1576/LabSense.git
cd LabSense
```

Project layout:
```text
LabSense/
├── docker-compose.yml       # Database & pgAdmin services
├── docker/
│   └── init.sql             # DB Schema and seed data
├── backend/                 # FastAPI REST API + AsyncIO TCP Server
│   ├── requirements.txt
│   ├── .env
│   └── app/
├── frontend/                # React 18 + Vite Web App
│   ├── package.json
│   └── src/
└── agent/                   # Linux client daemon
    ├── deploy_agent.sh
    └── labsense_agent/
```

---

## Phase 3: Start the Database (Docker)

From the project root directory (`LabSense/`):

```bash
# Start PostgreSQL and pgAdmin in detached background mode
docker compose up -d
```

### Verify Database:
```bash
# Check container status
docker compose ps

# Check database initialization logs
docker compose logs labsense-db
```

> **Default Database Credentials:**
> - Host: `localhost` (or server LAN IP)
> - Port: `5432`
> - User: `labsense`
> - Password: `labsense_dev`
> - Database: `labsense`
>
> **Default pgAdmin Access:**
> - URL: `http://localhost:5050`
> - Email: `admin@labsense.dev`
> - Password: `admin`

---

## Phase 4: Backend Setup (FastAPI & TCP Server)

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create Python virtual environment
python3 -m venv .venv

# 3. Activate the virtual environment
source .venv/bin/activate

# 4. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5. Verify or create the .env configuration
cat <<EOF > .env
LABSENSE_DATABASE_URL=postgresql://labsense:labsense_dev@localhost:5432/labsense
LABSENSE_JWT_SECRET=labsense-dev-secret-change-in-production
LABSENSE_TCP_HOST=0.0.0.0
LABSENSE_TCP_PORT=9000
EOF

# 6. Start the FastAPI backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> The backend initializes:
> 1. PostgreSQL async connection pool (`asyncpg`)
> 2. `PCStateManager` in-memory store
> 3. WebSocket broadcasting manager
> 4. Raw TCP Server on `0.0.0.0:9000` for client heartbeats
> 5. HTTP API on `0.0.0.0:8000` (docs available at `http://localhost:8000/docs`)

---

## Phase 5: Frontend Setup (React & Vite)

Open a **new terminal window** and run:

```bash
# 1. Navigate to frontend directory
cd LabSense/frontend

# 2. Install Node dependencies
npm install

# 3. Start Vite development server
npm run dev -- --host 0.0.0.0
```

> Frontend is now running at `http://localhost:5173` (or `http://<YOUR_UBUNTU_IP>:5173`).
> 
> **Default Seed Logins:**
> - Admin: `admin@labsense.dev` / `password123`
> - Professor: `prof@labsense.dev` / `password123`
> - Student: `student@labsense.dev` / `password123`

---

## Phase 6: Agent Setup & Testing

### Option A: Run Mock Agent for testing
In a new terminal:
```bash
cd LabSense/agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python mock_agent.py
```

### Option B: Deploy Live Systemd Linux Agent
To deploy the background telemetry agent on this PC (or any lab client PC):
```bash
cd LabSense/agent

# Deploy as systemd service (replace 127.0.0.1 with Server IP if on client PC)
sudo ./deploy_agent.sh --server-host 127.0.0.1 --server-port 9000 --pc-id lab-a-pc-1
```

Useful agent management commands:
```bash
# Check service status
sudo systemctl status labsense-agent

# View live real-time logs
sudo journalctl -u labsense-agent -f

# Restart or Stop
sudo systemctl restart labsense-agent
sudo systemctl stop labsense-agent
```

---

## Phase 7: Firewall Configuration (For LAN Lab Access)

If other PCs in the lab need to connect to this server, allow the required ports in UFW:

```bash
# Allow SSH (important if connecting remotely!)
sudo ufw allow 22/tcp

# Allow Frontend
sudo ufw allow 5173/tcp

# Allow Backend API & WebSockets
sudo ufw allow 8000/tcp

# Allow Agent TCP Heartbeat Server
sudo ufw allow 9000/tcp

# (Optional) Allow pgAdmin & Postgres
sudo ufw allow 5050/tcp
sudo ufw allow 5432/tcp

# Enable firewall
sudo ufw enable
sudo ufw status
```

---

## Quick Reference: Starting Everything Daily

```bash
# 1. Start Database
cd ~/LabSense
docker compose up -d

# 2. Start Backend (Terminal 1)
cd ~/LabSense/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Start Frontend (Terminal 2)
cd ~/LabSense/frontend
npm run dev -- --host 0.0.0.0
```
