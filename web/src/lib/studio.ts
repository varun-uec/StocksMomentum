/**
 * Strategy Studio form logic (FR-25, ADR-014). Pure, so the page stays a view.
 *
 * The form is built from the rule registry (`GET /studio/rules`). A config
 * holds only what the registry declares: engines, rules, gates, parameters and
 * weights. The server copies the other sections from the parent.
 */

type Schemas = import('./api-schema').components['schemas'];
export type RuleRegistry = Schemas['RuleRegistryDTO'];
export type RuleSchema = Schemas['RuleSchemaDTO'];
export type ParamSpec = Schemas['ParamSpecDTO'];
export type Family = Schemas['FamilyDTO'];
export type StudioStrategy = Schemas['StudioStrategyDTO'];
export type Evaluation = Schemas['EvaluationDTO'];
export type ResultClass = Evaluation['result_class'];

export interface RuleEntry {
  id: string;
  weight: string;
  gate: boolean;
  params: Record<string, string | number>;
}

export interface EngineEntry {
  id: string;
  enabled: boolean;
  weight: string;
  gate: boolean;
  rules: RuleEntry[];
}

export interface StudioConfig {
  name: string;
  description?: string | null;
  engines: EngineEntry[];
  scoring?: { momentum_weights?: Record<string, string>; buy_setup_weights?: Record<string, string> };
  [section: string]: unknown;
}

/** Sections the registry does not declare; Studio v1 never sends them. */
export const FIXED_SECTIONS = ['universe', 'indicators', 'ranking', 'benchmark_index'] as const;

/** The three result classes in the order the Studio offers them, with their fixed labels. */
export const RESULT_CLASSES: { id: ResultClass; label: string }[] = [
  { id: 'screening', label: 'Screening Result' },
  { id: 'in_sample', label: 'Historical Research — In-Sample' },
  { id: 'out_of_sample', label: 'Out-of-Sample Evaluation' },
];

export function rulesFor(registry: RuleRegistry, engineId: string): RuleSchema[] {
  return registry.rules.filter((r) => r.engine_id === engineId);
}

/** A copy of `config` without the fixed sections and the server-set version. */
export function editable(config: Record<string, unknown>, name?: string): StudioConfig {
  const copy = structuredClone(config) as StudioConfig;
  for (const section of FIXED_SECTIONS) delete copy[section];
  delete copy.version;
  if (name !== undefined) copy.name = name;
  return copy;
}

/** A config written from scratch: every engine listed, none enabled, no rules. */
export function scratchConfig(registry: RuleRegistry, name: string): StudioConfig {
  return {
    name,
    engines: registry.engines.map((id) => ({ id, enabled: false, weight: '1', gate: false, rules: [] })),
  };
}

function mapEngine(config: StudioConfig, engineId: string, change: (e: EngineEntry) => EngineEntry): StudioConfig {
  const engines = config.engines.some((e) => e.id === engineId)
    ? config.engines
    : [...config.engines, { id: engineId, enabled: false, weight: '1', gate: false, rules: [] }];
  return { ...config, engines: engines.map((e) => (e.id === engineId ? change(e) : e)) };
}

export function setEngine(config: StudioConfig, engineId: string, patch: Partial<Omit<EngineEntry, 'id' | 'rules'>>): StudioConfig {
  return mapEngine(config, engineId, (e) => ({ ...e, ...patch }));
}

/** Add a rule with its registry defaults, or remove it. */
export function toggleRule(config: StudioConfig, schema: RuleSchema, on: boolean): StudioConfig {
  return mapEngine(config, schema.engine_id, (e) => {
    const rules = e.rules.filter((r) => r.id !== schema.rule_id);
    if (!on) return { ...e, rules };
    const params = Object.fromEntries(schema.params.map((p) => [p.name, p.default]));
    return { ...e, rules: [...rules, { id: schema.rule_id, weight: '1', gate: false, params }] };
  });
}

