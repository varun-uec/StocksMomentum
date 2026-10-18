# M12 Report — Workspace Shell

> **Date:** 2026-10-18 · **Branch:** `wickstreet/m10-m11` · **Plan:** [milestones](../plans/2026-10-18-wickstreet-milestones.md) · **Wireframes:** [M9 study §5](../plans/2026-10-18-m9-reference-study.md)

## What changed

| Part | Result |
|---|---|
| Drawing rail | The chart workspace's drawing tools sit in a column left of the chart: Select, Trendline, Horizontal ray, Rectangle, Fib retracement, Clear. Research screens keep the toolbar row. |
| Chart keys | ← / → pan, Ctrl/⌘+↑ / ↓ or + / − zoom, Alt+R resets, Alt+T / H / Shift+R / F pick a tool, Alt+W adds or removes the symbol from the watchlist, `?` lists every shortcut. `/` stays symbol search (D9). [Shortcut list](../../current/keyboard-shortcuts.md). |
| Side panel | Right of the chart, with two tabs. Watchlist: the list with close, change and rank; a click opens the symbol. Details: readiness, scores, gate failures, why it ranks and what could invalidate it, and a link to full research. The open tab is saved in the workspace (`right_panel`). |
| Screener in the shell | On wide screens the dashboard shows the selected row beside the ranked table: a year of closes, the run's explanation, and links to the chart and the research page. Narrow screens open the research page, as before. |
| Indicator panes | Clipped to the price bars' span, so they no longer stretch the time axis (carried from the M11 review). |
| Navigation | The existing top bar stays: primary screens plus the Research menu, which keeps every advanced screen one click away. |

## Decisions taken

- **Daily panes keep the snapshot's bar window.** Recomputed on the full history, the last ADX value differed in the 4th decimal for 2 of 100 symbols (ABBOTINDIA 23.1470 vs 23.1471). Pane values must equal the rules' inputs, so on the longest ranges daily panes start where that window starts (about 13 months back). Weekly panes cover the whole history.
- **No new dependency.** Native `<dialog>`, `ResizeObserver` and `matchMedia` cover the dialog, the resizing chart and the wide-screen check. ADR-013 allows Radix and resizable panels; they wait until menus and panel sizes need them (M13).
- **The Research menu is the "More" menu.** It already holds every advanced screen, with full keyboard support. Renaming it would only churn links.
- **Workspace merges cover every top-level field.** Before this, a new workspace field would have been dropped in a merge without notice.
- **The extracted helpers are shared.** `rankReasons`, `investmentReadiness` and `ExplanationSummary` serve the stock page, the side panel and the screener, so all three explain a symbol the same way.

## Defects found and fixed

1. The gate badges stretched into tall ovals beside wrapped text (seen in screenshots).
2. The pane separator was the library's default white, harsh in the dark theme.
3. The chart resized only with the window, so a panel opening beside it would have left it too wide. It now follows its container.

## Verification

| Suite | Result |
|---|---|
| Backend `pytest` | 707 passed |
| `ruff check`, `mypy --strict`, import contracts | clean |
| Web Vitest | 74 passed |
| Web ESLint, build | clean |
| Playwright | 53 passed (21 route tests unchanged). The M11, M11b and M12 specs passed 3 repetitions in a row (69/69). |
| NFR-11 chart open (30 runs each) | Warm P95 165 ms (target ≤ 1 s); cold P95 201 ms (target ≤ 3 s) |

## Not in M12

Panel resizing, more drawing tools, the indicator dialog, context menus, chart types, log scale and multi-chart layouts (M13).
