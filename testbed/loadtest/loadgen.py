"""LabSense scale test: many simulated lab PCs and live dashboards against one server.

Point it at any LabSense server - the testbed (`testbed/testbed.sh scale` does
that with a laptop-sized server), or the real Windows server from a Linux
machine on the lab Wi-Fi. Needs Python 3.10+ and `pip install websockets`
(plus psutil for --monitor-pid). Speaks the real agent wire protocol
(labsense_agent.protocol).

For each step (e.g. 250, 500, 1000 PCs) it:
  1. registers the PCs through the admin API, in labs lt01, lt02, ... of
     --lab-size PCs each (deleted again at the end unless --keep-labs);
  2. connects that many simulated agents, each on its own TCP connection like
     a real lab PC: a SOFTWARE_REPORT (--packages names) when it boots and
     every --software-interval after that, and a HEARTBEAT every 5 s from a
     random phase. A mix of PCs in use, idle and logged out, some changing
     over time (--churn-minutes);
  3. keeps --dashboards WebSocket dashboards open; --measured of them time
     every heartbeat from the moment it was sent to the moment it arrived;
  4. probes the REST API the way people browsing the dashboard do;
  5. reports latency percentiles, false offline flips (an in-use PC marked
     Available because its heartbeats were not processed within the 15 s grace
     period), REST latency, server CPU/memory, and errors - and whether the step
     met the SLOs.

Optional: --storm drops every PC's connection at once after the last step and
reconnects them all (an access point rebooting, power returning to a lab);
--stalled-dashboards adds dashboards that stay connected but stop reading (a
frozen tab); --dead-dashboards adds dashboards that go silent mid-run without
closing, like a laptop that went to sleep with the page open (testbed only).

Example (testbed): testbed/testbed.sh scale --steps 250,500,1000
Example (real lab): python loadgen.py --server 10.234.237.199 --steps 100,250
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import shutil
import signal
import socket
import statistics
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'agent'))
sys.path.insert(0, str(HERE))
from labsense_agent.protocol import encode_message  # noqa: E402

import websockets  # noqa: E402

HEARTBEAT_INTERVAL = 5.0
GRACE_SECONDS = 15.0
LAB_PREFIX = 'lt'
SCENARIO_MIX = (('in-use', 0.5), ('idle', 0.3), ('logged-out', 0.2))


# ---------------------------------------------------------------------------
# Shared measurements
# ---------------------------------------------------------------------------

class Metrics:
    def __init__(self):
        self.reset()

    def reset(self):
        self.started = time.monotonic()
        self.latencies: list[float] = []
        self.rest: dict[str, list[float]] = {}
        self.rest_errors = 0
        self.false_flips = 0
        self.flipped_pcs: set[str] = set()
        # In-use PCs the REST API reported as Available. The dashboards can't
        # see a flip while broadcasts are stuck; the REST API still can.
        self.rest_wrong: set[str] = set()
        self.sent = 0
        self.send_errors = 0
        self.connect_errors = 0
        self.rejected = 0
        self.ws_messages = 0
        self.ws_errors = 0
        self.loop_lag: list[float] = []
        self.stalled_closed_after: list[float] = []


M = Metrics()
SENT_AT: dict[tuple[str, int], float] = {}   # (pc_id, idle_seconds tag) -> send time


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


# ---------------------------------------------------------------------------
# REST helper (stdlib; run in a thread so it never blocks the event loop)
# ---------------------------------------------------------------------------

class Api:
    def __init__(self, base: str):
        self.base = base.rstrip('/')
        self.token: str | None = None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(self, method: str, path: str, body=None, token: str | None = None, timeout=30):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header('Content-Type', 'application/json')
        tok = token or self.token
        if tok:
            req.add_header('Authorization', f'Bearer {tok}')
        with self.opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None

    def login(self, email: str, password: str) -> str:
        return self.call('POST', '/auth/login', {'email': email, 'password': password})['access_token']


def ensure_pcs(api: Api, n: int, lab_size: int) -> list[str]:
    """Return at least n registered pc_ids in load-test labs, creating what is missing."""
    labs = sorted(l['lab_id'] for l in api.call('GET', '/labs') if l['lab_id'].startswith(LAB_PREFIX))
    by_lab = {lab: sorted(p['pc_id'] for p in api.call('GET', f'/labs/{lab}/pcs')) for lab in labs}
    total = sum(len(v) for v in by_lab.values())
    i = 1
    while total < n:
        lab = f'{LAB_PREFIX}{i:02d}'
        if lab not in by_lab:
            api.call('POST', '/admin/labs', {'lab_id': lab, 'lab_name': f'Load Test Lab {i:02d}',
                                             'operating_start_time': '00:00:00',
                                             'operating_end_time': '23:59:59'})
            by_lab[lab] = []
        while len(by_lab[lab]) < lab_size and total < n:
            by_lab[lab].append(api.call('POST', '/admin/pcs', {'lab_id': lab})['pc_id'])
            total += 1
        i += 1
    pcs = [pc for lab in sorted(by_lab) for pc in by_lab[lab]]
    return pcs[:max(n, 0)] if n else pcs


def delete_load_labs(api: Api) -> int:
    labs = [l['lab_id'] for l in api.call('GET', '/labs') if l['lab_id'].startswith(LAB_PREFIX)]
    for lab in labs:
        api.call('DELETE', f'/admin/labs/{lab}')
    return len(labs)


# ---------------------------------------------------------------------------
# Simulated PCs
# ---------------------------------------------------------------------------

class SimPC:
    """One lab PC: a TCP connection, a software report, a heartbeat every 5 s.

    idle_seconds doubles as a sequence tag so a dashboard can match each
    broadcast to the heartbeat that caused it - chosen inside each scenario's
    range so the server's state rules see exactly what a real PC would send.
    """

    def __init__(self, pc_id: str, scenario: str, cfg, software_json: bytes, rng: random.Random):
        self.pc_id = pc_id
        self.scenario = scenario
        self.scenario_since = time.monotonic()
        self.cfg = cfg
        self.rng = rng
        self.software_json = software_json
        self.seq = 0
        self.writer: asyncio.StreamWriter | None = None
        self.connected_since = 0.0
        self.last_echo = 0.0
        self.reconnect_now = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.next_software: float | None = None  # None until the PC has booted

    # The server only ever marks an in-use PC Available through the staleness
    # timer, so seeing that (outside a deliberate scenario change) means its
    # heartbeats were not processed in time.
    def should_be_in_use(self, now: float) -> bool:
        if self.writer is None:  # not connected yet, or between reconnects
            return False
        settled = now - max(self.scenario_since, self.connected_since) > HEARTBEAT_INTERVAL + 1
        return self.scenario == 'in-use' and settled

    def telemetry(self) -> dict:
        self.seq += 1
        if self.scenario == 'in-use':
            return dict(session_active=True, screen_locked=False,
                        idle_seconds=self.seq % 250, cpu_percent=round(self.rng.uniform(8, 40), 1))
        if self.scenario == 'idle':
            return dict(session_active=True, screen_locked=False,
                        idle_seconds=600 + self.seq % 1000, cpu_percent=round(self.rng.uniform(0.5, 3), 1))
        return dict(session_active=False, screen_locked=False,
                    idle_seconds=2000 + self.seq % 1000, cpu_percent=round(self.rng.uniform(0.2, 2), 1))

    def maybe_churn(self) -> None:
        if self.scenario == 'logged-out' or not self.cfg.churn_minutes:
            return
        if self.rng.random() < HEARTBEAT_INTERVAL / (self.cfg.churn_minutes * 60):
            self.scenario = 'idle' if self.scenario == 'in-use' else 'in-use'
            self.scenario_since = time.monotonic()

    def software_frame(self) -> bytes:
        payload = (b'{"type": "SOFTWARE_REPORT", "pc_id": ' + json.dumps(self.pc_id).encode()
                   + b', "packages": ' + self.software_json + b', "timestamp": '
                   + json.dumps(datetime.now(timezone.utc).isoformat()).encode() + b'}')
        return struct.pack('!I', len(payload)) + payload

    async def _reader(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                header = await reader.readexactly(4)
                body = await reader.readexactly(struct.unpack('!I', header)[0])
                if json.loads(body).get('type') == 'REJECTED':
                    M.rejected += 1
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass

    def drop(self) -> None:
        """Lose the link abruptly (no FIN), then reconnect at once."""
        if self.writer is not None:
            self.writer.transport.abort()
        self.reconnect_now.set()

    async def run(self, start_delay: float, stop: asyncio.Event) -> None:
        await asyncio.sleep(start_delay)
        backoff = 5.0
        while not stop.is_set():
            try:
                reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.cfg.server, self.cfg.tcp_port), timeout=10)
            except (OSError, asyncio.TimeoutError):
                M.connect_errors += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)  # same back-off as the real agent
                continue
            backoff = 5.0
            self.connected_since = time.monotonic()
            self.reconnect_now.clear()
            read_task = asyncio.create_task(self._reader(reader))
            try:
                # Like the agent: one SOFTWARE_REPORT when it starts (the PC
                # boots), then one every --software-interval on its own timer,
                # skipped while disconnected - never extra ones on reconnect.
                # Across a fleet the timers are out of phase (PCs boot and
                # reboot all day), so later reports get a random phase.
                interval = self.cfg.software_interval
                if self.next_software is None:
                    if self.cfg.packages:
                        self.writer.write(self.software_frame())
                    self.next_software = time.monotonic() + self.rng.uniform(0, interval)
                while not stop.is_set():
                    now = time.monotonic()
                    if self.cfg.packages and interval > 0 and now >= self.next_software:
                        self.writer.write(self.software_frame())
                        while self.next_software <= now:
                            self.next_software += interval
                    self.maybe_churn()
                    tele = self.telemetry()
                    msg = {'type': 'HEARTBEAT', 'pc_id': self.pc_id, **tele,
                           'timestamp': datetime.now(timezone.utc).isoformat()}
                    SENT_AT[(self.pc_id, tele['idle_seconds'])] = time.monotonic()
                    self.writer.write(encode_message(msg))
                    await self.writer.drain()
                    M.sent += 1
                    try:  # the real agent sleeps a fixed interval after each send
                        await asyncio.wait_for(self.reconnect_now.wait(), HEARTBEAT_INTERVAL)
                        break  # dropped on purpose: reconnect immediately
                    except asyncio.TimeoutError:
                        pass
            except (ConnectionError, OSError):
                M.send_errors += 1
            finally:
                read_task.cancel()
                if self.writer is not None:
                    self.writer.transport.abort()
                self.writer = None


# ---------------------------------------------------------------------------
# Dashboards, probes, monitors
# ---------------------------------------------------------------------------

TCP_CLOSE, TCP_CLOSE_WAIT = 7, 8  # Linux tcpi_state values


def tcp_state(sock) -> int | None:
    """Kernel TCP state of a socket (Linux only; None elsewhere)."""
    try:
        return sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 1)[0]
    except (AttributeError, OSError):
        return None


async def dashboard(cfg, token: str, measured: bool, counts_flips: bool, stalled: bool,
                    pcs: dict[str, SimPC], stop: asyncio.Event) -> None:
    url = f'ws://{cfg.server}:{cfg.api_port}/ws?token={token}'
    while not stop.is_set():
        try:
            # proxy=None: dashboard traffic is LAN traffic. (websockets otherwise
            # honours HTTPS_PROXY, and urllib's no_proxy check ignores CIDR ranges.)
            async with websockets.connect(url, max_queue=1 if stalled else 4096,
                                          open_timeout=20, ping_interval=None,
                                          max_size=None, proxy=None) as ws:
                if stalled:
                    # Never read, so the server's sends back up. Note whether
                    # (and when) the server gives up on us. A client that has
                    # stopped reading never sees the close frame or the FIN, so
                    # ask the kernel: CLOSE_WAIT means the server hung up.
                    opened = time.monotonic()
                    sock = ws.transport.get_extra_info('socket')
                    while not stop.is_set():
                        if tcp_state(sock) in (TCP_CLOSE, TCP_CLOSE_WAIT):
                            M.stalled_closed_after.append(round(time.monotonic() - opened, 1))
                            break
                        try:
                            await asyncio.wait_for(stop.wait(), 1)
                        except asyncio.TimeoutError:
                            pass
                    return
                async for raw in ws:
                    M.ws_messages += 1
                    if not measured:
                        continue
                    now = time.monotonic()
                    msg = json.loads(raw)
                    if msg.get('type') != 'pc_update':
                        continue
                    pc = pcs.get(msg.get('pc_id'))
                    if pc is None:
                        continue
                    if 'cpu_percent' in msg:  # per-heartbeat telemetry broadcast
                        sent = SENT_AT.get((pc.pc_id, msg.get('idle_seconds')))
                        if sent is not None:
                            M.latencies.append(now - sent)
                            pc.last_echo = now
                    elif counts_flips and msg.get('state') == 'AVAILABLE' and pc.should_be_in_use(now):
                        M.false_flips += 1
                        M.flipped_pcs.add(pc.pc_id)
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as exc:
            M.ws_errors += 1
            if M.ws_errors <= 3:
                print(f'  dashboard connection failed: {exc!r}; retrying', flush=True)
            await asyncio.sleep(2)


NFT_TABLE = 'labsense_loadtest'


def blackhole_ports(ports: list[int], server_port: int) -> None:
    """Drop everything these local client ports send to the server (testbed only:
    Linux, root, nftables). To the server the dashboards look like laptops that
    went to sleep: no reads, no ACKs, no FIN - the connection just goes silent."""
    rules = ', '.join(str(p) for p in ports)
    cmds = [['nft', 'add', 'table', 'inet', NFT_TABLE],
            ['nft', 'add', 'chain', 'inet', NFT_TABLE, 'input',
             '{ type filter hook input priority -10 ; policy accept ; }'],
            ['nft', 'add', 'rule', 'inet', NFT_TABLE, 'input',
             'tcp', 'sport', '{', rules, '}', 'tcp', 'dport', str(server_port), 'drop']]
    for cmd in cmds:
        subprocess.run(cmd, check=True, capture_output=True, text=True)


def remove_blackhole() -> None:
    subprocess.run(['nft', 'delete', 'table', 'inet', NFT_TABLE], capture_output=True)


async def dead_dashboard(cfg, token: str, ports: list[int], stop: asyncio.Event) -> None:
    url = f'ws://{cfg.server}:{cfg.api_port}/ws?token={token}'
    # Advertise an Ethernet/Wi-Fi sized segment (MSS). Over loopback the MSS is
    # ~32 KB and Linux sizes the server's send buffer from it, hiding the
    # backpressure a real laptop on Wi-Fi (MSS ~1460) would cause within seconds.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG, 1448)
    except (AttributeError, OSError):
        pass
    sock.setblocking(False)
    await asyncio.get_running_loop().sock_connect(sock, (cfg.server, cfg.api_port))
    async with websockets.connect(url, sock=sock, max_queue=1, open_timeout=20,
                                  ping_interval=None, max_size=None, proxy=None) as ws:
        ports.append(ws.local_address[1])
        await stop.wait()


async def rest_probes(cfg, api: Api, lab: str, pcs: dict, stop: asyncio.Event) -> None:
    async def timed(name, path, token=None):
        t = time.perf_counter()
        try:
            out = await asyncio.to_thread(api.call, 'GET', path, None, token, 30)
            M.rest.setdefault(name, []).append(time.perf_counter() - t)
            return out
        except (urllib.error.URLError, OSError, ValueError):
            M.rest_errors += 1
            return None

    async def searches():  # someone looking for software, every 10 s
        while not stop.is_set():
            await timed('software_search', f'/software/search?q=labsoft-{lab}')
            await asyncio.sleep(10)

    search_task = asyncio.create_task(searches()) if cfg.packages else None
    tick = 0
    try:
        while not stop.is_set():
            await timed('health', '/health')
            rows = await timed('lab_pcs', f'/labs/{lab}/pcs')
            now = time.monotonic()
            for row in rows or ():
                pc = pcs.get(row.get('pc_id'))
                if pc is not None and row.get('current_state') == 'AVAILABLE' and pc.should_be_in_use(now):
                    M.rest_wrong.add(pc.pc_id)
            if tick % 5 == 0:
                await timed('labs', '/labs')
            tick += 1
            await asyncio.sleep(2)
    finally:
        if search_task is not None:
            search_task.cancel()


async def housekeeping(stop: asyncio.Event) -> None:
    """Measure the load generator's own event-loop lag and expire send records."""
    loop = asyncio.get_running_loop()
    while not stop.is_set():
        t = loop.time()
        await asyncio.sleep(0.25)
        M.loop_lag.append(loop.time() - t - 0.25)
        if len(SENT_AT) > 200_000 or int(t) % 10 == 0:
            cutoff = time.monotonic() - 60
            for k in [k for k, v in SENT_AT.items() if v < cutoff]:
                SENT_AT.pop(k, None)


