# Tasks: dead legacy mediamtx VPS script cluster cleanup

- Spec: specs/663-mediamtx-legacy-cleanup/spec.md

## Delivery tasks
- [x] Delete the three legacy VPS scripts: `deploy/vps/mediamtx-compatibility-remediation.sh`, `deploy/vps/mediamtx-systemd-v247-runner.sh`, `deploy/vps/camera1-final-cutover.sh` (RF-001)
- [x] Delete the two orphaned test files: `tests/test_mediamtx_compatibility_remediation.py` (14 tests), `tests/test_mediamtx_systemd_v247_runner.py` (7 tests) (RF-002)
- [x] Insert the #663 removal banner (insert-only, immediately after the H1) into `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md` and `docs/operations/MEDIAMTX_SYSTEMD_V247_COMPATIBILITY.md`, keeping every pre-existing line byte-identical (RF-003)
- [x] Write the SDD trio `specs/663-mediamtx-legacy-cleanup/{spec,plan,tasks}.md` and pass `scripts/ci/validate_sdd.py`
- [x] Run the full local battery: 1377 tests, OK (skipped=2); confirm `tests/test_398_wave6_demo.py` green on the bannered runbook
- [x] Run the reference grep: no live `*.py` references to the deleted script names outside the wave6 demo prose (RF-004)
- [ ] Create the #663 PR with the Change Contract (risk profile NOT REQUIRED, VPS deployment REQUIRED repo-level, operator actions 0)
- [ ] CI green on the #663 PR
- [ ] Merge the #663 PR to main

## Completion gate
- Full local battery green: 1377 tests, OK (skipped=2)
- validate_sdd green locally; validate_repo/validate_contracts green at PR time once the deletions are staged (#661 lesson: validate_secrets reads the git index)
- CI green on the #663 PR
- PR merged to main
- No runtime deployment in this chain: the removed scripts had no runtime presence (explicitly not a gate for this PR)

## Requirements traceability
- AC-001 | Task: deletions (3 scripts + 2 test files) | Evidence: git status --short shows exactly 5 D, 2 M docs, 3 untracked spec files; the five paths absent from the working tree | Coverage: COVERED
- AC-002 | Task: full local battery | Evidence: python3 -m unittest discover -s tests -p "test_*.py" → OK (skipped=2), 1377 tests (1398 baseline − 21) | Coverage: COVERED
- AC-003 | Task: insert-only banners + wave6 guard | Evidence: git diff docs/ = 10 insertions, 0 deletions; tests/test_398_wave6_demo.py green (section-scoped twins + 12 retired pins on the real runbook) | Coverage: COVERED
- AC-004 | Task: SDD trio + validators | Evidence: python3 scripts/ci/validate_sdd.py green on the delivered tree; validate_repo/validate_contracts green at PR time once the orchestrator stages the deletions (#661 unstaged-deletion gotcha) | Coverage: COVERED

## Definition of Done
- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
