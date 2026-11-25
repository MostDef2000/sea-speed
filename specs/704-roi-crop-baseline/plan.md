# Plan: #704 — ROI-crop inference baseline (offline measurement)

- Issue: #704
- Specification: `specs/704-roi-crop-baseline/spec.md`

## Architecture

One stdlib-only CLI, `scripts/worker/roi_crop_baseline.py`, with no runtime,
deploy, API or CI wiring. It owns a frozen synthetic workload and measures two
arms sequentially over the same scenarios.

Lifecycle:

1. Parse the frozen CLI (`--output`, optional `--tested-sha`, frozen
   `--frames-per-scenario`). There is no target URL, camera, host or model
   option. `ADOPTION_THRESHOLDS` is declared at module top before any
   measurement.
2. Record runtime identity (platform, Python, logical CPUs, CPU model, cgroup
   CPU quota), model identity (`models/yolo26x.pt`, image size 960 from
   `worker/analytics_profiles.py`, weights unavailable) and the frozen input
   identity (frame size, six scenarios, frames per scenario, fingerprint).
3. Build the six frozen scenarios: nonzero offset, nonrectangular, edge
   clipped, no ROI, degenerate zero-area bounds and outside-frame bounds.
4. For each scenario, `resolve_crop()` computes the clipped polygon bounds.
   Fewer than three points, zero polygon area or empty clipped bounds take the
   full-frame identity path with a recorded reason; every other polygon yields
   a crop box and offset.
5. `verify_scenario()` builds deterministic accepted and diagnostic records
   carrying `bbox_xyxy`, shifts them into crop coordinates, shifts them back by
   the crop offset, and asserts exact equality for both sets. The result feeds
   `geometry.all_roundtrip_exact`.
6. `measure_arm("baseline")` and `measure_arm("candidate")` run the same
   scenarios over a 1920 × 1080 × 3 synthetic frame. Baseline touches the
   full-frame synthetic buffer (no copy). Candidate resolves bounds and copies
   the cropped region. Neither arm rasterizes the production mask. Both record
   per-frame wall latency (nearest-rank median/p95) and parent CPU from
   `time.process_time()`.
7. Child CPU, inference CPU, inference latency, mask pixel cost and quality are
   `UNMEASURED` with explicit reasons: the harness spawns no inference child and
   this environment has neither OpenCV nor model weights nor labels.
8. Build the JSON report with `binding`, `frozen`, `runtime`, `model`, `input`,
   `quality`, `scenarios`, `geometry`, `arms`, `comparison`, `decision`,
   `unmeasured` and `duration_seconds`, then write it sorted and indented.

Determinism and honesty:

- Geometry is integer arithmetic, so the reverse shift is exact. Scenario
  polygons and frame dimensions are frozen constants.
- Measured numbers are host-specific preprocessing observations; the report
  labels them model-free and never as inference.
- The decision is built from the report, not from intent: any UNMEASURED
  inference, quality or workload cell forces
  `NO ADOPTION / insufficient evidence`.

## Decisions

- **Stdlib-only, no model runtime.** The experiment needs geometry and
  preprocessing cost first. A stdlib harness runs everywhere and cannot
  accidentally claim an inference result it did not measure.
- **Mirror the production mask shape, do not reimplement OpenCV.** The baseline
  keeps the full-frame inference input as `worker/worker_roi.py` does. The mask
  itself is recorded as UNMEASURED because `cv2.fillPoly` is not available; a
  pure-Python rasterizer would produce a misleading cost.
- **Crop the synthetic buffer region, not a rasterized mask.** The candidate
  computes clipped polygon bounds, copies the crop region and shifts boxes
  back. The production mask is not executed in either arm, so mask pixel cost
  is `UNMEASURED`; the measured claim is geometry and crop-copy cost only.
- **Reverse shift both box sets.** Accepted detections and diagnostic records
  share `bbox_xyxy`; shifting both by the same integer offset keeps ROI/motion
  checks in full-frame coordinates and prevents a coordinate-space bug.
- **Identity fallback for no ROI and degenerate bounds.** A zero-sized crop
  must never reach inference. Fall back to full frame and record the reason.
- **Frozen thresholds before data.** `ADOPTION_THRESHOLDS` covers samples,
  preprocessing ratio, inference ratio, end-to-end p95, quality parity, workload
  identity and tested-SHA binding; it is echoed into the report.
- **Enforce every declared threshold.** `build_decision` compares each measured
  ratio to its frozen maximum, honors the quality/inference/quality/identity/
  SHA requirement flags, and turns a breach or missing cell into an explicit
  refusal reason. It never returns adoption on an over-threshold ratio.
