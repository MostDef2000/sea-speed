# Implementation Plan: RTSP stream-copy recorder arm

- Feature: 699-rtsp-recorder
- Specification: specs/699-rtsp-recorder/spec.md
- Issue: #699
- Sub-issue: #699b
- Status: Source implementation

## Architecture

Issue #699b adds a second source arm to the existing opt-in recorder. The HLS
arm, the analytics main loop, the media reader, the API and the VPS contour are
unchanged.

1. **`worker/recorder.py` (selector + shared delivery).** `RecorderConfig`
   gains `source_type` (`hls` default, `rtsp`) read once from
   `SEA_SPEED_RECORDER_SOURCE_TYPE`, and `rtsp_url`. The disabled path still
   returns before any source validation or module import. The HLS branch keeps
   the #699 `SEA_SPEED_RECORDER_HLS_URL` HTTP(S)-only validation; the RTSP
   branch reads the existing `HLS_URL` and stores it for the lazy arm. The
   bounded rsync retry/backoff previously inlined in `HlsRecorder.upload` is
   extracted to a module-level `bounded_upload(config, path)` and reused by
   both arms. `main()` dispatches to the RTSP arm only when enabled and
   selected; the lazy loader registers the running script module so
   `recorder_rtsp` imports the same exception classes instead of re-executing
   the file.
2. **`worker/recorder_rtsp.py` (new).** `RtspRecorder` validates the source,
   resolves transport, builds the exact FFmpeg argv, spawns FFmpeg as a
   grandchild in the recorder process group, monitors numbered segment
   directories, and delivers completed objects through `bounded_upload`.
   - Source: credential-free relay on argv with `-rtsp_transport tcp`; a
     credential-bearing direct Camera 1 URL is written to a fresh 0600
     ffconcat in the private service tmp with the `CAMERA1_RTSP_TRANSPORT`
     transport (`udp` default, never forced to TCP).
   - Output: `SESSION/%09d/clip.mkv.part` with `-c:v copy` segmented Matroska,
     `-segment_time 2`, `-individual_header_trailer 1`,
     `-break_non_keyframes 0`, `-reset_timestamps 1`, `-reference_stream v:0`.
   - Completion: the NEXT numbered segment file appearing is the rollover
     witness; a clean FFmpeg exit witnesses the final fixture segment. Only
     then is the object renamed to a unique `camera-session-sequence.mkv`.
   - Faults: a monotonic 30-second no-completed-segment deadline, a bounded
     media cap or a nonzero exit terminates and reaps FFmpeg, discards the
     uncertain tail, counts a gap and an outage interval, then reconnects with
     bounded backoff. `RLIMIT_FSIZE` is applied to the FFmpeg child only.
   - Spool: the base spool directory must already exist (fail closed, no
     parent auto-create). The recorder creates one per-session directory and
     exactly two numbered directories ahead of the writer.
3. **Env examples and packaging.** Both Ubuntu env examples receive the same
   selector line and RTSP note (no new URL, key or tuning knob). The new
   module is added to the ubuntu-worker inventories in both quality scripts
   only; no lockfile or requirements file changes, because FFmpeg is already
   installed.

The receiver-side 500 GiB / 15-day quota and pruner remain dacha's
responsibility, exactly as in #699.

## Decisions

- D-699B-1 — FFmpeg stream-copy, not PyAV and not RTP capture: the required
  identity is ordered coded picture data; `-c:v copy` preserves it with no new
  dependency, decode or re-encode.
- D-699B-2 — FFmpeg as a grandchild in the recorder process group: the
  entrypoint already spawns the recorder with `start_new_session=True`, so
  `killpg` reaches FFmpeg; no new lifecycle wiring is needed.
- D-699B-3 — ffconcat for credential-bearing direct Camera 1 only: the camera
  password never enters `/proc/<pid>/cmdline`; a fresh 0600 file in private
  temp is written per attempt and removed on cleanup. Relay inputs are
  credential-free and go on argv.
- D-699B-4 — transport is source-derived: relay is always TCP; direct Camera 1
  follows `CAMERA1_RTSP_TRANSPORT` because the camera rejects TCP SETUP (`461
  Unsupported Transport`).
- D-699B-5 — rollover as the completion witness: Matroska with an individual
  trailer is only trusted when the next segment starts or FFmpeg exits
  cleanly; anything else is an uncertain tail and is discarded.
