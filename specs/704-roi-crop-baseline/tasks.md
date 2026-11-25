# Tasks: #704 — ROI-crop inference baseline (offline measurement)

- Spec: `specs/704-roi-crop-baseline/spec.md`
- Plan: `specs/704-roi-crop-baseline/plan.md`
- Issue: #704

## Delivery tasks

- [x] Frozen workload and adoption thresholds recorded in `specs/704-roi-crop-baseline/spec.md` **before** the evidence run: frame size, six scenario polygons, 32 frames per scenario per arm, model/input identities, mask non-execution, CPU/latency endpoints and the refusal rule
- [x] New stdlib-only on-demand CLI `scripts/worker/roi_crop_baseline.py`; no third-party import, no target URL, no camera/relay/service access
- [x] Baseline arm keeps the full-frame inference input shape; candidate arm resolves the clipped polygon bounds and copies the crop region of an unmasked synthetic buffer; mask pixel cost stays `UNMEASURED`
- [x] Exact reverse shift: accepted and diagnostic `bbox_xyxy` records are shifted into crop coordinates and back with integer arithmetic; geometry verified for both sets
- [x] Geometry coverage: nonzero offset, nonrectangular mask, edge clipping, no ROI, zero-area degenerate bounds and outside-frame empty bounds, each with an explicit fallback reason
- [x] Per-frame evidence: processed frames, per-scenario sample counts, parent CPU from `time.process_time`, model-free median/p95 latency, runtime/model/input identities
- [x] Honest UNMEASURED cells: mask pixel cost, child CPU, inference CPU, inference latency, quality and workload identity each carry an explicit reason; no number is fabricated
- [x] Machine-readable JSON report with `binding`, `frozen`, `runtime`, `model`, `input`, `quality`, `scenarios`, `geometry`, `arms`, `comparison`, `decision` and `unmeasured`; decision is `NO ADOPTION / insufficient evidence`
- [x] Adoption thresholds declared in `ADOPTION_THRESHOLDS` at module top before measurement and echoed into the report
- [x] Declared thresholds enforced: `build_decision` refuses on any measured ratio above its frozen maximum and honors the quality-parity, inference/quality/workload-measured and tested-SHA requirement flags
- [x] Malformed boxes fail closed: a present `bbox_xyxy` that is not a 4-element list raises a clear `ValueError`; an absent key is still skipped
- [x] Non-default `--frames-per-scenario` flagged `frozen.investigation_only=true` with a changed note and an explicit refusal reason, so an override cannot look like frozen evidence
- [x] Static gates: `python3 -m py_compile` and `ruff check --config scripts/quality/ruff.toml` pass for the new script
- [x] SDD trio written: spec.md (frozen workload/thresholds, metrics, Gherkin, honest limits, NFRs), plan.md (architecture, decisions, validation, risk/test design, correct-course check, transaction audit), tasks.md (this file)
- [x] SDD refreshed to the actual admitted surface (harness, SDD trio, two test-worker files) and the observed focused/clean-tree/RED test evidence
- [ ] PR Change Contract declares the exact diff, `Production impact: NONE`, no runtime contour, `Risk profile: REQUIRED` and `Specification: specs/704-roi-crop-baseline/spec.md`
- [ ] Exact-head CI green, including the SDD validator, repo/contracts/quality validators and ruff
- [ ] Exact-green-head merge to main; no deploy lane and no runtime acceptance for this offline harness

## Completion gate

- The admitted #704 surface is exactly
  `scripts/worker/roi_crop_baseline.py`,
  `specs/704-roi-crop-baseline/spec.md`,
  `specs/704-roi-crop-baseline/plan.md`,
  `specs/704-roi-crop-baseline/tasks.md`,
  `tests/test_roi_crop_baseline.py` (new) and
  `tests/test_701_crossing_votes.py` (guard re-pin only); no production worker,
  env example, API, deploy, workflow, lockfile, `scripts/quality/**` or
  `scripts/ci/**` change. This code worker edits only the harness and SDD; the
  two test files are owned by the separate test worker.
- The harness is stdlib-only and offline: no socket, no camera/relay/service,
  no private media, no secret and no new dependency.
- Both arms use the same frozen frames, polygons and settings; the candidate
  reverse-shifts accepted and diagnostic boxes exactly.
