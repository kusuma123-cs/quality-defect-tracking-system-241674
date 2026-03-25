from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from src.api.db import db_session
from src.api.repository import get_image_record

router = APIRouter(prefix="/images", tags=["images"])


@router.get(
    "/{image_id}",
    summary="Fetch defect image bytes",
    description="Serves a previously uploaded defect image by image record ID.",
    operation_id="get_image",
)
# PUBLIC_INTERFACE
def get_image_endpoint(image_id: int, conn=Depends(db_session)):
    rec = get_image_record(conn, image_id)
    path = Path(rec["storage_path"])
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found on disk")
    return FileResponse(path=str(path), media_type=rec["content_type"], filename=rec.get("file_name") or path.name)
