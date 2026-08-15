# Implementation Plan: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Issue: #178
- Status: Implementation

## Architecture

The control path is deliberately separate from Camera 1 media transport:

```text
Authenticated browser
  -> existing Authentik-protected /sea-speed/api/**
  -> VPS FastAPI fixed worker-control routes
  -> RFC1918 Ubuntu control-agent origin over ZeroTier
  -> bearer token validation
  -> fixed systemctl operation for sea-speed-worker.service only
```

The Ubuntu control agent is a separate systemd service and uses the existing protected `worker.env` only for the shared bearer token and optional private listener configuration. The AI worker remains the only controlled service. Camera relay/MediaMTX are not referenced by the control operation.

The agent persists `/opt/sea-speed-worker/shared/runtime/operator-desired-state` as `running` or `stopped`. Exact updater and rollback paths consult this marker: `running` keeps the current active-service/runtime-gate semantics; `stopped` permits intentional inactivity and installs the exact unit/control service without auto-starting the AI worker.

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

## Affected contours

- VPS: YES — frontend and FastAPI additive worker-control routes.
- Ubuntu worker/relay: YES — dedicated control agent/systemd unit plus maintenance semantics.
- Windows AI Worker: NO.
- Summary impact: MIXED.
- API compatibility: additive only.
- Security impact: YES; bounded authenticated runtime-control capability.

## Validation

- Unit: agent auth, fixed operation allowlist, desired-state behavior, API origin validation and proxy errors.
- Integration: frontend/API route contract, private nginx ingress exclusion, systemd installation/update/rollback contract tests.
- End-to-end: exact PR Validation + Quality integration.
- Runtime-manual after separate production approval: confirm HLS playback before/during/after AI worker stop/start and exact service/control-agent state.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Finding: a root-capable private control service could become remote execution if request parameters are generalized | Mitigation: fixed paths, literal service name, bearer auth, RFC1918 listener validation, no shell=True, no arbitrary arguments | Evidence: tests/test_worker_operator_control.py
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Finding: maintenance code could misclassify intentional stop as worker failure and auto-start it | Mitigation: explicit desired-state marker integrated into updater/rollback contracts | Evidence: updater/rollback tests and runtime-manual acceptance
- RISK-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Finding: UI worker stop might accidentally couple to live stream controls | Mitigation: separate endpoints/buttons and invariant tests for HLS path plus absence of relay operations | Evidence: frontend/control tests
- RISK-004 | Category: PERF | Probability: 2 | Impact: 2 | Score: 4 | Finding: unreachable Ubuntu agent could stall operator UI/API | Mitigation: bounded <=5s upstream timeout and asynchronous UI error state | Evidence: API tests
- RISK-005 | Category: BUS | Probability: 2 | Impact: 4 | Score: 8 | Finding: operator cannot restart worker if the control service is tied to AI worker lifecycle | Mitigation: dedicated independently enabled control systemd unit | Evidence: systemd contract and runtime-manual acceptance

## Test design

- TEST-001 | Covers: AC-002, AC-003, AC-004, AC-005, AC-006 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py
- TEST-002 | Covers: AC-001, AC-010 | Level: integration | Priority: P1 | Evidence: tests/test_frontend_contract.py
- TEST-003 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_systemd.py
- TEST-004 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py
- TEST-005 | Covers: AC-009 | Level: integration | Priority: P0 | Evidence: tests/test_sea_speed_auth_v1.py
- TEST-006 | Covers: AC-011 | Level: end-to-end | Priority: P0 | Evidence: exact-head PR Validation + Quality integration
- TEST-007 | Covers: AC-012 | Level: runtime-manual | Priority: P0 | Evidence: production service status plus continuous Camera 1 HLS playback before/during/after stop/start, recorded on Issue #178

## Correct-course check

- Trigger: ARCHITECTURE PIVOT
- Issue impact: clarified that the existing private nginx worker ingress is Ubuntu->VPS, so reverse worker control uses a dedicated Ubuntu private agent instead of reusing that ingress direction.
- Specification impact: direct private agent and fixed browser/API routes are explicitly defined.
- Plan impact: architecture diagram and D-001 record the corrected direction.
- Tasks impact: includes private-agent installation and private-ingress exclusion validation.
- Authorization impact: NONE — no file-scope expansion, outcome change, credential redesign, media-boundary change or protected behavior expansion beyond the approved bounded worker-control capability.
- Follow-up: keep runtime listener/peer details inside the later exact-SHA production envelope and protected host configuration.

## Rollout and rollback

- Rollout order after separate production approval: deploy VPS additive API/frontend -> prepare/install Ubuntu exact release and independent control service -> verify control status -> perform bounded stop/start test while monitoring HLS -> record acceptance.
- Rollback order: stop using UI control -> restore previous VPS release -> restore previous Ubuntu exact unit/release using existing rollback path while preserving prior desired state. Camera relay/HLS requires no rollback because it is not changed.
- Production mutation during source delivery: NONE.

## Runtime feedback

- Actual architecture after acceptance: PENDING production evidence.
- Differences from plan: NONE YET beyond the pre-write D-001 direction clarification recorded above.
- Deferred cleanup: NONE YET.
