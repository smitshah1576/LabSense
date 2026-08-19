"""Lab routes — list labs, get lab detail, get lab state."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException
from ..models.schemas import LabResponse
from ..models.enums import PCState
from ..auth.dependencies import get_current_user
from ..state.lab_state import compute_lab_state

router = APIRouter(prefix="/labs", tags=["labs"])


async def _enrich_lab(lab_row, conn, state_manager, now) -> dict:
    """Add computed lab state and available PC count to a lab row."""
    lab_id = lab_row["lab_id"]

    # Get timetable entries for this lab
    timetable_rows = await conn.fetch(
        """SELECT timetable_id, day_of_week, start_time, end_time
           FROM master_timetables WHERE lab_id = $1""",
        lab_id,
    )

    # Get cancellations for today
    cancellations = await conn.fetch(
        """SELECT sc.timetable_id
           FROM slot_cancellations sc
           JOIN master_timetables mt ON sc.timetable_id = mt.timetable_id
           WHERE mt.lab_id = $1 AND sc.cancelled_for_date = $2""",
        lab_id,
        now.date(),
    )
    cancelled_ids = {row["timetable_id"] for row in cancellations}

    lab_state = compute_lab_state(
        operating_start=lab_row["operating_start_time"],
        operating_end=lab_row["operating_end_time"],
        current_time=now,
        timetable_rows=[dict(r) for r in timetable_rows],
        cancelled_timetable_ids=cancelled_ids,
    )

    # Count available PCs
    pcs = await conn.fetch("SELECT pc_id FROM pcs WHERE lab_id = $1", lab_id)
    pc_ids = [row["pc_id"] for row in pcs]
    live_states = await state_manager.get_lab_states(pc_ids)
    available_count = sum(
        1 for s in live_states.values()
        if s.current_state in (PCState.AVAILABLE, PCState.AVAILABLE_SLEEP)
    )

    return LabResponse(
        lab_id=lab_row["lab_id"],
        lab_name=lab_row["lab_name"],
        operating_start_time=lab_row["operating_start_time"],
        operating_end_time=lab_row["operating_end_time"],
        state=lab_state.value,
    )


@router.get("", response_model=list[LabResponse])
async def get_labs(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """List all labs with computed state."""
    pool = request.app.state.db_pool
    state_manager = request.app.state.pc_state_manager
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        labs = await conn.fetch(
            "SELECT lab_id, lab_name, operating_start_time, operating_end_time FROM labs"
        )
        result = []
        for lab in labs:
            enriched = await _enrich_lab(lab, conn, state_manager, now)
            result.append(enriched)
    return result


@router.get("/{lab_id}", response_model=LabResponse)
async def get_lab(
    lab_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Get a single lab with computed state."""
    pool = request.app.state.db_pool
    state_manager = request.app.state.pc_state_manager
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        lab = await conn.fetchrow(
            "SELECT lab_id, lab_name, operating_start_time, operating_end_time FROM labs WHERE lab_id = $1",
            lab_id,
        )
        if not lab:
            raise HTTPException(status_code=404, detail="Lab not found")
        return await _enrich_lab(lab, conn, state_manager, now)


@router.get("/{lab_id}/state")
async def get_lab_state(
    lab_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Get just the lab state (Open/Occupied/Closed)."""
    pool = request.app.state.db_pool
    state_manager = request.app.state.pc_state_manager
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        lab = await conn.fetchrow(
            "SELECT lab_id, lab_name, operating_start_time, operating_end_time FROM labs WHERE lab_id = $1",
            lab_id,
        )
        if not lab:
            raise HTTPException(status_code=404, detail="Lab not found")
        enriched = await _enrich_lab(lab, conn, state_manager, now)
        return {"lab_id": lab_id, "state": enriched.state}
