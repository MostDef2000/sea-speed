# Implementation Plan: REC indicator from successful segment uploads

- Specification: specs/699-rec-indicator/spec.md
- Issue: #699
- Sub-issue: REC
- Status: Implemented on branch; tests owned by the test worker

## Architecture

Three small changes on the Ubuntu worker/relay contour plus documentation; the
VPS API consumes the new metadata key without any code change.

1. `worker/recorder.py` gains a fixed evidence constant
   `RECORDING_WITNESS_FRESHNESS_SEC = 30.0`, `recording_witness_path(spool_dir,
   camera_id)` and a best-effort `write_recording_witness(config)` that writes
   `{"camera_id", "last_success_at": UTC ISO}` atomically (temp file, `json.dump`,
   `fsync`, `chmod 0644`, `os.replace`). `HlsRecorder.capture` takes a
   `record_witness` flag; only the completed-segment call site in `run()` passes
   `record_witness=True`, so the init/EXT-X-MAP path never writes a witness. The
   write is wrapped so an I/O failure never turns a successful upload into a
   retry.
2. `worker/recorder_rtsp.py` calls `write_recording_witness(self.config)` inside
   `_finalize` only in the `if ok:` branch, after a nonempty finalized clip has
   passed the size/floor gates and uploaded successfully.
3. `worker/worker_transport.py` gains `recording_last_success_at()` and
   `_with_recording_state(metadata)`. `post_state` serialises a COPY of the
   metadata enriched with `recording_last_success_at` (fresh ISO string or
   explicit `null`). The reader gates on `SEA_SPEED_RECORDER_ENABLED`, uses only
   `CAMERA_ID`/`SEA_SPEED_RECORDER_SPOOL_DIR`, validates the witness camera and
   timestamp, and applies the fixed `0 <= age < 30 s` window; any error returns
   `null`. `datetime`/`re` are imported inside functions to keep the transport
   module import allowlist intact.
4. Both `deploy/worker/ubuntu/worker.env.example` and `road-worker.env.example`
   document the witness contract with identical text and add no new variable.

The API (`api/app/main.py`) already accepts arbitrary metadata keys and merges
metadata-only posts, so the explicit `null` clears a stale timestamp. No API,
schema or migration change is made.

## Decisions

### D-001 - Expiring witness file, not a sticky boolean or process check

- Decision: derive REC from a per-camera JSON witness whose `last_success_at`
  must be inside the fixed 30-second window on every state POST.
- Reason: REC must mean "a completed segment actually uploaded recently". A
  boolean would stick after the recorder stops, and a process check would report
  healthy for a recorder that has not delivered anything.
- Alternatives rejected: liveness/process probes (not delivery evidence); counting
  gaps in the playlist (proves nothing about upload success); an API-side TTL flag
  (adds state and a schema change the need does not justify).

### D-002 - Write only on successful completed-segment upload

- Decision: the witness is written in the successful segment branches only, never
  in `bounded_upload` (shared with init objects) and never on failed uploads.
- Reason: init/EXT-X-MAP objects are not media segments and a failed upload is
  exactly the outage REC must not hide.
- Alternatives rejected: writing in `bounded_upload` (would count init objects);
  writing on download success (before upload proves delivery).

### D-003 - Best-effort witness I/O

- Decision: every witness write and read is wrapped; failures are swallowed.
- Reason: witness bookkeeping must never change delivery success or suppress
  analytics.
- Alternatives rejected: raising on witness failure (turns a side effect into a
  retry/outage).

### D-004 - Enrich a copy in the single transport choke point

- Decision: `post_state` enriches a copy of the metadata, and every state path
  (including the three main-loop posts and the runtime wrapper) flows through it.
- Reason: one choke point covers all posts without touching the runtime worker
  module, and copying keeps the caller's payload immutable.
- Alternatives rejected: editing each call site (duplication, misses the runtime
  wrapper); a separate metadata key only on some paths (inconsistent).

### D-005 - Fixed 30-second constant, explicit null for non-evidence

