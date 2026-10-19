import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { DocumentStore, type DocumentSpec } from './server-document';
import { mergeById } from './merge';

interface Body {
  drawings: { id: string; price: number }[];
}

const spec: DocumentSpec<Body> = {
  path: '/api/v1/drawings/TCS',
  label: 'Your drawings on TCS',
  defaults: () => ({ drawings: [] }),
  merge: (base, mine, theirs) => {
    const r = mergeById(base?.drawings ?? [], mine.drawings, theirs.drawings);
    return { mine: { drawings: r.mine }, theirs: { drawings: r.theirs }, conflicted: r.conflicts.length > 0 };
  },
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

/** A fake server holding one document; requests are recorded. */
function fakeServer(initial: { revision: number; body: Body } | null) {
  let doc = initial;
  const calls: { method: string; headers: Record<string, string>; body?: Body }[] = [];
  const http = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const body = init?.body ? (JSON.parse(String(init.body)) as Body) : undefined;
    calls.push({ method, headers, body });
    if (method === 'GET') return doc ? json(200, doc) : json(404, {});
    const ifMatch = headers['If-Match'];
    const create = headers['If-None-Match'] === '*';
    const ok = create ? doc === null : doc !== null && ifMatch === `"${doc.revision}"`;
    if (!ok) return json(412, { current: doc });
    doc = { revision: (doc?.revision ?? 0) + 1, body: body! };
    return json(create ? 201 : 200, doc);
  });
  return {
    http: http as unknown as typeof fetch,
    calls,
    get doc() {
      return doc;
    },
    /** Another window saves directly. */
    otherWindowSaves(body: Body) {
      doc = { revision: (doc?.revision ?? 0) + 1, body };
    },
  };
}

