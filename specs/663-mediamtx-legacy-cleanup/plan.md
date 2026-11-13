# Plan: dead legacy mediamtx VPS script cluster cleanup

- Spec: specs/663-mediamtx-legacy-cleanup/spec.md

## Architecture
Pure removal, no new logic. The deletion set is one dead dependency chain inside `deploy/vps/`: `camera1-final-cutover.sh` (thin resumable launcher) references `mediamtx-systemd-v247-runner.sh` at line 9 (`COMPAT_RUNNER=`), which references `mediamtx-compatibility-remediation.sh` at line 10 (`CORE=`) — the chain dies with the files, so no dangling reference is created inside the deletion set. The two orphaned unittest files (the only code readers of the scripts) die with them, shrinking the battery by exactly 21 tests (14 + 7). The two runbooks are retained as historical records with an insert-only banner immediately after the H1; the banner is a blockquote (not a heading), so the `tests/support/markdown_docs.py` section scanner sees no new section and the wave6 demo's section-scoped twins and `_replace_exact` anchors (all below the H1) are untouched.

## Decisions
- `camera1-final-cutover.sh` is in scope: it is the entry point of the cluster (its only purpose is delegating prepare/activate/status to the v247 runner), it breaks with exit 7 once the runner is gone, and a repo-wide grep shows no other live references — keeping a launcher whose sole target is deleted would violate the #637 minimum-code rule (delete a dead mechanism entirely).
- Historical specs 075/076 stay untouched (as does every other closed spec record mentioning the scripts or their tests): they are immutable audit history; the #661 mark-never-erase precedent applies to the live runbooks, not to rewriting historical spec records.
- Deletion over deprecation: the scripts have no runtime presence (never deployed; no workflow, README or renderer reference), so there is no deprecation window to serve.
- Banners are insert-only blockquotes immediately after the H1: no existing line is modified or deleted, no heading is added, and the banner text avoids every retired pin and co-marker string the wave6 demo matches on — `tests/test_398_wave6_demo.py` remains green and stays the guard for the bannered doc.
- The historical line 38 of `MEDIAMTX_SYSTEMD_V247_COMPATIBILITY.md` still names `camera1-final-cutover.sh`: left as-is deliberately — the banner above it explains the removal (mark, never erase).
- No new tests: this is a deletion task; the existing battery is the safety net and shrinks by exactly the 21 deleted tests; `tests/test_398_wave6_demo.py` is the doc-banner guard.

## Affected contours
- VPS (single contour, repo-only — not MIXED): `deploy/vps/mediamtx-compatibility-remediation.sh`, `deploy/vps/mediamtx-systemd-v247-runner.sh`, `deploy/vps/camera1-final-cutover.sh` deleted; `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md` and `docs/operations/MEDIAMTX_SYSTEMD_V247_COMPATIBILITY.md` bannered. No Ubuntu worker/relay, frontend, api or worker files change and no server execution occurs.
- Tests: `tests/test_mediamtx_compatibility_remediation.py`, `tests/test_mediamtx_systemd_v247_runner.py` deleted (21 tests).
- SDD: `specs/663-mediamtx-legacy-cleanup/` (spec, plan, tasks).
- Explicitly unchanged: `deploy/vps/camera1-direct-h264-cutover.sh` (verified independent), `deploy/vps/README.md` (references none of the deleted scripts), `tests/test_398_wave6_demo.py` + `tests/support/markdown_docs.py` (live readers of the bannered doc), `specs/075-*`/`076-*` (historical), `.github/**`, `scripts/**`, `frontend/**`, `worker/**`, `api/**`.

