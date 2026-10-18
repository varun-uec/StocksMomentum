# ADR-011: Chart Engine — Keep lightweight-charts, Build the Workspace Around It

**Status:** Accepted (2026-10-17). Revised 2026-10-18 (draft): the persistence bullet now points to ADR-013 §5, and the product is named Wickstreet. The decision itself is unchanged.

## Context
ADD Amendment A1 adds the Wickstreet charting workspace. The project will be open source.

The web app already draws charts with `lightweight-charts` v5. The chart code is about 4,000 lines in `web/src/components/stock/`. It has four drawing tools (trendline, horizontal, rectangle, Fibonacci) and an indicator catalogue in `web/src/lib/indicators/`. Drawings live in browser `localStorage`.

## Decision
Keep `lightweight-charts` as the chart engine. Build the workspace UI in the web layer:

- **Shell:** top toolbar (symbol, interval, chart type, indicators, layout), left drawing rail, right watchlist panel.
- **Drawings:** grow from 4 to about 12 tools through the pane-primitive plugin API. Add select, move and delete.
- **Persistence:** workspace and drawings move to the server as versioned documents (ADR-013 §5). A drawing is user data. It holds no business rule.
- **Indicators:** keep the catalogue for display-only studies. Alert-capable indicators come from the backend (NFR-1a).

## Consequences
- Candles, scales and crosshair behave the way TradingView users expect, because this is TradingView's own open-source renderer.
- We own the drawing tools, the indicator dialog and multi-chart sync. That is most of the work in M11 to M13.
- The code can ship in a public repo. We must keep the licence attribution (ADR-012).

## Alternatives considered
- **TradingView Advanced Charting Library:** rejected. It is proprietary, and it cannot ship in an open-source project.
- **KLineChart or KLineChart Pro (Apache-2.0):** rejected. It means rewriting the existing chart code. Pro is at version 0.1.x.
- **Own canvas renderer:** rejected. High cost and no gain over the current engine.
