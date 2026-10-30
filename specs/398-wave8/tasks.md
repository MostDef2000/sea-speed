# Tasks — Issue #398 wave 8

- Issue: #398
- Specification: specs/398-wave8/spec.md

## Delivery tasks

- T-1: tests/test_deploy_freshness.py — `_extract_freshness_run_block`
  (L58–81 line-scan: `id: freshness` anchor, `run: |` scan, `^      - name:`
  terminator, manual dedent) converted to the parsed step lookup
  (`yaml.safe_load` → jobs → steps → `id == "freshness"` → `step["run"]`;
  the parser dedents the block scalar; clip chomping keeps the single
  trailing newline — byte-identical to the old output, probed before
  implementation); `_extract_sync_staging_command` (L228–232 whole-file
  regex `(?m)^\s*(git add\b.*)$`) converted to the parsed ALL-jobs →
  ALL-steps run-text line scan with `git add\b` word-boundary semantics and
  the exactly-one invariant (old message shape kept); unconditional
  `import yaml` added (wave-5 pattern); usage sites L148/L244, all test
  methods, env overrides and the FreshnessFixture byte-identical; module
  docstring unchanged ("extract" stays accurate; no "regex" mention); the
  wave-8 conversion comment added on both helpers. DONE (6 passed).
- T-2: tests/quality/test_quality_architecture.py — STATIC_POLICY
  annotation added above the L205–206 assertNotIn pair in
  test_windows_package_workflow_is_retired (byte-absence of the retired
  Windows fallback markers IS the contract; parsed-structure absence would
  let markers survive in comments; the tombstone check covers file
  absence); the assertions and the tombstone assertFalse byte-identical.
  DONE (8 passed).
- T-3: Demo tests/test_398_wave8_demo.py — exactly ONE test function
  (test_refactor_tolerance_and_legacy_line_scan_brittleness): Direction A
  reformat-equivalence (comment insertion + steps reindent + step reorder →
  identical extraction, equal to the expected script bytes); Direction B
  old-approach brittleness (verbatim documented copy of the retired
  line-scan helper — demo-twin-копия — returns different bytes on the same
  reformat); imports the real module helpers (wave-5 pattern), no mocking.
  DONE (1 passed).
- T-4: This SDD trio (specs/398-wave8/) — cluster-D mapping table +
  the outside-D residual inventory (14 files, per-file verdict classes,
  honest "verified raw" vs "heuristic count" markers) + the adjudicated
  NO-CHANGE rows. DONE.
- T-5: Grandfather line — scripts/ci/validate_sdd.py "398" set +=
  "398-wave8" + the cluster-D closure note (wave 8 final; outside-D
  residual inventoried pending owner decision); allowed-paths self-check;
  full battery worker-run per the work order. DONE.

## Completion gate

- Focused `python3 -m pytest -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w8/pytest-tmp tests/test_deploy_freshness.py
  tests/quality/test_quality_architecture.py tests/test_398_wave8_demo.py
  -q`: OBSERVED 15 passed in 1.30s (6 freshness + 8 architecture + 1 demo).
- Full battery `python3 -m pytest -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w8/pytest-tmp tests/ -q`: OBSERVED 1231
  passed / 2 skipped / 306 subtests in 77.08s (base 1230 passed / 2 skipped
  / 306 subtests on 4bde0e6, orchestrator-provided baseline; identity
  1230 + 1 demo method = 1231; subtests unchanged).
- Mutation evidence (tmp copies under /tmp/opencode/398-w8/mutations/,
  env-override runs, never in-repo): (a) comment line in the freshness run
  region → 6 passed (parsed run text identical to the real workflow,
  probed); (b) steps list reindented → 6 passed (run text identical,
  probed); (c) second `git add` inside a run block → 1 failed with exactly
  `AssertionError: expected exactly one git add staging command in sync
  workflow, got ["git add -- ':(glob)specs/*/tasks.md'", "git add --
  ':(glob)specs/*/plan.md'"]` (tests/test_deploy_freshness.py:233);
  (d) `#`-comment containing `git add` → 1 passed — CC-1 records the probed
  correction: the old regex was already blind to `#`-prefixed comments; its
  real weakness was the whole-file scan scope (false-fails on a
  non-executable line-start `git add` mention in a note field — probed,
  parsed walk unaffected).
