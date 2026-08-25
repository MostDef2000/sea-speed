# Plan: Road overlay polish — lag compensation, clean preview restore, stable crossings

- Issue: #314
- Specification: specs/059-road-overlay-polish/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-059-001 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: median lag compensation 0..600ms clamped, bracket gap ≤500ms, fail-closed if unavailable, no extrapolation | Validation: sync math lag unit tests | Residual risk: 1 | Owner: frontend | Status: MITIGATED
- RISK-059-002 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: independent Hls.js 1.5.7 instance for clean preview, same hls_url, placeholder hidden on playing | Validation: frontend contract tests | Residual risk: 1 | Owner: frontend | Status: MITIGATED
- RISK-059-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: crossings from hi bracket only, monotonic update, no per-detection interpolation | Validation: crossing stability unit tests | Residual risk: 1 | Owner: frontend | Status: MITIGATED

## Architecture

- Frontend: measure `playingDate - capture_time_unix_ms` median over 10s warmup (≥20 samples), subtract from media UTC before bracket search; clean preview `<video id="cleanPreviewVideo">` with second Hls instance; crossings stable from hi.
- No worker/API/nginx/schema changes; existing v2 envelope + PDT + SSE remain.

## Decisions

- D1: Frontend-only polish — no second encode, no worker reboot.
- D2: Lag compensation clamped 0..600ms, fail-closed on excess.
- D3: Clean preview duplicates same HLS URL, independent lifecycle.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: NOT REQUIRED

## Validation

- Unit: lag median, bracket skew, clean preview element, crossings stability, HLS PDT path.
- Runtime-manual: Road main p95/max skew, clean preview advancing, crossings monotonic, Water unchanged.

## Test design

- TEST-059-001 | Covers: R1 | Level: unit | Priority: P0 | Evidence: tests/test_road_overlay_sync.py | Coverage: COVERED
- TEST-059-002 | Covers: R3, R4 | Level: unit | Priority: P0 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- TEST-059-003 | Covers: R2 | Level: unit | Priority: P0 | Evidence: tests/test_road_overlay_sync.py | Coverage: COVERED
- TEST-059-004 | Covers: runtime | Level: runtime-manual | Priority: P1 | Evidence: VPS manifests + manual visual | Coverage: RUNTIME-MANUAL | Reason: protected hardware/media clocks

## Correct-course check

- Trigger: NONE
- Issue impact: frontend lag/crossings/clean-preview polish without worker
- Specification impact: add lag compensation + preview element + stable crossings contract
- Plan impact: frontend-only VPS delivery, no MIXED
- Tasks impact: AC-001..AC-003 → TASK-059-01..03
- Authorization impact: NONE — initial SDD for src-auth-059
- Follow-up: keep detector frequency benchmark separate

## Runtime feedback

- Prior `93798bd` verified but lag, empty clean preview, jitter observed.

## Deployment transaction audit

- TX-059-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-059-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-059-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy 93798bd | Evidence: deployment-manifest VPS runtime_verified
- TX-059-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 93798bd | Evidence: manifest + HLS PDT + preview check
- TX-059-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-059-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-059-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-059-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 93798bd | Rollback: itself | Evidence: rollbackTarget hash
