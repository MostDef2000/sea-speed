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

## Rollout and rollback

- Rollout: [order]
- Rollback: [target/decision boundary]

## Runtime feedback

- Actual architecture after acceptance: PENDING
- Differences from plan: NONE YET
- Deferred cleanup: NONE YET
