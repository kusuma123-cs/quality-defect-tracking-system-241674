from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.db import get_db_path, init_db
from src.api.routers.actions import router as actions_router
from src.api.routers.analytics import router as analytics_router
from src.api.routers.defects import router as defects_router
from src.api.routers.images import router as images_router

openapi_tags: list[dict[str, Any]] = [
    {"name": "defects", "description": "Defect CRUD, workflow, and image upload endpoints."},
    {"name": "actions", "description": "Corrective action CRUD endpoints."},
    {"name": "analytics", "description": "Dashboard aggregation, trends, and overdue alerts."},
    {"name": "images", "description": "Serve stored images by ID."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize application resources (SQLite DB connection) and cleanly close them on shutdown.
    """
    init_db()
    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    app.state.db = conn
    try:
        yield
    finally:
        conn.close()


app = FastAPI(
    title="Quality Defect Tracking API",
    description=(
        "FastAPI backend for logging, tracking, and analyzing quality defects and root causes. "
        "Includes workflow enforcement, corrective actions, dashboard analytics, overdue alerts, and image upload/serving."
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

# CORS
# Environment variables (expected from orchestrator via .env):
#  - NEXT_PUBLIC_FRONTEND_URL: Recommended for production
#  - NEXT_PUBLIC_BACKEND_URL: Optional (self) or additional allowed origin
frontend_url = os.getenv("NEXT_PUBLIC_FRONTEND_URL")
backend_url = os.getenv("NEXT_PUBLIC_BACKEND_URL")

allow_origins = [o for o in [frontend_url, backend_url] if o]
if not allow_origins:
    # Safe fallback for dev templates; for production you should set NEXT_PUBLIC_FRONTEND_URL
    allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    summary="Health check",
    description="Simple health check endpoint.",
    tags=["analytics"],
)
# PUBLIC_INTERFACE
def health_check():
    """Health check endpoint.

    Returns:
        JSON message confirming the server is running.
    """
    return {"message": "Healthy"}


@app.get(
    "/docs/help",
    summary="API usage help",
    description="Notes on using this API including image upload endpoints.",
    tags=["analytics"],
)
# PUBLIC_INTERFACE
def docs_help():
    """Documentation helper endpoint providing quick usage hints."""
    return {
        "images": {
            "upload_base64": {
                "method": "POST",
                "path": "/defects/{defect_id}/images/base64",
                "body": {"file_name": "optional.png", "content_type": "image/png", "data_base64": "<base64>"},
            },
            "upload_multipart": {
                "method": "POST",
                "path": "/defects/{defect_id}/images",
                "form_field": "file",
            },
            "fetch": {"method": "GET", "path": "/images/{image_id}"},
        },
        "workflow": {
            "defect_statuses": ["open", "investigating", "corrective_action", "resolved", "verified", "closed"],
            "root_cause_required_when_status_in": ["resolved", "verified", "closed"],
        },
    }


# Routers
app.include_router(defects_router)
app.include_router(actions_router)
app.include_router(analytics_router)
app.include_router(images_router)
