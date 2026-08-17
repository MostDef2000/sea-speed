# Implementation Plan: Reciprocal Water/Road navigation toggle

- Specification: specs/021-water-road-reciprocal-nav/spec.md
- Issue: #209
- Status: Implementing

## Architecture

This is a bounded protected-frontend change. The Water and Road pages keep their existing document structure, session handling, runtime endpoints and controls. Each page reuses the existing `.objects-link` pill styling for one reciprocal context link:

- Water `/sea-speed/` -> highlighted `Дорога` -> `/sea-speed/road/`;
- Road `/sea-speed/road/` -> highlighted `Вода` -> `/sea-speed/`.

No JavaScript routing, API route, Worker behavior, analytics schema, camera source, Authentik rule, MediaMTX route, private M2M ingress or Ubuntu runtime asset is added or changed.

Runtime delivery is VPS-only because the two HTML files are served from the VPS release. Source integration itself performs no production mutation.

## Decisions

- D-001: Reuse the existing header pill component rather than introduce a new navigation component.
- D-002: Keep `Реестр объектов` and `Камеры` unchanged and place the reciprocal context action immediately after `Камеры` on both pages.
- D-003: Make the reciprocal action visually highlighted on both pages because it is a domain switch, not a current-page tab marker.
- D-004: Lock exact reciprocal link text/targets and preserved authenticated navigation contracts in `tests/test_frontend_contract.py`, and keep `tests/test_analytics_profiles.py` synchronized so Water/Objects/Cameras retain Road navigation while the Road page reciprocates to Water without weakening private-source/M2M/control checks.
- D-005: Treat runtime delivery as VPS-only with `CONNECTOR`; Ubuntu Worker/relay is explicitly not required and operator actions expected remain zero.
- D-006: Keep production separately gated by exact merged SHA, production authorization fingerprint, post-merge Quality and VPS release evidence.

## Affected contours

- VPS: REQUIRED. Only the protected Water and Road frontend HTML release changes at runtime.
- Ubuntu Worker/relay: NOT REQUIRED. No Worker, relay, analytics profile, protected source or service-control asset changes.
- Windows: retired and not an active production contour.
- VPS execution capability: `CONNECTOR`.
- Operator actions expected: `0`.

## Validation

Source validation requires an exact seven-path diff, valid linked SDD quality layer, focused reciprocal-navigation assertions, synchronized analytics-profile navigation regression with all protected-source/M2M/control assertions retained, the existing frontend behavioral contracts, PR Validation and aggregate Quality integration on the same exact head.

Before merge, refresh `main`, PR head, exact changed-file list, reviews and review threads. Merge only with expected-head protection. After merge, require post-merge Quality on the exact new main SHA.

Runtime validation is separate: exact-SHA production authorization, VPS Connector deployment, accepted release/deployment evidence, then authenticated browser smoke for both navigation directions and preserved session usability.

## Risk profile

- Risk profile: NOT REQUIRED

