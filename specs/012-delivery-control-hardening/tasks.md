# Tasks: Delivery Control Hardening

Specification: specs/012-delivery-control-hardening/spec.md
Issue: #172
Status: Accepted / completed

## Delivery tasks

- [x] T001 Model VPS, Ubuntu Worker/relay and Windows AI Worker as exact production contours.
- [x] T002 Harden exact-main SHA and aggregate main-push quality proof before SSH.
- [x] T003 Add canonical Issue/PR/Outcome-bound durable production authorization fingerprint.
- [x] T004 Introduce release provenance v2 with approved/actual scope and exact artifact/evidence bindings.
- [x] T005 Add explicit Ubuntu deployment target while preserving persisted v1 readability.
- [x] T006 Wire SDD linkage validation into aggregate quality.
- [x] T007 Add focused contour/authorization/provenance/deployment/workflow tests.
- [x] T008 Synchronize canonical governance/runtime contracts and templates.
- [x] T009 Open PR #173 with exact 34-path scope and obtain exact-head PR Validation + Quality integration success.
- [x] T010 Merge exact green head, re-read main, persist post-merge exact-main quality evidence and close Issue #172 completed.

## Completion gate

- [x] Exact changed-file set was the approved 34 paths.
- [x] No runtime payload or GitHub settings change occurred.
- [x] PR Validation and Quality integration succeeded on exact final PR head.
- [x] No unresolved review thread blocked merge.
- [x] Expected-head merge succeeded.
- [x] Post-merge main `9178bd13c6236b396e6931605fe4257319241c71` was re-read and exact-main PR Validation + Quality integration succeeded.
- [x] Issue #172 records terminal source evidence and is closed completed.
- [x] No production workflow was dispatched.
