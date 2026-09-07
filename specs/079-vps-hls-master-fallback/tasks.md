# Delivery Tasks: VPS HLS master fallback

- Specification: specs/079-vps-hls-master-fallback/spec.md
- Issue: #335
- Status: Source implementation

## Delivery tasks

- T-001 [x] Confirm main 43e408a, SDD 079, Scope and OUTCOME APPROVED.
- T-002 [x] Fix helper _camera1_hls_sequence to return 0 for #EXTM3U.
- T-003 [x] Fix watchdog _hls_sequence similarly.
- T-004 [x] Fix advancing 0,0 => True in both.
- T-005 [x] Verify py_compile, validate_repo/sdd, manual curl master.
- T-006 [ ] Open PR with Change Contract VPS REQUIRED.

## Requirements traceability

- AC-001 | Task: T-002,T-003 | Evidence: master returns 0 | Coverage: COVERED
- AC-002 | Task: T-002 | Evidence: media returns sequence | Coverage: COVERED
- AC-003 | Task: T-005 | Evidence: py_compile PASS | Coverage: COVERED
- AC-004 | Task: T-006 | Evidence: PR Change Contract | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current — master fallback fix recorded.
- [x] Exact changed-file scope verified — diff limited to two helper files and 079 spec.
- [x] Required tests and evidence complete — py_compile, validate_repo/sdd, manual curl master PASS.
- [ ] Required CI green — PR exact head must pass PR Validation and Quality, then exact-main Quality.
- [ ] Exact-green-head merge complete — merge only after fresh base/head gate.
- [x] Deployment state resolved — PR no deployment; VPS contour REQUIRED, autonomous post-merge.
- [x] Runtime acceptance resolved — fix makes master verifiable.
- [x] Risks resolved or explicitly accepted — Risk profile NOT REQUIRED.
- [x] Waivers resolved or current — no waiver.
- [x] Deferred work recorded — no deferred work; next is PR merge and autonomous deploy.

## Completion gate

DONE forbidden until exact-head PR Validation and Quality pass, exact green head merges, and exact-main Quality succeeds.
