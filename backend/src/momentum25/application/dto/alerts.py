"""Daily alert requests and responses (FR-22, M15)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from momentum25.application.dto.user_documents import Identifier, Symbol
from momentum25.domain.entities.alert import (
    Alert,
    AlertCondition,
    AlertInterval,
    AlertSource,
    AlertStatus,
    DrawingAlert,
)

# The column is Numeric(18, 4): at most 14 digits before the point and 4 after.
Threshold = Annotated[Decimal, Field(max_digits=18, decimal_places=4, allow_inf_nan=False)]


class CreateAlertRequest(BaseModel):
    """A new alert on one value of a symbol's chart series."""

    model_config = ConfigDict(extra="forbid")

    symbol: Symbol
    source: AlertSource
    interval: AlertInterval = "1D"
    condition: AlertCondition
    threshold: Threshold
    drawing_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_drawing_rule(self) -> CreateAlertRequest:
        """Drawing rules are bounded daily price rules; zones require a drawing."""
        if self.drawing_id is not None:
            if self.source != "close" or self.interval != "1D":
                raise ValueError("Drawing alerts require daily close prices")
            if self.condition not in {
                "crosses_above",
                "crosses_below",
                "enters_zone",
                "leaves_zone",
            }:
                raise ValueError("Drawing alerts require a crossing, entry or exit condition")
        elif self.condition in {"enters_zone", "leaves_zone"}:
            raise ValueError("Zone conditions require a saved rectangle drawing")
        return self


class EditAlertRequest(CreateAlertRequest):
    """Replace an armed rule only if its revision still matches."""

    expected_revision: int = Field(ge=1)


class DrawingAnchorDTO(BaseModel):
    """One traded-price anchor in the captured drawing."""

    date: date
    price: Decimal


class DrawingAlertDTO(BaseModel):
    """The immutable drawing snapshot used by an armed or triggered rule."""

    id: str
    kind: str
    points: list[DrawingAnchorDTO]
    revision: int

    @classmethod
    def of(cls, drawing: DrawingAlert) -> DrawingAlertDTO:
        """Convert a domain snapshot for API output."""
        return cls(
            id=drawing.id,
            kind=drawing.kind,
            revision=drawing.revision,
            points=[DrawingAnchorDTO(date=p.date, price=p.price) for p in drawing.points],
        )


class AlertDTO(BaseModel):
    """One alert and, once it fired, the bar that fired it."""

    id: int
    symbol: str
    source: AlertSource
    interval: AlertInterval
    condition: AlertCondition
    threshold: Decimal
    armed_after: date = Field(description="Only complete bars after this date count.")
    status: AlertStatus
    triggered_on: date | None
    trigger_value: Decimal | None
    data_version: str | None = Field(description="The data the firing value came from.")
    seen: bool
    created_at: datetime | None
    revision: int
    drawing: DrawingAlertDTO | None

    @classmethod
    def of(cls, alert: Alert) -> AlertDTO:
        """Build the response from a stored alert."""
        assert alert.id is not None
        return cls(
            id=alert.id,
            symbol=alert.symbol,
            source=alert.source,
            interval=alert.interval,
            condition=alert.condition,
            threshold=alert.threshold,
            armed_after=alert.armed_after,
            status=alert.status,
            triggered_on=alert.triggered_on,
            trigger_value=alert.trigger_value,
            data_version=alert.data_version,
            seen=alert.seen,
            created_at=alert.created_at,
            revision=alert.revision,
            drawing=DrawingAlertDTO.of(alert.drawing) if alert.drawing else None,
        )


class AlertListDTO(BaseModel):
    """Every alert, fired ones first, and how many fired alerts are unseen."""

    alerts: list[AlertDTO]
    unseen: int


class AlertEvaluationDTO(BaseModel):
    """What one evaluation did."""

    evaluated: int
    fired: int
    failed: list[str] = Field(description="Symbols whose series could not be read.")
