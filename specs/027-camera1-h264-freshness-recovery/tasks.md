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
- T-012 [x] Open linked PR #227; final PR Validation `32232830011` and aggregate Quality `32232829994` succeeded before expected-head merge.
- T-013 [x] Merge PR #227 as `28e9f4f30554de40ace25ddc1e65184e9a68e6b8` with expected-head protection and verify exact-main Quality run `32232933446` SUCCESS.
- T-014 [x] Record durable source-integration evidence on Issue #226 for the exact merged source and VPS-only runtime contour.
- T-015 [x] Compute fingerprint `6ee65b0b0b18f9a35e8b373a48ef99f7094700ab519d266d9b27ff838d69aff3` and obtain exact-SHA production authorization with `Execution-Intent: EXECUTE` for `28e9f4f30554de40ace25ddc1e65184e9a68e6b8`.
- T-016 [x] Perform the repository-owned exact-source `install-auth-privilege-boundary.sh` bootstrap for `28e9f4f...` and record PASS/fixed-topology/no-root-shell evidence.
- T-017 [ ] Execute canonical GitHub Actions VPS deployment for the exact authorized release and require accepted `runtime_verified` evidence including Camera 1 freshness PASS; the first `28e9f4f...` attempt failed closed at PRE-MUTATION because production FFmpeg rejected `-rw_timeout`, and rollback to `0af31b5e2516fb0d529228a51025693e7a932779` succeeded. Corrective source integration is required before retry.
- T-018 [ ] Complete authenticated browser acceptance proving current-day advancing clean video and unchanged Water/Road worker state.
- T-019 [ ] Persist sanitized production/browser evidence and close Issue #226 only after all applicable source/runtime/acceptance gates pass.
- T-020 [x] Resolve production failure read-only: `ffmpeg ... -rw_timeout 10000000` fails on the VPS with `Option rw_timeout not found`, while the bounded same-relay probe using `-rtsp_transport tcp -timeout 10000000` opens the stream and reaches HEVC decoding; present revised five-path Scope and obtain fresh immediately-following `OUTCOME APPROVED`.
- T-021 [x] Correct the fixed privileged relay probe to use `-timeout 10000000`, add exact argv regression coverage rejecting `-rw_timeout`, and update SDD production-learning/adjacent-stage evidence without changing topology or `deploy/vps/deploy.sh`.
- T-022 [ ] Open the corrective PR, require PR Validation and aggregate Quality on one exact head, refresh `main`/head/scope/reviews, merge only with expected-head protection, then require exact-main Quality.
- T-023 [ ] For the corrective merge only, compute a new production fingerprint, obtain fresh exact-SHA production authorization, perform one new exact-source privilege bootstrap, and run canonical VPS deployment to `runtime_verified` with Camera 1 freshness PASS; Ubuntu remains skipped.

## Requirements traceability

- AC-001 | Task: T-003,T-004,T-008 | Evidence: advancing-HLS unit test returns NOOP and captures no `ffmpeg`/restart command | Coverage: COVERED
- AC-002 | Task: T-003,T-005,T-006,T-008,T-020,T-021 | Evidence: static-HLS unit test requires relay frame through exact VPS-compatible `-rtsp_transport tcp -timeout 10000000` argv with no `-rw_timeout`, restarts exactly fixed H264 service and proves post-restart sequence advancement | Coverage: COVERED
- AC-003 | Task: T-005,T-008 | Evidence: relay-failure unit test raises before any service restart | Coverage: COVERED
- AC-004 | Task: T-006,T-008 | Evidence: equal post-restart media sequences raise fail-closed error | Coverage: COVERED
- AC-005 | Task: T-007,T-008,T-021 | Evidence: fixed constants, exact relay-probe argv, unsupported-action and no-argument helper/installer assertions | Coverage: COVERED
- AC-006 | Task: T-006,T-008 | Evidence: captured command set excludes nginx, HLS HTTP, MediaMTX, Water worker and Road worker services | Coverage: COVERED
- AC-007 | Task: T-007,T-008 | Evidence: reconcile integration emits Auth PASS plus Camera 1 no-op/freshness PASS markers | Coverage: COVERED
- AC-008 | Task: T-009 | Evidence: deployment-contract assertion confirms accepted `runtime_verified` write remains after successful `run_auth_boundary` gate | Coverage: COVERED
- AC-009 | Task: T-011,T-012,T-020,T-021,T-022 | Evidence: exact authorized-subset corrective diff plus exact-head PR Validation and aggregate Quality | Coverage: COVERED
- AC-010 | Task: T-013,T-014,T-022 | Evidence: expected-head merge followed by exact-main Quality and Issue #226 source evidence | Coverage: COVERED
- AC-011 | Task: T-015,T-016,T-023 | Evidence: exact release authorization plus repository-owned privilege installer PASS markers; corrective merge requires a new authorization/bootstrap pair | Coverage: RUNTIME-MANUAL | Reason: root-owned exact-source helper bundle exists only on the production VPS
- AC-012 | Task: T-017,T-023 | Evidence: canonical VPS deployment manifest with corrective exact source, `runtimeVerified=true`, `state=runtime_verified`, Camera 1 freshness PASS; Ubuntu skipped | Coverage: RUNTIME-MANUAL | Reason: deployment manifest and fixed service state are production runtime evidence
- AC-013 | Task: T-018,T-019 | Evidence: authenticated clean-stream browser acceptance shows current advancing media while Water/Road worker state is unchanged | Coverage: RUNTIME-MANUAL | Reason: protected browser session and live camera time are runtime-only evidence

## Definition of Done

- [x] Issue/spec/plan/tasks current — #226 source intent, fixed privilege boundary, first production failure, FFmpeg timeout compatibility correction, risk profile and eight-stage Deployment Transaction Audit are represented.
- [ ] Exact changed-file scope verified — corrective diff must be a subset of the fresh five-path Scope and match its PR Change Contract.
- [ ] Required tests and evidence complete — corrective exact argv/helper tests, full PR CI, exact-main Quality, fresh production bootstrap/deployment and browser acceptance remain required.
- [ ] Required CI green — corrective exact head must pass PR Validation and aggregate Quality, followed by exact-main Quality after merge.
- [ ] Exact-green-head merge complete — merge corrective PR only after fresh base/head/scope/review gate with expected-head protection.
- [ ] Deployment state resolved — corrective merged release must receive a new production authorization, helper bundle refresh, and accepted canonical VPS deployment.
- [ ] Runtime acceptance resolved — authenticated clean Camera 1 stream must show current advancing video; Water/Road worker state remains unaffected.
- [x] Deferred work recorded — physical camera changes, Ubuntu relay changes, HLS HTTP/MediaMTX/nginx/Auth changes, Water Passage natural-vessel acceptance, ReID and AIS remain separate outcomes.
- [x] Risks resolved or explicitly accepted — Risk profile REQUIRED; source design remains bounded by fixed constants, exact-source/no-args root helper, production-compatible relay probe, relay-before-restart and post-restart freshness proof.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`DONE` is forbidden until the corrective Issue #226 exact-head PR Validation and aggregate Quality pass on one head, the exact green corrective head merges with expected-head protection, exact-main Quality succeeds, the corrective merged SHA receives a new production authorization with execution intent, the repository-owned exact-source privilege bootstrap reports PASS/fixed-topology/no-root-shell markers, canonical VPS deployment reaches accepted `runtime_verified` with Camera 1 freshness PASS and Ubuntu skipped, authenticated browser acceptance proves current advancing clean video with Water/Road workers unaffected, and terminal sanitized evidence is recorded on Issue #226.