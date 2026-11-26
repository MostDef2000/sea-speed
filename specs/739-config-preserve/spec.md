# Feature Specification: #739 — Deploy preserves the protected recorder configuration

- Feature: 739-config-preserve
- Issue: #739
- Status: Implementation landed on branch; tests and CI pending
- Owner outcome: Every deploy reconciles the protected analytics env files without
  wiping operator-owned `SEA_SPEED_RECORDER_*` configuration, a wiped config falls back to a
  safe RELATIVE destination instead of doubling the rrsync root, and the recorder spool
  directory exists before the service starts.

## Product outcome

The Ubuntu deploy step `deploy/worker/ubuntu/configure-analytics-profiles.py` rewrites
`worker.env` and `road-worker.env` wholesale from the analytics whitelist. The recorder block
(`SEA_SPEED_RECORDER_*`) is not part of that whitelist, so every deploy dropped all twelve
recorder keys. Four live symptoms followed: the recorder never started (ENABLED/SOURCE_TYPE
gone), the local spool directory was missing, the SSH known-hosts path was not reachable for
the service user in the wiped configuration, and the destination fell back to the absolute
`root@10.123.239.127:/mnt/fleet-backup/sea-speed/` which the restricted
`rrsync -wo /mnt/fleet-backup/sea-speed` endpoint doubles
(`mkdir "/mnt/fleet-backup/sea-speed/mnt/fleet-backup/sea-speed" failed`).

Outcome 1: the deploy carries the recorder block across both protected env files. Operator
values are preserved when they are valid, an invalid value degrades to the recorder's safe
default instead of failing the deploy, and no recorder value is ever printed.

Outcome 2: the only destination the deploy and the code default ever emit is RELATIVE
(`root@10.123.239.127:./`), because the rrsync endpoint already pins the writable root. A
wiped or absent configuration therefore still fails safe.

Outcome 3: the deploy (and initial commissioning) creates the recorder spool directory under
each service WorkingDirectory with the service user as owner and mode 750, so a fresh deploy
needs no manual `install -d`.

## User scenarios

### Scenario 1 - Deploy preserves every recorder key

Given `worker.env` holds ENABLED=1, SOURCE_TYPE=rtsp, SPOOL_DIR=recorder-spool, a relative
DESTINATION and valid numeric tuning values,
When `configure-analytics-profiles.py` reconciles the protected configuration,
Then `worker.env` still carries all twelve `SEA_SPEED_RECORDER_*` keys with the same valid
values and the recorder starts after the deploy.

### Scenario 2 - Each worker keeps its own recorder block

Given `worker.env` has ENABLED=1 and `road-worker.env` has ENABLED=0,
When the reconcile runs,
Then the Water env keeps ENABLED=1 and the Road env keeps ENABLED=0; a missing Road key falls
back to the same safe default instead of inheriting the Water value.

### Scenario 3 - Invalid preserved value falls back

Given a protected env holds ENABLED=yes, POLL_SEC=abc, OBJECT_MAX_BYTES=1 and
RSYNC_RETRIES=99,
When the reconcile runs,
Then ENABLED becomes 0, POLL_SEC 2, OBJECT_MAX_BYTES 67108864 and RSYNC_RETRIES 3, the deploy
exits successfully, and the invalid values are never echoed.

### Scenario 4 - Relative destination enforced

Given the protected env still holds the legacy absolute
`root@10.123.239.127:/mnt/fleet-backup/sea-speed/`,
When the reconcile runs,
Then the written destination is the relative default `root@10.123.239.127:./`, and the same
relative value is what `worker/recorder.py` uses when no env value is present at all.

### Scenario 5 - Spool directory exists before start

Given a host where the runtime roots exist but no `recorder-spool` directory was ever created,
When the deploy transaction reconciles the protected configuration,
Then `shared/runtime/recorder-spool` and `shared/road-runtime/recorder-spool` exist, are owned
by the service user, have mode 750, and are not symlinks, without weakening any existing
permission check.

## Requirements

