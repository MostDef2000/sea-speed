# Plan: #703 — Persistent decoder CPU baseline + keyframe/Range prototype

- Issue: #703
- Specification: `specs/703-decoder-grab-baseline/spec.md`

## Architecture

One stdlib-only CLI, `scripts/worker/decoder_grab_baseline.py`, with no runtime,
deploy or CI wiring. It owns a disposable local HLS source and origin and
measures two sequential arms against the same encoded timeline.

Lifecycle:

1. Parse the frozen CLI. There is no `--url`/`--target` option; `--source-dir`
   must be a local directory containing `source.m3u8` and `seg*.ts`. The only
   network targets are the harness's own ephemeral `127.0.0.1` origin.
2. Resolve `ffmpeg` from `--ffmpeg` or `PATH` and record its build string. Read
   runtime identity: platform, Python, logical CPUs, CPU model, cgroup CPU
   quota (`/sys/fs/cgroup/cpu.max` or v1 equivalent) and software decode mode.
3. If no `--source-dir` is supplied, generate one 210 s MPEG-TS HLS timeline
   with libx264: 1920 × 1080, 10 FPS, 2500 kbps, 2 s GOP, keyframe-aligned 2 s
   segments, synthetic `testsrc2` moving pattern. Parse the source playlist
   into an ordered segment catalog and record the source fingerprint (sha256
   of the playlist plus every segment payload).
4. Start a `ThreadingHTTPServer` on `127.0.0.1:0`. It serves a sliding live
   playlist (6 segments) and Range-capable segments. Segment availability is
   paced by a per-arm epoch: segment *i* is published at `epoch + start_i`.
   A request for a listed segment blocks at most 10 s; an unpublished index is
   404. The origin is shut down in a `with` block on every path.
5. Baseline arm, for each requested profile (`water` 5 FPS, `road` 10 FPS):
   reset the epoch, spawn ffmpeg with the production HLS reader flags
   (`-i URL -vf fps=N,scale=1920:1080 -pix_fmt bgr24 -f rawvideo pipe:1`), and
   start a consumer thread that drains complete 6 220 800-byte frames via
   `os.readv`. Sleep 10 s warm-up, then run three 60 s windows. Per window:
   sample `/proc/<decoder>/stat` and `/proc/<self>/stat`, count frames and
   frame-arrival gaps, report delivered FPS, yield, misses and stalls.
6. Prototype arm, for each profile: reset the epoch, poll the playlist every
   1 s. When the latest complete sequence advances, count missed opportunities
   (advance > 1), request
   `Range: bytes=0-511999`, validate status 206 + `Content-Range` + lengths,
   write the capped bytes to a short-lived file and decode one keyframe with a
   fresh ffmpeg (`-skip_frame nokey`, one frame, profile scale/FPS). Child CPU
   comes from `RUSAGE_CHILDREN` deltas; latency is poll start → complete frame.
   These observations are bucketed into the same three 60 s windows.
7. Compare arms per profile: prototype total arm CPU ÷ baseline total arm CPU,
   frame-ready p95, prototype failure count. Build the JSON report (sorted
   keys, fixed float precision) with `binding`, `frozen`, `source.runtime`,
   `arms`, `comparison`, `outcome_scope`, `decision`, `not_executed` and
   `duration_seconds`.
8. `finally`: terminate→wait→kill the decoder, join the consumer, stop the
   origin, remove generated sources, write the report. A crashed decoder or a
   failed generation is recorded as `NOT EXECUTED`/`FAILED` with its exit code
   and stderr tail; no number is fabricated.

Determinism and pacing:

- The report structure is deterministic; measured values are, of course,
  host-specific. The CLI defaults reproduce the frozen workload.
- The baseline is wall-clock-paced by segment publication, not an `-re` flag
  and not a file read. The consumer always drains, so the decoder is never
  blocked on a full stdout pipe. That is what distinguishes this from an
  unpaced file-decode microbenchmark.
- Both arms use HLS. The comparison is HLS-only; no RTSP arm or production
  relay is introduced.

Metric derivation:

- Decoder CPU s/s = Δutime+Δstime (ticks ÷ `SC_CLK_TCK`) ÷ window wall seconds.
- Pipeline CPU s/s = the same for the harness process over the same window.
- Arm total = decoder + pipeline for the baseline; child CPU + pipeline for
  the prototype. Prototype child CPU already includes process startup.
