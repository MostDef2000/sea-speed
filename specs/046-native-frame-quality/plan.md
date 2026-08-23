# Plan: Native frame quality for Water and Road (HD analysis + sharpness-aware best frame)

- Issue: #285
- Specification: specs/046-native-frame-quality/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-046-001 | Category: PERF | Probability: 3 | Impact: 2 | Score: 6 | Mitigation: YOLO imgsz unchanged at 960; frame size increase only affects rawvideo transport (~31 MB/s) and crop quality; validated by FPS stability check and no throughput regression | Validation: unit profile asserts + manual sampler FPS check post-deploy | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-046-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: per-profile frame sizes preserve backward compat via env override; worker remains functional if env unset (defaults to profile); tested with explicit env override | Validation: env override test | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-046-003 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: sharpness metric is additive — low-sharpness candidate only skipped when a sharper frame already stored; confidence*area still primary; Laplacian var threshold 100 calibrated against synthetic blur | Validation: sharpness unit test | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Architecture

- worker/analytics_profiles.py: extend AnalyticsProfile with frame_width/frame_height (1920/1080 for both profiles); include in profile_defaults().
- worker/hls_motion_yolo_worker_events.py: start_ffmpeg() resolves frame size from profile/env (FRAME_WIDTH/HEIGHT env overrides profile); FFmpegFrameReader width/height follow; write_passage_snapshot uses new helper crop_sharpness() when evaluating candidate.
- worker/water_passage.py: snapshot scoring incorporates sharpness — add helper _laplacian_variance(crop) and gate is_better with sharpness comparison when scores are within ratio window.
- worker/ubuntu_worker_entrypoint.py: pass frame size via env from profile defaults when launching worker.
- deploy/worker/ubuntu/worker.env.example: update FRAME_WIDTH/FRAME_HEIGHT defaults to 1920/1080 with comment.
- tests: extend test_analytics_profiles.py with frame size assertions; add test_frame_quality.py with sharpness metric and per-profile resolution tests.

## Decisions

- D1: Use 1920x1080 as default for both profiles — matches typical camera native HD and keeps ratio 16:9; higher (2560+) possible via env without code change.
- D2: Env FRAME_WIDTH/HEIGHT override profile — preserves operator tuning without redeploy.
- D3: Sharpness via Laplacian variance on grayscale crop — lightweight (no extra model), threshold 100 empirically separates sharp vs blurred synthetic data.

## Affected contours

- Ubuntu Worker/relay: REQUIRED — worker frame pipeline, snapshot quality, passage scoring.
- VPS: NOT REQUIRED.

## Validation

- Local: python scripts/ci/validate_sdd.py, validate_change_contract.py, validate_repo.py, validate_contracts.py, scripts/quality/*, python -m unittest discover -s tests -p test_*.py -v
- PR: Repository validation + quality-integration required on exact head
- Runtime: after Ubuntu deploy, verify passage snapshots are HD crops, overlay FPS stable, registry shows higher-resolution images for both cam1 and road1.

## Test design

- TEST-046-001 | Covers: AC-001, AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_analytics_profiles.py asserts frame_width/height per profile and profile_defaults propagation
- TEST-046-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_frame_quality.py verifies start_ffmpeg env override and default profile resolution
- TEST-046-003 | Covers: AC-004, AC-005 | Level: unit | Priority: P0 | Evidence: tests/test_frame_quality.py Laplacian variance on synthetic sharp vs blurry crops; passage snapshot scoring with sharpness gate
- TEST-046-004 | Covers: AC-006 | Level: unit | Priority: P1 | Evidence: worker.env.example content assertion
- TEST-046-005 | Covers: AC-007 | Level: unit | Priority: P1 | Evidence: existing analytics/passage tests still pass at new resolution (no tracking regression)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE — same Issue #285 and branch agent/044-native-frame-quality; spec renumbered 044->046 as non-material sequence correction (044 already occupied by crossing-daily-sync) — no scope change
- Follow-up: NONE

## Deployment transaction audit

Required: Ubuntu Worker/relay REQUIRED (shared executable worker/**).

- TX-046-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous release serving | Retry: after policy/state correction | Rollback: NOT REQUIRED | Evidence: deploy-runtime-autonomous log with policy decision
- TX-046-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection/Quality mismatch aborts before transport | Retry: after remediation | Rollback: NOT REQUIRED | Evidence: verify_source_protection.py output
- TX-046-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps serving on health gate failure | Retry: rerun Ubuntu contour | Rollback: redeploy rollbackTarget from manifest | Evidence: deployment manifest Ubuntu
- TX-046-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified=false blocks DONE | Retry: rerun verification | Rollback: rollback target if cannot pass | Evidence: manifest checks (frame size, snapshot presence)
- TX-046-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing blocks completion | Retry: rerun evidence upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-046-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: stale tmp remains | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-046-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deploy without audit not claimed complete | Retry: rerun audit emission | Rollback: NOT REQUIRED | Evidence: typed execution audit bound to policy decision
- TX-046-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual decision + redeploy known-good | Rollback: itself is rollback path | Evidence: rollbackTarget hash in manifest

## Runtime feedback

To be recorded after Ubuntu Worker/relay deployment acceptance.
