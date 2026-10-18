# M9 Reference Study and UX Specification

> **Status:** Proposed, for review, 2026-10-18. Scope per [ADD A1](../../architecture/ADD-amendment-A1.md) §27 M9: a full capability inventory and parity matrix, a reuse matrix from the code, and wireframes for the M11 workflow and the screener only.
> **Clean-room rule (A1 §1a):** this study uses public documentation and observable behaviour only. Sources and exposure are logged in the [design record](../../architecture/design-record.md).

## 1. Sources

| Source | What it gave | Kind |
|---|---|---|
| [OpenChart README](https://github.com/longsurf-ai/openchart) | Capability list: indicators, Volume Profile, 4×4 grid, drawings, alerts, Tea, agents, desktop app | Public README |
| [OpenChart getting started](https://openchart.co/docs/getting-started/) | Setup flow, data providers (Binance, Yahoo Finance), alerts need the desktop app open | Public docs |
| [TradingView Charting Library: keyboard shortcuts](https://www.tradingview.com/charting-library-docs/latest/getting_started/Shortcuts) | The documented shortcut set for search, intervals, drawings, layouts | Public docs |
| Wickstreet code at `65800e7` | What exists today | Our code |

No OpenChart or TradingView frontend source was read.

## 2. Capability inventory and parity matrix

"Today" means what Wickstreet does at `65800e7`. P0 means needed for a TradingView user to feel at home. P1 means needed for a complete workspace. P2 means later or never. Out of scope means excluded by A1 §4.

| Capability | TradingView (public docs) | OpenChart (public docs) | Wickstreet today | Target | Priority |
|---|---|---|---|---|---|
| Symbol search from anywhere | Start typing on the chart; `Ctrl+K` quick search | "Search for the instrument" | Search box in the nav bar only | M11 | P0 |
| Daily bars, candles | Yes | Yes | Yes (`PriceChart`) | — | P0 |
| Intervals 1D / 1W / 1M | Digit or `,` changes interval | Not documented | 1D only; `1W`/`1M` are visible ranges, not intervals | M11b (1W), M13 (1M) | P0 |
| Chart types (bar, line, area, Heikin-Ashi) | Yes | Not documented | Candles only | M13 | P1 |
| Log and percent scale | `Alt+L`, `Alt+P` | Not documented | No | M13 | P1 |
| Pan, zoom, reset | Arrow keys, `Ctrl+↑/↓`, `Alt+R` | Implied | Mouse pan and zoom (library default) | M12 (keys) | P0 |
| Crosshair legend (OHLC and values) | Yes | Implied | Yes (crosshair readout) | — | P0 |
| Indicator search dialog | `/` opens indicators | "Add indicators" | `OverlayPicker` (catalogue list) | M11 (reuse), M13 (dialog) | P0 |
| Indicator sub-panes | Yes | Yes | RSI, MACD, ADX (server values) | — | P0 |
| Drawing tools: trend, horizontal, rectangle, Fib | `Alt+T/H/Shift+R/F` | "Lines or zones" | All four exist | — | P0 |
| Select, move, delete a drawing | Click, drag, arrow keys, `Delete` | Implied | **No** | M11 | P0 |
| Undo / redo | `Ctrl+Z` / `Ctrl+Y` | Not documented | No | M13 | P1 |
| About 12 drawing tools, style editing | Many tools | Not documented | 4 | M13 | P1 |
| Drawings persist per symbol | Yes (account) | Not documented | Browser `localStorage` only | M11 (server) | P0 |
| Saved workspace / layout | `Ctrl+S` save, `.` load | Not documented | No | M11 (autosave) | P0 |
| Multi-chart layouts | Yes | Up to 4×4 | Diagnostic grid only (`/lab/chart-grid`) | M13 | P1 |
| Watchlist panel | Right panel, `Alt+W` adds | "Semantic Watchlist" coming soon | Watchlist page | M12 (panel) | P1 |
| Price and indicator alerts | Yes | Yes, plus drawing-triggered | No | M15 (daily) | P1 |
| Volume Profile | Yes | Yes | No | Backlog | P2 |
| Scripting language | Pine Script | Tea | No | **Out of scope** | — |
| AI agents | No | Yes | No | **Out of scope** | — |
| Intraday / real-time data | Yes | Binance, Yahoo | No (NSE EOD) | **Out of scope** | — |
| Screener with explained ranks | Screener (no rule-level explanation) | Not documented | **Yes: Top-25, rule breakdown, gates, history** | M12 (in shell) | P0, differentiator |
| Strategy configuration | Pine Script | Tea | Strategy JSON, read-only in the UI | M14 Studio | P1, differentiator |
| Self-hosted, no account | No | Desktop app; cloud data optional | Yes, loopback by default | — | P0, differentiator |

## 3. Interaction inventory for the M11 workflow

Each row names an interaction a TradingView user will try in the first minute, what we observed in public docs, and what Wickstreet does in M11.

| Step | User tries | Reference behaviour | Wickstreet M11 behaviour |
|---|---|---|---|
| Find | Types a symbol while the chart has focus | Typing opens symbol search with the typed text | Same. Also `/` and `Ctrl/⌘+K`. Results from `GET /securities?q=`. ↑/↓ choose, Enter opens, Esc closes. |
| Find | Opens a link someone shared | Chart opens on that symbol | `/chart/RELIANCE` opens directly (deep link, S1) |
| Analyse | Scrolls and pinches | Pan and zoom | Library default, unchanged |
| Analyse | Picks a range (1Y, MAX) | Range buttons under the chart | Existing range buttons |
| Analyse | Adds an MA, then RSI | Indicator dialog | Existing MA toggles and pane toggles; RSI/MACD from the server |
| Draw | Picks a tool, clicks twice | Tool stays active for one drawing | Existing behaviour |
| Draw | Clicks a drawing | Selects it; handles appear | **New:** selection with handles |
| Draw | Drags it | Moves the whole drawing; dragging a handle moves one point | **New:** move whole and move one anchor |
| Draw | Presses Delete or Backspace | Removes the selected drawing | **New** |
| Draw | Presses Esc | Cancels the tool or the selection | **New** for selection |
| Restore | Closes the tab, comes back | Everything is as it was | **New:** server documents, autosave |
| Restore | Opens a second browser | Same state | **New** |
| Restore | Edits in two windows | The later save wins or warns | **New:** conflict notice (ADR-013 §5), never silent |

## 4. Reuse matrix

| Existing module | Lines | M11 use | Change |
|---|---|---|---|
| `components/stock/PriceChart.tsx` | 1,050 | The chart | Forward pointer events to the drawing layer for select and move. No new state. |
| `components/stock/chart-drawings.ts` | 313 | Drawing model and renderer | **Extend:** hit-test, selected state, handles, move |
| `components/stock/useChartShell.ts` | 96 | Bars, panes and preferences per symbol | Reuse as the seam. Its preference source changes underneath. |
| `lib/chart-preferences.ts` | 137 | Range, MAs, panes, drawings | **Swap backing** from `localStorage` to server documents; keep the hook API |
| `lib/overlay-preferences.ts` | 128 | Catalogue overlays per symbol | **Swap backing**, same as above |
| `components/stock/OverlayPicker.tsx` | 214 | Add catalogue indicators | Reuse |
| `NavBar.tsx` `SymbolSearch` | 132 | Search with keyboard choice | **Extract** into `components/workspace/SymbolSearch.tsx`, add a dialog mode and the type-anywhere trigger; the nav bar keeps using it |
| `lib/api-client.ts` | 482 | HTTP calls | Add the document calls, using generated types |
| `GET /securities?q=`, `/securities/{s}/ohlcv`, `/stocks/{s}/indicators/series` | — | Search, bars, server indicators | Reuse unchanged |
| Watchlist backend (`0007`, port, repo, use case, router) | — | Persistence pattern | Copy the layering for `user_documents` |
| — | — | Server documents | **New:** migration `0014`, port, repository, use cases, router, tests |
| — | — | `useServerDocument`, `ConflictNotice`, `/chart/:symbol` | **New** |

Dependencies: no new runtime dependency is needed for M11. Radix primitives (ADR-013) arrive with the M12 shell, where menus and dialogs multiply; M11's one dialog and one notice are plain components.

Test coverage today: `PriceChart` and `chart-drawings` have no unit tests. M11 adds geometry tests for hit-testing and moving. The E2E suite covers every route.

## 5. Wireframes

Original layouts. They follow the common conventions of charting terminals (chart in the centre, tools on the left, details on the right), not any product's visual design.

### 5.1 Chart screen, M11 (`/chart/:symbol`)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [W] Wickstreet   Screener  Watchlist  Market  Learn  More▾     [Search ⌘K] ◐ │  existing nav bar
├──────────────────────────────────────────────────────────────────────────────┤
│ RELIANCE · Reliance Industries   1,412.30  +0.84%        [1M 3M 6M 1Y MAX]   │  symbol bar
├───┬──────────────────────────────────────────────────────────────────────────┤
│ ↖ │ O 1,401.2  H 1,415.0  L 1,398.4  C 1,412.3   MA50 1,377.9  MA200 1,322.4  │  crosshair legend
│ ╱ │                                                                    ┊      │
│ ─ │            ╭╮       ╭─╮                                            ┊ 1420 │
│ ▭ │      ╭╮╭─╮╭╯╰╮ ╭╮╭─╯ ╰╮      ●━━━━━━━━━━━━━━━━━● (selected)        ┊      │
│ ≡ │  ╭─╮╭╯╰╯ ╰╯   ╰─╯╰╯    ╰╮╭╮  ┃                 ┃                   ┊ 1380 │
│   │ ─╯ ╰╯                   ╰╯╰──●━━━━━━━━━━━━━━━━━●                   ┊      │
│ 🗑 │──────────────────────────────────────────────────────────────────────────│
│   │ RSI 14   58.2                                                      ┊  70  │  server pane
│   │ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ┊  30  │
├───┴──────────────────────────────────────────────────────────────────────────┤
│ [+ Indicator]  MA 20 50 150 200   Panes: RSI MACD ADX        Saved ✓ 09:41   │  study bar + save state
├──────────────────────────────────────────────────────────────────────────────┤
│ Charts by TradingView Lightweight Charts™ · About Wickstreet                 │  footer
└──────────────────────────────────────────────────────────────────────────────┘
 Left rail: select (↖), trendline (╱), horizontal (─), rectangle (▭), Fib (≡), delete (🗑).
```

Rules:
- The chart takes all the free height. No cards above it.
- "Saved ✓ hh:mm" shows the last confirmed save. "Saving…" shows while a save is in flight. "Not saved" shows with a retry link after a failure.
- The left rail is the existing drawing toolbar, moved into a column. M12 restyles it.

### 5.2 Symbol search dialog

```
          ┌──────────────────────────────────────────────┐
          │ 🔍 reli█                                      │
          ├──────────────────────────────────────────────┤
          │ ▸ RELIANCE   Reliance Industries Ltd    NSE  │  ← highlighted
          │   RELINFRA   Reliance Infrastructure    NSE  │
          │   RPOWER     Reliance Power             NSE  │
          ├──────────────────────────────────────────────┤
          │ ↑↓ choose · Enter open · Esc close           │
          └──────────────────────────────────────────────┘
```

- Opens on any printable key while the chart has focus, on `/`, or on `Ctrl/⌘+K`. The first typed character goes into the box.
- Centred over the chart, with the page dimmed behind it. Focus is trapped inside. Esc returns focus to the chart.
- No results → "No NSE symbol matches 'xyz'."

### 5.3 Conflict notice

```
┌──────────────────────────────────────────────────────────────────────┐
│ ⚠ Your drawings on RELIANCE changed in another window.               │
│   [Keep theirs]   [Apply mine]                                       │
└──────────────────────────────────────────────────────────────────────┘
```

- It appears above the study bar. It does not block the chart.
- **Keep theirs** loads the server version. **Apply mine** re-applies the local edit on top of it and saves.
- An edit to a *different* drawing merges silently and shows no notice (ADR-013 §5).

### 5.4 Screener inside the shell (M12)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [W] Wickstreet   Screener  Watchlist  Market  Learn  More▾     [Search ⌘K] ◐ │
├──────────────────────────────────────────────────────────────────────────────┤
│ Screener · Momentum25 (minervini_trend_template v3)   Run 2026-08-07 ✓  [▶ Run]│
├───────────────────────────────────────────────┬──────────────────────────────┤
│ #  Symbol     Momentum  Setup  Gates  Δ rank  │ RELIANCE                      │
│ 1  ABCD        91.2     78.0   8/8     ▲2     │ [mini chart, 1Y]              │
│ 2  EFGH        89.7     81.5   8/8     ─      │ Why it ranks: 3 top rules     │
│ 3  …                                          │ Gates: all passed             │
│ …  (Top 25)                                   │ [Open chart →] [Explain →]    │
└───────────────────────────────────────────────┴──────────────────────────────┘
```

- The table is the existing `MomentumTable`. The right panel shows the selected row. "Open chart" goes to `/chart/:symbol`.
- Explanations keep their exact domain terms: gate, qualified set, score.

## 6. Keyboard map for M11

| Key | Action | Reference |
|---|---|---|
| Any printable key on the chart, `/`, `Ctrl/⌘+K` | Open symbol search | TradingView: typing, `Ctrl+K` |
| ↑ / ↓, Enter, Esc | Choose, open, close (search) | Common |
| Click a drawing | Select | TradingView |
| Drag | Move the drawing; drag a handle to move one point | TradingView |
| Delete / Backspace | Delete the selected drawing | TradingView |
| Esc | Cancel the active tool or selection | TradingView |

Note: TradingView uses `/` for the indicator dialog. Wickstreet uses `/` for symbol search. *(Amended at the M11 review: `/` stays symbol search in every milestone, and M13 gives the indicator dialog another shortcut. Design record D9.)*

## 7. Open usability questions (default taken)

| Question | Default in M11 |
|---|---|
| Should the chart remember the last symbol on `/chart` with no symbol? | Yes: `/chart` opens the workspace's last symbol, or RELIANCE on a fresh install |
| Should drawings be shared across ranges (1Y vs MAX)? | Yes: drawings belong to the symbol (ADR-013 §5) |
| Should the existing `/stock/:symbol/analysis` screen move to the new storage? | Yes: it uses the same hooks, so it moves too and keeps working |