class Monitors:
    """Server CPU/RSS (local pid) and DB container stats, sampled in threads."""

    def __init__(self, pid: int | None, db_container: str | None):
        self.sampler = None
        if pid:
            from server_monitor import ProcessSampler
            self.sampler = ProcessSampler(pid)
        self.db_container = db_container
        self.db: list[tuple[float, float]] = []  # (cpu %, mem MB)
        self._stop = threading.Event()
        self._threads = []

    def start(self) -> None:
        if self.sampler:
            self._threads.append(threading.Thread(target=self._proc_loop, daemon=True))
        if self.db_container:
            self._threads.append(threading.Thread(target=self._db_loop, daemon=True))
        for t in self._threads:
            t.start()

    def _proc_loop(self):
        while not self._stop.wait(1.0):
            try:
                self.sampler.sample()
            except Exception:
                pass

    def _db_loop(self):
        while not self._stop.wait(4.0):
            try:
                out = subprocess.run(
                    ['docker', 'stats', '--no-stream', '--format', '{{.CPUPerc}};{{.MemUsage}}',
                     self.db_container], capture_output=True, text=True, timeout=10).stdout.strip()
                cpu, mem = out.split(';')
                used = mem.split('/')[0].strip()
                mb = float(used[:-3]) * (1024 if used.endswith('GiB') else 1) if used[-3:] in ('MiB', 'GiB') else 0
                self.db.append((float(cpu.rstrip('%')), mb))
            except Exception:
                pass

    def reset(self):
        if self.sampler:
            self.sampler.reset()
        self.db.clear()

    def summary(self) -> dict:
        out = {}
        if self.sampler:
            out['server'] = self.sampler.summary()
        if self.db:
            cpus = [c for c, _ in self.db]
            out['db'] = {'cpu_avg_pct': round(statistics.fmean(cpus), 1),
                         'cpu_max_pct': round(max(cpus), 1),
                         'mem_max_mb': round(max(m for _, m in self.db), 1)}
        return out

    def stop(self):
        self._stop.set()


