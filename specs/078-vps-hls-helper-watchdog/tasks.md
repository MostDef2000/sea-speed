# Delivery Tasks: VPS HLS helper watchdog

- Specification: specs/078-vps-hls-helper-watchdog/spec.md
- Issue: #335
- Status: Source implementation

## Delivery tasks

- T-001 [x] Confirm main 45ec10b, SDD prefix 078, Scope and OUTCOME APPROVED.
- T-002 [x] Fix helper _camera1_hls_sequence: add -L to curl.
- T-003 [x] Fix watchdog _hls_sequence: add -L to curl.
- T-004 [x] Verify py_compile, validate_repo, validate_sdd, manual curl -L.
- T-005 [ ] Open PR with Change Contract VPS REQUIRED.

## Requirements traceability

- AC-001 | Task: T-002,T-003 | Evidence: curl -L finds media sequence | Coverage: COVERED
- AC-002 | Task: T-002,T-003 | Evidence: py_compile PASS | Coverage: COVERED
- AC-003 | Task: T-004 | Evidence: validate_repo PASS | Coverage: COVERED
- AC-004 | Task: T-005 | Evidence: PR Change Contract | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current — helper/watchdog curl -L fix recorded.
- [x] Exact changed-file scope verified — diff limited to two helper files and 078 spec.
- [x] Required tests and evidence complete — py_compile, validate_repo/sdd, manual curl -L PASS.
- [ ] Required CI green — PR exact head must pass PR Validation and Quality, then exact-main Quality.
- [ ] Exact-green-head merge complete — merge only after fresh base/head gate.
- [x] Deployment state resolved — PR performs no deployment; VPS contour REQUIRED, autonomous post-merge.
- [x] Runtime acceptance resolved — fix makes healthy HLS verifiable.
- [x] Risks resolved or explicitly accepted — Risk profile NOT REQUIRED.
- [x] Waivers resolved or current — no waiver.
- [x] Deferred work recorded — no deferred work; next is PR merge and autonomous deploy.

## Completion gate

DONE forbidden until exact-head PR Validation and Quality pass, exact green head merges, and exact-main Quality succeeds.
