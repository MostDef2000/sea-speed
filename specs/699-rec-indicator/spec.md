# Feature Specification: #699 — REC indicator (recording evidence from successful segment uploads)

- Feature: 699-rec-indicator
- Issue: #699
- Sub-issue: REC
- Status: Source implementation landed on branch; tests and CI pending

## Product outcome

Operators cannot tell from the camera state whether the recorder is actually
delivering media. "The recorder process exists" is not evidence that a segment
was completed and uploaded, so a silently stalled recorder looks identical to a
healthy one.

This feature adds a REC indicator derived only from actual successful uploads:
REC means "this camera successfully uploaded a completed media segment within
the last 30 seconds". The recorder writes a tiny per-camera witness file only
when a completed segment upload succeeds; the analytics worker reads that
witness and reports `recording_last_success_at` (UTC ISO timestamp or explicit
`null`) in every camera state it posts. The indicator is expiring evidence, not
a sticky boolean, and it is never a promise of a no-gap or playable archive.

No API change, no schema migration, no new configuration: the 30-second window
is a fixed evidence constant. A missing, malformed, wrong-camera, future or
expired witness, failed upload, init-only cycle, incomplete clip and disabled
recording all resolve to `null`.

## User scenarios

Feature: REC indicator derived from successful segment uploads

Rule: a camera reports fresh recording evidence only after a completed segment
upload succeeds and remains inside the 30-second window.

```gherkin
Scenario: AC-001 — recording disabled writes no witness and reports null
  Given SEA_SPEED_RECORDER_ENABLED is 0
  When any media segment would be produced by the source
  Then the recorder writes no recording witness file
  And the camera state carries recording_last_success_at = null

Scenario: AC-002 — init-only HLS cycle reports null
  Given the HLS recorder downloads only the EXT-X-MAP init object successfully
  And no completed media segment is uploaded
  Then no witness is written
  And the camera state carries recording_last_success_at = null

Scenario: AC-003 — incomplete RTSP clip reports null
  Given the RTSP recorder has a finalized clip whose size is empty or over the object cap
  When that clip is discarded without a successful upload
  Then no witness is written
  And the camera state carries recording_last_success_at = null

Scenario: AC-004 — failed upload reports null
  Given a completed segment reaches the bounded rsync upload
  And the upload fails after its bounded retries
  Then no witness is written for that segment
  And the camera state carries recording_last_success_at = null

Scenario: AC-005 — successful HLS segment reports a timestamp
  Given a completed HLS media segment uploads successfully
  When the analytics worker posts the next camera state
  Then the witness records last_success_at as a UTC ISO timestamp
  And the state carries recording_last_success_at equal to that timestamp

Scenario: AC-006 — successful RTSP segment reports a timestamp
  Given a nonempty finalized RTSP clip uploads successfully
  When the analytics worker posts the next camera state
  Then the witness records last_success_at as a UTC ISO timestamp
  And the state carries recording_last_success_at equal to that timestamp

Scenario: AC-007 — freshness expires at 30 seconds
  Given a witness whose last_success_at is 29.9 seconds old
  Then the camera state carries the timestamp
  When the same witness is exactly 30 seconds old or older
  Then the camera state carries recording_last_success_at = null
  And a witness timestamp in the future also yields null

Scenario: AC-008 — unusable witness reports null without suppressing analytics
  Given the witness is missing, malformed, corrupt JSON or written for a different camera
  Then the camera state carries recording_last_success_at = null
  And the state POST and analytics keep running

Scenario: AC-009 — disabled recording with a leftover witness reports null
  Given a valid fresh witness file is left over from a previous enabled run
  And SEA_SPEED_RECORDER_ENABLED is now 0
  Then the camera state still carries recording_last_success_at = null
```

## Requirements

- R-1 (success-only witness): the HLS recorder writes the witness only on a
  successful completed media segment upload and the RTSP recorder only after a
  nonempty finalized clip upload succeeds. Init/EXT-X-MAP objects, failed
  uploads, discarded/over-cap/incomplete clips and disabled recording write no
  witness.
