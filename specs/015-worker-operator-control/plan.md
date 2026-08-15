# Implementation Plan: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Issue: #178
- Status: Correct-course remediation validation

## Architecture

The control path is deliberately separate from Camera 1 media transport:

```text
Authenticated browser
  -> existing Authentik-protected /sea-speed/api/**
  -> VPS FastAPI fixed worker-control routes
  -> RFC1918 Ubuntu control-agent origin over ZeroTier
  -> bearer token validation
  -> fixed protocol marker sea_speed_worker_control_v1
  -> fixed systemctl operation for sea-speed-worker.service only
```

The Ubuntu control agent is a separate systemd service and uses the existing protected `worker.env` only for the shared bearer token and optional private listener configuration. The AI worker remains the only controlled service. Camera relay/MediaMTX are not referenced by the control operation.

The agent persists `/opt/sea-speed-worker/shared/runtime/operator-desired-state` as `running` or `stopped`. Exact updater and rollback paths consult this marker: `running` keeps the current active-service/runtime-gate semantics; `stopped` permits intentional inactivity and installs the exact unit/control service without auto-starting the AI worker.

Release provenance is separate from runtime transport. Quality tooling preserves the existing quality-evidence v1 exact inventory for `vps` and legacy `edge`, and the same deterministic exact-artifacts manifest additionally carries a release-specific `ubuntu-worker` archive. The custom validator proves all three archives. Release-manifest v2 can then directly bind the Ubuntu archive digest and the SHA-256 of the complete exact-artifacts manifest.

The VPS code-deployment verifier is also a release boundary. Its origin-health probe must target the accepted Auth v1 FastAPI loopback origin `127.0.0.1:8010`. The same `restart_and_verify` function is used after candidate installation and after automatic rollback, so one canonical origin identity must be correct for both paths.

## Decisions

### D-001 - Direct VPS-to-Ubuntu private agent

- Decision: VPS FastAPI calls a dedicated RFC1918 Ubuntu HTTP control agent directly over ZeroTier.
- Reason: the existing private nginx M2M ingress is Ubuntu->VPS and cannot safely be inverted; direct private control keeps the browser unaware of the Ubuntu host and avoids browser SSH.
- Alternatives rejected: browser direct-to-worker requests, SSH from browser, repurposing Camera 1 relay endpoints, arbitrary command RPC.

### D-002 - Reuse existing API bearer secret

- Decision: use `SEA_SPEED_API_TOKEN` as the private service-to-service bearer token.
- Reason: both VPS API and Ubuntu worker already hold this protected secret; no new credential lifecycle is required.
- Alternatives rejected: repository token, browser-carried secret, unauthenticated private endpoint.

### D-003 - Literal service allowlist of one

- Decision: the agent accepts only `/v1/status`, `/v1/start`, `/v1/stop` and always targets literal `sea-speed-worker.service`.
- Reason: root-level service control must not become a generic remote execution interface.
- Alternatives rejected: service name request parameter, shell command field, sudo command passthrough.

### D-004 - Desired-state marker owns intentional stop

- Decision: persist operator desired state independently from heartbeat/state freshness.
- Reason: a stale worker heartbeat cannot distinguish an intentional stop from a crash; deployment/rollback must preserve operator intent.
- Alternatives rejected: infer desired state from API heartbeat age or systemd activity only.

### D-005 - Live media remains a separate failure domain

- Decision: worker-control source never invokes or reconfigures MediaMTX, camera relay, HLS routes or live-camera browser controls.
- Reason: the requested product invariant is continuous live viewing while AI is stopped.

### D-006 - Fixed private worker-control protocol marker

- Decision: successful agent responses include `sea_speed_worker_control_v1`; VPS FastAPI requires the same marker before accepting a successful upstream response.
- Reason: independently deployed VPS and Ubuntu contours must fail closed on a stale or incompatible private control agent instead of interpreting an unknown response shape as safe.
- Alternatives rejected: implicit compatibility based only on HTTP 200/`ok=true`, semantic version negotiation, fallback to SSH or another control channel.

### D-007 - First-class Ubuntu Worker exact artifact with legacy quality-evidence compatibility

- Decision: `scripts/quality/build_exact_artifacts.py` builds a deterministic `ubuntu-worker` archive containing the repository-owned Ubuntu install/update/control/runtime source needed for the exact release. The manifest keeps `vps` and `edge` under its existing `artifacts` inventory consumed by quality-evidence v1 and stores `ubuntu-worker` under a separate release-specific inventory; `validate_exact_artifacts.py` requires and validates all three.
- Reason: release-manifest v2 requires at least one exact artifact for a deployable `ubuntu-worker` component in `ready_for_deployment`, while the existing quality-evidence v1 schema does not enumerate `ubuntu-worker`. Separating the release-specific inventory preserves the current quality evidence contract without mislabeling Ubuntu as `edge`; release-manifest v2 directly binds the Ubuntu archive digest plus the full exact-manifest hash.
- Alternatives rejected: relabel legacy `edge` as Ubuntu, weaken/waive the quality schema, expand source scope into schema migration without authorization, partially deploy VPS before Ubuntu admission, or treat server-pull transport as provenance evidence without an exact artifact.

