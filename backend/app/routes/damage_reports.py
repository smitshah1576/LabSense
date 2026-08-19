"""Damage report routes — student submission and admin review."""

from fastapi import APIRouter, Depends, Request, HTTPException
from ..models.schemas import DamageReportCreate, DamageReportResponse, DamageReportResolve
from ..models.enums import UserRole, DamageReportStatus
from ..auth.dependencies import get_current_user, require_role

router = APIRouter(prefix="/damage-reports", tags=["damage-reports"])


@router.post("", response_model=DamageReportResponse)
async def submit_report(
    report: DamageReportCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Submit a damage report for a PC (any authenticated user)."""
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        # Verify PC exists
        pc = await conn.fetchrow("SELECT pc_id FROM pcs WHERE pc_id = $1", report.pc_id)
        if not pc:
            raise HTTPException(status_code=404, detail="PC not found")

        row = await conn.fetchrow(
            """INSERT INTO damage_reports (pc_id, reported_by, issue_description, status)
               VALUES ($1, $2, $3, $4)
               RETURNING report_id, pc_id, reported_by, issue_description, status,
                         created_at, resolved_by, resolved_at""",
            report.pc_id,
            current_user["user_id"],
            report.issue_description,
            DamageReportStatus.PENDING.value,
        )
        return dict(row)


@router.get(
    "",
    response_model=list[DamageReportResponse],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def get_all_reports(request: Request):
    """List all damage reports (admin only)."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM damage_reports ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]


@router.get(
    "/pending",
    response_model=list[DamageReportResponse],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def get_pending_reports(request: Request):
    """List pending damage reports (admin only)."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM damage_reports WHERE status = $1 ORDER BY created_at ASC",
            DamageReportStatus.PENDING.value,
        )
        return [dict(r) for r in rows]


@router.put(
    "/{report_id}/resolve",
    response_model=DamageReportResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def resolve_report(
    report_id: int,
    resolve_data: DamageReportResolve,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Resolve a damage report. If APPROVED, sets the PC to MAINTENANCE."""
    pool = request.app.state.db_pool
    state_manager = request.app.state.pc_state_manager

    async with pool.acquire() as conn:
        report = await conn.fetchrow(
            "SELECT report_id, pc_id FROM damage_reports WHERE report_id = $1",
            report_id,
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        status_val = resolve_data.status.value if hasattr(resolve_data.status, "value") else resolve_data.status

        await conn.execute(
            """UPDATE damage_reports
               SET status = $1, resolved_by = $2, resolved_at = CURRENT_TIMESTAMP
               WHERE report_id = $3""",
            status_val,
            current_user["user_id"],
            report_id,
        )

        # If approved, set PC to MAINTENANCE
        if status_val == DamageReportStatus.APPROVED.value:
            pc_id = report["pc_id"]
            transition = await state_manager.set_maintenance(pc_id, True)

            await conn.execute(
                "UPDATE pcs SET is_maintenance = TRUE, current_state = 'MAINTENANCE' WHERE pc_id = $1",
                pc_id,
            )

            if transition:
                old_state, new_state = transition
                await conn.execute(
                    """INSERT INTO state_transitions (pc_id, from_state, to_state)
                       VALUES ($1, $2, $3)""",
                    pc_id,
                    old_state.value if hasattr(old_state, "value") else str(old_state),
                    new_state.value if hasattr(new_state, "value") else str(new_state),
                )

        updated = await conn.fetchrow(
            "SELECT * FROM damage_reports WHERE report_id = $1", report_id
        )
        return dict(updated)
