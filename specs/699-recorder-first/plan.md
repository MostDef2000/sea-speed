# Implementation Plan: Opt-in recorder of original encoded HLS segments

- Feature: 699-recorder-first
- Specification: specs/699-recorder-first/spec.md
- Issue: #699
- Status: Source implementation

## Architecture

One opt-in recorder module plus lifecycle wiring at the Ubuntu Worker boundary;
no change to the analytics main loop, media reader, API or VPS contours.

1. **`worker/recorder.py` (new).** `RecorderConfig.from_env()` reads a bounded
   configuration once: `SEA_SPEED_RECORDER_ENABLED` (only `0`/`1`),
   `SEA_SPEED_RECORDER_HLS_URL` (explicit HTTP(S) only), spool directory,
   dacha destination, poll interval, 64 MiB object cap, 12 GiB free-space
   floor, HTTP deadline, rsync timeout/retries/backoff. `parse_playlist`
   extracts `#EXT-X-MEDIA-SEQUENCE`, `#EXT-X-MAP` and `#EXTINF`-referenced
   segment URIs. `HlsRecorder` fetches the playlist, resolves relative URIs
   against the final playlist URL, downloads each object through a chunked
   reader with a per-object deadline and size cap, atomically renames the
   completed spool file, then rsyncs it to dacha over the LoadCredential key.
   Same-origin redirects are permitted by a custom redirect handler; a
   cross-origin redirect raises. Basic auth reuses
   `worker_kernel.media_basic_auth_for_input` and is attached only to the
   configured origin. A bounded recent-key set prevents duplicate delivery;
   media-sequence jumps and failed uploads increment a gap counter.
2. **`worker/ubuntu_worker_entrypoint.py` (lifecycle only).** At `__main__`,
   after the existing supervisor self-test, `_start_recorder()` spawns
   `recorder.py` as a separate process with `stdin=DEVNULL`,
   `start_new_session=True` and no pipe or readiness wait. Any spawn failure
   prints a diagnostic and leaves recording disabled; it cannot fail ingest.
   `_stop_recorder()` sends SIGTERM to the recorder process group (reaching a
   running rsync descendant) and escalates to SIGKILL after 10 s. SIGTERM/SIGINT
   are converted into `SystemExit` so the existing `finally` block runs.
3. **Configuration and packaging.** Both Ubuntu env examples carry the same
   `SEA_SPEED_RECORDER_*` opt-in block; both service templates keep the
   `LoadCredential=recorder_ed25519:/etc/sea-speed/recorder_ed25519` mount.
   `worker/recorder.py` is added to the ubuntu-worker required lists in
   `scripts/quality/build_exact_artifacts.py` and
   `scripts/quality/validate_exact_artifacts.py`; vps and edge inventories are
   untouched.

Object naming in the spool is `<camera>-<sequence>-<index>-<basename>` (or a
hash tag when the playlist has no media sequence) and
`<camera>-init-<digest>-<basename>` for `#EXT-X-MAP`, so a rolling playlist
cannot overwrite an earlier object. The receiver-side 500 GiB / 15-day quota
and pruner are operated at dacha; the worker deletes each local object after
its upload attempt.

## Decisions

- D-699-1 — direct HTTP(S) object fetch, not ffmpeg: the requirement is the
  original encoded bytes; a remux/decode would change the artifact and add a
  GPU dependency. RTSP packet capture is explicitly out of scope.
- D-699-2 — separate child process: ingest isolation is structural. A hung
  receiver or a crashing recorder cannot block the worker main loop because
  there is no shared pipe, lock or readiness wait.
- D-699-3 — stdlib `urllib`: no new runtime dependency; requests is not
  required by the recorder, matching the existing guarded-import discipline.
- D-699-4 — LoadCredential only: the key path is resolved from
  `$CREDENTIALS_DIRECTORY` or `/run/credentials/recorder_ed25519`; the
  `ProtectHome=true` unit stays intact and no key is embedded or logged.
- D-699-5 — same-origin redirects only, with auth scoped to the configured
  origin: this follows the bounded-source contract and avoids credential
  leakage to a redirect target.
- D-699-6 — bounded spool, discard-on-prolonged-failure: one object at a time,
  64 MiB cap, 12 GiB free-space floor, bounded rsync retry/backoff, then delete
  and count a gap. This keeps the local footprint tiny and the failure local.
- D-699-7 — receiver retention is not worker logic: dacha enforces 500 GiB /
  15 days; the worker only delivers original objects and never claims to prune
  the receiver.

## Affected contours

- Contour: Ubuntu Worker/relay.
- VPS deployment: NOT APPLICABLE — no `api/**` or frontend change.
- Ubuntu worker/relay update: REQUIRED — new `worker/recorder.py`, entrypoint
  lifecycle wiring, both Ubuntu env examples and both service templates change;
  the exact-release path ships the new file.
