# Implementation Plan: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Issue: #178
- Status: Ubuntu updater cleanup-exit remediation validation

## Architecture

The product control path remains deliberately separate from Camera 1 media transport:

```text
Authenticated browser
  -> existing Authentik-protected /sea-speed/api/**
  -> VPS FastAPI fixed worker-control routes
  -> RFC1918 Ubuntu control-agent origin over ZeroTier
  -> bearer token validation
  -> fixed protocol marker sea_speed_worker_control_v1
  -> fixed systemctl operation for sea-speed-worker.service only
```

The VPS contour is runtime-accepted at exact source `e2a4f39eab80849882a42cf6e892bba127223649`. Ubuntu remains pending final exact-source activation and Stop/HLS/Start/HLS acceptance. The current accepted Ubuntu baseline is `efdbdfd9612d425bf34a81384298e091de06ec15`, immutable runtime `a9a9aaccd97e5c824ccc568504ad146936a4a69b5f8fe1ff36451ecd7317f88b`, worker active/enabled, and no worker-control unit.

Ubuntu release preparation/activation remains repository-owned server-pull. `update-exact.sh` stages one exact SHA, verifies the exact push/main quality workflow, binds the release to the immutable runtime, and only mutates systemd with explicit `--activate`. The cleanup trap is housekeeping around that transaction and must never redefine the primary operation result.

## Decisions

### D-001 - Direct VPS-to-Ubuntu private agent
- Decision: VPS FastAPI calls a dedicated RFC1918 Ubuntu HTTP control agent directly over ZeroTier.
- Reason: the browser never receives Ubuntu host access and no browser SSH path exists.

### D-002 - Existing bearer boundary
- Decision: private VPS-to-Ubuntu control reuses the protected `SEA_SPEED_API_TOKEN` and fixed private origin.
- Reason: no new credential lifecycle is introduced.

### D-003 - Literal service allowlist
- Decision: the agent exposes only fixed status/start/stop paths for literal `sea-speed-worker.service`.
- Reason: worker control must not become generic remote execution.

### D-004 - Desired state owns intentional stop
- Decision: persist operator desired state independently from heartbeat/systemd observation.
- Reason: maintenance must distinguish intentional stop from failure.

### D-005 - Live media is a separate failure domain
- Decision: worker-control source never invokes or reconfigures MediaMTX, camera relay or HLS lifecycle.
- Reason: Camera 1 playback must remain independent of AI worker state.

### D-006 - Fixed control protocol marker
- Decision: successful agent responses include `sea_speed_worker_control_v1`; VPS rejects mismatch.
- Reason: independently deployed contours fail closed on incompatibility.

### D-007 - First-class Ubuntu release artifact
- Decision: deterministic exact-artifact tooling carries `ubuntu-worker` release provenance.
- Reason: Ubuntu runtime delivery requires exact artifact identity.

### D-008 - Canonical VPS origin health is 8010
- Decision: VPS deployment/rollback health uses `http://127.0.0.1:8010/api/health`.
- Reason: production run #25 disproved the former 8000 default.

### D-009 - Pipefail-safe first-parent admission
- Decision: Deploy VPS fully consumes first-parent history instead of `git rev-list | grep -q` under pipefail.
- Reason: production run #26 exposed SIGPIPE false-negative behavior.

### D-010 - Stale VPS pruning is best-effort
- Decision: current/previous VPS releases are protected and stale cleanup warns after verified persistence.
- Reason: run #27 proved pruning is housekeeping, not candidate health.

### D-011 - Ubuntu quality verification uses the real verifier CLI
- Decision: `update-exact.sh` uses `--workflow-file quality-integration.yml` and focused tests execute verifier `--help`.
- Reason: the first Ubuntu preparation failed on the unsupported `--required-name` argument.

### D-012 - Control-service presence/absence is rollback state
- Decision: updater/rollback preserve exact modern-or-legacy control-unit topology and reject partial targets.
- Reason: the real accepted baseline predates worker control.

### D-013 - Cleanup preserves the primary updater result
- Decision: `cleanup()` captures `$?` on entry, attempts staging/optional backup/marker removal best-effort, and returns the captured status. Focused regression executes the real function as an `EXIT` trap under `set -euo pipefail`.
- Reason: authorized preparation of `6b948ef...` completed all preparation gates but exited 1 because an empty optional cleanup predicate became the trap result under `set -e`.
- Alternatives rejected: ignore updater exit status in the operator wrapper, remove `set -e`, suppress only the final predicate, or manually accept preparation despite a nonzero process result.

## Affected contours

Parent feature runtime acceptance:
- VPS: ACCEPTED at `e2a4f39eab80849882a42cf6e892bba127223649`.
- Ubuntu Worker/relay: YES — pending corrected exact source preparation/activation and runtime acceptance.
- Windows AI Worker: NO.