- R-2 (witness format): a per-camera JSON object
  `{"camera_id": <id>, "last_success_at": <UTC ISO>}` written in the configured
  recorder spool directory using an atomic temp-write + `os.replace`.
- R-3 (best-effort write): a witness I/O failure is swallowed and never turns a
  successful delivery into a retry.
- R-4 (state enrichment): every camera state POST carries
  `recording_last_success_at`, either the fresh ISO timestamp or an explicit
  `null`, added to a copy of the metadata so the reporter never mutates the
  caller's payload. An explicit `null` clears a prior witness on a metadata-only
  API merge.
- R-5 (freshness): only `0 <= age < 30` seconds is fresh; exactly 30 seconds is
  not. Missing, malformed, corrupt, wrong-camera and future timestamps resolve to
  `null`. The window is a fixed constant, not a setting.
- R-6 (read isolation): a witness read failure must not suppress analytics, and
  the analytics layer loads no credential- or URL-bearing recorder configuration
  (only the shared enabled/spool-dir/camera values).
- R-7 (no API change): the API already accepts arbitrary JSON metadata keys and
  merges metadata-only posts; no allowlist, schema, migration or default-state
  change is made.
- R-8 (documentation): both Ubuntu worker env examples document the witness
  contract identically and add no new flag.

## Acceptance criteria

- AC-001: With recording disabled, no witness file is written and every state carries `recording_last_success_at=null`.
- AC-002: An HLS cycle that uploads only the init object writes no witness and reports `null`.
- AC-003: An incomplete/empty/over-cap RTSP clip is discarded without a witness write and reports `null`.
- AC-004: A segment whose bounded upload fails writes no witness and reports `null`.
- AC-005: A successful completed HLS segment upload writes the witness and the next state reports the fresh timestamp.
- AC-006: A successful nonempty finalized RTSP clip upload writes the witness and the next state reports the fresh timestamp.
- AC-007: Freshness is `0 <= age < 30 s`; a 29.9 s witness reports the timestamp, exactly 30 s or older reports `null`, and a future timestamp reports `null`.
- AC-008: A missing, malformed, corrupt or wrong-camera witness reports `null` and never suppresses the state POST or analytics.
- AC-009: A leftover fresh witness from a previous enabled run still reports `null` while recording is disabled.

## NFR assessment

- NFR-001 | Area: OPERABILITY | Target: an operator can distinguish a delivering recorder from a stalled one within one 30-second window from camera state alone, with no new setting to configure | Validation: transport/recorder tests planned by the test worker; implementation-time probes recorded in tasks.md | Evidence: TEST-001/TEST-002 planned; direct probe of the enrichment helper recorded in tasks.md | Status: CONCERNS
- NFR-002 | Area: RELIABILITY | Target: no witness I/O or read failure changes delivery success or suppresses state/analytics; a successful upload stays a success | Validation: negative-path tests around the best-effort writer and reader | Evidence: TEST-003/TEST-004 planned by the test worker | Status: CONCERNS
- NFR-003 | Area: SEC | Target: the analytics read path loads no credential or URL recorder config and never logs witness contents | Validation: import/read-path inspection plus the fixed transport import allowlist test | Evidence: TEST-005 planned; implementation-time import inspection recorded in tasks.md | Status: CONCERNS
- NFR-004 | Area: DATA | Target: a stale or wrong-camera witness can never surface as fresh REC evidence; the window is fixed at 30 s | Validation: freshness matrix (29.9 s, exactly 30 s, future, wrong camera, corrupt) | Evidence: TEST-002/TEST-003 planned by the test worker | Status: CONCERNS

## Runtime feedback

- Runtime acceptance: not yet performed; the merged main SHA deploys to the
  Ubuntu worker/relay contour and the REC indicator is observed in camera state
  while a recorder segment cycle runs.
- Known follow-up (outside this scope): the REC indicator is evidence of a
  successful completed-segment upload, not a no-gap or playable-archive proof.