- FR-001: `configure-analytics-profiles.py` MUST preserve every `SEA_SPEED_RECORDER_*` key
  found in `worker.env` (Water) and `road-worker.env` (Road) when it rewrites those files; the
  twelve known keys MUST always be written (preserved-or-safe-default), and unknown
  `SEA_SPEED_RECORDER_*` extras MUST be preserved verbatim.
- FR-002: `SEA_SPEED_RECORDER_ENABLED` MUST be literally `0` or `1`;
  `SEA_SPEED_RECORDER_SOURCE_TYPE` MUST be `hls` or `rtsp` (case-insensitive input,
  lowercase output). Anything else falls back to `0` / `hls`.
- FR-003: The numeric keys MUST parse and stay inside the bounds `worker/recorder.py` enforces:
  POLL_SEC 0.5-30, OBJECT_MAX_BYTES 1 MiB-512 MiB, MIN_FREE_BYTES 0-1 TiB,
  HTTP_TIMEOUT_SEC 1-600, RSYNC_TIMEOUT_SEC 1-3600, RSYNC_RETRIES 1-20,
  RSYNC_BACKOFF_SEC 0-300. Non-numeric, non-finite or out-of-range values fall back to the
  recorder defaults.
- FR-004: `SEA_SPEED_RECORDER_DESTINATION` MUST be a RELATIVE rsync target
  (`[user@]host:relative/path`). A missing host, a missing path, an absolute path, a `..`
  segment or an embedded `:` falls back to `root@10.123.239.127:./`.
- FR-005: `SEA_SPEED_RECORDER_SPOOL_DIR` MUST be a relative path without `.`/`..` segments;
  anything else falls back to `recorder-spool`. `SEA_SPEED_RECORDER_HLS_URL` is preserved only
  when it is an explicit credential-free-or-not HTTP(S) URL; otherwise it becomes empty.
- FR-006: A malformed preserved value MUST NOT abort the deploy: validation catches every
  conversion error and substitutes the default. The reconcile prints only status words
  (`RECORDER_CONFIG_PRESERVED=YES`), never a recorder value.
- FR-007: `worker/recorder.py` MUST default `SEA_SPEED_RECORDER_DESTINATION` to the RELATIVE
  `root@10.123.239.127:./`, and the environment override MUST keep working unchanged.
- FR-008: The deploy transaction (`deploy-authorized.sh`) MUST create the recorder spool
  directory under `shared/runtime` and `shared/road-runtime` after the protected-config
  reconcile and before service activation, owner `sea-speed`, mode 750, refusing a symlink and
  skipping only an absent runtime root.
- FR-009: Initial commissioning (`install-systemd.sh`) MUST create the same spool directories
  and include them in the existing 750 ownership/mode pass.
- FR-010: `worker.env.example` and `road-worker.env.example` MUST document that the destination
  stays relative under the restricted rrsync endpoint, MUST keep both blocks identical, and
  MUST use the relative default value.
- FR-011: Nothing else changes: no analytics key, secret handling, mode-600 check, API/token
  validation, deploy authorization, runtime pin or test contract is altered.

## Acceptance criteria

- AC-001: Reconcile preserves all twelve `SEA_SPEED_RECORDER_*` keys with valid operator values in both `worker.env` and `road-worker.env`, independently per file, on repeat runs.
- AC-002: Invalid preserved values (bad literal, non-numeric, non-finite, out-of-bounds) are replaced by the recorder safe defaults; the reconcile exits 0 and never prints a recorder value.
- AC-003: An absolute, empty or malformed `SEA_SPEED_RECORDER_DESTINATION` in protected config is rewritten to the relative default `root@10.123.239.127:./`.
- AC-004: `worker/recorder.py` uses the relative destination when the env value is absent, and still honours an explicit env override.
- AC-005: The deploy/commissioning path creates both recorder spool directories owned by the service user with mode 750, rejecting a symlink, with no existing permission check weakened.
- AC-006: `worker.env.example` and `road-worker.env.example` document the relative-destination constraint identically and ship the relative default value.
- AC-007: The existing protected-config validation (mode 600, API token, M2M URL, relay URL) and the analytics whitelist behaviour are unchanged, and no secret value is logged.