Current 5-path remediation:
- Derived Change Contract production impact: `UBUNTU_WORKER`.
- VPS deployment: NOT REQUIRED.
- Ubuntu worker/relay update: REQUIRED after exact-green merge and fresh exact-SHA production authorization.
- Windows worker update: NOT REQUIRED.
- Production safety envelope: REQUIRED.
- Security impact: NONE.
- API/event/state/storage schema impact: NONE.
- Destructive/data migration impact: NO.
- Other high-risk trigger: YES — production updater exit/housekeeping semantics affect safe admission to activation.

## Validation

- `tests/test_ubuntu_worker_exact_updater.py`: shell syntax; exact-main admission; real verifier CLI compatibility; shared runtime binding; control topology; and executable cleanup/EXIT semantics.
- Cleanup regression extracts the actual `cleanup()` implementation from `update-exact.sh` and runs it through an `EXIT` trap under `set -euo pipefail` for primary status 0 and 37, with both successful and deliberately failing cleanup operations.
- Existing worker-control, media, API, security, systemd and rollback tests remain authoritative through aggregate Quality integration.
- Exact source delivery requires PR Validation + aggregate Quality integration on one final 5-path head.
- Runtime-manual after merge requires a fresh production envelope, expected `RUNTIME_REUSED`, exact activation identity, then Stop -> HLS continuity -> Start -> HLS continuity.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: TECH | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: bind updater to the real quality-verifier CLI and execute its parser surface | Validation: tests/test_ubuntu_worker_exact_updater.py | Residual risk: future interface drift must fail CI before production | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: preserve exact legacy/modern control topology on activation failure and rollback | Validation: updater/rollback regression plus read-only runtime preflight | Residual risk: physical systemd state still requires runtime readback | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: cleanup captures and returns primary status while every cleanup operation is guarded best-effort | Validation: executable EXIT-trap cleanup regression with forced rm failures | Residual risk: failed temporary cleanup may leave root-only staging/backups for later housekeeping but cannot redefine deployment result | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: DATA | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: cleanup scope remains only root-only staging/unit-backup/control-backup/marker temp paths; releases/runtimes/shared state remain excluded | Validation: source assertions and exact diff review | Residual risk: local temporary artifacts may require later manual cleanup if filesystem removal fails | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-002,AC-003,AC-004,AC-005,AC-006 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py
- TEST-002 | Covers: AC-001,AC-010 | Level: integration | Priority: P1 | Evidence: tests/test_frontend_contract.py
- TEST-003 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_systemd.py
- TEST-004 | Covers: AC-008,AC-018,AC-019 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py
- TEST-005 | Covers: AC-009 | Level: integration | Priority: P0 | Evidence: tests/test_sea_speed_auth_v1.py
- TEST-006 | Covers: AC-011 | Level: end-to-end | Priority: P0 | Evidence: exact-head PR Validation + Quality integration
- TEST-007 | Covers: AC-012 | Level: runtime-manual | Priority: P0 | Evidence: production service status plus continuous Camera 1 HLS playback before/during/after stop/start
- TEST-008 | Covers: AC-013 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py
- TEST-009 | Covers: AC-014 | Level: end-to-end | Priority: P0 | Evidence: tests/quality/test_quality_architecture.py plus exact-artifact/release-evidence jobs
- TEST-010 | Covers: AC-015,AC-017 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_origin_health.py plus accepted VPS evidence
- TEST-011 | Covers: AC-016 | Level: integration | Priority: P0 | Evidence: tests/quality/test_quality_architecture.py plus accepted VPS admission evidence
- TEST-012 | Covers: AC-020,RISK-003,RISK-004 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py executable cleanup EXIT-trap cases

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #178 records production learning #6: authorized preparation reached `RUNTIME_REUSED`, exact release/quality preparation and `NOT_ACTIVATED`, then process exit became 1 in cleanup; activation did not run.
- Specification impact: adds FR-020, AC-020, NFR-011 and runtime-learning #6 without changing operator/media/AI behavior.
- Plan impact: adds D-013, cleanup-specific risk/test evidence and updates the transaction audit housekeeping semantics.
- Tasks impact: active source gate becomes exact 5 paths for updater, executable regression and SDD synchronization before a fresh production envelope.
- Authorization impact: fresh `OUTCOME APPROVED` is recorded for this exact 5-path remediation; the production authorization for `6b948ef...` is stale for the remediation merge SHA.
- Follow-up: merge only an exact-green 5-path head, verify push/main quality/artifacts, obtain fresh production authorization, re-read the actual worker baseline/prepared state, prepare the new exact SHA with expected runtime reuse, then activate and finish Stop/HLS/Start/HLS acceptance.

## Deployment transaction audit

