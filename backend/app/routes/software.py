"""Software search routes — global and lab-wise software discovery."""

from fastapi import APIRouter, Depends, Query, Request
from ..models.schemas import SoftwareSearchResult
from ..auth.dependencies import get_current_user

router = APIRouter(tags=["software"])


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
            # Extract matching package names
            matching = [
                pkg for pkg in (row["installed_software"] or [])
                if q.lower() in pkg.lower()
            ]
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
            matching = [
                pkg for pkg in (row["installed_software"] or [])
                if q.lower() in pkg.lower()
            ]
            results.append(SoftwareSearchResult(
                pc_id=row["pc_id"],
                lab_id=row["lab_id"],
                lab_name=row["lab_name"],
                matching_packages=matching,
            ))
        return results
