# Spec: #398 wave 8 — cluster D residual (workflow-YAML extraction hardening) + outside-D residual inventory

- Issue: #398
- Specification: specs/398-wave8/spec.md
- Authorization: six-field Scope for #398 approved by the owner; wave 8 = the
  cluster D residual (workflow-YAML) of that scope per the wave-8 work order
  (base 4bde0e6, the wave-7 merge); owner phrase `commit approved` 2026-10-30.

## Product outcome

The two remaining workflow-YAML regex/line-scan EXTRACTION helpers stop
slicing raw workflow text and start reading the PARSED structure
(`yaml.safe_load`): tests/test_deploy_freshness.py
`_extract_freshness_run_block` walks `jobs` → `steps` and returns the `run`
of the step whose `id` is `freshness` (the YAML block scalar is already
dedented by the parser — the manual indent-stripping is gone), and
`_extract_sync_staging_command` walks ALL jobs' ALL steps' run texts and
returns the single line whose stripped form starts with `git add`
(word-boundary semantics kept), still requiring EXACTLY ONE match across
the workflow. Both extractions become comment-blind and reindent-safe: a
harmless workflow refactor (a YAML comment inserted in the previously swept
region, reindentation, step reordering) no longer changes the extracted
bytes, while a real structural change (a second staging command) still
fails the exactly-one invariant. The executed assertions at both usage
sites (the freshness block run in a git fixture; the staging command run
via shell) and all test methods stay byte-identical. The one unannotated
byte-ban pair (tests/quality/test_quality_architecture.py
`test_windows_package_workflow_is_retired`) gets its STATIC_POLICY verdict:
byte-absence of the retired Windows fallback markers IS the contract — a
parsed-structure absence check would be weaker (markers could survive in
comments) — with the tombstone assertFalse above covering file absence.
Finally, the OUTSIDE-D residual (raw source-text pins in 14 test files that
waves 1–7 never adjudicated, ~200 candidate pins) is inventoried with
per-file verdict classes and honest verification markers in plan.md —
conversion is OUT of scope pending an owner decision (a material change vs
the approved six-field scope, recorded as such). A one-test demo
(tests/test_398_wave8_demo.py) proves the conversion on in-memory fixtures:
Direction A carries the demo's RED-sensitivity (the parsed extraction is
refactor-blind where the module would return different bytes if it reverted
to the line-scan implementation — the demo fails there on a revert);
Direction B constrains only a verbatim documented copy of the retired
helper, recording its brittleness on the same reformat.

## User scenarios

- A developer reformats the freshness step's workflow YAML (inserts a YAML
  comment after the run block, reindents the steps list, reorders an
  unrelated step before it): the parsed extraction returns the identical
  run text and the executed freshness tests stay green — the retired
  line-scan helper returned different bytes on the same reformat (it swept
  past the reindented step terminator and swallowed the comment into the
  "script"), a false failure the conversion removes (proven by the demo).
- A developer adds a second `git add` line inside a sync workflow run
  block: the exactly-one staging invariant fails loudly with the full match
  list; conversely a non-executable `git add` mention outside step run
  texts (note field, comment) no longer trips the invariant — the old
  whole-file regex false-failed on those.
- A reviewer reads test_windows_package_workflow_is_retired: the byte-ban
  verdict is recorded in-code (STATIC_POLICY) — byte-absence is the
  retirement contract, the tombstone covers file absence — so the next
  conversion wave does not re-litigate it.

## Requirements

- R-1: `_extract_freshness_run_block` performs a parsed step lookup
  (`yaml.safe_load`, walk `jobs` → `steps`, match `id == "freshness"`,
  return `step["run"]`) with meaningful AssertionErrors when the step is
  missing or its run is empty/missing; the returned script stays
  byte-identical for the real workflow (YAML clip chomping preserves the
  single trailing newline — probed before implementation), so the executed
  tests stay green untouched.
- R-2: `_extract_sync_staging_command` performs a parsed walk of ALL jobs →
  ALL steps' run texts, scans lines with `git add\b` word-boundary semantics
  on the stripped line, requires EXACTLY ONE match across the workflow and
  returns it (old message shape kept); comment-only lines and non-run
  regions no longer match (strictly stronger scoping than the whole-file
  regex).
- R-3 (no weakening): no test method, assertion, env-override constant
  (SEA_SPEED_DEPLOY_FRESHNESS_WORKFLOW / SEA_SPEED_SYNC_TASKS_WORKFLOW) or
  fixture is touched; the module docstring stays accurate (it says
  "extract", not "regex"); each converted helper carries the wave-8
  conversion comment.
