# Implementation Plan: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Issue: #178
- Status: Ubuntu updater/legacy-control rollback remediation validation

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

The VPS contour is now runtime-accepted at exact source `e2a4f39eab80849882a42cf6e892bba127223649`. The remaining parent outcome is the Ubuntu installation and runtime-manual stop/start + HLS continuity proof.

Ubuntu release preparation and activation remain repository-owned server-pull operations. `update-exact.sh` stages the exact requested SHA, uses `verify_quality_status.py --workflow-file quality-integration.yml`, binds the release to the immutable shared runtime, and mutates systemd only when `--activate` is explicit. The real current baseline `efdbdfd9612d425bf34a81384298e091de06ec15` uses runtime `a9a9aaccd97e5c824ccc568504ad146936a4a69b5f8fe1ff36451ecd7317f88b` and predates `sea-speed-worker-control.service`.

Control-service topology is therefore part of exact operational state. Forward activation to a modern release may introduce the independent control unit, but a failed activation must restore a legacy baseline to no control unit. Explicit rollback must likewise distinguish modern targets from legacy targets rather than assuming every release has control components.

## Decisions

### D-001 - Direct VPS-to-Ubuntu private agent

- Decision: VPS FastAPI calls a dedicated RFC1918 Ubuntu HTTP control agent directly over ZeroTier.
- Reason: the browser remains unaware of the Ubuntu host and no browser SSH/arbitrary command path exists.

### D-002 - Existing bearer boundary

- Decision: private VPS-to-Ubuntu control reuses the protected `SEA_SPEED_API_TOKEN` and fixed private origin.
- Reason: no new credential lifecycle or browser-carried secret is introduced.

### D-003 - Literal service allowlist

- Decision: the agent exposes only fixed status/start/stop paths and always targets literal `sea-speed-worker.service`.
- Reason: worker control must not become generic remote execution.

### D-004 - Desired state owns intentional stop

- Decision: persist operator desired state independently from worker heartbeat/systemd observation.
- Reason: deployment and rollback must distinguish intentional stop from failure.

### D-005 - Live media is a separate failure domain

- Decision: worker-control source never invokes or reconfigures MediaMTX, camera relay, HLS routes or live-camera controls.
- Reason: Camera 1 live playback must remain independent of AI worker state.

### D-006 - Fixed control protocol marker

- Decision: successful agent responses include `sea_speed_worker_control_v1` and VPS rejects a missing/mismatched marker.
- Reason: independently deployed VPS/Ubuntu contours fail closed on incompatible control versions.

### D-007 - First-class Ubuntu release artifact

- Decision: deterministic exact-artifact tooling carries a release-specific `ubuntu-worker` archive while retaining quality-evidence compatibility for `vps`/legacy `edge`.
- Reason: release-manifest v2 requires exact Ubuntu provenance.

### D-008 - Canonical VPS origin-health identity is port 8010

- Decision: VPS deployment/rollback health uses `http://127.0.0.1:8010/api/health`.
- Reason: run #25 proved the former 8000 default was a false-negative.

### D-009 - Pipefail-safe first-parent admission

- Decision: Deploy VPS uses full-consumption first-parent matching instead of `git rev-list | grep -q` under pipefail.
- Reason: run #26 proved the old pipeline could reject a valid first-line match.

### D-010 - Stale release pruning is best-effort after verified persistence

- Decision: VPS current/previous releases are protected and older-release removal failures only warn after verified state persistence.
- Reason: run #27 proved stale permissions are housekeeping, not candidate health.

### D-011 - Ubuntu quality verification uses the verifier's actual workflow-file CLI

- Decision: `update-exact.sh` calls `verify_quality_status.py` with `--workflow-file quality-integration.yml`; focused tests execute the verifier `--help` parser surface and forbid the unsupported `--required-name` caller.
- Reason: the first Ubuntu production preparation attempt stopped before mutation because CI had asserted a caller argument that the exact verifier did not implement.
- Alternatives rejected: add a redundant `--required-name` compatibility alias to the verifier, bypass exact quality verification, or manually create a quality marker.

### D-012 - Control-service presence/absence is exact rollback state

