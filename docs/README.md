# Momentum25 documentation

All project documentation lives in this folder. Start with `current/`.

## Read first

| Page | Answers |
|---|---|
| [current/architecture.md](current/architecture.md) | What runs, how the layers fit, where the code differs from the approved ADD |
| [current/design.md](current/design.md) | How the screener and the backtest decide: pipeline, rules, gates, scores, determinism |
| [current/capabilities.md](current/capabilities.md) | What the product does: every API endpoint, web page and CLI command |
| [current/state.md](current/state.md) | Where things stand: checks, delivery record, research verdicts, open defects, data gaps |
| [current/keyboard-shortcuts.md](current/keyboard-shortcuts.md) | Every key the chart workspace answers |

`current/` was verified against the code on 2026-10-18. When the code changes, update it in the same commit.

## Folders

| Folder | Role | Changes how |
|---|---|---|
| [architecture/](architecture/) | Approved blueprint: [ADD](architecture/ADD.md), [Implementation Spec](architecture/IMPLEMENTATION_SPEC.md), [ADRs](architecture/adr/), [strategy configs](architecture/strategies/), and the Wickstreet [design record](architecture/design-record.md) (append only) | Only by approved amendment or new ADR. The API reads `strategies/` at startup — do not move it. |
| [current/](current/) | As-built view | Kept in step with the code |
| [operations/](operations/) | Runbooks: deployment, backup, production readiness | When operations change |
| [research/](research/) | Research reports and the frozen dataset spec, dated | Append only. New report per study. |
| [history/](history/) | Point-in-time audits, plans and the backtest Builder/Reviewer loop | Never edited. Evidence only. |
| [ENGINEERING_GUIDELINES.md](ENGINEERING_GUIDELINES.md) | Engineering, quantitative and product principles | Rarely |

Outside this folder: [README.md](../README.md) (run the app), [CLAUDE.md](../Claude.md) (engineering rules for agents), [backend/README.md](../backend/README.md) (backend dev loop), `.claude/agents/` (agent definitions).

## Precedence

When documents conflict, CLAUDE.md sets the order: ADD → ADRs → Implementation Spec → CLAUDE.md → task → code. `current/` describes the code; it does not override the ADD. Its [drift table](current/architecture.md#drift-from-the-add) lists where the two disagree.

## History index

| Record | What it is |
|---|---|
| [history/audits/2026-08-09-functional-audit.md](history/audits/2026-08-09-functional-audit.md) | Full app audit against real data, diagnosis only |
| [history/audits/2026-08-11-ui-ux-audit.md](history/audits/2026-08-11-ui-ux-audit.md) | UI/UX audit, fixes applied |
| [history/audits/2026-08-15-functional-audit.md](history/audits/2026-08-15-functional-audit.md) | Comprehensive functional audit, F1–F20 |
| [history/audits/2026-08-15-ui-ux-audit.md](history/audits/2026-08-15-ui-ux-audit.md) | UI/UX recommendations against an Investing.com benchmark, not applied |
| [history/audits/2026-10-18-m10-stack-spike-report.md](history/audits/2026-10-18-m10-stack-spike-report.md) | Wickstreet M10: Vite spike evidence (S1–S7), security-boundary tests, defects fixed |
| [history/audits/2026-10-18-m11-vertical-slice-report.md](history/audits/2026-10-18-m11-vertical-slice-report.md) | Wickstreet M11 review gate: Find → Analyse → Draw → Restore, NFR-11 results, defects fixed, defaults to confirm |
| [history/plans/2026-08-10-unified-analysis-screen-plan.md](history/plans/2026-08-10-unified-analysis-screen-plan.md) | Plan and user decisions for the analysis screen (shipped) |
| [history/plans/2026-08-10-signal-engine-proposal.md](history/plans/2026-08-10-signal-engine-proposal.md) | Open proposal: signals as a scoring engine |
| [history/plans/2026-10-18-wickstreet-milestones.md](history/plans/2026-10-18-wickstreet-milestones.md) | Wickstreet M9–M16: dependencies and exit criteria (proposed) |
| [history/plans/2026-10-18-m11-vertical-slice-plan.md](history/plans/2026-10-18-m11-vertical-slice-plan.md) | M11 Find → Analyse → Draw → Restore: design, changes, tests (proposed) |
| [history/plans/2026-10-18-m9-reference-study.md](history/plans/2026-10-18-m9-reference-study.md) | Wickstreet M9: capability inventory, parity matrix, reuse matrix, wireframes (proposed) |
| [history/plans/2026-10-22-wickstreet-2/](history/plans/2026-10-22-wickstreet-2/README.md) | Wickstreet 2.0 blueprint: fundamentals, funds, ETFs, unified screener, scorecards, portfolio; data-source feasibility; roadmap (proposed, with [ADD A2](architecture/ADD-amendment-A2.md) and ADR-016 to ADR-021) |
| [history/backtest-loop/](history/backtest-loop/) | Backtest brief (ground truth for `domain/backtest/`), addenda, loop protocol, round-by-round findings |
| [history/autonomous-audit/](history/autonomous-audit/) | 2026-08-18 six-batch audit: findings, fixes, verification, final report |

Removed on 2026-10-18 as superseded (recoverable from git at `f492f81`): `capabilities-summary.md`, `Momentum25_Autonomous_Review_Build_Loop_Prompt.md`, `docs/momentum25-backlog.md`, `docs/2026-08-09-functional-audit-plan.md`, `docs/2026-08-10-ui-ux-audit-plan.md`, `autonomous-audit/AUDIT_PLAN.md`, `autonomous-audit/CAPABILITY_REGISTRY.md`. Their live content is in `current/`.
