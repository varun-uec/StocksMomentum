# ADR-005: Strategy as Versioned JSON Config + Rule Registry

**Status:** Accepted

## Context
The platform must support multiple screening methodologies (Minervini first) and frequent tuning of thresholds/weights, **without** code changes or redesign for each variation.

## Decision
Model a **Strategy** as versioned JSON configuration (enabled engines, rule sets, thresholds, weights, gates, scoring weights), validated by a `StrategyConfig` Pydantic model, stored in the `strategies` table and hashed to `config_hash`. **Rules** self-register in a `RuleRegistry` (`rule_id → Rule`). A `StrategyEngine` orchestrates engines→rules→scoring→ranking from the config.

## Consequences
- Changing thresholds/weights = config edit. Adding a rule = one class + registry entry. Adding a strategy = a new JSON row. No core redesign (NFR-6/8).
- `config_hash` participates in run identity → reproducibility (ADR-009).
- Requires disciplined config validation to avoid invalid strategies.

## Alternatives considered
- **Hard-coded strategy logic:** rejected — violates the strategy-agnostic requirement and maintainability goals.
- **Rules-as-code only (no config):** rejected — every tweak needs a deploy.
