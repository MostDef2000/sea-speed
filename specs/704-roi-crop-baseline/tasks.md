# Tasks: #704 — ROI-crop inference baseline (offline measurement)

- Spec: `specs/704-roi-crop-baseline/spec.md`
- Plan: `specs/704-roi-crop-baseline/plan.md`
- Issue: #704

## Delivery tasks

- [x] Frozen workload and adoption thresholds recorded in `specs/704-roi-crop-baseline/spec.md` **before** the evidence run: frame size, six scenario polygons, 32 frames per scenario per arm, model/input identities, mask non-execution, CPU/latency endpoints and the refusal rule
- [x] New stdlib-only on-demand CLI `scripts/worker/roi_crop_baseline.py`; no third-party import, no target URL, no camera/relay/service access
- [x] Baseline arm keeps the full-frame masked inference input shape; candidate arm resolves the clipped polygon bounds and copies the masked frame crop
- [x] Exact reverse shift: accepted and diagnostic `bbox_xyxy` records are shifted into crop coordinates and back with integer arithmetic; geometry verified for both sets
- [x] Geometry coverage: nonzero offset, nonrectangular mask, edge clipping, no ROI, zero-area degenerate bounds and outside-frame empty bounds, each with an explicit fallback reason
- [x] Per-frame evidence: processed frames, per-scenario sample counts, parent CPU from `time.process_time`, model-free median/p95 latency, runtime/model/input identities
- [x] Honest UNMEASURED cells: mask pixel cost, child CPU, inference CPU, inference latency, quality and workload identity each carry an explicit reason; no number is fabricated
- [x] Machine-readable JSON report with `binding`, `frozen`, `runtime`, `model`, `input`, `quality`, `scenarios`, `geometry`, `arms`, `comparison`, `decision` and `unmeasured`; decision is `NO ADOPTION / insufficient evidence`
- [x] Adoption thresholds declared in `ADOPTION_THRESHOLDS` at module top before measurement and echoed into the report
- [x] Static gates: `python3 -m py_compile` and `ruff check --config scripts/quality/ruff.toml` pass for the new script
- [x] SDD trio written: spec.md (frozen workload/thresholds, metrics, Gherkin, honest limits, NFRs), plan.md (architecture, decisions, validation, risk/test design, correct-course check, transaction audit), tasks.md (this file)
- [ ] PR Change Contract declares the exact diff, `Production impact: NONE`, no runtime contour, `Risk profile: REQUIRED` and `Specification: specs/704-roi-crop-baseline/spec.md`
- [ ] Exact-head CI green, including the SDD validator, repo/contracts/quality validators and ruff
- [ ] Exact-green-head merge to main; no deploy lane and no runtime acceptance for this offline harness

## Completion gate

- The delivered-file scope is exactly
  `scripts/worker/roi_crop_baseline.py`,
  `specs/704-roi-crop-baseline/spec.md`,
  `specs/704-roi-crop-baseline/plan.md` and
  `specs/704-roi-crop-baseline/tasks.md`; no production worker, env example,
  API, deploy, workflow, lockfile, `scripts/quality/**` or `scripts/ci/**`
  change and no test is modified.
- The harness is stdlib-only and offline: no socket, no camera/relay/service,
  no private media, no secret and no new dependency.
- Both arms use the same frozen frames, polygons and settings; the candidate
  reverse-shifts accepted and diagnostic boxes exactly.
- Thresholds were frozen in spec.md before the evidence run; the evidence below
  transcribes one real run and moves no threshold.
- Inference CPU, inference latency, mask cost, quality and workload identity are
  UNMEASURED with reasons; the decision refuses adoption.
- Raw run output is not in git; it lives under `/tmp/opencode/704-roi-crop/`.
- The test worker owns `tests/**`; this delivery records the test design
  (plan.md) and the observed runtime evidence only.

## Evidence — offline run (issue #704)

**Environment:** base `36f28bec2c434dd60e682c5741159ae6c13b7df4`, branch
`agent/wave9-704-roi-crop-baseline`, Linux x86_64, 22 logical CPUs, Intel Xeon,
Python 3.14.4. `numpy` present; OpenCV absent; no `models/` weights; no labeled
replay or external fixture. cgroup CPU quota `unknown`.

**Command**

