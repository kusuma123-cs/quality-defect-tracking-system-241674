from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query

from src.api.constants import DefectStatus, Severity
from src.api.db import db_session
from src.api.models import AnalyticsResponse, DashboardCounts, OverdueAlertsResponse, TrendPoint
from src.api.repository import analytics, dashboard_counts, overdue_alerts

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/dashboard",
    response_model=DashboardCounts,
    summary="Dashboard counts",
    description="Aggregated counts for dashboard: defects by status/severity, open defects, overdue actions.",
    operation_id="get_dashboard_counts",
)
# PUBLIC_INTERFACE
def get_dashboard_counts_endpoint(conn=Depends(db_session)):
    data = dashboard_counts(conn)
    by_status = {DefectStatus(k): int(v) for k, v in data["by_status"].items()}
    by_severity = {Severity(k): int(v) for k, v in data["by_severity"].items()}
    return DashboardCounts(
        by_status=by_status,
        by_severity=by_severity,
        open_defects=int(data["open_defects"]),
        overdue_actions=int(data["overdue_actions"]),
    )


@router.get(
    "",
    response_model=AnalyticsResponse,
    summary="Analytics trends",
    description="Time-series analytics for created vs resolved defects over the last N days.",
    operation_id="get_analytics",
)
# PUBLIC_INTERFACE
def get_analytics_endpoint(range_days: int = Query(30, ge=1, le=365, description="Days of history"), conn=Depends(db_session)):
    data = analytics(conn, range_days=range_days)
    trends = [
        TrendPoint(date=date.fromisoformat(p["date"]), created=int(p["created"]), resolved=int(p["resolved"]))
        for p in data["trends"]
    ]
    return AnalyticsResponse(range_days=int(data["range_days"]), trends=trends, avg_days_to_resolve=data["avg_days_to_resolve"])


@router.get(
    "/overdue",
    response_model=OverdueAlertsResponse,
    summary="Overdue corrective action alerts",
    description="List overdue corrective actions (due_date < today and not done/canceled).",
    operation_id="get_overdue_alerts",
)
# PUBLIC_INTERFACE
def get_overdue_alerts_endpoint(limit: int = Query(50, ge=1, le=200, description="Max items"), conn=Depends(db_session)):
    items = overdue_alerts(conn, limit=limit)
    # Coerce due_date strings to date
    normalized = []
    for it in items:
        normalized.append(
            {
                **it,
                "due_date": date.fromisoformat(it["due_date"]),
            }
        )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return OverdueAlertsResponse(as_of=now, count=len(normalized), items=normalized)