- Decision: updater and explicit rollback snapshot whether the current control unit exists and, when present, its enabled/active state. Failed forward activation restores that exact topology. A legacy rollback target with no control components explicitly stops/disables/removes a newer control service and verifies absence; partial target control components fail closed.
- Reason: the real accepted Ubuntu baseline predates the control service. Restoring only the worker unit would leave newly introduced runtime authority behind and would not be an exact rollback.
- Alternatives rejected: require a control unit on every historical target, leave a modern control unit running after legacy rollback, manually clean systemd after failure, or broaden rollback to arbitrary units.

## Affected contours

Parent feature runtime acceptance remains:
- VPS: ACCEPTED at `e2a4f39eab80849882a42cf6e892bba127223649`.
- Ubuntu Worker/relay: YES — pending exact source preparation/activation and worker-control acceptance.
- Windows AI Worker: NO.

Current 9-path remediation:
- Derived Change Contract production impact: Ubuntu Worker/relay.
- VPS deployment: NOT REQUIRED.
- Ubuntu worker/relay update: REQUIRED after exact-green merge and fresh exact-SHA production authorization.
- Windows worker update: NOT REQUIRED.
- Production safety envelope: REQUIRED.
- API/event/state/storage schema impact: NONE.
- Security impact: NONE — no new browser/M2M/service authority; rollback removes unintended new control authority when returning to legacy state.
- Destructive/data migration impact: NO.
- Other high-risk trigger: YES — production update/rollback and systemd control-topology semantics change.

## Validation

- `tests/test_ubuntu_worker_exact_updater.py`: shell syntax, exact-main admission, real verifier `--help` compatibility, supported `--workflow-file` caller, forbidden `--required-name`, shared-runtime binding, desired-state preservation, target control completeness, legacy no-control automatic restoration and active-marker ordering.
- `tests/test_ubuntu_worker_rollback.py`: shell syntax, exact current/target/quality/runtime identity, modern-vs-legacy target control classification, partial-target rejection, exact current control snapshot, legacy target control removal, modern control exact-source verification and failed-target restoration.
- Documentation: exact update/rollback runbooks describe the production quality CLI and legacy/modern topology semantics without secrets.
- Existing product/media/security tests remain authoritative and are re-run by aggregate Quality integration.
- End-to-end source: exact PR Validation + aggregate Quality integration on one final 9-path head.
- Runtime-manual after merge: fresh exact-SHA production authorization, server-pull preparation from an exact trusted checkout, expected `RUNTIME_REUSED` for unchanged runtime ID, activation, exact worker/control identity, then Stop -> HLS continuity -> Start -> HLS continuity.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: TECH | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: bind updater to the verifier's existing `--workflow-file` CLI and execute the real verifier parser surface in focused tests | Validation: tests/test_ubuntu_worker_exact_updater.py plus exact-head CI | Residual risk: future caller/verifier drift must fail focused CI before production | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: snapshot legacy/modern control topology before mutation and restore exact presence/enabled/active state on failed activation | Validation: updater topology regression plus read-only preflight before production activation | Residual risk: physical systemd state can still diverge outside repository control and therefore must be re-read before mutation | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: explicit rollback classifies target control capability, removes control for legacy targets, requires exact active control for modern targets and rejects partial components | Validation: tests/test_ubuntu_worker_rollback.py plus separately authorized runtime rollback evidence if exercised | Residual risk: hosted CI cannot execute real systemd on the production host | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: DATA | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: no shared config/model/dataset/output/release/runtime deletion is introduced; only the fixed control-unit file may be removed when exact target topology requires absence | Validation: source regression assertions and exact diff review | Residual risk: operator-controlled files outside the declared install/systemd paths are not modified by this remediation | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-002, AC-003, AC-004, AC-005, AC-006 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py
- TEST-002 | Covers: AC-001, AC-010 | Level: integration | Priority: P1 | Evidence: tests/test_frontend_contract.py
- TEST-003 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_systemd.py
- TEST-004 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py
- TEST-005 | Covers: AC-009 | Level: integration | Priority: P0 | Evidence: tests/test_sea_speed_auth_v1.py
- TEST-006 | Covers: AC-011 | Level: end-to-end | Priority: P0 | Evidence: exact-head PR Validation + Quality integration
- TEST-007 | Covers: AC-012 | Level: runtime-manual | Priority: P0 | Evidence: production service status plus continuous Camera 1 HLS playback before/during/after stop/start, recorded on Issue #178
- TEST-008 | Covers: AC-013 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py
- TEST-009 | Covers: AC-014 | Level: end-to-end | Priority: P0 | Evidence: tests/quality/test_quality_architecture.py plus Quality integration exact-artifact/release-evidence jobs
- TEST-010 | Covers: AC-015 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_origin_health.py plus accepted VPS runtime evidence
- TEST-011 | Covers: AC-016 | Level: integration | Priority: P0 | Evidence: tests/quality/test_quality_architecture.py plus successful later deployment admission
- TEST-012 | Covers: AC-017 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_origin_health.py plus accepted VPS deployment evidence
- TEST-013 | Covers: AC-018,RISK-001 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py executing verifier CLI help/parser and caller source contract
- TEST-014 | Covers: AC-019,RISK-002,RISK-003,RISK-004 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #178 records the failed pre-mutation Ubuntu preparation, real baseline source/runtime/control topology, adjacent-stage rollback finding and exact 9-path remediation authorization.
- Specification impact: adds FR-018/FR-019, AC-018/AC-019, NFR-010 and production-learning #5 without changing operator/media/AI behavior.
- Plan impact: adds D-011/D-012, current Ubuntu risk/test design and the complete eight-stage Ubuntu deployment transaction audit.
- Tasks impact: active source gate becomes the exact 9 updater/rollback/test/doc/SDD paths, then a fresh Ubuntu production gate before runtime continuation.
- Authorization impact: fresh `OUTCOME APPROVED` was obtained for the exact 9-path remediation; all older production authorizations are stale for the remediation merge SHA.
- Follow-up: merge only an exact-green 9-path head, verify post-merge push/main quality, obtain a fresh production authorization/fingerprint, prepare the exact release from an exact trusted checkout, require runtime reuse, activate, then execute bounded Stop/HLS/Start/HLS acceptance.

