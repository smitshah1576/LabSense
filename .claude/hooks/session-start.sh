#!/bin/bash
# SessionStart hook (Claude Code on the web): get the LabSense E2E testbed
# ready to run. Installs host dependencies and pre-builds the Docker images;
# it does not start any services — `testbed/testbed.sh up` does that in ~10 s.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
    exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Progress goes to stderr; stdout from this hook is added to Claude's context.
./testbed/bootstrap.sh >&2

# Best effort: the session is still usable without Docker (backend unit work,
# frontend builds), so never fail session start over it.
if ! ./testbed/testbed.sh prepare >&2; then
    echo "[session-start] Docker image pre-warm failed; testbed/testbed.sh up will retry." >&2
fi

cat <<'MSG'
LabSense E2E testbed is installed (see TESTBED.md). Nothing is running yet.
  testbed/testbed.sh up      start DB, backend, frontend and 5 client PCs (~10 s)
  testbed/testbed.sh test    run the end-to-end suite
  testbed/pcctl status       fleet table; drive PCs with e.g. `testbed/pcctl 3 sleep`
MSG
