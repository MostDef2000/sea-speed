# Implementation Plan: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Issue: #178
- Status: Single dynamic Stream action remediation

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

The runtime product path is already accepted: Ubuntu exact source `8dc74762a344dbf763d3ce1e7ecb1bac6872affb` proved worker Stop/Start while Camera 1 HLS remained continuously available. The active continuation changes only the VPS-hosted Operator UI presentation: Worker remains a top-strip dynamic control, Stream uses exactly one dynamic Play/Stop action in the top Stream status item, and the Live camera card remains free of duplicate Stream controls. No API, worker agent, MediaMTX/relay, systemd or credential boundary changes.

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
- Decision: `cleanup()` captures `$?` on entry, attempts staging/optional backup/marker removal best-effort, and returns the captured status.
- Reason: updater housekeeping must not override the primary result.

### D-014 - Compact status-strip controls are single dynamic actions
- Decision: Worker remains one dynamic icon-only action. Stream is also exactly one dynamic action button in the top Stream status item: Play when HLS is not desired/playing, Stop when HLS is desired/active. The Live camera card contains no Stream action button. Worker Stop executes immediately without `confirm(...)`; dynamic `aria-label` and `title` describe each current action.
- Reason: showing Play and Stop simultaneously is redundant and caused the production browser acceptance to fail the intended compact-control UX. A single contextual action makes the available operation unambiguous without changing HLS lifecycle semantics.
- Alternatives rejected: two simultaneous top-strip Stream buttons, duplicate Live camera controls, or a worker confirmation popup.

## Affected contours

Current five-path UI continuation:
- Derived Change Contract production impact: `VPS`.
- VPS deployment: REQUIRED after exact-green merge and fresh exact-SHA production authorization/execution intent.
- Ubuntu worker/relay update: NOT REQUIRED.
- Windows worker update: NOT REQUIRED.
- Production safety envelope: REQUIRED for VPS only.
- Security impact: NONE.
- API/event/state/storage schema impact: NONE.
- Destructive/data migration impact: NO.
- Other high-risk trigger: YES — live runtime control presentation changes on the operator surface.

## Validation

- `tests/test_frontend_contract.py` proves Worker control remains separate from HLS semantics, contains no worker `confirm(...)`, renders exactly one `streamControlBtn` in the top status strip, dynamically exposes Play/Stop SVG state with accessible `aria-label`/`title`, contains no legacy `connectBtn`/`disconnectBtn`, and keeps the Live camera card free of Stream controls.
- Existing HLS retry/recovery/autoconnect semantics remain authoritative and unchanged.
- Existing worker-control API/security/systemd/update/rollback tests remain authoritative through aggregate Quality integration.
- Exact source delivery requires PR Validation + aggregate Quality integration on one final five-path head.
- Runtime after merge requires only VPS deployment plus browser smoke: exactly one Stream action and one Worker action are present in the top strip, no duplicate Stream controls exist, and HLS behavior remains usable.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: TECH | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: bind updater to the real quality-verifier CLI and execute its parser surface | Validation: tests/test_ubuntu_worker_exact_updater.py | Residual risk: historical Ubuntu release risk is regression-protected | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: preserve exact legacy/modern control topology on activation failure and rollback | Validation: updater/rollback regression plus accepted runtime evidence | Residual risk: historical systemd risk is regression-protected | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: updater cleanup preserves primary status while every cleanup operation is guarded best-effort | Validation: executable EXIT-trap cleanup regression | Residual risk: historical housekeeping risk is regression-protected | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: DATA | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: updater cleanup excludes protected release/runtime/shared state | Validation: source assertions and accepted Ubuntu runtime | Residual risk: historical temporary-artifact risk only | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: frontend contract proves one dynamic Stream action, unique IDs, no Live camera duplicates and unchanged HLS lifecycle | Validation: tests/test_frontend_contract.py plus production browser smoke | Residual risk: visual spacing varies by browser width but action remains accessible through label/title | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-002,AC-003,AC-004,AC-005,AC-006 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py
- TEST-002 | Covers: AC-001,AC-010,AC-021 | Level: integration | Priority: P0 | Evidence: tests/test_frontend_contract.py
- TEST-003 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_systemd.py
- TEST-004 | Covers: AC-008,AC-018,AC-019,AC-020 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py
- TEST-005 | Covers: AC-009 | Level: integration | Priority: P0 | Evidence: tests/test_sea_speed_auth_v1.py
- TEST-006 | Covers: AC-011 | Level: end-to-end | Priority: P0 | Evidence: exact-head PR Validation + Quality integration
- TEST-007 | Covers: AC-012,AC-021 | Level: runtime-manual | Priority: P0 | Evidence: production Operator UI single-action smoke after VPS-only deploy

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: Issue #178 remains canonical and open; terminal UI acceptance is not yet satisfied.
- Specification impact: Scenario 4, FR-001/FR-021, AC-001/AC-021 and NFR operator-UX wording require one dynamic Stream action.
- Plan impact: D-014 and validation/rollout are revised; backend/runtime boundaries remain unchanged.
- Tasks impact: current five-path UI continuation is re-opened for single-action remediation and requires a fresh exact-green merge/VPS deployment/browser smoke.
- Authorization impact: operator supplied fresh `OUTCOME APPROVED` immediately after the visible six-field five-path Scope on 2026-08-16.
- Follow-up: merge only exact-green five-path source, then obtain one exact-release VPS production authorization carrying execution intent and complete the UI smoke.

## Deployment transaction audit

This audit models the VPS-only rollout of the compact Operator UI; it does not redeploy Ubuntu or Windows.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production VPS remains on the accepted previous release | Retry: correct exact SHA/quality/authorization evidence then re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact first-parent SHA, push/main Quality integration, canonical Issue production authorization and execution intent
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores previous exact release | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after actual current release is known | Rollback: automatic previous-release verification through accepted loopback origin and protected public smoke | Evidence: origin health on 127.0.0.1:8010, public smoke, exact frontend release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous exact VPS release remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but UI acceptance remains incomplete | Retry: recollect browser smoke without redeployment when exact runtime identity is unchanged | Rollback: decide from actual UI/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus Operator UI single-action smoke
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if previous exact release cannot be restored/verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous exact VPS release | Evidence: existing VPS rollback logs and verified origin/public health

## Rollout and rollback

- Source rollout: merge only the exact green five-path UI continuation after fresh base/head/scope/review verification and expected-head protection.
- Production checkpoint: exact push/main Quality integration + exact VPS artifact evidence for the merge SHA, then one fresh VPS production authorization with `Execution-Intent: EXECUTE`.
- Deployment: existing repository-owned VPS deploy workflow only; Ubuntu Worker and Windows Worker are not redeployed.
- Product acceptance: verify exactly one dynamic Stream Play/Stop action and one Worker `▶`/`■` action in the top status strip, no worker confirmation popup, no Stream controls in Live camera, and normal HLS operation.
- Rollback: existing VPS previous exact release through the protected deployment transaction.

## Runtime feedback

- Worker-control runtime outcome is accepted on Ubuntu exact source `8dc74762a344dbf763d3ce1e7ecb1bac6872affb`; Stop/Start did not interrupt Camera 1 HLS.
- VPS UI polish `0c2651629f517f939b8d18cacbc624654e8c4e11` was deployed/runtime-verified, but browser acceptance rejected its two simultaneously visible Stream actions.
- Current source authorization and exact five-path scope are recorded on Issue #178 after the fail-closed visible Scope gate.
