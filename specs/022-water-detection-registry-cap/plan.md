# Implementation Plan: Water detection activation and registry cap

- Specification: specs/022-water-detection-registry-cap/spec.md
- Issue: #212
- Status: Implementing

## Architecture

The existing shared analytics-profile layer remains the only source of model/profile defaults. `water-v1` is the safe no-argument default while Road continues to select `road-v1` explicitly through protected configuration.

The Objects Registry remains one SQLite `objects` table shared by Water and Road. Retention is implemented in the persistence layer, not the frontend or list API: a deterministic pruning helper deletes all rows outside the newest 100 ordered by `detected_at DESC, object_id DESC`. It runs after schema/index initialization and after a successful new insert. JSON event history and snapshot/media lifecycle remain unchanged.

Executable runtime applicability remains MIXED for exact runtime target `9e0cd96aa2f790f1ba806299c3dd4019e5572899`: VPS receives the API/storage change, then Ubuntu receives the shared Worker profile-default change and Water activation. Production learning established an additional VPS pre-mutation prerequisite: the root-owned Auth privilege bundle is exact-source-bound, so it must be transactionally rebound to the exact runtime target before the normal Connector VPS deployment can pass privilege admission. This corrective PR changes only the SDD triplet and creates no new runtime release.

## Decisions

- D-001: Use `water-v1` as the safe default because the primary shared Water worker is the no-argument analytics consumer; Road already has explicit protected `road-v1` configuration.
- D-002: Enforce the test cap in SQLite persistence so API filters/pagination cannot bypass retention.
- D-003: Cap the combined Water + Road registry at 100 rows, matching the approved test-stage outcome.
- D-004: Retain deterministic newest ordering by `detected_at DESC, object_id DESC`.
- D-005: Do not delete snapshot/media assets or truncate JSON event-history files in this Outcome.
- D-006: Preserve strict rollout order: VPS privilege bootstrap -> canonical VPS deployment -> registry acceptance -> Ubuntu exact release/Water activation.
- D-007: Treat VPS execution capability for exact runtime target `9e0cd96aa2f790f1ba806299c3dd4019e5572899` as `ONE_COMMAND_FALLBACK`; the single VPS fallback is the repository-owned exact-source `deploy/vps/install-auth-privilege-boundary.sh` transaction, after which Connector deployment remains responsible for application mutation, verification, evidence, and rollback.
- D-008: Keep Ubuntu execution capability `ONE_COMMAND_FALLBACK` unless restricted zero-touch SSH transport is independently observed as provisioned; worst-case operator actions expected for the MIXED release are `2`.
- D-009: This production-learning corrective PR is specs-only and derives `NONE` production impact; it must not deploy its corrective merge SHA or replace executable runtime target `9e0cd96aa2f790f1ba806299c3dd4019e5572899`.
- D-010: Preserve the existing runtime production authorization because the production-learning correction changes neither the Issue Outcome Contract nor immutable PR #213 fields used by the authorization fingerprint: runtime contour declarations, security impact, production-impact rationale, rollback target, Issue, PR, or source SHA.

## Affected contours

For the already authorized executable runtime release `9e0cd96aa2f790f1ba806299c3dd4019e5572899`:

- VPS: REQUIRED — `api/app/main.py` changes persistent storage behavior. Execution capability: `ONE_COMMAND_FALLBACK` due exact-source-bound root Auth privilege bundle, followed by canonical Connector VPS deployment.
- Ubuntu Worker/relay: REQUIRED — `worker/analytics_profiles.py` changes shared executable Worker default semantics and the accepted Outcome includes Water activation. Execution capability: `ONE_COMMAND_FALLBACK` unless restricted zero-touch transport is independently proven available.
- Windows: retired; NOT APPLICABLE.
- Operator actions expected: `2` worst case when both required contours remain `ONE_COMMAND_FALLBACK`.

For this production-learning corrective PR, changed paths are only `specs/022-water-detection-registry-cap/{spec,plan,tasks}.md`, so its derived production impact is `NONE`; VPS and Ubuntu deployment fields and execution capabilities are not applicable to the corrective source integration itself.

## Validation

Original product source validation is complete on PR #213: exact seven-path scope, final exact head `1a619bc50ed5e6f8316bf13aa95f68a7c2e39a5e`, PR Validation #449 / `32094366745`, aggregate Quality #399 / `32094366780`, expected-head merge as runtime target `9e0cd96aa2f790f1ba806299c3dd4019e5572899`. The protected runtime deployment workflow independently rejects production mutation unless a successful exact `push/main` Quality run exists for that exact runtime SHA.

Production-learning corrective source validation requires exactly the three authorized SDD paths from Issue #212 comment `5323340646`, a machine-valid `PRODUCTION_LEARNING` correct-course record and adjacent-stage transaction audit, PR Validation and aggregate Quality on the same exact corrective head, fresh main/head/scope/review checks, expected-head merge, and post-merge Quality. Because the correction is specs-only, its resulting main SHA is governance/source evidence only and does not replace runtime target `9e0cd96...`.