- Frame yield = delivered ÷ (profile FPS × wall seconds); a window below 0.90
  invalidates the baseline measurement.
- Stalls are frame-to-frame gaps above 3.5 s; misses are
  max(0, round(expected − delivered)).
- Range success requires 206, `bytes 0-<end>/<total>` with the requested end,
  matching Content-Length and body length ≤ 500 KiB. A 200 full-body answer is
  recorded as a failure and still counted, never discarded.
- Frame-ready latency = poll start → complete first keyframe. Detection
  latency is UNMEASURED.

Report/decision shape:

- `binding` = BOUND only for a full 40-hex `--tested-sha`.
- `measurement` = GREEN only when both arms produced measured, non-empty
  windows and the baseline frame-yield floor holds; otherwise RED.
- `recommendation` = `NO_ADOPTION_RECOMMENDATION` whenever the report is
  UNBOUND, the measurement is RED, or `full_outcome` is UNMEASURED. Only an
  approved representative source with labeled events can produce
  `full_outcome: MEASURED` and an adoption-eligible recommendation.
- No `PASS` token is emitted anywhere; a green-looking report without a bound
  SHA must be impossible.

## Decisions

- **Disposable origin, no target URL.** A target option would invite
  production load and make the number meaningless. Owning the origin keeps the
  workload hermetic and safe.
- **Wall-clock-paced live HLS, drained consumer.** A file decode runs as fast
  as the disk and a full stdout pipe turns the number into backpressure; both
  would mislabel live-load CPU. Segment publication pacing and a draining
  consumer preserve the production shape.
- **Production reader flags verbatim.** The baseline command is exactly the
  `start_ffmpeg()` construction in `worker/worker_media.py`, so the measured
  decoder is the shipped one. Only stderr is drained by a harness thread (the
  production reader also exposes stderr; draining it prevents a child block).
- **Profiles are separate cells.** 5 FPS water and 10 FPS road have different
  decode costs; a silent average would hide the difference. Never run both
  arms concurrently.
- **Decoder CPU is separated from the pipeline.** Sampling and draining have a
  real cost; reporting only the decoder would understate the whole pipeline,
  and reporting only the total would hide where it goes.
- **Range is validated strictly.** A 200 body is not a Range success, a
  malformed `Content-Range` is a failure, and capped bytes must decode a
  keyframe. Every such failure stays in the denominator.
- **Process startup is charged to the prototype.** A grab-latest design that
  spawns ffmpeg per segment must pay for those spawns; excluding them would
  flatter the prototype.
- **Synthetic evidence never recommends adoption.** The fixture tests
  accounting and Range mechanics; representativeness and detection need an
  approved source and labeled events. Those cells are UNMEASURED.
- **Measurement only.** No production flag, reader replacement, relay or
  transport change ships from this issue.
- **No test edits here.** A separate test worker owns `tests/**`; this plan
  records the test design and the pure-helper oracles it should pin. The
  harness lives in `scripts/worker/` (not `scripts/quality/` or `scripts/ci/`)
  and is not in unittest discovery.

## Affected contours

- Repository: `scripts/worker/decoder_grab_baseline.py` (new) and the SDD trio
  under `specs/703-decoder-grab-baseline/` (new).
- VPS: NONE — no `api/**`, `frontend/**`, `deploy/**` or `contracts/**` change.
- Ubuntu worker/relay: NONE — no `worker/**` change; the harness only mirrors
  the existing reader flags.
- Windows worker/AI: NONE.
- Public interfaces: NONE — no endpoint, schema or contract change.
- CI interfaces: NONE — no workflow, gate or artifact upload.
- Tests: NONE in this scope — `tests/**` belongs to the separate test worker.
- Change-control impact: NONE (top-level `scripts/worker/` is not a
  CONTROL_PLANE pattern; the harness is a developer tool).
- Explicitly unchanged: production source, deploy/workflow files, lockfiles,
  `scripts/quality/**`, `scripts/ci/**` and every existing test.

## Validation

- Static: `python3 -m py_compile scripts/worker/decoder_grab_baseline.py`,
  `ruff check --config scripts/quality/ruff.toml scripts/worker/decoder_grab_baseline.py`,
  `python3 scripts/ci/validate_sdd.py`, and `git status --short` showing only
  the four allowed new paths.
- Isolation oracle: `--help` exposes no host/URL option; the only outbound
  connections target the origin's ephemeral loopback port.
