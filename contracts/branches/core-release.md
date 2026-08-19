# Review Lens: Release Integration

Version: 2.2.0
Status: Active
Compatibility path: `contracts/branches/core-release.md`
Role: Release Integration Review Lens

## Purpose

Provide an on-demand release/integration checklist to the Sea Speed Delivery Orchestrator. This file is not a second orchestrator and never owns lifecycle state.

## Review checklist

- canonical Issue and current Outcome Contract linked;
- exact changed files equal approved scope;
- branch fresh against current `main`;
- required PR Validation and Quality succeed on exact head;
- unresolved review threads zero and expected-head merge protection used when supported;
- merged source re-read on `main` and exact-main Quality succeeds;
- runtime release, when applicable, has exact artifacts and valid `sea_speed_release_manifest_v3`;
- standing production delegation is trusted external state, current for repository/policy, and repository text is not authority;
- typed policy decision is `allow` before applicable runtime transport;
- applicable VPS/Ubuntu protected workflows independently re-check policy;
- rollback identity explicit and successful runtime execution produces typed audit;
- historical v1/v2/Windows evidence remains readable but non-authoritative;
- terminal evidence persisted on canonical Issue.

## Output

Return `APPROVED FOR RELEASE`, `CHANGES REQUIRED`, or `BLOCKED` findings to the Delivery Orchestrator. The Orchestrator retains lifecycle ownership.
