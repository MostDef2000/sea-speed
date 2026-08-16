# Implementation Plan: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Issue: #178
- Status: VPS release-pruning remediation validation

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

The Ubuntu control agent remains a separate systemd service. The AI worker is the only controlled service; Camera relay/MediaMTX are not referenced by the control operation. The worker desired-state marker (`running|stopped`) remains independent of heartbeat freshness so exact updater/rollback semantics can preserve an intentional stop.

Release provenance remains as established by merged PR #180: quality evidence keeps `vps` and legacy `edge`, while the deterministic exact-artifacts manifest also carries a release-specific `ubuntu-worker` archive that release-manifest v2 can bind directly.

Merged PR #181 corrected the VPS origin-health verifier to the accepted Auth v1 FastAPI loopback origin `127.0.0.1:8010`. Merged PR #182 corrected the Deploy VPS first-parent admission false-negative without weakening first-parent membership. Deploy VPS run #27 then passed admission, quality, authorization, provenance, SSH, candidate origin health and all public smoke checks, but returned failure during post-verification cleanup because an older release tree was not removable by the deploy user.

The current correct-course change is VPS deployment hardening: current and previous releases remain the protected rollback pair, while deletion of any older release is best-effort housekeeping after verified state and deployment evidence are persisted. A stale-release permission failure must be visible as a warning but must not convert a verified deployment into a failed deployment.

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

- Decision: deterministic exact-artifact tooling carries a release-specific `ubuntu-worker` archive while retaining quality-evidence v1 compatibility for `vps`/legacy `edge`.
- Reason: release-manifest v2 requires exact Ubuntu provenance for the pending worker-control rollout.

### D-008 - Canonical VPS origin-health identity is port 8010

- Decision: `deploy/vps/deploy.sh` defaults `SEA_SPEED_ORIGIN_HEALTH_URL` to `http://127.0.0.1:8010/api/health`; candidate deployment and automatic rollback verification use that single verifier.
- Reason: accepted Auth v1 runtime evidence and delivery policy identify `127.0.0.1:8010` as the FastAPI origin. Deploy run #25 proved the former `8000` default creates a false-negative for both candidate and rollback verification.
- Alternatives rejected: environment-only override of a wrong source default, public Authentik-protected URL as origin health, rollback without origin health, or moving the working API back to port 8000.

### D-009 - Pipefail-safe first-parent admission

- Decision: Deploy VPS enumerates `git rev-list --first-parent origin/main` through a full-consumption read loop, records an explicit match flag, and rejects the target unless the flag is set; it does not pipe `git rev-list` into an early-exit `grep -q`.
- Reason: run #26 proved that current-main itself can be falsely rejected when `grep -q` exits after the first match and `pipefail` propagates the resulting upstream SIGPIPE. Full consumption preserves the exact first-parent requirement without weakening it to generic ancestry.
- Alternatives rejected: disabling `pipefail`, ignoring exit 141, using generic `git merge-base --is-ancestor` that can admit second-parent ancestry, normalizing/guessing a different SHA, or bypassing the first-parent gate.

### D-010 - Stale release pruning is best-effort after verified persistence

- Decision: `prune_releases` never targets the names stored in `current-release` or `previous-release`; deletion of any other release runs inside an explicit conditional. Success may be logged, while removal failure logs a warning and returns control without changing the verified deployment result.
- Reason: run #27 proved candidate activation and runtime verification can succeed while an unrelated older release has filesystem ownership that prevents cleanup. Current/previous state and the runtime-verified manifest are persisted before pruning, so stale cleanup is housekeeping rather than an acceptance condition.
- Alternatives rejected: granting broad delete privileges merely to make pruning fatal, deleting current/previous release trees, moving pruning ahead of runtime verification/state persistence, suppressing the warning entirely, or interpreting stale cleanup failure as candidate-health failure.

## Affected contours

Parent feature runtime acceptance remains:
- VPS: YES — Operator frontend/API plus correct exact-deployment health and retention semantics.
- Ubuntu Worker/relay: YES — worker/control source and exact artifact from merged PR #180 remain pending production installation/acceptance.
- Windows AI Worker: NO.
- Parent outcome summary: MIXED.

