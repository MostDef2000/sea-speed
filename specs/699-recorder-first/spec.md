# Feature Specification: Opt-in recorder of original encoded HLS segments

- Feature: 699-recorder-first
- Issue: #699
- Status: Source implementation

## Product outcome

The operator needs the original camera HLS stream recorded for later evidence
without changing what the analytics worker already decodes. Issue #699 adds an
**opt-in**, independent recorder at the Ubuntu Worker boundary: it fetches every
playlist-referenced media segment and the `#EXT-X-MAP` init object directly over
HTTP(S), keeps the ORIGINAL ENCODED BYTES, and delivers each completed object to
the provisioned dacha destination. There is no ffmpeg remux, no decoded frame
and no RTSP packet capture.

The recorder is disabled by default. It runs as one optional child process per
enabled camera, reads its SSH key only from the systemd `LoadCredential`
surface, and is isolated from ingest: it shares no media pipe, never waits for
readiness and never backpressures `worker.main()`. A recorder failure — missing
URL/key, spool exhaustion, hung receiver — affects recording only.

## User scenarios

- SC-1: the recorder flag is unset or `0`; the worker starts exactly as before
  and no recorder child, HTTP request, rsync process or spool write occurs.
- SC-2: the recorder is enabled against an authorized HTTP(S) playlist; every
  completed segment and init object arrives at dacha byte-identical to the
  source object.
- SC-3: the receiver stops accepting transfers; the recorder retries only
  within bounded time, discards the object, counts a gap, and the analytics
  worker keeps reading and publishing frames.
- SC-4: the receiver-side quota/pruner (500 GiB retained, 15 days) removes old
  recordings; the worker's local spool stays small because each object is
  deleted after its upload attempt.
- SC-5: an operator configures an RTSP source; the recorder refuses the
  configuration (no RTSP fallback) while ingest is unaffected.
- SC-6: a playlist redirect points at another origin; the recorder refuses the
  redirect instead of forwarding credentials.

## Requirements

- R-1 (opt-in): `SEA_SPEED_RECORDER_ENABLED` accepts only `0` or `1`, default
  `0`. Disabled means no child process and zero recorder I/O.
- R-2 (explicit HTTP(S) source): when enabled, `SEA_SPEED_RECORDER_HLS_URL` is
  required and must be an explicit `http://` or `https://` URL. RTSP is
  rejected; there is no RTSP fallback and no ffmpeg remux.
- R-3 (original bytes): the recorder fetches playlist-referenced media segment
  objects and the `#EXT-X-MAP` init object verbatim. It preserves relative URI
  resolution against the final playlist URL and never decodes, remuxes or
  rewrites the payload.
- R-4 (redirect/auth boundary): same-origin redirects are followed; a redirect
  to a different origin is refused. Basic auth follows the existing
  `media_basic_auth_for_input` semantics and is attached only to the configured
  origin.
- R-5 (bounded acquisition): reads are chunked with a per-object deadline, a
  64 MiB per-object cap and a 12 GiB free-space stop floor; objects are never
  buffered whole in memory.
- R-6 (bounded delivery): each completed object is rsynced through the
  provisioned restricted `rrsync` key with bounded retries/backoff. Prolonged
  failure discards the object, counts a gap and resumes later; gaps are also
  counted when the playlist media sequence advances past uncaptured segments.
- R-7 (lifecycle isolation): the Ubuntu entrypoint spawns at most one recorder
  child per enabled camera without readiness wait or media IPC. Spawn failure
  disables recording only. Stop terminates the child and its rsync descendant.
- R-8 (credential boundary): the key is read from
  `$CREDENTIALS_DIRECTORY/recorder_ed25519` or the documented
  `/run/credentials/recorder_ed25519`; it is never read from `/home` and never
  embedded, logged or committed.
- R-9 (packaging): `worker/recorder.py` is part of the Ubuntu Worker exact
  artifact inventory only (not vps/edge). Both Ubuntu env examples carry the
  same opt-in block; both service templates keep the `LoadCredential` mount.
- R-10 (receiver boundary): dacha enforces its own 500 GiB / 15-day quota and
  pruner. The worker records raw objects and does not implement receiver-side
  retention.

