# Review Lens: Frontend

Version: 1.1.0
Status: Active
Role: Operator Frontend Review Lens

## Scope

Review live/overlay presentation, event cards, Worker status, state/debug panels, ROI/calibration editors and protected operator workflows within approved scope.

## Invariants

Do not silently redefine API fields/event meaning. Errors remain readable; UI distinguishes offline/stale/skipped/failed/successful states. No unapproved API/Worker/deploy/governance changes.

## Checks

HTML/JavaScript contracts where tooling exists, selectors/API paths, auth/session boundary, browser acceptance plan and VPS applicability.

## Output

Return findings to the Sea Speed Delivery Orchestrator; no autonomous lifecycle handoff.
