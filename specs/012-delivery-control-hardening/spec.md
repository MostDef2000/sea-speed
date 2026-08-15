# Feature Specification: Delivery Control Hardening

- Feature: 012-delivery-control-hardening
- Issue: #172
- Status: Accepted / completed

## Product outcome

Sea Speed delivery controls fail closed and produce machine-verifiable provenance for VPS, Ubuntu Worker/relay and Windows AI Worker. Production admission proves exact current-main first-parent source, exact successful aggregate `push/main` quality, canonical Issue/merged-PR/Outcome linkage and durable exact-SHA production authorization before runtime mutation.

## User scenarios

1. Ubuntu deployment source is classified Ubuntu, never generic control plane.
2. VPS production dispatch rejects non-lowercase/non-main/non-first-parent SHA before SSH.
3. Release audit distinguishes approved files from actual diff and binds artifacts/evidence.
4. Significant PR without valid SDD linkage cannot obtain aggregate quality success.

## Requirements

- exact three-contour classification with MIXED summary and exact flags;
- runtime contour requires production envelope;
- manual VPS workflow retains `production` environment;
- exact successful quality workflow must be event `push`, branch `main`, exact SHA;
- production authorization binds canonical Issue/merged PR/Outcome/contours/security/deployment/rollback via fingerprint;
- release manifest v2 records approved vs actual scope and exact artifact/evidence digests;
- persisted v1 release/deployment evidence remains readable;
- aggregate quality executes SDD validation;
- Stage A performs no runtime deployment.

## Acceptance criteria

All focused contour/provenance/authorization/release/deployment/SDD tests passed; PR Validation and Quality integration were green on exact head; expected-head merge completed; post-merge exact-main PR Validation and Quality integration both succeeded; no production workflow was dispatched.

## Runtime feedback

Runtime acceptance: NOT REQUIRED. Issue #172 is closed `completed`; Stage A merged as exact main `9178bd13c6236b396e6931605fe4257319241c71` with post-merge quality evidence persisted on the Issue.
