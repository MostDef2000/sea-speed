# Tasks: Water camera RTSP 461 — configurable transport and credentials out of argv (#384)

- Specification: specs/384-water-rtsp-udp/spec.md
- Plan: specs/384-water-rtsp-udp/plan.md
- Issue: #384

## Delivery tasks

- T-384-001 [x] SDD: specs/384-water-rtsp-udp/{spec,plan,tasks}.md (R1–R4, NFR, risks, tests, audit)
- T-384-002 [x] `deploy/worker/ubuntu/camera1-h264-transcode.sh` run mode: `CAMERA1_RTSP_TRANSPORT` (default udp, strict validation), credential URL into 0600 ffconcat file in PrivateTmp, stale cleanup, argv without HLS_URL (R1)
- T-384-003 [x] `deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`: fixed source probe → `rtsp://10.123.239.102:8554/cam1-h264` (R3)
- T-384-004 [x] `worker/ubuntu_worker_entrypoint.py`: `_credential_bearing` / `_camera1_rtsp_transport` / `_write_rtsp_ffconcat_input` helpers; `_spawn_rtsp_ffmpeg` ffconcat branch for credential inputs, tcp relay branch preserved (R2)
- T-384-005 [x] `worker.env.example` documents `CAMERA1_RTSP_TRANSPORT=udp`; `road-worker.env.example` documents tcp-only relay reads (R1/R2)
- T-384-006 [x] Tests: watchdog source pin (test_camera1_h264_freshness_watchdog.py), transport/ffconcat contract + helper behavior (test_camera1_live_replacement.py) (R1–R3)
- T-384-007 [x] Local validation: `bash -n` + full unittest suite + validate_sdd/validate_repo/validate_contracts/quality validators
- T-384-008 [x] Push branch; open PR with exact Change Contract (Ubuntu REQUIRED, VPS NOT REQUIRED, operator actions 0)
- T-384-009 [ ] PR CI green (`Repository validation` + `quality-integration`); exact-green-head squash merge
- T-384-010 [ ] Post-merge main Quality → `deploy-runtime-autonomous` → policy ALLOW → `deploy-ubuntu-worker` success
- T-384-011 [ ] Runtime acceptance: journal without 461, transcode active without restart growth, freshness timer exit 0, ffprobe from VPS, dashboard cam20/cam16+, `ps` argv without credentials; close #384

## Requirements traceability

- AC-001 | Task: T-384-002, T-384-003, T-384-009, T-384-010, T-384-011 | Evidence: deploy evidence (deployment-manifest, execution-audit v1) + Worker journal | Coverage: RUNTIME-MANUAL | Reason: requires the exact deployed release on the physical Worker and live camera UDP pull; not reproducible in CI
- AC-002 | Task: T-384-010, T-384-011 | Evidence: ffprobe from VPS + dashboard frame freshness | Coverage: RUNTIME-MANUAL | Reason: live VPS→Worker RTSP read and dashboard rendering require production runtime
- AC-003 | Task: T-384-002, T-384-004, T-384-011 | Evidence: unit tests for argv/ffconcat construction + runtime `ps` check | Coverage: COVERED (runtime confirmation pending)
- AC-004 | Task: T-384-006, T-384-007 | Evidence: new tests + full local suite + validators | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current — #384 outcome, scope and SDD linked
- [x] Exact changed-file scope verified — the five source/config paths, two test files, specs/384-water-rtsp-udp/* only
- [ ] Required tests and evidence complete — full local suite + validators PASS (T-384-007)
- [ ] Required CI green — PR exact head must pass Repository validation and quality-integration, then exact-main Quality
- [ ] Exact-green-head merge complete — merge only after fresh base/head and required checks green
- [ ] Deployment state resolved — autonomous Ubuntu deploy pending post-merge Quality
- [ ] Runtime acceptance resolved — journal/ffprobe/dashboard/ps evidence pending
- [ ] Deferred work recorded — reader consolidation (Variant C) as separate follow-up
- [x] Risks resolved or explicitly accepted — Risk profile REQUIRED: 4 mitigated (SEC-6, REL-3, OPS-2, TECH-2), 1 accepted (TECH-1)
- [x] Waivers resolved or current — no waiver

## Completion gate

- Direct water readers select transport via `CAMERA1_RTSP_TRANSPORT` (default udp) and
  never expose the credential URL in ffmpeg argv (0600 ffconcat in PrivateTmp)
- Worker watchdog probes the product path `cam1-h264`; road/relay tcp behavior unchanged
- PR merged exact-green-head; autonomous deploy-ubuntu-worker succeeds with
  deployment-manifest + execution-audit v1; runtime acceptance evidence recorded in #384
- Deferred follow-up (reader consolidation) recorded; #384 closed
