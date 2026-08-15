# Implementation Plan: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Issue: #178
- Status: Correct-course remediation validation

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

The current correct-course change is narrower: the VPS code-deployment verifier is a release boundary and its origin-health probe must target the accepted Auth v1 FastAPI loopback origin `127.0.0.1:8010`. The same `restart_and_verify` function is used after candidate installation and after automatic rollback, so one canonical origin identity must be correct for both paths.

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

## Affected contours

Parent feature runtime acceptance remains:
- VPS: YES — Operator frontend/API plus correct exact-deployment health verification.
- Ubuntu Worker/relay: YES — worker/control source and exact artifact from merged PR #180 remain pending production installation/acceptance.
- Windows AI Worker: NO.
- Parent outcome summary: MIXED.

Current 7-path source remediation is narrower:
- Derived Change Contract production impact: VPS.
- VPS deployment: REQUIRED after a fresh exact-SHA production authorization.
- Ubuntu worker/relay update from this diff: NOT REQUIRED.
- Windows AI Worker update: NOT REQUIRED.
- API/event/state/storage schema impact: NONE.
- Security impact: NONE.
- Destructive/data migration impact: NO.
- Other high-risk trigger: NO.

The final product verdict still requires accepted evidence for the pending Ubuntu worker-control release as well as the remediated VPS release. This VPS-only diff does not imply Ubuntu deployment or authorization.

## Validation

- Integration: `tests/test_vps_deploy_origin_health.py` proves the canonical 8010 default, rejects the stale 8000 URL, and proves candidate/rollback paths use the same `restart_and_verify` origin verifier.
- Historical deploy-contract alignment: `tests/test_camera_preview_gallery.py` and `tests/test_sea_speed_auth_v1.py` assert the same canonical 8010 deployment origin while retaining their unrelated media/auth boundary assertions unchanged.
- Existing product/security tests from PR #179/#180 remain authoritative and are re-run by aggregate CI.
- Release provenance: deterministic `vps`, release-specific `ubuntu-worker`, and legacy `edge` artifacts remain covered by Quality integration.
- End-to-end: exact PR Validation + Quality integration on the final 7-path remediation head.
- Runtime-manual after fresh production authorization: deploy VPS with the corrected verifier and confirm exact source/health on 8010; separately re-verify the pending compatible Ubuntu release before bounded worker stop/start plus continuous HLS acceptance.

## Risk profile

- Risk profile: NOT REQUIRED

The current PR has VPS-only derived impact, Security impact `NONE`, API/event/state/storage schema impact `NONE`, destructive/data migration `NO`, and other high-risk trigger `NO`, so the executable Change Contract does not require a new full risk profile. The full MIXED/security risk evidence from merged PR #180 remains immutable audit evidence for the parent feature and will still inform final runtime acceptance; it is not duplicated as active `RISK-*` rows in this VPS-only remediation.

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

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Prior evidence: release admission for merged PR #179 / `dc0fd44dbea5ba38f8e18a4ba6ed3eeb93db3d11` stopped before the first runtime write because exact-artifact tooling lacked `ubuntu-worker`; merged PR #180 / `1d0aa285d5f30165980c4d628a97da7e23b66ffe` closed that provenance gap.
- Current observed evidence: authorized Deploy VPS run #25 for `1d0aa285d5f30165980c4d628a97da7e23b66ffe` reached the VPS, then candidate verification and rollback verification both failed against stale `127.0.0.1:8000`. Immediate read-only operator evidence showed `current-release=6bf909c13d48df1d44b87a62d0686b61d8c3af45`, `sea-speed-api=active`, listener `127.0.0.1:8010`, and healthy `/api/health` reporting that restored source.
- Issue impact: Issue #178 carries the durable 7-path remediation Implementation Scope Check; original 17-path, prior 9-path, and superseded 5-path scopes remain immutable audit history.
- Specification impact: adds FR-015, AC-015, NFR-007 and the restored VPS baseline/false-negative learning.
- Plan impact: adds D-008 and TEST-010, aligns active risk applicability to the exact VPS-only diff, and distinguishes this remediation from the parent feature's pending Ubuntu acceptance.
- Tasks impact: active source gate becomes exactly the approved 7 paths, including the two stale historical deploy-contract tests exposed by exact-head CI.
- Authorization impact: fresh `OUTCOME APPROVED` obtained after CI exposed the required 7-path scope expansion on 2026-08-16. Production authorization for `1d0aa285...` is not transferable to the next merge SHA.
- Protected boundaries: unchanged — no media ownership, credential, Authentik/private-M2M, worker-control command surface, Windows Worker or AI-semantic expansion.
- Follow-up: after exact-green-head merge and push/main quality, obtain a fresh production authorization for the new VPS remediation SHA before retrying VPS deployment; separately re-verify authorization/compatibility for the pending Ubuntu worker-control contour before any Ubuntu mutation.

## Rollout and rollback

- Source rollout: merge only the exact green 7-path remediation head after fresh base/head/scope/review verification.
- Current remediation production contour: VPS only by exact changed-path derivation. After a fresh exact-SHA approval, run the canonical VPS deployment; candidate and rollback health checks must prove `127.0.0.1:8010/api/health` and correct source identity.
- VPS rollback target: restored runtime-verified `6bf909c13d48df1d44b87a62d0686b61d8c3af45`; corrected 8010 verification must prove rollback health if candidate activation fails.
- Parent Outcome continuation: after VPS acceptance, re-verify the eligible exact Ubuntu worker-control source/authorization from PR #180 (or a later authorized Ubuntu-affecting merge), install the compatible Ubuntu release/control service, verify protocol/status, then perform bounded stop/start while monitoring HLS.
- Camera relay/HLS has no source change to roll back.
- Production mutation during this remediation source delivery: NONE.

## Runtime feedback

- Actual architecture after acceptance: PENDING final production evidence.
- Restored VPS baseline after run #25: `6bf909c13d48df1d44b87a62d0686b61d8c3af45`, `sea-speed-api` active, healthy on `127.0.0.1:8010`; Ubuntu rollout not started.
- Production learning: deployment automation was inconsistent with the accepted Auth v1 origin. The stale 8000 probe produced false-negative candidate and rollback verdicts while the restored API was healthy on 8010.
- Corrective source task: active 7-path remediation for canonical 8010 deployment/rollback verification, focused regression evidence, and alignment of the two stale historical deploy-contract assertions found by CI.
- Deferred work: fresh VPS production approval/retry, then pending Ubuntu worker-control installation and runtime-manual AC-012/AC-015 acceptance.