Current 5-path source remediation is narrower:
- Derived Change Contract production impact: VPS.
- VPS deployment from this diff: REQUIRED after exact-green merge and fresh production authorization.
- Ubuntu worker/relay update from this diff: NOT REQUIRED.
- Windows AI Worker update from this diff: NOT REQUIRED.
- Production safety envelope for this source diff: REQUIRED before deployment because `deploy/vps/deploy.sh` is runtime-affecting VPS source.
- API/event/state/storage schema impact: NONE.
- Security impact: NONE.
- Destructive/data migration impact: NO.
- Other high-risk trigger: YES — release deletion/rollback-retention logic is changing.

The new remediation merge SHA becomes the next VPS release identity because Deploy VPS checks out the exact authorized target before invoking `deploy/vps/deploy.sh`. The earlier authorization for `1d7c8478a467f28f4519111bae06f5d2f7fa5e61` cannot transfer to the new merge SHA. The parent product verdict still requires accepted VPS runtime evidence and the pending Ubuntu worker-control acceptance.

## Validation

- Stale release pruning: `tests/test_vps_deploy_origin_health.py` requires explicit current/previous exclusion, conditional `rm -rf -- "$path"`, a warning path on removal failure, and ordering that persists previous/current plus the runtime-verified manifest before pruning.
- Existing control-plane admission: `tests/quality/test_quality_architecture.py` continues to reject the unsafe `git rev-list --first-parent origin/main | grep -Fxq "$DEPLOY_SHA"` pattern and requires the explicit full-consumption first-parent match guard.
- Existing VPS origin-health evidence: `tests/test_vps_deploy_origin_health.py`, `tests/test_camera_preview_gallery.py`, and `tests/test_sea_speed_auth_v1.py` retain canonical 8010 deployment/rollback assertions from PR #181.
- Existing product/security tests from PR #179/#180 remain authoritative and are re-run by aggregate CI.
- Release provenance: deterministic `vps`, release-specific `ubuntu-worker`, and legacy `edge` artifacts remain covered by Quality integration.
- End-to-end: exact PR Validation + Quality integration on the final 5-path VPS remediation head.
- Runtime-manual after merge: obtain fresh exact-SHA production authorization for the new merge SHA, manually dispatch Deploy VPS from current `main`, and require successful deployment evidence upload. Before any further runtime mutation, re-read the actual post-run #27 current/previous/runtime state because run #27 skipped formal evidence collection after pruning failed.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: current and previous release names remain explicit exclusions and pruning occurs only after runtime verification/state persistence | Validation: tests/test_vps_deploy_origin_health.py plus exact-head CI and next production deployment evidence | Residual risk: filesystem ownership can continue to leave stale release directories, consuming disk until separately cleaned with appropriate permissions | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: pruning is constrained to directories under the release root whose basename is neither current nor previous; no widening of path selection or privileged recursive deletion is introduced | Validation: static regression contract and exact diff review | Residual risk: incorrect state-file contents could protect the wrong pair, so deployment state must remain exact and evidence-backed | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: failed cleanup emits an explicit warning so housekeeping debt is observable without changing the verified deployment result | Validation: source assertion for warning path and next production log evidence | Residual risk: repeated warnings can accumulate stale releases and should lead to a separate maintenance/ownership remediation rather than broadening deploy privileges | Owner: Delivery Orchestrator | Status: MITIGATED

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
- TEST-010 | Covers: AC-015 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_origin_health.py, tests/test_camera_preview_gallery.py, tests/test_sea_speed_auth_v1.py, plus later runtime origin-health/source verification on 8010
- TEST-011 | Covers: AC-016 | Level: integration | Priority: P0 | Evidence: tests/quality/test_quality_architecture.py plus workflow_dispatch admission evidence from run #27
- TEST-012 | Covers: AC-017 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_origin_health.py plus next Deploy VPS log/evidence showing stale cleanup warning cannot fail verified deployment

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Prior evidence: release admission for merged PR #179 / `dc0fd44dbea5ba38f8e18a4ba6ed3eeb93db3d11` exposed missing Ubuntu exact provenance; PR #180 closed that gap. Deploy run #25 exposed the stale port-8000 origin probe; PR #181 / `1d7c8478a467f28f4519111bae06f5d2f7fa5e61` corrected the origin to 8010. Deploy run #26 exposed the `grep -q`/`pipefail` first-parent false-negative; PR #182 / `c87969a0b4184b253cc133e9d5c1d8632646fb15` corrected the control-plane guard.
- Current observed evidence: Deploy VPS run #27 used workflow definition `c87969a0b4184b253cc133e9d5c1d8632646fb15` and target `1d7c8478a467f28f4519111bae06f5d2f7fa5e61`. Admission, exact quality, durable production authorization, release provenance and SSH all passed. Candidate API origin health on 8010 and all configured public smoke checks passed. The deploy script then failed when pruning older release `8248fd6ff54bb4fd197dfef45a31c75f3b39ace5` returned permission denied. Formal deployment-evidence collection/upload was skipped because the step exited 1.
- Issue impact: Issue #178 carries the durable 5-path VPS remediation Implementation Scope Check and `OUTCOME APPROVED`; historical scopes remain immutable audit history.
- Specification impact: adds FR-017, AC-017, NFR-009 and production-learning #4 without changing operator-control/media behavior.
- Plan impact: adds D-010, TEST-012 and a REQUIRED risk profile focused on release retention/deletion boundaries.
- Tasks impact: active source gate becomes exactly the approved 5 VPS/SDD paths.
- Authorization impact: fresh `OUTCOME APPROVED` obtained for the exact 5-path VPS remediation on 2026-08-16. After merge, a fresh exact-SHA `PRODUCTION APPROVED` is required because the remediation changes deployable VPS source.
- Protected boundaries: unchanged — current/previous releases remain rollback-protected; no API/frontend/media ownership, credential, Authentik/private-M2M, worker command surface, Windows Worker or AI-semantic change.
- Follow-up: merge only an exact-green 5-path VPS head; verify post-merge push/main quality; re-read actual VPS state; obtain fresh production authorization for the new merge SHA; then manually dispatch Deploy VPS and require complete deployment evidence before continuing to Ubuntu.

