"""Daily alert endpoints (FR-22, M15). Shown in the app; no delivery outside it."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from momentum25.application.dto.alerts import (
    AlertDTO,
    AlertEvaluationDTO,
    AlertListDTO,
    CreateAlertRequest,
)
from momentum25.application.use_cases.alerts import (
    CreateAlert,
    DeleteAlert,
    EvaluateAlerts,
    ListAlerts,
    MarkAlertsSeen,
    RearmAlert,
)
from momentum25.interface.api.dependencies import (
    get_create_alert,
    get_delete_alert,
    get_evaluate_alerts,
    get_list_alerts,
    get_mark_alerts_seen,
    get_rearm_alert,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertListDTO)
async def list_alerts(use_case: Annotated[ListAlerts, Depends(get_list_alerts)]) -> AlertListDTO:
    """Return every alert, fired ones first, and the unseen count."""
    return await use_case.execute()


@router.post("", response_model=AlertDTO, status_code=201)
async def create_alert(
    request: CreateAlertRequest,
    use_case: Annotated[CreateAlert, Depends(get_create_alert)],
) -> AlertDTO:
    """Create an alert that watches complete bars after the last stored session."""
    return await use_case.execute(request)


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: int, use_case: Annotated[DeleteAlert, Depends(get_delete_alert)]
) -> Response:
    """Delete an alert."""
    await use_case.execute(alert_id)
    return Response(status_code=204)


@router.post("/{alert_id}/rearm", response_model=AlertDTO)
async def rearm_alert(
    alert_id: int, use_case: Annotated[RearmAlert, Depends(get_rearm_alert)]
) -> AlertDTO:
    """Make a fired alert watch again, from bars after the last stored session."""
    return await use_case.execute(alert_id)


@router.post("/seen", status_code=204)
async def mark_alerts_seen(
    use_case: Annotated[MarkAlertsSeen, Depends(get_mark_alerts_seen)],
) -> Response:
    """Mark every fired alert seen."""
    await use_case.execute()
    return Response(status_code=204)


@router.post("/evaluate", response_model=AlertEvaluationDTO)
async def evaluate_alerts(
    use_case: Annotated[EvaluateAlerts, Depends(get_evaluate_alerts)],
) -> AlertEvaluationDTO:
    """Check every active alert now. The daily job runs the same check after each sync."""
    return await use_case.execute()
