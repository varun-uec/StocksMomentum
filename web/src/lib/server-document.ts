/**
 * Saved documents on the server, with optimistic concurrency (ADR-013 §5).
 *
 * One store per document, shared by every component that reads it, so two
 * hooks on one page never race each other. Saves are debounced, one is in
 * flight at a time, and every save names the revision it builds on. A 412
 * means another window saved first: the store merges the two versions and
 * saves again, or, when both windows changed the same thing, waits for the
 * user to choose. It never overwrites silently.
 */

import { useSyncExternalStore } from 'react';

export type SaveStatus = 'loading' | 'saved' | 'unsaved' | 'saving' | 'conflict' | 'error';

export interface DocumentState<T> {
  status: SaveStatus;
  body: T;
  /** Server revision of the last confirmed save; null if never saved. */
  revision: number | null;
  savedAt: Date | null;
  /** Both candidate bodies while the user decides a conflict. */
  conflict: { mine: T; theirs: T } | null;
}

export interface MergeResult<T> {
  mine: T;
  theirs: T;
  conflicted: boolean;
}

export interface DocumentSpec<T> {
  /** API path, e.g. `/api/v1/drawings/RELIANCE`. */
  path: string;
  /** Names the owner's work in the conflict notice, e.g. "Your drawings on TCS". */
  label: string;
  defaults: () => T;
  /** Three-way merge used when a save returns 412. */
  merge: (base: T | null, mine: T, theirs: T) => MergeResult<T>;
}

interface ServerDocument<T> {
  revision: number;
  /** Null at revision 0: the document was never saved. That is a normal state, not an error. */
  body: T | null;
}

/** A never-saved document, whether the server says 404 (older servers) or revision 0. */
const neverSaved = <T>(doc: ServerDocument<T> | null): doc is null => doc === null || doc.body === null;

const SAVE_DELAY_MS = 400;

export class DocumentStore<T> {
  private state: DocumentState<T>;
  private base: T | null = null;
  private listeners = new Set<() => void>();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private inFlight = false;
  /** The owner edited before the first load finished; the load merges those edits in. */
  private editedWhileLoading = false;

  constructor(
    readonly spec: DocumentSpec<T>,
    private readonly http: typeof fetch = (...args) => fetch(...args),
  ) {
    this.state = { status: 'loading', body: spec.defaults(), revision: null, savedAt: null, conflict: null };
  }

  getState = (): DocumentState<T> => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  async load(): Promise<void> {
    try {
      const res = await this.http(this.spec.path, { cache: 'no-store' });
      if (res.status === 404) {
        this.loaded(null);
        return;
      }
      if (!res.ok) throw new Error(`${res.status}`);
      const doc = (await res.json()) as ServerDocument<T>;
      this.loaded(neverSaved(doc) ? null : doc);
    } catch {
      this.set({ status: 'error' });
    }
  }

  /**
   * Take the loaded version. Edits made while it loaded were made on the
   * defaults, so they merge onto it like another window's save: a drawing
   * placed the moment a chart appears is kept, and so is every saved one.
   */
  private loaded(doc: ServerDocument<T> | null): void {
    const theirs = (doc?.body as T | null | undefined) ?? this.spec.defaults();
    const revision = doc?.revision ?? null;
    if (doc) this.base = doc.body as T;
    if (!this.editedWhileLoading) {
      this.set({ status: 'saved', body: theirs, revision });
      return;
    }
    this.editedWhileLoading = false;
    const merged = this.spec.merge(this.spec.defaults(), this.state.body, theirs);
    if (merged.conflicted) {
      this.set({ revision, status: 'conflict', conflict: { mine: merged.mine, theirs: merged.theirs } });
      return;
    }
    this.set({ revision, body: merged.mine, status: 'unsaved' });
    this.schedule();
  }

  /** Resolves once the first load has finished, whatever its outcome. */
  whenLoaded(): Promise<void> {
    return new Promise((resolve) => {
      if (this.state.status !== 'loading') return resolve();
      const stop = this.subscribe(() => {
        if (this.state.status === 'loading') return;
        stop();
        resolve();
      });
    });
  }

  /**
   * Apply a local edit and schedule a save. Ignored while a conflict waits.
   * An edit that returns the body unchanged saves nothing. An edit made while
   * the document loads waits for the load (see `loaded`).
   */
  update(edit: (body: T) => T): void {
    if (this.state.status === 'conflict') return;
    const body = edit(this.state.body);
    if (body === this.state.body) return;
    if (this.state.status === 'loading') {
      this.editedWhileLoading = true;
      this.set({ body });
      return;
    }
    this.set({ body, status: 'unsaved' });
    this.schedule();
  }

  /** Settle a conflict with one side, then save it. */
  resolve(choice: 'mine' | 'theirs'): void {
    const conflict = this.state.conflict;
    if (!conflict) return;
    this.set({ body: conflict[choice], conflict: null, status: 'unsaved' });
    void this.save();
  }

