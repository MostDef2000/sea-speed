# Spec: dead legacy mediamtx VPS script cluster cleanup

- Issue: #663

## Product outcome
The dead legacy mediamtx-era VPS tooling cluster is removed from the repository: the three scripts (`deploy/vps/mediamtx-compatibility-remediation.sh`, `deploy/vps/mediamtx-systemd-v247-runner.sh`, `deploy/vps/camera1-final-cutover.sh`) and their two orphaned test files are deleted, and the two runbooks (`docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md`, `docs/operations/MEDIAMTX_SYSTEMD_V247_COMPATIBILITY.md`) carry prominent removal banners. History is preserved in the docs (mark, never erase — precedent #661). No runtime impact: the scripts were never deployed and have no runtime presence — the #661 delivery record explicitly deferred them as a separate decision ("легаси-хвосты ... отдельное решение, не трогались"), which #663 executes.

## User scenarios
- A repository reader searching for the legacy mediamtx compatibility tooling finds both runbooks retained in full, each headed by a banner stating the tooling was removed in #663 and the scripts no longer exist in the repo; the historical body (including the line-38 `camera1-final-cutover.sh` entry-point description in the v247 runbook) is retained as record below the banner.
- A contributor running the full test battery gets exactly the pre-cleanup suite minus the 21 orphaned tests (14 + 7) that exercised the deleted scripts; no other test changes.
- An operator listing `deploy/vps/` sees only live tooling; the internal dependency chain (`camera1-final-cutover.sh:9` → `mediamtx-systemd-v247-runner.sh:10` → `mediamtx-compatibility-remediation.sh`) dies with the files, so no launcher references a missing runner.

## Requirements
1. RF-001: Delete the three legacy VPS scripts `deploy/vps/mediamtx-compatibility-remediation.sh`, `deploy/vps/mediamtx-systemd-v247-runner.sh` and `deploy/vps/camera1-final-cutover.sh` (the cluster entry point; it breaks with exit 7 once the runner is gone and has no other live references).
2. RF-002: Delete the two orphaned test files `tests/test_mediamtx_compatibility_remediation.py` (14 tests) and `tests/test_mediamtx_systemd_v247_runner.py` (7 tests) — exactly 21 tests leave the battery.
3. RF-003: Insert a short removal banner (2-4 lines, insert-only) immediately after the H1 of both runbooks stating the tooling was removed in #663, the scripts no longer exist in the repo, and the document is retained as a historical record; every pre-existing line stays byte-identical and no new heading may collide with the wave6 demo's section scopes.
4. RF-004: After the deletion, no live references to the removed scripts remain outside historical specs (`specs/075-*`, `specs/076-*`) and prose history (closed spec records, the bannered runbooks themselves, the wave6 demo's prose comments about the retained doc).

Out of scope: `deploy/vps/camera1-direct-h264-cutover.sh` (verified independent), `deploy/vps/README.md`, `.github/workflows/**`, historical specs 075/076 and every other closed spec record, the renderer, frontend, worker and api.

## Acceptance criteria
- AC-001: The five files (three scripts + two test files) are absent from the working tree; `git status --short` shows exactly 5 deletions, 2 modified docs and 3 untracked spec files.
- AC-002: The full unittest battery is green: 1377 tests, OK (skipped=2) — the #661 baseline 1398 minus exactly the 21 deleted tests.
- AC-003: Both runbooks carry the #663 removal banner with all pre-existing content intact (insert-only diff); `tests/test_398_wave6_demo.py` — the section-scoped guard reading MEDIAMTX_COMPATIBILITY_REMEDIATION.md — stays green.
- AC-004: `scripts/ci/validate_sdd.py` is green on the delivered tree; validate_repo/validate_contracts green at PR time once the deletions are staged (#661 lesson: validate_secrets reads the git index, so unstaged deletions fail validate_repo; staging fixes it and no pinned reference exists).

## Runtime feedback
- The #661 delivery (PR #662, merge `23c29ef`) deleted `camera-source-switch.sh` and marked four runbooks; its record explicitly left the `mediamtx-compatibility-remediation.sh` / `mediamtx-systemd-v247-runner.sh` tails as "отдельное решение, не трогались" — #663 executes that decision and completes the cluster removal (`camera1-final-cutover.sh` was the entry point into those two scripts).
- No runtime feedback loop applies: the scripts were never deployed and never executed on any contour; removal is repo-only with zero production impact and no operator action.

## NFR assessment
- NFR-001 | Area: Maintainability | Target: No dead legacy mediamtx-era VPS tooling or orphaned tests remain in the repository; history preserved in marked runbooks | Validation: git status scope check + repo-wide reference grep | Evidence: 5 deletions in the diff; remaining mentions only in historical spec records and the bannered runbooks' retained prose | Status: PASS
- NFR-002 | Area: Compatibility | Target: Zero runtime impact — the deleted scripts were never deployed and no runtime contour references them | Validation: full unittest battery + repo-wide grep for the three script names | Evidence: battery 1377 OK (skipped=2); no live references outside historical specs and prose history | Status: PASS
- NFR-003 | Area: Maintainability | Target: Retained runbooks keep every pre-existing line byte-identical (mark, never erase) while clearly marking the removal | Validation: insert-only diff inspection + tests/test_398_wave6_demo.py green | Evidence: git diff shows 10 inserted lines and 0 deleted/modified lines across the two docs; the wave6 demo (section-scoped twins + 12 retired pins on the real runbook) passes | Status: PASS