## Gherkin acceptance examples

### Rule: disabled means no recorder I/O

```gherkin
Scenario: recorder disabled
  Given SEA_SPEED_RECORDER_ENABLED is unset or 0
  When the Ubuntu worker starts
  Then no recorder child process is spawned
  And no playlist, segment or init HTTP request is made
  And no rsync process runs and no spool file is written
  And analytics ingest continues byte-identically to the previous release

Scenario: malformed flag
  Given SEA_SPEED_RECORDER_ENABLED is "true" or "yes"
  When the recorder child evaluates its configuration
  Then it refuses the configuration
  And recording stays disabled without affecting ingest
```

### Rule: enabled delivers original encoded objects

```gherkin
Scenario: segment and init object delivered verbatim
  Given the recorder is enabled against an authorized HTTP(S) playlist
  And the playlist references init.mp4 through EXT-X-MAP and seg0.ts relatively
  When the recorder completes the objects
  Then init.mp4 and seg0.ts arrive at the dacha destination byte-identical to the source objects
  And their SHA-256 digests match the source bytes
```

### Rule: hung receiver produces a bounded gap

```gherkin
Scenario: receiver stops accepting transfers
  Given the recorder is enabled and an object is complete in the local spool
  When every bounded rsync attempt times out
  Then the recorder discards the object after the bounded retry budget
  And it increments the gap counter and logs the discard
  And it continues capturing later playlist objects
  And the analytics worker ingest is never backpressured
```

### Rule: receiver quota and pruner are receiver-side

```gherkin
Scenario: dacha retention
  Given the recorder has delivered recordings to dacha
  When the receiver reaches its 500 GiB / 15-day policy
  Then the receiver-side pruner removes old recordings
  And the worker does not implement or depend on that retention policy
```

### Rule: no RTSP fallback

```gherkin
Scenario: RTSP source configured
  Given SEA_SPEED_RECORDER_ENABLED is 1
  And SEA_SPEED_RECORDER_HLS_URL is an rtsp:// URL
  When the recorder evaluates its configuration
  Then it refuses to start recording
  And ingest remains unaffected
```

### Rule: same-origin redirects only

```gherkin
Scenario: cross-origin redirect
  Given an authorized HTTP(S) playlist at origin A
  When a playlist or object response redirects to origin B
  Then the recorder refuses the redirect
  And it does not forward the configured basic-auth credential to origin B
```

## Acceptance criteria

- AC-001: With `SEA_SPEED_RECORDER_ENABLED` unset/0 no recorder child is spawned and no recorder HTTP, rsync or spool I/O occurs; ingest behavior is unchanged.
- AC-002: With the recorder enabled, every completed media segment and `#EXT-X-MAP` init object is delivered byte-identical (matching SHA-256) to the dacha destination.
- AC-003: Relative playlist URIs resolve against the final playlist URL, same-origin redirects are followed, cross-origin redirects are refused, and RTSP sources are rejected with no fallback.
- AC-004: Object acquisition is chunked with a per-object deadline, a 64 MiB per-object cap and a 12 GiB free-space floor; no whole object is buffered in memory.
- AC-005: A hung receiver causes only bounded retries/backoff, one discarded object and a counted gap; later capture resumes and ingest is not backpressured.
- AC-006: The entrypoint spawns one recorder child per enabled camera without waiting, a spawn failure disables recording only, stop terminates the child and its rsync descendant, and the key is read only from the LoadCredential surface.
- AC-007: `worker/recorder.py` appears in the ubuntu-worker exact-artifact build and validation inventories only, and both Ubuntu env examples carry the identical opt-in block while both service templates keep `LoadCredential`.
- AC-008: Static verification is observed and dedicated regression coverage exists in `tests/test_699_recorder.py` and `tests/test_699_recorder_lifecycle.py`; the observed targeted run is 49 passed / 55 subtests.

## Out of scope (explicit)

- RTSP packet capture and RTSP ingest are **out of scope**. The recorder only
  consumes an explicit authorized HTTP(S) HLS playlist.
- ffmpeg remux, transcode, decode or frame extraction is **out of scope**. The
  recorder only stores the original encoded HLS objects.
