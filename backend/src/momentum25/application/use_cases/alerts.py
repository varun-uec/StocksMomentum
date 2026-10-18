"""Daily alert use cases (FR-22, M15).

Evaluation reads each alert's values through the same use cases the chart
calls, so the chart and the alert see one series (NFR-1a).
"""

from __future__ import annotations

from datetime import date

from momentum25.application.dto.alerts import (
    AlertDTO,
    AlertEvaluationDTO,
    AlertListDTO,
    CreateAlertRequest,
)
from momentum25.application.use_cases.securities import GetSecurityOHLCV
from momentum25.application.use_cases.stocks import GetIndicatorSeries
from momentum25.domain.entities.alert import Alert, AlertInterval, SeriesPoint, first_firing
from momentum25.domain.errors import NotFoundError
from momentum25.domain.ports.repositories import (
    AlertRepository,
    OHLCVRepository,
    SecurityRepository,
)
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("alerts")


async def _last_session(ohlcv: OHLCVRepository) -> date:
    return await ohlcv.latest_date() or date.today()


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
        self, securities: SecurityRepository, ohlcv: OHLCVRepository, alerts: AlertRepository
    ) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._ohlcv = ohlcv
        self._alerts = alerts

    async def execute(self, request: CreateAlertRequest) -> AlertDTO:
        """Raise :class:`NotFoundError` for an unknown symbol."""
        security = await self._securities.get_by_symbol(request.symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {request.symbol}")
        alert = Alert(
            symbol=str(security.symbol),
            source=request.source,
            interval=request.interval,
            condition=request.condition,
            threshold=request.threshold,
            armed_after=await _last_session(self._ohlcv),
        )
        return AlertDTO.of(await self._alerts.add(security.id, alert))


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

    def __init__(self, ohlcv: OHLCVRepository, alerts: AlertRepository) -> None:
        """Wire the use case with its collaborators."""
        self._ohlcv = ohlcv
        self._alerts = alerts

    async def execute(self, alert_id: int) -> AlertDTO:
        """Raise :class:`NotFoundError` if it does not exist."""
        alert = await self._alerts.rearm(alert_id, await _last_session(self._ohlcv))
        if alert is None:
            raise NotFoundError(f"Alert not found: {alert_id}")
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

    async def inputs(self, alert: Alert) -> tuple[list[SeriesPoint], str]:
        """Return the values the alert reads and their data version.

        They are the chart API's own values: ``close`` from the price series,
        every other source from the indicator series, with the price series'
        ``partial`` flags.
        """
        interval: AlertInterval = alert.interval
        prices = await self._prices.execute(alert.symbol, interval=interval)
        if alert.source == "close":
            points = [SeriesPoint(b.date, b.close, b.partial) for b in prices.bars]
            return points, prices.data_version
        partial = {b.date: b.partial for b in prices.bars}
        # The default strategy's series: the one the chart workspace draws.
        series = await self._indicators.execute(alert.symbol, interval=interval)
        points = [
            SeriesPoint(b.date, getattr(b, alert.source), partial.get(b.date, False))
            for b in series.bars
        ]
        return points, series.data_version

    async def execute(self) -> AlertEvaluationDTO:
        """One failing symbol never stops the others; it is reported."""
        active = await self._alerts.list_active()
        fired = 0
        failed: list[str] = []
        for alert in active:
            assert alert.id is not None
            try:
                points, version = await self.inputs(alert)
            except NotFoundError:
                _logger.warning("alert_series_missing", alert_id=alert.id, symbol=alert.symbol)
                failed.append(alert.symbol)
                continue
            firing = first_firing(alert.condition, alert.threshold, alert.armed_after, points)
            if firing is not None:
                await self._alerts.fire(alert.id, firing, version)
                fired += 1
        _logger.info("alerts_evaluated", evaluated=len(active), fired=fired, failed=len(failed))
        return AlertEvaluationDTO(evaluated=len(active), fired=fired, failed=sorted(set(failed)))