- Lifecycle oracle: a short investigation run (non-frozen overrides) completes
  both arms, writes the report, and leaves no listener or decoder process.
- Frozen-run oracle: a 210 s source, 10 s warm-up, 3 × 60 s windows, both
  profiles, both arms; the tasks.md table is a transcription of that report.
- Negative oracles: a run without `--tested-sha` reports UNBOUND and
  `NO_ADOPTION_RECOMMENDATION`; a prototype range rejection or zero usable
  observation yields RED and no adoption recommendation.
- Honest-limit oracle: source-class synthetic leaves `full_outcome` UNMEASURED
  even when all performance thresholds pass.
- Test ownership: the test worker's `tests/**` cases should pin the pure
  helpers — `binding_for_sha` rejects short/invalid SHAs, `evaluate_range_response`
  rejects 200 and malformed/mismatched Content-Range, `percentile` is
  nearest-rank, `parse_playlist` reads media sequence/URIs/durations, and
  `build_decision` never emits PASS and never recommends adoption for an
  UNBOUND/UNMEASURED report.

## Runtime feedback

- On-demand measurement tool: no runtime contour, deploy lane or acceptance
  probe against a deployed service.
- The evidence run is bound to one tested SHA and one host/FFmpeg build; a
  different host, build, profile or source is a new baseline, not a
  contradiction.
- The synthetic fixture and the absence of labeled events keep the full
  outcome UNMEASURED; the report says so explicitly and recommends no
  adoption.
- Raw output stays outside git (`/tmp/opencode/703-baseline/`).

## Risk profile

- Risk profile: NOT REQUIRED
- Justification: the change adds an on-demand stdlib-only developer tool plus
  SDD text under `scripts/` and `specs/`. It touches no production runtime,
  deploy path, workflow, schema, secret or migration, adds no dependency, and
  binds only loopback. No security, schema, destructive or MIXED trigger
  applies.

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `binding_for_sha` returns BOUND only for a full 40-hex SHA and UNBOUND otherwise; the option parser exposes no URL/host option; the origin is created on port 0 and stopped in a context manager
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: the `FROZEN` table and CLI defaults agree on 210 s source, 10 s warm-up, 3 × 60 s windows, 1 s polling, 500 KiB Range, 5/10 FPS profiles, and the report echoes `frozen`; a frozen-run report records tested SHA, runtime identity and source fingerprint
- TEST-003 | Covers: AC-003 | Level: runtime-manual | Priority: P0 | Evidence: a frozen run reports per-window decoder CPU s/s, pipeline CPU s/s, delivered frames, yield, stalls and misses for both profiles; the decoder command equals the production reader flags; the consumer count matches complete frames only
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `evaluate_range_response` rejects status 200, missing/malformed Content-Range, span/total mismatch, Content-Length mismatch and short bodies; `parse_range_header` handles start-end, open-end and suffix forms; a capped non-keyframe payload yields `decode_ok: false`
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: `build_decision` returns UNBOUND + `NO_ADOPTION_RECOMMENDATION` for a missing SHA, RED for zero observations, and never emits the token `PASS`; a synthetic source leaves `full_outcome` UNMEASURED even with all thresholds met
- TEST-006 | Covers: AC-006 | Level: runtime-manual | Priority: P1 | Evidence: the four static commands pass and `git status --short` contains only the script and the three SDD files

## Correct-course check

- Trigger: NONE
- Issue impact: none — the scope matches issue #703 as admitted: a persistent
  decoder CPU baseline harness, a keyframe/Range prototype and its SDD.
- Specification impact: none — the frozen workload and thresholds are stated
  before measurement; no production or test file changes.
- Plan impact: none — the implementation follows the admitted
  disposable-origin, paced-HLS, separated-CPU, strict-Range design.
- Tasks impact: none — the harness, SDD and the evidence table are delivered;
  PR lifecycle, CI and test-worker coverage remain with the orchestrator and
  the test worker.
- Authorization impact: NONE — bounded worker work order on branch
  `agent/wave6-703-702-687`; the orchestrator owns Git lifecycle, PR admission
  and CI evidence.
- Follow-up: if the frozen comparison fails or a cell is UNMEASURED, the
  result is recorded as-is and no adoption is recommended; validating against
  an approved representative source with labeled events would be a separate,
  explicitly authorized measurement.
