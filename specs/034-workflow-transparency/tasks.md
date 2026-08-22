# Tasks 034 — Workflow Transparency

- Specification: specs/034-workflow-transparency/spec.md
- Plan: specs/034-workflow-transparency/plan.md
- Issue: #254
- Status: Active

## Delivery tasks

- [x] Create composite action `.github/actions/verify-exact-release/action.yml`
- [x] Refactor `deploy-vps.yml` and `deploy-ubuntu-worker.yml` to use shared action (-60 lines each)
- [x] Add `docs/WORKFLOW_OVERVIEW.md` with 5-step diagram
- [x] Disable legacy HLS workflows via API (agent-hls-*, repair-speed-stability)
- [x] Add SDD specs/034 with required markers
- [x] Update PR #253 Change Contract to reference Issue #254 and specs/034

## Completion gate

- [x] Exact changed-file scope verified (4 + 3 SDD files)
- [x] workflow-policy valid
- [x] 428 tests PASS, 2 skipped
- [x] No runtime impact, Operator actions 0
- [x] PR Validation + quality-integration success required before merge
