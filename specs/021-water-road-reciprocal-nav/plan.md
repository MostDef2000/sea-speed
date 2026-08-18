# Implementation Plan: Reciprocal Water/Road navigation toggle

- Specification: specs/021-water-road-reciprocal-nav/spec.md
- Issue: #209
- Status: Implementing

## Architecture

This is a bounded protected-frontend outcome whose executable runtime release is already integrated as exact merge `e4183d329ef970160582021a2b6ed4608822c907`. The Water and Road pages keep their existing document structure, session handling, runtime endpoints and controls. Each page reuses the existing `.objects-link` pill styling for one reciprocal context link:

- Water `/sea-speed/` -> highlighted `Дорога` -> `/sea-speed/road/`;
- Road `/sea-speed/road/` -> highlighted `Вода` -> `/sea-speed/`.

No JavaScript routing, API route, Worker behavior, analytics schema, camera source, Authentik rule, MediaMTX route, private M2M ingress or Ubuntu runtime asset is added or changed.

Runtime delivery is VPS-only because the two HTML files are served from the VPS release. Production learning established that the VPS Auth privileged helper/bundle is root-owned and exact-source-bound. The exact runtime release must therefore receive one repository-owned root privilege-boundary bootstrap before the normal Connector VPS deployment can pass its pre-live-mutation admission. This corrective PR changes only this SDD triplet and creates no new runtime release.

## Decisions

- D-001: Reuse the existing header pill component rather than introduce a new navigation component.
- D-002: Keep `Реестр объектов` and `Камеры` unchanged and place the reciprocal context action immediately after `Камеры` on both pages.
- D-003: Make the reciprocal action visually highlighted on both pages because it is a domain switch, not a current-page tab marker.
- D-004: Lock exact reciprocal link text/targets and preserved authenticated navigation contracts in `tests/test_frontend_contract.py`, and keep `tests/test_analytics_profiles.py` synchronized so Water/Objects/Cameras retain Road navigation while the Road page reciprocates to Water without weakening private-source/M2M/control checks.
- D-005: Treat runtime release `e4183d329ef970160582021a2b6ed4608822c907` as VPS-only with truthful execution capability `ONE_COMMAND_FALLBACK`; Ubuntu Worker/relay is explicitly not required and operator actions expected is `1`.
- D-006: Preserve the existing exact production authorization in Issue #209 comment `5321867764` because the production-learning correction does not change the Outcome Contract or immutable merged PR #210 fields bound into the fingerprint: active runtime deployment contours, security impact, production-impact rationale and rollback target.
- D-007: Use the repository-owned `deploy/vps/install-auth-privilege-boundary.sh` exact-source transaction for the single fallback. The installer must be run from an exact `e4183d...` checkout as root for non-root deployment user `sea-speed-deploy`; after PASS, the Connector remains the owner of VPS release mutation, verification, evidence and rollback.
- D-008: Treat this corrective PR itself as CONTROL_PLANE/NONE because it changes only `specs/**`; it must not create a new production envelope or cause a deployment of its corrective merge SHA.

## Affected contours

For the already authorized executable runtime release `e4183d329ef970160582021a2b6ed4608822c907`:

- VPS: REQUIRED. Only the protected Water and Road frontend HTML release changes at runtime.
- Ubuntu Worker/relay: NOT REQUIRED. No Worker, relay, analytics profile, protected source or service-control asset changes.
- Windows: retired and not an active production contour.
- VPS execution capability: `ONE_COMMAND_FALLBACK`.
- Operator actions expected: `1`.

For this production-learning corrective PR, changed paths are only `specs/021-water-road-reciprocal-nav/{spec,plan,tasks}.md`, so its derived production impact is `NONE`; both active runtime deployment fields and execution capabilities are not applicable to the corrective source integration itself.

## Validation

Original product source validation is complete: exact seven-path scope, linked SDD, focused reciprocal-navigation assertions, synchronized analytics-profile regression with protected-source/M2M/control checks retained, PR Validation #441 / `32032753264`, aggregate Quality #391 / `32032753207`, expected-head merge as `e4183d329ef970160582021a2b6ed4608822c907`, and post-merge Quality #392 / `32032834524`.

Production-learning corrective source validation requires exactly the three authorized SDD paths from Issue #209 comment `5321926492`, a machine-valid `PRODUCTION_LEARNING` correct-course record and adjacent-stage transaction audit, PR Validation and aggregate Quality on the same exact corrective head, fresh main/head/scope/review checks, expected-head merge, and post-merge Quality. Because the correction is specs-only, its resulting main SHA is governance/source evidence only and does not replace runtime target `e4183d...`.

