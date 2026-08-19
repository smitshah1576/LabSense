"""Installed software inventory scanner.

Scans the system for installed packages from multiple sources:

- **dpkg** — Debian/Ubuntu system packages
- **pip**  — globally installed Python packages (``pip list --format=json``)

Virtual environments are explicitly NOT scanned (stated project limitation).

All subprocess calls use ``asyncio.create_subprocess_exec`` to avoid blocking
the event loop.  Each scanner degrades gracefully if its tool is missing.
"""

from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger(__name__)


async def scan_dpkg() -> list[str]:
    """Scan system packages via ``dpkg -l``.

    Returns:
        Sorted list of package names for packages in state ``ii`` (installed).
        Returns an empty list if ``dpkg`` is not available.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            'dpkg', '-l',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=60.0
        )

        if proc.returncode != 0:
            logger.warning(
                'dpkg -l exited with code %d: %s',
                proc.returncode,
                stderr.decode().strip(),
            )
            return []

        packages: list[str] = []
        for line in stdout.decode(errors='replace').splitlines():
            # dpkg -l output lines for installed packages start with 'ii '
            if line.startswith('ii '):
                parts = line.split()
                if len(parts) >= 2:
                    # parts[1] is the package name (may include :arch suffix)
                    packages.append(parts[1])
        return packages

    except FileNotFoundError:
        logger.info('dpkg not found — skipping system package scan')
        return []
    except asyncio.TimeoutError:
        logger.warning('dpkg -l timed out after 60s')
        return []
    except Exception as exc:
        logger.warning('dpkg scan failed: %s', exc)
        return []


async def scan_pip() -> list[str]:
    """Scan globally installed pip packages via ``pip list --format=json``.

    Returns:
        List of package names.  Returns an empty list if ``pip`` is not
        available or the output cannot be parsed.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            'pip', 'list', '--format=json',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=60.0
        )

        if proc.returncode != 0:
            logger.warning(
                'pip list exited with code %d: %s',
                proc.returncode,
                stderr.decode().strip(),
            )
            return []

        packages = json.loads(stdout.decode())
        return [p['name'] for p in packages if 'name' in p]

    except FileNotFoundError:
        logger.info('pip not found — skipping Python package scan')
        return []
    except asyncio.TimeoutError:
        logger.warning('pip list timed out after 60s')
        return []
    except json.JSONDecodeError as exc:
        logger.warning('pip list returned invalid JSON: %s', exc)
        return []
    except Exception as exc:
        logger.warning('pip scan failed: %s', exc)
        return []


async def scan_all_software() -> list[str]:
    """Scan all software sources and return a deduplicated, sorted list.

    Runs dpkg and pip scans concurrently and merges the results.

    Returns:
        Sorted, deduplicated list of all discovered package names.
    """
    dpkg_pkgs, pip_pkgs = await asyncio.gather(
        scan_dpkg(),
        scan_pip(),
    )

    all_packages = sorted(set(dpkg_pkgs + pip_pkgs))
    logger.info(
        'Software scan complete: %d packages found '
        '(%d dpkg, %d pip)',
        len(all_packages),
        len(dpkg_pkgs),
        len(pip_pkgs),
    )
    return all_packages