const settle = async () => {
  await vi.runAllTimersAsync();
};

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('DocumentStore', () => {
  test('a missing document loads as defaults and is created with If-None-Match: *', async () => {
    const server = fakeServer(null);
    const store = new DocumentStore(spec, server.http);
    await store.load();
    expect(store.getState()).toMatchObject({ status: 'saved', revision: null, body: { drawings: [] } });
    store.update(() => ({ drawings: [{ id: 'a', price: 1 }] }));
    expect(store.getState().status).toBe('unsaved');
    await settle();
    expect(server.calls.at(-1)?.headers['If-None-Match']).toBe('*');
    expect(store.getState()).toMatchObject({ status: 'saved', revision: 1 });
  });

  test('an edit made while a missing document loads is kept and creates it', async () => {
    const server = fakeServer(null);
    const store = new DocumentStore(spec, server.http);
    const loading = store.load();
    store.update(() => ({ drawings: [{ id: 'new', price: 1 }] }));
    expect(store.getState()).toMatchObject({ status: 'loading', body: { drawings: [{ id: 'new', price: 1 }] } });
    await loading;
    await settle();
    expect(server.doc).toEqual({ revision: 1, body: { drawings: [{ id: 'new', price: 1 }] } });
    expect(store.getState()).toMatchObject({ status: 'saved', revision: 1 });
  });

  test('an edit made while a saved document loads merges onto it, losing neither', async () => {
    const server = fakeServer({ revision: 4, body: { drawings: [{ id: 'old', price: 2 }] } });
    const store = new DocumentStore(spec, server.http);
    const loading = store.load();
    store.update((b) => ({ drawings: [...b.drawings, { id: 'new', price: 1 }] }));
    await loading;
    await settle();
    expect(server.calls.at(-1)?.headers['If-Match']).toBe('"4"');
    expect(server.doc?.body.drawings.map((d) => d.id).sort()).toEqual(['new', 'old']);
    expect(store.getState().status).toBe('saved');
  });

  test('an edit that changes nothing saves nothing', async () => {
    const server = fakeServer({ revision: 1, body: { drawings: [] } });
    const store = new DocumentStore(spec, server.http);
    const loaded = store.whenLoaded();
    await store.load();
    await loaded;
    store.update((b) => b);
    await settle();
    expect(store.getState().status).toBe('saved');
    expect(server.calls.filter((c) => c.method === 'PUT')).toHaveLength(0);
  });

  test('quick edits are debounced into one save that names the revision it saw', async () => {
    const server = fakeServer({ revision: 4, body: { drawings: [] } });
    const store = new DocumentStore(spec, server.http);
    await store.load();
    for (let i = 0; i < 5; i += 1) store.update((b) => ({ drawings: [...b.drawings, { id: `d${i}`, price: i }] }));
    await settle();
    const puts = server.calls.filter((c) => c.method === 'PUT');
    expect(puts).toHaveLength(1);
    expect(puts[0].headers['If-Match']).toBe('"4"');
    expect(server.doc?.body.drawings).toHaveLength(5);
  });

  test('a 412 on edits to different drawings merges and saves again, losing nothing', async () => {
    const server = fakeServer({ revision: 1, body: { drawings: [{ id: 'a', price: 1 }] } });
    const store = new DocumentStore(spec, server.http);
    await store.load();
    server.otherWindowSaves({ drawings: [{ id: 'a', price: 1 }, { id: 'theirs', price: 9 }] });
    store.update((b) => ({ drawings: [...b.drawings, { id: 'mine', price: 5 }] }));
    await settle();
    expect(server.doc).toEqual({
      revision: 3,
      body: { drawings: [{ id: 'a', price: 1 }, { id: 'theirs', price: 9 }, { id: 'mine', price: 5 }] },
    });
    expect(store.getState()).toMatchObject({ status: 'saved', revision: 3, conflict: null });
  });

  test('a 412 on the same drawing waits for the user, then saves the chosen side', async () => {
    const server = fakeServer({ revision: 1, body: { drawings: [{ id: 'a', price: 1 }] } });
    const store = new DocumentStore(spec, server.http);
    await store.load();
    server.otherWindowSaves({ drawings: [{ id: 'a', price: 2 }] });
    store.update(() => ({ drawings: [{ id: 'a', price: 3 }] }));
    await settle();
    expect(store.getState().status).toBe('conflict');
    expect(store.getState().conflict).toEqual({ mine: { drawings: [{ id: 'a', price: 3 }] }, theirs: { drawings: [{ id: 'a', price: 2 }] } });
    expect(server.doc?.revision).toBe(2);

    store.update(() => ({ drawings: [] }));
    expect(store.getState().status).toBe('conflict');

    store.resolve('mine');
    await settle();
    expect(server.doc).toEqual({ revision: 3, body: { drawings: [{ id: 'a', price: 3 }] } });
    expect(store.getState().status).toBe('saved');
  });

  test('keeping theirs saves nothing new over the other window', async () => {
    const server = fakeServer({ revision: 1, body: { drawings: [{ id: 'a', price: 1 }] } });
    const store = new DocumentStore(spec, server.http);
    await store.load();
    server.otherWindowSaves({ drawings: [{ id: 'a', price: 2 }] });
    store.update(() => ({ drawings: [{ id: 'a', price: 3 }] }));
    await settle();
    store.resolve('theirs');
    await settle();
    expect(server.doc?.body).toEqual({ drawings: [{ id: 'a', price: 2 }] });
    expect(store.getState().body).toEqual({ drawings: [{ id: 'a', price: 2 }] });
  });

  test('an edit made while a save is in flight is saved next, on the new revision', async () => {
    const server = fakeServer({ revision: 1, body: { drawings: [] } });
    const store = new DocumentStore(spec, server.http);
    await store.load();
    store.update(() => ({ drawings: [{ id: 'a', price: 1 }] }));
    await vi.advanceTimersByTimeAsync(400); // first save starts
    store.update((b) => ({ drawings: [...b.drawings, { id: 'b', price: 2 }] }));
    await settle();
    const puts = server.calls.filter((c) => c.method === 'PUT');
    expect(puts.map((p) => p.headers['If-Match'])).toEqual(['"1"', '"2"']);
    expect(server.doc?.body.drawings.map((d) => d.id)).toEqual(['a', 'b']);
  });

  test('a network failure shows an error and retry saves', async () => {
    const server = fakeServer({ revision: 1, body: { drawings: [] } });
    let offline = true;
    const http = vi.fn((url: RequestInfo | URL, init?: RequestInit) =>
      offline && init?.method === 'PUT' ? Promise.reject(new Error('offline')) : server.http(url, init),
    ) as unknown as typeof fetch;
    const store = new DocumentStore(spec, http);
    await store.load();
    store.update(() => ({ drawings: [{ id: 'a', price: 1 }] }));
    await settle();
    expect(store.getState().status).toBe('error');
    offline = false;
    store.retry();
    await settle();
    expect(store.getState()).toMatchObject({ status: 'saved', revision: 2 });
  });
});