- D-699B-6 — reuse the bounded delivery path: `bounded_upload` keeps one
  retry/backoff/rsync contract for both arms and one delete-after-attempt
  spool discipline.
- D-699B-7 — structural bounds: two 64 MiB slots per camera, a 12 GiB floor
  and `RLIMIT_FSIZE` on FFmpeg only; missing parent directories fail closed.

## Affected contours

- Contour: Ubuntu Worker/relay.
- VPS deployment: NOT APPLICABLE — no `api/**` or frontend change.
- Ubuntu worker/relay update: REQUIRED — new `worker/recorder_rtsp.py`,
  selector and shared upload in `worker/recorder.py`, both Ubuntu env examples
  and the two quality inventories change. The recorder remains default OFF.
- Windows worker update: NOT APPLICABLE — retired from production.
- Production safety envelope: no new route, API, database, public exposure or
  runtime authority. When enabled the RTSP arm reads an authorized source and
  writes bounded original stream-copy objects to the provisioned dacha
  destination with the restricted key.

## Validation

Observed outputs are recorded in `specs/699-rtsp-recorder/tasks.md` under
`## Evidence (observed only)`. Static checks, SDD validation and the
exact-artifact build/validate pair are run on this working tree; the dedicated
test-worker oracle is PENDING and is not claimed here.

## Runtime feedback

- Pre-change behavior: the recorder had only the #699 HLS arm.
- Expected post-deploy behavior while disabled: unchanged worker and unchanged
  HLS arm; the Ubuntu artifact gains an unimported-by-default module.
- Expected behavior when the selector is `rtsp`: stream-copied Matroska
  objects delivered to dacha; receiver or stream faults yield bounded gaps and
  outages; analytics ingest continues.
- Runtime acceptance: PENDING — no production enablement is part of this
  change.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the next numbered directory is created at rollover before upload, the session base must exist, and the 30-second deadline plus nonzero-exit handling terminate and reap FFmpeg with bounded reconnect | Validation: test-worker fault-path oracle PENDING plus code inspection | Residual risk: a receiver slower than the directory look-ahead can force a bounded outage interval | Owner: worker implementation | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: `-c:v copy`, video-only mapping, `-map_metadata -1`, no decode and no re-encode; completion is witnessed by rollover or clean EOF | Validation: test-worker oracle PENDING plus argv inspection | Residual risk: Matroska framing differs from the camera container by design and is not byte-identical | Owner: worker implementation | Status: MITIGATED
- RISK-003 | Category: SEC | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: direct credentials only in a fresh 0600 ffconcat in private temp; FFmpeg stderr discarded; only the safe scheme and host label logged; single quotes and backslashes rejected | Validation: code inspection plus credential-path tests PENDING | Residual risk: a malicious authorized source could still serve non-media bytes | Owner: worker implementation | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: `RLIMIT_FSIZE` on FFmpeg only, two 64 MiB slots per camera, 12 GiB free-space floor and delete-after-attempt | Validation: code inspection plus bounds tests PENDING | Residual risk: many small objects can create rsync churn | Owner: worker implementation | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: default OFF, explicit selector, source-derived transport and no production enablement in this scope | Validation: env examples default to 0 and hls; operator enablement remains a separate decision | Residual risk: an operator could enable recording without confirming source authorization or storage policy | Owner: operator enablement | Status: ACCEPTED
- RISK-006 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: `-break_non_keyframes 0` forbids mid-GOP cuts and the spec explicitly disclaims exact 2-second identity | Validation: sparse-keyframe oracle PENDING plus argv inspection | Residual risk: sparse-keyframe sources produce segments longer than 2 s by design | Owner: worker implementation | Status: MITIGATED
- RISK-007 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the monotonic deadline, nonzero-exit handling and bounded backoff convert an outrun or disconnect into a counted gap and outage rather than an unbounded hang | Validation: fault-path oracle PENDING | Residual risk: a persistent stream failure yields repeated bounded outage intervals and no media | Owner: worker implementation | Status: MITIGATED

## Test design