Runtime validation remains separately governed by the already durable authorization for `e4183d...`: execute one exact-source root privilege-boundary bootstrap, require transactional PASS evidence, then issue the canonical Connector VPS deployment retry for the same runtime target. Require exact release/deployment evidence with `runtimeVerified=true` and `state=runtime_verified`, followed by authenticated browser smoke for both navigation directions and preserved session usability.

## Risk profile

- Risk profile: NOT REQUIRED

The product change is presentation-only and the production-learning correction is specs-only. No security-impact field, schema, destructive/data migration, MIXED runtime, new privileged implementation, secret handling or trust-boundary redesign is introduced by this correction. The known operational privilege-boundary constraint is handled by fail-closed exact-source admission, the existing repository-owned transactional installer, the standard Connector deployment transaction and the mandatory production-learning audit below.

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: integration | Priority: P0 | Evidence: tests/test_frontend_contract.py and tests/test_analytics_profiles.py plus original exact-head repository behavioral validation
- TEST-002 | Covers: AC-003 | Level: end-to-end | Priority: P0 | Evidence: original PR Validation #441, Quality #391, merge `e4183d...`, post-merge Quality #392, exact three-path corrective compare, corrective PR Validation/Quality and corrective post-merge Quality
- TEST-003 | Covers: AC-004 | Level: runtime-manual | Priority: P0 | Evidence: Issue #209 production authorization comment `5321867764`, exact-source root privilege-bootstrap PASS, subsequent Connector VPS `runtime_verified` deployment manifest and authenticated Water↔Road browser smoke

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Product outcome and protected runtime behavior are unchanged. Production delivery analysis after authorization showed that the VPS root-owned Auth privilege bundle is exact-source-bound, so Connector-only execution metadata for runtime release `e4183d329ef970160582021a2b6ed4608822c907` was not truthful; the correct capability is one root fallback followed by Connector deployment.
- Specification impact: FR-007/FR-008, AC-003/AC-004, release-provenance NFR evidence and runtime feedback now record VPS `ONE_COMMAND_FALLBACK`, operator actions expected `1`, the exact bootstrap requirement, unchanged runtime target and retained production authorization.
- Plan impact: VPS capability/action budget, runtime sequencing, validation, test evidence and the eight-stage production transaction audit are corrected; this corrective PR is explicitly distinguished as specs-only CONTROL_PLANE/NONE.
- Tasks impact: Original seven-path source integration and exact production authorization are reconciled to completed evidence; new bounded tasks cover the three-path corrective merge, one exact root bootstrap, Connector retry, browser smoke and terminal Issue completion.
- Authorization impact: RESOLVED. Fresh exact three-path source authorization is durable in Issue #209 comment `5321926492`. Existing runtime production authorization comment `5321867764` and fingerprint `38f6346631f398363b4205dc9ae2e23b52aeff432dd17ea41934de9bbf5b4835` remain applicable because no fingerprint-bound Outcome Contract/PR field changed.
- Follow-up: Merge only the exact green three-path corrective head and require post-merge Quality; then execute the single repository-owned root privilege-boundary bootstrap for exact runtime release `e4183d329ef970160582021a2b6ed4608822c907`, retry the canonical Connector VPS deployment under the existing production authorization, and complete authenticated browser acceptance.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: The root-owned Auth privileged bundle installed for the prior accepted VPS runtime embeds that prior exact source SHA, while `deploy/vps/deploy.sh` for target `e4183d329ef970160582021a2b6ed4608822c907` stages the exact target and then invokes privileged status admission before any live source, service, current-release, deployment-manifest or nginx mutation. The privileged helper requires installed bundle `source_sha` to equal the request `source_sha`, so Connector-only activation cannot pass until the repository-owned root installer rebinds the bundle to `e4183d...`.
- Production-learning adjacent-stage findings: Admission before the privilege check already has an exact merged runtime target, successful post-merge Quality #392 and durable exact production authorization; the source-bound mismatch is a PRE-MUTATION boundary before accepted live release mutation; `install-auth-privilege-boundary.sh` transactionally backs up and restores helper/bundle/sudoers on failure; after bootstrap PASS the ordinary Connector VPS workflow remains responsible for release mutation, verification, state commit, evidence and rollback. No Ubuntu action is applicable.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on the previously accepted runtime and execution is rejected | Retry: only when exact runtime target `e4183d...` remains on current main first-parent, post-merge Quality #392 remains valid, durable production authorization matches and the corrective SDD source state is accepted | Rollback: not applicable because no mutation occurred | Evidence: merge/first-parent identity, Quality #392, Issue #209 comments `5321867764`, `5321895134` and corrective source integration evidence
- TX-002 | Stage: PRE-MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: no candidate VPS release is accepted; if the root bootstrap mutates then fails, the installer restores the prior helper, privileged bundle and sudoers transactionally | Retry: re-resolve actual root-bundle state, ensure an exact `e4183d...` repository checkout and rerun only the repository-owned installer once the failure cause is resolved | Rollback: installer backup/cleanup restores the previous root-owned helper/bundle/sudoers on bootstrap failure; no live application release rollback is required before Connector activation | Evidence: installer exact-checkout/repository-identity admission plus `SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS`, exact `SOURCE_SHA`, fixed-helper/no-root-shell markers or rollback marker
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: Connector candidate activation is not accepted and the previous accepted VPS release remains or is restored by the existing deploy transaction | Retry: only after bootstrap PASS and after the Connector failure root cause is resolved with actual current state re-read | Rollback: restore the exact previous accepted VPS application release through the canonical deploy transaction | Evidence: Connector VPS deployment logs, exact release identity and rollback markers
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: an unverified candidate is not accepted as production; protected auth/private-M2M and frontend health must remain fail-closed | Retry: only after failed health/public-route/security evidence is resolved and the same exact candidate is reverified | Rollback: canonical VPS deploy restores the previous accepted application release/auth state when candidate verification fails | Evidence: origin/public protected smokes, frontend route checks, private-M2M auth check and exact source/runtime identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: current-release and deployment manifest are not accepted unless verification passed | Retry: only after exact candidate identity and verification are re-established | Rollback: restore previous current-release/manifest state through the canonical deploy transaction | Evidence: current-release marker and deployment manifest with `sourceCommit=e4183d...`, `runtimeVerified=true`, `state=runtime_verified`
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified active runtime remains accepted while stale release cleanup may remain pending | Retry: safe after accepted runtime state without changing the active release | Rollback: no rollback of a verified release for housekeeping-only failure | Evidence: release pruning/cleanup output and retained current/previous release identity
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: runtime may be healthy but Issue #209 cannot become DONE without durable bootstrap, deployment and browser evidence | Retry: re-read machine-observable state and persist sanitized evidence without redeploying solely to regenerate evidence | Rollback: not applicable to evidence recording | Evidence: Issue #209 comments, exact workflow run/artifact IDs, deployment manifest and authenticated browser acceptance
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: the exact previous accepted VPS release/root privilege state is restored or a critical unresolved production state is recorded fail-closed | Retry: prohibited until actual runtime/root-bundle state and rollback outcome are verified | Rollback: bootstrap failures restore the prior root bundle transactionally; Connector failures use the exact previous accepted VPS release recorded by the deployment transaction | Evidence: installer rollback marker when applicable, Connector rollback markers, previous source SHA/current-release marker and protected health smoke

