# LabSense scale test - 50-dashboards

2026-10-01T18:34:43+00:00 - server `172.28.0.1`, 50 dashboards (3 timing, 0 stalled, 0 per step gone to sleep), software reports of 1500 packages every 300 s, churn every ~30.0 min.

Laptop profile: backend pinned to CPU 0, started as on the Windows server (no --reload, stock asyncio loop); PostgreSQL on CPU 1 with 1g; load generator on CPUs 2-3. Host calibration score (loadtest/calibrate.py): 40,199 heartbeats/s.

| PCs | heartbeats/s | dashboard msgs/s | latency p50 / p95 / p99 / max (ms) | delivered | false flips: dashboard / REST (while connecting) | REST p95 (ms) | server CPU avg / max | server RSS | DB CPU | result |
|---:|---:|---:|---|---:|---:|---|---|---:|---:|---|
| 1000 | 200.0 | 10075.8 | 1.9 / 6.3 / 11.0 / 123.6 | 100.0% | 0 / 0 (0 / 0) | health 8.7, lab_pcs 37.5, labs 345.2 | 28.8% / 35.8% | 202.4 MB | 2.5% | PASS |

**Largest step meeting every SLO: 1000 PCs.**

SLOs: heartbeat-to-dashboard p95 <= 1000 ms and p99 <= 3000 ms, >= 97 % of heartbeats delivered, no false offline flips (seen by a dashboard or the REST API), REST p95 <= 1000 ms, no rejections, server CPU <= 80 % of one core.

Load generator: Python 3.11.15 on Intel(R) Xeon(R) Processor @ 2.10GHz.
