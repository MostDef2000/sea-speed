# Plan: Registry image zoom and live stream fullscreen

- Issue: #287
- Specification: specs/047-registry-live-fullscreen/spec.md

## Risk profile

- Risk profile: NOT REQUIRED

## Architecture

Frontend-only:
- `objects/index.html`: add `#imageZoomOverlay` dialog (fixed fullscreen, backdrop, centered img, ×), handlers: card image click, detail image click, backdrop/Esc/× close, body `overflow:hidden` lock.
- `frontend/sea-speed/index.html` (water): wrap `.live-preview-frame` with relative + absolute ⛶ button `#liveFullscreenBtn`; add `#liveFullscreenOverlay` (fixed, backdrop, video container, ×); on open move existing `#video` element into overlay (preserving HLS), on close move back; backdrop/Esc/× close restores inline.
- `frontend/sea-speed/road/index.html` same as water but IDs scoped to road preview (`#livePreviewFrame`).

No new JS dependencies, no backend.

## Decisions

- D1: Move single `<video>` element into fullscreen overlay instead of cloning HLS to avoid double stream and keep `hls` instance valid.
- D2: Reuse existing modal pattern (`modal-backdrop`/`modal`) styles for registry zoom to keep visual consistency.
- D3: Zoom disabled for `photo-empty` fallback — guard checks `snapshot_url`.

## Affected contours

- VPS: REQUIRED (frontend static). Ubuntu Worker/relay: NOT REQUIRED.

## Validation

- Unit: none required (DOM behavior, runtime-manual). Existing 500+ unit tests stay green.
- Manual: registry zoom + water fullscreen + road fullscreen smoke.

## Runtime feedback

To be recorded after VPS deployment acceptance.

## Test design

- TEST-047-001 | Covers: AC-001, AC-002, AC-005 | Level: runtime-manual | Priority: P0 | Evidence: operator clicks registry thumbnail/detail → overlay with same src → ×/Esc/backdrop closes; empty photo not clickable | Coverage: RUNTIME-MANUAL | Reason: DOM overlay requires browser
- TEST-047-002 | Covers: AC-003 | Level: runtime-manual | Priority: P0 | Evidence: water live ⛶ → fullscreen video playing → × returns inline | Coverage: RUNTIME-MANUAL
- TEST-047-003 | Covers: AC-004 | Level: runtime-manual | Priority: P0 | Evidence: road live ⛶ → fullscreen video playing → × returns inline | Coverage: RUNTIME-MANUAL
- TEST-047-004 | Covers: NFR-047-004 | Level: unit | Priority: P1 | Evidence: `python -m unittest discover -s tests -p test_*.py -v` stays green | Coverage: COVERED

## Correct-course check

- Adjacent-stage review: COMPLETE (reviewed ROI/crossing/registry modals, live HLS controls, no conflict with existing overlays)
- Trigger: NONE
- Issue impact: new UX request for evidence inspection and live fullscreen
- Specification impact: R1-R6 add zoom + fullscreen overlays frontend-only
- Plan impact: VPS REQUIRED, validates via manual smoke
- Tasks impact: traceability maps AC-001..AC-006 to tasks
- Authorization impact: NONE — fresh receipt src-auth-287-registry-live-fullscreen covers exact 3 files
- Follow-up: operator verifies overlays post-deploy on mostdef.ru

## Deployment transaction audit

Required: runtime deployment REQUIRED (VPS frontend).

- TX-047-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous release serving | Retry: after policy/state correction | Rollback: NOT REQUIRED | Evidence: autonomous workflow log with policy decision id
- TX-047-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection/Quality mismatch aborts before transport | Retry: after remediation | Rollback: NOT REQUIRED | Evidence: verify_source_protection.py output
- TX-047-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps serving on health gate failure | Retry: rerun failed contour | Rollback: redeploy rollbackTarget from manifest | Evidence: deployment-manifest VPS runtime_verified
- TX-047-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified=false blocks DONE | Retry: rerun verification | Rollback: rollback target if cannot pass | Evidence: manifest checks array
- TX-047-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing blocks completion | Retry: rerun evidence upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-047-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: stale tmp remains | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-047-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deploy without audit not claimed complete | Retry: rerun audit emission | Rollback: NOT REQUIRED | Evidence: typed execution audit bound to policy decision
- TX-047-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual decision + redeploy known-good | Rollback: itself is rollback path | Evidence: rollbackTarget hash in manifest