  retry(): void {
    if (this.state.status === 'error') void (this.state.revision === null && !this.base ? this.load() : this.save());
  }

  /** Send any unsaved edit now, even while the page unloads. */
  flush(): void {
    if (this.state.status !== 'unsaved' || this.inFlight) return;
    if (this.timer) clearTimeout(this.timer);
    void this.http(this.spec.path, { ...this.request(this.state.body), keepalive: true }).catch(() => undefined);
  }

  private schedule(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.save(), SAVE_DELAY_MS);
  }

  private request(body: T): RequestInit {
    const precondition: Record<string, string> =
      this.state.revision === null ? { 'If-None-Match': '*' } : { 'If-Match': `"${this.state.revision}"` };
    return {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...precondition },
      body: JSON.stringify(body),
    };
  }

  private async save(): Promise<void> {
    if (this.inFlight) return;
    this.inFlight = true;
    const sent = this.state.body;
    this.set({ status: 'saving' });
    try {
      const res = await this.http(this.spec.path, this.request(sent));
      if (res.status === 412) {
        const problem = (await res.json()) as { current: ServerDocument<T> | null };
        this.rebase(problem.current);
        return;
      }
      if (!res.ok) throw new Error(`${res.status}`);
      const doc = (await res.json()) as ServerDocument<T>;
      this.base = doc.body as T;
      const changedMeanwhile = this.state.body !== sent;
      this.set({ revision: doc.revision, savedAt: new Date(), status: changedMeanwhile ? 'unsaved' : 'saved' });
      if (changedMeanwhile) this.schedule();
    } catch {
      this.set({ status: 'error' });
    } finally {
      this.inFlight = false;
    }
  }

  /** Another window saved first: merge onto its version, then save or ask. */
  private rebase(current: ServerDocument<T> | null): void {
    if (neverSaved(current)) {
      this.base = null;
      this.set({ revision: null, status: 'unsaved' });
      this.schedule();
      return;
    }
    const merged = this.spec.merge(this.base, this.state.body, current.body as T);
    this.base = current.body as T;
    if (merged.conflicted) {
      this.set({ revision: current.revision, status: 'conflict', conflict: { mine: merged.mine, theirs: merged.theirs } });
      return;
    }
    this.set({ revision: current.revision, body: merged.mine, status: 'unsaved' });
    this.schedule();
  }

  private set(patch: Partial<DocumentState<T>>): void {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((listener) => listener());
  }
}

const stores = new Map<string, DocumentStore<unknown>>();

export interface ConflictedDocument {
  path: string;
  label: string;
  resolve: (choice: 'mine' | 'theirs') => void;
}

let conflicted: ConflictedDocument[] = [];
const conflictListeners = new Set<() => void>();

/** Recompute the conflict list; a new array only when its members change. */
function refreshConflicts(): void {
  const now = [...stores.values()].filter((store) => store.getState().status === 'conflict');
  if (now.length === conflicted.length && now.every((store, i) => store.spec.path === conflicted[i].path)) return;
  conflicted = now.map((store) => ({
    path: store.spec.path,
    label: store.spec.label,
    resolve: (choice) => store.resolve(choice),
  }));
  conflictListeners.forEach((listener) => listener());
}

/** The shared store for one document; created and loaded on first use. */
export function documentStore<T>(spec: DocumentSpec<T>): DocumentStore<T> {
  let store = stores.get(spec.path) as DocumentStore<T> | undefined;
  if (!store) {
    store = new DocumentStore(spec);
    stores.set(spec.path, store as DocumentStore<unknown>);
    store.subscribe(refreshConflicts);
    void store.load();
  }
  return store;
}

/** Reload a document that was never saved here, e.g. after an import created it. */
export function reloadIfPristine(path: string): void {
  const store = stores.get(path);
  const state = store?.getState();
  if (store && state?.revision === null && state.status === 'saved') void store.load();
}

/** Every open document, so unsaved edits leave with the page. */
if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', () => stores.forEach((store) => store.flush()));
}

export function useServerDocument<T>(spec: DocumentSpec<T>): DocumentState<T> & {
  update: (edit: (body: T) => T) => void;
  retry: () => void;
} {
  const store = documentStore(spec);
  const state = useSyncExternalStore(store.subscribe, store.getState);
  return {
    ...state,
    update: (edit) => store.update(edit),
    retry: () => store.retry(),
  };
}

/** Every open document waiting for the owner to settle a conflict, on any screen. */
export function useConflictedDocuments(): ConflictedDocument[] {
  return useSyncExternalStore(
    (listener) => {
      conflictListeners.add(listener);
      return () => conflictListeners.delete(listener);
    },
    () => conflicted,
  );
}