- TEST-699B-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: test-worker disabled zero-I/O oracle PENDING (no FFmpeg, HTTP, rsync or spool activity; selector not validated)
- TEST-699B-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: test-worker HLS-unchanged oracle PENDING (default selector runs HLS; RTSP source still rejected on the HLS arm)
- TEST-699B-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: test-worker RTSP source validation oracle PENDING (missing, relative, non-rtsp and control-character sources rejected; no fallback)
- TEST-699B-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: test-worker stream-copy argv and delivery oracle PENDING
- TEST-699B-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: test-worker rollover and sparse-keyframe oracle PENDING
- TEST-699B-006 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: test-worker atomic rename, bounded upload and delete oracle PENDING
- TEST-699B-007 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: test-worker deadline, terminate and reconnect oracle PENDING
- TEST-699B-008 | Covers: AC-008 | Level: unit | Priority: P0 | Evidence: test-worker transport and credential-boundary oracle PENDING (relay TCP argv; direct 0600 ffconcat; no credential in argv or logs)
- TEST-699B-009 | Covers: AC-009 | Level: integration | Priority: P1 | Evidence: test-worker bounds oracle PENDING (RLIMIT_FSIZE child-only, 64 MiB, 128 MiB, 12 GiB floor, no parent auto-create)
- TEST-699B-010 | Covers: AC-010 | Level: integration | Priority: P0 | Evidence: test-worker packaging oracle PENDING plus the exact-artifact build and validate pair
- TEST-699B-011 | Covers: AC-011 | Level: runtime-manual | Priority: P1 | Evidence: default-OFF inspection and rollback review; runtime acceptance PENDING by design

## Correct-course check

- Trigger: NONE
- Issue impact: Issue #699 defines the recorder; #699b is the agreed RTSP extension, so no issue rewrite is required.
- Specification impact: New `specs/699-rtsp-recorder/spec.md` authored for this scope.
- Plan impact: This plan; no scope change after admission.
- Tasks impact: Tasks T001-T008 cover the selector, the RTSP arm, env examples, packaging, SDD and verification.
- Authorization impact: Bounded Ubuntu worker and SDD scope only; no new production authority and no runtime enablement.
- Follow-up: Dedicated test-worker regression coverage and CI/merge evidence remain PENDING; field enablement and relay/transport observation are operational follow-up.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: working tree and branch unchanged | Retry: N/A | Rollback: N/A | Evidence: work order for Issue #699b on branch agent/wave7-699b-rtsp-recorder; allowed paths are worker/recorder_rtsp.py, worker/recorder.py, both Ubuntu env examples, the two quality scripts and specs/699-rtsp-recorder/**; base_sha c689947 verified as branch HEAD
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous Ubuntu Worker release remains active | Retry: N/A | Rollback: N/A | Evidence: py_compile, ruff, validate_sdd and the exact-artifact build plus validate pair run before publication on the changed tree
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: the exact-release install fails closed before activation and the previous release keeps running | Retry: Re-dispatch the Ubuntu deploy workflow on the same merged main SHA | Rollback: roll the Ubuntu Worker back to the previous complete release with rollback-exact.sh | Evidence: both Ubuntu env examples and the ubuntu-worker exact artifact change; the existing deploy-authorized exact-release transaction is unchanged
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release remains active | Retry: Re-run the same verification after fixing the failing gate | Rollback: N/A | Evidence: existing post-deploy worker health and runtime-progression gates apply unchanged; local static, SDD and artifact validation recorded in tasks.md
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker state store and dacha destination | Retry: N/A | Rollback: N/A | Evidence: no schema, database or API state change; the RTSP arm writes only its bounded session spool and dacha objects; default OFF means no writes at deploy time
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scratch only under /tmp/opencode with no repository residue | Retry: N/A | Rollback: N/A | Evidence: progress and scratch artifacts live under /tmp/opencode/699b-rtsp-recorder; no progress, cache or generated file enters the repository
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial but no runtime effect | Retry: Re-run the observed command and append output | Rollback: N/A | Evidence: observed py_compile, ruff, validate_sdd, exact-artifact build and validate plus git status and diff stat recorded in tasks.md; test-worker evidence PENDING
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: N/A | Rollback: revert the bounded PR or roll the Ubuntu Worker back to the previous complete release; with the recorder default OFF the previous release impact is none | Evidence: diff limited to the allowed worker, deploy, quality and spec paths; disabled flag short-circuits before source validation and no media path changes
