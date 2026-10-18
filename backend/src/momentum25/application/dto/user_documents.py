"""User-document bodies (ADR-013 §5), version 1.

Strict on purpose: an unknown field is rejected, never dropped, and every list
has a cap, so one request can never store an unbounded document. A new field
means a new schema version.

Drawings belong to a symbol. Presentation (range, indicators, panes) belongs
to a chart inside the workspace, so two charts of one symbol can differ while
sharing drawings.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from momentum25.domain.entities.user_document import UserDocument

ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
SYMBOL_PATTERN = r"^[A-Z0-9][A-Z0-9&._-]{0,31}$"

Identifier = Annotated[str, Field(pattern=ID_PATTERN)]
Symbol = Annotated[str, Field(pattern=SYMBOL_PATTERN)]
ShortName = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,32}$")]
ParamName = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── symbol_drawings ───────────────────────────────────────────────────────


class DrawingPointV1(_Strict):
    """One anchor: a date and the traded price on that date, not adjusted (ADR-013 §5)."""

    date: date
    price: FiniteFloat


class DrawingV1(_Strict):
    """One drawing on a symbol's chart."""

    id: Identifier
    kind: ShortName
    points: list[DrawingPointV1] = Field(min_length=1, max_length=8)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    width: int = Field(default=2, ge=1, le=4)
    text: str | None = Field(default=None, max_length=200)


class SymbolDrawingsV1(_Strict):
    """Every drawing on one symbol."""

    price_basis: Literal["traded"] = Field(
        default="traded",
        description="Point prices are as printed on each point's date, never adjusted. "
        "The chart adjusts them only to draw them (ADR-013 §5).",
    )
    drawings: list[DrawingV1] = Field(max_length=1000)


# ── workspace ─────────────────────────────────────────────────────────────


class IndicatorV1(_Strict):
    """One configured catalogue indicator. Display only (NFR-1a)."""

    uid: Identifier
    id: Identifier
    params: dict[ParamName, FiniteFloat | Annotated[str, Field(max_length=64)]] = Field(
        max_length=16
    )


class ChartV1(_Strict):
    """Presentation of one chart slot."""

    symbol: Symbol | None = None
    range: Literal["1W", "1M", "3M", "6M", "1Y", "MAX"]
    interval: Literal["1D", "1W", "1M"] = "1D"
    chart_type: Literal["candles", "bars", "line", "area", "heikin_ashi"] = "candles"
    scale: Literal["normal", "log", "percent"] = "normal"
    mas: list[Annotated[int, Field(ge=0, le=1000)]] = Field(max_length=8)
    panes: list[ShortName] = Field(max_length=8)
    indicators: list[IndicatorV1] = Field(max_length=32)
    preset_id: ShortName | None = None
    show_signals: bool = True
    preset_edited: bool = False
    compare: list[Symbol] = Field(
        default_factory=list,
        max_length=4,
        description="Symbols drawn as lines rebased to this chart's symbol (M13).",
    )


class SyncV1(_Strict):
    """What the charts of a multi-chart layout share (M13)."""

    symbol: bool = False
    interval: bool = False
    crosshair: bool = True


class WorkspaceV1(_Strict):
    """The owner's workspace: which chart is active and how each chart looks."""

    active_chart_id: Identifier | None = None
    right_panel: Literal["watchlist", "details"] | None = "watchlist"
    layout: Literal["1x1", "2x1", "1x2", "2x2", "3x3", "4x4"] = Field(
        default="1x1", description="Chart grid, columns x rows (M13)."
    )
    sync: SyncV1 = Field(default_factory=SyncV1)
    charts: dict[Identifier, ChartV1] = Field(max_length=32)


# ── responses ─────────────────────────────────────────────────────────────


class _DocumentMeta(BaseModel):
    key: str
    schema_version: int
    revision: int
    updated_at: datetime


class WorkspaceDocument(_DocumentMeta):
    """A stored workspace and its revision."""

    body: WorkspaceV1

    @classmethod
    def of(cls, doc: UserDocument) -> WorkspaceDocument:
        """Build the response from a stored document."""
        return cls(
            key=doc.key,
            schema_version=doc.schema_version,
            revision=doc.revision,
            updated_at=doc.updated_at,
            body=WorkspaceV1.model_validate(doc.body),
        )


class SymbolDrawingsDocument(_DocumentMeta):
    """A symbol's stored drawings and their revision."""

    body: SymbolDrawingsV1

    @classmethod
    def of(cls, doc: UserDocument) -> SymbolDrawingsDocument:
        """Build the response from a stored document."""
        return cls(
            key=doc.key,
            schema_version=doc.schema_version,
            revision=doc.revision,
            updated_at=doc.updated_at,
            body=SymbolDrawingsV1.model_validate(doc.body),
        )
