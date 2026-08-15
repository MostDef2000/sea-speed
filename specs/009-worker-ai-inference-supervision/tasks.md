# Tasks: Worker AI inference supervision

Specification: `specs/009-worker-ai-inference-supervision/spec.md`

## Delivery tasks

- [x] Confirm failed production evidence for `c73c6e048399ff5985918348c028d3f9a6a2ca89` and successful automatic restore.
- [x] Keep the remediation inside the already approved AI-inference-supervision outcome.
- [x] Create correction branch from exact current `main`.
- [x] Bound AI child request writes with the same absolute deadline used for response reads.
- [x] Preserve the self-tested persistent child for production frames instead of replacing it after readiness is declared.
- [x] Give replacement AI children one bounded warm-call budget before normal inference deadlines resume.
- [x] Expand the exact activation observation window so the deployment gate cannot expire before the allowed startup sequence can complete.
- [x] Preserve `model.track(... persist=True ...)`, tracker selection, detection shape, vehicle allow-list, ROI filtering, speed semantics, API schemas, and frontend behavior.
- [x] Add focused source-contract coverage for bounded writes, same-child startup validation, warm-child timeout selection, and activation budget.
- [ ] Open correction PR with exact Change Contract.
- [ ] Pass PR Validation, Quality integration, and Worker package gates.
- [ ] Merge exact green head and pass post-merge gates.
- [ ] Obtain fresh exact-SHA production authorization.
- [ ] Run one Worker exact activation and sustained UI/runtime acceptance.
- [ ] Deploy VPS/frontend on the same accepted SHA and close Issue #159 with production evidence.

## Completion gate

Source correction is complete only when the exact PR head is green and merged,
and the merged SHA has fresh post-merge gates. Production remains incomplete
until that same exact SHA passes Worker activation/runtime acceptance and the
Issue #159 VPS/frontend acceptance after fresh production authorization.
