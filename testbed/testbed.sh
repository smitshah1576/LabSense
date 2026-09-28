#!/usr/bin/env bash
# ==============================================================================
# LabSense testbed — the whole system on one machine, ready for E2E testing.
#
#   database   PostgreSQL 16 in Docker (repo docker-compose.yml, seeded by
#              docker/init.sql)                                     :5432
#   backend    FastAPI + raw TCP heartbeat server (uvicorn --reload)
#                                                        :8000 (HTTP/WS) :9000 (TCP)
#   frontend   React dashboard (vite dev server)                    :5173
#   fleet      five client PCs on a Docker "lab LAN" (testbed/compose.yml):
#              lab-a-pc-1..4 scenario-driven mocks, lab-a-pc-5 the real agent
#
# Usage: testbed/testbed.sh <command> [options]
#
#   up [--no-fleet]      install deps if needed, start everything, wait for health
#   prepare              start Docker, pull images, build the agent image (no
#                        services started; used by the SessionStart hook)
#   down [--wipe]        stop everything; --wipe also deletes the database volume
#                        so the next `up` re-seeds from docker/init.sql
#   restart [--wipe]     down + up
#   status               health of every component + the fleet table
#   logs <name> [-f]     backend | frontend | db | dockerd | lab-a-pc-N
#   test [pytest args]   run the automated E2E suite (testbed/tests)
#
# Mock PCs are driven with testbed/pcctl (e.g. `testbed/pcctl 3 sleep`).
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TB="$ROOT/testbed"
RUN="$TB/.run"
PY="$ROOT/backend/.venv/bin/python"

BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:5173"
TCP_PORT=9000
AGENT_IMAGE="labsense-agent:testbed"

DB_COMPOSE=(docker compose -f "$ROOT/docker-compose.yml")
FLEET_COMPOSE=(docker compose -f "$TB/compose.yml")

log()  { printf '\033[0;36m[testbed]\033[0m %s\n' "$*"; }
ok()   { printf '\033[0;32m[testbed]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[testbed]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m[testbed] %s\033[0m\n' "$*" >&2; exit 1; }

mkdir -p "$RUN"

# wait_for <description> <timeout-seconds> <command...>
wait_for() {
    local what=$1 timeout=$2 i
    shift 2
    for ((i = 0; i < timeout; i++)); do
        if "$@" >/dev/null 2>&1; then return 0; fi
        sleep 1
    done
    return 1
}

# --- Docker --------------------------------------------------------------------

docker_up() { docker info >/dev/null 2>&1; }

ensure_docker() {
    docker_up && return 0
    command -v dockerd >/dev/null 2>&1 \
        || die "Docker is not running and dockerd is not installed. Start Docker Desktop / the docker service."
    [ "$(id -u)" -eq 0 ] \
        || die "Docker is not running. Start it (e.g. sudo systemctl start docker) and retry."
    # Cloud sandboxes have no systemd, so nothing starts dockerd for us.
    log "Starting Docker daemon"
    setsid nohup dockerd >"$RUN/dockerd.log" 2>&1 </dev/null &
    wait_for "Docker daemon" 30 docker_up \
        || die "Docker daemon failed to start — see $RUN/dockerd.log"
}

# --- Database ------------------------------------------------------------------

# Queried over TCP inside the container on purpose: during first-run init the
# entrypoint's temporary server listens on the Unix socket only, so a socket
# check can pass before init.sql has finished and the real server is up.
db_ready() {
    docker exec -e PGPASSWORD=labsense_dev labsense-db \
        psql -h 127.0.0.1 -U labsense -d labsense -tAc "SELECT count(*) FROM pcs" >/dev/null 2>&1
}

start_db() {
    log "Starting PostgreSQL (docker-compose.yml → labsense-db)"
    "${DB_COMPOSE[@]}" up -d labsense-db
    wait_for "PostgreSQL" 90 db_ready || die "PostgreSQL not ready — try: $0 logs db"
    ok "PostgreSQL ready on :5432"
}

# --- Host processes (backend, frontend) ------------------------------------------

proc_alive() { [ -f "$RUN/$1.pid" ] && kill -0 "$(cat "$RUN/$1.pid")" 2>/dev/null; }