### D-008 - Canonical VPS origin-health identity is port 8010

- Decision: `deploy/vps/deploy.sh` defaults `SEA_SPEED_ORIGIN_HEALTH_URL` to `http://127.0.0.1:8010/api/health`; both candidate deployment and automatic rollback verification use that single verifier.
- Reason: accepted Auth v1 production evidence and current delivery policy identify `127.0.0.1:8010` as the FastAPI origin. Deploy run #25 proved the former `8000` default creates a false-negative for both candidate and rollback verification.
- Alternatives rejected: keep 8000 and override it only in Actions secrets/environment, probe the public Authentik-protected URL as origin health, accept rollback without origin health, or change the running API back to port 8000.

## Affected contours

Parent feature runtime acceptance remains:
- VPS: YES — Operator frontend/API plus correct exact-deployment health verification.
- Ubuntu worker/relay: YES — worker/control source and exact artifact from merged PR #180 remain pending production installation/acceptance.
- Windows AI Worker: NO.
- Parent outcome summary: MIXED.

Current 5-path source remediation is narrower:
- Derived Change Contract production impact: VPS.
- VPS deployment: REQUIRED after a fresh exact-SHA production authorization.
- Ubuntu worker/relay update from this diff: NOT REQUIRED; no Ubuntu-impact path changes in this remediation.
- Windows AI Worker update: NOT REQUIRED.
- API/event/state/storage schema impact: NONE.
- Security impact: NONE for this remediation; existing feature security boundaries are unchanged.

The final product verdict still requires accepted evidence for the pending Ubuntu worker-control release as well as the remediated VPS release. Do not infer Ubuntu deployment from this VPS-only source diff.

## Validation

- Unit: agent auth, fixed operation allowlist, desired-state behavior, protocol marker, API origin validation and fail-closed protocol mismatch guard remain covered by previously merged feature tests.
- Integration: `tests/test_vps_deploy_origin_health.py` proves the canonical 8010 default, rejects the stale 8000 URL and proves candidate/rollback paths use the same `restart_and_verify` origin verifier.
- Existing integration: frontend/API route contract, private nginx ingress exclusion, systemd installation/update/rollback contract tests remain authoritative and are re-run by aggregate CI.
- Release-provenance: deterministic `vps`, release-specific `ubuntu-worker`, and legacy `edge` exact artifacts remain covered by quality integration.
- End-to-end: exact PR Validation + Quality integration on the final 5-path remediation head.
- Runtime-manual after fresh production authorization: deploy VPS with the corrected origin verifier, confirm source/health on 8010, then separately verify the still-pending compatible Ubuntu worker-control release before bounded stop/start plus continuous HLS acceptance.

## Risk profile

