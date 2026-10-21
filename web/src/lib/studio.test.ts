import { describe, expect, it } from 'vitest';
import {
  checkParam,
  editable,
  lineage,
  problems,
  scratchConfig,
  setRule,
  toggleRule,
  variantProblems,
  variantRequest,
  type VariantForm,
  joinableFamilies,
  type Family,
  type RuleRegistry,
} from './studio';

const registry: RuleRegistry = {
  version: 'abc',
  max_weight: '10',
  engines: ['trend_template', 'volume_accumulation'],
  engines_without_rules: [],
  rules: [
    {
      rule_id: 'tt_rs_rating_min',
      engine_id: 'trend_template',
      meaning: 'RS rating at or above a floor.',
      note: null,
      params: [
        { name: 'min', kind: 'number', unit: 'RS rating (1-99)', default: '70', meaning: 'Lowest rating.', minimum: '1', maximum: '99', choices: [] },
      ],
    },
    {
      rule_id: 'risk_extension',
      engine_id: 'volume_accumulation',
      meaning: 'x',
      note: null,
      params: [
        { name: 'ma', kind: 'choice', unit: 'sessions', default: '50', meaning: 'x', minimum: null, maximum: null, choices: ['50', '150', '200'] },
        { name: 'n', kind: 'integer', unit: 'sessions', default: '5', meaning: 'x', minimum: '1', maximum: '10', choices: [] },
      ],
    },
  ],
};

describe('studio form', () => {
  it('checks parameters as the server does', () => {
    const [rs] = registry.rules[0].params;
    const [ma, n] = registry.rules[1].params;
    expect(checkParam(rs, '80')).toBeNull();
    expect(checkParam(rs, 150)).toMatch('1–99');
    expect(checkParam(rs, '')).toMatch('number');
    expect(checkParam(n, '2.5')).toMatch('whole');
    expect(checkParam(ma, '150')).toBeNull();
    expect(checkParam(ma, '100')).toMatch('50, 150, 200');
  });

  it('adds a rule with its defaults, edits it and reports problems', () => {
    let config = scratchConfig(registry, 'mine');
    expect(config.engines.map((e) => e.enabled)).toEqual([false, false]);
    config = toggleRule(config, registry.rules[0], true);
    expect(config.engines[0].rules).toEqual([{ id: 'tt_rs_rating_min', weight: '1', gate: false, params: { min: '70' } }]);
    config = setRule(config, 'trend_template', 'tt_rs_rating_min', { param: ['min', '120'], weight: '11' });
    expect(problems(config, registry)).toEqual({
      'trend_template.tt_rs_rating_min': 'Allowed: 0–10.',
      'trend_template.tt_rs_rating_min.min': 'Allowed: 1–99 RS rating (1-99).',
    });
    config = toggleRule(config, registry.rules[0], false);
    expect(config.engines[0].rules).toEqual([]);
    expect(problems({ ...config, name: ' ' }, registry)).toEqual({ name: 'Give the strategy a name.' });
  });

  it('never sends the fixed sections or the version', () => {
    const sent = editable({ name: 'a', version: 3, universe: {}, ranking: {}, indicators: {}, benchmark_index: 'X', engines: [] }, 'b');
    expect(sent).toEqual({ name: 'b', engines: [] });
  });
});

describe('lineage', () => {
  const member = (hash: string, parent: string | null) => ({
    config_hash: hash, name: 'n', version: 1, family_id: 1, parent_config_hash: parent, config: {},
  });
  it('orders members under their parents from a strategy file', () => {
    const family: Family = {
      id: 1, hypothesis: 'h', root_config_hash: 'file', root: 'builtin', created_at: '',
      members: [member('a', 'file'), member('b', 'a'), member('c', 'file'), member('d', 'b')],
    };
    expect(lineage(family).map(({ member: m, depth }) => `${m.config_hash}${depth}`)).toEqual(['a0', 'b1', 'd2', 'c0']);
  });
  it('puts a scratch root first', () => {
    const family: Family = {
      id: 1, hypothesis: 'h', root_config_hash: 'r', root: 'scratch', created_at: '',
      members: [member('r', null), member('x', 'r')],
    };
    expect(lineage(family).map(({ member: m, depth }) => `${m.config_hash}${depth}`)).toEqual(['r0', 'x1']);
  });
});

describe('experiment-page handoff', () => {
  const form: VariantForm = {
    parentHash: 'a'.repeat(64),
    name: ' rs-floor ',
    overrides: [
      { parameter_path: 'trend_template.tt_rs_rating_min.params.min', value: ' 60 ' },
      { parameter_path: '', value: '' },
    ],
    mode: 'new',
    hypothesis: ' A lower RS floor keeps more winners. ',
    familyId: null,
    confirmed: false,
  };

  it('sends only used overrides, trimmed, with a stated hypothesis', () => {
    expect(variantProblems(form)).toEqual([]);
    expect(variantRequest(form)).toEqual({
      parent_config_hash: 'a'.repeat(64),
      variant_name: 'rs-floor',
      overrides: [{ parameter_path: 'trend_template.tt_rs_rating_min.params.min', value: '60' }],
      hypothesis: 'A lower RS floor keeps more winners.',
      hypothesis_confirmed: false,
    });
  });

  it('blocks a vague hypothesis and an unconfirmed family', () => {
    expect(variantProblems({ ...form, hypothesis: 'short' })).toEqual(['State the hypothesis in at least 10 characters.']);
    const join: VariantForm = { ...form, mode: 'existing', familyId: 3 };
    expect(variantProblems(join)).toEqual(["Confirm that the family's hypothesis covers this variant."]);
    expect(variantRequest({ ...join, confirmed: true })).toMatchObject({ family_id: 3, hypothesis_confirmed: true });
    expect(variantRequest({ ...join, confirmed: true })).not.toHaveProperty('hypothesis');
  });

  it('lists only families rooted at the base strategy', () => {
    const fam = (id: number, root: string) => ({ id, root_config_hash: root }) as Family;
    expect(joinableFamilies([fam(1, 'x'), fam(2, 'y')], 'y').map((f) => f.id)).toEqual([2]);
  });
});
