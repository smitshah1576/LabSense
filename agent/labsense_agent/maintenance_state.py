"""Maintenance status hand-off between the agent and the desktop notifier.

The agent runs as the ``labsense`` system user and cannot reach the logged-in
user's display or session bus, so it cannot show a notification itself.
Instead it publishes the status the server sent to a small world-readable
JSON file, and ``notifier.py`` — running inside each desktop session — shows
the notification.

The file lives in ``config.STATE_DIR`` (``/run/labsense`` by default), a
tmpfs that is empty after every boot.  A missing file therefore means
"not yet told by the server", never "not under maintenance", so a PC that
was cleared while it was powered off never flashes a stale notice.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

_FILENAME = 'maintenance.json'

# Last value written by this process, so reconnects that repeat the same
# status don't rewrite the file.
_last_written: Optional[bool] = None
_warned_unwritable = False


def status_path() -> str:
    """Absolute path of the maintenance status file."""
    return os.path.join(config.STATE_DIR, _FILENAME)


def write_status(is_maintenance: bool, pc_id: str) -> None:
    """Publish the maintenance status atomically for the notifier.

    Never raises: failing to publish costs the user a notice, but must not
    take down the heartbeat.
    """
    global _last_written, _warned_unwritable

    if is_maintenance == _last_written:
        return

    payload = {
        'pc_id': pc_id,
        'is_maintenance': is_maintenance,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    try:
        fd, tmp = tempfile.mkstemp(dir=config.STATE_DIR, prefix='.maintenance-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                json.dump(payload, fh)
            # Desktop users must be able to read it; mkstemp creates 0600.
            os.chmod(tmp, 0o644)
            os.replace(tmp, status_path())
        except BaseException:
            os.unlink(tmp)
            raise
    except OSError as exc:
        if not _warned_unwritable:
            logger.warning(
                'Cannot write maintenance status to %s (%s) — the desktop '
                'notifier will not show maintenance notices. Check '
                'RuntimeDirectory=labsense in the service unit, or set '
                'LABSENSE_STATE_DIR.',
                status_path(), exc,
            )
            _warned_unwritable = True
        return

    _last_written = is_maintenance
    _warned_unwritable = False
    logger.debug('Wrote maintenance status (%s) to %s', is_maintenance, status_path())


def read_status() -> Optional[bool]:
    """Return the published status, or ``None`` if it is not known yet."""
    try:
        with open(status_path(), encoding='utf-8') as fh:
            return bool(json.load(fh)['is_maintenance'])
    except (OSError, ValueError, KeyError, TypeError):
        return None