- Playlist rewriting, encryption-key handling, receiver-side retention and
  receiver-side transcoding are out of scope.

## Runtime feedback

- Runtime acceptance: PENDING — the feature ships disabled by default; no
  production enablement is part of this change.
- Accepted production behavior while disabled: unchanged.
- Accepted behavior when enabled: raw HLS objects recorded; recording failures
  produce bounded gaps and never affect analytics ingest.
- Regression coverage: `tests/test_699_recorder.py` (byte identity, disabled
  zero-I/O, source rejection, bounds, credentials) and
  `tests/test_699_recorder_lifecycle.py` (entrypoint lifecycle, packaging,
  scope guard); the targeted run observed 49 passed / 55 subtests.
- Deferred work: field enablement and dacha quota/pruner observation after a
  lane-A Ubuntu deploy.

## NFR assessment

- NFR-001 | Area: OPERABILITY | Target: opt-in default OFF; `SEA_SPEED_RECORDER_ENABLED` accepts only 0/1; every threshold bounded and read once | Validation: code inspection of RecorderConfig and entrypoint `_recorder_enabled` | Evidence: `worker/recorder.py` config clamps; entrypoint spawns only on literal `1`; both env examples default to 0 | Status: PASS
- NFR-002 | Area: DATA | Target: delivered objects are byte-identical to source segment/init objects | Validation: `tests/test_699_recorder.py::RecorderByteIdentityOracleTests` byte-identity oracle plus scratch smoke | Evidence: observed targeted run 49 passed / 55 subtests; byte-identity oracle compares SHA-256 and length of delivered init + segments; scratch smoke also matched `SEG0`/`SEG1`/`INIT` | Status: PASS
- NFR-003 | Area: RELIABILITY | Target: recorder failure never blocks or crashes ingest; spawn failure disables recording only | Validation: `tests/test_699_recorder_lifecycle.py::RecorderEntrypointLifecycleTests` plus code inspection | Evidence: observed targeted run 49 passed / 55 subtests covers spawn, rc 143 stop, spawn-failure isolation and process-group termination; disabled/malformed paths in `RecorderDisabledZeroIoTests` | Status: PASS
- NFR-004 | Area: SEC | Target: key only from `$CREDENTIALS_DIRECTORY`/`/run/credentials`; no credential logging, embedding or `/home` read; cross-origin redirect refused | Validation: `RecorderCredentialTests`, `RecorderSourceRejectionTests` and scratch redirect/auth check | Evidence: observed targeted run 49 passed / 55 subtests; credential tests pin the two allowed paths and the no-`/home` source scan; cross-origin redirect test asserts origin B receives zero requests | Status: PASS
- NFR-005 | Area: PERF | Target: bounded 64 MiB per object and 12 GiB free-space floor; one object at a time; spool deleted after each upload | Validation: `RecorderBoundsTests` plus code inspection | Evidence: observed targeted run 49 passed / 55 subtests covers pinned bounds, content-length and streamed caps, chunked reads, stalled-body deadline, free-space floor, retry budget and spool cleanup | Status: PASS
- NFR-006 | Area: OBSERVABILITY | Target: start, object success, gap, discard, spool-low and cycle-error lines are emitted with bounded detail | Validation: code inspection, scratch recorder output and lifecycle/recorder test output | Evidence: observed `recorder start`, `recorder object ok`, `recorder cycle error`, `recorder gap` and `reason=upload_failed` lines in the targeted run; spool-low log path added for the peer-review fix | Status: PASS
- NFR-007 | Area: OPS | Target: receiver-side 500 GiB / 15-day quota and pruner documented; worker does not claim or implement receiver retention | Validation: spec/plan inspection and env example destination documentation | Evidence: this specification plus both env examples document the dacha destination; receiver pruner is outside the worker and not covered by worker tests | Status: CONCERNS
- NFR-008 | Area: BUS | Target: Ubuntu-only packaging and deployment; vps/edge inventories unchanged | Validation: `RecorderPackagingTests` and the exact-artifact build/validate | Evidence: observed targeted run 49 passed / 55 subtests covers inventory and env/template assertions; exact-artifact build and validation PASS | Status: PASS
