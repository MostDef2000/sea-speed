# Implementation Plan: #739 — Deploy preserves the protected recorder configuration

- Specification: specs/739-config-preserve/spec.md
- Issue: #739
- Status: Implemented on branch (tests owned by the test worker)

## Architecture

Three small, independent changes on the Ubuntu worker/relay contour:

1. `deploy/worker/ubuntu/configure-analytics-profiles.py` gains a module-level recorder
   contract (`RECORDER_PREFIX`, `RECORDER_DEFAULTS`, `RECORDER_BOUNDS`) and
   `preserved_recorder_env(source)`, which returns the complete validated recorder block for
   one protected env file. `main()` spreads that block into the Water dict (from `worker.env`)
   and into the Road dict (from the existing `road-worker.env`) at the same point where the
   existing `_preserve_float`/`existing_road` values are applied. Value validators return the
   safe default on every malformed input, so the deploy path stays crash-free. The reconcile
   prints only `RECORDER_CONFIG_PRESERVED=YES`.
2. `worker/recorder.py` changes `DEFAULT_DESTINATION` to the RELATIVE
   `root@10.123.239.127:./`; the existing `SEA_SPEED_RECORDER_DESTINATION` read path is
   untouched, so an env override still wins.
3. The deploy transaction `deploy-authorized.sh` provisions
   `shared/runtime/recorder-spool` and `shared/road-runtime/recorder-spool` (owner = service
   user, mode 750, symlink refused, absent runtime root skipped) between the protected-config
   reconcile and `update-exact.sh` activation. `install-systemd.sh` creates the same
   directories during initial commissioning and includes them in its existing 750 pass.

No analytics key, secret rule, permission check, runtime pin or deploy authorization changes.

## Decisions

### D-001 - Preserve inside the reconcile, not in a new config store

- Decision: extend the existing configure step with a validated recorder block instead of
  introducing a side file, an env-merge helper or a second source of truth for protected
  configuration.
- Reason: the wipe happens exactly here (`write_env` is called only from this script for these
  two files); a single validated spread restores the invariant with the least surface.
- Alternatives rejected: a separate `recorder.env` fragment (new load path, new failure mode,
  `EnvironmentFile` churn); teaching the analytics whitelist the recorder keys (they are not
  analytics profile values and Road has no analytics default for them).

### D-002 - Conservative validation with safe fallback, never a deploy failure

- Decision: known keys are re-validated on every reconcile against literals and the bounds
  `worker/recorder.py` applies; an invalid or out-of-range preserved value becomes the
  recorder default, and no conversion error escapes.
- Reason: a stale or hand-edited protected value must not block analytics deploys, and a
  value outside the recorder's own bounds would be silently clamped or rejected there anyway.
- Alternatives rejected: clamping (hides intent, and a typo becomes a surprising runtime
  value); raising (turns a recorder typo into a failed worker deploy).

### D-003 - Relative destination in both the validator and the code default

- Decision: the only destination the reconcile writes (preserved or fallback) and the only
  code default is `root@10.123.239.127:./`. Absolute, empty, `..`-bearing or multi-colon
  values are rejected.
- Reason: restricted `rrsync -wo /mnt/fleet-backup/sea-speed` already pins the root; an
  absolute remote path is appended to it and doubled, which is the observed production
  failure.
- Alternatives rejected: keeping the absolute default and only rewriting it on reconcile
  (a wiped or hand-edited config then fails again); stripping the prefix from absolute paths
  in the recorder (silently guesses a root the recorder does not own).

### D-004 - Spool provisioning in the deploy transaction and commissioning

- Decision: create each spool directory in `deploy-authorized.sh` after a successful reconcile
  and before `update-exact.sh`, and during initial commissioning in `install-systemd.sh`.
- Reason: the deploy path never runs `install-systemd.sh`, and `update-exact.sh` restarts the
  units immediately after; the directory must exist before that start. Owner/mode mirror the
  existing 750 convention for runtime roots, and only an absent runtime root is skipped.
- Alternatives rejected: relying on the recorder's own `mkdir` (the observed symptom was a
  missing spool, and a read-only or wrongly-owned WorkingDirectory would fail at runtime);
  touching the service templates (no new capability needed).

## Affected contours

- Repository: `deploy/worker/ubuntu/configure-analytics-profiles.py`,
  `deploy/worker/ubuntu/deploy-authorized.sh`, `deploy/worker/ubuntu/install-systemd.sh`,
  `deploy/worker/ubuntu/worker.env.example`, `deploy/worker/ubuntu/road-worker.env.example`,
  `worker/recorder.py`, this SDD trio.
- Ubuntu worker/relay: REQUIRED — next deploy reconciles the recorder block and provisions the
  spool directories on the GPU box.
- VPS: NONE.
- Windows worker/AI: NONE.
- Public interfaces: none; protected env-file format gains no new key and loses none.

## Validation

- Static: `python3 -m py_compile` on both changed Python files, `bash -n` on both changed
  shell scripts, `python3 -m ruff check --config scripts/quality/ruff.toml` on both Python
  files, `python3 scripts/ci/validate_sdd.py`.
- Unit/integration (test worker): reconcile over temp install roots — preservation, per-file
  independence, invalid-value matrix, destination rejection, idempotent re-run, no value in
  stdout; `RecorderConfig` relative default and env override; spool provisioning behaviour.
