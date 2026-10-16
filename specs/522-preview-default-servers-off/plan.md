# Plan: #522 — preview relay: explicitly disable unused mediamtx default servers

- Specification: specs/522-preview-default-servers-off/spec.md

## Architecture

The preview relay renderer (`scripts/operations/mediamtx_path_config.py`,
mode `ubuntu-preview-relay`) builds the mediamtx config from scratch: it is
the single source of truth for which servers exist. Adding five explicit
top-level toggles to the render skeleton is a leaf change: no input schema,
CLI flag, auth-rule, catalog or unit-file surface is touched. The renderer
output reaches the box through the standing worker deploy (install root
`/opt/sea-speed-worker`; `deploy/worker/ubuntu/camera-preview-relay.sh:83`
resolves the renderer relative to `repo_root`) and is applied by the
digest-bound prepare→activate tx, which restarts only the preview service.

## Decisions

- D-1 (disable, don't rebind): :8892 is killed by disabling the owning
  default server rather than narrowing its bind. Zero established peers,
  RTSP-only in-repo consumers, and the re-render trap (hand-edited yml is
  silently reverted by the next prepare) make elimination the only durable
  fix. Rebinding would leave an unused server alive.
- D-2 (canonical vocabulary): the five added toggles are exactly the cam1
  disable vocabulary minus what the preview already pins
  (`rtmp/hls/webrtc/srt` are already `false`); `api/metrics/pprof/
  playback/moq` complete it. No `rtsps`/`ui`/`httpAddress` guesses — the
  cam1 profile proved this vocabulary against a real binary.
- D-3 (one-time documented drift): golden/parity tests deliberately freeze
  the byte skeleton; this change is a synchronized, reviewed skeleton bump
  (renderer + tests + runbook in one PR), the documented one-time-drift
  pattern from specs/442.
- D-4 (verify-preview-auth untouched): auth verification parses the auth
  rule block; server toggles are outside its contract. The new state is
  covered by positive unit pins instead.

## Affected contours

- Ubuntu Worker/relay: renderer bytes land via the lane-A worker deploy;
  applied on-box by one lane-B sysadmin prepare→activate tx (preview
  service restart, scoped). VPS: none. Repo CI: full battery + validators.

## Validation

- `python3 -m pytest tests/test_mediamtx_preview_relay.py
  tests/test_camera_preview_gallery.py -q` (focused);
  `python3 -m pytest tests/ -q` (full battery);
  `python3 scripts/ci/validate_sdd.py`; `python3 scripts/ci/validate_repo.py`;
  PR Change Contract exact-file match; CI 8/8 on exact head.
- Runtime (on-box, lane-B tx): step 0 records `mediamtx --version` and
  current digests; after activate `ss -tlnp` must show no :8892 on the
  preview PID and `rtspAddress 10.123.239.102:8555` alive; evidence on #522.

## Runtime feedback

- Any strict-parser rejection (unknown key on an old binary) surfaces as an
  activate failure BEFORE state commit (candidates are staged, active/ and
  unit untouched until digest-bound commit); rollback = activate with the
  previous digest triple from backups/candidates.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: activate is digest-bound and fail-closed (is-active gate + TCP listener probe) and only commits after the new config passes render schema; step 0 records the box binary version | Validation: on-box tx step 0 + activate gates; rollback drill command in handoff | Residual risk: binary older than the moq key would keep the tx from applying (open key rejected); detected at activate, no state damage | Owner: delivery-orchestrator | Status: OPEN
- RISK-002 | Category: OPS | Probability: 3 | Impact: 2 | Score: 6 | Mitigation: activate restarts only the preview service (scoped classification: CAM1_RELAY_CHANGED=NO, AI_WORKER_CHANGED=NO); scheduled window; sourceOnDemand semantics make recovery immediate | Validation: service active + :8555 listener probe post-activate | Residual risk: seconds-scale preview gap for road analytics during restart | Owner: delivery-orchestrator | Status: OPEN
- RISK-003 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the change strictly reduces exposed surface; auth rule block byte-identical (R-5) and verify-preview-auth gates it on-box | Validation: verify-preview-auth output in tx evidence; golden auth-block pin in tests | Residual risk: out-of-repo consumers of the disabled servers would lose them; none observed (0 established peers) — accepted by owner via issue decision 2026-10-16 | Owner: delivery-orchestrator | Status: OPEN

## Test design

- TEST-001 | Covers: R-1, R-2, R-3 | Level: unit | Priority: P0 | Evidence: updated golden byte-config + positive five-toggle pin in tests/test_mediamtx_preview_relay.py (focused green)
- TEST-002 | Covers: R-3, R-4 | Level: unit | Priority: P1 | Evidence: legacy-parity oracle and re-render byte-identity tests updated, legacy 9-mode structural pin green
- TEST-003 | Covers: R-5 | Level: unit | Priority: P1 | Evidence: auth-rule block byte-identity assertions unchanged and green; verify-preview-auth drift tests untouched
- TEST-004 | Covers: AC-004 | Level: runtime-manual | Priority: P1 | Evidence: lane-B sysadmin tx evidence on #522 (ss probe, service status, digests, mediamtx --version)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

On-box application of the merged renderer (lane-B sysadmin prepare→activate
tx after the lane-A worker deploy of the exact merged head).

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no tx started; repo change stays unapplied | Retry: after fresh DEPLOY-HANDOFF | Rollback: not applicable (no mutation) | Evidence: lane-A deploy of the exact merged head completed (deploy-authorized run) + canonical issue #522 Outcome Contract present
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: current active relay config untouched | Retry: yes after evidence re-read | Rollback: not applicable | Evidence: `mediamtx --version`, current CONFIG/UNIT/CATALOG digests, `ss -tlnp | grep 8892` pre-state recorded on #522
- TX-003 | Stage: MUTATION | Mutation: YES | Mutation detail: prepare writes new 0600 candidates; activate swaps active/mediamtx.yml + unit and restarts the preview service | Failure disposition: CONDITIONAL | State after failure: digest-bound candidates staged; active/ and unit unchanged on any prepare failure; on activate failure the service restart is gated by is-active and the previous active config remains authoritative | Retry: one bounded retry after root-cause read | Rollback: activate with the previous digest triple (backups/candidates) restores byte-identical prior state | Evidence: prepare/activate outputs with CONFIG_SHA256/UNIT_SHA256/SANITIZED_CATALOG_SHA256
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: new config active but tx not accepted; rollback executed | Retry: after remediation | Rollback: as TX-005 | Evidence: ss probe: no :8892 on preview PID; :8555 present; systemctl is-active; verify-preview-auth PASS
- TX-005 | Stage: STATE-COMMIT | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: previous active config already authoritative; candidates retained for re-activate | Retry: yes after evidence | Rollback: activate with previous digests | Evidence: activate output (SERVICE_RESTARTED, listener probe) relayed in lane-B handoff result
- TX-006 | Stage: HOUSEKEEPING | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: runtime correct; stale dated inventory backup may remain for the next window | Retry: next box session | Rollback: not applicable (removal of backups/inventory.json.stale-2026-10-16 per no-accumulation protocol) | Evidence: rm + ls in tx log
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime correct; evidence gap closes on next session | Retry: yes | Rollback: not applicable | Evidence: #522 comment with digests + ss output; JOURNAL entry
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: previous digest-bound active config restored, service active | Retry: one bounded retry then hold for owner decision | Rollback: cp of dated backups + activate with previous digests | Evidence: pre-state digests recorded at TX-002 (rollback `ready_not_used` unless triggered)
