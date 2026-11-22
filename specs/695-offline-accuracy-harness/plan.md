# Plan: #695 — Offline accuracy harness

- Issue: #695
- Specification: specs/695-offline-accuracy-harness/spec.md

## Architecture

One stdlib-only CLI plus one committed synthetic dataset, with no runtime,
deploy or CI wiring.

- `scripts/worker/accuracy_harness.py` reads the `--pairs` JSON array, validates
  every record against the closed input contract, computes the six confusion
  cells and three rates, then writes the `--output` report. It imports only
  `argparse`, `hashlib`, `json`, `sys` and `pathlib`; it performs no network,
  git, clock, hostname or environment reads.
- `scripts/worker/accuracy_pairs_synthetic_v1.json` is a hand-authored,
  media-free array of 13 records with the fields `id`, `truth`, `outcome` and
  opaque synthetic IDs. Its frozen decisions are A,B,C = 4,1,2 and D,E,F =
  2,3,1; the derived rates are 0.333333, 0.230769 and 0.7.
- `specs/695-offline-accuracy-harness/` records the closed metric contract, the
  Gherkin acceptance examples, the quality layer and the traceability.

Data flow: `--pairs` bytes -> UTF-8/JSON decode -> per-record validation
(exact key set, string types, nonblank unique IDs, enum membership, duplicate
JSON keys) -> validated rows -> confusion counts -> exact rational rates ->
canonical fingerprint -> sorted-key JSON bytes -> `--output`. Validation
completes before the output path is opened, so an invalid input can never
replace an earlier report.

## Decisions

- **New standalone script, not an extension of the benchmark stub.** The
  `benchmark_detector_frequency.py` CLI shape (`--matrix`/`--output`, argparse)
  is the precedent, but its empty `results` list and zero commit field are an
  honest stub; copying its behaviour would produce a vacuous report. The new
  script copies only the CLI shape.
- **Exact three-field input, extra fields rejected.** A permissive reader would
  let a typo (`truh`) through as a missing field or silently ignore an extra
  label; the contract requires exactly `id`, `truth`, `outcome`, all strings.
- **Fingerprint over validated rows, not file bytes or filename.** Hashing the
  file would make indentation and row order part of the identity and would let
  the absolute filename leak into the report. Sorting validated rows by `id`
  and hashing canonical compact JSON makes the fingerprint a property of the
  labelled cases only.
- **Integer half-even rounding, not float `round`.** The contract says "exact
  fraction rounded to 6 decimal places, nearest with ties to even"; scaling by
  10^6 and comparing the remainder against the denominator implements that
  exactly, while `round(numerator / denominator, 6)` can inherit binary
  representation error before rounding.
- **JSON null for every zero denominator.** A zero denominator means the rate
  is undefined, not perfect and not zero; `recognized_accuracy` on an
  all-unknown dataset is therefore null, while `false_pass_rate_on_violation`
  stays 0.0 when there are real non-passes but no false passes.
- **Counts as a fixed A–F object, rates as a fixed object.** Six integer cells
  are always emitted including zeros; consumers never have to infer a missing
  cell from a rate.
- **Deterministic bytes with a literal trailing LF.** `json.dumps(...,
  sort_keys=True, ensure_ascii=False, indent=2)` plus `"\n"`, encoded UTF-8 and
  written with `Path.write_bytes`, removes platform newline translation and
  makes the report a stable acceptance oracle.
- **13-case fixture despite the work-order parenthetical "12".** The six
  required counts (`4,1,2,2,3,1`) sum to 13 and the three required literal
  rates are exactly 2/6, 3/13 and 7/10, so the dataset must have N = 13; the
  recorded discrepancy is an arithmetic slip in the work order, handled by the
  authoritative counts and rates rather than by inventing a different metric.
- **No CI wiring.** The issue asks for an offline harness; a gate would turn a
  small labelled fixture into a merge blocker without a real reference dataset.
  Integrating it is out of scope until #584's dataset decision lands.
- **No test edit in this worker scope.** A separate test worker owns `tests/**`;
  this plan records the test design and the oracles it must pin.

## Affected contours

- Repository: `scripts/worker/accuracy_harness.py` (new),
  `scripts/worker/accuracy_pairs_synthetic_v1.json` (new), and the SDD trio
  under `specs/695-offline-accuracy-harness/` (new).
- VPS: NONE — no API, frontend, edge, deploy script or release manifest change.
- Ubuntu worker/relay: NONE — no `worker/**` or `deploy/worker/**` change; the
  harness is a developer tool under `scripts/worker/`, which the change-control
  policy classifies as `Production impact: NONE`.
- Windows worker/AI: NONE.
- Public interfaces: NONE — no API, worker, frontend or schema endpoint.
- CI interfaces: NONE — no workflow, no gate, no artifact upload; the harness
  is run on demand.
