# Spec: #695 — Offline accuracy harness for predeclared pass/non-pass cases

- Issue: #695
- Specification: specs/695-offline-accuracy-harness/spec.md
- Authorization: wave-4 admission (issue #695), branch
  `agent/wave4-695-accuracy-harness`, base `91570fb043894a39fe30a444b0de7d23bdd1d6ed`
  (current `main`).
- Related: #584 (reference-dataset calibration, DEFERRED by the owner on
  2026-11-13) and the abstention-aware metric note recorded for #584 in the
  delivery journal. This feature builds the offline scoring tool only.

## Product outcome

Issue #695 asks for an offline accuracy harness so detection outcomes can be
scored against a labeled dataset without guessing from aggregate logs. Today
there is no repeatable way to ask "of the actual violations, how many did the
detector let pass, and how often did it abstain instead of answering?" The
`scripts/worker/benchmark_detector_frequency.py` kit is an honest stub with an
empty result list and a zero commit field, so it cannot answer that question.

This feature adds one stdlib-only CLI that reads a hand-authored, labeled JSON
array of predeclared passage opportunities, computes a closed confusion-matrix
contract (including abstentions), and writes a deterministic JSON report. The
report separates `unknown` (abstention) from a wrong answer, so an abstention
is never silently scored as a false pass or a false rejection, and an empty
input is rejected instead of producing a vacuous perfect score. A 13-case
synthetic fixture with frozen decisions is committed as the reproducible
mini-dataset.

Explicit boundaries: this is **not a CI gate**, it does **not** change worker
detection, and it does **not** unblock #584. #584 remains deferred until the
owner supplies a real reference dataset and accepts a calibration decision; the
synthetic fixture here proves the harness behaviour only, not detector quality.

## Closed metric contract

One case = one predeclared passage opportunity for one target in one
observation window, weight 1. Truth ∈ {pass, non_pass}; detector outcome ∈
{pass, non_pass, unknown}. "Violation" means violation of the asserted pass
condition (truth non_pass), NOT speeding or legal compliance.

Confusion cells: A=(truth pass, outcome pass), B=(pass, non_pass), C=(pass,
unknown), D=(non_pass, pass), E=(non_pass, non_pass), F=(non_pass, unknown).
N=A+B+C+D+E+F.

- false_pass_rate_on_violation = D / (D+E+F)  [all actual non-passes in denominator, including F]
- unknown_fraction = (C+F) / N
- recognized_accuracy = (A+E) / (A+B+D+E)  [C and F excluded entirely]

Report all six integer counts including zeros. Zero denominator → JSON null
(never 0, NaN, or a perfect score). Empty input → reject as "no cases".
Nonempty all-unknown input → valid.

## Report contract

The report is one JSON object with contract id `sea_speed_accuracy_report_v1`,
the six integer cell counts `A`–`F`, the three rates above, and a dataset
fingerprint:

```json
{
  "contract": "sea_speed_accuracy_report_v1",
  "counts": {"A": 4, "B": 1, "C": 2, "D": 2, "E": 3, "F": 1},
  "dataset_sha256": "<64 lowercase hex>",
  "rates": {
    "false_pass_rate_on_violation": 0.333333,
    "recognized_accuracy": 0.7,
    "unknown_fraction": 0.230769
  }
}
```

- `dataset_sha256` is SHA256 over the UTF-8 bytes of canonical JSON of the
  validated rows sorted by `id`: `json.dumps(rows_sorted_by_id,
  ensure_ascii=False, sort_keys=True, separators=(",", ":"))`. It does not
  hash the filename, the file bytes or the input iteration order.
- Rates are exact fractions rounded to 6 decimal places, nearest with ties to
  even, and serialized as JSON numbers (the shortest round-tripping form, so
  an exact 0.7 is written `0.7`, not `0.700000`).
- Serialization: object keys sorted, UTF-8, deterministic indentation, one
  literal trailing LF, written as bytes so no platform newline translation
  applies.
- The report contains no timestamp, hostname, cwd, output path, input
  iteration order or git state.

## Input contract