# start_proc <name> <workdir> <command...>
# Runs in its own session so stop_proc can take down the whole process group
# (uvicorn's reloader + worker, npm + vite). Only the command itself is
# backgrounded — backgrounding `cd && cmd` would leave a wrapper subshell
# holding our stdout open and put the wrapper's pid, not the service's, in
# the pid file.
start_proc() {
    local name=$1 dir=$2
    shift 2
    (
        cd "$dir" || exit 1
        setsid nohup "$@" >"$RUN/$name.log" 2>&1 </dev/null &
        echo $! >"$RUN/$name.pid"
    )
}

stop_proc() {
    local name=$1 pid i
    proc_alive "$name" || { rm -f "$RUN/$name.pid"; return 0; }
    pid=$(cat "$RUN/$name.pid")
    log "Stopping $name (pid $pid)"
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for ((i = 0; i < 10; i++)); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
    done
    kill -KILL -- "-$pid" 2>/dev/null || true
    rm -f "$RUN/$name.pid"
}

# wait_proc <name> <timeout> <check-command...> — also fails fast if it dies.
wait_proc() {
    local name=$1 timeout=$2 i
    shift 2
    for ((i = 0; i < timeout; i++)); do
        if "$@" >/dev/null 2>&1; then return 0; fi
        if ! proc_alive "$name"; then
            warn "$name exited during startup. Last log lines:"
            tail -n 25 "$RUN/$name.log" >&2 || true
            return 1
        fi
        sleep 1
    done
    warn "$name not ready after ${timeout}s. Last log lines:"
    tail -n 25 "$RUN/$name.log" >&2 || true
    return 1
}

backend_healthy() { curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1 && nc -z localhost "$TCP_PORT" 2>/dev/null; }
frontend_healthy() { curl -fsS -o /dev/null "$FRONTEND_URL" 2>/dev/null; }

start_backend() {
    if backend_healthy; then ok "Backend already running on :8000 / :$TCP_PORT"; return; fi
    log "Starting backend (uvicorn :8000, TCP heartbeat server :$TCP_PORT)"
    # --reload so backend edits take effect without re-running `up`; limited
    # to app/ so the venv isn't watched.
    start_proc backend "$ROOT/backend" \
        .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
    wait_proc backend 60 backend_healthy || die "Backend failed to start — full log: $RUN/backend.log"
    ok "Backend ready: $BACKEND_URL (docs at /docs), TCP :$TCP_PORT"
}

start_frontend() {
    if frontend_healthy; then ok "Frontend already running on :5173"; return; fi
    log "Starting frontend (vite :5173)"
    start_proc frontend "$ROOT/frontend" npm run dev -- --host 0.0.0.0 --port 5173 --strictPort
    wait_proc frontend 60 frontend_healthy || die "Frontend failed to start — full log: $RUN/frontend.log"
    ok "Frontend ready: $FRONTEND_URL"
}

# --- Client fleet ----------------------------------------------------------------

build_agent_image() {
    # No provenance attestation: it stamps every build uniquely, so an
    # unchanged agent would still get a new image ID and compose would
    # needlessly restart lab-a-pc-5 on every `up`.
    local args=(build -q --provenance=false -t "$AGENT_IMAGE")
    local proxy="${HTTPS_PROXY:-${https_proxy:-}}"
    local ca="${PIP_CERT:-${REQUESTS_CA_BUNDLE:-${SSL_CERT_FILE:-}}}"
    if [ -n "$proxy" ]; then
        # A proxy on loopback (as in the cloud sandbox) is only reachable
        # from the host's network namespace.
        args+=(--network host --build-arg "HTTPS_PROXY=$proxy"
               --build-arg "NO_PROXY=${NO_PROXY:-${no_proxy:-}}")
    fi
    if [ -n "$ca" ] && [ -f "$ca" ]; then
        args+=(--secret "id=pip_ca,src=$ca")
    fi
    # Always rebuilt: layer caching makes an unchanged agent a ~2s no-op, and
    # it guarantees lab-a-pc-5 runs the agent code in this checkout.
    log "Building real-agent image ($AGENT_IMAGE)"
    docker "${args[@]}" "$ROOT/agent" >/dev/null
}

start_fleet() {
    build_agent_image
    log "Starting client fleet (testbed/compose.yml)"
    "${FLEET_COMPOSE[@]}" up -d --no-build --remove-orphans
    log "Waiting for every fleet PC to reach the backend"
    "$PY" "$TB/pcctl" wait --timeout 60 || die "Fleet not reporting — try: $TB/pcctl status"
    ok "Fleet reporting: lab-a-pc-1..4 (mock), lab-a-pc-5 (real agent)"
}