- Thresholds were frozen in spec.md before the evidence run; the evidence below
  transcribes one real run and moves no threshold.
- Inference CPU, inference latency, mask cost, quality and workload identity are
  UNMEASURED with reasons; the decision refuses adoption.
- Raw run output is not in git; it lives under `/tmp/opencode/704-roi-crop/`.
- The test worker owns `tests/test_roi_crop_baseline.py` and the
  `tests/test_701_crossing_votes.py` re-pin; this delivery records the test
  design (plan.md) and the observed test/runtime evidence only.

## Evidence — offline run (issue #704)

**Environment:** base `36f28bec2c434dd60e682c5741159ae6c13b7df4`, tested HEAD
`96a7345b8222ec4717a0e43d7ab045191d36a422`, branch
`agent/wave9-704-roi-crop-baseline`, Linux x86_64, 22 logical CPUs, Intel Xeon,
Python 3.14.4. `numpy` present; OpenCV absent; no `models/` weights; no labeled
replay or external fixture. cgroup CPU quota `unknown`.

**Command**

```text
python3 scripts/worker/roi_crop_baseline.py \
  --tested-sha 96a7345b8222ec4717a0e43d7ab045191d36a422 \
  --output /tmp/opencode/704-roi-crop/report.json
```

**Observed harness output**

```text
report: /tmp/opencode/704-roi-crop/report.json
binding: BOUND tested_sha=96a7345b8222ec4717a0e43d7ab045191d36a422
geometry_roundtrip_exact: True
decision: NO ADOPTION / insufficient evidence
```

The refusal reasons cover the unexecuted inference, every `UNMEASURED` arm and
quality/workload cell, the missing inference CPU ratio, the quality-parity
requirement and a measured preprocess ratio above the frozen `1.0` maximum.

**Observed report fields**

| Field | Observed value |
|---|---|
| `contract` | `issue-704-roi-crop-baseline-v1` |
| `binding` | `BOUND` |
| `geometry.all_roundtrip_exact` | `true` |
| `geometry.scenarios_checked` | `6` |
| `geometry.crop_used` / `identity_fallback` / `edge_clipped` | `3` / `3` / `2` |
| `arms.baseline.processed_frames` | `192` (32 samples × 6 scenarios) |
| `arms.candidate.processed_frames` | `192` (32 samples × 6 scenarios) |
| `arms.*.child_cpu_seconds_per_frame` | `UNMEASURED` |
| `arms.*.inference_cpu_seconds_per_frame` | `UNMEASURED` |
| `arms.*.inference_latency_ms` | `UNMEASURED` |
| `arms.*.end_to_end_latency_ms` | `UNMEASURED` |
| `arms.*.quality` | `UNMEASURED` |
| `comparison.preprocess_only_threshold_met` | `false` |
| `comparison.inference_cpu_ratio` | `UNMEASURED` |
| `comparison.quality_parity` | `UNMEASURED` |
| `input.workload_identity` | `UNMEASURED` |
| `decision.value` | `NO ADOPTION / insufficient evidence` |
| `decision.adoption` | `false` |
| `unmeasured` cells | 10, each with an explicit reason |
| `frozen.frames_per_scenario_default` | `32` |
| `frozen.investigation_only` | `false` |
| `runtime.opencv_available` | `false` |
| `model.inference_executed` | `false` |
| `duration_seconds` | sub-second (host-specific) |

**Model-free numbers (not inference measurements):** the candidate preprocessing
loop is slower than the baseline full-frame hand-off, so
`preprocess_only_parent_cpu_ratio` exceeds the frozen `1.00` maximum and the
decision records a threshold-breach reason; the exact host-specific ratio stays
in the raw report. The report explicitly notes that a preprocessing ratio cannot
justify adoption. Per-scenario crop geometry was exact: `nonzero_offset` offset
`(320, 180)`, `nonrectangular` offset `(200, 120)`, `edge_clipped` offset
`(0, 100)` with `clipped=true`, `no_roi`, `degenerate_bounds` and
`outside_frame` falling back to full frame with their recorded reasons.

**Raw output:** `/tmp/opencode/704-roi-crop/report.json` (outside git).

**Static gates observed**

