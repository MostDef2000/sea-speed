# Tasks: #695 — Offline accuracy harness

- Spec: specs/695-offline-accuracy-harness/spec.md
- Plan: specs/695-offline-accuracy-harness/plan.md
- Issue: #695

## Delivery tasks

- [x] Closed metric contract recorded in `specs/695-offline-accuracy-harness/spec.md`: six confusion cells, N=A+B+C+D+E+F, the exact three formulas with explicit denominators, all six integer counts including zeros, zero denominator -> JSON null, empty input rejected as "no cases", nonempty all-unknown input valid
- [x] New stdlib-only CLI `scripts/worker/accuracy_harness.py` with the required invocation `python3 scripts/worker/accuracy_harness.py --pairs INPUT --output REPORT`; imports limited to argparse, hashlib, json, sys and pathlib; no network, git, clock, hostname, cwd or environment read
- [x] Input validation before the output is opened: exact key set `id`/`truth`/`outcome`, all strings, unique nonblank IDs, truth in {pass, non_pass}, outcome in {pass, non_pass, unknown}, duplicate JSON keys rejected, missing and extra fields rejected
- [x] Deterministic report: contract id `sea_speed_accuracy_report_v1`, six cell counts, three rates, `dataset_sha256` over canonical compact JSON of validated rows sorted by id, sorted object keys, UTF-8, one literal trailing LF, written as bytes
- [x] Exact rational rounding: rates are the exact fraction scaled by 10^6 with nearest-ties-to-even integer rounding; zero denominators become JSON null instead of 0, NaN or a perfect score
- [x] Committed synthetic fixture `scripts/worker/accuracy_pairs_synthetic_v1.json`: 13 media-free hand-authored records with opaque `synthetic` IDs and frozen decisions A=4 B=1 C=2 D=2 E=3 F=1, yielding the literal rates 0.333333, 0.230769 and 0.7
- [x] Determinism proof: the fixture scored from the repository root and a reversed row copy scored from `/tmp/opencode/695-check` produced byte-identical reports (`cmp` exit 0) with SHA256 `aab9a2e69299ed38382ca031e75a33b0844de91019188934553b20c4f2a15ffd` for both files
- [x] Negative-input proof: unknown truth, unknown outcome, empty array, duplicate ID, missing field, extra field, non-string value, blank ID and duplicate JSON key each exit nonzero before the output path is touched; a pre-existing valid report keeps its exact bytes
- [x] Abstention proof: a three-case all-unknown input exits 0 with counts C=1 F=2, `recognized_accuracy` null and `unknown_fraction` 1.0
- [x] Static gates on the branch: `python3 -m py_compile scripts/worker/accuracy_harness.py` passes, `ruff check --config scripts/quality/ruff.toml scripts/worker/accuracy_harness.py` passes, and `python3 scripts/ci/validate_sdd.py` passes
- [x] Scope proof: the final delivered scope is six files — `scripts/worker/accuracy_harness.py`, `scripts/worker/accuracy_pairs_synthetic_v1.json`, `specs/695-offline-accuracy-harness/spec.md`, `specs/695-offline-accuracy-harness/plan.md`, `specs/695-offline-accuracy-harness/tasks.md`, and the test-worker-owned `tests/test_accuracy_harness.py` — and `git status --short` shows those new paths with no modified tracked file
- [x] SDD trio written for this feature and the work-order arithmetic reconciled in writing: A,B,C = 4,1,2 plus D,E,F = 2,3,1 is 13 cases, and the three literal rates are 2/6, 3/13 and 7/10, so the fixture is 13 cases and the "12 cases total" parenthetical is recorded as an arithmetic slip
- [x] `tests/test_accuracy_harness.py` is the landed test-worker file and carries the reproducing RED cases for the F1/F2 peer findings; it is not edited or weakened by this worker, whose only fixes in this pass are `scripts/worker/accuracy_harness.py` and this tasks.md wording
- [ ] PR Change Contract declares `Production impact: NONE`, `VPS deployment: NOT REQUIRED`, `Ubuntu worker/relay update: NOT REQUIRED`, `Production safety envelope: NOT REQUIRED`, `VPS execution capability: NOT APPLICABLE`, `Ubuntu worker execution capability: NOT APPLICABLE`, `Operator actions expected: 0`, plus `Risk profile: NOT REQUIRED` and `Specification: specs/695-offline-accuracy-harness/spec.md`
- [ ] Exact-head CI on the PR is green, including the test worker's harness cases, the SDD validator for this trio, the contracts, quality and repo validators, and ruff
- [ ] Exact-green-head merge of the PR to main, with no deploy lane and no runtime acceptance for this offline tool

