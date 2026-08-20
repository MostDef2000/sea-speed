# Implementation Plan: Authentik 30-Day Session Retention

- Specification: specs/029-authentik-session-retention/spec.md
- Issue: #231
- Status: Source implementation

## Architecture

The product change is two managed Authentik User Login stage attributes in the existing canonical blueprint: ordinary login and post-enrollment login move to `session_duration: days=30`; remember-me/device offsets stay disabled. Authentik 2026.5.6 already runs on the Ubuntu Worker and the worker monitors the bind-mounted blueprint file, so no image pull, database migration, server restart or full identity restage is required.

The source location is historical: the canonical blueprint remains under `deploy/vps/authentik/blueprints/**`, but production ownership is Ubuntu. The change-control policy therefore adds a more-specific first-match `UBUNTU_WORKER` rule for that subtree before the generic `deploy/vps/**` VPS rule. The exact merged #231 diff should consequently derive one active contour: Ubuntu Worker/relay.

`deploy/worker/ubuntu/deploy-authorized.sh` remains the target-side Ubuntu transaction. Protected GitHub Actions has already evaluated standing delegation with `--require-allow` before transport. The target script independently proves exact current-main first-parent source, classifies the exact merge diff for transaction selection, and uses a dedicated Authentik-only path when the canonical blueprint changed without analytics runtime files. The previous obsolete call to the retired per-release verifier is removed.

`deploy/worker/ubuntu/authentik/reconcile-blueprint.sh` validates the exact source blueprint, snapshots the two current managed User Login stage values through `docker compose exec -T worker ak shell`, backs up the current mounted blueprint, writes through the existing bind-mounted file inode, and polls the same two ORM objects for `days=30|seconds=0|seconds=0`. Authentik's worker handles blueprint discovery/apply from the file modification. Verification failure restores the previous bytes and requires the pre-change runtime values to reappear before returning bounded rollback success.

The Authentik-only path snapshots Water/Road service active states before reconciliation and requires them unchanged after it. It does not call analytics profile reconciliation, `update-exact.sh`, analytics rollback, nginx, PostgreSQL or Docker image pull/restart. Successful execution emits the standard Ubuntu deployment manifest with exact source/previous-main identity and runtime checks. The protected workflow then builds existing typed execution audit evidence.

## Decisions

- D-001: Use one 30-day managed login-session duration for both ordinary and post-enrollment login; do not enable Authentik remember-me/device extensions.
- D-002: Preserve the canonical blueprint path and correct source-derived runtime ownership with a specific Ubuntu rule rather than relocating historical identity source in this Outcome.
- D-003: Apply the blueprint by modifying the existing bind-mounted runtime file and relying on Authentik worker file watching; do not restart Authentik containers solely for session retention.
- D-004: Verify runtime through Authentik ORM for the two exact Sea Speed User Login stage names, not by assuming file copy equals successful blueprint application.
- D-005: On verification failure restore the exact pre-mutation blueprint and require the pre-mutation ORM state before declaring rollback success.
- D-006: Treat the exact #231 release as Authentik-only even though it also changes target transaction/helper/test/control-plane files; exclude `deploy-authorized.sh` and `deploy/worker/ubuntu/authentik/**` from analytics-runtime detection.
- D-007: Reject a future exact merge that combines this Authentik blueprint mutation with analytics-worker runtime mutation; a combined transaction requires separate explicit design rather than implicit sequencing.
- D-008: Remove target-side consumption of the retired per-release verifier. Standing delegation remains enforced by the protected Ubuntu workflow before transport; target-side checks remain exact source, bounded mutation and runtime integrity.
- D-009: Keep current `ONE_COMMAND_FALLBACK` planning capability because durable runtime evidence says restricted zero-touch Ubuntu transport is not provisioned. Operator actions expected: 1 unless capability changes before execution.
- D-010: Use the successful #231 release as the first ordinary runtime-impacting acceptance for the standing-delegation Outcome #229.

## Affected contours

- Source/control plane: REQUIRED — blueprint, change-control mapping, Ubuntu target transaction, tests, docs and SDD change.
- Production impact: `UBUNTU_WORKER`.
- VPS deployment: NOT REQUIRED.
- Ubuntu Worker/relay update: REQUIRED.
- VPS execution capability: NOT APPLICABLE.
- Ubuntu worker execution capability: `ONE_COMMAND_FALLBACK` from latest durable evidence; may become `CONNECTOR` only if the protected workflow freshly proves transport provisioned before runtime execution.
- Operator actions expected: 1 under current capability.
- Security impact: REQUIRED because authenticated session lifetime changes from hours to days.
- Production safety envelope: REQUIRED — exact policy allow, exact source, bounded blueprint mutation, runtime ORM verification, rollback and evidence.

## Validation

Source tests assert exactly two 30-day duration declarations, two disabled remember-me/device settings and unchanged Owner TOTP/role/password-policy markers. Policy tests load the real change-control contract and prove the blueprint path derives only Ubuntu Worker impact.

