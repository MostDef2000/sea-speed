# Implementation Plan: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Issue: #178
- Status: Control-plane admission remediation validation

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

Merged PR #181 corrected the VPS origin-health verifier to the accepted Auth v1 FastAPI loopback origin `127.0.0.1:8010`. The current correct-course change is control-plane-only: Deploy VPS must still require the exact target SHA to be on current `main` first-parent history, but the implementation must not couple `git rev-list` to an early-exit `grep -q` under `set -o pipefail`, because that producer/consumer pattern can convert a valid first-line match into SIGPIPE failure.

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

## Affected contours

Parent feature runtime acceptance remains:
- VPS: YES — Operator frontend/API plus correct exact-deployment health verification.
- Ubuntu Worker/relay: YES — worker/control source and exact artifact from merged PR #180 remain pending production installation/acceptance.
- Windows AI Worker: NO.
- Parent outcome summary: MIXED.

Current 5-path source remediation is narrower:
- Derived Change Contract production impact: CONTROL_PLANE.
- VPS deployment from this diff: NOT REQUIRED.
- Ubuntu worker/relay update from this diff: NOT REQUIRED.
- Windows AI Worker update from this diff: NOT REQUIRED.
- Production safety envelope for this source diff: NOT REQUIRED because no runtime contour is changed.
- API/event/state/storage schema impact: NONE.
- Security impact: NONE.
- Destructive/data migration impact: NO.
- Other high-risk trigger: YES — the changed workflow implements a production admission guard.

The control-plane merge does not become the runtime deployment target. After it is merged and green, the manually dispatched workflow from current `main` will still target the separately authorized runtime SHA `1d7c8478a467f28f4519111bae06f5d2f7fa5e61`, which remains on first-parent history. The parent product verdict still requires accepted VPS runtime evidence and the pending Ubuntu worker-control acceptance.

## Validation

- Control-plane admission: `tests/quality/test_quality_architecture.py` rejects the exact unsafe `git rev-list --first-parent origin/main | grep -Fxq "$DEPLOY_SHA"` pattern and requires the explicit full-consumption first-parent match guard.
- Existing VPS origin-health evidence: `tests/test_vps_deploy_origin_health.py`, `tests/test_camera_preview_gallery.py`, and `tests/test_sea_speed_auth_v1.py` retain canonical 8010 deployment/rollback assertions from PR #181.
- Existing product/security tests from PR #179/#180 remain authoritative and are re-run by aggregate CI.
- Release provenance: deterministic `vps`, release-specific `ubuntu-worker`, and legacy `edge` artifacts remain covered by Quality integration.
- End-to-end: exact PR Validation + Quality integration on the final 5-path control-plane remediation head.
- Runtime-manual after merge: manually dispatch Deploy VPS from current `main` using `commit_sha=1d7c8478a467f28f4519111bae06f5d2f7fa5e61` and `canonical_issue=178`; admission must pass first-parent resolution, then existing quality/authorization/provenance gates must pass before SSH. Only then may VPS runtime mutation occur under the already-current runtime envelope.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: preserve exact lowercase SHA and strict current-main first-parent enumeration; change only the membership implementation, never the admission semantics | Validation: tests/quality/test_quality_architecture.py plus exact-head CI and the next manual workflow dispatch | Residual risk: a future workflow edit could weaken or bypass first-parent semantics and must re-enter Change Contract/SDD review | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: consume the complete first-parent stream before evaluating the match flag so no early consumer exit can SIGPIPE the producer under pipefail | Validation: static regression rejects the producer-to-grep-q pattern and requires the full-consumption loop | Residual risk: hosted-runner shell behavior is finally proven only by the next workflow_dispatch execution | Owner: Delivery Orchestrator | Status: MITIGATED

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
- TEST-011 | Covers: AC-016 | Level: integration | Priority: P0 | Evidence: tests/quality/test_quality_architecture.py plus later workflow_dispatch admission evidence

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Prior evidence: release admission for merged PR #179 / `dc0fd44dbea5ba38f8e18a4ba6ed3eeb93db3d11` exposed missing Ubuntu exact provenance; PR #180 closed that gap. Deploy run #25 for PR #180 then exposed the stale port-8000 origin probe; PR #181 / `1d7c8478a467f28f4519111bae06f5d2f7fa5e61` corrected the origin to 8010.
- Current observed evidence: Deploy VPS run #26 received `INPUT_COMMIT=1d7c8478a467f28f4519111bae06f5d2f7fa5e61` and fetched `origin/main` at that exact SHA, yet the `git rev-list --first-parent origin/main | grep -Fxq "$DEPLOY_SHA"` pipeline failed under `set -o pipefail`. The run stopped before aggregate-quality verification, durable-authorization verification, SSH, or production mutation.
- Issue impact: Issue #178 now carries the durable 5-path control-plane remediation Implementation Scope Check and `OUTCOME APPROVED`; historical 17/9/7-path remediation records remain audit history.
- Specification impact: adds FR-016, AC-016, NFR-008 and production-learning #3 without changing product behavior.
- Plan impact: adds D-009, TEST-011 and an explicit high-risk control-plane risk profile for the production admission guard.
- Tasks impact: active source gate becomes exactly the approved 5 control-plane/SDD paths.
- Authorization impact: fresh `OUTCOME APPROVED` obtained for the exact 5-path control-plane remediation on 2026-08-16. Existing production authorization remains bound to runtime SHA `1d7c8478a467f28f4519111bae06f5d2f7fa5e61`; the control-plane merge SHA is not substituted as a runtime release identity.
- Protected boundaries: unchanged — first-parent admission remains mandatory; no runtime application, media ownership, credential, Authentik/private-M2M, worker command surface, Windows Worker or AI-semantic change.
- Follow-up: merge only an exact-green 5-path control-plane head; then manually dispatch Deploy VPS from the new current-main workflow definition targeting the already-authorized runtime SHA. Re-check the authorization fingerprint before SSH and continue to Ubuntu only after VPS acceptance.

