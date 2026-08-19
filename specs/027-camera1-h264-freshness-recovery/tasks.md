# Delivery Tasks: Camera 1 H264 Freshness Recovery

- Specification: specs/027-camera1-h264-freshness-recovery/spec.md
- Issue: #226
- Status: Source implementation

## Delivery tasks

- T-001 [x] Confirm Issue #226 Task Brief, current `main`, unique SDD prefix `027`, visible six-field Scope and immediately following `OUTCOME APPROVED` source authorization.
- T-002 [x] Preserve the accepted Camera 1 topology, browser URL, Ubuntu relay, nginx/Auth boundary, HLS HTTP service and Water/Road worker ownership unchanged.
- T-003 [x] Add fixed local-HLS media-sequence sampling to the exact-source no-argument privileged helper.
- T-004 [x] Add healthy-HLS no-op behavior with no private-relay probe and no service restart.
- T-005 [x] For valid static HLS, require one decodable frame from the fixed private Ubuntu relay before any mutation.
- T-006 [x] Restart only `sea-speed-camera1-h264.service`, require it active, and require post-restart HLS media-sequence advancement.
- T-007 [x] Preserve unsupported-action rejection, exact-source bundle validation, fixed request schema, no-argument sudo boundary and `ARBITRARY_ROOT_EXECUTION=NO` contract.
- T-008 [x] Add focused tests for no-op, fixed restart, relay failure before restart, post-restart stale failure, forbidden service names, fixed constants and reconcile integration.
- T-009 [x] Prove accepted VPS `runtime_verified` state remains behind successful `run_auth_boundary`; no deploy-script source change is required for the narrow recovery design.
- T-010 [x] Update the protected Camera 1 H264 runbook and complete the linked `027` spec/plan/tasks quality layer, risk profile, correct-course record and eight-stage Deployment Transaction Audit.
- T-011 [x] Verify exact branch diff is an authorized subset, contains no secrets/runtime media and matches the PR Change Contract.
- T-012 [x] Open linked PR #227; pre-final exact head `5ea33d74d1c5c4c36f8701e11cb338b02a64e548` passed PR Validation `32232720306` and aggregate Quality `32232720337`; the final checklist head must reproduce both gates before merge.
- T-013 [ ] Refresh `main`, exact PR head, changed-file set, reviews and unresolved threads; merge only with expected-head protection.
- T-014 [ ] Require exact-main Quality after merge and record durable source-integration evidence on Issue #226.
- T-015 [ ] Compute the merged release production fingerprint and obtain a separate exact-SHA `PRODUCTION APPROVED` envelope with `Execution-Intent: EXECUTE`.
- T-016 [ ] Perform the one repository-owned exact-source `install-auth-privilege-boundary.sh` bootstrap on VPS and record PASS/fixed-topology/no-root-shell evidence.
- T-017 [ ] Execute canonical GitHub Actions VPS deployment for the exact authorized release and require accepted `runtime_verified` evidence including Camera 1 freshness PASS; Ubuntu contour remains skipped.
- T-018 [ ] Complete authenticated browser acceptance proving current-day advancing clean video and unchanged Water/Road worker state.
- T-019 [ ] Persist sanitized production/browser evidence and close Issue #226 only after all applicable source/runtime/acceptance gates pass.

## Requirements traceability