- Windows worker update: NOT APPLICABLE — retired from production.
- Production safety envelope: recorder default OFF; no new route, API,
  database, public exposure or runtime authority. When enabled it reads an
  authorized HTTP(S) source and writes original objects to the provisioned
  dacha destination with a restricted key.

## Validation

Observed on this working tree (2026-11-25), no fabricated results:

- `python3 -m py_compile worker/recorder.py worker/ubuntu_worker_entrypoint.py scripts/quality/build_exact_artifacts.py scripts/quality/validate_exact_artifacts.py`
  → `PYCOMPILE_OK`.
- `python3 -m ruff check --config scripts/quality/ruff.toml worker/recorder.py worker/ubuntu_worker_entrypoint.py scripts/quality/build_exact_artifacts.py scripts/quality/validate_exact_artifacts.py`
  → `All checks passed!`.
- Scratch oracle `/tmp/opencode/699-recorder-first/smoke.py` → `RECORDER_SMOKE_OK`:
  - playlist parse: init `init.mp4`, segments `seg0.ts`/`seg1.ts`, media
    sequence 7;
  - downloaded segment and init bytes equal the source objects;
  - same-origin redirect delivered the original bytes;
  - cross-origin redirect was refused;
  - RTSP source configuration was rejected;
  - `CREDENTIALS_DIRECTORY` key resolution selected the credential file;
  - fake-rsync delivery was byte-identical and the local spool was cleaned.
- Entrypoint lifecycle scratch run → recorder child spawned; SIGTERM stop
  observed exit code 143; spawn failure printed `recorder disabled spawn
  failure reason=OSError` and left no child; disabled flag spawned nothing.
- Inventory assertion over `COMPONENT_FILES` and `REQUIRED_BY_COMPONENT` →
  `INVENTORY_OK` (ubuntu-worker has `worker/recorder.py`; vps/edge do not).
- `python3 scripts/quality/build_exact_artifacts.py --source-commit a66b5a8039cdba585f8b549e1091989586b0d72a --output-dir /tmp/opencode/699-recorder-first/dist`
  → exit 0, Ubuntu Worker artifact includes `worker/recorder.py`.
- `python3 scripts/quality/validate_exact_artifacts.py --manifest /tmp/opencode/699-recorder-first/dist/exact-artifacts.json`
  → `Exact artifacts valid: VPS/edge quality evidence plus Ubuntu Worker release inventory, digests, extraction and syntax`.
- `python3 scripts/ci/validate_sdd.py` → recorded in tasks.md evidence.
- Dedicated `tests/**` coverage is owned by the test worker and is PENDING in
  this worker's evidence; no test result is claimed here.

## Runtime feedback

- Pre-change behavior: no recorder existed; the worker only decoded the HLS
  stream for analytics.
- Expected post-deploy behavior while disabled: unchanged worker and unchanged
  artifact payload for vps/edge; the Ubuntu artifact gains an unimported-by-
  default module and the lifecycle hooks do nothing when the flag is `0`.
- Expected behavior when enabled: original HLS objects delivered to dacha;
  receiver outage yields bounded gaps; analytics ingest continues.
- Runtime acceptance: PENDING — the feature ships disabled by default and no
  production enablement is part of this change.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: every object transfer has a per-object deadline, bounded rsync timeout, bounded retry/backoff and discard; a hung receiver cannot block the worker main process | Validation: code inspection of `download_object`/`upload`/`rsync_object`; scratch timeout/retry paths are not yet dedicated-test covered (PENDING) | Residual risk: a receiver outage loses the objects inside the bounded gap window | Owner: worker implementation | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: stream original bytes to a `.part` file, atomically rename, then rsync the completed file; no decode/remux/rewrite | Validation: scratch smoke compared segment/init bytes and fake-rsync delivered bytes; dedicated tests PENDING | Residual risk: a source server serving different bytes for the same URI remains outside the worker's control | Owner: worker implementation | Status: MITIGATED
- RISK-003 | Category: SEC | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: key only from LoadCredential paths; no `/home`; basic auth only on the configured origin; cross-origin redirects refused; no credential values logged | Validation: code inspection of `_credential_path`/`headers_for`/`_SameOriginRedirect`; scratch cross-origin refusal; dedicated tests PENDING | Residual risk: a malicious authorized source could still serve non-media bytes as segment payloads | Owner: worker implementation | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: one object at a time, 64 MiB per-object cap, 12 GiB free-space floor, spool file deleted after each upload attempt | Validation: code inspection and scratch spool cleanup; dedicated tests PENDING | Residual risk: many small objects can still create high rsync churn | Owner: worker implementation | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: default OFF, explicit HTTP(S) URL required when ON, operator enablement only; no automatic production enablement in this scope | Validation: env examples default `SEA_SPEED_RECORDER_ENABLED=0`; entrypoint spawns only on literal `1`; runtime acceptance PENDING | Residual risk: an operator enables recording against a source without confirming authorization/storage policy | Owner: operator enablement | Status: ACCEPTED
- RISK-006 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: receiver-side 500 GiB / 15-day quota and pruner are documented as dacha responsibility; worker does not delete receiver data or claim retention | Validation: spec/plan and env example review; no receiver mutation code in the change | Residual risk: dacha quota/pruner drift is outside repository control and must be observed operationally | Owner: receiver operations | Status: ACCEPTED

