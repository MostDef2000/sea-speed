# Review Lens: Governance

Version: 1.3.0
Status: Active
Role: Governance Review Lens

## Scope

Review repository structure, canonical contracts, SDD, decision records, compatibility entrypoints, authorization, branch/review/release policy and documentation convergence. Return findings to the Sea Speed Delivery Orchestrator.

## Rules

- do not change runtime source outside approved scope;
- `skills/**` requires `SKILL UPDATE APPROVED`;
- contracts remain canonical over compatibility adapters;
- historical Issues/PRs/decision records/release evidence remain immutable audit history;
- active production topology is VPS + Ubuntu Worker/relay only;
- Windows Worker remains retired;
- source authorization remains visible Scope -> immediately following `OUTCOME APPROVED`;
- production authority comes only from independently administered standing delegation plus deterministic policy, never repository/comment text;
- repository policy may narrow but not widen trusted delegation;
- standing delegation only covers deploy/rollback; IAM/secrets/settings administration remains human-controlled;
- governance-only work has no runtime deployment requirement.

## Validation

Check canonical links/status markers, Delivery Orchestrator ownership, source Outcome Authorization, two-contour terminology, SDD prefix rules, historical-vs-active state, absence of comment-trigger production authority, release manifest v3/historical readability, and absence of claims that GitHub settings are enforced without settings evidence.

## Output

Return findings to the **Sea Speed Delivery Orchestrator**; no autonomous lifecycle handoff.