Runtime validation remains bound to exact target `9e0cd96...`: first execute one exact-source VPS root privilege-boundary bootstrap and require transactional PASS evidence; then run the canonical VPS deployment and require exact source, health, `runtime_verified` deployment evidence, and registry count <=100; only after VPS acceptance, deploy/activate Ubuntu Water and require exact source/runtime identity, protected model/profile values, service state, advancing frame/state/AI telemetry, and Water `vessel` events reaching the registry.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: DATA | Probability: 5 | Impact: 4 | Score: 20 | Mitigation: deterministic pruning only outside newest 100; explicit test-stage contract; no media deletion | Validation: oversized initialization and insertion tests plus production registry check | Residual risk: pruned SQLite history is not recoverable by source rollback | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: exact-source root bootstrap is isolated before VPS application mutation; VPS-first acceptance precedes Ubuntu activation; separate exact-SHA production gate remains authoritative | Validation: bootstrap markers, deployment manifests, and runtime registry count | Residual risk: a failed mixed rollout can leave one contour on the new release; contours remain backward compatible | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: preserve exact YOLO26x/ByteTrack/threshold/class-map values and add default-profile regression | Validation: analytics-profile tests and runtime model/profile evidence | Residual risk: protected runtime config can still override defaults intentionally | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: pruning operates on at most the transient current registry and uses existing detected-at index | Validation: unit contract and production smoke | Residual risk: one delete query occurs after each successful insert | Owner: Delivery Orchestrator | Status: ACCEPTED
- RISK-005 | Category: OPS | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: treat source-bound root privilege state as an explicit PRE-MUTATION transaction; use only repository-owned transactional installer with rollback, fixed helper/no-args sudo scope, and exact repository/SHA admission | Validation: privilege installer PASS/rollback markers and subsequent Connector preflight | Residual risk: root bootstrap still requires one protected operator action on the VPS | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `tests/test_analytics_profiles.py`
- TEST-002 | Covers: AC-002,AC-003 | Level: unit | Priority: P0 | Evidence: `tests/test_api_contract.py`
- TEST-003 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: existing API contract suite
- TEST-004 | Covers: AC-005,AC-006 | Level: integration | Priority: P0 | Evidence: original exact compare/CI/merge plus exact three-path corrective compare, PR Validation, aggregate Quality, expected-head merge and post-merge Quality
- TEST-005 | Covers: AC-007 | Level: runtime-manual | Priority: P0 | Evidence: exact-source VPS privilege-bootstrap PASS, VPS deployment manifest and direct registry-count evidence
- TEST-006 | Covers: AC-008 | Level: runtime-manual | Priority: P0 | Evidence: Ubuntu deployment manifest or one-command fallback evidence, Water service/telemetry, protected model/profile identity and resulting Water object evidence

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Product outcome, exact runtime target, Water model/profile semantics, registry cap and MIXED contour set are unchanged. Production preflight showed that the VPS root-owned Auth privileged bundle is exact-source-bound, so the original Connector-only VPS execution metadata is not truthful for `9e0cd96aa2f790f1ba806299c3dd4019e5572899`.
- Specification impact: FR-011/FR-012, AC-005/AC-006/AC-007/AC-008, release-provenance NFR evidence and Runtime feedback now record the exact VPS bootstrap requirement, truthful execution capabilities, operator-action budget and unchanged runtime target.
- Plan impact: VPS capability/action budget, rollout sequencing, validation, risk record, test evidence and the eight-stage deployment transaction audit are corrected; this PR is explicitly distinguished as specs-only with no runtime deployment.
- Tasks impact: Original source integration and production authorization are reconciled to completed evidence; new bounded tasks cover the three-path corrective merge, one exact VPS root bootstrap, Connector VPS acceptance, Ubuntu delivery/Water activation and terminal Issue evidence.
- Authorization impact: RESOLVED — fresh exact three-path source authorization is durable in Issue #212 comment `5323340646`. Existing runtime production authorization remains applicable because this correction does not change authorization-bound Issue/PR/source/runtime-contour/security/deployment-target/rollback fields.
- Follow-up: Merge only the exact green three-path corrective head with post-merge Quality; then execute one repository-owned VPS root privilege-boundary bootstrap for exact `9e0cd96...`, run canonical VPS deployment and registry acceptance, and only then continue Ubuntu exact release/Water activation.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: The installed root-owned Auth privilege bundle contains an exact `source_sha`, while `deploy/vps/deploy.sh` stages the requested exact release and invokes the privileged helper's status admission before any accepted live application/service/current-release/deployment-manifest/nginx mutation. `sea-speed-auth-privileged-helper.py` rejects a request when the installed bundle `source_sha` differs from the requested deployment SHA. The last accepted bundle is bound to an older runtime, so Connector-only delivery cannot pass for `9e0cd96aa2f790f1ba806299c3dd4019e5572899` until the repository-owned installer transactionally rebinds it to that exact SHA.
- Production-learning adjacent-stage findings: Admission already fixes the runtime target to one merged exact SHA and requires exact `push/main` Quality plus durable production authorization before mutation; the source-bound privilege mismatch is a PRE-MUTATION boundary, not an application-release mutation failure; `install-auth-privilege-boundary.sh` verifies exact checkout/repository identity and transactionally backs up/restores helper, bundle and sudoers on failure; after bootstrap PASS the existing Connector VPS transaction remains responsible for release mutation, verification, state commit, evidence and rollback; Ubuntu must remain blocked until VPS registry acceptance completes.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on previously accepted runtime and execution is rejected | Retry: only when exact runtime target `9e0cd96...` remains on current-main first-parent history, exact push/main Quality is successful, durable authorization matches, corrective SDD is accepted and rollback targets remain known | Rollback: not applicable because no mutation occurred | Evidence: runtime workflow admission, exact SHA/Quality verification, Issue #212 production authorization and corrective source evidence
- TX-002 | Stage: PRE-MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: no candidate VPS application release is accepted; if root bootstrap mutates then fails, the installer restores prior helper, privileged bundle and sudoers transactionally | Retry: re-resolve actual root-bundle state, ensure an exact `9e0cd96...` repository checkout, and rerun only the repository-owned installer after the failure cause is resolved | Rollback: installer backup/cleanup restores the previous root-owned helper/bundle/sudoers on bootstrap failure; no application release rollback is required before Connector activation | Evidence: exact-checkout/repository-identity admission plus `SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS`, exact `SOURCE_SHA`, fixed-helper/no-root-shell/fixed-topology markers or rollback marker
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: VPS or Ubuntu candidate is not accepted and the prior accepted executable release remains or is restored where supported | Retry: only after required prior contour acceptance and actual failure root cause are resolved | Rollback: canonical deployment transaction restores prior exact executable release; VPS must complete before Ubuntu mutation begins | Evidence: VPS/Ubuntu deployment logs and exact release identities
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: unverified candidate is not accepted; for VPS, registry pruning may already have deleted historical rows beyond newest 100 and those rows remain non-restorable | Retry: only after failed health/source/registry or Ubuntu telemetry/model/service evidence is resolved and the same exact candidate is reverified | Rollback: prior exact executable release; pruned SQLite history cannot be restored by source rollback | Evidence: VPS source/health/registry checks and Ubuntu source/model/profile/service/frame/state/AI/object checks
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: release markers/manifests remain unaccepted unless verification passed | Retry: only after exact candidate identity and verification are re-established | Rollback: restore previous current-release/manifest state where supported | Evidence: deployment manifests/current-release state with exact runtime source and `runtimeVerified=true`
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified active runtime remains accepted while stale release cleanup may remain pending | Retry: safe after acceptance without changing active release | Rollback: none for housekeeping-only failure | Evidence: cleanup output and retained current/previous release identity
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: task cannot reach DONE without durable corrective-source/bootstrap/deployment/registry/Water evidence | Retry: re-read machine-observable state and persist sanitized evidence without redeploying solely to regenerate evidence | Rollback: not applicable to evidence recording | Evidence: Issue #212, exact workflow/artifact IDs, deployment manifests and runtime acceptance records
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: prior executable/root privilege state is restored or a critical unresolved production state is recorded fail-closed | Retry: prohibited until actual runtime/root-bundle state and rollback outcome are verified | Rollback: bootstrap failures restore prior root bundle transactionally; runtime failures restore Ubuntu then VPS exact releases where safe; pruned registry history is explicitly non-restorable | Evidence: installer rollback marker when applicable, deployment rollback markers, previous source/current-release identity and protected health checks

