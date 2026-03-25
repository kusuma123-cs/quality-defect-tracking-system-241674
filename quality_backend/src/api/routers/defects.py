from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile

from src.api.constants import DefectStatus, Severity
from src.api.db import db_session
from src.api.images import save_base64_image, save_multipart_image
from src.api.models import (
    APIMessage,
    Defect,
    DefectCreate,
    DefectSearchResponse,
    DefectUpdate,
    ImageMeta,
    ImageUploadBase64Request,
)
from src.api.repository import (
    create_defect,
    delete_defect,
    get_defect,
    insert_image_record,
    list_defects,
    update_defect,
)
from src.api.workflow import validate_defect_transition, validate_root_cause_for_status

router = APIRouter(prefix="/defects", tags=["defects"])


def _defect_row_to_model(row: dict) -> Defect:
    images = []
    for img in row.get("images", []) or []:
        images.append(
            ImageMeta(
                id=int(img["id"]),
                defect_id=int(img["defect_id"]),
                file_name=img.get("file_name"),
                content_type=img["content_type"],
                url=f"/images/{int(img['id'])}",
                created_at=datetime.fromisoformat(img["created_at"].replace("Z", "+00:00")),
            )
        )
    return Defect(
        id=int(row["id"]),
        title=row["title"],
        description=row["description"],
        severity=Severity(row["severity"]),
        status=DefectStatus(row["status"]),
        area=row.get("area"),
        location=row.get("location"),
        reported_by=row.get("reported_by"),
        assigned_to=row.get("assigned_to"),
        root_cause=row.get("root_cause"),
        due_date=row.get("due_date"),
        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
        images=images,
        actions_open=int(row.get("actions_open", 0) or 0),
        actions_total=int(row.get("actions_total", 0) or 0),
    )


@router.get(
    "",
    response_model=DefectSearchResponse,
    summary="List/search defects",
    description="List defects with optional search/filter/sort and pagination.",
    operation_id="list_defects",
)
# PUBLIC_INTERFACE
def list_defects_endpoint(
    q: Optional[str] = Query(None, description="Search query across title/description/root_cause"),
    status: Optional[DefectStatus] = Query(None, description="Filter by defect status"),
    severity: Optional[Severity] = Query(None, description="Filter by severity"),
    limit: int = Query(25, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    sort: str = Query("updated_at", description="Sort key: created_at, updated_at, due_date, severity, status"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    conn=Depends(db_session),
):
    rows, total = list_defects(conn, q=q, status=status, severity=severity, limit=limit, offset=offset, sort=sort, order=order)
    # hydrate images + counts per defect (N+1 but OK for small SQLite use; can optimize later)
    items = [_defect_row_to_model(get_defect(conn, int(r["id"]))) for r in rows]
    return DefectSearchResponse(items=items, total=total, limit=limit, offset=offset, sort=sort, order=order)


@router.post(
    "",
    response_model=Defect,
    summary="Create defect",
    description="Create a new defect. root_cause is required if status is resolved/verified/closed.",
    operation_id="create_defect",
)
# PUBLIC_INTERFACE
def create_defect_endpoint(payload: DefectCreate, conn=Depends(db_session)):
    validate_root_cause_for_status(status_value=payload.status, root_cause=payload.root_cause)
    defect_id = create_defect(
        conn,
        payload={
            "title": payload.title,
            "description": payload.description,
            "severity": payload.severity.value,
            "status": payload.status.value,
            "area": payload.area,
            "location": payload.location,
            "reported_by": payload.reported_by,
            "assigned_to": payload.assigned_to,
            "root_cause": payload.root_cause,
            "due_date": payload.due_date.isoformat() if payload.due_date else None,
        },
    )
    return _defect_row_to_model(get_defect(conn, defect_id))


@router.get(
    "/{defect_id}",
    response_model=Defect,
    summary="Get defect",
    description="Fetch a defect by ID including image metadata and action counts.",
    operation_id="get_defect",
)
# PUBLIC_INTERFACE
def get_defect_endpoint(defect_id: int, conn=Depends(db_session)):
    return _defect_row_to_model(get_defect(conn, defect_id))


@router.patch(
    "/{defect_id}",
    response_model=Defect,
    summary="Update defect",
    description="Update defect fields. Enforces workflow transitions and root-cause requirement on status changes.",
    operation_id="update_defect",
)
# PUBLIC_INTERFACE
def update_defect_endpoint(defect_id: int, payload: DefectUpdate, conn=Depends(db_session)):
    current = get_defect(conn, defect_id)
    current_status = DefectStatus(current["status"])

    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        new_status = updates["status"]
        root_cause = updates.get("root_cause", current.get("root_cause"))
        validate_defect_transition(current_status=current_status, new_status=new_status, root_cause=root_cause)
        updates["status"] = new_status.value

    if "severity" in updates and updates["severity"] is not None:
        updates["severity"] = updates["severity"].value

    if "due_date" in updates and updates["due_date"] is not None:
        updates["due_date"] = updates["due_date"].isoformat()

    # If root_cause explicitly updated without status change, ensure still valid for current status
    if "root_cause" in updates and "status" not in updates:
        validate_root_cause_for_status(status_value=current_status, root_cause=updates.get("root_cause"))

    update_defect(conn, defect_id, updates)
    return _defect_row_to_model(get_defect(conn, defect_id))


@router.delete(
    "/{defect_id}",
    response_model=APIMessage,
    summary="Delete defect",
    description="Delete a defect (cascades to actions/images).",
    operation_id="delete_defect",
)
# PUBLIC_INTERFACE
def delete_defect_endpoint(defect_id: int, conn=Depends(db_session)):
    delete_defect(conn, defect_id)
    return APIMessage(message="Deleted")


@router.post(
    "/{defect_id}/images/base64",
    response_model=ImageMeta,
    summary="Upload defect image (base64)",
    description="Upload an image for a defect using base64 payload.",
    operation_id="upload_defect_image_base64",
)
# PUBLIC_INTERFACE
def upload_defect_image_base64_endpoint(defect_id: int, payload: ImageUploadBase64Request, conn=Depends(db_session)):
    storage_path, created_at = save_base64_image(
        defect_id=defect_id, file_name=payload.file_name, content_type=payload.content_type, data_base64=payload.data_base64
    )
    image_id = insert_image_record(
        conn,
        defect_id=defect_id,
        file_name=payload.file_name,
        content_type=payload.content_type,
        storage_path=storage_path,
        created_at=created_at,
    )
    return ImageMeta(
        id=image_id,
        defect_id=defect_id,
        file_name=payload.file_name,
        content_type=payload.content_type,
        url=f"/images/{image_id}",
        created_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
    )


@router.post(
    "/{defect_id}/images",
    response_model=ImageMeta,
    summary="Upload defect image (multipart)",
    description="Upload an image for a defect using multipart/form-data file upload.",
    operation_id="upload_defect_image_multipart",
)
# PUBLIC_INTERFACE
async def upload_defect_image_multipart_endpoint(
    defect_id: int, file: UploadFile = File(..., description="Image file"), conn=Depends(db_session)
):
    storage_path, created_at, content_type, file_name = await save_multipart_image(defect_id=defect_id, upload=file)
    image_id = insert_image_record(
        conn,
        defect_id=defect_id,
        file_name=file_name,
        content_type=content_type,
        storage_path=storage_path,
        created_at=created_at,
    )
    return ImageMeta(
        id=image_id,
        defect_id=defect_id,
        file_name=file_name,
        content_type=content_type,
        url=f"/images/{image_id}",
        created_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
    )
