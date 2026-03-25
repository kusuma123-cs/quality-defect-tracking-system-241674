from __future__ import annotations

from fastapi import HTTPException, status

from src.api.constants import DEFECT_WORKFLOW_TRANSITIONS, DefectStatus


def _root_cause_required(for_status: DefectStatus) -> bool:
    return for_status in {DefectStatus.resolved, DefectStatus.verified, DefectStatus.closed}


# PUBLIC_INTERFACE
def validate_defect_transition(
    *, current_status: DefectStatus, new_status: DefectStatus, root_cause: str | None
) -> None:
    """Validate defect status workflow transitions and root-cause requirements."""
    if new_status == current_status:
        return

    allowed = DEFECT_WORKFLOW_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status transition: {current_status.value} -> {new_status.value}",
        )

    if _root_cause_required(new_status) and (root_cause is None or root_cause.strip() == ""):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"root_cause is required when setting status to '{new_status.value}'",
        )


# PUBLIC_INTERFACE
def validate_root_cause_for_status(*, status_value: DefectStatus, root_cause: str | None) -> None:
    """Validate that root_cause is present when a defect is already in a status that requires it."""
    if _root_cause_required(status_value) and (root_cause is None or root_cause.strip() == ""):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"root_cause is required when status is '{status_value.value}'",
        )
