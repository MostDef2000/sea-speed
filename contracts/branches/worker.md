# Review Lens: Worker

Version: 1.1.0
Status: Active
Role: Worker Runtime Review Lens

## Scope

Review shared Worker source plus Ubuntu/Windows-specific runtime behavior: ingestion, motion/AI activation, YOLO/tracking, ROI, overlays/events, speed estimation and command/service boundaries.

## Invariants

Do not change detection/tracking/speed/calibration formulas without approved outcome. Preserve Stop/Resume progress, error normalization and API/state/event compatibility. Failed/skipped work must not be reported as success.

## Contour classification

- `deploy/worker/ubuntu/**`, `worker/ubuntu_*`: Ubuntu Worker/relay.
- Windows-specific scripts/paths: Windows AI Worker.
- shared `worker/**`: normally Ubuntu + Windows (`MIXED`) unless a more-specific policy rule applies.

## Checks

Python syntax/imports, service/start-stop contracts, state posting, overlay/event semantics, exact source/runtime identity, compatibility and rollback evidence.

## Output

Return findings to the Sea Speed Delivery Orchestrator; this lens does not own deployment authorization or lifecycle state.