The reconcile-helper tests run the actual shell transaction in a sandbox with a fake Docker/ORM boundary. They cover successful update, idempotent no-op and failed apply with byte/runtime rollback. Source assertions prohibit image pull and PostgreSQL/Water/Road restart primitives.

Ubuntu target-transaction tests preserve the established analytics transaction checks while proving: exact-main first-parent validation precedes mutation; no retired production-verifier call remains; Authentik-only and analytics-runtime mutation are separate; Authentik-only does not invoke analytics profile/update/rollback paths; Water/Road state comparison and the Authentik runtime checks enter the deployment manifest.

Before PR creation, compare exact branch files with Issue #231 Scope, run Change Contract/SDD/repository validation, and verify no secret/runtime artifact is tracked. PR Validation and aggregate Quality must pass on one exact head. Merge requires fresh main/head/scope/review state and exact expected-head protection when supported. Exact-main Quality must succeed before autonomous runtime routing is accepted.

After exact-main Quality, the autonomous router must evaluate standing policy for the merged #231 release. If Ubuntu restricted SSH remains unavailable, the protected Ubuntu workflow must emit its exact one-command fallback only after policy `allow`. The operator executes that single repository-owned artifact on the canonical Ubuntu Worker as root/sudo. Runtime acceptance then requires the standard deployment manifest and typed execution audit plus browser validation of protected Sea Speed, Owner TOTP semantics and explicit Logout.

## Risk profile

- Risk profile: REQUIRED

Extending an authenticated browser session increases the window in which a stolen session cookie could remain useful. The requested product trade-off is bounded by retaining explicit Logout/revocation, Owner TOTP at login, no remember-me/device extension, existing access roles and the existing Authentik Forward Auth boundary. Deployment risk is bounded by blueprint-only mutation, exact runtime verification and rollback.