- Risk profile: REQUIRED
- Note: the parent open feature retains its full MIXED/security risk profile. The current 5-path PR has no new security/schema/destructive/MIXED/other-high-risk trigger, so its Change Contract risk-profile applicability is `NOT REQUIRED`; this retained feature risk register remains the runtime-acceptance model.

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: fixed paths, literal service name, bearer auth, RFC1918 listener validation, no shell=True, no arbitrary arguments | Validation: tests/test_worker_operator_control.py | Residual risk: root control agent remains privileged but exposes only the fixed worker action surface | Owner: PM/operator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: explicit desired-state marker integrated into updater/rollback contracts | Validation: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Residual risk: production maintenance must still verify marker/service agreement before mutation | Owner: PM/operator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: separate endpoints/buttons and invariant tests for HLS path plus absence of relay operations | Validation: tests/test_frontend_contract.py and tests/test_worker_operator_control.py | Residual risk: runtime HLS continuity still requires manual production evidence | Owner: PM/operator | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: bounded <=5s upstream timeout and asynchronous UI error state | Validation: tests/test_worker_operator_control.py | Residual risk: private network outage can temporarily make control unavailable without affecting HLS | Owner: PM/operator | Status: MITIGATED
- RISK-005 | Category: BUS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: dedicated independently enabled control systemd unit | Validation: tests/test_ubuntu_worker_systemd.py plus runtime-manual acceptance | Residual risk: control service availability must be verified during production rollout | Owner: PM/operator | Status: MITIGATED
- RISK-006 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: first-class deterministic `ubuntu-worker` exact release artifact, strict three-artifact validator, preserved quality-evidence v1 contract, and later release-manifest v2 direct artifact/full-manifest hash binding | Validation: tests/quality/test_quality_architecture.py | Residual risk: a future Ubuntu release-source expansion must update the explicit artifact inventory in the same approved task | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-007 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: fixed protocol marker required by VPS before successful upstream payload is accepted | Validation: tests/test_worker_operator_control.py | Residual risk: protocol version changes require coordinated source delivery and fresh production authorization | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-008 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: bind deploy/rollback origin health to accepted port 8010 and enforce source regression test against stale 8000 default | Validation: tests/test_vps_deploy_origin_health.py plus runtime 8010 source/health evidence | Residual risk: a future production origin migration must update deployment verifier, baseline and delivery policy atomically | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-002, AC-003, AC-004, AC-005, AC-006 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py
- TEST-002 | Covers: AC-001, AC-010 | Level: integration | Priority: P1 | Evidence: tests/test_frontend_contract.py
- TEST-003 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_systemd.py
- TEST-004 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py
- TEST-005 | Covers: AC-009 | Level: integration | Priority: P0 | Evidence: tests/test_sea_speed_auth_v1.py
- TEST-006 | Covers: AC-011 | Level: end-to-end | Priority: P0 | Evidence: exact-head PR Validation + Quality integration
- TEST-007 | Covers: AC-012 | Level: runtime-manual | Priority: P0 | Evidence: production service status plus continuous Camera 1 HLS playback before/during/after stop/start, recorded on Issue #178
- TEST-008 | Covers: AC-013 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py
- TEST-009 | Covers: AC-014 | Level: end-to-end | Priority: P0 | Evidence: tests/quality/test_quality_architecture.py plus Quality integration exact-artifact and release-evidence jobs
- TEST-010 | Covers: AC-015 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_origin_health.py plus runtime origin-health/source verification on 8010

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Prior evidence: release admission for merged PR #179 / `dc0fd44dbea5ba38f8e18a4ba6ed3eeb93db3d11` stopped before the first runtime write because exact-artifact tooling lacked `ubuntu-worker`; merged PR #180 / `1d0aa285d5f30165980c4d628a97da7e23b66ffe` closed that provenance gap.
- Current observed evidence: authorized Deploy VPS run #25 for `1d0aa285d5f30165980c4d628a97da7e23b66ffe` reached the VPS, installed the candidate, then candidate verification and rollback verification both failed against stale `127.0.0.1:8000`. Immediate read-only operator evidence showed `current-release=6bf909c13d48df1d44b87a62d0686b61d8c3af45`, `sea-speed-api=active`, listener `127.0.0.1:8010`, and healthy `/api/health` reporting that exact restored source.
- Issue impact: Issue #178 carries the new durable 5-path remediation Implementation Scope Check; original 17-path and prior 9-path scopes remain immutable audit history.
- Specification impact: adds FR-015, AC-015, NFR-007 and the accepted restored VPS baseline/false-negative learning.
- Plan impact: adds D-008, RISK-008, TEST-010 and explicitly distinguishes this VPS-only source remediation from the parent feature's still-pending mixed runtime acceptance.
- Tasks impact: active source gate becomes exactly the approved 5 paths and adds the VPS health-probe/regression tasks.
- Authorization impact: fresh `OUTCOME APPROVED` obtained after the exact 5-path scope check on 2026-08-16. Production authorization for `1d0aa285...` is not transferable to the next merge SHA.
- Protected boundaries: unchanged — no media ownership, credential, Authentik/private-M2M, worker-control command surface, Windows Worker or AI-semantic expansion.
- Follow-up: after exact-green-head merge and push/main quality, obtain a fresh production authorization for the new VPS remediation SHA before retrying VPS deployment; separately re-verify authorization/compatibility for the pending Ubuntu worker-control contour before any Ubuntu mutation.

## Rollout and rollback

- Source rollout: merge only the exact green 5-path remediation head after fresh base/head/scope/review verification.
- Current remediation production contour: VPS only by exact changed-path derivation. After a fresh exact-SHA approval, run the canonical VPS deployment; its candidate and rollback health checks must prove `127.0.0.1:8010/api/health` and correct source identity.
- Parent Outcome continuation: once VPS is accepted, re-verify the eligible exact Ubuntu worker-control source/authorization from PR #180 (or a later authorized Ubuntu-affecting merge if one exists), install the compatible Ubuntu release/control service, then verify protocol/status and perform bounded stop/start while monitoring HLS.
- VPS rollback target for the current retry: restored runtime-verified `6bf909c13d48df1d44b87a62d0686b61d8c3af45`; corrected 8010 verification must prove rollback health if candidate activation fails.
- Ubuntu rollback semantics remain the previous exact unit/release with operator desired state preserved. Camera relay/HLS requires no rollback because it is not changed.
- Production mutation during this remediation source delivery: NONE.

## Runtime feedback

- Actual architecture after acceptance: PENDING final production evidence.
- Restored VPS baseline after run #25: `6bf909c13d48df1d44b87a62d0686b61d8c3af45`, `sea-speed-api` active, healthy on `127.0.0.1:8010`; Ubuntu rollout not started.
- Production learning: deployment automation was internally inconsistent with the accepted Auth v1 origin. The stale 8000 probe produced false-negative candidate and rollback verdicts while the restored API was healthy on 8010.
- Corrective source task: active 5-path remediation for canonical 8010 deployment/rollback verification plus regression evidence.
- Deferred work: fresh VPS production approval/retry, then pending Ubuntu worker-control installation and runtime-manual AC-012/AC-015 acceptance.
