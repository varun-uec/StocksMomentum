/**
 * CSV export of a screen: every matched row at full precision, with each missing
 * value's state and reason, and the revision, method and filter that produced it.
 */
import type { Envelope, ScreenRow } from './api';

export function csvCell(value: unknown): string {
  if (value === null || value === undefined) return '';
  const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
  return /[",\n\r]/.test(text) || /^[=+\-@\t]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function screenCsv(columns: string[], rows: ScreenRow[], meta: Envelope & { filter: unknown; sort: unknown; formulas: unknown }): string {
  const lines = [
    `# Wickstreet screen export; NAV data as of ${meta.as_of}; snapshot ${meta.data_revision}; method v${meta.method_version}; sources ${meta.sources.join(' ')}`,
    `# filter ${csvCell(meta.filter)}`,
    `# sort ${csvCell(meta.sort)}; formulas ${csvCell(meta.formulas)}`,
    ['amfi_code', 'name', ...columns.flatMap((c) => [c, `${c}_missing`])].join(','),
  ];
  for (const row of rows) {
    const cells = [row.amfi_code, row.name, ...columns.flatMap((c) => [row.values[c], row.states[c] ? `${row.states[c].state}:${row.states[c].reason}` : ''])];
    lines.push(cells.map(csvCell).join(','));
  }
  return `${lines.join('\n')}\n`;
}

export function download(name: string, text: string, type = 'text/csv') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
