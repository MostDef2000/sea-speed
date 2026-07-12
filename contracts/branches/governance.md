# Branch Contract: Governance

Version: 1.0.0
Status: Active
Role: Governance Agent

## Scope

- repository structure;
- contracts and decision records;
- architecture and README;
- skills compatibility entrypoints;
- approval, branch, review and release policy.

## Rules

- Do not change runtime source files unless separately approved.
- Changes under `skills/**` require `SKILL UPDATE APPROVED`.
- Durable behavior changes must be recorded in `docs/decision_records/`.
- Contracts are canonical; skills must not become a conflicting second source of truth.
- Governance-only work does not require VPS deployment or Windows worker update.

## Validation

Verify links, contract priority, consistent state names, release applicability, absence of runtime changes and absence of claims that unimplemented automation already exists.