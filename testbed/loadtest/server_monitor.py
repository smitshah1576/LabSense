"""Sample the LabSense server process's CPU and memory during a load test.

Run it on the machine the server runs on - the Windows laptop in the lab, or
the testbed host (testbed.sh scale does that for you through loadgen.py).
CPU is reported as a percentage of ONE core: the backend is a single asyncio
event loop, so ~100 % means it is saturated no matter how many cores the
machine has.

Usage:
    python server_monitor.py --match uvicorn          # find the server by command line
    python server_monitor.py --pid 1234 --csv run.csv

Needs psutil (`pip install psutil`; the testbed installs it). Ctrl-C prints a summary.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time

import psutil


class ProcessSampler:
    """CPU (% of one core) and RSS of a process and its children."""

    def __init__(self, pid: int):
        self.root = psutil.Process(pid)
        self._procs: dict[int, psutil.Process] = {}
        self.samples: list[tuple[float, float, float]] = []  # (time, cpu %, rss MB)
        self.sample()  # prime cpu_percent counters; first reading is discarded
        self.samples.clear()

    def _tree(self) -> list[psutil.Process]:
        procs = [self.root]
        try:
            procs += self.root.children(recursive=True)
        except psutil.Error:
            pass
        for p in procs:  # keep one Process object per pid so cpu_percent has history
            self._procs.setdefault(p.pid, p)
        return [self._procs[p.pid] for p in procs]

    def sample(self) -> tuple[float, float]:
        cpu = rss = 0.0
        for p in self._tree():
            try:
                cpu += p.cpu_percent(interval=None)
                rss += p.memory_info().rss
            except psutil.Error:
                pass
        rss_mb = rss / 2**20
        self.samples.append((time.time(), cpu, rss_mb))
        return cpu, rss_mb

    def reset(self) -> None:
        self.samples.clear()

    def summary(self) -> dict:
        if not self.samples:
            return {}
        cpus = [s[1] for s in self.samples]
        return {
            'cpu_avg_pct': round(statistics.fmean(cpus), 1),
            'cpu_p95_pct': round(sorted(cpus)[int(0.95 * (len(cpus) - 1))], 1),
            'cpu_max_pct': round(max(cpus), 1),
            'rss_max_mb': round(max(s[2] for s in self.samples), 1),
            'samples': len(self.samples),
        }


def find_pid(match: str) -> int:
    me = psutil.Process().pid
    for p in psutil.process_iter(['pid', 'cmdline']):
        cmd = ' '.join(p.info['cmdline'] or [])
        if match in cmd and p.info['pid'] != me and 'server_monitor' not in cmd:
            return p.info['pid']
    raise SystemExit(f'no process whose command line contains {match!r}')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument('--pid', type=int)
    who.add_argument('--match', help='substring of the server command line, e.g. uvicorn')
    ap.add_argument('--interval', type=float, default=1.0)
    ap.add_argument('--csv', help='also write every sample to this CSV file')
    args = ap.parse_args()

    pid = args.pid or find_pid(args.match)
    sampler = ProcessSampler(pid)
    print(f'monitoring pid {pid}: {" ".join(sampler.root.cmdline())[:100]}')
    print('time      cpu% (of one core)   rss MB')
    out = open(args.csv, 'w', newline='') if args.csv else None
    writer = csv.writer(out) if out else None
    if writer:
        writer.writerow(['unix_time', 'cpu_pct_of_one_core', 'rss_mb'])
    try:
        while True:
            time.sleep(args.interval)
            cpu, rss = sampler.sample()
            print(f'{time.strftime("%H:%M:%S")}  {cpu:8.1f}            {rss:8.1f}', flush=True)
            if writer:
                writer.writerow([round(time.time(), 1), round(cpu, 1), round(rss, 1)])
    except KeyboardInterrupt:
        pass
    except psutil.NoSuchProcess:
        print('server process exited')
    finally:
        if out:
            out.close()
    print('summary:', sampler.summary())
    return 0


if __name__ == '__main__':
    sys.exit(main())