def start_profiler(cfg, out_dir: Path, n: int):
    """py-spy flame graph of the server during this step's measurement window."""
    if not (cfg.profile and cfg.monitor_pid):
        return None
    exe = shutil.which('py-spy') or str(Path(sys.executable).with_name('py-spy'))
    out_dir.mkdir(parents=True, exist_ok=True)
    # --nonblocking: sample without pausing the server, so profiling does not
    # distort the latencies being measured.
    return subprocess.Popen(
        [exe, 'record', '--pid', str(cfg.monitor_pid), '--duration', str(cfg.step_seconds),
         '--rate', '50', '--nonblocking', '--output', str(out_dir / f'flame-{n}pcs.svg')],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------------------
# Step evaluation
# ---------------------------------------------------------------------------

def step_result(n: int, seconds: float, cfg, monitors: Monitors) -> dict:
    lat = M.latencies
    expected = M.sent * cfg.measured
    res = {
        'pcs': n,
        'heartbeats_per_s': round(M.sent / seconds, 1),
        'dashboard_msgs_per_s': round(M.ws_messages / seconds, 1),
        'latency_ms': {k: (round(v * 1000, 1) if v is not None else None) for k, v in
                       (('p50', pct(lat, .50)), ('p95', pct(lat, .95)),
                        ('p99', pct(lat, .99)), ('max', max(lat) if lat else None))},
        'delivered_ratio': round(len(lat) / expected, 3) if expected else None,
        'false_offline_flips': M.false_flips,
        'pcs_flipped': len(M.flipped_pcs),
        'in_use_pcs_shown_available_by_rest': len(M.rest_wrong),
        'rest_p95_ms': {k: round(pct(v, .95) * 1000, 1) for k, v in M.rest.items() if v},
        'rest_errors': M.rest_errors,
        'connect_errors': M.connect_errors,
        'send_errors': M.send_errors,
        'rejected': M.rejected,
        'dashboard_errors': M.ws_errors,
        'stalled_dashboards_closed_by_server_after_s': M.stalled_closed_after,
        'loadgen_loop_lag_p95_ms': round((pct(M.loop_lag, .95) or 0) * 1000, 1),
        **monitors.summary(),
    }
    fails = []
    p95, p99 = res['latency_ms']['p95'], res['latency_ms']['p99']
    if p95 is None or p95 > cfg.slo_p95_ms:
        fails.append(f'p95 latency {p95} ms > {cfg.slo_p95_ms}')
    if p99 is not None and p99 > cfg.slo_p99_ms:
        fails.append(f'p99 latency {p99} ms > {cfg.slo_p99_ms}')
    if res['delivered_ratio'] is not None and res['delivered_ratio'] < 0.97:
        fails.append(f'only {res["delivered_ratio"]:.0%} of heartbeats reached dashboards')
    if M.false_flips:
        fails.append(f'{M.false_flips} false offline flips')
    if M.rest_wrong:
        fails.append(f'{len(M.rest_wrong)} in-use PCs shown as Available by the REST API')
    for name, v in res['rest_p95_ms'].items():
        if v > cfg.slo_rest_ms:
            fails.append(f'REST {name} p95 {v} ms > {cfg.slo_rest_ms}')
    if M.rejected:
        fails.append(f'{M.rejected} heartbeats rejected')
    cpu = res.get('server', {}).get('cpu_avg_pct')
    if cpu is not None and cpu > cfg.slo_cpu_pct:
        fails.append(f'server CPU {cpu}% > {cfg.slo_cpu_pct}% of one core')
    res['slo_failures'] = fails
    res['passed'] = not fails
    if res['loadgen_loop_lag_p95_ms'] > 100:
        res['warning'] = 'load generator itself was overloaded; latencies are pessimistic'
    return res


def print_row(r: dict) -> None:
    lat = r['latency_ms']
    srv = r.get('server', {})
    print(f"  {r['pcs']:>6} PCs  {r['heartbeats_per_s']:>7.1f} hb/s  "
          f"lat p50/p95/p99 {lat['p50']}/{lat['p95']}/{lat['p99']} ms  "
          f"flips {r['false_offline_flips']}/{r['in_use_pcs_shown_available_by_rest']}  cpu {srv.get('cpu_avg_pct', '-')}%  "
          f"rss {srv.get('rss_max_mb', '-')} MB  -> {'PASS' if r['passed'] else 'FAIL'}"
          + (f"  ({'; '.join(r['slo_failures'])})" if r['slo_failures'] else ''), flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def software_list(count: int) -> bytes:
    """A plausible dpkg + pip inventory of `count` package names."""
    rng = random.Random(7)
    stems = ['lib', 'python3-', 'gir1.2-', 'fonts-', 'gnome-', 'x11-', 'node-', 'texlive-']
    names = {f'{rng.choice(stems)}{rng.choice("abcdefghijklmnopqrstuvwxyz")}'
             f'{rng.randrange(10**6):x}{rng.choice(["", "-dev", "-common", "-data"])}'
             for _ in range(count * 2)}
    return json.dumps(sorted(names)[:count]).encode()


def environment(cfg) -> dict:
    env = {'loadgen_python': platform.python_version(), 'loadgen_platform': platform.platform(),
           'loadgen_cpus': os.cpu_count(), 'server': cfg.server}
    try:
        if sys.platform.startswith('linux'):
            for line in Path('/proc/cpuinfo').read_text().splitlines():
                if line.startswith('model name'):
                    env['loadgen_cpu'] = line.split(':', 1)[1].strip()
                    break
    except OSError:
        pass
    return env


async def run(cfg, out_dir: Path) -> dict:
    api = Api(f'http://{cfg.server}:{cfg.api_port}')
    api.token = await asyncio.to_thread(api.login, cfg.admin_email, cfg.password)
    student_token = await asyncio.to_thread(api.login, cfg.student_email, cfg.password)

    steps = sorted(cfg.steps)
    # Start from a clean slate, so the database holds exactly this run's PCs
    # (software search time, for one, grows with every stored inventory).
    removed = await asyncio.to_thread(delete_load_labs, api)
    if removed:
        print(f'Removed {removed} load-test labs left by an earlier run', flush=True)
    print(f'Registering {steps[-1]} PCs in labs of {cfg.lab_size} ...', flush=True)
    t = time.perf_counter()
    pc_ids = await asyncio.to_thread(ensure_pcs, api, steps[-1], cfg.lab_size)
    print(f'  {len(pc_ids)} PCs ready in {time.perf_counter() - t:.1f}s', flush=True)

    rng = random.Random(cfg.seed)
    # Every PC in a lab shares the lab's image: the common inventory plus one
    # package only that lab has, which the REST probe searches for ("which lab
    # has MATLAB?") - a full search that returns one lab's PCs.
    base = software_list(cfg.packages) if cfg.packages else b''
    lab_software: dict[str, bytes] = {}

    def software_for(pc_id: str) -> bytes:
        lab = pc_id[:-2]  # the server numbers PCs <lab_id><NN>
        if lab not in lab_software:
            lab_software[lab] = (b'[' + json.dumps(f'labsoft-{lab}').encode() + b', ' + base[1:]
                                 if base else b'[]')
        return lab_software[lab]

    pcs: dict[str, SimPC] = {}
    order: list[SimPC] = []
    for pc_id in pc_ids:
        r = rng.random()
        acc = 0.0
        for scenario, share in SCENARIO_MIX:
            acc += share
            if r <= acc:
                break
        pc = SimPC(pc_id, scenario, cfg, software_for(pc_id), random.Random(rng.random()))
        pcs[pc_id] = pc
        order.append(pc)

    stop = asyncio.Event()
    monitors = Monitors(cfg.monitor_pid, cfg.db_container)
    monitors.start()
    background = [asyncio.create_task(housekeeping(stop)),
                  asyncio.create_task(rest_probes(cfg, api, pc_ids[0][:len(LAB_PREFIX) + 2], pcs, stop))]
    for i in range(cfg.dashboards):
        background.append(asyncio.create_task(dashboard(
            cfg, student_token, measured=i < cfg.measured, counts_flips=i == 0,
            stalled=False, pcs=pcs, stop=stop)))
    for _ in range(cfg.stalled_dashboards):
        background.append(asyncio.create_task(dashboard(
            cfg, student_token, False, False, True, pcs, stop)))
    dead_ports: list[int] = []
    await asyncio.sleep(2)

    results = []
    running = 0
    try:
        for n in steps:
            new = order[running:n]
            ramp = max(cfg.ramp_seconds, len(new) / cfg.connect_rate)
            print(f'Step {n} PCs: connecting {len(new)} more over {ramp:.0f}s, '
                  f'settling {cfg.warmup_seconds}s, measuring {cfg.step_seconds}s', flush=True)
            for pc in new:
                pc.task = asyncio.create_task(pc.run(rng.uniform(0, ramp), stop))
            running = n
            await asyncio.sleep(ramp + cfg.warmup_seconds)
            # Every step, --dead-dashboards fresh dashboards open a few seconds
            # before they go silent: someone opens the page and shuts the lid.
            # That is the worst case - the server's kernel send buffer for a
            # young connection is still small (Linux grows it with traffic), so
            # its backlog reaches uvicorn's buffer limit soonest.
            fresh_dead: list[int] = []
            for _ in range(cfg.dead_dashboards):
                background.append(asyncio.create_task(
                    dead_dashboard(cfg, student_token, fresh_dead, stop)))
            for _ in range(100):
                if len(fresh_dead) >= cfg.dead_dashboards:
                    break
                await asyncio.sleep(0.2)
            if cfg.dead_dashboards:
                await asyncio.sleep(3)
            # What PCs and dashboards saw while the new PCs were connecting.
            ramp_report = {
                'connect_rate_per_s': round(len(new) / ramp, 1) if ramp else None,
                'false_offline_flips': M.false_flips,
                'in_use_pcs_shown_available_by_rest': len(M.rest_wrong),
                'latency_p99_ms': round((pct(M.latencies, .99) or 0) * 1000, 1),
                'latency_max_ms': round(max(M.latencies) * 1000, 1) if M.latencies else None,
                'connect_errors': M.connect_errors,
            }
            M.reset()
            monitors.reset()
            if fresh_dead:
                await asyncio.to_thread(blackhole_ports, fresh_dead, cfg.api_port)
                dead_ports += fresh_dead
                print(f'  {len(fresh_dead)} dashboard(s) just "went to sleep" (packets dropped)', flush=True)
            profiler = start_profiler(cfg, out_dir, n)
            await asyncio.sleep(cfg.step_seconds)
            r = step_result(n, cfg.step_seconds, cfg, monitors)
            r['while_connecting'] = ramp_report
            if ramp_report['false_offline_flips'] or ramp_report['in_use_pcs_shown_available_by_rest']:
                r['slo_failures'].append(
                    f"{ramp_report['false_offline_flips']} false offline flips "
                    f"({ramp_report['in_use_pcs_shown_available_by_rest']} PCs wrong in REST) while "
                    f"{len(new)} PCs connected at {ramp_report['connect_rate_per_s']}/s")
                r['passed'] = False
            if profiler is not None:
                await asyncio.to_thread(profiler.wait, 60)
                r['flame_graph'] = f'flame-{n}pcs.svg'
            results.append(r)
            print_row(r)
            if not r['passed'] and cfg.stop_on_fail:
                print('  stopping: SLOs not met', flush=True)
                break

        storm = None
        if cfg.storm and results:
            n = results[-1]['pcs']
            print(f'Reconnect storm: dropping all {n} connections at once ...', flush=True)
            M.reset()
            monitors.reset()
            t0 = time.monotonic()
            for pc in order[:n]:
                pc.last_echo = 0.0
                pc.drop()
            deadline = t0 + 120
            while time.monotonic() < deadline:
                await asyncio.sleep(0.5)
                if all(pc.last_echo > t0 for pc in order[:n]):
                    break
            recovered = [pc.last_echo - t0 for pc in order[:n] if pc.last_echo > t0]
            await asyncio.sleep(GRACE_SECONDS + 2)  # catch any staleness flips it caused
            storm = {
                'pcs': n,
                'recovered': len(recovered),
                'recovery_s_p50': round(pct(recovered, .5), 1) if recovered else None,
                'recovery_s_max': round(max(recovered), 1) if recovered else None,
                'false_offline_flips': M.false_flips,
                'in_use_pcs_shown_available_by_rest': len(M.rest_wrong),
                'connect_errors': M.connect_errors,
                **monitors.summary(),
            }
            storm['passed'] = (len(recovered) == n and not M.false_flips and not M.rest_wrong
                               and storm['recovery_s_max'] is not None
                               and storm['recovery_s_max'] < GRACE_SECONDS)
            print(f"  {storm['recovered']}/{n} PCs back, slowest after {storm['recovery_s_max']}s, "
                  f"{storm['false_offline_flips']}/{storm['in_use_pcs_shown_available_by_rest']} false flips "
                  f"(dashboard/REST) -> {'PASS' if storm['passed'] else 'FAIL'}",
                  flush=True)

        freeze = None
        if cfg.freeze_server and results and cfg.monitor_pid:
            # The server stops running for a while (a stall, a hung disk, a
            # saturated event loop) while the PCs keep sending. Their
            # heartbeats wait in socket buffers; none is late. Count the PCs
            # the server nevertheless declares offline when it resumes.
            n = results[-1]['pcs']
            print(f'Freezing the server for {cfg.freeze_server:g}s ...', flush=True)
            M.reset()
            monitors.reset()
            os.kill(cfg.monitor_pid, signal.SIGSTOP)
            try:
                await asyncio.sleep(cfg.freeze_server)
            finally:
                os.kill(cfg.monitor_pid, signal.SIGCONT)
            await asyncio.sleep(GRACE_SECONDS + 5)
            freeze = {
                'pcs': n,
                'seconds': cfg.freeze_server,
                'false_offline_flips': M.false_flips,
                'pcs_flipped': len(M.flipped_pcs),
                'in_use_pcs_shown_available_by_rest': len(M.rest_wrong),
                'latency_max_ms': round(max(M.latencies) * 1000, 1) if M.latencies else None,
            }
            freeze['passed'] = not M.false_flips and not M.rest_wrong
            print(f"  {freeze['pcs_flipped']} in-use PCs flipped to Available on resume "
                  f"({freeze['false_offline_flips']} flip messages) -> "
                  f"{'PASS' if freeze['passed'] else 'FAIL'}", flush=True)
        elif cfg.freeze_server:
            print('--freeze-server needs --monitor-pid (a server on this machine); skipped', flush=True)
    finally:
        if dead_ports:
            await asyncio.to_thread(remove_blackhole)
        stop.set()
        for pc in order[:running]:
            if pc.writer is not None:
                pc.writer.transport.abort()
        for task in background + [pc.task for pc in order[:running] if pc.task]:
            task.cancel()
        await asyncio.gather(*background, *[pc.task for pc in order[:running] if pc.task],
                             return_exceptions=True)
        monitors.stop()

    passing = [r['pcs'] for r in results if r['passed']]
    report = {
        'label': cfg.label,
        'when': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'config': {k: v for k, v in vars(cfg).items() if k not in ('password',)},
        'environment': environment(cfg),
        'steps': results,
        'storm': storm,
        'freeze': freeze,
        'max_passing_pcs': max(passing) if passing else 0,
    }
    if not cfg.keep_labs:
        removed = await asyncio.to_thread(delete_load_labs, api)
        print(f'Removed the {removed} load-test labs', flush=True)
    return report


def write_report(report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    cfg, env = report['config'], report['environment']
    lines = [f"# LabSense scale test - {report['label'] or 'run'}", '',
             f"{report['when']} - server `{cfg['server']}`, {cfg['dashboards']} dashboards "
             f"({cfg['measured']} timing, {cfg['stalled_dashboards']} stalled, "
             f"{cfg.get('dead_dashboards', 0)} per step gone to sleep), "
             f"software reports of {cfg['packages']} packages every {cfg.get('software_interval', 0):g} s, "
             f"churn every ~{cfg['churn_minutes']} min.",
             '']
    if cfg.get('profile_note'):
        lines += [cfg['profile_note'], '']
    lines += ['| PCs | heartbeats/s | dashboard msgs/s | latency p50 / p95 / p99 / max (ms) | '
              'delivered | false flips: dashboard / REST (while connecting) | REST p95 (ms) | '
              'server CPU avg / max | server RSS | DB CPU | result |',
              '|---:|---:|---:|---|---:|---:|---|---|---:|---:|---|']
    for r in report['steps']:
        lat, srv, db = r['latency_ms'], r.get('server', {}), r.get('db', {})
        wc = r.get('while_connecting', {})
        rest = ', '.join(f'{k} {v}' for k, v in r['rest_p95_ms'].items())
        lines.append(
            f"| {r['pcs']} | {r['heartbeats_per_s']} | {r['dashboard_msgs_per_s']} | "
            f"{lat['p50']} / {lat['p95']} / {lat['p99']} / {lat['max']} | "
            f"{'-' if r['delivered_ratio'] is None else format(r['delivered_ratio'], '.1%')} | "
            f"{r['false_offline_flips']} / {r['in_use_pcs_shown_available_by_rest']} "
            f"({wc.get('false_offline_flips', '-')} / {wc.get('in_use_pcs_shown_available_by_rest', '-')}) | {rest} | "
            f"{srv.get('cpu_avg_pct', '-')}% / {srv.get('cpu_max_pct', '-')}% | "
            f"{srv.get('rss_max_mb', '-')} MB | {db.get('cpu_avg_pct', '-')}% | "
            f"{'PASS' if r['passed'] else 'FAIL: ' + '; '.join(r['slo_failures'])} |")
    lines += ['', f"**Largest step meeting every SLO: {report['max_passing_pcs']} PCs.**", '']
    for r in report['steps']:
        if r.get('warning'):
            lines += [f"Warning at {r['pcs']} PCs: {r['warning']} "
                      f"(its event-loop lag p95 was {r['loadgen_loop_lag_p95_ms']} ms).", '']
    if report['storm']:
        s = report['storm']
        lines += [f"**Reconnect storm** ({s['pcs']} PCs dropped at once): {s['recovered']} back, "
                  f"median {s['recovery_s_p50']} s, slowest {s['recovery_s_max']} s, "
                  f"{s['false_offline_flips']} false offline flips, "
                  f"{s['in_use_pcs_shown_available_by_rest']} in-use PCs shown Available by REST "
                  f"-> {'PASS' if s['passed'] else 'FAIL'}.", '']
    if report.get('freeze'):
        f = report['freeze']
        lines += [f"**Server frozen for {f['seconds']:g} s** with {f['pcs']} PCs (heartbeats kept arriving): "
                  f"{f['pcs_flipped']} in-use PCs flipped to Available on resume, "
                  f"slowest heartbeat reached the dashboards after {f['latency_max_ms']} ms "
                  f"-> {'PASS' if f['passed'] else 'FAIL'}.", '']
    lines += ['SLOs: heartbeat-to-dashboard p95 <= {slo_p95_ms} ms and p99 <= {slo_p99_ms} ms, '
              '>= 97 % of heartbeats delivered, no false offline flips (seen by a dashboard or the REST API), REST p95 <= {slo_rest_ms} ms, '
              'no rejections, server CPU <= {slo_cpu_pct} % of one core.'.format(**cfg), '',
              f"Load generator: Python {env['loadgen_python']} on {env.get('loadgen_cpu', env['loadgen_platform'])}."]
    (out_dir / 'report.md').write_text('\n'.join(lines) + '\n')
    return out_dir


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--server', default=os.environ.get('LABSENSE_SERVER_HOST', '127.0.0.1'),
                    help="server's IP (the Windows laptop's Wi-Fi IP in the lab)")
    ap.add_argument('--tcp-port', type=int, default=9000)
    ap.add_argument('--api-port', type=int, default=8000)
    ap.add_argument('--steps', default='100,250,500,1000',
                    type=lambda s: [int(x) for x in s.split(',') if x])
    ap.add_argument('--step-seconds', type=int, default=60, help='measurement window per step')
    ap.add_argument('--warmup-seconds', type=int, default=15)
    ap.add_argument('--ramp-seconds', type=float, default=10.0, help='minimum time to bring new PCs online')
    ap.add_argument('--connect-rate', type=float, default=50.0,
                    help='max new PCs per second while ramping (a lab booting up)')
    ap.add_argument('--dashboards', type=int, default=10, help='open dashboards (browser tabs)')
    ap.add_argument('--measured', type=int, default=3, help='how many of them time every heartbeat')
    ap.add_argument('--stalled-dashboards', type=int, default=0,
                    help="dashboards that stay connected but stop reading (a frozen tab)")
    ap.add_argument('--dead-dashboards', type=int, default=0,
                    help='per step, dashboards that open and then go silent like a laptop '
                         'whose lid was shut (testbed only: needs Linux, root and nftables)')
    ap.add_argument('--packages', type=int, default=1500, help='software report size per PC (0 = none)')
    ap.add_argument('--software-interval', type=float, default=300.0,
                    help="seconds between a PC's software reports (the agent's "
                         "LABSENSE_SOFTWARE_SCAN_INTERVAL default; 0 = only at boot)")
    ap.add_argument('--churn-minutes', type=float, default=30.0,
                    help='mean time between a PC changing between in-use and idle (0 = never)')
    ap.add_argument('--lab-size', type=int, default=50, help='PCs per load-test lab (max 99)')
    ap.add_argument('--storm', action='store_true', help='finish with a reconnect storm')
    ap.add_argument('--freeze-server', type=float, default=0, metavar='SECONDS',
                    help='finally, pause the server process (SIGSTOP) this long while PCs keep '
                         'sending (testbed only: needs --monitor-pid, Linux)')
    ap.add_argument('--stop-on-fail', action='store_true')
    ap.add_argument('--keep-labs', action='store_true',
                    help='keep the load-test labs (ltNN) afterwards; by default they are deleted, '
                         'and every run deletes any left over before it starts')
    ap.add_argument('--monitor-pid', type=int, help='sample this local server process (psutil)')
    ap.add_argument('--db-container', help='sample this Docker container (docker stats)')
    ap.add_argument('--profile', action='store_true',
                    help='record a py-spy flame graph of --monitor-pid during each step')
    ap.add_argument('--slo-p95-ms', type=float, default=1000)
    ap.add_argument('--slo-p99-ms', type=float, default=3000)
    ap.add_argument('--slo-rest-ms', type=float, default=1000)
    ap.add_argument('--slo-cpu-pct', type=float, default=80)
    ap.add_argument('--admin-email', default='admin@labsense.dev')
    ap.add_argument('--student-email', default='student@labsense.dev')
    ap.add_argument('--password', default='password123')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--label', default='')
    ap.add_argument('--profile-note', default='', help='free text recorded in the report')
    ap.add_argument('--out', default=str(HERE / 'results'))
    cfg = ap.parse_args(argv)
    if cfg.measured > cfg.dashboards:
        ap.error('--measured cannot exceed --dashboards')
    if not 1 <= cfg.lab_size <= 99:
        ap.error('--lab-size must be 1-99 (the server numbers PCs with two digits)')
    return cfg


def main(argv=None) -> int:
    cfg = parse_args(argv)
    name = time.strftime('%Y%m%d-%H%M%S') + (f'-{cfg.label}' if cfg.label else '')
    out_dir = Path(cfg.out) / name
    report = asyncio.run(run(cfg, out_dir))
    out = write_report(report, out_dir)
    print(f'\nReport: {out}/report.md')
    print(f"Largest step meeting every SLO: {report['max_passing_pcs']} PCs")
    return 0 if report['steps'] and report['steps'][-1]['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
