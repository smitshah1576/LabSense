"""Timetable routes — master timetable CRUD and slot cancellations."""

from fastapi import APIRouter, Depends, Request, HTTPException
from ..models.schemas import TimetableEntry, TimetableCreate, SlotCancellation, SlotCancellationCreate
from ..models.enums import UserRole
from ..auth.dependencies import get_current_user, require_role

router = APIRouter(tags=["timetable"])


@router.get("/labs/{lab_id}/timetable", response_model=list[TimetableEntry])
async def get_timetable(
    lab_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Get all timetable entries for a lab."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT timetable_id, lab_id, day_of_week, start_time, end_time, course_code
               FROM master_timetables WHERE lab_id = $1
               ORDER BY day_of_week, start_time""",
            lab_id,
        )
        return [dict(r) for r in rows]


@router.post(
    "/labs/{lab_id}/timetable",
    response_model=TimetableEntry,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def create_timetable_entry(
    lab_id: str,
    entry: TimetableCreate,
    request: Request,
):
    """Create a new timetable entry (admin only)."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        # Verify lab exists
        lab = await conn.fetchrow("SELECT lab_id FROM labs WHERE lab_id = $1", lab_id)
        if not lab:
            raise HTTPException(status_code=404, detail="Lab not found")

        row = await conn.fetchrow(
            """INSERT INTO master_timetables (lab_id, day_of_week, start_time, end_time, course_code)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING timetable_id, lab_id, day_of_week, start_time, end_time, course_code""",
            lab_id,
            entry.day_of_week,
            entry.start_time,
            entry.end_time,
            entry.course_code,
        )
        return dict(row)


@router.delete(
    "/timetable/{timetable_id}",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def delete_timetable_entry(timetable_id: int, request: Request):
    """Delete a timetable entry (admin only)."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM master_timetables WHERE timetable_id = $1", timetable_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Timetable entry not found")
    return {"message": "Timetable entry deleted"}


@router.post(
    "/timetable/{timetable_id}/cancel",
    response_model=SlotCancellation,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.PROFESSOR))],
)
async def cancel_slot(
    timetable_id: int,
    cancel: SlotCancellationCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Cancel a timetable slot for a specific date (prof/admin only)."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        # Verify timetable entry exists
        entry = await conn.fetchrow(
            "SELECT timetable_id FROM master_timetables WHERE timetable_id = $1",
            timetable_id,
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Timetable entry not found")

        # Check if already cancelled for this date
        existing = await conn.fetchrow(
            """SELECT cancellation_id FROM slot_cancellations
               WHERE timetable_id = $1 AND cancelled_for_date = $2""",
            timetable_id,
            cancel.cancelled_for_date,
        )
        if existing:
            raise HTTPException(
                status_code=400, detail="Slot already cancelled for this date"
            )

        row = await conn.fetchrow(
            """INSERT INTO slot_cancellations (timetable_id, cancelled_for_date, cancelled_by)
               VALUES ($1, $2, $3)
               RETURNING cancellation_id, timetable_id, cancelled_for_date, cancelled_by""",
            timetable_id,
            cancel.cancelled_for_date,
            current_user["user_id"],
        )
        return dict(row)


@router.get("/labs/{lab_id}/cancellations", response_model=list[SlotCancellation])
async def get_cancellations(
    lab_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """List cancellations for a lab's timetable entries."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT sc.cancellation_id, sc.timetable_id, sc.cancelled_for_date, sc.cancelled_by
               FROM slot_cancellations sc
               JOIN master_timetables mt ON sc.timetable_id = mt.timetable_id
               WHERE mt.lab_id = $1
               ORDER BY sc.cancelled_for_date DESC""",
            lab_id,
        )
        return [dict(r) for r in rows]
