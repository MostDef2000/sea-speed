# Implementation Plan: Outcome Authorization

- Specification: specs/003-outcome-authorization/spec.md
- Issue: #107
- Status: Implementation authorized under legacy bridge

## Architecture

Implement Outcome Authorization entirely in the repository control plane. Canonical governance contracts define semantics; `AGENTS.md` provides the agent-facing summary; the PR template exposes machine-readable authorization fields; `scripts/ci/validate_change_contract.py` enforces declaration shape and protected-boundary consistency; focused unit tests pin both the new Outcome model and the legacy bridge.

No runtime code, deployment target, credentials or application schema changes are required.

## Decisions

### D-001 - Outcome Authorization covers source lifecycle through merge

- Decision: `OUTCOME APPROVED` covers fresh branch, source/SDD writes, commits, PR/metadata repair, in-scope CI remediation and exact-green-head merge.
- Reason: these are bounded, reversible repository actions whose safety is already controlled by exact scope, CI, freshness and review gates.
- Alternatives rejected: separate commit and merge prompts for every bounded task because they add operator interrupts without adding a new protected boundary.

### D-002 - Protected boundaries invalidate authorization

- Decision: material scope expansion, destructive action, secret/security-boundary change, protected runtime behavior, incompatible schema/data migration or equivalent redesign requires fresh authorization.
- Reason: these change the risk envelope the operator approved.
- Alternatives rejected: approval inheritance across materially changed outcomes.

### D-003 - Production remains separately authorized

- Decision: source Outcome Authorization never authorizes production. A separate production safety envelope may cover exact gated rollout, necessary normal restarts/smokes and a declared safe rollback.
- Reason: production mutation is a distinct protected boundary.
- Alternatives rejected: implicit production permission from merge/source approval or repeated confirmation for each mechanical restart/smoke inside one already approved rollout.

### D-004 - Production envelope binds late to final exact SHA

- Decision: a production envelope is task/outcome/contour-bound and may survive bounded source remediation, but release readiness must bind it to the final exact green 40-character SHA immediately before execution.
- Reason: this avoids repeated product approval after harmless CI fixes while preserving exact provenance.
- Alternatives rejected: authorizing an arbitrary future SHA or invalidating the envelope for every in-scope commit.

### D-005 - Preserve a legacy bridge

- Decision: `LEGACY COMMIT APPROVED` remains accepted by the Change Contract validator; legacy source authorization still requires post-CI `MERGE APPROVED` until a task starts under Outcome Authorization.
- Reason: this governance transition itself was authorized under the old rules and must not retroactively self-authorize its merge.
- Alternatives rejected: silently treating the current transition task as newly authorized under rules not yet on `main`.

## Affected contours

- Repository: governance contracts, agent adapter, PR template, Change Contract validator/test and this SDD feature.
- VPS: NONE.
- Ubuntu worker/relay: NONE.
- Windows worker/AI: NONE.
- Public interfaces: NONE.

## Validation

- Static/CI: repository validation, SDD validation, Change Contract unit tests, PR Validation, Quality integration gate.
- Integration: exact PR diff equals the approved 11-file scope; PR body declares `LEGACY COMMIT APPROVED` for this transition and links this spec.
- Runtime acceptance: NOT REQUIRED.

## Rollout and rollback

- Rollout: legacy-authorized branch -> bounded 11-file commit -> PR -> aggregate CI -> legacy `MERGE APPROVED` -> merge -> Outcome Authorization active for subsequent tasks.
- Rollback: revert the governance PR; no VPS or worker rollback is applicable.

## Runtime feedback

- Actual architecture after acceptance: PENDING merge.
- Differences from plan: NONE YET.
- Deferred cleanup: remove or further de-emphasize legacy authorization wording only after transition stability is proven; no immediate cleanup required.