```text
python3 scripts/worker/roi_crop_baseline.py \
  --tested-sha 36f28bec2c434dd60e682c5741159ae6c13b7df4 \
  --output /tmp/opencode/704-roi-crop/report.json
```

**Observed harness output**

```text
report: /tmp/opencode/704-roi-crop/report.json
binding: BOUND tested_sha=36f28bec2c434dd60e682c5741159ae6c13b7df4
geometry_roundtrip_exact: True
decision: NO ADOPTION / insufficient evidence
  - inference was not executed: no model runtime or weights in the harness
  - baseline inference CPU is UNMEASURED
  - baseline inference latency is UNMEASURED
  - baseline end-to-end latency is UNMEASURED
  - candidate inference CPU is UNMEASURED
  - candidate inference latency is UNMEASURED
  - candidate end-to-end latency is UNMEASURED
  - quality is UNMEASURED: no labeled replay or fixtures
  - workload identity is UNMEASURED: synthetic frames only
  - candidate inference CPU ratio is UNMEASURED
```

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
| `runtime.opencv_available` | `false` |
| `model.inference_executed` | `false` |
| `duration_seconds` | `0.057` (host-specific) |

**Model-free numbers (not inference measurements):** the candidate preprocessing
loop is slower than the baseline full-frame hand-off; the report records the
ratio as `preprocess_only_parent_cpu_ratio: 438.371585` (one host-specific
observed run) and explicitly notes
that a preprocessing ratio cannot justify adoption. Per-scenario crop geometry
was exact: `nonzero_offset` offset `(320, 180)`, `nonrectangular` offset
`(200, 120)`, `edge_clipped` offset `(0, 100)` with `clipped=true`, `no_roi`,
`degenerate_bounds` and `outside_frame` falling back to full frame with their
recorded reasons.

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

**Test-worker evidence:** PENDING — a separate test worker owns `tests/**`; no
test is written, modified or reported by this delivery. The oracles it should
pin are in `plan.md` § Test design.

**Adoption:** refused. `NO ADOPTION / insufficient evidence` because inference
CPU, inference latency, quality and workload identity are UNMEASURED. No
production worker, env flag, API, deploy file or workflow changes in this PR.

## Requirements traceability

- AC-001 | Task: paired arms on frozen frames/polygons/settings; baseline keeps the full-frame inference input; candidate crops to clipped polygon bounds and shifts accepted plus diagnostic boxes back exactly | Evidence: `resolve_crop`, `shift_records`, `verify_scenario`; the run reports `geometry.all_roundtrip_exact: true` | Coverage: COVERED
- AC-002 | Task: geometry coverage for nonzero offsets, nonrectangular masks, edge clipping, no ROI and empty/degenerate bounds, with exact reverse shifts for both box sets | Evidence: six frozen scenarios; observed `crop_used: 3`, `identity_fallback: 3`, `edge_clipped: 2`, every scenario `accepted_roundtrip_exact` and `diagnostic_roundtrip_exact` true | Coverage: COVERED
- AC-003 | Task: record per-frame parent CPU, child/inference CPU status, model-free median/p95, sample counts and runtime/model/input identities; mark inference CPU and quality UNMEASURED with reasons | Evidence: arm rows report 192 processed frames and 32 samples per scenario; child/inference CPU, inference latency and quality are `UNMEASURED` with notes; runtime and model identities recorded | Coverage: COVERED
- AC-004 | Task: machine-readable JSON with a decision that refuses adoption on missing quality/timing/workload evidence; thresholds declared before measurement | Evidence: `ADOPTION_THRESHOLDS` echoed under `frozen`; `decision.value` is `NO ADOPTION / insufficient evidence`, `decision.adoption` is false, `unmeasured` lists 10 reasoned cells | Coverage: COVERED
- AC-005 | Task: stdlib-only, offline, no new dependency, no private media, no secret, no production file/env/API/workflow change | Evidence: stdlib imports only; no socket or target option; the run reads synthetic buffers and writes one local report; `git status --short` shows only the four allowed paths | Coverage: COVERED
- AC-006 | Task: static quality — py_compile, ruff, validate_sdd.py and scope-limited git status | Evidence: observed `py_compile` success, ruff `All checks passed!`, `Sea Speed SDD validation passed`, and `git status --short` / `git diff --stat` showing exactly the four allowed new paths | Coverage: COVERED

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