# --- Commands --------------------------------------------------------------------

cmd_prepare() {
    ensure_docker
    log "Pulling images"
    "${DB_COMPOSE[@]}" pull -q labsense-db
    "${FLEET_COMPOSE[@]}" pull -q --ignore-buildable
    build_agent_image
    ok "Images ready — testbed/testbed.sh up will not need to download anything"
}

cmd_up() {
    local fleet=1
    for arg in "$@"; do
        case $arg in
            --no-fleet) fleet=0 ;;
            *) die "unknown option for up: $arg" ;;
        esac
    done
    "$TB/bootstrap.sh"
    ensure_docker
    start_db
    start_backend
    start_frontend
    if [ "$fleet" -eq 1 ]; then start_fleet; fi
    echo
    ok "LabSense testbed is up."
    cat <<EOF

  Dashboard   $FRONTEND_URL      admin@labsense.dev / prof@labsense.dev / student@labsense.dev
                                          (password: password123)
  API         $BACKEND_URL/docs
  Heartbeats  tcp://localhost:$TCP_PORT

  Fleet       $TB/pcctl status
  Drive a PC  $TB/pcctl 3 sleep    (scenario <name> | sleep | wake | power-off | hang | unplug | ...)
  E2E suite   $TB/testbed.sh test
EOF
}

cmd_down() {
    local wipe=0
    for arg in "$@"; do
        case $arg in
            --wipe) wipe=1 ;;
            *) die "unknown option for down: $arg" ;;
        esac
    done
    if docker_up; then
        log "Stopping client fleet"
        "${FLEET_COMPOSE[@]}" down --remove-orphans >/dev/null 2>&1 || true
    fi
    stop_proc frontend
    stop_proc backend
    if docker_up; then
        if [ "$wipe" -eq 1 ]; then
            log "Stopping database and deleting its volume (next up re-seeds)"
            "${DB_COMPOSE[@]}" down -v
        else
            log "Stopping database (data kept; use --wipe to re-seed)"
            "${DB_COMPOSE[@]}" down
        fi
    fi
    ok "Testbed stopped"
}

row() { printf '  %-10s %-6s %s\n' "$1" "$2" "$3"; }

cmd_status() {
    local up='\033[0;32mup\033[0m' down='\033[0;31mdown\033[0m'
    echo "Components:"
    if docker_up; then
        row docker "$(printf "$up")" ""
        if db_ready; then row database "$(printf "$up")" "labsense-db :5432"; else row database "$(printf "$down")" ""; fi
    else
        row docker "$(printf "$down")" "run: $0 up"
        row database "$(printf "$down")" ""
    fi
    if backend_healthy; then row backend "$(printf "$up")" "$BACKEND_URL, TCP :$TCP_PORT"; else row backend "$(printf "$down")" ""; fi
    if frontend_healthy; then row frontend "$(printf "$up")" "$FRONTEND_URL"; else row frontend "$(printf "$down")" ""; fi
    echo
    "$PY" "$TB/pcctl" status || true
}

cmd_logs() {
    local name=${1:-} follow=()
    [ -n "$name" ] || die "usage: $0 logs <backend|frontend|db|dockerd|lab-a-pc-N> [-f]"
    [ "${2:-}" = "-f" ] && follow=(-f)
    case $name in
        backend|frontend|dockerd) tail -n 200 "${follow[@]}" "$RUN/$name.log" ;;
        db|database) docker logs --tail 200 "${follow[@]}" labsense-db ;;
        lab-a-pc-*) docker logs --tail 200 "${follow[@]}" "$name" ;;
        [1-5]|pc-[1-5]) docker logs --tail 200 "${follow[@]}" "lab-a-pc-${name#pc-}" ;;
        *) die "unknown log source: $name" ;;
    esac
}

cmd_test() {
    backend_healthy || die "Backend is not running — run: $0 up"
    "$PY" -m pytest "$TB/tests" "$@"
}

case ${1:-} in
    up)      shift; cmd_up "$@" ;;
    prepare) cmd_prepare ;;
    down)    shift; cmd_down "$@" ;;
    restart) shift; cmd_down "$@"; cmd_up ;;
    status)  cmd_status ;;
    logs)    shift; cmd_logs "$@" ;;
    test)    shift; cmd_test "$@" ;;
    *)       awk 'NR > 2 && /^# =+$/ { exit } NR > 2 { sub(/^# ?/, ""); print }' "$0"; exit 1 ;;
esac