The change is presentation-only, uses existing protected URLs and existing link styling, introduces no new trust boundary, schema, control path, secret, service, camera source or destructive operation. Deployment remains covered by the standard VPS exact-release transaction and separate production authorization.

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: integration | Priority: P0 | Evidence: tests/test_frontend_contract.py and tests/test_analytics_profiles.py
- TEST-002 | Covers: AC-003 | Level: end-to-end | Priority: P0 | Evidence: linked SDD validation, PR Validation, aggregate Quality integration, expected-head merge and post-merge main Quality
- TEST-003 | Covers: AC-004 | Level: runtime-manual | Priority: P0 | Evidence: Issue #209 exact production authorization, VPS deployment manifest and authenticated Water↔Road browser smoke

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: Product outcome is unchanged. CI first required the canonical SDD triplet for significant frontend changes, expanding source scope from three to six paths. Exact-head behavioral CI then exposed one stale historical Road self-link assertion in `tests/test_analytics_profiles.py`, expanding scope from six to seven paths solely to synchronize that regression with the already approved reciprocal behavior.
- Specification impact: `021-water-road-reciprocal-nav` now records the final seven-path scope and the exact behavioral-CI finding while preserving the original reciprocal navigation outcome and VPS-only runtime boundary.
- Plan impact: The delivery-quality layer records Risk profile NOT REQUIRED, test design, exact VPS transaction audit, the SDD linkage correction, and the second CI-driven regression synchronization without changing production/runtime semantics.
- Tasks impact: Delivery tasks and acceptance traceability include the SDD remediation, analytics-profile regression synchronization, exact seven-path CI, merge, separate production authorization, VPS deployment and browser acceptance.
- Authorization impact: RESOLVED. The latest fresh complete six-field seven-path Scope was presented immediately before the operator replied `OUTCOME APPROVED`; durable evidence is Issue #209 comment `5316347354`.
- Follow-up: Change only `tests/test_analytics_profiles.py` to replace the stale Road self-link assumption with the reciprocal Road→Water assertion, update only the already-authorized SDD triplet to record the seven-path correct-course state, require exact-head green CI and expected-head merge, then request a separate production authorization for the exact merged SHA before any VPS mutation.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains unchanged and deployment is rejected | Retry: only after exact target is on current main first-parent with green Quality and valid durable production authorization | Rollback: not applicable because no mutation occurred | Evidence: production authorization verifier, current-main ancestry check and exact release provenance
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: current VPS release remains authoritative and candidate activation does not begin | Retry: only after VPS connectivity, exact artifact and deployment preflight are healthy | Rollback: not applicable before mutation | Evidence: VPS deployment preflight and exact artifact verification
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release is not accepted and the deployment transaction restores or retains the previous release | Retry: only after the failure root cause is resolved and actual current state is re-read | Rollback: restore the exact previous VPS release identified by the deployment transaction | Evidence: VPS deploy logs, release directory identity and rollback markers
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: an unverified candidate is not accepted as the production release | Retry: only after health/public-route failure is resolved and the exact candidate is reverified | Rollback: revert to the exact previous accepted VPS release if candidate verification fails | Evidence: protected public smoke, frontend route checks and exact source/release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: current-release and deployment manifest are not committed as accepted unless verification passed | Retry: after exact candidate identity and health are re-established | Rollback: restore the previous current-release pointer and accepted manifest state | Evidence: VPS current-release marker and deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified active release remains accepted while stale release cleanup may remain pending | Retry: safe after accepted runtime state without changing the active release | Rollback: no rollback of a verified release for housekeeping-only failure | Evidence: release pruning/cleanup output
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: runtime may be healthy but Issue #209 cannot be completed without durable exact evidence | Retry: re-read machine-observable runtime/deployment state and persist sanitized evidence without redeploying solely for evidence | Rollback: not applicable to evidence recording | Evidence: Issue #209 comments, exact workflow run IDs, deployment manifest and authenticated browser acceptance
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: the exact previous VPS release is restored or an unresolved production state is recorded fail-closed | Retry: prohibited until actual state and rollback outcome are verified | Rollback: exact previous accepted VPS release `dc0d09143b171a0c2846076db6555569988ff011` unless a newer accepted baseline is established before deployment | Evidence: rollback target SHA, active-release marker and protected health smoke

## Runtime feedback

- PR #210 initially contained only the two frontend paths and the focused frontend regression.
- Quality integration #377 derived the PR impact as VPS correctly, then failed at linked SDD validation because significant `frontend/**` changes require a canonical feature specification and delivery-quality layer.
- Fresh six-path authorization was recorded on Issue #209 comment `5316246154`; the product outcome and protected/runtime boundaries did not change.
- On exact head `0460ab1bfc1df8b0e51f03990228248161526119`, PR Validation #435 / `32032076813` and Quality #385 / `32032076857` both failed only because `tests/test_analytics_profiles.py` still required the Road page itself to contain `/sea-speed/road/`. The new reciprocal frontend contract passed, and SDD/Change Contract/repository/protected-boundary checks passed before the behavioral failure.
- Fresh seven-path authorization was recorded on Issue #209 comment `5316347354`; the seventh path is limited to synchronizing that stale assertion and retaining its private-source/M2M/bounded-control checks.
- Source integration remains non-production. Runtime remains VPS-only, `CONNECTOR`, zero operator actions, with Ubuntu Worker/relay explicitly not required.
- Final browser acceptance remains runtime-manual because static tests can prove link structure but cannot prove the protected production session and deployed navigation behavior.
