# Spec: #704 — ROI-crop inference baseline (offline measurement)

- Issue: #704
- Specification: `specs/704-roi-crop-baseline/spec.md`
- Authorization: wave-9 admission (issue #704), branch
  `agent/wave9-704-roi-crop-baseline`, base
  `36f28bec2c434dd60e682c5741159ae6c13b7df4`.
- Related: #703 (decoder CPU baseline) is the harness/SDD precedent and its
  recorded outcome was `NO ADOPTION` for lack of admissible evidence. This
  feature owns the offline ROI-crop harness and its SDD only. A separate test
  worker owns `tests/**`.

## Product outcome

The worker currently masks each frame to the road/water ROI at full frame size
and runs inference on that full masked frame (`worker/worker_roi.py:83-105`).
The open question is narrow and measurable: if inference instead consumed only
the **masked polygon bounding-box crop**, would worker CPU and latency fall
without losing detection quality, once every accepted and diagnostic box is
shifted back into full-frame coordinates?

This feature adds one on-demand, stdlib-only CLI,
`scripts/worker/roi_crop_baseline.py`, that compares two arms on the same frozen
synthetic frames, polygons and settings:

1. **Baseline** — the existing polygon-mask-at-full-frame shape: the inference
   input stays full frame.
2. **Candidate** — crop the masked frame to the clipped polygon bounds for
   inference, then shift **both** accepted and diagnostic boxes back into
   full-frame coordinates before any motion/ROI check.

The harness measures what it can honestly measure offline: crop bounds,
exact reverse coordinate shifts, crop-copy cost and model-free preprocessing
latency. The repository has no model weights, no labeled replay and no external
fixtures, and this sandbox has no OpenCV, so the production mask cost, inference
CPU, end-to-end inference latency and detection quality are recorded as
`UNMEASURED` with explicit reasons. The report therefore always refuses
adoption.

**Explicit boundary:** this spec does not authorize a production change. No
production worker file, env flag, API, event coordinate, deploy file or
workflow changes in this PR. Production adoption happens only after admissible
measurement — real frames, real weights, labeled replay, a measured CPU/latency
win and no quality loss — on a separately authorized change. Synthetic frames
prove geometry and preprocessing cost only; model-free timings are never
labeled inference measurements.

## Frozen workload (recorded before measurement)

The committed harness defaults reproduce these values. Overriding any of them
produces an investigation run, not frozen evidence.

| Knob | Frozen value |
|---|---|
| Tested source | full 40-hex `--tested-sha`; the report is UNBOUND without it |
| Runtime identity | recorded at run start: platform, Python, logical CPUs, CPU model, cgroup CPU quota |
| Frame | synthetic zero-filled `1920 × 1080 × 3` (`bytearray`, 6 220 800 bytes) |
| Scenario count | 6, declared as frozen input identities in `SCENARIOS` |
| Frames per scenario per arm | 32 (default; 192 processed frames per arm) |
| `nonzero_offset` polygon | `((320,180),(1280,240),(1200,860),(360,900))` |
| `nonrectangular` polygon | `((200,150),(900,120),(1500,480),(1100,950),(300,900))` |
| `edge_clipped` polygon | `((-120,140),(1000,100),(1900,980),(400,1120))` |
| `no_roi` polygon | `()` — fewer than three points |
| `degenerate_bounds` polygon | `((640,360),(640,360),(640,360))` — zero area |
| `outside_frame` polygon | `((2400,1400),(2600,1500),(2500,1700))` — empty clipped bounds |
| Production mask | `cv2.fillPoly` + `cv2.bitwise_and` (`worker/worker_roi.py:83-105`); **not executed** by a stdlib-only harness |
| Model identity | `models/yolo26x.pt`, inference image size 960 (`worker/analytics_profiles.py`); weights absent, inference **not executed** |
| Quality input | none — no labeled replay or external fixture exists in the repository |
| Preprocess CPU accounting | parent process `time.process_time()` delta ÷ processed frames |
| Child / inference CPU | **UNMEASURED** — no inference child is spawned |
| Latency endpoints | `time.perf_counter_ns` around one model-free preprocessing iteration; nearest-rank median/p95 |
| Concurrency | sequential; one arm at a time |

## Frozen adoption thresholds (recorded before measurement)

Every threshold is declared in `ADOPTION_THRESHOLDS` at the top of the script
before any measurement runs and is echoed into the report. A threshold is never
relaxed after seeing data.

| ID | Metric | Unit | Threshold |
|---|---|---|---|
| BIND | report bound to a full 40-hex `--tested-sha` | — | BOUND |
| SAMPLE | processed frames per arm | frames | ≥ 30 |
| PRE-CPU | candidate preprocess parent CPU ÷ baseline preprocess parent CPU | ratio | ≤ 1.00 |
| INF-CPU | candidate inference CPU ÷ baseline inference CPU | ratio | ≤ 0.80 (requires measured inference) |
| E2E-P95 | candidate end-to-end p95 ÷ baseline end-to-end p95 | ratio | ≤ 0.90 (requires measured end-to-end) |
| QUALITY | candidate detection quality parity with baseline | — | MEASURED and no loss |
| WORKLOAD | workload identity is the target camera workload | — | MEASURED |
| GEOMETRY | accepted and diagnostic boxes survive crop → reverse shift exactly | — | exact for every scenario |

`decision.adoption` is `true` only if every UNMEASURED cell is replaced by
admissible evidence *and* all thresholds pass. While inference CPU, quality or
workload identity is `UNMEASURED`, the decision is literally
`NO ADOPTION / insufficient evidence`.

## Metric definitions

- **Crop bounds**: min/max of the polygon clipped to `[0,width]×[0,height]`;
  `no_roi` (fewer than three points), zero-area polygons and polygons whose
  clipped bounds are empty fall back to the full-frame identity path instead of
  producing a zero-sized input.
- **Forward shift**: subtract `(x0, y0)` from each `bbox_xyxy` so boxes are in
  crop coordinates.
- **Reverse shift**: add `(x0, y0)` back. Integer arithmetic makes the
  round-trip exact; it is applied identically to accepted detections and
  diagnostic records because both carry `bbox_xyxy`.
- **Model-free preprocess CPU**: parent process CPU seconds per processed frame.
  It covers only polygon bounds and the candidate crop copy. It is **not**
  inference CPU and is never labelled as such.
- **Model-free preprocess latency**: per-iteration wall time, nearest-rank
  median and p95. It is **not** inference or end-to-end detection latency.
- **Inference CPU / latency / quality**: `UNMEASURED`; the harness executes no
  model and sees no labels. No number is invented.

## Honest limits

- A zero-filled synthetic frame proves coordinate geometry and crop-copy cost
  only. It says nothing about the target camera workload, detections, tracking,
  motion or ROI acceptance rates.
- OpenCV is unavailable to a stdlib-only harness, so the production mask's
  pixel cost is not measured. Both arms conceptually mask first; the mask cost
  is common and cancels only if it is actually measured, which it is not here.
- No weights exist in the workspace and the harness does not import a model
  runtime, so inference CPU and latency are unknown. The candidate's possible
  inference saving is the central unmeasured cell.
- No labeled replay or fixtures exist, so detection quality and recall cannot be
  compared. "Crop lost detections" is not claimed; it is unmeasured.
- A preprocessing ratio (candidate copy vs full-frame hand-off) is a real
  model-free number but cannot justify adoption.
- One run on one host is a bounded observation, not a capacity guarantee.

## User scenarios

```gherkin
Feature: Offline ROI-crop inference baseline

  Rule: Reverse shift is exact for accepted and diagnostic boxes
    Scenario Outline: Crop a nonrectangular ROI with a nonzero offset
      Given the frozen frame and polygon "<scenario>"
      When the candidate crops to the clipped polygon bounds
      And every accepted and diagnostic box is shifted into crop coordinates
      And both box sets are shifted back by the crop offset
      Then every box equals its original full-frame value exactly
      And the geometry report marks the round trip exact

      Examples:
        | scenario       |
        | nonzero_offset |
        | nonrectangular |
        | edge_clipped   |

    Scenario: Edge clipping keeps the visible polygon inside the crop
      Given a polygon that extends past the frame edge
      When the crop bounds are clipped to the frame
      Then the crop reports clipped=true
      And every box still round-trips exactly

  Rule: Missing ROI and degenerate bounds use the identity path
    Scenario: No ROI is configured
      Given fewer than three polygon points
      When the candidate resolves its crop
      Then the input stays full frame
      And the offset is (0, 0)
      And boxes are unchanged by the reverse shift

    Scenario Outline: Empty or degenerate bounds fall back safely
      Given the polygon "<scenario>"
      When the candidate resolves its crop
      Then the crop is full-frame rather than zero-sized
      And the reason is recorded
      And the round trip stays exact

      Examples:
        | scenario          |
        | degenerate_bounds |
        | outside_frame     |

  Rule: The report refuses adoption without admissible evidence
    Scenario: No model weights or labeled replay are available
      Given inference and quality are UNMEASURED
      And workload identity is synthetic
      When the decision is built
      Then the decision value is "NO ADOPTION / insufficient evidence"
      And adoption is false
      And every missing cell is listed with a reason

    Scenario: Model-free timings are not inference measurements
      Given the harness measured a preprocessing loop
      When the report is written
      Then inference CPU and inference latency are UNMEASURED
      And the preprocessing timings are labelled model-free
      And no crop speedup is claimed

  Rule: Thresholds precede measurement
    Scenario: The harness runs with frozen defaults
      Given adoption thresholds are constants at the top of the script
      When the report is written
      Then the thresholds are echoed into the report
      And no threshold changed after measurement
```

## Requirements

- R-1: the harness is `scripts/worker/roi_crop_baseline.py`, an on-demand,
  stdlib-only CLI; it imports no third-party package and adds no dependency.
- R-2: both arms run on the same frozen synthetic frames, polygons and
  settings; the baseline is the masked full-frame shape and the candidate
  crops the masked frame to the clipped polygon bounds.
- R-3: the candidate shifts **both** accepted and diagnostic `bbox_xyxy` values
  back into full-frame coordinates before any motion/ROI check; the reverse
  shift is exact.
- R-4: the harness covers nonzero crop offsets, nonrectangular masks, edge
  clipping, no ROI, and empty/degenerate bounds.
- R-5: per processed frame, the harness records parent CPU, child/inference CPU
  status, model-free median/p95 latency and sample counts, plus runtime, model
  and input identities.
- R-6: where no model/weights are available, inference CPU and quality are
  `UNMEASURED` with an explicit reason; model-free timings are never labelled
  inference; no number is fabricated.
- R-7: the JSON report is machine-readable and carries a `decision` field that
  refuses adoption when quality, inference timing or workload identity is
  missing: `NO ADOPTION / insufficient evidence`.
- R-8: adoption thresholds are declared as constants at the top of the script
  before any measurement and echoed into the report.
- R-9: the report binds to a full 40-hex `--tested-sha`; anything else is
  `UNBOUND` and cannot be adoption-eligible.
- R-10: the harness is offline: it opens no socket, reads no camera, no relay
  and no production service, and uses no private media or secret.
- R-11: no production worker file, env flag, API, event coordinate, deploy file
  or workflow changes in this PR; the change is the harness plus this SDD trio.
- R-12: the separate test worker owns `tests/**`; this delivery writes no test
  and records the test design and observed evidence only.

## Acceptance criteria

- AC-001: paired arms on the same frozen frames, polygons and settings: the
  baseline keeps the full-frame inference input; the candidate crops the masked
  frame to the clipped polygon bounds and shifts accepted and diagnostic boxes
  back exactly.
- AC-002: geometry coverage — nonzero offsets, nonrectangular masks, edge
  clipping, no ROI and empty/degenerate bounds — with exact reverse shifts for
  both box sets.
- AC-003: per-frame parent CPU, child/inference CPU status, end-to-end
  median/p95 latency and sample counts are recorded with runtime/model/input
  identities; inference CPU and quality are `UNMEASURED` with reasons when no
  model or weights exist.
- AC-004: a machine-readable JSON report carries a decision that refuses
  adoption when quality, timing or workload identity is missing
  (`NO ADOPTION / insufficient evidence`); thresholds are constants declared
  before measurement.
- AC-005: stdlib-only where practical, no new dependency, no private media, no
  secrets; offline only; no production file, env flag, API or workflow change.
- AC-006: static quality — `py_compile`, `ruff check --config
  scripts/quality/ruff.toml`, `validate_sdd.py` and a scope-limited
  `git status --short` pass, and the changed paths are exactly the harness plus
  the three SDD files.

## NFR assessment

- NFR-001 | Area: Isolation | Target: the harness is offline, opens no socket, reads no camera/relay/service, and imports no third-party package | Validation: source inspection plus a full run with no network/credential input | Evidence: the script imports stdlib modules only; the run completed from synthetic buffers and wrote a local JSON report | Status: PASS
- NFR-002 | Area: Geometry correctness | Target: crop bounds cover the visible polygon and accepted plus diagnostic boxes survive crop → reverse shift exactly for every frozen scenario | Validation: run the harness and inspect `geometry.all_roundtrip_exact` and each scenario row | Evidence: the observed run reported `geometry.all_roundtrip_exact: true` across 6 scenarios (7 accepted and 7 diagnostic boxes each), including edge-clipped, zero-area and outside-frame cases | Status: PASS
- NFR-003 | Area: Evidence honesty | Target: inference CPU, inference latency, quality and workload identity are UNMEASURED with explicit reasons; decision is `NO ADOPTION / insufficient evidence`; model-free timings are never labelled inference | Validation: inspect the report's `decision`, `unmeasured` and arm notes | Evidence: the observed run reported the refusal decision, 10 UNMEASURED cells with reasons, and model-free-only preprocessing timings | Status: PASS
- NFR-004 | Area: Boundedness | Target: fixed scenario count, finite per-scenario frame loop, no external wait or subprocess | Validation: source inspection of loops and the observed run duration | Evidence: six frozen scenarios, 32 frames each per arm, one short local run; no blocking call or child process | Status: PASS
- NFR-005 | Area: Static quality | Target: the new script and SDD pass the repository static gates and touch only the allowed paths | Validation: `python3 -m py_compile`, `ruff check --config scripts/quality/ruff.toml`, `python3 scripts/ci/validate_sdd.py`, `git status --short` | Evidence: `py_compile` and ruff passed; the SDD validator and final scope check are recorded in `tasks.md` | Status: PASS
- NFR-006 | Area: Test coverage | Target: the test worker's `tests/**` cases pin the geometry helpers and the refusal rule | Validation: test-worker delivered test run | Evidence: the test file and its results are owned by the separate test worker and remain PENDING in this delivery; no test is written or modified here | Status: CONCERNS

## Runtime feedback

- Offline experiment only: no runtime contour, deploy lane, acceptance probe,
  env flag or production change is introduced and no service is contacted.
- The evidence run is bound to one host and one tested SHA. Different hardware,
  OpenCV availability, weights or frames make a new measurement, not a
  contradiction of this one.
- Synthetic frames prove geometry and preprocessing cost only; inference cost
  and quality stay `UNMEASURED`, so no adoption claim is made.
- Where a prerequisite is absent (OpenCV, weights, labels), the affected cell is
  `UNMEASURED` with its exact reason and no number is invented.
