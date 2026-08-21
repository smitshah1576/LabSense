"""Admin routes — register and deregister labs and PCs (admin-only).

PC IDs are auto-generated using the convention <lab_id padded to 3 digits><sequence 2 digits>.
For example, lab "408" gets PCs: 40801, 40802, 40803, …
"""

from fastapi import APIRouter, Depends, Request, HTTPException

from ..models.schemas import LabCreate, LabResponse, PCCreate, PCCreateResponse
from ..models.enums import UserRole
from ..auth.dependencies import require_role

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


# ─── Lab CRUD ────────────────────────────────────────────────────────────────


@router.post("/labs", response_model=LabResponse, status_code=201)
async def create_lab(lab: LabCreate, request: Request):
    """Register a new lab (admin only)."""
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT lab_id FROM labs WHERE lab_id = $1", lab.lab_id
        )
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Lab '{lab.lab_id}' already exists"
            )

        await conn.execute(
            """INSERT INTO labs (lab_id, lab_name, operating_start_time, operating_end_time)
               VALUES ($1, $2, $3, $4)""",
            lab.lab_id,
            lab.lab_name,
            lab.operating_start_time,
            lab.operating_end_time,
        )

    return LabResponse(
        lab_id=lab.lab_id,
        lab_name=lab.lab_name,
        operating_start_time=lab.operating_start_time,
        operating_end_time=lab.operating_end_time,
    )


@router.delete("/labs/{lab_id}")
async def delete_lab(lab_id: str, request: Request):
    """Delete a lab and all its associated PCs, timetable entries, etc. (admin only).

    Cascading deletes are handled in application code to accommodate databases
    created before ON DELETE CASCADE was added to the FK constraints.
    """
    pool = request.app.state.db_pool
    state_manager = request.app.state.pc_state_manager

    async with pool.acquire() as conn:
        lab = await conn.fetchrow(
            "SELECT lab_id FROM labs WHERE lab_id = $1", lab_id
        )
        if not lab:
            raise HTTPException(
                status_code=404, detail=f"Lab '{lab_id}' not found"
            )

        # Collect PC IDs for in-memory cleanup
        pcs = await conn.fetch(
            "SELECT pc_id FROM pcs WHERE lab_id = $1", lab_id
        )
        pc_ids = [row["pc_id"] for row in pcs]

        # Delete in correct FK order to avoid constraint violations
        for pid in pc_ids:
            await conn.execute(
                "DELETE FROM state_transitions WHERE pc_id = $1", pid
            )
            await conn.execute(
                "DELETE FROM damage_reports WHERE pc_id = $1", pid
            )

        await conn.execute("DELETE FROM pcs WHERE lab_id = $1", lab_id)

        # master_timetables → slot_cancellations cascade is handled by the DB
        await conn.execute(
            "DELETE FROM master_timetables WHERE lab_id = $1", lab_id
        )

        await conn.execute("DELETE FROM labs WHERE lab_id = $1", lab_id)

    # Clean up in-memory live state
    for pid in pc_ids:
        await state_manager.remove_pc(pid)

    return {
        "message": f"Lab '{lab_id}' and {len(pc_ids)} PC(s) deleted successfully"
    }


# ─── PC CRUD ─────────────────────────────────────────────────────────────────


@router.post("/pcs", response_model=PCCreateResponse, status_code=201)
async def create_pc(pc: PCCreate, request: Request):
    """Register a new PC in a lab (admin only).

    The pc_id is auto-generated: <lab_id padded to 3 digits><next 2-digit sequence>.
    For lab '408', the first PC gets id '40801', the second '40802', etc.
    Maximum 99 PCs per lab.
    """
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        # Validate lab exists
        lab = await conn.fetchrow(
            "SELECT lab_id FROM labs WHERE lab_id = $1", pc.lab_id
        )
        if not lab:
            raise HTTPException(
                status_code=404, detail=f"Lab '{pc.lab_id}' not found"
            )

        # Auto-generate PC ID using the naming convention
        lab_prefix = pc.lab_id.zfill(3)

        # Find the highest existing sequence number for this lab
        existing_pcs = await conn.fetch(
            "SELECT pc_id FROM pcs WHERE lab_id = $1", pc.lab_id
        )

        max_seq = 0
        for row in existing_pcs:
            pid = row["pc_id"]
            # Only consider IDs that follow the convention for this lab
            if pid.startswith(lab_prefix) and len(pid) == len(lab_prefix) + 2:
                try:
                    seq = int(pid[len(lab_prefix):])
                    max_seq = max(max_seq, seq)
                except ValueError:
                    pass

        next_seq = max_seq + 1
        if next_seq > 99:
            raise HTTPException(
                status_code=400, detail="Maximum 99 PCs per lab reached"
            )

        pc_id = f"{lab_prefix}{str(next_seq).zfill(2)}"

        # Safety check against collision
        collision = await conn.fetchrow(
            "SELECT pc_id FROM pcs WHERE pc_id = $1", pc_id
        )
        if collision:
            raise HTTPException(
                status_code=409,
                detail=f"Generated PC ID '{pc_id}' already exists",
            )

        await conn.execute(
            "INSERT INTO pcs (pc_id, lab_id, current_state) VALUES ($1, $2, 'AVAILABLE')",
            pc_id,
            pc.lab_id,
        )

    return PCCreateResponse(
        pc_id=pc_id,
        lab_id=pc.lab_id,
        message=f"PC '{pc_id}' registered in lab '{pc.lab_id}'",
    )


@router.delete("/pcs/{pc_id}")
async def delete_pc(pc_id: str, request: Request):
    """Deregister a single PC (admin only).

    Removes the PC and all related state transitions and damage reports.
    """
    pool = request.app.state.db_pool
    state_manager = request.app.state.pc_state_manager

    async with pool.acquire() as conn:
        pc = await conn.fetchrow(
            "SELECT pc_id FROM pcs WHERE pc_id = $1", pc_id
        )
        if not pc:
            raise HTTPException(
                status_code=404, detail=f"PC '{pc_id}' not found"
            )

        # Delete in correct FK order
        await conn.execute(
            "DELETE FROM state_transitions WHERE pc_id = $1", pc_id
        )
        await conn.execute(
            "DELETE FROM damage_reports WHERE pc_id = $1", pc_id
        )
        await conn.execute("DELETE FROM pcs WHERE pc_id = $1", pc_id)

    # Clean up in-memory live state
    await state_manager.remove_pc(pc_id)

    return {"message": f"PC '{pc_id}' deleted successfully"}