- RISK-001 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: 30-day maximum applies only after successful existing authentication; Owner still requires TOTP; remember-me/device remain disabled; logout/session revocation remain available | Validation: blueprint contract and browser acceptance | Residual risk: a valid stolen session can persist longer before natural expiry; this is the explicit usability/security trade-off requested by the operator | Owner: Sea Speed operator | Status: ACCEPTED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: mutate only the mounted blueprint; poll exact ORM stage values; restore previous bytes/runtime on failure | Validation: successful/idempotent/rollback helper tests plus production manifest | Residual risk: Authentik worker file-watcher latency may delay apply; bounded poll fails rather than assuming success | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: Authentik-only path bypasses analytics config/update/rollback and asserts Water/Road service states unchanged | Validation: transaction source tests and production service-state evidence | Residual risk: unrelated host-level failure could occur concurrently; actual state must be resolved before retry | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: protected workflow evaluates standing delegation before transport; target no longer consumes retired verifier; no per-release authority text is reintroduced | Validation: workflow/policy and target source assertions; policy decision evidence | Residual risk: operator with root access can always mutate the host outside repository workflow, which remains outside this delivery contract | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: current `ONE_COMMAND_FALLBACK` is explicitly modeled and produced only after exact policy allow; one operator action completes the same repository-owned target transaction | Validation: protected workflow result and fallback runtime manifest/audit | Residual risk: human root/sudo execution remains required until restricted zero-touch Ubuntu transport is provisioned | Owner: Sea Speed operator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P0 | Evidence: canonical blueprint has exactly two `days=30`, no active legacy duration, and two zero remember offsets/devices with TOTP/roles/password markers retained
- TEST-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: real change-control policy derives `UBUNTU_WORKER` only for the blueprint path
- TEST-003 | Covers: AC-004,AC-005 | Level: integration | Priority: P0 | Evidence: Ubuntu target transaction has first-parent gate, no retired verifier, separate Authentik-only path and no analytics mutation within that path
- TEST-004 | Covers: AC-006,AC-007 | Level: integration | Priority: P0 | Evidence: sandbox helper successful update, idempotency, rollback and forbidden-mutation source assertions
- TEST-005 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: exact GitHub changed-file list is subset of Issue #231 Scope and exactly matches PR Change Contract
- TEST-006 | Covers: AC-009 | Level: integration | Priority: P0 | Evidence: PR Validation, aggregate Quality, expected-head merge and exact-main Quality on exact identities
- TEST-007 | Covers: AC-010 | Level: runtime-manual | Priority: P0 | Evidence: standing policy allow decision for exact merged #231 source with Ubuntu contour and no per-release prompt
- TEST-008 | Covers: AC-011 | Level: runtime-manual | Priority: P0 | Evidence: Ubuntu deployment manifest `runtime_verified`, Authentik 30-day checks, Water/Road unchanged and typed execution audit; fallback artifact/output when required
- TEST-009 | Covers: AC-012 | Level: runtime-manual | Priority: P0 | Evidence: protected Sea Speed access, Owner TOTP behavior, applied 30-day stage configuration and explicit Logout termination
- TEST-010 | Covers: AC-013 | Level: end-to-end | Priority: P0 | Evidence: #229 receives first autonomous ordinary release chain from exact-main Quality through policy allow/deploy/runtime/audit

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #231 is a new product/security Outcome; Issue #229 remains open specifically awaiting the first ordinary autonomous runtime release and can consume #231 execution evidence.
- Specification impact: changes authenticated session lifetime and adds exact blueprint-runtime acceptance; no camera/analytics or identity-role topology change.
- Plan impact: introduces a bounded Authentik-only Ubuntu target transaction and corrects first-match runtime routing for the historical blueprint location.
- Tasks impact: requires source/CI integration, then standing-policy runtime routing, likely one fallback execution, runtime/browser acceptance and evidence feedback to both #231 and #229.
- Authorization impact: source lifecycle is authorized by the immediate `OUTCOME APPROVED`; runtime authority remains the already-configured standing delegation. No new per-release production authorization is requested.
- Follow-up: provision restricted zero-touch Ubuntu transport separately if desired; it is not required to deliver the 30-day session Outcome.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: the production login-session contract remained at 12 hours despite the operator's desired 30-day retention, while the historical blueprint path was generically classified as VPS even though active Authentik runs on Ubuntu and the Ubuntu target still retained an obsolete per-release verifier.
- Production-learning adjacent-stage findings: admission must derive the Ubuntu contour from exact source, pre-mutation must prove exact current-main and existing Authentik state, mutation must remain blueprint-only, verification must query exact ORM stages and preserve Water/Road state, state-commit/evidence must bind runtime verification and typed audit, and rollback must restore both blueprint bytes and observed runtime values.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no Ubuntu runtime transport occurs when exact-main Quality or standing policy admission is absent/denied | Retry: after exact source/Quality/policy state is valid | Rollback: not applicable | Evidence: exact-main Quality + policy decision JSON for #231
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: runtime unchanged; target must prove exact source on current main first-parent, exact Authentik-only classification, existing runtime compose/blueprint and readable two-stage pre-state | Retry: after source/host precondition correction | Rollback: not applicable before mutation | Evidence: target logs, source SHA, pre-state query, Water/Road state snapshot
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: only `/opt/sea-speed-auth/blueprints/sea-speed-auth-v1.yaml` may have changed; backup exists until transaction completion | Retry: prohibited until verification/rollback resolves actual state | Rollback: restore exact pre-mutation blueprint bytes | Evidence: helper source/target digest, `AUTHENTIK_BLUEPRINT_CHANGED=YES|NO`
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: new session configuration is not accepted unless both exact ORM stages show `days=30|seconds=0|seconds=0` and Water/Road service states remain unchanged | Retry: helper polls bounded attempts; after expiry it enters rollback | Rollback: restore previous blueprint and verify previous ORM state | Evidence: `AUTHENTIK_LOGIN_STAGES_VERIFIED=2`, `AUTHENTIK_SESSION_DURATION=days=30`, service-state comparison
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: release is not marked runtime-verified unless helper/runtime checks passed | Retry: only after full verification | Rollback: previous main is recorded as rollback target; helper already restored on failed apply | Evidence: Ubuntu deployment manifest with exact source, previousVersion/rollbackTarget and `runtimeVerified=true`
- TX-006 | Stage: HOUSEKEEPING | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: verified runtime can remain accepted; temporary exact-source stage/backup cleanup may be retried safely | Retry: remove target-owned temporary files only | Rollback: no runtime rollback solely for cleanup failure | Evidence: target cleanup/trap completion and no leaked secret values
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: runtime may be healthy but Outcome remains incomplete without policy/release/deployment/audit and browser evidence | Retry: read/rebuild deterministic evidence without redeploy when exact identity remains provable | Rollback: not applicable | Evidence: policy decision, v3 release manifest, deployment manifest, execution audit, Issue #231/#229 comments
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: previous blueprint/runtime values are restored or runtime is unresolved and no retry is allowed | Retry: only after actual state is proven | Rollback: pre-mutation blueprint bytes and pre-mutation exact two-stage ORM values | Evidence: `AUTHENTIK_BLUEPRINT_ROLLBACK=PASS` or critical unresolved-state log

## Runtime feedback

- The existing runtime is healthy enough that this Outcome is configuration-only; no Authentik server/PostgreSQL topology change is justified.
- Authentik worker file-watch behavior makes in-place mounted-file mutation the narrowest supported application mechanism; the transaction still verifies database-backed stage state rather than trusting the watcher.
- Current durable Ubuntu capability is `ONE_COMMAND_FALLBACK`. Source and CI work can complete autonomously; the fallback root/sudo execution becomes the only expected operator action if the capability remains unchanged at deployment time.
