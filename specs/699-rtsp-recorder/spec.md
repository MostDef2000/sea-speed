# Feature Specification: RTSP stream-copy recorder arm

- Feature: 699-rtsp-recorder
- Issue: #699
- Sub-issue: #699b
- Status: Source implementation

## Product outcome

Issue #699 added an opt-in recorder that preserves the original encoded HLS
objects to dacha. Issue #699b extends the same recorder with a second source
arm so a camera that is only reachable over RTSP can be recorded without
changing the analytics ingest, the HLS arm or the receiver contract.

The RTSP arm spawns FFmpeg as a grandchild inside the recorder's process group
and **stream-copies** the source (`-c:v copy`) into 2-second segmented
Matroska objects. There is no decode, no re-encode and no RTP packet capture.
Each object that is provably complete is atomically renamed and delivered
through the same bounded rsync operation as #699. The recorder remains disabled
by default; the selector
`SEA_SPEED_RECORDER_SOURCE_TYPE=hls|rtsp` defaults to `hls`.

## Identity contract (explicit)

What is preserved is the **ordered coded picture data** handed to FFmpeg: every
coded frame is written, in order, into the Matroska object. This is deliberately
NOT any of the following:

- not the RTP wire bytes — the arm does not capture packets; RTSP is consumed
  by FFmpeg and the RTP transport is reconstructed;
- not byte-identical files — Matroska framing, headers and timestamps differ
  from the camera's own container;
- not an exact 2-second cut — `-segment_time 2` is a target, segment boundaries
  follow keyframes, and `-break_non_keyframes 0` forbids cutting mid-GOP, so a
  sparse-keyframe source produces segments longer than 2 s. The 2 s value is
  not an acceptance identity.

There is no decode (`-map 0:v:0` video only, `-an -sn -dn`) and no re-encode
(`-c:v copy`).

## Transport caveat

- A credential-free private relay source is passed on argv and always uses
  `-rtsp_transport tcp` with bounded `-timeout`, `-analyzeduration` and
  `-probesize`.
- A credential-bearing direct Camera 1 source is passed through a fresh 0600
  ffconcat file in the private service tmp; its transport follows the existing
  `CAMERA1_RTSP_TRANSPORT` semantics (`udp` default, `tcp`, `automatic`). TCP
  is never forced for direct Camera 1 because the camera rejects TCP SETUP with
  `461 Unsupported Transport`.

## User scenarios

- SC-1: the recorder flag is unset or `0`; the worker starts exactly as before
  and no recorder child, FFmpeg process, HTTP request, rsync process or spool
  write occurs.
- SC-2: the selector is absent or `hls`; the #699 HLS arm behaves exactly as
  before.
- SC-3: the selector is `rtsp` against a credential-free relay; stream-copied
  Matroska objects appear at dacha and the HLS arm is not used.
- SC-4: a sparse-keyframe source produces longer segments; no segment is cut
  mid-GOP.
- SC-5: the receiver stalls; the bounded rsync attempt is abandoned, the object
  is discarded, a gap is counted and later objects resume.
- SC-6: the RTSP stream disconnects; FFmpeg is terminated and reaped, the
  uncertain tail is discarded, a gap and an outage interval are counted, and
  the arm reconnects after a bounded backoff.
- SC-7: the feature is disabled or a release is reverted; no media, API or
  receiver state requires repair.

## Requirements

- R-1 (selector): `SEA_SPEED_RECORDER_SOURCE_TYPE` accepts only `hls` or
  `rtsp`, default `hls`. `SEA_SPEED_RECORDER_ENABLED=0` returns before source
  validation, module import or any I/O.
- R-2 (HLS unchanged): the HLS arm still requires
  `SEA_SPEED_RECORDER_HLS_URL` as an explicit HTTP(S) URL and still rejects
  RTSP with no fallback.
- R-3 (RTSP source): the RTSP arm reads the existing `HLS_URL` variable, which
  must be an absolute `rtsp://` URL with a host. There is no fallback to another
  variable. Control characters (`< 0x20`, DEL) are rejected; a credential-bearing
  URL additionally rejects single quotes and backslashes that the ffconcat
  directive cannot carry safely.
- R-4 (stream copy): FFmpeg runs as a grandchild in the recorder process group
  with the exact argv: `-hide_banner -nostdin -nostats -loglevel error -xerror`
  + source + `-map 0:v:0 -an -sn -dn -c:v copy -map_metadata -1 -map_chapters -1
  -f segment -reference_stream v:0 -segment_time 2 -segment_format matroska
  -individual_header_trailer 1 -break_non_keyframes 0 -reset_timestamps 1
  SESSION/%09d/clip.mkv.part`.
- R-5 (completion witness): a segment is complete only when the NEXT numbered
  segment file appears (rollover) or FFmpeg exits cleanly on fixture EOF. On
  timeout, signal or error the uncertain tail is discarded.
- R-6 (bounded delivery): a complete object is atomically renamed to a unique
  `camera-session-sequence.mkv`, uploaded through the shared bounded rsync
  retry/backoff, and deleted after the attempt. Upload failure discards the
  local object and counts a gap.
