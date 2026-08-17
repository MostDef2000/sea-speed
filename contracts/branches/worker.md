# Review Lens: Worker

Version: 1.2.0
Status: Active
Role: Worker Runtime Review Lens

## Scope

Review shared Worker source plus Ubuntu-specific runtime behavior: ingestion, motion/AI activation, YOLO/tracking, ROI, overlays/events, speed estimation and service boundaries. Return findings to the Sea Speed Delivery Orchestrator.

## Invariants

Do not change detection/tracking/speed/calibration formulas without approved outcome. Preserve Stop/Resume progress, error normalization and API/state/event compatibility. Failed/skipped work must not be reported as success.

## Contour classification

- `deploy/worker/ubuntu/**`, `worker/ubuntu_*`: Ubuntu Worker/relay.
- shared executable `worker/**`: Ubuntu Worker/relay unless a more-specific archival rule applies.
- `worker/*.ps1`, `worker/*.cmd`, `worker/windows/**`, `worker/README.txt`, `worker/UPDATE.md`: deprecated non-production local/archive tooling; no runtime contour.

Windows Worker is retired as a production target. Cross-platform Python compatibility may still be preserved, but that does not create a Windows release/deployment/acceptance requirement. Historical Windows evidence remains readable audit history.

## Checks

Python syntax/imports, service/start-stop contracts, state posting, overlay/event semantics, exact source/runtime identity, compatibility and rollback evidence.

## Output

Return findings to the **Sea Speed Delivery Orchestrator**; this lens does not own deployment authorization or lifecycle state.