- Runtime acceptance: deploy the merged main SHA; confirm the six recorder symptoms are gone
  (recorder start line with relative destination, spool exists 750 owned by `sea-speed`, no
  rrsync double-path error) without any manual host command.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: preserved values are validated against the recorder's own literals/bounds and always fall back to safe defaults; the reconcile never raises for recorder input | Validation: negative matrix TEST-003 over a temp install root | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the destination validator rejects absolute/`..`/multi-colon targets and both the fallback and the code default are the same relative value; the real deploy keeps the existing config backup/restore transaction | Validation: TEST-001 destination cases plus TEST-004 code default; deploy TX-003 rollback evidence | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-003 | Category: SEC | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the reconcile prints only status words; values stay inside the same mode-600 files; no new file or permission surface | Validation: TEST-003 stdout/mode assertions plus implementation probe output `SECRETS_DISPLAYED=NO` | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: the destination default and the numeric bounds are mirrored from `worker/recorder.py`; a drift guard test compares the code default with the configure fallback | Validation: TEST-004 drift assertion owned by the test worker | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001, AC-003 | Level: unit | Priority: P0 | Evidence: test worker adds reconcile tests over temp install roots (preserve all twelve keys per file, absolute destination rewritten, repeat run idempotent)
- TEST-002 | Covers: AC-001, AC-002 | Level: unit | Priority: P0 | Evidence: test worker adds per-file independence and malformed-value matrix rows (enabled/source literals, out-of-bounds numerics, unknown extras preserved)
- TEST-003 | Covers: AC-002, AC-007 | Level: integration | Priority: P0 | Evidence: test worker runs the reconcile end-to-end in a temp root and asserts exit 0, mode 600, no recorder value in stdout
- TEST-004 | Covers: AC-004, AC-005 | Level: unit | Priority: P1 | Evidence: test worker asserts `RecorderConfig` relative default and env override, and the configure fallback equals the recorder default
- TEST-005 | Covers: AC-005, AC-006 | Level: runtime-manual | Priority: P1 | Evidence: post-deploy acceptance on the GPU box: `stat` of both spool directories (owner `sea-speed`, mode 750) and the recorder journal start line with the relative destination

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: SSH `known_hosts` provisioning for the service user remains a separate issue and is not part of the admitted scope.

## Deployment transaction audit

This audit models the Ubuntu worker/relay rollout of the recorder-preserving reconcile
(`deploy/worker/ubuntu/**`, `worker/recorder.py`). The deploy target is the exact green main
SHA produced by this PR, activated through `.github/workflows/deploy-ubuntu-worker.yml` under
the standing production delegation policy after the protected transaction proves exact
current-main first-parent source. Runtime acceptance is planned, not yet performed.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: the host stays on the release recorded in `shared/runtime/active-source-commit` and no protected file is touched | Retry: re-enter the protected deploy workflow only with an exact first-parent main SHA, green Quality evidence on that SHA and an allowed policy decision | Rollback: NOT REQUIRED before any mutation | Evidence: exact main SHA, green Quality integration run and standing-delegation policy decision for that SHA
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: config backups may exist under the updater root while both protected env files and services remain on the previous release | Retry: verify the protected env modes and service states, then re-enter the deploy transaction | Rollback: backups are removed by the transaction cleanup; active release is unchanged | Evidence: `PROTECTED_CONFIG_BACKUP=PASS` and captured pre-deploy service states
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: a protected env file may be rewritten or the spool directory may be partially provisioned while services still run the previous release | Retry: only after the transaction either restores the protected backup or proves a coherent reconciled state | Rollback: `restore_protected_config` reinstalls the backup with the recorded owner and mode 600 and the pre-deployment service state is restored | Evidence: `PROTECTED_CONFIG_RECONCILED=YES`, `RECORDER_CONFIG_PRESERVED=YES`, `RECORDER_SPOOL_READY=YES`
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: the new release may be active but not accepted; recorder configuration and spool readiness are unproven | Retry: resolve identity or post-activation check failure after the actual active release is known | Rollback: `verify_active_target` failure triggers the protected previous-release rollback with protected config restore | Evidence: exact `ExecStart` identity, service states, protected env mode 600 and spool ownership/mode checks
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: the deployment manifest is missing or incomplete and completion is forbidden | Retry: verify the active release identity before writing the manifest again | Rollback: the previous active release remains the declared rollback target | Evidence: `deployment-manifest-ubuntu-worker.json` with `runtime_verified` state and the reconciled-config check
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: the verified runtime stays valid while stage directories or stale backups may remain | Retry: remove leftover stage artifacts on the next deploy | Rollback: NOT REQUIRED solely for housekeeping failure | Evidence: transaction cleanup trap output and updater-root listing
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: the runtime may be healthy while recorder acceptance evidence is incomplete | Retry: recollect the recorder start line and spool `stat` probes without redeploying when the SHA is unchanged | Rollback: decide from actual runtime behaviour, not evidence upload alone | Evidence: recorder journal start line with relative destination, spool `stat` output, absence of the rrsync double-path error
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous release cannot be restored and verified, automated mutation stops and the actual host state must be recovered | Retry: read active marker, runtime id and service evidence before any new mutation | Rollback: no guessed target; restore the previous exact release recorded in the active marker and its protected config backup | Evidence: rollback-exact logs, restored config, and verified service states

## Rollout and rollback

- Rollout: normal Ubuntu worker deploy of the merged SHA; the reconcile preserves the recorder
  block, rewrites a legacy absolute destination to the relative default and provisions the
  spool directories before services restart.
- Rollback: revert this PR's merge or run the protected previous-release rollback; the
  protected config backup restores the pre-deploy env files, so reverted code and config stay
  consistent. The relative destination remains valid for both old and new recorder code.

## Runtime feedback

- Actual architecture after acceptance: expected to match the plan.
- Differences from plan: NONE YET
- Deferred cleanup: SSH `known_hosts` provisioning for the service user (separate issue).
