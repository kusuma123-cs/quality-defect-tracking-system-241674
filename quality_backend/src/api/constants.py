from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """Severity levels for a defect."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DefectStatus(str, Enum):
    """Workflow status for a defect."""

    open = "open"
    investigating = "investigating"
    corrective_action = "corrective_action"
    resolved = "resolved"
    verified = "verified"
    closed = "closed"


class ActionStatus(str, Enum):
    """Status for a corrective action."""

    open = "open"
    in_progress = "in_progress"
    done = "done"
    canceled = "canceled"


# Allowed transitions for defects.
DEFECT_WORKFLOW_TRANSITIONS: dict[DefectStatus, set[DefectStatus]] = {
    DefectStatus.open: {DefectStatus.investigating, DefectStatus.closed},
    DefectStatus.investigating: {DefectStatus.corrective_action, DefectStatus.resolved, DefectStatus.closed},
    DefectStatus.corrective_action: {DefectStatus.resolved, DefectStatus.closed},
    DefectStatus.resolved: {DefectStatus.verified, DefectStatus.corrective_action, DefectStatus.closed},
    DefectStatus.verified: {DefectStatus.closed, DefectStatus.corrective_action},
    DefectStatus.closed: set(),
}


# Statuses considered "active" (not closed).
ACTIVE_DEFECT_STATUSES: set[DefectStatus] = {
    DefectStatus.open,
    DefectStatus.investigating,
    DefectStatus.corrective_action,
    DefectStatus.resolved,
    DefectStatus.verified,
}
