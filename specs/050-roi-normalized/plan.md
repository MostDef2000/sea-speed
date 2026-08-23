# Plan: Normalized ROI model 0..1 for HD 1920 and future 4K

- Issue: #294
- Specification: specs/050-roi-normalized/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-050-001 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: API accepts both absolute & normalized, worker scales on read, frontend normalizes on write, one-shot VPS migration | Validation: roundtrip test 704→1920 + legacy load | Residual risk: 2 | Owner: worker | Status: MITIGATED
- RISK-050-002 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: idempotent migration, reference_width persisted, rollback preserves old file | Validation: deploy migration dry-run + rollback read | Residual risk: 1 | Owner: vps | Status: MITIGATED
- RISK-050-003 | Category: PERF | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: O(N) scale per frame only when ROI enabled | Validation: mask timing <1ms | Residual risk: 1 | Owner: worker | Status: ACCEPTED

## Architecture

VPS+Worker+MIXED normalized:

- `api/app/main.py` — extend `clean_points_list` to accept `x_norm/y_norm`; add `normalize_points_for_storage(points, ref_w=1920, ref_h=1080)` and `denormalize_for_response(normalized, ref_w, ref_h)`; add `reference_width/height` to ROI/speed/crossing JSON; on POST accept either schema, convert to normalized, persist; on GET if legacy file without norms, infer src 704×576 (if max≤704/576) else 1920×1080, convert and persist migration; keep `utilization_pct` area calc on denormalized.
- `worker/hls_motion_yolo_worker_events.py` — add `scale_normalized_points(norm_points, ref_w, ref_h, dst_w, dst_h)` → absolute `round(x_norm*dst_w)`; modify `fetch_remote_roi/mask/fetch_crossing/speed` to read normalized fields when present else legacy absolute, scale to current `_resolve_frame_size()`; keep `detection_inside_road_roi` on scaled.
- `frontend/sea-speed/index.html` + `road/index.html` — add `sourceDims()` using `state.frame_width/height` (water) unified, `normalizePoint(p,w,h)->{x_norm,y_norm}` on save, `denormalize(p,w,h)` on display; CSS `aspect-ratio: 1920/1080`; crossing editors share same dims.
- `deploy/vps/deploy.sh` — one-shot `migrate_roi_to_normalized()` before `ensure_current_release_has_road_frontend`: for each `*_roi.json, *_speed_lines.json, *_crossing_line.json` if no `reference_width`, apply same inference and rewrite.

## Decisions

- D1: Normalized `0..1` float (not 0..1000) — matches frontend/CSS and minimal wire change.
- D2: Reference defaults to 1920×1080 (current HD) for new saves; legacy inferred as 704×576 if bounds fit, else 1920.
- D3: API returns both `polygon` (absolute for legacy clients) and `polygon_norm`+`reference_width/height` for worker/frontend; worker prefers norm if present.
- D4: Migration idempotent — second run no-op.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: `clean_points` accepts both schemas, `normalize→denormalize` roundtrip ±1px, worker scale test 704→1920, frontend normalize math.
- Integration: existing `test_roi` pipeline re-runs with normalized ROI.
- Manual: legacy ROI file before/after visual on 1920 preview same lane; new ROI save+reload.

## Test design

- TEST-050-001 | Covers: AC-001, R1, R2 | Level: unit | Priority: P0 | Evidence: `test_roi_normalization` — legacy 704 accepted & migrated | Coverage: COVERED
- TEST-050-002 | Covers: AC-002, R1 | Level: unit | Priority: P0 | Evidence: normalized roundtrip write/read | Coverage: COVERED
- TEST-050-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: deploy migration script dry-run | Coverage: COVERED
- TEST-050-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: frontend normalize math + CSS 1920/1080 | Coverage: COVERED
- TEST-050-005 | Covers: AC-005, R3 | Level: unit | Priority: P0 | Evidence: worker scaled mask center test | Coverage: COVERED
- TEST-050-006 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: `discover` + validators + MIXED Quality | Coverage: COVERED
- TEST-050-007 | Covers: AC-001..005 | Level: runtime-manual | Priority: P1 | Evidence: visual ROI water+road after deploy | Coverage: RUNTIME-MANUAL | Reason: visual preview

## Correct-course check

- Adjacent-stage review: COMPLETE (api roi storage, worker mask/speed/crossing, frontend coords, deploy migration)
- Trigger: NONE
- Issue impact: #294 fixes HD scatter by normalizing ROI geometry
- Specification impact: R1-R6 introduce normalized + migration
- Plan impact: MIXED deployment, idempotent migration, frontend unified dims
- Tasks impact: traceability AC-001..006 → TASK-050-01/02
- Authorization impact: NONE — fresh receipt src-auth-050 covers listed files
- Follow-up: future 4K no data change needed

## Runtime feedback

To be recorded after MIXED deployment acceptance (ROI visual before/after, heartbeat scaling).

## Deployment transaction audit

Required: runtime deployment REQUIRED (MIXED).

- TX-050-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-050-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-050-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous VPS/Worker serving | Retry: rerun contour | Rollback: redeploy f9abae9 | Evidence: deployment-manifest MIXED runtime_verified
- TX-050-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: f9abae9 | Evidence: manifest checks
- TX-050-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-050-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-050-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-050-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy f9abae9 | Rollback: itself | Evidence: rollbackTarget hash
