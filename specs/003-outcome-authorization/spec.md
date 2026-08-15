# Feature Specification: Outcome Authorization

- Feature: 003-outcome-authorization
- Issue: #107
- Status: Accepted / active governance model

## Product outcome

An operator approves a bounded product outcome once; the Sea Speed Delivery Orchestrator executes reversible repository delivery through exact-green-head merge without repetitive commit/merge prompts while approved scope and protected boundaries remain unchanged.

## User scenarios

1. `OUTCOME APPROVED` after the Outcome Contract authorizes branch/source/PR/CI remediation/exact-green-head merge.
2. In-scope CI remediation continues without reauthorization.
3. Material scope/security/schema/destructive/protected-runtime change requires fresh authorization.
4. Production always requires a separate exact-SHA production safety envelope.

## Requirements

- Outcome Contract precedes source authorization.
- New Change Contracts use `OUTCOME APPROVED`.
- Fresh base/head, exact scope, required CI, zero unresolved threads and expected-head merge remain mandatory.
- Source authorization never authorizes production.
- Historical legacy `COMMIT APPROVED` / `MERGE APPROVED` evidence remains readable as audit history but is not a valid source authorization for new PRs after Stage B convergence.
- Connector-only publication, secrets/provenance/runtime-acceptance rules remain unchanged.

## Acceptance criteria

- Issue #107 is closed completed.
- Current validator accepts `OUTCOME APPROVED` and rejects legacy authorization in a new Change Contract.
- Material boundary drift fails admission.
- Control-plane work requires no production envelope; runtime work does.
- No runtime mutation occurred for the governance transition.

## Compatibility and boundaries

Historical Issue #107 and transition PR retain their original legacy-bridge evidence. Stage B changes only the active admission model; it does not rewrite that history.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED.
- Governance acceptance: COMPLETE; Outcome Authorization is the active model for new work.
