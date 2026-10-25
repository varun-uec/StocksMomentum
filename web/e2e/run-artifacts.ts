import { randomUUID } from 'node:crypto';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

/** Each runner owns its assets and reports; a simultaneous build cannot remove its chunks. */
export function runArtifacts(suite: string) {
  // Workers inherit this value so their config uses the runner's directory too.
  const key = `WICKSTREET_${suite.toUpperCase()}_RUN_ID`;
  const id = process.env[key] ??= randomUUID();
  if (!/^[a-zA-Z0-9_-]+$/.test(id)) throw new Error(`${key} must contain only letters, numbers, _ or -`);
  const root = join(tmpdir(), `wickstreet-${suite}-${id}`);
  return { dist: join(root, 'dist'), results: join(root, 'test-results') };
}
