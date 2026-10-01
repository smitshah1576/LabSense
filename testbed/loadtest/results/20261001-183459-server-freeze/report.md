# LabSense scale test - server-freeze

2026-10-01T18:37:10+00:00 - server `172.28.0.1`, 10 dashboards (3 timing, 0 stalled, 0 per step gone to sleep), software reports of 1500 packages every 300 s, churn every ~30.0 min.

Laptop profile: backend pinned to CPU 0, started as on the Windows server (no --reload, stock asyncio loop); PostgreSQL on CPU 1 with 1g; load generator on CPUs 2-3. Host calibration score (loadtest/calibrate.py): 37,588 heartbeats/s.

| PCs | heartbeats/s | dashboard msgs/s | latency p50 / p95 / p99 / max (ms) | delivered | false flips: dashboard / REST (while connecting) | REST p95 (ms) | server CPU avg / max | server RSS | DB CPU | result |
|---:|---:|---:|---|---:|---:|---|---|---:|---:|---|
| 1000 | 200.0 | 2015.2 | 1.1 / 2.7 / 6.3 / 141.1 | 100.0% | 0 / 0 (0 / 0) | health 6.2, lab_pcs 39.1, labs 242.5 | 11.9% / 20.0% | 198.5 MB | 2.8% | PASS |

**Largest step meeting every SLO: 1000 PCs.**

**Server frozen for 12 s** with 1000 PCs (heartbeats kept arriving): 222 in-use PCs flipped to Available on resume, slowest heartbeat reached the dashboards after 12607.3 ms -> FAIL.

SLOs: heartbeat-to-dashboard p95 <= 1000 ms and p99 <= 3000 ms, >= 97 % of heartbeats delivered, no false offline flips (seen by a dashboard or the REST API), REST p95 <= 1000 ms, no rejections, server CPU <= 80 % of one core.

Load generator: Python 3.11.15 on Intel(R) Xeon(R) Processor @ 2.10GHz.
