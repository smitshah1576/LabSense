# LabSense scale test - baseline

2026-10-01T18:54:20+00:00 - server `172.28.0.1`, 10 dashboards (3 timing, 0 stalled, 0 per step gone to sleep), software reports of 1500 packages every 300 s, churn every ~30.0 min.

Laptop profile: backend pinned to CPU 0, started as on the Windows server (no --reload, stock asyncio loop); PostgreSQL on CPU 1 with 1g; load generator on CPUs 2-3. Host calibration score (loadtest/calibrate.py): 43,471 heartbeats/s.

| PCs | heartbeats/s | dashboard msgs/s | latency p50 / p95 / p99 / max (ms) | delivered | false flips: dashboard / REST (while connecting) | REST p95 (ms) | server CPU avg / max | server RSS | DB CPU | result |
|---:|---:|---:|---|---:|---:|---|---|---:|---:|---|
| 1000 | 200.0 | 2015.3 | 1.0 / 2.4 / 6.3 / 55.2 | 100.0% | 0 / 0 (0 / 0) | health 4.9, lab_pcs 31.3, labs 238.1, software_search 879.6 | 12.2% / 20.0% | 204.3 MB | 13.0% | PASS |
| 2000 | 400.0 | 4019.5 | 1.0 / 3.7 / 9.0 / 121.0 | 100.0% | 0 / 0 (0 / 0) | labs 228.8, health 17.8, lab_pcs 39.3, software_search 1914.8 | 18.6% / 24.9% | 333.8 MB | 20.7% | FAIL: REST software_search p95 1914.8 ms > 1000 |
| 4000 | 800.0 | 8026.7 | 1.4 / 7.4 / 38.3 / 377.2 | 100.0% | 0 / 0 (0 / 0) | health 10.9, lab_pcs 42.0, software_search 3635.9, labs 349.5 | 31.4% / 45.9% | 591.4 MB | 30.9% | FAIL: REST software_search p95 3635.9 ms > 1000 |
| 6000 | 1200.0 | 12037.5 | 2.1 / 36.0 / 221.5 / 786.9 | 100.0% | 0 / 0 (0 / 0) | health 13.6, lab_pcs 47.2, software_search 6337.0, labs 485.4 | 43.2% / 79.7% | 851.2 MB | 43.7% | FAIL: REST software_search p95 6337.0 ms > 1000 |

**Largest step meeting every SLO: 1000 PCs.**

**Reconnect storm** (6000 PCs dropped at once): 6000 back, median 7.6 s, slowest 8.9 s, 0 false offline flips, 0 in-use PCs shown Available by REST -> PASS.

**Server frozen for 12 s** with 6000 PCs (heartbeats kept arriving): 1710 in-use PCs flipped to Available on resume, slowest heartbeat reached the dashboards after 18432.5 ms -> FAIL.

SLOs: heartbeat-to-dashboard p95 <= 1000 ms and p99 <= 3000 ms, >= 97 % of heartbeats delivered, no false offline flips (seen by a dashboard or the REST API), REST p95 <= 1000 ms, no rejections, server CPU <= 80 % of one core.

Load generator: Python 3.11.15 on Intel(R) Xeon(R) Processor @ 2.10GHz.