- **Investigation runs are visibly non-frozen.** A non-default
  `--frames-per-scenario` sets `frozen.investigation_only=true`, changes the
  frozen note and adds a refusal reason, so an override cannot masquerade as
  frozen evidence.
- **Malformed boxes fail closed.** A present `bbox_xyxy` that is not a
  4-element list raises a clear `ValueError`; only a genuinely absent key is
  skipped.
- **Refuse adoption on missing evidence.** The repository has no labels,
  weights or fixtures and this environment has no OpenCV, so the honest decision
  is `NO ADOPTION / insufficient evidence`, never a claimed crop win.
- **Measurement only.** No production worker, env flag, API, deploy file,
  workflow or lockfile changes. Adoption is a separate, measured, authorized
  change.
- **No test edits here.** A separate test worker owns
  `tests/test_roi_crop_baseline.py` (new) and the
  `tests/test_701_crossing_votes.py` guard re-pin; this code worker edits
  neither and records the pure-helper oracles the tests pin.

## Affected contours

- Repository (code worker): `scripts/worker/roi_crop_baseline.py` (new) and
  the SDD trio under `specs/704-roi-crop-baseline/` (new).
- Repository (test worker): `tests/test_roi_crop_baseline.py` (new) and
  `tests/test_701_crossing_votes.py` (guard re-pin only).
- VPS: NONE — no `api/**`, `frontend/**`, `deploy/**` or `contracts/**` change.
- Ubuntu worker/relay: NONE — no `worker/**` change; the harness only mirrors
  the existing ROI shape for measurement.
- Windows worker/AI: NONE.
- Public interfaces: NONE — no endpoint, event coordinate, schema or contract
  change.
- CI interfaces: NONE — no workflow, gate or artifact upload.
- Tests: the two admitted `tests/**` paths above are owned by the separate test
  worker; this code worker neither writes nor edits them.
- Change-control impact: NONE — `scripts/worker/` is not a CONTROL_PLANE
  pattern; this is an offline developer tool.
- Explicitly unchanged: production source, deploy/workflow files, env examples,
  lockfiles, `scripts/quality/**`, `scripts/ci/**` and every test except the
  two admitted test-worker paths.

## Validation

- Static: `python3 -m py_compile scripts/worker/roi_crop_baseline.py`,
  `ruff check --config scripts/quality/ruff.toml
  scripts/worker/roi_crop_baseline.py`, `python3 scripts/ci/validate_sdd.py`,
  and `git status --short` showing only the admitted #704 surface (the harness,
  the SDD trio and the two test-worker-owned test files).
- Geometry oracle: the harness run reports
  `geometry.all_roundtrip_exact: true`, `crop_used: 3`,
  `identity_fallback: 3`, and `edge_clipped: 2`, with every scenario row
  showing exact accepted and diagnostic round trips.
- Refusal oracle: the run reports
  `decision.value == "NO ADOPTION / insufficient evidence"`, `adoption == false`
  and reasons covering inference, quality, workload identity and any measured
  ratio above its frozen maximum; a non-default frame count adds the
  investigation-only reason.
- UNMEASURED oracle: `unmeasured` lists inference CPU/latency, mask cost,
  child CPU, quality and workload identity with explicit reasons; no arm claims
  an inference number.
- Boundedness oracle: six frozen scenarios × 32 frames per arm completes as one
  short local run with no socket, subprocess or external wait.
- Test ownership: `tests/test_roi_crop_baseline.py` pins `resolve_crop` (no
  ROI, degenerate, outside-frame, clipped), `shift_records` exactness for
  accepted and diagnostic keys plus malformed-box fail-closed,
  `binding_for_sha`, percentile nearest-rank, threshold enforcement and that
  `build_decision` never sets `adoption` while any inference/quality/workload
  cell is UNMEASURED. `tests/test_701_crossing_votes.py` only re-pins its guard.

## Runtime feedback

- Offline experiment: no runtime contour, deploy lane, acceptance probe or
  production service.
- One host and one tested SHA bound the run; a different host or model makes a
  new measurement.
- Synthetic frames keep workload identity UNMEASURED; no adoption is
  recommended and no production change follows from this report.