- R-7 (fault containment): a monotonic 30-second no-completed-segment deadline
  terminates FFmpeg (bounded wait, then kill and reap), discards the tail,
  counts a gap and an outage interval, and reconnects with bounded backoff.
- R-8 (bounds): `RLIMIT_FSIZE` equal to the per-object cap is applied to the
  FFmpeg child only. Defaults are 64 MiB per file, at most 128 MiB of media
  per camera (two admitted slots) and a 12 GiB free-space floor. Missing
  parent directories are never auto-created: the spool base must already exist
  and numbered directories are created only below the per-session directory.
- R-9 (credential boundary): the credential-bearing URL is written to a fresh
  0600 ffconcat in the private service tmp (never the spool, never the ingest
  path) and removed on cleanup. FFmpeg stderr is discarded and never logged;
  only the safe scheme/host label is logged. The SSH key still comes only from
  the `LoadCredential` surface.
- R-10 (packaging): `worker/recorder_rtsp.py` enters the ubuntu-worker exact
  artifact inventories only (not vps/edge). Both Ubuntu env examples carry the
  identical selector block. No lockfile or requirements file changes.

## Gherkin acceptance examples

### Rule: disabled means no recorder I/O

```gherkin
Scenario: recorder disabled
  Given SEA_SPEED_RECORDER_ENABLED is unset or 0
  And SEA_SPEED_RECORDER_SOURCE_TYPE is hls or rtsp
  When the Ubuntu worker starts
  Then no recorder child process is spawned
  And no FFmpeg, HTTP or rsync process runs and no spool file is written
  And no recorder source URL is validated and no source module is imported
  And analytics ingest continues byte-identically to the previous release
```

### Rule: the HLS arm is unchanged

```gherkin
Scenario: selector defaults to hls
  Given SEA_SPEED_RECORDER_ENABLED is 1
  And SEA_SPEED_RECORDER_SOURCE_TYPE is unset
  And SEA_SPEED_RECORDER_HLS_URL is an explicit HTTP(S) playlist URL
  When the recorder evaluates its configuration
  Then it runs the existing #699 HLS arm
  And it never imports the RTSP module

Scenario: hls still rejects rtsp
  Given SEA_SPEED_RECORDER_ENABLED is 1
  And SEA_SPEED_RECORDER_SOURCE_TYPE is hls
  And SEA_SPEED_RECORDER_HLS_URL is an rtsp:// URL
  When the recorder evaluates its configuration
  Then it refuses to start recording
  And ingest remains unaffected
```

### Rule: RTSP success

```gherkin
Scenario: relay stream-copy delivered
  Given the selector is rtsp and HLS_URL is a credential-free rtsp relay
  When FFmpeg stream-copies the source through two segment rollovers
  Then the first object is finalised only after the next segment file appears
  And it is renamed to a unique camera-session-sequence.mkv
  And it is delivered through the shared bounded rsync operation and deleted
  And no decode and no re-encode occurs

Scenario: direct Camera 1 credential boundary
  Given HLS_URL is a credential-bearing direct Camera 1 rtsp URL
  And CAMERA1_RTSP_TRANSPORT is udp
  When the RTSP arm starts FFmpeg
  Then the URL is written to a fresh 0600 ffconcat file in the private temp
  And the URL does not appear in the FFmpeg argv or in any log line
  And the ffconcat carries rtsp_transport udp
```

### Rule: sparse keyframes are not cut

```gherkin
Scenario: no keyframe at the 2 second target
  Given the RTSP source has keyframes further apart than 2 seconds
  When FFmpeg reaches the segment_time target without a keyframe
  Then it does not cut mid-GOP
  And the resulting segment is longer than 2 seconds
  And the ordered coded picture data is preserved
```

### Rule: slow receiver produces a bounded gap

```gherkin
Scenario: receiver stops accepting transfers
  Given a complete object is ready for delivery
  When every bounded rsync attempt times out
  Then the recorder discards the local object after the bounded retry budget
  And it increments the gap counter and logs the discard
  And it continues recording later segments
```

### Rule: disconnect reconnects within bounds

```gherkin
Scenario: RTSP stream stalls
  Given FFmpeg has produced no completed segment for 30 seconds
  When the monotonic deadline expires
  Then the recorder terminates and reaps FFmpeg
  And it discards the uncertain tail
  And it counts a gap and one outage interval
  And it reconnects after a bounded backoff
```

### Rule: rollback leaves no repair work

```gherkin
Scenario: feature disabled or reverted
  Given the recorder is disabled by default
  When the selector is reverted or the release is rolled back
  Then no media, API, database or receiver state requires repair
  And the previous Ubuntu Worker release runs unchanged
```

## Acceptance criteria