## Completion gate

- The changed-file scope is exactly `scripts/worker/accuracy_harness.py`,
  `scripts/worker/accuracy_pairs_synthetic_v1.json`,
  `specs/695-offline-accuracy-harness/spec.md`,
  `specs/695-offline-accuracy-harness/plan.md` and
  `specs/695-offline-accuracy-harness/tasks.md`; no test, production, deploy,
  workflow, lockfile, `scripts/quality/**` or `scripts/ci/**` file changes.
- The harness is stdlib-only and offline; it never queries git, the network,
  the clock, the hostname, the cwd or the output path when building the report.
- Invalid input is rejected entirely before the output is opened; a previous
  valid report is preserved, and an empty array is rejected as "no cases".
- The committed synthetic fixture yields the frozen counts and the literal
  rates recorded in the spec, and the report is byte-identical across cwd and
  row order.
- The test worker owns `tests/**`; this delivery records the test design and
  the pre-test CLI evidence, and no test file is modified here.
- This feature is not wired into CI, does not change any runtime contour, and
  does not unblock #584; #584 remains DEFERRED pending the owner's real labeled
  dataset.

## Requirements traceability

- AC-001 | Task: reproducible on a fixed commit — deterministic report bytes across cwd and input order with no environment-derived state | Evidence: spec.md Report contract and NFR-001; observed `cmp` exit 0 and identical SHA256 `aab9a2e69299ed38382ca031e75a33b0844de91019188934553b20c4f2a15ffd` for the repository-root run and the reversed-copy run from /tmp/opencode/695-check; this worker's pre-test oracle is the CLI itself, the test worker pins it in tests/** | Coverage: COVERED
- AC-002 | Task: the closed metric formulas are written in the spec with the confusion table, explicit denominators and the zero-denominator null rule | Evidence: spec.md sections Closed metric contract and Report contract record the verbatim contract; plan.md Test design TEST-002 traces the formulas to the fixture rates; the written spec is the oracle the test worker asserts against | Coverage: COVERED
- AC-003 | Task: the labelled synthetic mini-dataset is committed with frozen decisions and the reproduction procedure is the documented CLI invocation | Evidence: scripts/worker/accuracy_pairs_synthetic_v1.json has 13 records and yields A=4 B=1 C=2 D=2 E=3 F=1 with rates 0.333333, 0.230769 and 0.7; the invocation and determinism proof are recorded in plan.md Validation and in this file's delivery tasks | Coverage: COVERED
- AC-004 | Task: invalid or empty input exits nonzero before the output is opened and leaves a previous valid report untouched, while a nonempty all-unknown input is valid | Evidence: observed exit 2 with preserved report bytes for unknown truth, unknown outcome, empty array, duplicate ID, missing field, extra field, non-string value, blank ID and duplicate JSON key; the all-unknown run exited 0 with nullable rates; plan.md Test design TEST-004 pins it for the test worker | Coverage: COVERED
- AC-005 | Task: abstention is separated from error by counting unknown outcomes in C and F only, excluding them from recognized_accuracy, including them in unknown_fraction and keeping F in the false-pass denominator | Evidence: spec.md Closed metric contract formulas and the Gherkin abstention scenario; observed all-unknown report with C=1 F=2, `recognized_accuracy` null and `unknown_fraction` 1.0; plan.md Test design TEST-005 pins it for the test worker | Coverage: COVERED

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
