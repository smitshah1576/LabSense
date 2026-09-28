# LabSense agent as a container.
#
# Used by the testbed (testbed/compose.yml) to run the real agent as one of the
# simulated lab PCs. Real lab PCs run the agent under systemd via
# deploy_agent.sh instead: inside a container there is no logind, no D-Bus
# system bus and no /dev/input, so the agent runs in its degraded mode
# (session from utmp, D-Bus listener retrying) — which is itself worth testing.
FROM python:3.11-slim

WORKDIR /opt/labsense-agent

COPY requirements.txt .
# Optional build secret `pip_ca`: a CA bundle for networks whose proxy
# re-signs TLS (such as the Claude Code cloud sandbox). Without it, plain pip.
RUN --mount=type=secret,id=pip_ca \
    if [ -s /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY labsense_agent ./labsense_agent
COPY probe_telemetry.py test_heartbeat.py ./

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "labsense_agent.main"]
