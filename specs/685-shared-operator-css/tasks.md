# Tasks — 685 shared operator CSS extraction

- Specification: specs/685-shared-operator-css/spec.md
- Issue: #685
- Branch: `agent/wave7-688-685`
- Actual worktree HEAD: `e4c5bf2a1b6ec2c66975f76e572c41a9ca75a634`
- Ordered base SHA `eba2604dbbc5bf22546d948d118b5e6abb0141ff` is absent locally (recorded in plan.md).

## Delivery tasks

- [x] T001 — Extract the ordered shared prefix (`:root` → base `.objects-link`, 22 rules) into `frontend/sea-speed/operator-common.css` (2366 bytes).
- [x] T002 — Add `<link rel="stylesheet" href="/sea-speed/operator-common.css">` before `<style>` in `frontend/sea-speed/index.html` and delete only the prefix.
- [x] T003 — Same link + prefix removal for `frontend/sea-speed/road/index.html`, keeping `.objects-link.active` inline.
- [x] T004 — Add `frontend/sea-speed/operator-common.css` to the VPS required lists in `scripts/quality/build_exact_artifacts.py` and `scripts/quality/validate_exact_artifacts.py`.
- [x] T005 — Extend `deploy/vps/deploy.sh`: target/URL vars, `release_complete`, download loop, install-to-release, bootstrap capture (live or `.absent`), `ensure_current_release_has_operator_css`, `css_state` guard, activation ordering, `verify_frontends` CSS check.
- [x] T006 — Prove ordered whole-rule equivalence for both pages (Water 129=22+107, Road 130=22+108).
- [x] T007 — Run `bash -n deploy/vps/deploy.sh` and `py_compile` of both quality scripts; confirm inventories converged.
- [x] T008 — Author this SDD trio (spec/plan/tasks) and pass `python3 scripts/ci/validate_sdd.py`.
- [ ] T009 — UI worker visual parity matrix (V-1..V-3) against the pre-#685 baseline (PENDING; not this worker).

## Completion gate

Deployment/merge is not performed by this worker. Completion gate for the
orchestrator: ordered-rule equivalence green, `bash -n` green, `py_compile`
green, inventories converged, SDD validator green, test worker suite green,
UI-worker visual matrix green, then merge + lane-A deploy. Until the UI matrix
and test suite land, AC-008 and the test-owned AC evidence remain open.

## Requirements traceability

- AC-001 | Task: T001 | Evidence: operator-common.css = 22 ordered rules, 2366 bytes, from :root through base .objects-link inclusive | Coverage: COVERED
- AC-002 | Task: T002,T003 | Evidence: both pages link /sea-speed/operator-common.css before <style>; residual starts at .objects-link:hover; .active inline only on Road | Coverage: COVERED
- AC-003 | Task: T006 | Evidence: ordered whole-rule reconstruction True for both pages (Water 129=22+107, Road 130=22+108) | Coverage: COVERED
- AC-004 | Task: T004 | Evidence: CSS present in both VPS inventories; validate VPS set is a subset of build VPS set | Coverage: COVERED
- AC-005 | Task: T005 | Evidence: deploy.sh declares OPERATOR_COMMON_CSS_TARGET/URL and covers release_complete, download, install, bootstrap, ordering, verify_frontends; bash -n OK | Coverage: COVERED
- AC-006 | Task: T005 | Evidence: ensure_current_release_has_operator_css + css_state accept pre-feature (neither file) only when HTML does not reference CSS; referencing-missing candidate rejected | Coverage: COVERED
- AC-007 | Task: T007 | Evidence: bash -n deploy/vps/deploy.sh OK; py_compile of both quality scripts OK | Coverage: COVERED
- AC-008 | Task: T009 | Evidence: pending UI-worker screenshot matrix V-1..V-3 | Coverage: RUNTIME-MANUAL | Reason: rendered visual parity requires a browser and the owner-visible shared screenshot artifacts, owned by the UI worker; not produced here

## Definition of Done

- Issue/spec/plan/tasks current: yes — spec/plan/tasks authored for #685 with the prefix boundary, equivalence proof, visual matrix, deploy audit and rollback case.
- Exact changed-file scope verified: yes — only `frontend/sea-speed/operator-common.css`, the two operator pages, the two quality inventories, `deploy/vps/deploy.sh`, and this SDD trio changed.
- Required tests and evidence complete: static evidence complete (equivalence True, bash -n OK, py_compile OK, inventories converged); test-worker suite and UI matrix still pending.
- Required CI green: pending orchestrator CI run (not executed by this worker).
- Exact-green-head merge complete: pending orchestrator (no merge performed here).
- Deployment state resolved: pending orchestrator lane-A deploy of the merged SHA.
- Runtime acceptance resolved: pending UI worker visual matrix and live upgrade/rollback probes.
- Deferred work recorded: yes — UI comparison (T009/AC-008), test-worker suite, live deploy/rollback exercise, base-SHA discrepancy.
- Risks resolved or explicitly accepted: RISK-001 mitigated by equivalence proof (visual residual pending UI); RISK-002 accepted pending first live rollback.
- Waivers resolved or current: none required.