This audit models Ubuntu exact-release preparation/activation after production learning #6.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: active worker source/runtime/control topology unchanged | Retry: correct exact SHA, quality/provenance or production envelope then retry from trusted exact checkout | Rollback: NOT REQUIRED before release/systemd mutation | Evidence: exact SHA ancestry, exact push/main quality, authorization and provenance
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: immutable target release/quality marker may exist while active systemd/source state remains baseline | Retry: verify prepared release/runtime and re-read active topology before retry | Rollback: NOT REQUIRED for preparation-only state | Evidence: source-commit, quality-approved, runtime-id, `RUNTIME_REUSED` and active topology readback
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: target worker/control units may be partially installed while active marker remains previous source | Retry: only after automatic restoration proves the prior topology or separately authorized recovery | Rollback: restore previous worker/runtime plus exact previous control topology | Evidence: install/control/worker logs and root-only unit backups
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: target not accepted and automatic restoration is attempted while active marker remains previous source | Retry: resolve verification failure and confirm restored state read-only | Rollback: exact previous worker/runtime/control topology and desired worker state | Evidence: control/worker ExecStart, service states and runtime progression gate
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: unresolved if verified target cannot atomically write active-source marker; automated mutation stops | Retry: read actual service/unit/marker state before any retry | Rollback: use the previous exact source/runtime/topology from pre-mutation evidence when recovery is required | Evidence: active-source marker atomic write only after target verification
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: root-only staging/backups/temporary marker may remain, but primary updater status and accepted/prepared state are unchanged | Retry: remove leftover temporary artifacts independently when safe | Rollback: NOT REQUIRED solely for temporary cleanup failure | Evidence: cleanup captures `$?`, guards every removal best-effort, returns original status, and executable fault-path regression proves 0/nonzero preservation
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime/preparation may be healthy but Issue #178 acceptance remains incomplete until exact evidence is recorded | Retry: recollect sanitized read-only evidence without unnecessary mutation | Rollback: decide from actual runtime state, not evidence-copy failure alone | Evidence: updater outputs, source/runtime/control identities and HLS observations
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: unknown if exact previous/target topology cannot be verified; automated mutation stops | Retry: recover actual worker/control/source/runtime state read-only and use separately authorized recovery | Rollback: modern target requires exact active control; legacy target requires control absent; source marker changes only after acceptance | Evidence: `RESTORED`, `ACTIVATION_ABORTED` or `ROLLED_BACK` plus exact runtime readback

- Adjacent-stage review: COMPLETE
- Production-learning root cause: under `set -euo pipefail`, `update-exact.sh` `cleanup()` ended on `[[ -n "$marker_tmp" ]] && rm -f "$marker_tmp"`; in successful preparation optional temp variables were empty, so the EXIT trap returned 1 and converted a completed preparation process into failure.
- Production-learning adjacent-stage findings: admission and preparation were successful; no activation/systemd mutation started; prepared exact release and runtime reuse evidence remain valid as historical state only; the active marker/topology must be re-read before the next attempt; housekeeping must preserve primary success/failure and attempt all populated cleanup targets; outer orchestration must continue to trust process status rather than infer success from log strings; legacy-control rollback semantics from PR #186 remain unchanged and still require runtime verification before activation.

## Rollout and rollback

- Source rollout: merge only exact green 5-path remediation after fresh base/head/scope/review verification and expected-head protection.
- Production checkpoint: exact push/main Quality integration + exact artifact evidence for the merge SHA, then a fresh Ubuntu production fingerprint/authorization.
- Preparation: use exact target updater without `--activate`; require exact quality, `RUNTIME_REUSED` for unchanged runtime definition, preparation outputs, and process exit 0.
- Activation: re-read active source/runtime/control topology, then run exact updater with `--activate`; require exact control source, worker source/runtime and runtime progression.
- Automatic rollback: failed activation before marker commit restores previous worker/runtime/control topology; current legacy baseline returns to no control unit.
- Product acceptance: Stop worker while Camera 1 HLS remains playable, then Start worker while HLS remains playable and worker progression resumes.
- Production mutation during this source remediation lifecycle: NONE.

## Runtime feedback

- Actual architecture after acceptance: VPS accepted; Ubuntu pending cleanup-remediation source integration and final production acceptance.
- Observed Ubuntu baseline before preparation: `efdbdfd9612d425bf34a81384298e091de06ec15` + runtime `a9a9aaccd97e5c824ccc568504ad146936a4a69b5f8fe1ff36451ecd7317f88b`, worker active/enabled, control unit absent.
- Production learning #5: verifier CLI mismatch exposed legacy-control rollback topology debt; PR #186 remediated both before activation.
- Production learning #6: preparation of `6b948ef40a2e6d13c3a7fde8a63d7b4ef937176f` passed quality/runtime/release preparation and emitted `NOT_ACTIVATED`, but EXIT cleanup returned 1 because optional temp variables were empty under `set -e`.
- Current corrective source task: exact 5-path cleanup-status remediation with executable EXIT-trap fault cases.
- Deferred work: exact-head CI/merge, post-merge quality/artifact evidence, fresh production authorization, read-only runtime reconciliation, exact preparation/activation, control protocol/status check, Stop/HLS/Start/HLS evidence, then Issue #178 completion decision.