## Preserved recorder contract

| Key | Preserved when | Fallback |
|---|---|---|
| `SEA_SPEED_RECORDER_ENABLED` | literal `0`/`1` | `0` |
| `SEA_SPEED_RECORDER_SOURCE_TYPE` | `hls`/`rtsp` (any case) | `hls` |
| `SEA_SPEED_RECORDER_HLS_URL` | explicit `http(s)://host...` without whitespace | empty |
| `SEA_SPEED_RECORDER_SPOOL_DIR` | relative, no `.`/`..` segment | `recorder-spool` |
| `SEA_SPEED_RECORDER_DESTINATION` | `[user@]host:relative` (no absolute path, no `..`, no `:`) | `root@10.123.239.127:./` |
| `SEA_SPEED_RECORDER_POLL_SEC` | finite float 0.5-30 | `2` |
| `SEA_SPEED_RECORDER_OBJECT_MAX_BYTES` | int 1 MiB-512 MiB | `67108864` |
| `SEA_SPEED_RECORDER_MIN_FREE_BYTES` | int 0-1 TiB | `12884901888` |
| `SEA_SPEED_RECORDER_HTTP_TIMEOUT_SEC` | finite float 1-600 | `30` |
| `SEA_SPEED_RECORDER_RSYNC_TIMEOUT_SEC` | finite float 1-3600 | `60` |
| `SEA_SPEED_RECORDER_RSYNC_RETRIES` | int 1-20 | `3` |
| `SEA_SPEED_RECORDER_RSYNC_BACKOFF_SEC` | finite float 0-300 | `5` |

Unknown `SEA_SPEED_RECORDER_*` extras are copied verbatim into the same file they came from.

## Compatibility and boundaries

- Stable behaviour kept: mode-600 requirement, `SEA_SPEED_API_TOKEN` requirement, private M2M
  URL derivation, relay URL validation, analytics profile defaults, atomic `write_env` chmod 600,
  the `road-worker.env` existence check, and the recorder's own config validation/clamping.
- Out of scope: SSH `known_hosts` provisioning for the service user, the recorder source,
  rrsync endpoint configuration, any production configuration value, `tests/**`.
- Security constraints: preserved values are non-secret tuning/transport settings already
  present in the same protected file; the reconcile never prints them.

## NFR assessment

- NFR-001 | Area: OPERABILITY | Target: after a deploy on a previously wiped host, all twelve recorder keys exist in both protected env files and no manual `install -d` is required to start the recorder | Validation: unit-level reconcile probe over temp install roots plus re-run idempotency, owned by the test worker | Evidence: TEST-001/TEST-002 planned by the test worker; implementation-time temp-root probes recorded in tasks.md | Status: CONCERNS
- NFR-002 | Area: RELIABILITY | Target: every malformed preserved value degrades to a recorder safe default and the reconcile always exits 0; a deploy is never aborted by recorder configuration | Validation: negative matrix in a temp install root | Evidence: TEST-003 planned by the test worker | Status: CONCERNS
- NFR-003 | Area: SEC | Target: no recorder value or token appears in reconcile output; protected env files stay mode 600 | Validation: captured stdout/stdout inspection and stat mode check in temp roots | Evidence: TEST-003 planned; implementation-time probe recorded `SECRETS_DISPLAYED=NO` | Status: CONCERNS
- NFR-004 | Area: RELIABILITY | Target: no recorder write can address a doubled rrsync path; the emitted and code-default destination is always relative | Validation: unit test of the destination validator plus RecorderConfig default | Evidence: TEST-001/TEST-004 planned by the test worker | Status: CONCERNS

## Runtime feedback

- Runtime acceptance: not yet performed; the deploy targets the merged main SHA and the
  recorder spool ownership/mode is verified on the host during acceptance.
- Known follow-up (outside this scope): SSH `known_hosts` visibility for the service user is a
  separate concern from the config wipe and needs its own admission.
