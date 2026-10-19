/**
 * The `?from=` return path (plan 2026-10-19, context model). A view opened
 * from another view carries where it came from, so it can offer the way back.
 * Only a same-origin path is accepted: never a scheme, a host or a
 * protocol-relative URL, so a crafted link cannot send the user off-site.
 */

/** The return path, or null when `raw` is missing or not a same-origin path. */
export function safeReturnPath(raw: string | null): string | null {
  if (!raw) return null;
  const path = raw.trim();
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('\\') || /[\u0000-\u001f]/.test(path)) return null;
  try {
    const url = new URL(path, 'http://same.origin');
    return url.origin === 'http://same.origin' ? url.pathname + url.search + url.hash : null;
  } catch {
    return null;
  }
}

/** "Back to chart · TCS" for a /chart path; "Back" otherwise. */
export function returnLabel(path: string): string {
  const chart = /^\/chart(?:\/([^/?#]+))?/.exec(path);
  if (!chart) return 'Back';
  return chart[1] ? `Back to chart · ${decodeURIComponent(chart[1])}` : 'Back to chart';
}