The `--pairs` file is a UTF-8 JSON array. Each record must be a JSON object
with EXACTLY the three string fields `id`, `truth` and `outcome`. IDs must be
unique and nonblank. `truth` must be exactly `pass` or `non_pass`; `outcome`
must be exactly `pass`, `non_pass` or `unknown`. The whole input is validated
before the output file is opened: malformed records, duplicate JSON keys,
duplicate IDs, missing or extra fields, non-string values and unknown enum
values are rejected with a nonzero exit, and a previous valid report at the
output path is left untouched. An empty array is rejected as "no cases". A
valid input with poor accuracy still exits 0.

## User scenarios

- SC-1: an engineer runs the harness twice on the committed fixture from two
  different working directories, once with the fixture rows and once with the
  rows reversed; both runs produce byte-identical reports with the same
  dataset fingerprint and the same counts.
- SC-2: an engineer scores a dataset where every case abstains; the report is
  valid, `recognized_accuracy` is JSON null (zero denominator), and
  `unknown_fraction` is 1.0 — abstention is visible, not converted into an
  error or a perfect score.
- SC-3: an engineer mistypes `truth` as `PASS`; the harness exits nonzero with
  a clear message and an existing valid report at the same output path keeps
  its exact bytes.
- SC-4: an engineer inspects the fixture report: the six counts match the
  frozen labels and the three rates are the literal values 0.333333, 0.230769
  and 0.7.

## Requirements

- R-1: `scripts/worker/accuracy_harness.py` is stdlib-only, performs no
  network access, no git query, and imports no third-party package.
- R-2: the CLI is exactly `python3 scripts/worker/accuracy_harness.py --pairs
  INPUT --output REPORT`; both options are required.
- R-3: the whole pairs input is validated against the input contract before
  the output path is touched; invalid input exits nonzero and leaves any
  previous report byte-identical.
- R-4: the report uses the constant contract id `sea_speed_accuracy_report_v1`,
  all six integer counts including zeros, and the three closed-form rates.
- R-5: zero denominators produce JSON null; empty input is rejected as "no
  cases"; a nonempty all-unknown input is valid.
- R-6: rates are exact fractions rounded to 6 decimals with nearest-ties-to-even,
  independent of floating-point drift.
- R-7: `dataset_sha256` is the SHA256 of canonical JSON of the validated rows
  sorted by `id`, with no filename, cwd, clock, hostname or iteration-order
  input.
- R-8: report bytes are deterministic: sorted object keys, UTF-8, one trailing
  LF, written as bytes.
- R-9: `scripts/worker/accuracy_pairs_synthetic_v1.json` is a committed,
  hand-authored, media-free synthetic fixture whose IDs and file name say
  "synthetic" and whose frozen decisions yield A,B,C = 4,1,2 and D,E,F =
  2,3,1.
- R-10: SDD records the closed metric contract, the Gherkin acceptance
  examples, the NFR assessment and the traceability of the three issue
  acceptance criteria.
- R-11: no production source, worker runtime, deploy path, workflow or test
  file changes in this scope.

## Acceptance examples (Gherkin)

```gherkin
Feature: Offline accuracy harness

  Rule: The report is deterministic for a fixed commit and input
    Scenario: Two runs from different cwd with reversed input order
      Given the committed synthetic fixture and a reversed copy of its rows
      When the harness runs once from the repository root and once from a temporary directory
      Then both reports are byte-identical
      And the dataset fingerprint and all six counts are identical

  Rule: Abstention is separated from error
    Scenario: Every case abstains
      Given a nonempty input whose every outcome is "unknown"
      When the harness scores it
      Then the report is valid with unknown_fraction 1.0
      And recognized_accuracy is JSON null because its denominator is zero
      And abstentions are counted in C and F, never in B, D or E

  Rule: Invalid input never destroys a previous report
    Scenario: Unknown truth enum
      Given a previous valid report at the output path
      When the harness reads a case with truth "PASS"
      Then it exits nonzero with an input error
      And the previous report keeps its exact bytes

  Rule: Empty input is not a perfect score
    Scenario: Empty pairs array
      Given an empty JSON array
      When the harness runs
      Then it rejects the input as "no cases"
      And no report is written

  Rule: The frozen synthetic fixture reproduces the written formulas
    Scenario: Score the committed fixture
      Given scripts/worker/accuracy_pairs_synthetic_v1.json
      When the harness writes a report
      Then counts are A=4 B=1 C=2 D=2 E=3 F=1
      And false_pass_rate_on_violation is 0.333333
      And unknown_fraction is 0.230769
      And recognized_accuracy is 0.7
```

## Acceptance criteria

