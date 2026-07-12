# Branch Contract: Frontend

Version: 1.0.0
Status: Active
Role: Operator Frontend Agent

## Scope

- live video and overlay presentation;
- event cards and snapshots;
- worker/AI status;
- state/debug panels;
- ROI and calibration editors.

## Invariants

- Do not change worker, API, deploy or governance files unless explicitly approved.
- Do not silently redefine API fields or event meaning.
- Errors must be readable and must not render as `[object Object]`.
- UI must distinguish offline, stale, skipped, failed and successful states.

## Validation

Validate HTML/JavaScript where tooling exists, inspect selectors and API paths, and verify affected operator workflows.

## Handoff

Report branch, commit, changed files, checks, API assumptions, VPS deploy requirement and browser acceptance steps.