## Deployment transaction audit

This audit models the pending Ubuntu exact-release preparation/activation transaction and the explicit rollback path against the currently observed legacy no-control baseline.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: active worker source/runtime/control topology unchanged | Retry: correct exact SHA/main history/quality CLI or production envelope, then retry from a trusted exact checkout | Rollback: NOT REQUIRED because systemd/release mutation has not started | Evidence: exact SHA ancestry, supported quality verifier result, authorization and source artifact/provenance evidence
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: preparation may have created an immutable target release/quality marker but active worker/control topology remains unchanged until activation | Retry: verify prepared release/runtime plus actual active marker, worker ExecStart and control presence/enabled/active state before activation | Rollback: NOT REQUIRED for preparation-only state; prepared immutable release may remain | Evidence: source-commit, quality-approved, runtime-id, RUNTIME_REUSED/CREATED output and read-only active topology
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: target worker/control unit files or enablement may be partially installed while active marker still identifies previous release | Retry: only after automatic restoration proves previous exact worker/runtime/control topology or after separately authorized recovery | Rollback: restore backed-up previous worker unit and exact previous control presence/enabled/active state | Evidence: updater install/control/worker logs and pre-mutation unit backups
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: target is not accepted; automatic restoration is attempted while active marker remains previous source | Retry: resolve control/worker/runtime progression failure, confirm actual restored state read-only, then issue a new authorized activation attempt | Rollback: exact previous worker/runtime plus legacy-or-modern control topology and desired worker state | Evidence: control ExecStart/status, worker ExecStart/status, runtime progression or intentional-stopped gate
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: if active-source marker cannot be atomically written after verification, target acceptance is unresolved and further mutation stops | Retry: read actual service/unit/marker state before any retry | Rollback: use previous exact source/runtime/topology identified by pre-mutation evidence when recovery is required | Evidence: atomic active-source-commit write after all target verification
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: temporary staging/backups may remain but protected releases/runtimes/shared data and accepted service identity must not be deleted | Retry: remove root-only temporary updater artifacts independently when safe | Rollback: NOT REQUIRED solely for temporary-file cleanup failure | Evidence: cleanup trap scope plus source assertions forbidding release/runtime/shared deletion
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be healthy but Issue #178 acceptance remains incomplete until exact source/runtime/control/HLS evidence is recorded | Retry: recollect sanitized read-only evidence without unnecessary runtime mutation | Rollback: decide from actual runtime state, not evidence-copy failure alone | Evidence: prepared/activated outputs, systemd identities, runtime ID, worker state and continuous HLS observations
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if exact previous topology or explicit target rollback cannot be verified, runtime state is unknown and automated mutation stops | Retry: recover actual worker/control/source/runtime state read-only and use separately authorized recovery | Rollback: modern target requires exact active control; legacy target requires control service absent; current source marker changes only after target acceptance | Evidence: ROLLBACK_ABORTED/RESTORED or ROLLED_BACK output plus exact worker/control/source/runtime readback