## Runtime feedback

- Original exact seven-path product source was accepted through PR #210: final head `114221486c3cdd24ce1f063f09e55bb517a0e917`, PR Validation #441 / `32032753264`, Quality #391 / `32032753207`, merge runtime target `e4183d329ef970160582021a2b6ed4608822c907`, and post-merge Quality #392 / `32032834524`.
- Source-integration evidence is Issue #209 comment `5316405026`. The executable runtime target remains `e4183d329ef970160582021a2b6ed4608822c907`.
- Exact runtime production authorization is Issue #209 comment `5321867764`, fingerprint `38f6346631f398363b4205dc9ae2e23b52aeff432dd17ea41934de9bbf5b4835`, execution intent `EXECUTE`.
- Production-learning evidence is Issue #209 comment `5321895134`: the root-owned Auth bundle is source-bound and is checked before accepted live-source mutation, so the truthful VPS capability is `ONE_COMMAND_FALLBACK` with one operator action, followed by Connector deployment; Ubuntu Worker/relay remains NOT REQUIRED.
- Fresh source authorization for this correction is comment `5321926492`, bounded to exactly this `spec.md`, `plan.md` and `tasks.md` triplet.
- This correction creates no new runtime-installed source and does not alter immutable PR #210 authorization-bound fields; the existing production authorization remains the runtime authority for `e4183d...`.
- No accepted live-source mutation is claimed before the exact root bootstrap. Remaining runtime sequence is bootstrap -> Connector VPS retry -> exact deployment evidence -> authenticated reciprocal-navigation browser acceptance.