## Validation
- Full battery: `python3 -m unittest discover -s tests -p "test_*.py"` → 1377 tests, OK (skipped=2) — baseline 1398 minus exactly the 21 deleted tests.
- Focused guard: `tests.test_398_wave6_demo` green (the real runbook still satisfies every section-scoped twin and all 12 retired pins after the banner insertion).
- `python3 scripts/ci/validate_sdd.py` green with the new trio.
- `git status --short` shows exactly 5 deletions, 2 modified docs and 3 untracked spec files.
- Reference grep: no `*.py` under tests/ references the deleted script names outside the wave6 demo's prose comments.
- validate_repo/validate_contracts run green at PR time once the orchestrator stages the deletions (#661 lesson: validate_secrets reads the git index, so unstaged deletions fail validate_repo with FileNotFoundError; staging the deletion fixes it and no pinned reference exists).

## Runtime feedback
- The #661 delivery record deferred exactly this cluster ("Легаси-хвосты mediamtx-compatibility-remediation.sh / mediamtx-systemd-v247-runner.sh — отдельное решение, не трогались"); #663 closes it, adding the cluster entry point `camera1-final-cutover.sh` to the same removal.
- No runtime feedback applies: the scripts were never deployed, never executed on any contour, and no deploy workflow or runbook instruction invokes them; removal has zero production impact.

## Risk profile
- Risk profile: NOT REQUIRED

Rationale: Security impact NONE — the change is a pure deletion of three
never-deployed VPS scripts and their two orphaned test files, plus insert-only
doc banners and a new SDD trio. No security, schema or destructive-operation
trigger applies: nothing existing is weakened or bypassed, no secrets,
credentials or config contracts are touched, the scripts never reached a
runtime contour (no deploy workflow, README or runbook references them), and
the doc banners add lines without removing any. The safety net is the existing
battery (1377 tests, including `tests/test_398_wave6_demo.py`, which pins the
bannered runbook's section-scoped contract) plus the SDD/contract validators
at PR time. Runtime acceptance is not applicable: there is no runtime
deployment in this chain — the removed scripts had no runtime presence, so no
contour update, operator action or rollback surface exists beyond `git revert`
of the merge commit.

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `git status --short` shows exactly 5 D (three scripts + two test files), 2 M docs and 3 untracked spec files; the five paths are absent from the working tree
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: full `python3 -m unittest discover -s tests -p "test_*.py"` tail `OK (skipped=2)` with 1377 tests (1398 baseline − 21 deleted)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: `git diff docs/` = 10 insertions, 0 deletions (insert-only banners); `tests/test_398_wave6_demo.py` green (real runbook satisfies all section-scoped twins and retired pins post-banner)
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: `python3 scripts/ci/validate_sdd.py` → "Sea Speed SDD validation passed"; validate_repo/validate_contracts green at PR time after the deletions are staged (#661 unstaged-deletion gotcha)

## Correct-course check
- Trigger: NONE
- Issue impact: requirements stable since issue #663 opened; the approved scope is pure removal
- Specification impact: none — the spec matches the locked scope (5 deletions, 2 banners, SDD trio)
- Plan impact: none — no deviation discovered during implementation
- Tasks impact: none — delivery tasks executed as written
- Authorization impact: NONE
- Follow-up: none required; no runtime deployment exists in this chain

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no branch, no changes applied | Retry: N/A | Rollback: N/A | Evidence: branch agent/663-mediamtx-legacy-cleanup created from base 23c29ef; scope locked to the 10 allowed paths
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: working tree clean at base; no repo or runtime state touched | Retry: N/A | Rollback: N/A | Evidence: pre-edit recon confirmed the 5 files dead (no live references outside historical specs and prose history) and the wave6 demo anchors all below the H1
- TX-003 | Stage: MUTATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: partial repo edit visible in git status; no runtime state exists to corrupt | Retry: re-apply the remaining deletions/banner inserts | Rollback: git checkout the 5 deleted paths and the 2 docs | Evidence: git status shows exactly the 5 deletions, 2 doc modifications and 3 new spec files
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not opened | Retry: re-run battery and validators | Rollback: N/A | Evidence: battery tail OK (skipped=2) with 1377 tests; validate_sdd green; wave6 demo green; reference grep empty
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: PR open, main unchanged | Retry: re-run CI / re-merge per orchestrator | Rollback: close the PR or revert the merge commit | Evidence: PR head SHA with required CI green, recorded by the orchestrator
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: re-record | Rollback: N/A | Evidence: JOURNAL.md entry for #663
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence tails missing from the delivery record | Retry: re-run and re-capture | Rollback: N/A | Evidence: battery/validator output tails quoted in the PR delivery record
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: N/A in this chain (no runtime mutation) | Retry: N/A | Rollback: git revert of the merge commit restores the 5 files, removes the banners and the trio | Evidence: git revert on main

- Deployment fields for the PR Change Contract: VPS deployment REQUIRED (repo-level only — no runtime execution in this chain), Ubuntu worker/relay update NOT APPLICABLE, VPS execution capability CONNECTOR, Operator actions expected: 0.
