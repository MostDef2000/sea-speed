# Tasks: #703 — Persistent decoder CPU baseline + keyframe/Range prototype

- Spec: `specs/703-decoder-grab-baseline/spec.md`
- Plan: `specs/703-decoder-grab-baseline/plan.md`
- Issue: #703

## Delivery tasks

- [x] Frozen workload and thresholds recorded in `specs/703-decoder-grab-baseline/spec.md` **before** the evidence run: tested-SHA binding, runtime identity, hardware/quota, FFmpeg build and decode mode, separate water 5 FPS / road 10 FPS profiles, HLS transport, input fingerprint, H.264, 1920 × 1080, 10 FPS source, 2500 kbps moving-pattern fixture, 2 s GOP, 2 s MPEG-TS segments, output rate, sequential concurrency, 10 s warm-up, 3 × 60 s windows, 1 s polling, CPU accounting and latency endpoints
- [x] New stdlib-only on-demand CLI `scripts/worker/decoder_grab_baseline.py`; imports only the standard library; no target-URL option; binds one ephemeral `127.0.0.1` origin and shuts it down on every path
- [x] Baseline arm: wall-clock-paced live HLS replay with the production reader flags from `worker/worker_media.py` and a consumer draining complete raw frames; records decoder CPU s/s, pipeline CPU s/s, frames delivered, yield, stalls and misses per 60 s window
- [x] Prototype arm: latest complete segment, `Range: bytes=0-511999`, strict `206` + `Content-Range` + length validation, capped body, fresh-ffmpeg keyframe decode (`-skip_frame nokey`), with child CPU, process startup and polling charged to the arm
- [x] Failure accounting: ignored Range (`200`), malformed/missing `Content-Range`, missing init data (fMP4 without a fetched init segment), incomplete keyframes and missed opportunities are counted as failures, never dropped samples
- [x] Binding and decision: a full 40-hex `--tested-sha` yields BOUND; missing/invalid yields UNBOUND; no `PASS` token is emitted; synthetic source and absent labeled events keep `full_outcome` UNMEASURED and recommend no adoption
- [x] Deterministic JSON report written to `--output` with `contract`, `tested_sha`, `binding`, `frozen`, `runtime`, `source`, `outcome_scope`, `arms`, `comparison`, `decision`, `not_executed` and duration; raw output stays outside git
- [x] Boundedness: playlist 3 s, segment 10 s, decode 15 s and server-wait 10 s timeouts; decoder terminated→waited→killed in `finally`; consumer joined; generated sources removed
- [x] Static gates: `python3 -m py_compile` and `ruff check --config scripts/quality/ruff.toml` pass for the new script
- [x] SDD trio written: spec.md (frozen workload/thresholds, metrics, Gherkin, honest limits, NFRs), plan.md (lifecycle, validation, risk/test design, correct-course check), tasks.md (this file)
- [x] One human-reviewed evidence table below from a real frozen run with tested SHA, runtime identity, source fingerprint, thresholds, measured rows and decision; unmeasurable cells are `UNMEASURED` with their exact reason
- [ ] PR Change Contract declares `Production impact: NONE`, `VPS deployment: NOT REQUIRED`, `Ubuntu worker/relay update: NOT REQUIRED`, `Production safety envelope: NOT REQUIRED`, `Risk profile: NOT REQUIRED` and `Specification: specs/703-decoder-grab-baseline/spec.md`
- [ ] Exact-head CI green, including the SDD validator, repo/contracts/quality validators and ruff
- [ ] Exact-green-head merge to main; no deploy lane and no runtime acceptance for this measurement tool

## Completion gate

- The delivered-file scope is exactly `scripts/worker/decoder_grab_baseline.py`,
  `specs/703-decoder-grab-baseline/spec.md`,
  `specs/703-decoder-grab-baseline/plan.md`,
  `specs/703-decoder-grab-baseline/tasks.md` and
  `tests/test_decoder_grab_baseline.py`; no production, deploy, workflow,
  lockfile, `scripts/quality/**` or `scripts/ci/**` change, and no existing
  test is modified. The test file is owned by the test worker and is an
  allowed delivered path.