```text
$ python3 -m py_compile scripts/worker/roi_crop_baseline.py
PY_COMPILE_OK

$ python3 -m ruff check --config scripts/quality/ruff.toml scripts/worker/roi_crop_baseline.py
All checks passed!

$ python3 scripts/ci/validate_sdd.py
Sea Speed SDD validation passed
```

The SDD quality records (NFR, RISK, TEST, traceability, DoD and the eight-stage
transaction audit) were also exercised directly through `validate_sdd.py`'s
`validate_feature_quality` / `_validate_deployment_transaction_audit` helpers
and passed.

**Test evidence (the test worker owns both admitted test files):**

- Focused `tests/test_roi_crop_baseline.py`, reproduced in this session:
  `Ran 8 tests` with `44` subtests, `0` failures, `0` errors, `0` skipped. The
  run covers geometry round trips for all six scenarios, the refusal decision
  with ten reasoned UNMEASURED cells, threshold/flag behavior and the #704
  scope guard (including the `tests/test_701_crossing_votes.py` re-pin).
- Clean-tree full battery (test-worker clean-tree run): `1760 passed`,
  `2 skipped`, `1029` subtests, `0 failed`. This is the clean-tree count; a run
  with uncommitted code-worker edits makes other issues' working-tree scope
  guards fail closed by design, so it is not used as the battery evidence here.
- RED on the pre-change base: the same test file against a `36f28b` archive
  (`Ran 8 tests`) gives `7 failed / 1 passed` (2 failures + 5 errors) — the
  harness and its decision did not exist on base.

No test is written, modified or reported as authored by this code worker; the
oracles are in `plan.md` § Test design.

**Adoption:** refused. `NO ADOPTION / insufficient evidence` because inference
CPU, inference latency, quality and workload identity are UNMEASURED. No
production worker, env flag, API, deploy file or workflow changes in this PR.

## Requirements traceability

- AC-001 | Task: paired arms on frozen frames/polygons/settings; baseline keeps the full-frame inference input; candidate crops the synthetic buffer to clipped polygon bounds and shifts accepted plus diagnostic boxes back exactly; mask pixel cost UNMEASURED | Evidence: `resolve_crop`, `shift_records`, `verify_scenario`; the run reports `geometry.all_roundtrip_exact: true` | Coverage: COVERED
- AC-002 | Task: geometry coverage for nonzero offsets, nonrectangular masks, edge clipping, no ROI and empty/degenerate bounds, with exact reverse shifts for both box sets | Evidence: six frozen scenarios; observed `crop_used: 3`, `identity_fallback: 3`, `edge_clipped: 2`, every scenario `accepted_roundtrip_exact` and `diagnostic_roundtrip_exact` true | Coverage: COVERED
- AC-003 | Task: record per-frame parent CPU, child/inference CPU status, model-free median/p95, sample counts and runtime/model/input identities; mark inference CPU and quality UNMEASURED with reasons | Evidence: arm rows report 192 processed frames and 32 samples per scenario; child/inference CPU, inference latency and quality are `UNMEASURED` with notes; runtime and model identities recorded | Coverage: COVERED
- AC-004 | Task: machine-readable JSON with a decision that refuses adoption on missing quality/timing/workload evidence, an over-threshold measured ratio, a missing requirement flag or a non-frozen frame count; thresholds declared before measurement | Evidence: `ADOPTION_THRESHOLDS` echoed under `frozen`; `decision.value` is `NO ADOPTION / insufficient evidence`, `decision.adoption` is false, `unmeasured` lists 10 reasoned cells, and the run adds a preprocess-ratio breach reason | Coverage: COVERED
- AC-005 | Task: stdlib-only, offline, no new dependency, no private media, no secret, no production file/env/API/workflow change | Evidence: stdlib imports only; no socket or target option; the run reads synthetic buffers and writes one local report; the admitted #704 surface is the harness, SDD trio and two test-worker files | Coverage: COVERED
- AC-006 | Task: static quality — py_compile, ruff, validate_sdd.py and scope-limited git status | Evidence: observed `py_compile` success, ruff `All checks passed!`, `Sea Speed SDD validation passed`; focused tests 8 passed / 44 subtests; clean-tree 1760/2 skipped/1029 subtests/0 failed; RED on base 7 failed / 1 passed | Coverage: COVERED

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