## Runtime feedback

- Original exact seven-path product source was accepted through PR #213: final head `1a619bc50ed5e6f8316bf13aa95f68a7c2e39a5e`, PR Validation #449 / `32094366745`, Quality #399 / `32094366780`, and expected-head merge runtime target `9e0cd96aa2f790f1ba806299c3dd4019e5572899`.
- Source integration evidence is Issue #212 comment `5323051369`; it also records that the Connector wrapper could not itself enumerate exact merge-SHA push/main Quality, while protected deployment code independently enforces that exact gate before mutation.
- Production authorization for exact runtime target `9e0cd96...` was granted in chat with execution intent. Issue #212 comment `5323137259` durably records the first two authority lines, and comment `5323138127` issued the VPS-only deployment request to preserve VPS-first sequencing without invoking the parallel MIXED router.
- Production-learning analysis established the exact-source root Auth privilege mismatch before accepted VPS live mutation. Current repository code confirms `deploy/vps/deploy.sh` emits `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES` when privilege admission fails and the helper requires the root bundle `source_sha` to equal the requested release SHA.
- Fresh source authorization for this production-learning correction is Issue #212 comment `5323340646`, bounded to exactly this `spec.md`, `plan.md` and `tasks.md` triplet.
- This correction creates no executable/runtime artifact and does not alter immutable PR #213 authorization-bound fingerprint fields; executable runtime target remains `9e0cd96aa2f790f1ba806299c3dd4019e5572899`.
- No accepted new VPS application release or Ubuntu Water activation is claimed before the required runtime sequence. Remaining order is corrective SDD merge -> exact VPS root bootstrap -> canonical VPS deployment/registry acceptance -> Ubuntu exact release/Water activation -> terminal evidence.