# Implementation Plan: [FEATURE NAME]

- Specification: specs/[NNN-feature-slug]/spec.md
- Issue: #[ISSUE]
- Status: Draft

## Architecture

[Describe the smallest architecture that satisfies the specification.]

## Decisions

### D-001 - [decision]

- Decision: [what was chosen]
- Reason: [why]
- Alternatives rejected: [what/why]

## Affected contours

- Repository: [paths/domains]
- VPS: [NONE or impact]
- Ubuntu worker/relay: [NONE or impact]
- Windows worker/AI: [NONE or impact]
- Public interfaces: [NONE or impact]

## Validation

- Static/CI: [checks]
- Integration: [checks]
- Runtime acceptance: [observable product evidence or NOT REQUIRED]

## Risk profile

- Risk profile: [REQUIRED/NOT REQUIRED]

When REQUIRED, add at least one complete row. Probability and impact are 1-5; score is their product.

- RISK-001 | Category: [TECH/SEC/PERF/DATA/BUS/OPS] | Probability: [1-5] | Impact: [1-5] | Score: [P*I] | Mitigation: [control] | Validation: [test/evidence] | Residual risk: [LOW/MEDIUM/HIGH or explanation] | Owner: [owner] | Status: [OPEN/MITIGATED/ACCEPTED/CLOSED]

## Test design

- TEST-001 | Covers: [AC-001/RISK-001/etc.] | Level: [unit/integration/end-to-end/runtime-manual] | Priority: [P0/P1/P2/P3] | Evidence: [test path or observable runtime evidence]

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

Use `PRODUCTION_LEARNING`, `ARCHITECTURE_PIVOT`, or `MATERIAL_SCOPE_CHANGE` when applicable and record the concrete impacts/follow-up. Material Outcome/scope/protected-boundary change still requires normal reauthorization.

## Deployment transaction audit

Required when the change affects deployment/release execution, a deploy workflow, declares any runtime deployment `REQUIRED`, or corrects a `PRODUCTION_LEARNING`. Record exactly one row for every transaction stage. For non-applicable work, this section may remain as template guidance and is not machine-required.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: after admission evidence is corrected | Rollback: NOT REQUIRED because mutation has not started | Evidence: admission result
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: after prerequisite is corrected | Rollback: NOT REQUIRED because mutation has not started | Evidence: prerequisite result
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: [state] | Retry: [safe retry rule] | Rollback: [rollback rule] | Evidence: [mutation evidence]
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: [state] | Retry: [safe retry rule] | Rollback: [rollback rule] | Evidence: [verification evidence]
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: [state] | Retry: [safe retry rule] | Rollback: [rollback rule] | Evidence: [persisted state evidence]
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime state preserved | Retry: independently after deployment | Rollback: NOT REQUIRED solely for housekeeping failure | Evidence: warning or cleanup evidence
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime state unchanged but acceptance unresolved | Retry: recollect evidence if safe | Rollback: based on runtime evidence, not evidence transport alone | Evidence: exact deployment evidence
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: [state] | Retry: [safe recovery rule] | Rollback: [secondary recovery/escalation] | Evidence: rollback health and identity evidence

When `Trigger: PRODUCTION_LEARNING`, also record concrete review evidence:

- Adjacent-stage review: COMPLETE
- Production-learning root cause: [root cause]
- Production-learning adjacent-stage findings: [what was checked beyond the failing line]

## Rollout and rollback

- Rollout: [order]
- Rollback: [target/decision boundary]

## Runtime feedback

- Actual architecture after acceptance: PENDING
- Differences from plan: NONE YET
- Deferred cleanup: NONE YET
