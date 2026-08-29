# Delivery Tasks: Water operator dashboard redesign

- Specification: `specs/069-water-operator-redesign/spec.md`
- Issue: #326
- Branch: `issue-326-water-operator-redesign`

## Delivery tasks

- T001 — Recompose `frontend/sea-speed/index.html` into the approved Water desktop/mobile hierarchy with a compact lighthouse-first header, dominant AI camera, right information rail, and under-camera controls while preserving existing runtime IDs/endpoints.
- T002 — Move the existing crossing-line editor into the under-camera control area and separate all crossing statistics into the new `Пересечения` card backed by the existing summary endpoint.
- T003 — Add direct Water `История` navigation and extend `frontend/sea-speed/objects/index.html` so `scope=water&view=crossings` activates the existing crossing layer and synchronizes query state.
- T004 — Keep recent Water passages as an independent three-record dashboard card with actual passage fields/snapshot availability and a full-registry link.
- T005 — Update `tests/test_frontend_contract.py` and `tests/test_unified_registry.py` for the approved layout, protected Road boundary, existing HLS/API markers, direct crossing-history behavior, and responsive baseline.
- T006 — Run exact-scope review, SDD/Change Contract validation, unit tests and PR quality gates; remediate only within the admitted paths.
- T009 — Merge only the exact green head after fresh base/head/scope/review verification, then require exact-main Quality.
- T010 — Resolve protected VPS deployment, runtime acceptance, evidence and Issue terminal state; Ubuntu Worker/relay remains not required.

## Requirements traceability

- AC-001 | Task: T001 | Evidence: compact header/lighthouse/navigation/status contract assertions and runtime visual acceptance | Coverage: COVERED
- AC-002 | Task: T001 | Evidence: absence of visible clean-stream markers plus preserved HLS/watchdog/live-overlay contract assertions | Coverage: COVERED
- AC-003 | Task: T001,T002 | Evidence: under-camera control markers, existing control IDs and no `cxSummary` statistics in editor | Coverage: COVERED
- AC-004 | Task: T002 | Evidence: crossing-summary endpoint/date/KPI/class-table assertions and runtime data check | Coverage: COVERED
- AC-005 | Task: T003 | Evidence: direct `scope=water&view=crossings` link and registry query-state contract test | Coverage: COVERED
- AC-006 | Task: T004 | Evidence: passages endpoint limit, independent card, record fields and Water registry link assertions | Coverage: COVERED
- AC-007 | Task: T005,T006 | Evidence: updated frontend/registry tests, exact changed-file review and repository validation | Coverage: COVERED
- AC-008 | Task: T006,T009,T010 | Evidence: exact-head CI, exact-green merge, exact-main Quality, protected VPS deployment and runtime acceptance | Coverage: RUNTIME-MANUAL | Reason: deployment and authenticated production viewport evidence exist only after merge through the protected runtime path

## Definition of Done

- Issue/spec/plan/tasks current — Issue #326 and SDD 069 reflect the admitted Water outcome and final evidence.
- Exact changed-file scope verified — only the seven approved source/spec/test paths differ from authorization-base main.
- Required tests and evidence complete — frontend/registry contracts, repository validators and required unit/quality suite are green.
- Required CI green — exact PR head passes Repository validation and quality-integration.
- Exact-green-head merge complete — merge commit contains the exact reviewed/green PR head and no intervening source change.
- Deployment state resolved — VPS deployment reaches accepted success or an explicit terminal blocker/decision state; Ubuntu Worker is not required.
- Runtime acceptance resolved — authenticated Water product checks and responsive acceptance are recorded before DONE.
- Deferred work recorded — any unavailable persisted latest-crossing timestamp or later Road redesign remains explicit separate follow-up rather than hidden scope expansion.
- Risks resolved or explicitly accepted — SDD 069 risk rows match final evidence and residual risk disposition.
- Waivers resolved or current — no waiver is expected; any future waiver must be complete and durable before acceptance.

## Completion gate

Source completion requires exact approved-path diff, current SDD, passing local/static contract evidence where executable, and exact-head GitHub CI. Delivery completion additionally requires exact-green-head merge, exact-main Quality, protected VPS policy/deployment evidence, authenticated Water runtime acceptance, durable Issue checkpoint progression, and terminal `DONE` evidence. No intermediate source/CI state is task completion.
