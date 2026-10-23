import { test as base, expect, type Page, type Route } from '@playwright/test';

/** A fund with ten years of NAVs in the local snapshot (Parag Parikh Flexi Cap Direct Growth). */
export const FUND = '122639';
export const OTHER = '120503';
export const API = 'http://localhost:8000/api/v1/mf';

interface StoredRecord {
  id: string;
  kind: string;
  name: string;
  body: unknown;
  schema_version: number;
  version: number;
  created_at: string;
  updated_at: string;
  archived: boolean;
}

/**
 * An in-memory /workspace/records service with the real contract: If-Match is
 * required (428) and a stale version gets 412. Tests never write to the real
 * database. `forceConflict` makes the next PUT lose a race.
 */
export class WorkspaceMock {
  records: StoredRecord[] = [];
  forceConflict = false;
  private next = 1;

  async install(page: Page) {
    await page.route('**/api/v1/mf/workspace/records**', (route) => this.handle(route));
  }

  private json(route: Route, status: number, body: unknown, version?: number) {
    return route.fulfill({ status, contentType: 'application/json', headers: version ? { ETag: `"${version}"` } : {}, body: JSON.stringify(body) });
  }

  private handle(route: Route) {
    const req = route.request();
    const url = new URL(req.url());
    const id = url.pathname.split('/records/')[1];
    const now = new Date().toISOString();
    if (req.method() === 'GET' && !id) {
      const kind = url.searchParams.get('kind');
      const archived = url.searchParams.get('archived') === 'true';
      const list = this.records.filter((r) => (!kind || r.kind === kind) && r.archived === archived).sort((a, b) => b.updated_at.localeCompare(a.updated_at));
      return this.json(route, 200, list);
    }
    if (req.method() === 'POST') {
      const body = req.postDataJSON();
      const record: StoredRecord = { id: `00000000-0000-4000-8000-${String(this.next++).padStart(12, '0')}`, kind: body.kind, name: body.name.trim(), body: body.body ?? {}, schema_version: 1, version: 1, created_at: now, updated_at: now, archived: !!body.archived };
      this.records.push(record);
      return this.json(route, 201, record, 1);
    }
    const record = this.records.find((r) => r.id === id);
    if (!record) return this.json(route, 404, { title: 'unknown-record', detail: 'No such record.' });
    if (req.method() === 'GET') return this.json(route, 200, record, record.version);
    const ifMatch = req.headers()['if-match'];
    if (!ifMatch) return this.json(route, 428, { detail: 'Send If-Match.' });
    if (this.forceConflict || Number(ifMatch.replace(/"/g, '')) !== record.version) {
      this.forceConflict = false;
      record.version += 1;
      record.updated_at = now;
      return this.json(route, 412, { title: 'version-conflict', detail: `The record is at version ${record.version}.` });
    }
    const body = req.postDataJSON();
    Object.assign(record, { name: body.name.trim(), body: body.body, archived: !!body.archived, version: record.version + 1, updated_at: now });
    return this.json(route, 200, record, record.version);
  }
}

/**
 * Every test fails on a console error or an uncaught page error, and gets a
 * workspace mock. An HTTP error status is allowed only where a test expects it.
 */
export const test = base.extend<{ page: Page; workspace: WorkspaceMock; allowStatus: number[] }>({
  allowStatus: [[], { option: true }],
  page: async ({ page, allowStatus }, run) => {
    const problems: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !/Failed to load resource: the server responded with a status of \d{3}/.test(msg.text())) problems.push(`console: ${msg.text()}`);
    });
    page.on('response', (response) => {
      if (response.status() >= 400 && !allowStatus.includes(response.status())) problems.push(`HTTP ${response.status()}: ${response.url()}`);
    });
    page.on('pageerror', (err) => problems.push(`pageerror: ${err.message}`));
    await run(page);
    expect(problems, 'browser errors').toEqual([]);
  },
  // Automatic, so no test can reach the real /workspace store.
  workspace: [
    async ({ page }, run) => {
      const mock = new WorkspaceMock();
      await mock.install(page);
      await run(mock);
    },
    { auto: true },
  ],
});

export { expect };

/** Fails when the page scrolls sideways at the current viewport. */
export async function expectNoSideScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, 'page-level horizontal overflow in px').toBeLessThanOrEqual(1);
}
