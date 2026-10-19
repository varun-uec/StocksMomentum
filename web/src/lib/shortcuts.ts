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
  { keys: 'Alt+V', action: 'Vertical line tool' },
  { keys: 'Click, drag, Delete', action: 'Select, move or delete a drawing' },
  { keys: '← → ↑ ↓ (drawing selected)', action: 'Move the drawing a bar sideways, or a little up or down' },
  { keys: 'Right-click, ContextMenu key, Shift+F10', action: "The drawing's menu (colour, width, text, delete), or the chart's (reset, indicators, scale, alert at a price)" },
  { keys: 'Ctrl/⌘+Z', action: 'Undo a drawing edit made in this window' },
  { keys: 'Ctrl/⌘+Shift+Z, Ctrl+Y', action: 'Redo' },
  { keys: 'Esc', action: 'Cancel the tool or the selection' },
  { keys: 'Alt+I', action: 'Open the indicator list' },
  { keys: 'Alt+W', action: 'Add the symbol to the watchlist, or remove it' },
  { keys: '?', action: 'Show these shortcuts' },
];

/** True when the key goes to a field or an open dialog, not to the workspace. */
export function isTyping(e: KeyboardEvent): boolean {
  const target = e.target as HTMLElement | null;
  // A checkbox or radio takes no text, so the workspace keys still apply after a click on one.
  const field = target?.closest(
    'input:not([type="checkbox"]):not([type="radio"]), textarea, select, [contenteditable="true"]',
  );
  const fieldDialog = field?.closest('dialog');
  if (fieldDialog && !fieldDialog.open) return false;
  return !!field || !!target?.closest('dialog[open]');
}

/** True when a key press should open symbol search instead of typing somewhere. */
export function opensSearch(e: KeyboardEvent): { initial: string } | null {
  if (isTyping(e)) return null;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') return { initial: '' };
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  if (e.key === '/') return { initial: '' };
  if (/^[a-z0-9]$/i.test(e.key)) return { initial: e.key };
  return null;
}