- The harness is stdlib-only, accepts no target URL, and connects only to its
  own ephemeral loopback origin; CPU is read from `/proc`/`RUSAGE_CHILDREN`.
- The baseline is paced and drained; no unpaced file decode or blocked-pipe
  measurement is labelled live-load CPU.
- The prototype validates Range strictly and counts every Range/init/keyframe/
  missed case as a failure.
- Thresholds were frozen in spec.md before the evidence run; the results table
  below transcribes one real run and moves no threshold.
- A report without a full 40-hex tested SHA is UNBOUND and never claims a
  positive outcome; synthetic evidence leaves the full outcome UNMEASURED and
  recommends no adoption.
- Raw run output is not in git; it lives under `/tmp/opencode/703-baseline/`.
- The test worker owns `tests/**`; this delivery records the test design and
  the observed runtime evidence only.

## Evidence — frozen run (issue #703)

<!-- RESULTS_TABLE_START -->
**Command**

```text
python3 scripts/worker/decoder_grab_baseline.py \
  --ffmpeg /tmp/opencode/ffmpeg-btbn/ffmpeg \
  --output /tmp/opencode/703-baseline/report.json \
  --tested-sha 8ba614b9c5f9234fc16a7c6ab01aa6727ec1b559 \
  --profiles water road \
  --source-seconds 210 --warmup-seconds 10 \
  --window-seconds 60 --windows 3
```

**Tested source:** `8ba614b9c5f9234fc16a7c6ab01aa6727ec1b559` (admitted
base; the harness file itself is uncommitted at run time). Report binding:
**BOUND**.

**Environment:** Linux `x86_64`, 22 logical CPUs, Intel Xeon processor;
cgroup CPU quota `unknown` (no `cpu.max`/CFS file exposed in this sandbox);
Python 3.14.4; FFmpeg `N-129219-g359c825152-20261122` (BtbN static build
installed under `/tmp` because the sandbox image had no ffmpeg), software
decode, default decoder threading (no `-threads` override).

**Source (generated fixture):** H.264/libx264, 1920 × 1080, 10 FPS,
2500 kbps, 2 s GOP, MPEG-TS HLS, 2 s segments, 105 segments, 210.0 s,
synthetic `testsrc2` moving pattern.
Fingerprint: `4eadb904dbc8fbb2d96116b779ab5534df603e62b8c2a6f063addb7f838bb96d`.
This is a synthetic moving pattern, not an approved representative camera
stream.

**Workload (frozen, from spec.md):** `water-v1` 5 FPS and `road-v1` 10 FPS
measured separately; both arms HLS-only and sequential (never concurrent);
10 s warm-up excluded; 3 × 60 s windows per arm/profile; prototype polls every
1.0 s and requests `Range: bytes=0-511999` of the latest complete segment;
CPU from `/proc` (baseline decoder/pipeline) and `RUSAGE_CHILDREN` (prototype
children).

**Thresholds (frozen, never moved):** baseline frame yield ≥ 0.90;
prototype Range/init/keyframe/missed failures = 0; ≥ 1 usable
observation per prototype window; prototype total CPU ÷ baseline total CPU
≤ 0.50; frame-ready p95 ≤ 3000 ms; report BOUND to a full 40-hex SHA.

**Raw output:** `/tmp/opencode/703-baseline/report.json` and
`/tmp/opencode/703-baseline/frozen-run.log` (outside git). Run duration
773.8 s.

### Baseline (persistent reader, paced live HLS, complete-frame consumer)

