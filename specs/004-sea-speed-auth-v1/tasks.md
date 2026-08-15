# Tasks: Sea Speed Auth v1

- Specification: specs/004-sea-speed-auth-v1/spec.md
- Plan: specs/004-sea-speed-auth-v1/plan.md
- Issue: #115
- Runtime topology Issue: #122

## Delivery tasks

- [x] Define invite-only Authentik security outcome and protected `/sea-speed/**` namespace.
- [x] Relocate production Authentik/PostgreSQL to Ubuntu Worker under Issue #122.
- [x] Implement/review private Authentik origin and exact-peer Worker M2M boundary.
- [x] Implement reproducible nginx split-layout/canonical-host/outpost cutover corrections.
- [x] Deploy accepted application/header identity corrections under separate exact-SHA authorization.
- [x] Diagnose and remediate missing Authentik system scope mappings without weakening nginx/private boundaries.
- [x] Complete authenticated browser acceptance for trusted username and Camera 1.
- [x] Complete bounded fail-closed dependency test and recovery (`FAIL_CLOSED_TEST=PASS`).
- [x] Close runtime topology Issue #122 completed.
- [ ] Parent Issue #115 remains open for any explicitly outstanding/deferred parent-backlog items; do not infer closure from core boundary acceptance.

## Completion gate

- [x] Worker-hosted Authentik/private origin accepted.
- [x] Public `/` remains available.
- [x] `/sea-speed/**` is protected and fail-closed.
- [x] `/cams/**` remains retired.
- [x] Forged Authentik headers do not bypass protection.
- [x] Trusted username/browser/Camera 1 acceptance passed.
- [x] Core Auth v1 runtime-security boundary verdict: accepted.
- [ ] Parent Issue #115 GitHub state: OPEN (audit/backlog fact, not a failed core runtime gate).
