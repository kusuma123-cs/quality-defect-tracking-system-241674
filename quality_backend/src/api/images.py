from __future__ import annotations

import base64
import os
import re
import secrets
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile, status

from src.api.db import get_db_path
from src.api.utils import utc_now_iso


def _storage_root() -> Path:
    configured = os.getenv("QUALITY_IMAGE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    # Store alongside DB under ../data/images
    return get_db_path().parent / "images"


def _safe_filename(name: str) -> str:
    # Keep alnum + selected punctuation
    name = name.strip().replace("\\", "_").replace("/", "_")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:200] if name else "image"


def _new_object_name(original_name: Optional[str], content_type: str) -> str:
    ext = ""
    if original_name and "." in original_name:
        ext = "." + original_name.rsplit(".", 1)[-1][:10]
    elif content_type in ("image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"):
        ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
        ext = ext_map.get(content_type, "")
    token = secrets.token_urlsafe(16)
    base = _safe_filename((original_name or "image").rsplit(".", 1)[0])
    return f"{base}_{token}{ext}"


def _decode_base64(data: str) -> bytes:
    # Accept "data:image/png;base64,...." as well
    if "," in data and data.strip().lower().startswith("data:"):
        data = data.split(",", 1)[1]
    try:
        return base64.b64decode(data, validate=True)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 data") from e


# PUBLIC_INTERFACE
def save_base64_image(*, defect_id: int, file_name: Optional[str], content_type: str, data_base64: str) -> Tuple[str, str]:
    """Save a base64-encoded image to disk and return (storage_path, created_at_iso)."""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image/* content_type is supported")

    payload = _decode_base64(data_base64)
    if len(payload) > 8 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large (max 8MB)")

    root = _storage_root()
    defect_dir = root / str(defect_id)
    defect_dir.mkdir(parents=True, exist_ok=True)

    obj_name = _new_object_name(file_name, content_type)
    path = defect_dir / obj_name
    path.write_bytes(payload)
    return str(path), utc_now_iso()


# PUBLIC_INTERFACE
async def save_multipart_image(*, defect_id: int, upload: UploadFile) -> Tuple[str, str, str, Optional[str]]:
    """Save a multipart UploadFile to disk and return (storage_path, created_at_iso, content_type, file_name)."""
    content_type = upload.content_type or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image uploads are supported")

    data = await upload.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large (max 8MB)")

    root = _storage_root()
    defect_dir = root / str(defect_id)
    defect_dir.mkdir(parents=True, exist_ok=True)

    file_name = upload.filename
    obj_name = _new_object_name(file_name, content_type)
    path = defect_dir / obj_name
    path.write_bytes(data)
    return str(path), utc_now_iso(), content_type, file_name