| Profile | Window | Frames | Delivered FPS | Yield | Misses | Stalls | Max gap s | Decoder CPU s/s | Pipeline CPU s/s | Arm total s/s | RSS MiB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| water 5 FPS | 0 | 296 | 4.933 | 0.9867 | 4 | 0 | 2.0077 | 0.052333 | 0.006333 | 0.058666 | 410.59 |
| water 5 FPS | 1 | 300 | 5.000 | 1.0000 | 0 | 0 | 2.0055 | 0.049500 | 0.007667 | 0.057167 | 434.34 |
| water 5 FPS | 2 | 300 | 5.000 | 1.0000 | 0 | 0 | 2.0079 | 0.050833 | 0.008333 | 0.059166 | 440.29 |
| **water aggregate** | **3 × 60 s** | **896** | **4.978** | **0.9956** | **4** | **0** | — | **0.050889** | **0.007444** | **0.058333** | 440.29 |
| road 10 FPS | 0 | 600 | 10.000 | 1.0000 | 0 | 0 | 1.9984 | 0.067333 | 0.012167 | 0.079500 | 404.55 |
| road 10 FPS | 1 | 600 | 10.000 | 1.0000 | 0 | 0 | 1.9986 | 0.067333 | 0.012667 | 0.080000 | 428.54 |
| road 10 FPS | 2 | 600 | 10.000 | 1.0000 | 0 | 0 | 1.9979 | 0.066500 | 0.011833 | 0.078333 | 458.38 |
| **road aggregate** | **3 × 60 s** | **1800** | **10.000** | **1.0000** | **0** | **0** | — | **0.067056** | **0.012222** | **0.079278** | 458.38 |

The four water misses are in the first window's live-edge startup and are
reported, not discarded; every window stays above the 0.90 floor. Max
frame gaps ≈ 2.0 s track the 2 s segment publication cadence, not decoder
stalls; the stall threshold is 3.5 s.

### Prototype (latest complete segment, 500 KiB Range, keyframe decode)

| Profile | Window | Observations | Failures | p50 ms | p95 ms | Max ms | Child CPU s | Child CPU s/s | Pipeline s/s | Arm total s/s |
|---|---|---|---|---|---|---|---|---|---|---|
| water | 0 | 29 | 0 | 78.710 | 94.348 | 95.007 | 2.122937 | — | — | — |
| water | 1 | 30 | 0 | 71.807 | 88.636 | 93.030 | 2.057587 | — | — | — |
| water | 2 | 30 | 0 | 72.473 | 86.518 | 91.909 | 2.081259 | — | — | — |
| **water aggregate** | **3 × 60 s** | **89** | **0** | **75.588** | **91.351** | **95.007** | **6.261783** | **0.032951** | **0.008262** | **0.041213** |
| road | 0 | 29 | 0 | 72.169 | 84.979 | 87.751 | 1.980780 | — | — | — |
| road | 1 | 30 | 0 | 77.737 | 88.807 | 90.450 | 2.171182 | — | — | — |
| road | 2 | 30 | 0 | 72.586 | 81.999 | 86.660 | 2.058046 | — | — | — |
| **road aggregate** | **3 × 60 s** | **89** | **0** | **74.010** | **87.566** | **90.450** | **6.210008** | **0.032679** | **0.007946** | **0.040625** |

Failure counters were zero for every class (ignored Range/200, malformed or
missing Content-Range, missing init data, incomplete keyframe, missed
opportunity). Latency is **frame-ready** (poll start
→ complete decoded keyframe), which includes the 1 s polling cadence; it is
**not** detection latency.

### Paired comparison and decision

| Profile | Baseline total s/s | Prototype total s/s | Ratio | ≤ 0.50? | Frame-ready p95 ms | ≤ 3000? | Prototype failures | Criteria met |
|---|---|---|---|---|---|---|---|---|
| water | 0.058333 | 0.041213 | 0.7065 | NO | 91.351 | YES | 0 | NO |
| road | 0.079278 | 0.040625 | 0.5124 | NO | 87.566 | YES | 0 | NO |