- Tests: NONE in this scope — `tests/**` belongs to the separate test worker.
- Explicitly unchanged: all production source, all deploy and workflow files,
  all lockfiles, `scripts/quality/**`, `scripts/ci/**` and every existing test.

## Validation

- Determinism oracle: run the committed fixture from the repository root and a
  reversed copy from `/tmp/opencode/695-check`, then compare bytes. Observed
  `cmp` exit 0 and identical SHA256
  `aab9a2e69299ed38382ca031e75a33b0844de91019188934553b20c4f2a15ffd`.
- Metric oracle: the committed fixture produces counts A=4 B=1 C=2 D=2 E=3 F=1
  and rates `false_pass_rate_on_violation` 0.333333,
  `unknown_fraction` 0.230769, `recognized_accuracy` 0.7.
- Negative-input oracle: unknown truth, empty array, duplicate ID, extra field,
  missing field, non-string value and blank ID each exit 2 before the output is
  opened; a pre-existing report stays byte-identical.
- Abstention oracle: a three-case all-unknown input is accepted with
  `recognized_accuracy` null and `unknown_fraction` 1.0.
- Static gates: `python3 -m py_compile scripts/worker/accuracy_harness.py`,
  `ruff check --config scripts/quality/ruff.toml
  scripts/worker/accuracy_harness.py`, and `python3 scripts/ci/validate_sdd.py`.
- Test ownership: the test worker's `tests/**` cases must pin the same oracles
  (deterministic bytes across cwd/order, formula literals from the fixture,
  invalid-input report preservation, all-unknown null, and the absence of
  environment state in the report). This worker only records the design.

## Runtime feedback

- This is an offline developer tool: no runtime contour changes, no deploy
  lane, no acceptance probe beyond running the CLI on the fixed fixture.
- Not a CI gate and not #584 unblock: the fixture is synthetic and proves the
  harness contract, not detector quality. #584 remains DEFERRED pending the
  owner's real labeled dataset.
- Work-order arithmetic: the required counts and rates are consistent only at
  13 cases, so the "12 cases total" parenthetical is recorded as a slip; the
  fixture follows the counts and rates.
- The test worker's tests are the durable behavioural pin; the observed CLI
  runs above are this worker's pre-test evidence, not a substitute for them.

## Risk profile

- Risk profile: NOT REQUIRED
- Justification: the change adds an offline, stdlib-only developer tool and a
  synthetic JSON fixture under `scripts/worker/**`; it touches no production
  runtime, deploy path, workflow, schema, secret or migration, and the
  change-control policy classifies every changed path as
  `Production impact: NONE`. No security, schema, destructive or MIXED trigger
  applies.

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: the test worker's harness case runs the committed fixture from two working directories with one reversed copy and asserts byte-identical report bytes plus the stable dataset fingerprint; this worker observed `cmp` exit 0 and SHA256 `aab9a2e69299ed38382ca031e75a33b0844de91019188934553b20c4f2a15ffd` for both runs
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: spec.md's closed metric contract is the written oracle, and the test worker asserts the fixture rates against its formulas: D/(D+E+F) = 2/6 = 0.333333, (C+F)/N = 3/13 = 0.230769, (A+E)/(A+B+D+E) = 7/10 = 0.7
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: the test worker asserts `scripts/worker/accuracy_pairs_synthetic_v1.json` parses as a 13-record array with exactly the three fields per record and frozen counts A=4 B=1 C=2 D=2 E=3 F=1; this worker observed those counts from the committed fixture
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: the test worker asserts nonzero exit and an untouched previous report for unknown truth, unknown outcome, empty array, duplicate ID, missing field, extra field, non-string value and blank ID; this worker observed exit 2 with a preserved report for the same cases
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P1 | Evidence: the test worker asserts a nonempty all-unknown input is accepted with `recognized_accuracy` null and `unknown_fraction` 1.0, and that unknown outcomes land only in C and F; this worker observed the same all-unknown report

## Correct-course check

- Trigger: NONE
- Issue impact: none — the scope matches issue #695: an offline accuracy harness, formulas in the written spec, and a committed labelled mini-dataset or reproduction procedure.
- Specification impact: none — the closed metric contract is recorded verbatim from the admitted work order; the only correction is the internal arithmetic of the fixture size (counts and literal rates require 13 cases, not the work order's "12"), recorded in Product outcome and Runtime feedback.
- Plan impact: none — the implementation follows the admitted CLI, input, report and determinism contract; no runtime or CI integration was added.
- Tasks impact: none — implementation, fixture and SDD are delivered; PR, CI, merge and any test-worker work remain with the orchestrator and the test worker as recorded in tasks.md.
- Authorization impact: NONE — bounded worker work order from the delivery orchestrator on branch `agent/wave4-695-accuracy-harness`; the orchestrator owns the Git lifecycle, PR admission and CI evidence.
- Follow-up: none in this change; wiring the harness to a real dataset is part of the separately deferred #584 calibration and is explicitly out of scope here.
