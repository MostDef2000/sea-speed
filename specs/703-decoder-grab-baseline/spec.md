# Spec: #703 — Persistent decoder CPU baseline + keyframe/Range prototype

- Issue: #703
- Specification: `specs/703-decoder-grab-baseline/spec.md`
- Authorization: wave-6 admission (issue #703), branch
  `agent/wave6-703-702-687`, base `8ba614b9c5f9234fc16a7c6ab01aa6727ec1b559`.
- Related: #687 and #702 share this wave; this feature owns only the
  measurement harness and its SDD. A separate test worker owns `tests/**`.

## Product outcome

Operators need a repeatable, honest answer to one question: how much CPU does
the **persistent HLS decoder** consume per wall-clock second on the two shipped
analytics profiles, and would a **grab-latest-keyframe over HTTP Range**
prototype cost less while still producing a usable frame?

This feature adds one on-demand, stdlib-only CLI,
`scripts/worker/decoder_grab_baseline.py`. It owns one disposable encoded HLS
timeline served from an ephemeral `127.0.0.1` origin and measures two arms
against that same timeline:

1. **Baseline** — a real ffmpeg subprocess with the production HLS reader
   flags (`worker/worker_media.py:42-94`) decodes a wall-clock-paced live HLS
   playlist while a consumer drains every complete raw frame. Decoder CPU and
   the whole sampling-pipeline CPU are recorded separately.
2. **Prototype** — poll the live playlist, take the latest **complete**
   segment, fetch only its first **500 KiB** with `Range`, require `206` and a
   matching `Content-Range`, cap the body, and decode one **keyframe** with a
   fresh ffmpeg process. Process startup and polling are part of the measured
   cost.

The deliverable is a measurement, not a production change. This spec does
**not** authorize a production flag, a reader replacement, a transport change,
or a production relay. It says nothing about a live camera, the production
relay, or a deployed host.

## Frozen workload (recorded before measurement)

The committed evidence run uses exactly these values. CLI defaults reproduce
them; overriding any value produces a non-frozen investigation run and is not
evidence. Both arms run **sequentially** (never concurrently) so they do not
contend for CPU.

| Knob | Frozen value |
|---|---|
| Tested source | full 40-hex SHA passed as `--tested-sha`; the report is UNBOUND without it |
| Runtime identity | recorded at run start: platform, Python, logical CPUs, CPU model, cgroup CPU quota, FFmpeg build string, software decode mode |
| Hardware / CPU quota | any Linux x86_64 host with `/proc`; the report records the actual host and cgroup quota; numbers are not portable across hosts |
| FFmpeg | `ffmpeg` from `PATH` unless `--ffmpeg PATH`; the version string is recorded; no hardware decode flag |
| Named profiles | `water-v1` at **5 FPS** and `road-v1` at **10 FPS**, measured separately; never averaged together |
| Transport | HLS over the harness's own loopback origin; both arms are HLS, so the comparison is **HLS-only** |
| Input fingerprint | sha256 over the served playlist plus every segment payload, recorded in the report |
| Codec | H.264 (libx264) in MPEG-TS HLS segments; stream init is in-band |
| Source resolution | 1920 × 1080 |
| Source rate | 10 FPS |
| Source bitrate / motion | 2500 kbps CBR-ish, synthetic `testsrc2` moving pattern |
| Source GOP | 2 s (20 frames), keyframe-aligned segment boundaries |
| Source duration | 210 s generated once per run (or `--source-dir` with an equal or longer source) |
| Segment format / duration | MPEG-TS, 2.0 s nominal (`#EXT-X-TARGETDURATION:2`) |
| Playlist window | 6 segments, sliding `#EXT-X-MEDIA-SEQUENCE` |
| Output rate | profile FPS (5 or 10) after `fps=N`; `rawvideo` `bgr24`; 6 220 800 bytes per 1920 × 1080 frame |
| Concurrency | one decoder process + one draining consumer per arm; one arm at a time |
| Warm-up | 10 s excluded from every window |
| Timed duration | 3 consecutive 60 s windows per arm and profile |
| Repetitions | one run per arm and profile; the three windows are the within-run repetitions |
| Polling cadence (prototype) | 1.0 s |
| Range request | `bytes=0-511999` (500 KiB) on the latest complete segment |
| CPU accounting | baseline decoder: `/proc/<pid>/stat` `utime+stime` ÷ `SC_CLK_TCK`; pipeline: the same fields for the harness PID; prototype children: `RUSAGE_CHILDREN` deltas |
| Latency endpoints | prototype t0 = start of the poll iteration (immediately before the playlist GET); t1 = complete first keyframe frame read; the difference is **frame-ready latency** |
| Detection latency | **UNMEASURED** — this harness has no labeled events and does not claim detection latency |
| Full-outcome scope | synthetic fixture and no labeled events ⇒ `full_outcome: UNMEASURED`; no adoption is recommended |

## Frozen thresholds (recorded before measurement)

Every row is evaluated per profile. A measured breach is a failed criterion
recorded with its value; a threshold is never relaxed after seeing data.

| ID | Metric | Unit | Threshold |
|---|---|---|---|
| BIND | report bound to a full 40-hex `--tested-sha` | — | BOUND |
| BASE-YIELD | frames delivered ÷ (profile FPS × measured wall seconds) per measured window | ratio | ≥ 0.90 in every measured window |
| BASE-STALL | frame-arrival gaps longer than 3.5 s | count | reported per window; a stall is not reclassified as a sample |
| BASE-MISS | expected frames − delivered frames per window | frames | reported; validity also requires BASE-YIELD |
| BASE-CPU | decoder CPU seconds per wall second | s/s | reported (no adoption gate; this is the baseline) |
| PROT-RANGE | Range answers that are not `206` with a valid `Content-Range` | count | 0 |
| PROT-INIT | missing stream-init data failures | count | 0 (MPEG-TS init is in-band; an fMP4 segment without a fetched init segment is counted as `missing_init_data`) |
| PROT-KEY | capped bytes that do not decode a usable keyframe | count | 0 |
| PROT-MISS | missed opportunities (playlist advanced by more than one segment between 1 s polls) | count | 0 |
| PROT-FAIL | sum of all prototype failure counters | count | 0 |
| PROT-OBS | usable keyframe observations per measured window | count | ≥ 1 |
| PROT-CPU-RATIO | prototype total arm CPU ÷ baseline total arm CPU | ratio | ≤ 0.50 |
| PROT-LAT-P95 | frame-ready latency p95 (nearest-rank) | ms | ≤ 3000 |
| MEASURE | baseline and paired prototype arms both measured with non-empty windows | — | GREEN |

`decision.measurement` is `GREEN` only when BIND, MEASURE, BASE-YIELD and the
prototype observation floor hold. `recommendation` is
`NO_ADOPTION_RECOMMENDATION` whenever the full outcome is UNMEASURED, even
when every performance threshold passes. The literal token `PASS` is never
emitted: an unbound or partial report must not look green.

## Metric definitions

- **Decoder CPU (s/s)**: Δ(`utime`+`stime`) of the ffmpeg PID over a window,
  divided by the window's monotonic wall seconds. One unit is one core-second
  per wall second (core-equivalents). It excludes the consumer.
- **Pipeline CPU (s/s)**: the same calculation for the harness process over
  the same window. It covers the draining consumer and the loopback origin.
  It is reported separately from decoder CPU and added only for the arm total.
- **Prototype child CPU (s)**: `RUSAGE_CHILDREN` delta around one decode
  process. It includes ffmpeg process startup and decode of the capped bytes.
- **Prototype arm CPU (s/s)**: (sum of child CPU + harness pipeline CPU over
  the arm) ÷ arm wall seconds. Polling and repeated startup are therefore in
  the cost.
- **Frames delivered**: complete raw frames the consumer read from the
  decoder's stdout pipe. A partial frame is never counted.
- **Frame yield**: frames delivered ÷ (profile FPS × measured wall seconds) per
  measured window; the aggregate is reported for context, and every measured
  window must meet the 0.90 floor.
- **Frame-arrival gap / stall**: monotonic time between consecutive complete
  frames; a gap above 3.5 s is counted as a stall. Live HLS may deliver small
  bursts; a gap is reported, not silently dropped.
- **Misses**: max(0, round(expected frames − delivered frames)) per window.
- **Range validation**: status must be `206`; `Content-Range` must parse as
  `bytes 0-<end>/<total>` with `end = min(500 KiB, total) − 1` and the same
  total; `Content-Length` and body length must equal `end + 1`; the body is
  capped at 500 KiB. A `200` full-body answer is a Range failure, not a
  success.
- **Usable keyframe**: ffmpeg with `-skip_frame nokey` decodes at least one
  full frame from the capped bytes. Zero output or a short output is an
  incomplete-keyframe failure.
- **Missed opportunity**: the live playlist advanced by more than one segment
  between consecutive 1 s polls, so a complete segment was never considered.
- **Frame-ready latency**: poll start → complete first keyframe. It is **not**
  detection latency; no labeled event exists to measure detection.

## Honest limits

- The generated `testsrc2` fixture is a **moving pattern**, not the camera
  scene. It exercises accounting, pacing and Range mechanics only. Without
  evidence that it represents the target encoding and load, and without
  detectable labeled events, the full outcome stays **UNMEASURED**. This
  report does not recommend adoption.
- Both arms use HLS; the comparison is **HLS-only**. No RTSP baseline is
  measured here, and no production relay is introduced. If a future run
  compares RTSP to an existing HLS rendition, the rendition identity and
  segment-publication delay must be recorded separately and must not be
  attributed to decode.
- Frame-ready latency is not detection latency.
- A report without a full 40-hex tested SHA is UNBOUND and cannot claim a
  positive outcome (precedent: #690 UNBOUND).
- One run on one host is a bounded observation, not a capacity guarantee.
- The prototype measures a **decode** of capped bytes, not end-to-end event
  delivery or analytics correctness.

## User scenarios (Gherkin)

```gherkin
Feature: Persistent decoder CPU baseline and keyframe/Range prototype

  Rule: An unbound report never looks green
    Scenario: The run omits --tested-sha
      Given the harness completes every measurement
      When the report is written without a full 40-hex tested SHA
      Then binding is UNBOUND
      And the recommendation is NO_ADOPTION_RECOMMENDATION
      And no PASS token appears in the report

  Rule: A full-body 200 is a Range failure
    Scenario: The origin ignores the Range header
      Given the prototype requests bytes=0-511999
      When the origin answers 200 with the whole segment
      Then the observation records a range_not_honored failure
      And PROT-RANGE counts it
      And the prototype failure count is nonzero

  Rule: Zero usable observations is never a win
    Scenario: Every Range fetch fails validation
      Given the prototype window contains no usable keyframe observation
      When the arm is evaluated
      Then the arm is NOT EXECUTED, not MEASURED
      And the overall measurement is RED
      And the recommendation is not adoption

  Rule: The baseline is paced and drained
    Scenario: Measure the road profile for 3 x 60 seconds
      Given the loopback origin publishes one 2 s segment at a time
      And the ffmpeg reader uses the production HLS flags
      And a consumer drains every complete raw frame
      Then each window reports decoder CPU s/s, pipeline CPU s/s, frames delivered, stalls and misses
      And an unpaced file decode is never labelled live-load CPU

  Rule: The prototype pays for startup and polling
    Scenario: A new complete segment appears
      Given the prototype polls once per second
      When a new segment is available
      Then the first 500 KiB are fetched with Range
      And a fresh ffmpeg process decodes one keyframe
      And its startup CPU and polling time are included in the arm cost

  Rule: Synthetic evidence leaves the full outcome UNMEASURED
    Scenario: The only source is a generated moving pattern
      Given source-class is synthetic and no labeled events are supplied
      When every performance threshold passes
      Then workload representativeness is UNMEASURED
      And labeled events are UNMEASURED
      And full outcome is UNMEASURED
      And the recommendation is NO_ADOPTION_RECOMMENDATION
```

## Requirements

- R-1: the harness is `scripts/worker/decoder_grab_baseline.py`, a
  stdlib-only on-demand CLI; it imports no third-party package.
- R-2: the harness accepts no target URL; it binds an ephemeral `127.0.0.1`
  port, serves only its own local source, and reads `/proc` for accounting.
- R-3: the baseline is a wall-clock-paced replay of one encoded HLS timeline
  with the production HLS reader flags and a consumer draining complete
  frames; an unpaced file decode is never reported as live-load CPU.
- R-4: the prototype takes the latest complete segment, requests only the
  first 500 KiB with Range, strictly requires `206` + a matching
  `Content-Range` + the expected capped length, and decodes a usable keyframe.
- R-5: ignored Range (`200`), malformed/missing `Content-Range`, missing init
  data, incomplete keyframes and missed opportunities are **failures**, never
  discarded samples.
- R-6: repeated prototype process startup and polling are included in the
  prototype cost; prototype child CPU uses `RUSAGE_CHILDREN` deltas.
- R-7: decoder CPU, pipeline CPU and arm totals are reported separately with
  units; CPU uses `/proc/<pid>/stat` and `SC_CLK_TCK`.
- R-8: three 60 s windows after a 10 s warm-up are frozen before measurement;
  the CLI defaults reproduce this spec.
- R-9: the JSON report is deterministic in structure and bound to a full
  40-hex `--tested-sha`; a missing/invalid SHA yields `UNBOUND` and never a
  positive decision.
- R-10: the report states HLS-only, synthetic-workload and frame-ready
  latency caveats and leaves the full outcome UNMEASURED without an approved
  representative source and labeled events.
- R-11: `tasks.md` carries one human-reviewed results table from a real run
  with tested SHA, runtime identity, source fingerprint, thresholds, measured
  rows and a decision; a cell that cannot be measured honestly is marked
  `UNMEASURED` with its exact reason, never fabricated.
- R-12: this change touches no production source, deploy, workflow, lockfile,
  `scripts/quality/**` or `scripts/ci/**` file; it is measurement only. The
  delivered scope includes `tests/test_decoder_grab_baseline.py` as an allowed
  path, owned by the test worker; no existing test is modified by this
  measurement work.

## Acceptance criteria

- AC-001: disposable isolation — no target-URL option; ephemeral loopback
  origin; local generated or approved source only; `/proc` accounting; the
  origin is shut down on every exit path.
- AC-002: frozen workload and thresholds — spec.md records the tested-SHA
  binding, runtime identity, hardware/quota, FFmpeg build and decode mode,
  named profiles, transport, input fingerprint, codec, FPS, bitrate/motion,
  resolution, GOP, segment format/duration, output rate, concurrency,
  warm-up, 3 × 60 s timed windows, polling cadence, CPU accounting, latency
  endpoints and thresholds before measurement; CLI defaults reproduce them.
- AC-003: baseline fidelity — wall-clock-paced HLS replay with the production
  reader flags and a complete-frame consumer; reports decoder CPU s/s,
  pipeline CPU s/s, frames delivered, stalls and misses per window.
- AC-004: prototype correctness — latest complete segment, 500 KiB Range,
  strict 206/Content-Range/length validation, usable-keyframe decode, and all
  Range/init/keyframe/missed cases counted as failures.
- AC-005: evidence integrity — JSON report bound to the tested SHA (UNBOUND
  otherwise), explicit HLS-only/synthetic/frame-ready caveats, full outcome
  UNMEASURED without approved source and labeled events, and no adoption
  recommendation from synthetic evidence.
- AC-006: static quality — `py_compile`, `ruff check --config
  scripts/quality/ruff.toml`, `validate_sdd.py` and a scope-limited
  `git status --short` pass, and the changed paths are exactly this script
  plus the three SDD files.

## NFR assessment

- NFR-001 | Area: Isolation | Target: the harness accepts no target URL, binds one ephemeral 127.0.0.1 origin, serves only a local source, and closes the origin on every exit path | Validation: source inspection of the option parser and socket target, plus a full run followed by a check that no listener remains | Evidence: the parser exposes no host/URL option; the origin is a ThreadingHTTPServer on port 0 with a context-managed shutdown; the run exits after closing it | Status: PASS
- NFR-002 | Area: Boundedness | Target: every wait is finite (playlist 3 s, segment 10 s, decode 15 s, server wait 10 s); windows are fixed at 3 × 60 s; the decoder is terminated then killed | Validation: source inspection of every blocking call plus a run with the decoder exiting early | Evidence: every HTTP call and subprocess wait has a timeout; `run_baseline` terminates and waits before killing the decoder; a crashed decoder is reported with its exit code instead of hanging | Status: PASS
- NFR-003 | Area: Measurement fidelity | Target: CPU is measured from /proc and RUSAGE_CHILDREN, frames are counted only when complete, decoder CPU is separated from pipeline CPU, and Range validation rejects 200/malformed answers | Validation: run the harness and inspect the report's per-window rows and failure counters | Evidence: the evidence run reports decoder and pipeline CPU separately, complete-frame counts, Range/Content-Range results and explicit failure counters; no partial frame enters the count | Status: PASS
- NFR-004 | Area: Evidence integrity | Target: thresholds are frozen before measurement, the report is bound to a full SHA, synthetic evidence leaves the full outcome UNMEASURED, and no PASS token is emitted | Validation: compare spec.md with the tasks.md results table and the report's decision block; run once without --tested-sha | Evidence: the report carries `binding`, `frozen`, `outcome_scope` and a decision derived from them; an UNBOUND report has `NO_ADOPTION_RECOMMENDATION` and no PASS token | Status: PASS
- NFR-005 | Area: Static quality | Target: the new script and SDD pass the repository's static gates and touch only the allowed paths | Validation: `python3 -m py_compile`, `ruff check --config scripts/quality/ruff.toml`, `python3 scripts/ci/validate_sdd.py`, `git status --short` | Evidence: all gates pass and only the script plus the three SDD files are added | Status: PASS

## Runtime feedback

- Measurement only: no runtime contour, deploy lane, acceptance probe or
  production flag is introduced. The harness never contacts a camera, relay
  or deployed service.
- The evidence run is bound to one host and one tested SHA. Different
  hardware, FFmpeg build, profiles or source makes a new baseline, not a
  contradiction of this one.
- The synthetic fixture and the absence of labeled events keep the full
  outcome UNMEASURED; no adoption is recommended from this report.
- Where `/proc` or ffmpeg is unavailable, the affected arm is `NOT EXECUTED`
  with the exact reason and no number is invented.