- R-4 (SP annotation): the two raw assertNotIn pins in
  test_windows_package_workflow_is_retired carry a STATIC_POLICY comment
  (byte-absence IS the contract; parsed-absence would let markers survive
  in comments; the tombstone covers file absence); the assertions and the
  tombstone assertFalse stay byte-identical.
- R-5 (demo): tests/test_398_wave8_demo.py — exactly ONE test function —
  proves (a) reformat-equivalence (comment insertion + reindentation + step
  reordering → identical extracted run text, equal to the expected script
  bytes) and (b) old-approach brittleness (a verbatim documented copy of the
  retired line-scan helper raises or returns different bytes on the same
  reformat); the demo imports the real module helpers (no mocking) and
  fails if the extraction were still line-scan-based.
- R-6 (inventory): plan.md carries the complete outside-D residual inventory
  (14 files) with per-file verdict classes and honest verification markers
  ("verified raw" / "heuristic count, verification pending" / adjudicated
  NO-CHANGE), transcribed from the wave-8 work order; conversion of those
  files is OUT of scope pending owner decision.
- R-7 (tests-only): no product/deploy/workflow file changes; the only
  non-test change is the recorded grandfather entry (`398-wave8`) in
  scripts/ci/validate_sdd.py with the cluster-D closure note; no new
  dependencies beyond PyYAML (already used by the wave-5 files).
- R-8: full battery green with the identity vs the baseline recorded
  (baseline 1230 passed / 2 skipped / 306 subtests on 4bde0e6; expected
  1231 = 1230 + 1 demo test); validate_sdd green for the trio after the
  grandfather line; ruff clean.

## Acceptance criteria

- AC-001: both cluster-D files are adjudicated in the plan.md mapping
  (test_deploy_freshness.py converted to parsed step lookup;
  test_quality_architecture.py SP-kept with the STATIC_POLICY annotation)
  and the focused run over both files + the demo is green. → TEST-001
- AC-002: the battery identity vs the baseline (1230 passed / 2 skipped /
  306 subtests on base 4bde0e6) is recorded in the tasks.md ledger with the
  per-site twin mapping; expected observed identity 1230 + 1 demo = 1231
  passed / 2 skipped / 306 subtests. → TEST-002
- AC-003: the outside-D residual inventory table in plan.md is complete
  (all 14 residual files + the adjudicated NO-CHANGE rows) with per-file
  verdict class and honest "verified this session" vs "heuristic count,
  verification pending" markers. → TEST-003

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only + one validator line
  (CONTROL_PLANE); no deploy and no production artifact changes. Runtime
  acceptance = exact-head CI green on the merge PR (the battery, including
  the demo, runs in CI; PyYAML is already available in the CI test env).
- RF-002: post-wave focused cluster reports 15 passed (6 freshness +
  8 architecture + 1 demo); the battery delta is +1 (demo only) — both
  converted helpers are module-level extraction functions, so the cluster
  test count is otherwise flat; every delta is recorded in the tasks.md
  ledger.

## NFR assessment

- NFR-001 | Area: reliability | Target: both extractions are deterministic parsed lookups (yaml.safe_load on in-memory text; no network; no new dependencies beyond PyYAML already used by the wave-5 files) | Validation: focused runs repeated across sessions; mutation probes on tmp copies only | Evidence: focused run 15 passed; mutation probes (a)/(b)/(d) green, (c) RED with the exactly-one message | Status: PASS
- NFR-002 | Area: coverage | Target: zero coverage loss — the extraction hardening touches no assertion; the SP annotation records the byte-ban verdict without touching the assertions; the inventory records the outside-D residual honestly instead of silently dropping it | Validation: mapping table in plan.md; tasks.md ledger; git diff inspection | Evidence: diff shows only helper bodies + import + annotation comment + demo + trio + validator line | Status: PASS
- NFR-003 | Area: performance | Target: wall time bounded — the focused cluster stays ~1.3s; the battery stays ~73s (parsed lookups replace regex scans on the same small files) | Validation: focused and battery timing observations | Evidence: run tails in tasks.md | Status: PASS
- NFR-004 | Area: maintainability | Target: house conversion models only (the wave-5/8 canon: yaml.safe_load parsed step lookup, comment-blind, reindent-safe; SP pins kept verbatim with recorded verdict) — no new framework/pattern invented | Validation: reviewer check that no new framework/pattern was invented | Evidence: diff review | Status: PASS