- Raw output stays outside git under `/tmp/opencode/704-roi-crop/`.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: freeze crop and reverse-shift semantics in pure integer helpers and exercise no-ROI, degenerate, outside-frame and edge-clipped cases in the same run | Validation: `geometry.all_roundtrip_exact` and per-scenario accepted/diagnostic exact flags in the observed report | Residual risk: a future production crop could still use different bounds or apply motion checks in crop coordinates, which this offline harness cannot catch | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-002 | Category: PERF | Probability: 3 | Impact: 2 | Score: 6 | Mitigation: label every measured number as model-free preprocessing and mark inference CPU, latency and quality UNMEASURED with reasons | Validation: `decision.value`, `unmeasured` and arm notes in the observed report | Residual risk: a reader could still mistake the preprocessing ratio for an inference win; the decision and notes explicitly deny it | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: keep the code change to one offline script plus SDD text; the test worker owns the two admitted tests/** files; no production file, env flag, API, deploy file, workflow or lockfile is touched | Validation: `git status --short` and `git diff --stat` show only the admitted #704 surface (harness, SDD trio, two test-worker files) | Residual risk: none introduced by this change because it cannot run in production | Owner: delivery-orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `resolve_crop` returns the clipped bbox and offset for a nonzero polygon, and `shift_records` round-trips accepted and diagnostic `bbox_xyxy` exactly
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: `resolve_crop` covers nonrectangular, edge-clipped, no-ROI (<3 points), zero-area and outside-frame polygons; fallbacks are full frame with the expected reason; both box sets round-trip
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: arm rows expose processed frames, per-scenario samples, model-free median/p95 and parent CPU, while child/inference CPU, inference latency and quality are the literal `UNMEASURED`
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `build_decision` returns `NO ADOPTION / insufficient evidence` and `adoption: false` while inference, quality or workload identity is UNMEASURED; an over-threshold measured ratio and a non-default `investigation_only` run are explicit refusal reasons; `ADOPTION_THRESHOLDS` is echoed unchanged
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P1 | Evidence: the script imports only the standard library, exposes no target/network option and never writes outside `--output`
- TEST-006 | Covers: AC-006 | Level: runtime-manual | Priority: P1 | Evidence: the static commands pass and `git status --short` shows only the admitted #704 surface: harness, SDD trio, `tests/test_roi_crop_baseline.py` and the `tests/test_701_crossing_votes.py` re-pin

## Correct-course check

- Trigger: NONE
- Issue impact: none — the scope matches issue #704 as admitted: an offline ROI-crop measurement harness and its SDD, with no production change.
- Specification impact: none — the frozen workload and adoption thresholds are stated before measurement; unmeasurable cells are UNMEASURED.
- Plan impact: none — the implementation follows the admitted paired-arm, exact reverse-shift, refusal-on-missing-evidence design.
- Tasks impact: none — the harness, SDD, observed evidence and the test-worker test files are delivered; PR lifecycle, CI and merge remain with the orchestrator.
- Authorization impact: NONE — bounded worker work order on branch `agent/wave9-704-roi-crop-baseline`; the orchestrator owns Git lifecycle, PR admission and CI evidence.
- Follow-up: if a later owner-authorized run supplies real frames, weights and labels, it must be a separate measurement and change; this report records no adoption.

## Deployment transaction audit

No deploy exists in this scope. The eight stages are recorded as honestly
non-mutating so the audit cannot be mistaken for a deployment. The only writes
are the admitted #704 source/SDD files on a feature branch (plus the test
worker's two admitted test files); no host, service or production state is
touched.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: no repository or runtime state changed; an out-of-scope request is refused before any edit | Retry: rerun after the scope is corrected | Rollback: not applicable — no mutation occurred | Evidence: issue #704 work order and allowed-path list
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: no production, deploy or workflow state exists in this scope to inspect | Retry: re-read the allowed paths | Rollback: not applicable — no mutation occurred | Evidence: base SHA and clean branch check
- TX-003 | Stage: MUTATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: only the harness and SDD files can be written or edited by this worker; the test worker owns the two test files; no production mutation path exists | Retry: rerun the local edit | Rollback: remove the new files from the branch | Evidence: `git status --short` lists only the admitted #704 surface
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: an unverified change stays local and unmerged | Retry: rerun `py_compile`, ruff, the harness and `validate_sdd.py` | Rollback: discard the branch changes | Evidence: static commands and the observed JSON report in `tasks.md`
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: no production state store exists in this scope | Retry: none — commit ownership stays with the orchestrator | Rollback: revert the local commit if one is made | Evidence: no deploy, release manifest or runtime state write occurs
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scratch output stays outside git | Retry: remove scratch output | Rollback: not applicable — scratch is disposable | Evidence: raw report path `/tmp/opencode/704-roi-crop/`
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: a missing cell is recorded as UNMEASURED, never fabricated | Retry: rerun the harness after prerequisites exist | Rollback: not applicable — evidence is append-only text | Evidence: JSON report and `tasks.md` evidence section
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: no production state exists to restore; the branch can simply be abandoned | Retry: not applicable — nothing to retry | Rollback: delete the admitted #704 files; no host or service action | Evidence: branch-only change with no deploy or runtime contour
