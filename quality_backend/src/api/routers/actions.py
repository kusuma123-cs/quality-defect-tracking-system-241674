from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.constants import ActionStatus
from src.api.db import db_session
from src.api.models import APIMessage, CorrectiveAction, CorrectiveActionCreate, CorrectiveActionUpdate
from src.api.repository import create_action, delete_action, list_actions, update_action
from src.api.utils import utc_now_iso

router = APIRouter(prefix="/actions", tags=["actions"])


def _action_row_to_model(row: dict) -> CorrectiveAction:
    completed_at = row.get("completed_at")
    return CorrectiveAction(
        id=int(row["id"]),
        defect_id=int(row["defect_id"]),
        title=row["title"],
        description=row.get("description"),
        owner=row.get("owner"),
        status=ActionStatus(row["status"]),
        due_date=row.get("due_date"),
        completed_at=datetime.fromisoformat(completed_at.replace("Z", "+00:00")) if completed_at else None,
        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
    )


@router.get(
    "",
    response_model=list[CorrectiveAction],
    summary="List corrective actions",
    description="List corrective actions, optionally filtered by defect_id. By default excludes done/canceled unless include_done=true.",
    operation_id="list_actions",
)
# PUBLIC_INTERFACE
def list_actions_endpoint(
    defect_id: Optional[int] = Query(None, description="Filter by defect ID"),
    include_done: bool = Query(False, description="Include done/canceled actions"),
    conn=Depends(db_session),
):
    rows = list_actions(conn, defect_id=defect_id, include_done=include_done)
    return [_action_row_to_model(r) for r in rows]


@router.post(
    "",
    response_model=CorrectiveAction,
    summary="Create corrective action",
    description="Create a corrective action for a defect.",
    operation_id="create_action",
)
# PUBLIC_INTERFACE
def create_action_endpoint(payload: CorrectiveActionCreate, conn=Depends(db_session)):
    action_id = create_action(
        conn,
        payload={
            "defect_id": payload.defect_id,
            "title": payload.title,
            "description": payload.description,
            "owner": payload.owner,
            "status": payload.status.value,
            "due_date": payload.due_date.isoformat() if payload.due_date else None,
            "completed_at": None,
        },
    )
    row = conn.execute("SELECT * FROM corrective_actions WHERE id = ?", (action_id,)).fetchone()
    return _action_row_to_model(dict(row))


@router.patch(
    "/{action_id}",
    response_model=CorrectiveAction,
    summary="Update corrective action",
    description="Update action fields. If status becomes done, completed_at is set if not provided.",
    operation_id="update_action",
)
# PUBLIC_INTERFACE
def update_action_endpoint(action_id: int, payload: CorrectiveActionUpdate, conn=Depends(db_session)):
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] is not None:
        updates["status"] = updates["status"].value
        if updates["status"] == ActionStatus.done.value and "completed_at" not in updates:
            updates["completed_at"] = utc_now_iso()
        if updates["status"] != ActionStatus.done.value and "completed_at" in updates and updates["completed_at"] is None:
            # allow clearing completed_at if reopening
            pass

    if "due_date" in updates and updates["due_date"] is not None:
        updates["due_date"] = updates["due_date"].isoformat()

    if "completed_at" in updates and isinstance(updates["completed_at"], datetime):
        updates["completed_at"] = updates["completed_at"].astimezone(timezone.utc).replace(microsecond=0).isoformat()

    update_action(conn, action_id, updates)
    row = conn.execute("SELECT * FROM corrective_actions WHERE id = ?", (action_id,)).fetchone()
    return _action_row_to_model(dict(row))


@router.delete(
    "/{action_id}",
    response_model=APIMessage,
    summary="Delete corrective action",
    description="Delete a corrective action.",
    operation_id="delete_action",
)
# PUBLIC_INTERFACE
def delete_action_endpoint(action_id: int, conn=Depends(db_session)):
    delete_action(conn, action_id)
    return APIMessage(message="Deleted")
