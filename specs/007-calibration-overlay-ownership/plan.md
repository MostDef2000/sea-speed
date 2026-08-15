# Implementation Plan: Calibration Overlay Ownership

- Specification: specs/007-calibration-overlay-ownership/spec.md
- Issue: #159
- Status: Source authorized

## Architecture

The operator view uses two independent data products that must no longer contain duplicate calibration graphics:

```text
Ubuntu AI worker
  -> Camera frame + AI annotations only
  -> latest overlay JPEG / event snapshot JPEG
  -> existing VPS state/event APIs

Existing VPS calibration state APIs
  -> ROI polygon
  -> Line A / Line B + distance

Browser frontend
  -> displays worker AI JPEG
  -> loads current calibration state
  -> persistently draws ROI + speed lines on transparent canvases
  -> edit mode enables pointer interaction and control-point handles
```

Worker computation continues to fetch the same ROI and speed-line configuration for filtering and calibrated speed estimation. Only the worker's final visual draw calls are removed from the JPEG path.

## Decisions

### D-001 - Frontend is the single visual calibration owner

- Decision: The browser canvases render saved ROI and speed lines in both normal and editing modes.
- Reason: Persisted calibration is operator-configured UI state, and rendering it after the worker JPEG prevents stale or duplicated geometry from being permanently baked into pixels.
- Alternatives rejected: hiding canvases outside edit mode leaves the user without the current saved configuration; drawing the same geometry in both worker and frontend creates duplicate ownership and stale visuals.

### D-002 - Worker calibration remains computational, not visual

- Decision: Keep ROI filtering and speed-line estimation code unchanged, but stop invoking ROI/speed-line drawing on the overlay JPEG used for latest state and event snapshots.
- Reason: The reported defect is rendering ownership, not calibration mathematics or detection semantics.
- Alternatives rejected: deleting worker calibration fetch/compute paths would alter detection/speed behavior and exceed the approved outcome.

### D-003 - Edit mode adds handles, not visibility

- Decision: Saved geometry is always rendered; edit mode only enables pointer events and per-point handles/labels for the geometry being edited.
- Reason: Saving or leaving edit mode must not make the persisted configuration disappear.
- Alternatives rejected: separate edit-only and view-only geometry stores would duplicate state and create synchronization risk.

### D-004 - No schema or state migration

- Decision: Reuse existing ROI and speed-line endpoints and persisted payloads without migration.
- Reason: Existing state is already authoritative and must be preserved.
- Alternatives rejected: clearing/recreating legacy calibration would be destructive and is not required to fix visual ownership.

### D-005 - Worker-first mixed rollout

- Decision: After a future exact-SHA production authorization, update/activate the Ubuntu worker first, verify fresh clean AI overlays and normal compute/state progression, then deploy the VPS frontend and perform browser acceptance.
- Reason: Deploying the frontend first while the old worker still bakes geometry would temporarily display duplicate calibration. Worker-first may briefly remove calibration from normal viewing under the currently deployed edit-only frontend, but computation remains active and it avoids showing two conflicting visual owners.
- Alternatives rejected: VPS-first creates the exact duplicate/stale visual state this change is intended to eliminate.

## Affected contours

- Repository: `frontend/sea-speed/index.html`, `worker/hls_motion_yolo_worker_events.py`, focused frontend/worker tests and `specs/007-calibration-overlay-ownership/**`.
- VPS: operator frontend deployment required after separate production authorization; API implementation and nginx/Auth are unchanged.
- Ubuntu worker/relay: exact worker source update/restart required after separate production authorization; media relay topology is unchanged.
- Windows worker/AI: repository path `worker/**` is the AI worker domain; the commissioned production target is the Ubuntu worker using the existing exact updater. No Windows control-laptop artifact is part of the normal rollout.
- Public interfaces: existing URLs and JSON payloads unchanged.

Compatibility during mixed rollout:
- old frontend + new worker: worker JPEG is clean while saved calibration may be hidden outside edit mode until VPS frontend follows; ROI filtering and speed computation continue normally;
- new frontend + old worker is intentionally avoided because it would render frontend calibration over the worker-baked legacy copy;
- new frontend + new worker: single frontend-owned persistent visual calibration.

## Validation

- Static/CI: focused `tests/test_frontend_contract.py` assertions for persistent canvas visibility/edit-only handles; focused `tests/test_worker_tracking_overlay.py` assertion that worker main does not draw calibration into JPEGs while ROI filtering and speed estimation remain on-path; repository SDD/Change Contract validation; full PR Validation and Quality integration.
- Integration: exact diff must contain only the seven approved files, branch must remain based on current `main`, no secret/runtime artifacts, and both runtime-impact classes must resolve to `MIXED`.
- Runtime acceptance: after separate production authorization, worker evidence must show exact source activation and fresh frame/state progression; browser acceptance must show exactly one current saved ROI/Line A/B layer during normal viewing and after save/reload, editing handles during edit mode, Clear removal, and intact Camera 1/AI/detection behavior.

## Rollout and rollback

- Rollout: Ubuntu worker exact update/activation first using the existing repo-owned exact updater; verify clean overlay/freshness and unchanged computation; then VPS exact source deployment using the existing repo-owned deployer; then browser acceptance.
- Rollback: if full rollback is required, restore the VPS frontend to its known previous release first so persistent canvases no longer duplicate an old worker overlay, then explicitly roll back the worker to its known previous exact release. A future production safety envelope must bind exact source SHA and concrete rollback targets before either mutation.

## Runtime feedback

- Actual architecture after acceptance: PENDING.
- Differences from plan: NONE YET.
- Deferred cleanup: legacy worker drawing helper functions may remain dormant after their main-path invocations are removed; removing unused helpers is optional cleanup unless future source validation requires it.
