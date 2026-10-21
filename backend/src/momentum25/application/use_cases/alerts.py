"""Daily alert use cases (FR-22, M15).

Evaluation reads each alert's values through the same use cases the chart
calls, so the chart and the alert see one series (NFR-1a).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import cast

from structlog import get_logger

from momentum25.application.dto.alerts import (
    AlertDTO,
    AlertEvaluationDTO,
    AlertListDTO,
    CreateAlertRequest,
    EditAlertRequest,
)
from momentum25.application.dto.market_data import AdjustmentStepDTO, SecurityOHLCVDTO
from momentum25.application.dto.user_documents import SymbolDrawingsV1
from momentum25.application.use_cases.securities import GetSecurityOHLCV
from momentum25.application.use_cases.stocks import GetIndicatorSeries
from momentum25.domain.entities.alert import (
    LINE_KINDS,
    PRICE_SCALED,
    Alert,
    AlertInterval,
    DrawingAlert,
    DrawingAnchor,
    DrawingKind,
    LineKind,
    SeriesPoint,
    chart_threshold,
    first_firing,
    first_line_firing,
    first_zone_firing,
    line_levels,
)
from momentum25.domain.errors import ConflictError, NotFoundError, ValidationError
from momentum25.domain.ports.repositories import (
    AlertRepository,
    OHLCVRepository,
    SecurityRepository,
    UserDocumentRepository,
)

_logger = get_logger("alerts")


async def _last_session(ohlcv: OHLCVRepository) -> date:
    return await ohlcv.latest_date() or date.today()


def _factor_at(steps: Sequence[AdjustmentStepDTO], day: date) -> Decimal:
    step = next((s for s in steps if s.until >= day), steps[-1] if steps else None)
    return step.factor if step else Decimal("1")


def _line_levels(drawing: DrawingAlert, prices: SecurityOHLCVDTO) -> list[Decimal | None]:
    """The captured line's value on each stored session, each anchor adjusted at its own date."""
    first, second = (
        (p.date, p.price * _factor_at(prices.adjustments, p.date)) for p in drawing.points
    )
    return line_levels(cast(LineKind, drawing.kind), (first, second), [b.date for b in prices.bars])


def _drawing_bounds(
    drawing: DrawingAlert, steps: Sequence[AdjustmentStepDTO]
) -> tuple[Decimal, Decimal | None]:
    bounds = [p.price * _factor_at(steps, p.date) for p in drawing.points]
    return min(bounds), max(bounds) if drawing.kind == "rectangle" else None


class ListAlerts:
    """Return every alert and the unseen count."""

    def __init__(self, alerts: AlertRepository) -> None:
        """Wire the use case with its collaborators."""
        self._alerts = alerts

    async def execute(self) -> AlertListDTO:
        """Fired alerts first, newest firing first."""
        alerts = await self._alerts.list_all()
        return AlertListDTO(
            alerts=[AlertDTO.of(a) for a in alerts],
            unseen=sum(1 for a in alerts if a.status == "triggered" and not a.seen),
        )


