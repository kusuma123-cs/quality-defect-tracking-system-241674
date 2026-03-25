from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.api.constants import ActionStatus, DefectStatus, Severity


class APIMessage(BaseModel):
    message: str = Field(..., description="Human-readable message")


class ImageMeta(BaseModel):
    id: int = Field(..., description="Image record ID")
    defect_id: int = Field(..., description="Associated defect ID")
    file_name: Optional[str] = Field(None, description="Original file name if provided")
    content_type: str = Field(..., description="MIME type of stored file")
    url: str = Field(..., description="Absolute or relative URL to fetch the image content")
    created_at: datetime = Field(..., description="When the image was uploaded (UTC)")


class DefectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Short defect title")
    description: str = Field(..., min_length=1, description="Defect details")
    severity: Severity = Field(..., description="Severity classification")
    area: Optional[str] = Field(None, max_length=120, description="Process/product area")
    location: Optional[str] = Field(None, max_length=120, description="Physical or logical location")
    reported_by: Optional[str] = Field(None, max_length=120, description="Reporter name/email")
    assigned_to: Optional[str] = Field(None, max_length=120, description="Assignee name/email")
    due_date: Optional[date] = Field(None, description="Target resolution date")


class DefectCreate(DefectBase):
    status: DefectStatus = Field(DefectStatus.open, description="Initial workflow status")
    root_cause: Optional[str] = Field(None, description="Root cause statement (required for resolved/verified/closed)")


class DefectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Short defect title")
    description: Optional[str] = Field(None, min_length=1, description="Defect details")
    severity: Optional[Severity] = Field(None, description="Severity classification")
    status: Optional[DefectStatus] = Field(None, description="Workflow status")
    area: Optional[str] = Field(None, max_length=120, description="Process/product area")
    location: Optional[str] = Field(None, max_length=120, description="Physical or logical location")
    reported_by: Optional[str] = Field(None, max_length=120, description="Reporter name/email")
    assigned_to: Optional[str] = Field(None, max_length=120, description="Assignee name/email")
    root_cause: Optional[str] = Field(None, description="Root cause statement")
    due_date: Optional[date] = Field(None, description="Target resolution date")


class Defect(DefectBase):
    id: int = Field(..., description="Defect ID")
    status: DefectStatus = Field(..., description="Workflow status")
    root_cause: Optional[str] = Field(None, description="Root cause statement")
    created_at: datetime = Field(..., description="Created timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last updated timestamp (UTC)")
    images: list[ImageMeta] = Field(default_factory=list, description="Associated image metadata")
    actions_open: int = Field(0, description="Number of open/in-progress actions")
    actions_total: int = Field(0, description="Number of total actions")


class CorrectiveActionBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Action title")
    description: Optional[str] = Field(None, description="Action details")
    owner: Optional[str] = Field(None, max_length=120, description="Action owner")
    status: ActionStatus = Field(ActionStatus.open, description="Action status")
    due_date: Optional[date] = Field(None, description="Action due date")


class CorrectiveActionCreate(CorrectiveActionBase):
    defect_id: int = Field(..., description="Associated defect ID")


class CorrectiveActionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Action title")
    description: Optional[str] = Field(None, description="Action details")
    owner: Optional[str] = Field(None, max_length=120, description="Action owner")
    status: Optional[ActionStatus] = Field(None, description="Action status")
    due_date: Optional[date] = Field(None, description="Action due date")
    completed_at: Optional[datetime] = Field(None, description="When marked done (UTC)")


class CorrectiveAction(CorrectiveActionBase):
    id: int = Field(..., description="Action ID")
    defect_id: int = Field(..., description="Associated defect ID")
    completed_at: Optional[datetime] = Field(None, description="When marked done (UTC)")
    created_at: datetime = Field(..., description="Created timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last updated timestamp (UTC)")


class DashboardCounts(BaseModel):
    by_status: dict[DefectStatus, int] = Field(..., description="Count of defects by status")
    by_severity: dict[Severity, int] = Field(..., description="Count of defects by severity")
    open_defects: int = Field(..., description="Total active (not closed) defects")
    overdue_actions: int = Field(..., description="Number of overdue corrective actions (not done/canceled)")


class TrendPoint(BaseModel):
    date: date = Field(..., description="Date bucket")
    created: int = Field(..., description="Defects created in bucket")
    resolved: int = Field(..., description="Defects moved to resolved/verified/closed in bucket")


class AnalyticsResponse(BaseModel):
    range_days: int = Field(..., description="Number of days included")
    trends: list[TrendPoint] = Field(..., description="Time series trend points")
    avg_days_to_resolve: Optional[float] = Field(None, description="Average days from created to resolved/verified/closed")


class OverdueActionAlert(BaseModel):
    action_id: int = Field(..., description="Corrective action ID")
    defect_id: int = Field(..., description="Related defect ID")
    title: str = Field(..., description="Action title")
    owner: Optional[str] = Field(None, description="Action owner")
    due_date: date = Field(..., description="Due date")
    days_overdue: int = Field(..., description="Days past due date")
    defect_title: str = Field(..., description="Related defect title")


class OverdueAlertsResponse(BaseModel):
    as_of: datetime = Field(..., description="Time the computation was run (UTC)")
    count: int = Field(..., description="Number of overdue actions")
    items: list[OverdueActionAlert] = Field(..., description="Overdue action records")


class ImageUploadBase64Request(BaseModel):
    file_name: Optional[str] = Field(None, description="Optional original file name")
    content_type: str = Field(..., description="MIME type (e.g., image/png)")
    data_base64: str = Field(..., description="Base64-encoded file contents")


class DefectSearchResponse(BaseModel):
    items: list[Defect] = Field(..., description="Defects list")
    total: int = Field(..., description="Total matching defects")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Offset used")
    sort: Literal["created_at", "updated_at", "due_date", "severity", "status"] = Field(
        "updated_at", description="Sort key"
    )
    order: Literal["asc", "desc"] = Field("desc", description="Sort order")
