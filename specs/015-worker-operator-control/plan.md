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

Release provenance is separate from runtime transport. Quality tooling preserves the existing quality-evidence v1 exact inventory for `vps` and legacy `edge`, and the same deterministic exact-artifacts manifest additionally carries a release-specific `ubuntu-worker` archive. The custom validator proves all three archives. Release-manifest v2 can then directly bind the Ubuntu archive digest and the SHA-256 of the complete exact-artifacts manifest. A MIXED production rollout is admitted only after these exact artifacts, valid quality evidence, release manifest v2 and a new exact-SHA production authorization all bind the same merged main commit.

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

## Affected contours

- VPS: YES — FastAPI private-control compatibility guard.
- Ubuntu worker/relay: YES — control-agent protocol marker and exact Ubuntu Worker artifact provenance.
- Windows AI Worker: NO.
- Summary impact: MIXED.
- API compatibility: additive private response marker; browser API existing fields remain compatible.
- Security impact: YES; existing bounded authenticated runtime-control capability is tightened with fail-closed compatibility checking, not expanded.

## Validation

- Unit: agent auth, fixed operation allowlist, desired-state behavior, protocol marker, API origin validation and fail-closed protocol mismatch guard.
- Integration: existing frontend/API route contract, private nginx ingress exclusion, systemd installation/update/rollback contract tests remain authoritative.
- Release-provenance: build exact artifacts twice; compare all three archives and complete manifests; validate all three inventories/digests/extraction/Python/shell/runtime-lock syntax; validate unchanged quality-evidence v1 for `vps`/`edge`; assert the separate Ubuntu release inventory has a deterministic digest available for release-manifest v2 binding.
- End-to-end: exact PR Validation + Quality integration.
- Runtime-manual after a new separate production approval: confirm exact VPS/Ubuntu identities, control-agent protocol, HLS playback before/during/after AI worker stop/start and exact service/control-agent state.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: fixed paths, literal service name, bearer auth, RFC1918 listener validation, no shell=True, no arbitrary arguments | Validation: tests/test_worker_operator_control.py | Residual risk: root control agent remains privileged but exposes only the fixed worker action surface | Owner: PM/operator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: explicit desired-state marker integrated into updater/rollback contracts | Validation: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Residual risk: production maintenance must still verify marker/service agreement before mutation | Owner: PM/operator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: separate endpoints/buttons and invariant tests for HLS path plus absence of relay operations | Validation: tests/test_frontend_contract.py and tests/test_worker_operator_control.py | Residual risk: runtime HLS continuity still requires manual production evidence | Owner: PM/operator | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: bounded <=5s upstream timeout and asynchronous UI error state | Validation: tests/test_worker_operator_control.py | Residual risk: private network outage can temporarily make control unavailable without affecting HLS | Owner: PM/operator | Status: MITIGATED
- RISK-005 | Category: BUS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: dedicated independently enabled control systemd unit | Validation: tests/test_ubuntu_worker_systemd.py plus runtime-manual acceptance | Residual risk: control service availability must be verified during production rollout | Owner: PM/operator | Status: MITIGATED
- RISK-006 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: first-class deterministic `ubuntu-worker` exact release artifact, strict three-artifact validator, preserved quality-evidence v1 contract, and later release-manifest v2 direct artifact/full-manifest hash binding | Validation: tests/quality/test_quality_architecture.py | Residual risk: a future Ubuntu release-source expansion must update the explicit artifact inventory in the same approved task | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-007 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: fixed protocol marker required by VPS before successful upstream payload is accepted | Validation: tests/test_worker_operator_control.py | Residual risk: protocol version changes require coordinated source delivery and fresh production authorization | Owner: Delivery Orchestrator | Status: MITIGATED

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

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Observed evidence: release admission for merged PR #179 / `dc0fd44dbea5ba38f8e18a4ba6ed3eeb93db3d11` stopped before the first runtime write because exact-artifact tooling produced only `vps` and legacy `edge`, while release-manifest v2 requires an exact artifact for `ubuntu-worker` in the declared MIXED rollout.
- Issue impact: Issue #178 now carries a separate durable 9-path remediation Implementation Scope Check while preserving the original 17-path implementation history.
- Specification impact: adds fixed private protocol compatibility and Ubuntu exact-artifact provenance requirements/acceptance criteria.
- Plan impact: adds D-006/D-007, provenance risk/test design and explicit fail-closed mixed-contour admission.
- Tasks impact: adds bounded remediation tasks and changes the active source gate from the historical 17 paths to exactly the approved 9 remediation paths.
- Authorization impact: FRESH `OUTCOME APPROVED` obtained after the exact remediation scope check on 2026-08-16; the prior production approval is stale for any new merge SHA.
- Protected boundaries: unchanged — no media ownership, credential, arbitrary-service, Windows Worker or AI-semantic expansion.
- Follow-up: after exact-green-head merge, obtain a new `PRODUCTION APPROVED <new-full-sha>` and only then restart the MIXED release-readiness/production flow.

## Rollout and rollback

- Source rollout: merge only the exact green remediation head after fresh base/head/scope/review verification.
- Production rollout after a new exact-SHA approval: validate the complete exact-artifacts manifest and quality evidence, build/validate release manifest v2 for both applicable components with the Ubuntu release-specific archive -> deploy VPS additive API/protocol guard -> prepare/install Ubuntu exact release and independent control service -> verify matching protocol/status -> perform bounded stop/start test while monitoring HLS -> record acceptance.
- Rollback order: stop using UI control -> restore previous VPS release -> restore previous Ubuntu exact unit/release using existing rollback path while preserving prior desired state. Camera relay/HLS requires no rollback because it is not changed.
- Partial rollout rule: if Ubuntu exact-artifact/release admission fails, do not deploy VPS alone; the MIXED rollout fails closed before runtime mutation.
- Production mutation during remediation source delivery: NONE.

## Runtime feedback

- Actual architecture after acceptance: PENDING production evidence.
- Difference discovered before production: release provenance did not model Ubuntu Worker as an exact release artifact even though runtime applicability correctly declared it.
- Corrective source task: active 9-path remediation branch for protocol compatibility and Ubuntu exact-artifact provenance.
- Deferred cleanup: NONE; runtime acceptance remains the only deferred product evidence after source merge and fresh production authorization.