class CreateAlert:
    """Store a new alert that watches bars after the last stored session."""

    def __init__(
        self,
        securities: SecurityRepository,
        ohlcv: OHLCVRepository,
        alerts: AlertRepository,
        documents: UserDocumentRepository | None = None,
        prices: GetSecurityOHLCV | None = None,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._ohlcv = ohlcv
        self._alerts = alerts
        self._documents = documents
        self._prices = prices

    async def execute(self, request: CreateAlertRequest) -> AlertDTO:
        """Raise :class:`NotFoundError` for an unknown symbol."""
        security_id, alert = await self.build(request)
        return AlertDTO.of(await self._alerts.add(security_id, alert))

    async def build(self, request: CreateAlertRequest) -> tuple[int, Alert]:
        """Validate and snapshot one rule, shared by creation and active editing."""
        security = await self._securities.get_by_symbol(request.symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {request.symbol}")
        prices: SecurityOHLCVDTO | None = None
        if request.expected_data_version is not None:
            if self._prices is None:
                raise ValidationError("Current chart prices are unavailable")
            prices = await self._prices.execute(str(security.symbol), interval="1D")
            if prices.data_version != request.expected_data_version:
                raise ConflictError("Chart data changed; refresh prices before arming")
        drawing: DrawingAlert | None = None
        if request.drawing_id is not None:
            if self._documents is None:
                raise ValidationError("Saved drawings are unavailable")
            doc = await self._documents.get("symbol_drawings", str(security.symbol))
            body = SymbolDrawingsV1.model_validate(doc.body) if doc else None
            found = (
                next((d for d in body.drawings if d.id == request.drawing_id), None)
                if body
                else None
            )
            if found is None or doc is None:
                raise NotFoundError("Save the drawing before linking an alert")
            if (
                request.expected_drawing_revision is not None
                and doc.revision != request.expected_drawing_revision
            ):
                raise ConflictError("Drawing changed; reload its saved revision before arming")
            if found.kind not in {"horizontal", "hline", "rectangle", *LINE_KINDS}:
                raise ValidationError(
                    "Only horizontal lines, trendlines, rays, extended lines "
                    "and rectangular price zones are supported"
                )
            count = 2 if found.kind == "rectangle" or found.kind in LINE_KINDS else 1
            if len(found.points) != count:
                raise ValidationError("Drawing has invalid anchors")
            if any(p.price <= 0 or p.price >= 10**14 for p in found.points):
                raise ValidationError(
                    "Drawing alert prices must be positive and below 100 trillion"
                )
            is_zone = request.condition in {"enters_zone", "leaves_zone"}
            if (found.kind == "rectangle") != is_zone:
                raise ValidationError("Rectangles require entry or exit; lines require crossing")
            drawing = DrawingAlert(
                id=found.id,
                kind=cast(DrawingKind, found.kind),
                revision=doc.revision,
                points=tuple(DrawingAnchor(p.date, Decimal(str(p.price))) for p in found.points),
            )
            if drawing.kind == "rectangle":
                if self._prices is None:
                    raise ValidationError("Adjusted drawing prices are unavailable")
                if prices is None:
                    prices = await self._prices.execute(str(security.symbol), interval="1D")
                lower, upper = _drawing_bounds(drawing, prices.adjustments)
                if lower == upper:
                    raise ValidationError("A price zone must have distinct adjusted bounds")
            if drawing.kind in LINE_KINDS:
                if self._prices is None:
                    raise ValidationError("Adjusted drawing prices are unavailable")
                if prices is None:
                    prices = await self._prices.execute(str(security.symbol), interval="1D")
                try:
                    _line_levels(drawing, prices)
                except ValueError as exc:
                    raise ValidationError(str(exc)) from exc
        alert = Alert(
            symbol=str(security.symbol),
            source=request.source,
            interval=request.interval,
            condition=request.condition,
            threshold=(
                drawing.points[0].price.quantize(Decimal("0.0001"))
                if drawing
                else request.threshold
            ),
            armed_after=await _last_session(self._ohlcv),
            drawing=drawing,
        )
        return security.id, alert


class EditAlert:
    """Replace an armed rule with a new observation window and captured anchors."""

    def __init__(self, creator: CreateAlert, alerts: AlertRepository) -> None:
        """Use the same validation and snapshot builder as alert creation."""
        self._creator = creator
        self._alerts = alerts

    async def execute(self, alert_id: int, request: EditAlertRequest) -> AlertDTO:
        """Reject stale rules and preserve triggered evidence."""
        current = await self._alerts.get(alert_id)
        if current is None:
            raise NotFoundError(f"Alert not found: {alert_id}")
        if current.status != "active" or current.revision != request.expected_revision:
            raise ConflictError("Alert changed or has triggered; reload before editing")
        security_id, alert = await self._creator.build(request)
        return AlertDTO.of(
            await self._alerts.edit(alert_id, security_id, alert, request.expected_revision)
        )


class DeleteAlert:
    """Delete one alert."""

    def __init__(self, alerts: AlertRepository) -> None:
        """Wire the use case with its collaborators."""
        self._alerts = alerts

    async def execute(self, alert_id: int) -> None:
        """Raise :class:`NotFoundError` if it does not exist."""
        if not await self._alerts.delete(alert_id):
            raise NotFoundError(f"Alert not found: {alert_id}")


class RearmAlert:
    """Make a fired alert watch again, from bars after the last stored session."""

    def __init__(
        self, ohlcv: OHLCVRepository, alerts: AlertRepository, prices: GetSecurityOHLCV
    ) -> None:
        """Wire the use case with its collaborators."""
        self._ohlcv = ohlcv
        self._alerts = alerts
        self._prices = prices

    async def execute(self, alert_id: int) -> AlertDTO:
        """Raise :class:`NotFoundError` if it does not exist."""
        current = await self._alerts.get(alert_id)
        if current is None:
            raise NotFoundError(f"Alert not found: {alert_id}")
        armed_after = await _last_session(self._ohlcv)
        threshold = current.threshold
        if current.drawing is None and current.source in PRICE_SCALED:
            prices = await self._prices.execute(current.symbol, interval="1D")
            threshold = (
                threshold
                * _factor_at(prices.adjustments, current.armed_after)
                / _factor_at(prices.adjustments, armed_after)
            ).quantize(Decimal("0.0001"))
        alert = await self._alerts.rearm(alert_id, armed_after, threshold, current.revision)
        return AlertDTO.of(alert)


class MarkAlertsSeen:
    """Mark every fired alert seen (the owner opened the list)."""

    def __init__(self, alerts: AlertRepository) -> None:
        """Wire the use case with its collaborators."""
        self._alerts = alerts

    async def execute(self) -> int:
        """Return how many alerts changed."""
        return await self._alerts.mark_seen()


class EvaluateAlerts:
    """Check every active alert against its chart series; record the ones that fire."""

    def __init__(
        self,
        alerts: AlertRepository,
        prices: GetSecurityOHLCV,
        indicators: GetIndicatorSeries,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._alerts = alerts
        self._prices = prices
        self._indicators = indicators

    async def inputs(self, alert: Alert) -> tuple[list[SeriesPoint], str, Decimal]:
        """Return the values the alert reads, their data version, and the threshold.

        The values are the chart API's own: ``close`` from the price series,
        every other source from the indicator series, with the price series'
        ``partial`` flags. The threshold is in the chart's current price basis.
        """
        interval: AlertInterval = alert.interval
        prices = await self._prices.execute(alert.symbol, interval=interval)
        threshold = chart_threshold(
            alert.source, alert.threshold, _factor_at(prices.adjustments, alert.armed_after)
        )
        if alert.source == "close":
            points = [SeriesPoint(b.date, b.close, b.partial) for b in prices.bars]
            return points, prices.data_version, threshold
        partial = {b.date: b.partial for b in prices.bars}
        # The default strategy's series: the one the chart workspace draws.
        series = await self._indicators.execute(alert.symbol, interval=interval)
        points = [
            SeriesPoint(b.date, getattr(b, alert.source), partial.get(b.date, False))
            for b in series.bars
        ]
        return points, series.data_version, threshold

    async def execute(self) -> AlertEvaluationDTO:
        """One failing symbol never stops the others; it is reported."""
        active = await self._alerts.list_active()
        fired = 0
        failed: list[str] = []
        for alert in active:
            assert alert.id is not None
            try:
                if alert.drawing is not None and alert.drawing.kind in LINE_KINDS:
                    prices = await self._prices.execute(alert.symbol, interval="1D")
                    points = [SeriesPoint(b.date, b.close, b.partial) for b in prices.bars]
                    version = prices.data_version
                    levels = _line_levels(alert.drawing, prices)
                    firing = first_line_firing(alert.condition, alert.armed_after, points, levels)
                elif alert.drawing is not None:
                    points, version, lower, upper = await self.drawing_inputs(alert)
                    firing = (
                        first_zone_firing(alert.condition, lower, upper, alert.armed_after, points)
                        if upper is not None
                        else first_firing(alert.condition, lower, alert.armed_after, points)
                    )
                else:
                    points, version, threshold = await self.inputs(alert)
                    firing = first_firing(alert.condition, threshold, alert.armed_after, points)
            except (NotFoundError, ValueError):
                # ValueError: a data correction left a captured line without two sessions.
                _logger.warning("alert_series_missing", alert_id=alert.id, symbol=alert.symbol)
                failed.append(alert.symbol)
                continue
            if firing is not None and await self._alerts.fire(
                alert.id, firing, version, alert.revision
            ):
                fired += 1
        _logger.info("alerts_evaluated", evaluated=len(active), fired=fired, failed=len(failed))
        return AlertEvaluationDTO(evaluated=len(active), fired=fired, failed=sorted(set(failed)))

    async def drawing_inputs(
        self, alert: Alert
    ) -> tuple[list[SeriesPoint], str, Decimal, Decimal | None]:
        """Read authoritative daily closes and adjust each captured traded anchor."""
        assert alert.drawing is not None
        prices = await self._prices.execute(alert.symbol, interval="1D")
        lower, upper = _drawing_bounds(alert.drawing, prices.adjustments)
        points = [SeriesPoint(b.date, b.close, b.partial) for b in prices.bars]
        return (
            points,
            prices.data_version,
            lower,
            upper,
        )