- Decision: the window is a fixed constant shared by writer and reader; the key is
  always present, as a timestamp or explicit `null`.
- Reason: the window is a correctness boundary, not a tuning knob, and always
  emitting the key lets a metadata-only API merge clear a stale value.
- Alternatives rejected: a configurable TTL (new flag, more failure modes);
  omitting the key when there is no evidence (leaves the previous timestamp
  stuck).

## Affected contours

- Repository: `worker/recorder.py`, `worker/recorder_rtsp.py`,
  `worker/worker_transport.py`,
  `deploy/worker/ubuntu/worker.env.example`,
  `deploy/worker/ubuntu/road-worker.env.example`, this SDD trio.
- Ubuntu worker/relay: REQUIRED — next deploy ships the recorder and analytics
  changes to the GPU box.
- VPS: consumer-only — the API already stores and returns the new metadata key;
  no VPS code, schema or deploy mutation is required.
- Windows worker/AI: NONE.
- Public interfaces: the camera-state metadata gains the
  `recording_last_success_at` key; no route, schema or response field changes.

## Validation

- Static: `python3 -m py_compile` on the three changed Python files,
  `ruff check --config scripts/quality/ruff.toml` on the same files,
  `python3 scripts/ci/validate_sdd.py`.
- Unit/integration (test worker): HLS/RTSP witness write on success only, freshness
  matrix (29.9 s / exactly 30 s / future / wrong camera / corrupt / missing),
  disabled-with-leftover, failed-upload and init-only paths, copy semantics of the
  enrichment, and the transport import allowlist.
- Runtime acceptance: deploy the merged main SHA and observe
  `recording_last_success_at` transition from `null` to a fresh timestamp while the
  recorder segments upload, and back to `null` when recording is stopped.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: all witness I/O is best-effort and wrapped; a write failure never converts a successful upload into a retry and a read failure never suppresses a state POST | Validation: TEST-003 negative-path tests owned by the test worker | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: fixed `0 <= age < 30 s` window, wrong-camera rejection, future-timestamp rejection and explicit `null` on every non-evidence path prevent stale or foreign REC | Validation: TEST-002 freshness/wrong-camera/corrupt matrix | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: writer and reader share `SEA_SPEED_RECORDER_SPOOL_DIR`/`CAMERA_ID` and the same sanitised filename; a mismatch resolves to `null` (no false positive) and is documented in both env examples | Validation: TEST-001 filename/shared-env parity plus post-deploy acceptance | Residual risk: MEDIUM | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-004 | Category: SEC | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the analytics read path touches only enabled/camera/spool-dir env and the witness file; it loads no credential or URL recorder config and logs no witness contents | Validation: TEST-005 read-path inspection plus the unchanged transport import allowlist test | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-005 | Category: PERF | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: a per-state-post read of one tiny JSON file, off the inference path, with all errors short-circuited | Validation: TEST-004 transport enrichment unit test | Residual risk: LOW | Owner: delivery-orchestrator | Status: ACCEPTED

## Test design

- TEST-001 | Covers: AC-005, AC-006 | Level: unit | Priority: P0 | Evidence: test worker asserts a successful HLS segment and a successful finalized RTSP clip each write exactly one witness with the expected camera and UTC timestamp, and that the segment call site is the only HLS writer
- TEST-002 | Covers: AC-007, AC-008 | Level: unit | Priority: P0 | Evidence: test worker asserts the freshness matrix (29.9 s fresh, exactly 30 s expired, future null, wrong camera null, corrupt JSON null, missing null) on the transport reader
- TEST-003 | Covers: AC-001, AC-002, AC-003, AC-004, AC-009 | Level: integration | Priority: P0 | Evidence: test worker drives disabled, init-only, incomplete/over-cap clip, failed upload and disabled-with-leftover scenarios and asserts no witness write and `null` state
- TEST-004 | Covers: AC-005, AC-008 | Level: unit | Priority: P1 | Evidence: test worker asserts `post_state` posts a copy enriched with `recording_last_success_at` (string or `null`) and never mutates the caller dict
- TEST-005 | Covers: AC-008 | Level: unit | Priority: P1 | Evidence: test worker asserts the transport import allowlist is unchanged and the analytics read path loads no recorder credential/URL config

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: the separate test worker owns `tests/**`, including updating existing assertions that a successful HLS delivery leaves an empty spool and that a metadata-only state payload equals its exact input (both change by design).

