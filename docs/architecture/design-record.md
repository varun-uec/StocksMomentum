# Wickstreet Design Record

> Kept under [ADD Amendment A1](./ADD-amendment-A1.md) §1a (Proposed). Append only: add entries, never rewrite them. A correction is a new entry that names the one it corrects.

Wickstreet is an independent implementation. TradingView and OpenChart are references for usability and capability, not sources of code. This record shows where each design idea came from, so anyone can check that independence later.

## Exposure log

Every contact with reference material, with its date and scope. It states what was seen honestly; it never claims that nothing was seen.

| # | Date | Who | Material | Scope | Frontend source read? |
|---|---|---|---|---|---|
| X1 | 2026-10-18 | Owner and Claude (assistant) | OpenChart README on GitHub | Capability list, licence summary | No |
| X2 | 2026-10-18 | Claude | OpenChart `LICENSE` file | Licence terms (logo clause, multi-tenant clause) | No |
| X3 | 2026-10-18 | Claude | openchart.co/docs/getting-started | Setup flow, data providers, alert behaviour | No |
| X4 | 2026-10-18 | Claude | TradingView Charting Library docs: keyboard shortcuts | Documented shortcut set | No |
| X5 | before 2026-10-17 | Owner | TradingView as an everyday user | Observable behaviour of tradingview.com | No |
| X6 | 2026-10-18 | Claude | TradingView Lightweight Charts™ `README` and `NOTICE` (Apache-2.0, a dependency) | Licence and attribution terms | Library code is a declared dependency, used under its licence |

## Decisions

Each entry: the Wickstreet decision, the reference that prompted it (if any), and our own reason.

| # | Date | Decision | Reference | Our reason |
|---|---|---|---|---|
| D1 | 2026-10-18 | Typing on the chart, `/` or `Ctrl/⌘+K` opens symbol search | X4, X5 (typing changes symbol; `Ctrl+K`) | Users with TradingView habits expect it. Search is the first step of every workflow. |
| D2 | 2026-10-18 | Drawings belong to the symbol, not to one chart | X5 | One analysis per symbol is visible at every range and on every chart that shows the symbol. ADR-013 §5. |
| D3 | 2026-10-18 | Click selects a drawing; drag moves it; Delete removes it; Esc cancels | X4, X5 | Standard direct manipulation. Without it, drawings cannot be corrected. |
| D4 | 2026-10-18 | Autosave with a visible "Saved ✓ hh:mm" state, no Save button in M11 | Own | A self-hosted app has no account flow to save into. Visible state builds trust. |
| D5 | 2026-10-18 | A conflict notice, never a silent overwrite | Own | ADR-013 §5. Two windows on one instance are a normal case. |
| D6 | 2026-10-18 | Chart in the centre, drawing tools on the left, details on the right | Common terminal convention (X5) | Layout convention shared by most charting tools; Wickstreet uses its own visual style |
| D7 | 2026-10-18 | `/` opens search in M11, and moves to the indicator dialog in M13 | X4 (`/` opens indicators) | M11 has no indicator dialog. The move keeps TradingView habits once the dialog exists. |
| D8 | 2026-10-18 | No scripting language and no AI agents | X1 (OpenChart offers both) | A1 §4. Momentum25's configurable, explained rules are the differentiator. |