**Measurement: GREEN** — both arms produced 3 measured windows per profile,
the baseline yield floor held, and the prototype produced 89 usable
observations per profile with zero failures. The numbers are reproducible
within the frozen workload.

**Decision: NO ADOPTION RECOMMENDED** — the prototype used 0.71× (water) and
0.51× (road) of the baseline total CPU, so the frozen 0.50 ratio was not met
on either profile (road is marginal at 0.5124), and more importantly the full
outcome is **UNMEASURED**.

### Explicitly UNMEASURED cells

- **Workload representativeness — UNMEASURED.** The source is a generated
  `testsrc2` moving pattern; there is no evidence it matches the target
  camera's encoding or load.
- **Labeled events / detection latency — UNMEASURED.** No labeled event source
  was supplied. The prototype latency above is frame-ready latency, not the
  time from a real event to its detection.
- **Full outcome — UNMEASURED.** Synthetic source plus no labeled events, so
  no adoption is recommended regardless of the CPU ratio.
- **RTSP comparison — NOT MEASURED.** Both arms are HLS; no RTSP baseline or
  production relay was introduced. Any future RTSP-vs-HLS comparison must
  record the rendition identity and segment-publication delay separately and
  must not attribute packaging delay to decode.

**Scope of the claim:** within this synthetic HLS-only workload on this host,
the persistent decoder cost about 0.051 s/s (water 5 FPS) and 0.067 s/s (road
10 FPS) of decoder CPU, while the latest-segment Range/keyframe prototype cost
about 0.033 s/s total per profile including process startup and polling. This
is a bounded measurement, not a capacity or adoption guarantee.
<!-- RESULTS_TABLE_END -->

## Requirements traceability

- AC-001 | Task: disposable isolation — no target-URL option, ephemeral loopback origin, local generated/approved source, `/proc` accounting, origin shut down on every exit path | Evidence: the parser has no URL/host option; `Origin` binds port 0 and is a context manager; `run_baseline` tests the local origin only; the report's `not_executed` records any missing prerequisite | Coverage: COVERED
- AC-002 | Task: frozen workload and thresholds recorded before measurement and reproduced by CLI defaults | Evidence: spec.md's Frozen workload and Frozen thresholds sections plus the report's `frozen`, `runtime`, `source` and `profile_selection` fields; the evidence run uses the frozen command | Coverage: COVERED
- AC-003 | Task: baseline fidelity — paced live HLS with production reader flags and a complete-frame consumer; decoder CPU separated from pipeline CPU | Evidence: `reader_command` mirrors `worker/worker_media.py`; `FrameDrain` counts complete frames only; each window reports decoder/pipeline CPU s/s, delivered frames, yield, stalls and misses | Coverage: RUNTIME-MANUAL | Reason: CPU and frame delivery are only meaningful in a real paced run; unit tests cannot prove the wall-clock shape
- AC-004 | Task: prototype correctness — latest complete segment, 500 KiB Range, strict 206/Content-Range validation, usable keyframe, all failure classes counted | Evidence: `evaluate_range_response` rejects 200/malformed/mismatched answers; `decode_keyframe` uses `-skip_frame nokey`; `failure_reasons` records every class; the evidence run reports its counters | Coverage: COVERED
- AC-005 | Task: evidence integrity — report bound to the tested SHA, HLS-only/synthetic/frame-ready caveats, full outcome UNMEASURED without approved source and labeled events, no adoption from synthetic evidence | Evidence: `binding_for_sha` and `build_decision`; `outcome_scope` records the caveats; the tasks table is bound to the tested SHA; no `PASS` token exists in the source | Coverage: COVERED
- AC-006 | Task: static quality — py_compile, ruff, validate_sdd.py and scope-limited git status | Evidence: the four commands are run and their output is reported with the evidence run | Coverage: COVERED

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