## Deployment transaction audit

This audit models the MIXED rollout of the REC indicator: the Ubuntu worker/relay
contour ships the recorder and analytics changes (`worker/**`,
`deploy/worker/ubuntu/**`), while the VPS API only consumes and returns the new
metadata key with no code or deploy mutation. The deploy target is the exact green
main SHA produced by this PR, activated through
`.github/workflows/deploy-ubuntu-worker.yml` under the standing production
delegation policy after the protected transaction proves exact current-main
source. Runtime acceptance is planned, not yet performed.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: the host stays on the release recorded in `shared/runtime/active-source-commit` and the VPS API is untouched | Retry: re-enter the protected deploy workflow only with an exact first-parent main SHA, green Quality evidence on that SHA and an allowed policy decision | Rollback: NOT REQUIRED before any mutation | Evidence: exact main SHA, green Quality integration run and standing-delegation policy decision for that SHA
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: backups may exist under the updater root while both services and the VPS API remain on the previous release | Retry: verify protected env modes and service states, then re-enter the deploy transaction | Rollback: transaction cleanup removes backups; the active release is unchanged | Evidence: `PROTECTED_CONFIG_BACKUP=PASS` and captured pre-deploy service states
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: the new worker code may be staged or partially activated while the previous release still runs; the VPS API is not mutated by this path | Retry: only after the transaction either rolls back or proves a coherent activated state | Rollback: `restore_protected_config` plus the protected previous-release rollback return the worker to the recorded release; VPS needs no rollback because it was never mutated | Evidence: `PROTECTED_CONFIG_RECONCILED=YES`, exact `ExecStart` identity of the activated release
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: the new release may be active but not accepted; the REC indicator is unproven | Retry: resolve identity or post-activation checks once the actual active release is known | Rollback: `verify_active_target` failure triggers the protected previous-release rollback | Evidence: exact `ExecStart` identity, service states, and a camera-state probe showing `recording_last_success_at` present (null or timestamp)
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: the deployment manifest is missing or incomplete and completion is forbidden | Retry: verify the active release identity before rewriting the manifest | Rollback: the previous active release remains the declared rollback target | Evidence: `deployment-manifest-ubuntu-worker.json` with `runtime_verified` state and the REC-probe result
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: the verified runtime stays valid while stage directories or stale backups may remain | Retry: remove leftover stage artifacts on the next deploy | Rollback: NOT REQUIRED solely for housekeeping failure | Evidence: transaction cleanup trap output and updater-root listing
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: the runtime may be healthy while REC acceptance evidence is incomplete | Retry: recollect the camera-state probe without redeploying when the SHA is unchanged | Rollback: decide from actual runtime behaviour, not evidence upload alone | Evidence: camera-state JSON showing `recording_last_success_at` null-to-timestamp-to-null transitions together with recorder segment-ok log lines
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous release cannot be restored and verified, automated mutation stops and the actual host state must be recovered | Retry: read the active marker, runtime id and service evidence before any new mutation | Rollback: no guessed target; restore the previous exact release recorded in the active marker and its protected config backup | Evidence: rollback-exact logs, restored config, and verified service states

## Rollout and rollback

- Rollout: normal Ubuntu worker deploy of the merged SHA ships the recorder
  witness writer and the analytics enrichment; the VPS API begins returning the
  new metadata key from the stored state with no VPS deploy required.
- Rollback: revert this PR's merge or run the protected previous-release
  rollback; the VPS never mutated, and an old worker simply stops emitting the
  key. Any leftover witness file is ignored by the reverted code.

## Runtime feedback

- Actual architecture after acceptance: expected to match the plan.
- Differences from plan: NONE YET
- Deferred cleanup: none beyond test-worker-owned `tests/**` updates.
