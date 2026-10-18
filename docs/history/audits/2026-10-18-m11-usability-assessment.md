# M11 Usability Assessment — Find → Analyse → Draw → Restore

> **Status:** open. The owner's hands-on assessment, kept apart from the [engineering gate](2026-10-18-m11-vertical-slice-report.md), which closed on 2026-10-18 on passing tests.

## How to try it

```bash
make up
open http://localhost:8000/chart
```

## What to judge

| Flow | Question |
|---|---|
| Find | Does typing on the chart, `/` or Ctrl/⌘+K find and open a symbol as fast as you expect? |
| Analyse | Do range, moving averages and RSI/MACD/ADX feel direct? |
| Draw | Do the four tools, select, drag and Delete behave as you expect? |
| Restore | After a reload, or in another browser, is everything where you left it? |
| Conflicts | With two windows open, are the notices clear, and does each choice do what it says? |

## Known issues to ignore here

- Indicator panes stretch the time axis on short ranges. M12 fixes it.
- The drawing tools sit in the chart toolbar, not a left rail. M12 adds the rail.

## Result

Not yet recorded.