## Rollout and rollback

- Source rollout: merge only the exact green 5-path VPS remediation head after fresh base/head/scope/review verification.
- Production checkpoint: after merge, compute the new exact merge SHA and obtain a fresh production authorization/fingerprint before runtime mutation.
- Runtime continuation: before the next deploy, read current-release, previous-release, service health/source identity and listeners to resolve the post-run #27 state. Then dispatch `Deploy VPS` from current `main` targeting the newly authorized merge SHA and Issue #178.
- Success semantics: candidate origin health and public smoke checks must pass; previous/current state and runtime-verified deployment manifest must be persisted; stale-release pruning may warn but cannot fail the deployment solely because an older unprotected directory is not removable.
- Runtime rollback: if candidate activation or verification fails before verified state is committed, automatic rollback to the current accepted release remains mandatory and must pass the same 8010 verifier. Pruning behavior does not weaken rollback.
- Source rollback: if best-effort pruning logic fails CI or violates retention boundaries, do not deploy it; revert through normal source governance.
- Parent Outcome continuation: after VPS acceptance, re-verify the eligible exact Ubuntu worker-control source/authorization (or create a later Ubuntu-affecting authorized merge as required by policy), install the compatible Ubuntu release/control service, verify protocol/status, then perform bounded stop/start while monitoring HLS.
- Camera relay/HLS has no source change to roll back.
- Production mutation during this remediation source delivery: NONE.

## Runtime feedback

- Actual architecture after acceptance: PENDING final production evidence.
- Last independently read-only verified baseline before run #27: `6bf909c13d48df1d44b87a62d0686b61d8c3af45`, healthy on `127.0.0.1:8010`; Ubuntu rollout not started.
- Production learning #2: run #25 showed deployment automation used a stale 8000 origin-health default; merged PR #181 corrected that source contract to 8010.
- Production learning #3: run #26 showed the workflow's first-parent membership pipeline was not `pipefail` safe even when target SHA equaled current main; merged PR #182 corrected the admission guard.
- Production learning #4: run #27 proved the corrected workflow reaches and verifies production successfully but a non-critical stale-release permission failure can still return exit 1 after verified state is persisted, suppressing formal evidence collection.
- Corrective source task: active 5-path VPS remediation makes stale pruning best-effort, protects current/previous, preserves ordering and adds regression/risk evidence.
- Deferred work: exact-head VPS remediation CI/merge, read-only state resolution, fresh production authorization for the new merge SHA, successful Deploy VPS with uploaded evidence, then pending Ubuntu worker-control installation and runtime-manual AC-012 acceptance.
