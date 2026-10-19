# Wickstreet workstation design system

Implemented 2026-10-19. Design provenance: D17–D21 in the [design record](../architecture/design-record.md). This is an implementation guide, not a proposed redesign.

## Hierarchy and surfaces

The symbol and its latest stored EOD price lead the chart workspace. Chart configuration sits immediately below; contextual evidence sits in the right inspector. Research keeps its own route and returns to the selected security through the shared symbol actions. All existing research/data/learning routes remain available.

Use paper (`#ffffff`) and ink (`#19262e` / `#101a21`) surfaces, fine separators and sea-green accents (`#176f5c` light, `#7cc5b1` dark). Positive/negative market colours remain semantic. No gradients, glow or decorative motion. `theme.ts` supplies the owned utility scales through Tailwind; `globals.css` supplies workstation geometry and surface variables.

Inter Variable is the single UI typeface. Financial values use tabular numerals. Chart controls use 11–12px text; route headings use 20–24px. Use 4px control radii, 6–8px panel radii, restrained borders and 4/8/12/16px spacing. Overlays alone receive a shadow. Keyboard focus uses a visible sea-green outline/ring; motion follows `prefers-reduced-motion`.

## Interaction rules

- A range establishes a viewport over the complete stored history. Panning is unrestricted. Research calculations retain their explicit analysis window.
- Legends identify studies and latest values. The shared Indicators inspector owns parameters, colour, visibility, removal and immediate restoration. Backend-authoritative panes and configurable display-only RSI/MACD remain explicitly separate.
- Price studies are hidden on percentage scale, avoiding independent-base distortions. Comparisons retain relative-return plotting and a stable, disclosed preset anchor.
- Grid controls share a compact row; only the active cell exposes the drawing rail. Activation retains chart instances. Dense 9/16-chart layouts temporarily release sidebar space without discarding the saved panel preference.
- Objects own drawing visibility, locking and undo/redo. Selection/context menus expose styling. Notes use an inline form. Transient annotation state clears on symbol changes.
- Alert levels carry an EOD label. Captured drawing alerts freeze saved traded-price anchors and a document revision; changing a drawing does not silently change a rule. Alert editing explicitly refreshes the snapshot and re-arms from the latest stored session. Stale data/drawing revisions are rejected.
- Native search/indicator dialogs trap focus. Compact inspectors dismiss outside or with Escape. Side-panel tabs support arrows/Home/End. Ctrl/Command+K opens symbol search from research routes too.

## Responsive behavior

Desktop uses the full window width. Below 1024px the evidence inspector opens as a contextual overlay and navigation moves to the bottom bar. Search stays in the top shell. Tablet/mobile content reserves space for bottom navigation. Touch controls use larger targets. Dense-grid tool rails scroll within the active plot height.

The 200% equivalent 720×450 regression remains part of the suite. Native Chrome 200% zoom was also exercised on the working preview. Automated axe checks cover dashboard/chart/Studio in both themes; these checks are evidence, not a comprehensive accessibility-conformance claim.

## Workstation geometry (amended 2026-10-19, D23)

TradingView supplies the structure; the skin above is unchanged. Reference measurements at 1440×900 (exposure X9): top toolbar ≈38 px, left rail ≈52 px, right strip ≈45 px plus a ≈300 px panel, bottom bar ≈38 px.

| Region | Desktop ≥1280 | Laptop 1024–1279 | Tablet 600–1023 | Phone <600 |
|---|---|---|---|---|
| Header bar (☰, mark, search, route slot) | 38 px, one row | same; low-priority controls fold into "⋯" | symbol, interval, Indicators, ⋯ | symbol, interval, ⋯ |
| Left drawing rail (chart surfaces) | 52 px, grouped, flyouts | 44 px | 40 px | one "Draw" button, groups in a bottom sheet |
| Right icon strip + panel | 45 px + 300 px, inline | strip inline; panel overlays the plot | no strip; header button opens a right sheet | full-width bottom sheet |
| Bottom range bar (/chart) | 30 px | 30 px | wraps to one scrollable row | scrolls horizontally |

Sheets and overlays never take width from the plot. Touch targets stay at least 32 px under `pointer: coarse`. The plot gets the space left after the chrome; it never uses a fixed chrome height.