- `python3 scripts/ci/validate_sdd.py` → PASS ("Sea Speed SDD validation
  passed") with the trio + the `398-wave8` grandfather line.
- ruff clean on every changed file (`python3 -m ruff check --config
  scripts/quality/ruff.toml` → All checks passed).

## Requirements traceability

- AC-001 | Task: T-1, T-2 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-1, T-3, T-5 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-4 | Evidence: TEST-003 | Coverage: COVERED

Requirement notes: R-1/R-2 → the converted helpers with the wave-8 comments
(mapping table in plan.md); R-3 → git diff shows only helper bodies + the
import (assertions/fixtures/env overrides untouched); R-4 → the
STATIC_POLICY annotation; R-5 → the demo's two-direction proof; R-6 → the
inventory tables in plan.md; R-7 → git status limited to the allowed paths;
R-8 → the battery identity above.

## Battery-delta ledger (base 4bde0e6 = wave-7 merge; identity: 1230 + 1 demo method = 1231 passed / 2 skipped / 306 subtests, OBSERVED)

| File | Delta (base→now) | Site → twin/rationale (same commit) |
|------|------------------|-------------------------------------|
| test_deploy_freshness.py | 0 (6→6) | L58–81 line-scan extraction → parsed step lookup (yaml.safe_load; comment-blind, reindent-safe; byte-identical run text, probed before implementation); L228–232 whole-file regex → parsed ALL-jobs/ALL-steps run-text scan with the exactly-one invariant; usage sites, assertions, fixtures and env overrides untouched |
| test_quality_architecture.py | 0 (8→8) | L205–206 assertNotIn pair → SP-KEEP + STATIC_POLICY annotation (byte-absence IS the contract; parsed-absence weaker — markers could survive in comments; tombstone assertFalse covers file absence) |
| demo tests/test_398_wave8_demo.py | +1 (new file: test_refactor_tolerance_and_legacy_line_scan_brittleness) | new two-direction regression demonstration (additive) |

Arithmetic note: both cluster-D files converted IN PLACE at 0 test-count
delta (only module-level helper bodies, one import and one annotation
comment changed); the battery delta is the demo +1; skips and subtests
unchanged (2 / 306).

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [x] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main (dfbe094b)
- [x] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main (dfbe094b)
- [x] Deployment state resolved — NOT REQUIRED (tests-only + one validator line = CONTROL_PLANE; no runtime artifact changes)
- [ ] Runtime acceptance resolved — runtime acceptance = exact-head CI green on the merge PR (RF-001)
- [x] Deferred work recorded — the outside-D residual (14 files, ~200 candidate pins) is inventoried in plan.md pending owner decision (wave-9 candidate or documented closure); waves 1–7 NO-CHANGE records stand
- [x] Risks resolved or explicitly accepted — plan.md Risk profile: NOT REQUIRED (tests-only wave)
- [x] Waivers resolved or current — no waivers

Wave record: cluster D closed (both files adjudicated: parsed step-lookup
conversion + SP-keep with the STATIC_POLICY annotation); battery delta +1
(demo only) with the identity recorded; no assertion weakened or skipped;
the outside-D residual (~200 candidate pins in 14 files) inventoried with
per-file verdict classes and honest verification markers, conversion out of
scope pending owner decision; mutation evidence recorded ((a)/(b)/(d)
green, (c) RED with the exactly-one message); validate_sdd.py grandfather
entry `398-wave8` added (one line + closure note, orchestrator-recorded
exception).
