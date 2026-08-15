# Review Lens: Release Integration

Version: 2.0.0
Status: Active
Compatibility path: `contracts/branches/core-release.md`
Role: Release Integration Review Lens

## Purpose

Provide an on-demand release/integration checklist to the Sea Speed Delivery Orchestrator. This file is not a second orchestrator and never owns task lifecycle state.

## Review checklist

- canonical Issue and current Outcome Contract are linked;
- exact changed files equal approved scope;
- branch is fresh against current `main`;
- required PR Validation and Quality integration succeeded on exact head;
- unresolved review threads are zero;
- expected-head merge protection is available/used;
- merged source is re-read on `main`;
- release manifest v2/exact artifacts are valid when runtime delivery applies;
- exact runtime contour set is VPS, Ubuntu Worker/relay, Windows AI Worker, or mixed;
- mixed compatibility/rollout/rollback order is explicit;
- production authorization and runtime evidence are present only when applicable;
- terminal evidence is persisted on the canonical Issue.

## Output

Return findings to the Delivery Orchestrator as `APPROVED FOR RELEASE`, `CHANGES REQUIRED`, or `BLOCKED`. The Delivery Orchestrator retains merge/runtime/terminal ownership.