## Test design

- TEST-699-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: PENDING — test worker owns `tests/**`; implementation path is entrypoint `_recorder_enabled`/`_start_recorder` returning before spawn when the flag is not `1`
- TEST-699-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: PENDING dedicated test; scratch smoke `RECORDER_SMOKE_OK` observed byte-identical segment/init download and fake-rsync delivery
- TEST-699-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: PENDING dedicated test; scratch smoke observed relative URI use, same-origin redirect success, cross-origin refusal and RTSP rejection
- TEST-699-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: PENDING dedicated test; code inspection of chunk loop, `object_max_bytes`, deadline and `min_free_bytes`
- TEST-699-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: PENDING dedicated test; code inspection of bounded retry/backoff, discard and gap counter
- TEST-699-006 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: PENDING dedicated test; scratch entrypoint lifecycle observed spawn, rc 143 stop and spawn-failure isolation
- TEST-699-007 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: PENDING dedicated test; `INVENTORY_OK` and exact-artifact build/validate observed locally, both env examples inspected
- TEST-699-008 | Covers: AC-008 | Level: integration | Priority: P1 | Evidence: PENDING test-worker evidence; py_compile, ruff and validate_sdd outputs are recorded in tasks.md

## Correct-course check

- Trigger: NONE
- Issue impact: Issue #699 defines the outcome; no issue rewrite required.
- Specification impact: New specs/699-recorder-first/spec.md authored for this scope.
- Plan impact: This plan; no scope change after admission.
- Tasks impact: Tasks T001-T006 cover recorder, lifecycle, env examples, packaging, SDD and verification.
- Authorization impact: Bounded Ubuntu worker/SDD scope only; no new production authority.
- Follow-up: Dedicated `tests/**` coverage by the test worker is intentionally deferred; field enablement and dacha retention observation remain operational follow-up.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: working tree and branch unchanged | Retry: N/A | Rollback: N/A | Evidence: work order for Issue #699 on branch agent/wave6-699-recorder; allowed paths are worker/recorder.py, worker/ubuntu_worker_entrypoint.py, both Ubuntu env examples, both service templates, the two quality scripts and specs/699-recorder-first/**; base_sha a66b5a80 verified as branch HEAD
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous Ubuntu Worker release remains active | Retry: N/A | Rollback: N/A | Evidence: py_compile OK, ruff All checks passed, scratch smoke RECORDER_SMOKE_OK, inventory check OK and exact-artifact build/validate PASS on the changed tree
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: the exact-release install fails closed before activation; the previous release keeps running | Retry: Re-dispatch the Ubuntu deploy workflow on the same merged main SHA | Rollback: roll the Ubuntu Worker back to the previous complete release with rollback-exact.sh | Evidence: deploy/worker/ubuntu env examples and systemd templates change; worker/recorder.py is added to the ubuntu-worker exact artifact; the existing deploy-authorized exact-release transaction is unchanged
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release remains active | Retry: Re-run the same verification after fixing the failing gate | Rollback: N/A | Evidence: existing post-deploy worker health and runtime-progression gates apply unchanged; local py_compile, ruff, validate_sdd and exact-artifact validation observed
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker state store and dacha destination | Retry: N/A | Rollback: N/A | Evidence: no schema, database or API state change; recorder writes only its bounded spool and dacha objects; default OFF means no writes at deploy time
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scratch only under /tmp/opencode, no repository residue | Retry: N/A | Rollback: N/A | Evidence: smoke/progress artifacts live under /tmp/opencode/699-recorder-first; no progress, cache or generated file is added to the repository
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial but no runtime effect | Retry: Re-run the observed command and append output | Rollback: N/A | Evidence: observed py_compile/ruff/smoke/inventory/build outputs plus validate_sdd and git status/diff stat; dedicated tests remain PENDING with the test worker
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: N/A | Rollback: revert the bounded PR or roll the Ubuntu Worker back to the previous complete release; with the recorder default OFF the runtime impact of the previous release is none | Evidence: diff limited to the allowed worker/deploy/quality/spec paths; disabled flag short-circuits before spawn and no media path changes
