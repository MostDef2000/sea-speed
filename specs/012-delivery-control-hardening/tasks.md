# Tasks: Delivery Control Hardening

Specification: specs/012-delivery-control-hardening/spec.md
Issue: #172
Status: Active

## Delivery tasks

- [x] T001 Model VPS, Ubuntu Worker/relay, and Windows AI Worker as explicit production runtime contours with exact mixed deployment flags.
- [x] T002 Harden exact-main production SHA and aggregate main-push quality proof before SSH.
- [x] T003 Add canonical Issue/PR/Outcome-bound durable production authorization with fail-closed fingerprint validation.
- [x] T004 Introduce release provenance v2 with separate approved/actual scope and artifact/evidence SHA-256 bindings while preserving v1 readers.
- [x] T005 Add explicit Ubuntu deployment-manifest target without invalidating persisted VPS/Windows v1 manifests.
- [x] T006 Wire SDD PR linkage validation into aggregate quality integration.
- [x] T007 Add focused tests for contours, authorization, quality provenance, release provenance, deployment compatibility, and workflow architecture.
- [x] T008 Synchronize canonical governance/runtime contracts and templates with executable controls.
- [ ] T009 Open PR with exact 34-path Change Contract and verify PR Validation + Quality integration on exact final head.
- [ ] T010 Merge exact green head, re-read `main`, and record source integration evidence on Issue #172.

## Completion gate

- [x] Exact changed-file set equals the 34 paths authorized on Issue #172.
- [x] No runtime payload or GitHub settings changes are present.
- [ ] PR Validation succeeds on exact final head.
- [ ] Quality integration succeeds on exact final head and includes SDD validation.
- [ ] No unresolved review thread blocks merge.
- [ ] Merge uses the exact verified head SHA.
- [ ] Post-merge `main` is re-read and source evidence is persisted on Issue #172.
- [x] No production workflow has been dispatched.