- AC-001: With `SEA_SPEED_RECORDER_ENABLED` unset/0 the recorder returns before source validation, module import or any I/O; no FFmpeg, HTTP, rsync or spool activity occurs.
- AC-002: With the selector absent or `hls` the #699 HLS arm behaves exactly as before, including HTTP(S)-only source validation and RTSP rejection.
- AC-003: With the selector `rtsp` the arm reads the existing `HLS_URL`, requires an absolute `rtsp://` URL with a host, and rejects missing, relative, non-rtsp or control-character sources without any fallback.
- AC-004: The RTSP arm stream-copies ordered coded picture data into segmented Matroska with the pinned argv; there is no decode and no re-encode.
- AC-005: A segment is treated as complete only on next-segment rollover or clean FFmpeg EOF; a sparse-keyframe source is never cut mid-GOP and segments may exceed 2 s.
- AC-006: A completed object is atomically renamed to a unique `camera-session-sequence.mkv`, delivered through the shared bounded rsync operation and deleted; a failed upload discards it and counts a gap.
- AC-007: A 30-second no-completed-segment deadline terminates and reaps FFmpeg, discards the tail and counts a gap plus an outage interval before a bounded reconnect.
- AC-008: The credential-free relay uses TCP argv transport; the credential-bearing direct Camera 1 URL is placed only in a fresh 0600 ffconcat in private temp with `CAMERA1_RTSP_TRANSPORT` semantics; no credential reaches argv, logs or the spool.
- AC-009: `RLIMIT_FSIZE` bounds FFmpeg to the per-object cap only; defaults are 64 MiB per file, 128 MiB per camera and a 12 GiB free-space floor; missing parent directories are never auto-created.
- AC-010: `worker/recorder_rtsp.py` is in both ubuntu-worker exact-artifact inventories only; both Ubuntu env examples carry the identical selector block; no lockfile or requirements file changes.
- AC-011: The feature ships disabled by default and requires no runtime enablement in this scope; reverting the release or rolling back the Ubuntu Worker requires no media, API, database or receiver repair.

## Out of scope (explicit)

- RTP packet capture, RTSP packet-level identity and any custom RTSP client are
  out of scope. FFmpeg consumes RTSP.
- Decode, re-encode, transcode, frame extraction and any GPU dependency are out
  of scope.
- Exact 2-second segment duration and byte-identical files are NOT identity
  requirements (see the identity contract).
- Receiver-side retention remains dacha's responsibility, exactly as in #699.

## Runtime feedback

- Runtime acceptance: PENDING — the feature ships disabled by default and no
  production enablement is part of this change.
- Accepted production behavior while disabled: unchanged worker and unchanged
  HLS arm.
- Accepted behavior when enabled: stream-copied Matroska objects are delivered
  to dacha; receiver or stream faults produce bounded gaps and outages and
  never affect analytics ingest.
- Deferred work: field enablement, transport/relay observation and test-worker
  regression evidence, recorded in tasks.md as PENDING.

## NFR assessment

- NFR-001 | Area: OPERABILITY | Target: opt-in default OFF with a bounded hls or rtsp selector read once from the service environment | Validation: code inspection of RecorderConfig.from_env and the env examples | Evidence: recorder.py returns before source work when disabled, rejects any selector other than hls or rtsp, and both env examples default to 0 and hls | Status: PASS
- NFR-002 | Area: DATA | Target: preserve the ordered coded picture data with no decode and no re-encode | Validation: build_ffmpeg_args argv inspection plus test-worker oracle PENDING | Evidence: argv pins -c:v copy, video-only mapping and -map_metadata -1; test evidence is PENDING | Status: CONCERNS
- NFR-003 | Area: RELIABILITY | Target: an RTSP fault never blocks or crashes ingest and reconnects within bounded time | Validation: separate-process design plus lifecycle tests owned by the test worker PENDING | Evidence: the arm runs inside the existing separate recorder process; test evidence is PENDING | Status: CONCERNS
- NFR-004 | Area: SEC | Target: no credential in argv, logs or the spool; ffconcat is 0600 in private temp and removed on cleanup | Validation: code inspection of write_ffconcat, safe_media_input_label logging and stderr=DEVNULL | Evidence: direct credentials are confined to a mkstemp 0600 ffconcat and FFmpeg stderr is discarded | Status: PASS
- NFR-005 | Area: PERF | Target: bounded 64 MiB per file, 128 MiB per camera and a 12 GiB free-space floor with two admitted slots | Validation: code inspection of RLIMIT_FSIZE, media_max_bytes and the free-space check | Evidence: RLIMIT_FSIZE is applied only to the FFmpeg child; the monitor enforces the media cap and the spool floor | Status: PASS
- NFR-006 | Area: OBSERVABILITY | Target: start, segment success, discard, gap, outage, deadline and media-cap lines are bounded and credential-free | Validation: code inspection of the print sites | Evidence: every line uses a numeric counter or the safe scheme/host label; no stderr or URL is logged | Status: PASS
- NFR-007 | Area: OPS | Target: Ubuntu-only packaging and deployment with no lockfile or requirements change | Validation: the exact-artifact build and validate pair plus both env examples | Evidence: recorder_rtsp.py is added to the ubuntu-worker inventories only; no lockfile or requirements file is edited | Status: PASS
- NFR-008 | Area: BUS | Target: reverting the release or rolling back the worker leaves no repair work | Validation: default-OFF and rollback inspection | Evidence: the feature is inert while disabled and writes only its own session spool and dacha objects | Status: PASS
