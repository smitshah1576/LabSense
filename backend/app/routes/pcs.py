"""PC routes — list PCs in a lab and toggle maintenance."""

from fastapi import APIRouter, Depends, Request, HTTPException
from ..models.schemas import PCResponse, PCMaintenanceToggle
from ..models.enums import UserRole, PCState
from ..database import get_pool
from ..auth.dependencies import get_current_user, require_role

router = APIRouter(tags=["pcs"])


@router.get("/labs/{lab_id}/pcs", response_model=list[PCResponse])
async def get_pcs_in_lab(
    lab_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """List all PCs in a lab, merging DB data with live state from PCStateManager."""
    pool = request.app.state.db_pool
    state_manager = request.app.state.pc_state_manager

    async with pool.acquire() as conn:
        lab = await conn.fetchrow("SELECT lab_id FROM labs WHERE lab_id = $1", lab_id)
        if not lab:
            raise HTTPException(status_code=404, detail="Lab not found")

        rows = await conn.fetch(
            """SELECT pc_id, lab_id, current_state, is_maintenance,
                      last_heartbeat_at, installed_software
               FROM pcs WHERE lab_id = $1""",
            lab_id,
        )

    result = []
    for row in rows:
        pc_id = row["pc_id"]
        live = await state_manager.get_state(pc_id)

        if live:
            result.append(PCResponse(
                pc_id=pc_id,
                lab_id=row["lab_id"],
                current_state=live.current_state,
                is_maintenance=(live.current_state == PCState.MAINTENANCE),
                last_heartbeat_at=live.last_heartbeat_at,
                cpu_percent=live.cpu_percent,
                idle_seconds=live.idle_seconds,
                session_active=live.session_active,
                screen_locked=live.screen_locked,
            ))
        else:
            result.append(PCResponse(
                pc_id=pc_id,
                lab_id=row["lab_id"],
                current_state=PCState(row["current_state"]),
                is_maintenance=row["is_maintenance"],
                last_heartbeat_at=row["last_heartbeat_at"],
            ))

    return result


@router.put(
    "/pcs/{pc_id}/maintenance",
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.PROFESSOR))],
)
async def toggle_maintenance(
    pc_id: str,
    toggle: PCMaintenanceToggle,
    request: Request,
):
    """Toggle maintenance mode on a PC (admin/professor only)."""
    pool = request.app.state.db_pool
    state_manager = request.app.state.pc_state_manager

    async with pool.acquire() as conn:
        pc = await conn.fetchrow("SELECT pc_id FROM pcs WHERE pc_id = $1", pc_id)
        if not pc:
            raise HTTPException(status_code=404, detail="PC not found")

        transition = await state_manager.set_maintenance(pc_id, toggle.is_maintenance)

        # Update DB
        await conn.execute(
            "UPDATE pcs SET is_maintenance = $1, current_state = $2 WHERE pc_id = $3",
            toggle.is_maintenance,
            PCState.MAINTENANCE.value if toggle.is_maintenance else PCState.AVAILABLE.value,
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

    return {"message": "Maintenance mode updated successfully"}