## Rollout and rollback

- Source rollout: merge only the exact green 5-path control-plane remediation head after fresh base/head/scope/review verification.
- Control-plane release behavior: no VPS/Ubuntu/Windows deployment is caused by the merge and no new runtime release manifest is needed for the control-plane SHA.
- Runtime continuation after merge: manually dispatch `Deploy VPS` from `main` with exact target `1d7c8478a467f28f4519111bae06f5d2f7fa5e61` and Issue #178. The fixed workflow definition must admit that first-parent SHA, then the target SHA's existing quality, authorization, exact-artifact, release and rollback gates remain authoritative before SSH.
- Control-plane rollback: if the new admission logic fails CI or later dispatch evidence, do not perform runtime mutation; revert the control-plane workflow change through normal source governance rather than weakening/bypassing first-parent admission.
- VPS runtime rollback target remains the restored runtime-verified `6bf909c13d48df1d44b87a62d0686b61d8c3af45`; corrected 8010 verification must prove rollback health if candidate activation later fails.
- Parent Outcome continuation: after VPS acceptance, re-verify the eligible exact Ubuntu worker-control source/authorization from PR #180 (or a later authorized Ubuntu-affecting merge), install the compatible Ubuntu release/control service, verify protocol/status, then perform bounded stop/start while monitoring HLS.
- Camera relay/HLS has no source change to roll back.
- Production mutation during this remediation source delivery: NONE.

## Runtime feedback

- Actual architecture after acceptance: PENDING final production evidence.
- Restored VPS baseline after run #25: `6bf909c13d48df1d44b87a62d0686b61d8c3af45`, `sea-speed-api` active, healthy on `127.0.0.1:8010`; Ubuntu rollout not started.
- Production learning #2: run #25 showed deployment automation used a stale 8000 origin-health default; merged PR #181 corrected that source contract to 8010.
- Production learning #3: run #26 showed the workflow's first-parent membership pipeline was not `pipefail` safe even when target SHA equaled current main. The false-negative occurred before any runtime operation.
- Corrective source task: active 5-path control-plane remediation preserves strict first-parent admission but removes the producer/early-exit pipeline and adds regression/risk evidence.
- Deferred work: exact-head control-plane CI/merge, then Deploy VPS retry for already-authorized runtime SHA, then pending Ubuntu worker-control installation and runtime-manual AC-012/AC-015/AC-016 acceptance.