- AC-001 | Task: T-003,T-004,T-008 | Evidence: advancing-HLS unit test returns NOOP and captures no `ffmpeg`/restart command | Coverage: COVERED
- AC-002 | Task: T-003,T-005,T-006,T-008 | Evidence: static-HLS unit test requires relay frame, restarts exactly fixed H264 service and proves post-restart sequence advancement | Coverage: COVERED
- AC-003 | Task: T-005,T-008 | Evidence: relay-failure unit test raises before any service restart | Coverage: COVERED
- AC-004 | Task: T-006,T-008 | Evidence: equal post-restart media sequences raise fail-closed error | Coverage: COVERED
- AC-005 | Task: T-007,T-008 | Evidence: fixed constants plus unsupported-action and no-argument helper/installer assertions | Coverage: COVERED
- AC-006 | Task: T-006,T-008 | Evidence: captured command set excludes nginx, HLS HTTP, MediaMTX, Water worker and Road worker services | Coverage: COVERED
- AC-007 | Task: T-007,T-008 | Evidence: reconcile integration emits Auth PASS plus Camera 1 no-op/freshness PASS markers | Coverage: COVERED
- AC-008 | Task: T-009 | Evidence: deployment-contract assertion confirms accepted `runtime_verified` write remains after successful `run_auth_boundary` gate | Coverage: COVERED
- AC-009 | Task: T-011,T-012 | Evidence: exact authorized-subset diff plus exact-head PR Validation and aggregate Quality | Coverage: COVERED
- AC-010 | Task: T-013,T-014 | Evidence: expected-head merge followed by exact-main Quality and Issue #226 source evidence | Coverage: COVERED
- AC-011 | Task: T-015,T-016 | Evidence: exact release authorization plus repository-owned privilege installer PASS markers | Coverage: RUNTIME-MANUAL | Reason: root-owned exact-source helper bundle exists only on the production VPS
- AC-012 | Task: T-017 | Evidence: canonical VPS deployment manifest with exact source, `runtimeVerified=true`, `state=runtime_verified`, Camera 1 freshness PASS; Ubuntu skipped | Coverage: RUNTIME-MANUAL | Reason: deployment manifest and fixed service state are production runtime evidence
- AC-013 | Task: T-018,T-019 | Evidence: authenticated clean-stream browser acceptance shows current advancing media while Water/Road worker state is unchanged | Coverage: RUNTIME-MANUAL | Reason: protected browser session and live camera time are runtime-only evidence

## Definition of Done

- [x] Issue/spec/plan/tasks current — #226 source intent, fixed privilege boundary, risk profile, production-learning findings and deployment transaction audit are represented.
- [x] Exact changed-file scope verified — PR #227 diff is exactly six paths, all within the eight-path approved Scope, and matches the declared Change Contract.
- [ ] Required tests and evidence complete — focused helper tests and pre-final full PR CI passed; final-head CI, exact-main Quality, production bootstrap/deployment and browser acceptance remain required.
- [ ] Required CI green — final checklist head must pass PR Validation and aggregate Quality, followed by exact-main Quality after merge.
- [ ] Exact-green-head merge complete — merge only after fresh base/head/scope/review gate with expected-head protection.
- [ ] Deployment state resolved — merged exact release must be separately production-authorized, helper bundle refreshed once, and canonical VPS deployment accepted.
- [ ] Runtime acceptance resolved — authenticated clean Camera 1 stream must show current advancing video; Water/Road worker state remains unaffected.
- [x] Deferred work recorded — physical camera changes, Ubuntu relay changes, HLS HTTP/MediaMTX/nginx/Auth changes, Water Passage natural-vessel acceptance, ReID and AIS remain separate outcomes.
- [x] Risks resolved or explicitly accepted — Risk profile REQUIRED; source design is bounded by fixed constants, exact-source/no-args root helper, relay-before-restart and post-restart freshness proof.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`DONE` is forbidden until Issue #226 exact-head PR Validation and aggregate Quality pass on one head, the exact green head merges with expected-head protection, exact-main Quality succeeds, the merged exact SHA receives separate production authorization with execution intent, the repository-owned exact-source privilege bootstrap reports PASS/fixed-topology/no-root-shell markers, canonical VPS deployment reaches accepted `runtime_verified` with Camera 1 freshness PASS and Ubuntu skipped, authenticated browser acceptance proves current advancing clean video with Water/Road workers unaffected, and terminal sanitized evidence is recorded on Issue #226.
