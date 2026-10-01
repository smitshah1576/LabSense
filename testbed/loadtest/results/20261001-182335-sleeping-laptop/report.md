# LabSense scale test - sleeping-laptop

2026-10-01T18:26:45+00:00 - server `172.28.0.1`, 10 dashboards (3 timing, 0 stalled, 1 per step gone to sleep), software reports of 1500 packages every 300 s, churn every ~30.0 min.

Laptop profile: backend pinned to CPU 0, started as on the Windows server (no --reload, stock asyncio loop); PostgreSQL on CPU 1 with 1g; load generator on CPUs 2-3. Host calibration score (loadtest/calibrate.py): 41,510 heartbeats/s.

| PCs | heartbeats/s | dashboard msgs/s | latency p50 / p95 / p99 / max (ms) | delivered | false flips: dashboard / REST (while connecting) | REST p95 (ms) | server CPU avg / max | server RSS | DB CPU | result |
|---:|---:|---:|---|---:|---:|---|---|---:|---:|---|
| 500 | 100.0 | 1013.2 | 1.3 / 2.5 / 6.3 / 25.7 | 100.0% | 0 / 0 (0 / 0) | health 8.5, lab_pcs 29.8, labs 361.4 | 8.0% / 16.0% | 134.7 MB | 4.3% | PASS |
| 1000 | 200.1 | 818.8 | 1.0 / 2.4 / 6.3 / 130.4 | 37.1% | 0 / 24 (0 / 0) | health 9.2, lab_pcs 29.3, labs 245.6 | 7.3% / 19.0% | 206.3 MB | 8.4% | FAIL: only 37% of heartbeats reached dashboards; 24 in-use PCs shown as Available by the REST API |

**Largest step meeting every SLO: 500 PCs.**

SLOs: heartbeat-to-dashboard p95 <= 1000 ms and p99 <= 3000 ms, >= 97 % of heartbeats delivered, no false offline flips (seen by a dashboard or the REST API), REST p95 <= 1000 ms, no rejections, server CPU <= 80 % of one core.

Load generator: Python 3.11.15 on Intel(R) Xeon(R) Processor @ 2.10GHz.