- Adjacent-stage review: COMPLETE
- Production-learning root cause: Ubuntu `update-exact.sh` and `verify_quality_status.py` had an unexecuted CLI contract mismatch: CI asserted the unsupported `--required-name` string instead of exercising the real verifier parser, so production preparation failed before release mutation.
- Production-learning adjacent-stage findings: admission must execute the real quality-verifier interface; preparation remains safe before activation; the real baseline has no control unit; forward installer introduces/enables a control unit; automatic rollback must remove that unit when restoring a legacy baseline; explicit rollback must classify modern versus legacy targets and reject partial control components; active-source commit remains post-verification state commit; shared releases/runtimes/data remain protected; final evidence must separately prove HLS continuity across worker stop/start.

## Rollout and rollback

- Source rollout: merge only the exact green 9-path remediation head after fresh base/head/scope/review verification and expected-head protection.
- Production checkpoint: verify exact push/main Quality integration for the merge SHA, compute the current authorization fingerprint with Ubuntu Worker/relay `REQUIRED`, and obtain fresh `PRODUCTION APPROVED <merge-sha>` before any worker filesystem/systemd mutation.
- Preparation: use a short server-pull bootstrap to an exact trusted checkout of the authorized merge SHA, then run that exact checkout's `update-exact.sh` without `--activate`; require exact quality success and expected runtime reuse when the runtime definition remains unchanged.
- Activation: re-read active source/runtime/control topology, then run the prepared exact updater with `--activate`; require exact control source, exact worker source/runtime and runtime progression while desired state is running.
- Automatic rollback: any failed activation before active marker commit restores the previous exact worker/runtime plus previous control presence/enabled/active state; the currently observed legacy baseline therefore returns to no control service.
- Explicit rollback: modern targets restore and verify exact control service; legacy targets stop/disable/remove the control service and verify absence. Partial control targets fail closed.
- Product acceptance: after activation, use the Operator control path for Stop worker while Camera 1 HLS remains playable, then Start worker while HLS remains playable and worker progression resumes.
- Camera relay/HLS has no source change to roll back.
- Production mutation during this source remediation delivery: NONE.

## Runtime feedback

- Actual architecture after acceptance: VPS accepted; Ubuntu pending the current updater/rollback remediation and final production acceptance.
- Observed Ubuntu baseline: `efdbdfd9612d425bf34a81384298e091de06ec15` + runtime `a9a9aaccd97e5c824ccc568504ad146936a4a69b5f8fe1ff36451ecd7317f88b`, worker active/enabled, control unit absent.
- Production learning #5: preparation of `1d0aa285d5f30165980c4d628a97da7e23b66ffe` failed at the quality-verifier CLI before `install-manual.sh`; no activation occurred. Adjacent-stage audit found legacy-control rollback topology was not exact even if the CLI alone were fixed.
- Corrective source task: exact 9-path remediation implements actual verifier CLI compatibility and legacy/modern control-topology rollback semantics with focused regression evidence and updated operator runbooks.
- Deferred work: exact-head CI/merge, post-merge quality, fresh production authorization, exact preparation/activation, worker control protocol/status check, Stop/HLS/Start/HLS runtime evidence, then final Issue #178 completion decision.
