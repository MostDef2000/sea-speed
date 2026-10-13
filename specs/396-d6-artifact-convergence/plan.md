# 396 — D-6 Plan: exact-artifact convergence (bidirectional)

- Issue: #396
- Specification: specs/396-d6-artifact-convergence/spec.md

## Architecture

Validation-only extension of `scripts/quality/validate_exact_artifacts.py` plus
one new focused test module. The validator already imports from its own package
(`scripts.quality.common`); it now also imports `COMPONENT_FILES` from
`scripts.quality.build_exact_artifacts` (constants-only module, no side effects)
so the required-module side of the invariant has a single source of truth — the
validator never re-states the build list. The deploy.sh side is derived at
validation time by `deploy_app_module_targets()` from the two TARGET-definition
idioms deploy.sh has used since wave 1: `API_TARGET="${SEA_SPEED_API_TARGET:-.../app/main.py}"`
(env-default) and `<NAME>_TARGET="$(dirname "$API_TARGET")/<m>.py"` (dirname).
The convergence function is wired into `main()` immediately after the manifest
schema check — fail-fast, before the heavy digest/extraction work. No new
processes, no new CI steps: every existing invocation of the validator
(quality-integration.yml x2, deploy-vps.yml, deploy-ubuntu-worker.yml) now
carries the check.

## Decisions

- D-1 (scope): the invariant covers the api/app module set only — the exact
  #396 pain set. Deploy plumbing files (deploy.sh, cutover, helper, nginx
  scripts) live in the build required list but are intentionally not
  TARGET-mirrored (they run from the release dir); frontends are mirrored but
  are not modules and carry no `.py` path, so the parser ignores them.
- D-2 (mirror anchor = TARGET definitions): deploy.sh mirrors each module
  through seven sites (wave-6 plan D-3), all consuming or repeating the
  `<NAME>_TARGET` definition; the definition line is the canonical declarative
  anchor. Checking all seven sites would duplicate deploy.sh's internal
  consistency problem inside the validator; the transaction suite
  (test_vps_deploy_transaction) already exercises the consumed sites.
- D-3 (parse contract): `_TARGET="(.*)"$` per line (greedy to the closing
  quote handles embedded quotes in the dirname idiom), then module names from
  `app/<m>.py` (env-default idiom) and `$(dirname "$API_TARGET")/<m>.py`
  (dirname idiom). Verified against all 18 TARGET assignments on converged
  main: exactly the 10 api/app modules, zero false positives.
- D-4 (fail-closed messages): each direction raises SystemExit naming the
  offending paths ("not mirrored by deploy/vps/deploy.sh TARGET sites: ..." /
  "deploy/vps/deploy.sh TARGET api/app modules missing from vps required list:
  ...") so the fix is mechanical in both directions.
- D-5 (test design): function-level fixtures mutate a copy of the real inputs
  (required set / deploy.sh text) — no repository files are mutated by tests;
  one end-to-end test builds and validates real artifacts and additionally
  text-pins the wiring (validator source must reference the convergence
  function), preventing silent unwinding.
- D-6 (trio placement deviation, resolved): the work order's literal path
  `specs/d6-artifact-convergence/` has no numeric prefix and hard-fails
  validate_sdd (`FEATURE_DIR_RE = ^\d{3,}-`; every existing trio dir carries
  the prefix of its canonical issue). Following the wave-6 D-5 precedent, the
  trio lives at `specs/396-d6-artifact-convergence/` (canonical issue #396,
  same program family) and `GRANDFATHERED_PREFIX_COLLISIONS["396"]` gains the
  one new dir — the mechanism exists precisely for multiple trios under one
  issue; no test pins the set's membership, only the fail-closed behavior for
  unregistered duplicates, which is preserved.

## Affected contours

- CI tooling only: `scripts/quality/validate_exact_artifacts.py`,
  `scripts/ci/validate_sdd.py` (grandfather data line),
  `tests/quality/test_exact_artifact_convergence.py` (new), and this trio.
- VPS / Ubuntu Worker / edge runtime behavior: unchanged — no api/**, no
  frontend, no worker, no deploy.sh change; exact-artifact bytes unchanged.
- PR Change Contract: VPS deployment NOT REQUIRED; Ubuntu worker/relay update
  NOT REQUIRED; route table untouched.

## Validation

- RED-first: new test module observed failing against base
  (`ImportError: cannot import name 'deploy_app_module_targets'`), and both
  sandbox drift scenarios observed exiting 0 against the base validator
  (Scenario A: ghost module in build list, clean deploy.sh → "Exact artifacts
  valid", exit 0; Scenario B: `GHOST_TARGET` in deploy.sh, clean build list →
  exit 0). After the fix both scenarios exit 1 with the D-4 messages.
- New tests: `tests.quality.test_exact_artifact_convergence` 5/5 OK.
- Battery: full suite Ran 915 OK (skipped=4) — delta exactly +5, zero other
  drift; validate_repo (678 files); validate_sdd (grandfathered #396 set + D-6);
  ruff 0.16.10 with `--config scripts/quality/ruff.toml` (CI invocation) All
  checks passed; `bash -n deploy/vps/deploy.sh` OK.

## Runtime feedback

None required — CI-tooling only, no runtime deploy, no behavior visible on any
contour. Post-merge evidence is CI green on the exact head.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001, AC-002, AC-003 (bidirectional fail-closed + parser contract) | Level: unit | Priority: P0 | Evidence: tests/quality/test_exact_artifact_convergence.py 5/5 OK; direction A/B fixtures raise SystemExit with D-4 messages
- TEST-002 | Covers: AC-004 (RED-first: drift passed against base, fails closed after) | Level: unit | Priority: P0 | Evidence: RED ImportError observed pre-fix; sandbox scenarios A/B exit 0 pre-fix and exit 1 post-fix (observed output in progress-d6.md)
- TEST-003 | Covers: AC-005 (no regression; convergence holds end-to-end) | Level: integration | Priority: P0 | Evidence: battery Ran 915 OK (skipped=4), delta exactly +5; end-to-end build+validate on real repo 0.34s OK; validate_repo 678; validate_sdd; ruff 0.16.10 clean; bash -n OK

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
