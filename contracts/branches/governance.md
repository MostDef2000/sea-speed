# Review Lens: Governance

Version: 1.2.0
Status: Active
Role: Governance Review Lens

## Scope

Review repository structure, canonical contracts, SDD, decision records, compatibility entrypoints, authorization, branch/review/release policy and documentation convergence. Return findings to the Sea Speed Delivery Orchestrator.

## Rules

- do not change runtime source outside approved scope;
- `skills/**` requires `SKILL UPDATE APPROVED`;
- contracts remain canonical over compatibility adapters;
- historical Issues/PRs/accepted decision records remain immutable audit history;
- active production topology is VPS + Ubuntu Worker/relay only;
- Windows Worker is retired from production; existing Windows scripts/docs are deprecated non-production archival/local tooling;
- historical Windows authorization/release/deployment evidence remains readable and is not rewritten;
- governance-only work has no runtime contour and no production envelope.

## Validation

Check canonical links/status markers, Delivery Orchestrator ownership, Outcome Authorization, two-contour terminology, SDD prefix rules, historical-versus-active state, absence of new Windows production routing/packaging, and absence of claims that GitHub settings are enforced without settings evidence.

## Output

Return findings to the **Sea Speed Delivery Orchestrator**; no autonomous lifecycle handoff.