- AC-001: reproducible on a fixed commit — the committed fixture scored by the
  committed script yields byte-identical report bytes from a different cwd and
  with reversed row order, the fingerprint is stable, and the report carries
  no environment-derived state.
- AC-002: formulas written in the spec — the closed metric contract above
  records the six cells, exact formulas, the explicit denominators and the
  zero-denominator null rule.
- AC-003: labeled mini-dataset committed — the synthetic fixture is committed
  with frozen decisions and yields A,B,C = 4,1,2, D,E,F = 2,3,1 and the
  literal rates 0.333333, 0.230769 and 0.7.
- AC-004: input contract enforced atomically — invalid or empty input exits
  nonzero before the output is opened and leaves a previous valid report
  untouched; a nonempty all-unknown input is valid.
- AC-005: abstention separated from error — `unknown` outcomes are counted in
  C and F, excluded from `recognized_accuracy`, included in
  `unknown_fraction`, and F stays in the false-pass denominator.

## NFR assessment

- NFR-001 | Area: Determinism | Target: the same validated rows produce byte-identical report bytes regardless of cwd or input row order, with no timestamp, hostname, cwd, output path or git state in the report | Validation: run the CLI from the repository root on the fixture and from `/tmp/opencode/695-check` on a reversed copy, then compare bytes and SHA256 | Evidence: both runs produced the identical file hash `aab9a2e69299ed38382ca031e75a33b0844de91019188934553b20c4f2a15ffd` and `cmp` exited 0 | Status: PASS
- NFR-002 | Area: Correctness | Target: the six counts and three rates follow the closed formulas exactly, with 6-decimal nearest-ties-to-even rounding and JSON null on a zero denominator | Validation: score the committed fixture and inspect the report; a direct unit probe covers 1/3, 3/13, 7/10, half-even ties and 0/0 | Evidence: report shows A=4 B=1 C=2 D=2 E=3 F=1 and rates 0.333333, 0.230769, 0.7; probe returned `rounded_rate(0,0) is None` and tie cases rounded to even | Status: PASS
- NFR-003 | Area: Reliability | Target: invalid input is rejected before the output is opened, so a previous valid report survives every rejection path | Validation: attempt unknown truth, empty array, duplicate ID, extra field, missing field, non-string value and blank ID against an output that already holds a valid report | Evidence: every case exited 2 and reported the specific defect; the pre-existing report bytes were unchanged after the invalid attempt and no output file was created for the other cases | Status: PASS
- NFR-004 | Area: Security / Offline boundary | Target: the harness is stdlib-only, performs no network or git access, and does not read secrets or environment state | Validation: source inspection of imports and a ruff pass; no socket, requests, subprocess, git, datetime, socket or os.environ usage exists in the script | Evidence: imports are argparse, hashlib, json, sys and pathlib only; `ruff check --config scripts/quality/ruff.toml` passed | Status: PASS
- NFR-005 | Area: Operability | Target: the new tool lands without touching runtime contours or CI and passes the repository's static gates | Validation: `python3 -m py_compile`, ruff, `python3 scripts/ci/validate_sdd.py` and `git status --short` on the branch | Evidence: py_compile and ruff pass; the SDD validator passes; only the six allowed new files are present | Status: PASS

## Runtime feedback

- Offline tool by design: no worker, API, frontend, deploy, workflow or CI file
  changes. There is no runtime probe for this feature, and the harness is not
  wired into any merge or deploy gate.
- Not #584 unblock: the synthetic fixture proves harness behaviour, not
  detector accuracy. #584 stays DEFERRED until the owner provides a real
  labeled reference dataset and accepts the calibration decision.
- Work-order arithmetic note: the allocation A,B,C = 4,1,2 and D,E,F = 2,3,1
  sums to 13 cases, while the work order parenthetical said 12. The six counts
  and the three literal rates (2/6 = 0.333333, 3/13 = 0.230769, 7/10 = 0.7)
  are mutually consistent only at N = 13, so the fixture has 13 cases and the
  "12" phrase is recorded here as an arithmetic slip, not silently changed
  elsewhere.
- Observation: `python3 scripts/worker/accuracy_harness.py --pairs
  scripts/worker/accuracy_pairs_synthetic_v1.json --output ...` exits 0 and
  writes the frozen report; reversing the rows and changing the cwd leaves the
  bytes identical.
