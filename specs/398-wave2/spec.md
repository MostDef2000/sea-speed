# Spec: #398 wave 2 — remaining cluster raw-source-text conversion (RB/SS/SP)

- Issue: #398
- Specification: specs/398-wave2/spec.md
- Authorization: six-field Scope for #398 approved by the owner; this wave = the remaining 16-file cluster of that scope (tests-only).

## Product outcome

The wave-2 regression cluster stops verifying deploy/worker/frontend behavior by reading source
files as raw text and starts verifying it by executing the real thing (RB) or parsing it
structurally (SS: `ast.parse`, `yaml.safe_load`, JSON, env-file KEY=VALUE). Raw `assertIn` /
byte-position pins become execution assertions or structured-shape assertions; STATIC_POLICY pins
(fail-closed shell markers whose textual presence is the deploy contract, workflow retirement
bans, anti-duplication sentinels) stay verbatim with in-code justification. Redundant text pins
retire only against recorded same-commit executed twins, so the battery is never weaker. A
two-direction demo (`tests/test_398_wave2_demo.py`) proves the conversion property on the real
road page.

## User scenarios

- A developer reformats a deploy script, renames a shell variable, or reflows a workflow YAML:
  the converted checks stay green (old text pins would have failed — false failure eliminated),
  except where the marker text itself IS the policy (SP pins deliberately still fail).
- A developer deletes the hash-locked install wiring, the M2M boundary verification, or the
  15 s session-watchdog interval while leaving the historical marker text in place: the converted
  check fails (old text pin would have passed — false pass eliminated).
- A future wave touches test-adjacent bytes without behavior change: review attention goes to
  real diffs instead of formatting churn.

## Scope

- tests/test_ubuntu_worker_installed_copy_refresh.py, tests/test_ubuntu_worker_runtime_hash_lock.py,
  tests/quality/test_quality_architecture.py, tests/test_ubuntu_worker_runtime_rebuild.py,
  tests/test_vps_auth_privilege_boundary.py, tests/test_detection_runtime_optimization.py,
  tests/test_analytics_profiles_configure_drift.py, tests/test_auth_session_frontend_contract.py —
  converted per the plan.md mapping table (RB→exec, SS→structured parse, SP verbatim,
  redundant→retired with twins).
- tests/support/frontend_html.py (new, additive) — HTML inline-script node-exec harness.
- tests/test_398_wave2_demo.py (new) — two-direction regression demonstration.
- specs/398-wave2/** — this trio.
- NO production surface: api/**, worker/**, frontend/**, deploy/**, .github/**,
  nginx/** untouched (wave-1 protected test files also untouched).
- Recorded orchestrator exception: `scripts/ci/validate_sdd.py` receives a one-line
  `398` entry in `GRANDFATHERED_PREFIX_COLLISIONS` (staged-wave precedent 396/397/520/537)
  so this trio is admissible; delivery-orchestrator addition, documented in plan.md
  Correct-course and tasks.md ledger. No other scripts/** surface is touched.

## Requirements

- R-1: every behavioral assertion carried by a raw text pin is replaced by an executed or
  structured twin per the plan.md mapping table; no assertion is lost without a recorded
  same-commit executed twin (redundancy ledger in tasks.md) or verbatim STATIC_POLICY retention.
- R-2 (SP justification): STATIC_POLICY pins kept verbatim carry an in-code justification comment
  (T8b deploy-transaction precedent, wave-1 D-6 wiring precedent, #514 anti-dup sentinel,
  forced-command/security bans).
- R-3: tests/test_398_wave2_demo.py proves both directions on tmp copies of the real page:
  (a) refactor tolerance — behavior-preserving reformat/rename passes the converted check while
  the retired text pins would fail; (b) dead-marker intolerance — marker text intact with broken
  wiring FAILS the converted check where the retired pins pass.
- R-4 (tests-only): if any conversion requires a production change → STOP and report; none did.
- R-5: the suite stays deterministic in CI — executed harnesses are offline (node stub DOM, tmp
  fixtures, no network); PyYAML is already pinned in CI (6.0.3).
- R-6: full battery green with per-file deltas accounted (never weaker); validate_repo and
  validate_sdd green; changed files limited to the allowed set.

## Acceptance criteria

- AC-001: all 16 cluster files adjudicated in the plan.md mapping table (converted / SP-kept /
  retired-with-twin / NO CHANGE) and every converted file's focused run is green.
- AC-002: battery delta vs baseline 1167 passed / 4 skipped / 262 subtests equals cluster net −8
  (F2 −3, F3 −1, F5 −3, F7 −1, F12 −1, F15 +1) plus demo +1, with the covering twin recorded in
  the tasks.md ledger for every removed assertion; observed 1160 / 4 / 271.
- AC-003: tests/test_398_wave2_demo.py passes with both explicit directions (refactor-tolerant
  AND dead-marker-intolerant), inverted-mutation run recorded in tasks.md.
- AC-004: full battery `pytest tests/ -q` green (observed 1160 passed / 4 skipped / 271 subtests).
- AC-005: `python3 scripts/ci/validate_sdd.py` green for this trio; `validate_repo.py` green
  (validate_repo observed green, 784 files).
- AC-006: `git status`/diff shows only tests/**, tests/support/**, specs/398-wave2/**
  plus the recorded orchestrator exception (one-line `398` grandfather entry in
  `scripts/ci/validate_sdd.py`, per Scope above).

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only change; no deploy and no production artifact
  changes. Runtime acceptance = exact-head CI green on the merge PR (the battery, including the
  node-exec suites, runs in CI).
- RF-002: after this wave the battery reports 1160 passed / 4 skipped / 271 subtests; every count
  delta vs the wave baseline is recorded in the tasks.md battery-delta ledger (retired assertion →
  covering executed twin, same commit). Subtests grew 262→271 (executed 11-sub-check classify
  matrix +7, legacy-HD read-back +2) — evidence that conversion made coverage observable, not
  smaller.

## NFR assessment

- NFR-001 | Area: reliability | Target: converted suites are deterministic (no network, tmp fixtures, stub DOM; node subprocess failures carry embedded stderr) | Validation: focused runs repeated across sessions; demo isolates mutations in tmp with cleanup | Evidence: full battery 1160 passed / 4 skipped | Status: PASS
- NFR-002 | Area: coverage | Target: zero coverage loss — every removed text assertion maps to an executed twin, a structured equivalent, or a retained verbatim SP pin; the classify order-mirror pin becomes STRONGER (all 11 sub-checks executed) | Validation: mapping table in plan.md; tasks.md redundancy ledger | Evidence: tests_run tails | Status: PASS
- NFR-003 | Area: performance | Target: battery wall time does not materially regress (43.24s vs 39.67s baseline; the executed classify matrix adds ~1.5s; one node spawn per frontend scenario) | Validation: full battery timing comparison vs baseline | Evidence: tests_run tails | Status: PASS
- NFR-004 | Area: maintainability | Target: ONE new support module (tests/support/frontend_html.py) beside the wave-1 harness; house conversion models only (node harness, yaml.safe_load, AST helpers from tests/support/worker_source.py) | Validation: reviewer check that no new framework/pattern was invented | Evidence: diff review | Status: PASS
