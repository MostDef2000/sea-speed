# Branch Contract: Worker

Version: 1.0.0
Status: Active
Role: Windows AI Worker Agent

## Scope

- HLS and FFmpeg ingestion;
- motion detection and AI activation;
- YOLO detection and filtering;
- ROI, tracking, overlay and event snapshots;
- speed estimation and worker command scripts.

## Invariants

- Do not change API, frontend, deploy or governance files unless explicitly approved.
- Do not change detection, tracking, speed or calibration formulas without approval.
- Preserve Stop/Resume progress.
- Do not report skipped or failed records as successfully processed.
- Normalize errors; never display or transmit `[object Object]`.
- Keep API/state/event schema compatibility unless a schema change is explicitly approved.

## Validation

Run Python syntax/import checks where available, inspect startup/shutdown scripts, verify state posting, overlay/event behavior and affected compatibility boundaries.

## Handoff

Report branch, commit, changed files, checks, schema impact, runtime configuration impact, release requirement and rollback notes.