export function setRule(
  config: StudioConfig,
  engineId: string,
  ruleId: string,
  patch: Partial<Pick<RuleEntry, 'weight' | 'gate'>> & { param?: [string, string] },
): StudioConfig {
  return mapEngine(config, engineId, (e) => ({
    ...e,
    rules: e.rules.map((r) => {
      if (r.id !== ruleId) return r;
      const { param, ...rest } = patch;
      return { ...r, ...rest, params: param ? { ...r.params, [param[0]]: param[1] } : r.params };
    }),
  }));
}

/** The same check the server makes, so the form can say what is wrong before saving. */
export function checkParam(spec: ParamSpec, raw: string | number): string | null {
  const text = String(raw).trim();
  const value = Number(text);
  if (text === '' || !Number.isFinite(value)) return 'Enter a number.';
  if (spec.kind === 'integer' && !Number.isInteger(value)) return 'Enter a whole number.';
  if (spec.kind === 'choice') {
    return spec.choices.map(Number).includes(value) ? null : `Choose ${spec.choices.join(', ')}.`;
  }
  const lo = spec.minimum === null ? -Infinity : Number(spec.minimum);
  const hi = spec.maximum === null ? Infinity : Number(spec.maximum);
  return value >= lo && value <= hi ? null : `Allowed: ${spec.minimum}–${spec.maximum} ${spec.unit}.`;
}

export function checkWeight(raw: string, max: string): string | null {
  const value = Number(raw);
  return raw.trim() !== '' && value >= 0 && value <= Number(max) ? null : `Allowed: 0–${max}.`;
}

/** Every problem in the form, keyed `engine` or `engine.rule` or `engine.rule.param`. */
export function problems(config: StudioConfig, registry: RuleRegistry): Record<string, string> {
  const found: Record<string, string> = {};
  for (const engine of config.engines) {
    const weight = checkWeight(engine.weight, registry.max_weight);
    if (weight) found[engine.id] = weight;
    for (const rule of engine.rules) {
      const schema = registry.rules.find((r) => r.rule_id === rule.id);
      const ruleWeight = checkWeight(rule.weight, registry.max_weight);
      if (ruleWeight) found[`${engine.id}.${rule.id}`] = ruleWeight;
      for (const spec of schema?.params ?? []) {
        const error = checkParam(spec, rule.params[spec.name] ?? spec.default);
        if (error) found[`${engine.id}.${rule.id}.${spec.name}`] = error;
      }
    }
  }
  if (!config.name.trim()) found.name = 'Give the strategy a name.';
  return found;
}

/** Members in lineage order: each one after its parent, indented by depth. */
export function lineage(family: Family): { member: StudioStrategy; depth: number }[] {
  const children = new Map<string, StudioStrategy[]>();
  for (const m of family.members) {
    const parent = m.parent_config_hash ?? family.root_config_hash;
    children.set(parent, [...(children.get(parent) ?? []), m]);
  }
  const out: { member: StudioStrategy; depth: number }[] = [];
  const walk = (hash: string, depth: number) => {
    for (const child of children.get(hash) ?? []) {
      if (child.config_hash === hash) continue; // a scratch root is its own parent
      out.push({ member: child, depth });
      walk(child.config_hash, depth + 1);
    }
  };
  if (family.root === 'scratch') {
    const root = family.members.find((m) => m.config_hash === family.root_config_hash);
    if (root) {
      out.push({ member: root, depth: 0 });
      walk(root.config_hash, 1);
    }
  } else {
    walk(family.root_config_hash, 0);
  }
  return out;
}

/** True when the family has already queued its one Out-of-Sample Evaluation on any window. */
export function holdoutSpent(evaluations: Evaluation[]): boolean {
  return evaluations.some((e) => e.result_class === 'out_of_sample');
}

export function labelOf(id: ResultClass): string {
  return RESULT_CLASSES.find((c) => c.id === id)?.label ?? id;
}
