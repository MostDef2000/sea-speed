# Delivery Tasks: VPS H264 cookieCheck fallback

- Specification: specs/077-vps-h264-cookiecheck-fallback/spec.md
- Issue: #335
- Status: Source implementation

## Delivery tasks

- T-001 [x] Confirm Issue #335 DONE, current main b3491ec, SDD prefix 077, visible six-field Scope and OUTCOME APPROVED.
- T-002 [x] Fix check_h264 in deploy/vps/sea-speed-auth-cutover.sh: add -L to curl to follow MediaMTX 302 ?cookieCheck=1.
- T-003 [x] Verify bash -n, validate_repo.py, validate_sdd.py pass; manual VPS curl -L PASS.
- T-004 [ ] Open linked PR with Change Contract (VPS REQUIRED, Ubuntu NOT REQUIRED, production safety envelope REQUIRED, VPS CONNECTOR, Ubuntu NOT APPLICABLE, operator actions 0).

## Requirements traceability

- AC-001 | Task: T-002 | Evidence: curl -L bare HLS follows 302 and grep PASS | Coverage: COVERED
- AC-002 | Task: T-002 | Evidence: curl ?cookieCheck=1 PASS preserved | Coverage: COVERED
- AC-003 | Task: T-003 | Evidence: bash -n passes | Coverage: COVERED
- AC-004 | Task: T-003 | Evidence: validate_repo.py passes | Coverage: COVERED
- AC-005 | Task: T-004 | Evidence: PR Change Contract declares VPS REQUIRED etc. | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current — #335 follow-up, single curl flag fix, risk and correct-course recorded.
- [x] Exact changed-file scope verified — diff limited to deploy/vps/sea-speed-auth-cutover.sh and 077 spec artifacts.
- [x] Required tests and evidence complete — bash -n, validate_repo.py, validate_sdd.py, manual VPS curl -L PASS.
- [ ] Required CI green — PR exact head must pass PR Validation and aggregate Quality, followed by exact-main Quality after merge.
- [ ] Exact-green-head merge complete — merge only after fresh base/head/scope/review gate with expected-head protection.
- [x] Deployment state resolved — this PR performs no deployment; VPS contour REQUIRED per policy, autonomous deploy post-merge.
- [x] Runtime acceptance resolved — no new runtime acceptance required; fix makes existing healthy HLS verifiable.
- [x] Risks resolved or explicitly accepted — Risk profile NOT REQUIRED; single flag, no host mutation.
- [x] Waivers resolved or current — no waiver active.
- [x] Deferred work recorded — no deferred work; next is PR merge and autonomous VPS deploy.

## Completion gate

DONE is forbidden until exact-head PR Validation and aggregate Quality pass on one head, exact green head merges with expected-head protection, and exact-main Quality succeeds.
