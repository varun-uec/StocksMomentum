/**
 * Keyboard shortcuts of the chart workspace (M12). The shortcuts dialog and
 * docs/current/keyboard-shortcuts.md both list this table.
 */
export const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: 'Type a letter, / or Ctrl/⌘+K', action: 'Search for a symbol' },
  { keys: '← / →', action: 'Pan the chart (chart focused)' },
  { keys: 'Ctrl/⌘+↑ / ↓, + / -', action: 'Zoom in or out (chart focused)' },
  { keys: 'Alt+R', action: 'Reset the view to the whole range (chart focused)' },
  { keys: 'Alt+T', action: 'Trendline tool' },
  { keys: 'Alt+H', action: 'Horizontal ray tool' },
  { keys: 'Alt+Shift+R', action: 'Rectangle tool' },
  { keys: 'Alt+F', action: 'Fib retracement tool' },
  { keys: 'Click, drag, Delete', action: 'Select, move or delete a drawing' },
  { keys: 'Esc', action: 'Cancel the tool or the selection' },
  { keys: 'Alt+W', action: 'Add the symbol to the watchlist, or remove it' },
  { keys: '?', action: 'Show these shortcuts' },
];
