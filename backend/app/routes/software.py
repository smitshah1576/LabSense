"""Software search routes — global and lab-wise software discovery."""

import json

from fastapi import APIRouter, Depends, Query, Request
from ..models.schemas import SoftwareSearchResult
from ..auth.dependencies import get_current_user

router = APIRouter(tags=["software"])


def _as_package_list(value) -> list[str]:
    """Normalise an ``installed_software`` column value to a list of names.

    The pool registers a jsonb codec so this is normally already a list, but
    rows written before that codec existed hold a double-encoded JSON string.
    Iterating one of those yields single characters, so decode it here rather
    than returning nonsense matches.
    """
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    if isinstance(value, list):
        return [str(pkg) for pkg in value]
    return []


def _matching_packages(value, query: str) -> list[str]:
    """Return the package names in ``value`` that contain ``query``."""
    needle = query.lower()
    return [pkg for pkg in _as_package_list(value) if needle in pkg.lower()]


@router.get("/software/search", response_model=list[SoftwareSearchResult])
async def search_software_global(
    request: Request,
    q: str = Query(..., min_length=2, description="Software package name to search"),
    current_user: dict = Depends(get_current_user),
):
    """Search for installed software across all labs (global search)."""
    pool = request.app.state.db_pool
    pattern = f"%{q}%"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT p.pc_id, p.lab_id, l.lab_name, p.installed_software
               FROM pcs p
               JOIN labs l ON p.lab_id = l.lab_id
               WHERE EXISTS (
                   SELECT 1
                   FROM jsonb_array_elements_text(p.installed_software) AS sw
                   WHERE sw ILIKE $1
               )""",
            pattern,
        )

        results = []
        for row in rows:
            matching = _matching_packages(row["installed_software"], q)
            results.append(SoftwareSearchResult(
                pc_id=row["pc_id"],
                lab_id=row["lab_id"],
                lab_name=row["lab_name"],
                matching_packages=matching,
            ))
        return results


@router.get("/labs/{lab_id}/software/search", response_model=list[SoftwareSearchResult])
async def search_software_lab(
    lab_id: str,
    request: Request,
    q: str = Query(..., min_length=2, description="Software package name to search"),
    current_user: dict = Depends(get_current_user),
):
    """Search for installed software within a single lab."""
    pool = request.app.state.db_pool
    pattern = f"%{q}%"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT p.pc_id, p.lab_id, l.lab_name, p.installed_software
               FROM pcs p
               JOIN labs l ON p.lab_id = l.lab_id
               WHERE p.lab_id = $1 AND EXISTS (
                   SELECT 1
                   FROM jsonb_array_elements_text(p.installed_software) AS sw
                   WHERE sw ILIKE $2
               )""",
            lab_id,
            pattern,
        )

        results = []
        for row in rows:
            matching = _matching_packages(row["installed_software"], q)
            results.append(SoftwareSearchResult(
                pc_id=row["pc_id"],
                lab_id=row["lab_id"],
                lab_name=row["lab_name"],
                matching_packages=matching,
            ))
        return results
