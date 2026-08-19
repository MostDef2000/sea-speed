# Implementation Plan: Domain-scoped Object Registry

- Specification: specs/026-domain-scoped-object-registry/spec.md
- Issue: #223
- Status: Source implementation

## Architecture

This is a bounded protected-frontend change. The existing Water and Road Operator pages keep their current navigation targets, authenticated session behavior and runtime controls. The shared Objects page becomes domain-scoped by resolving one of two immutable frontend scopes:

- `water` -> `camera_id=cam1`, `domain=water`;
- `road` -> `camera_id=road1`, `domain=road`.

A valid explicit `?scope=water|road` is authoritative. If scope is absent, only a same-origin `/sea-speed/road/` referrer selects Road; all other entries default Water. The resolved scope is immediately canonicalized into the URL. Camera/domain controls are rendered as locked reflections of that scope, while search/date/speed/status filters, pagination and object detail operations remain on the existing generic `/sea-speed/api/objects` contract.

No backend, SQLite, worker, camera, Authentik, nginx, MediaMTX, H264 or analytics-runtime code changes are permitted. Runtime impact is VPS-only because the served Objects HTML belongs to the VPS release.

## Decisions

- D-001: Reuse one shared Objects page and one existing API/storage implementation; do not fork Water/Road databases or backend endpoints.
- D-002: Make explicit `scope` authoritative and canonicalize inferred context immediately so reload/direct links do not depend on referrer state.
- D-003: Infer Road only from a same-origin Road Operator referrer when scope is absent; otherwise default Water, including unsupported explicit scope after canonicalization.
- D-004: Force scoped `camera_id` and `domain` into every list query and ignore ordinary form attempts to override those two keys.
- D-005: Reset clears ordinary filters only, then reapplies the immutable active scope.
- D-006: Preserve existing PATCH/DELETE/session/pagination behavior and newest-100/newest-300 retention semantics.
- D-007: Treat `frontend/sea-speed/index.html` and `frontend/sea-speed/road/index.html` as authorized but unchanged because their common Objects links are sufficient for contextual resolution.
- D-008: Use unique SDD prefix `026`; `025-tool-routing-contract` remains untouched.

## Affected contours

- VPS: REQUIRED after separate exact-SHA production authorization because `frontend/sea-speed/objects/index.html` is served from the VPS release.
- Ubuntu Worker/relay: NOT REQUIRED. No worker, relay, analytics profile or protected source changes.
- Windows: retired and not an active production contour.
- Backend/API/storage: unchanged; generic `/sea-speed/api/objects` filtering is reused.
- Camera/RTSP/H264/MediaMTX: unchanged and explicitly out of scope.
- Authentik/nginx/private M2M: unchanged and explicitly out of scope.

## Validation

Source validation requires the final base-to-head diff to remain exactly the intended five-file subset of the corrected seven-path authorization: Objects frontend, focused frontend contract test, and the `026` SDD triplet. PR Validation must pass Change Contract admission, SDD validation, repository/contracts/schema/runtime-evidence validation and behavioral tests. Aggregate Quality must pass on the same exact final head.

Before merge, refresh current `main`, exact PR head, changed-file scope and review state. Merge only with expected-head protection. Then require exact-main Quality on the resulting merge commit and persist source-integration evidence on Issue #223.

Runtime validation is separate: only after a fresh exact-SHA production authorization may the canonical VPS deployment transaction activate the merged release. Acceptance requires Water entry showing only `cam1/water`, Road entry showing only `road1/road`, scope persistence across Reset/reload, and smoke coverage for filters/pagination/edit/delete compatibility.

## Risk profile

- Risk profile: NOT REQUIRED

The change is frontend-only and reuses existing authenticated API/storage behavior. It introduces no security-impact field, schema migration, destructive data change, MIXED runtime contour, new secret, new trust boundary or privileged implementation. Production risk is handled by exact-SHA authorization, canonical VPS deployment, rollback and browser acceptance.

## Test design

- TEST-001 | Covers: AC-001,AC-002,AC-003,AC-004,AC-005,AC-006 | Level: integration | Priority: P0 | Evidence: `tests/test_frontend_contract.py` domain-resolution, scope-lock, Reset/reload, filter/pagination and existing detail-operation assertions
- TEST-002 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: exact five-file changed-scope verification plus PR Validation and aggregate Quality on one exact head
- TEST-003 | Covers: AC-008 | Level: end-to-end | Priority: P0 | Evidence: expected-head merge followed by exact-main Quality and Issue #223 source-integration evidence
- TEST-004 | Covers: AC-009 | Level: runtime-manual | Priority: P0 | Evidence: separately authorized VPS deployment manifest plus authenticated Water/Road browser acceptance

## Correct-course check

- Trigger: NONE
- Issue impact: NONE; the approved product outcome remains Water-only registry from Water and Road-only registry from Road.
- Specification impact: NONE beyond completing the mandatory SDD quality structure and the already approved `025` to `026` path correction.
- Plan impact: NONE beyond recording the canonical validation and later VPS transaction explicitly.
- Tasks impact: NONE beyond making CI, merge, production authorization and runtime acceptance gates machine-auditable.
- Authorization impact: NONE; the corrected path Scope already received exact `OUTCOME APPROVED`, and production remains separately unauthorized.
- Follow-up: complete exact-head CI, expected-head merge and exact-main Quality; then request separate exact-SHA production authorization before VPS mutation.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on the previously accepted VPS release and the candidate is rejected | Retry: only after exact merged target, exact-main Quality and durable production authorization are all valid | Rollback: not applicable because no production mutation occurred | Evidence: current-main first-parent identity, exact-main Quality, production authorization verifier
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate release is not activated and existing production remains unchanged | Retry: only after protected Auth/runtime preconditions and release provenance pass | Rollback: not applicable before live mutation | Evidence: canonical VPS deployment admission and preflight logs
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate activation is rejected and previous accepted VPS release remains or is restored | Retry: only after the mutation failure cause is resolved and actual state is re-read | Rollback: restore exact previous accepted VPS release through the canonical deployment transaction | Evidence: deployment mutation logs and previous/current release markers
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: unverified candidate is not accepted as production | Retry: only after protected route/frontend/API verification failures are resolved | Rollback: canonical deployment restores the previous accepted release if verification fails | Evidence: protected health checks, frontend route checks and exact release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: current-release/deployment manifest are not accepted unless verification passed | Retry: only after exact candidate verification is re-established | Rollback: restore previous current-release/manifest state through the canonical deploy transaction | Evidence: deployment manifest with exact source commit, runtime verification and accepted state
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified active runtime remains accepted while stale cleanup may remain pending | Retry: safe after accepted runtime without changing the active release | Rollback: no rollback of a verified release for housekeeping-only failure | Evidence: release pruning/cleanup output
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: runtime may be healthy but Issue #223 cannot be terminally accepted without durable deployment and browser evidence | Retry: re-read machine-observable state and persist sanitized evidence without redeploying solely for evidence | Rollback: not applicable to evidence recording | Evidence: workflow/run IDs, deployment manifest and authenticated browser acceptance recorded on Issue #223
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: exact previous accepted VPS release is restored or the unresolved critical state remains fail-closed and documented | Retry: prohibited until actual runtime state and rollback outcome are verified | Rollback: use the exact previous accepted release recorded by the deployment transaction | Evidence: rollback markers, previous source SHA/current-release marker and protected health smoke

## Runtime feedback

- Initial implementation stayed within the approved frontend/test/SDD boundary; no backend, storage, worker, camera or auth path entered the PR diff.
- Early PR Validation attempts failed only at Change Contract/SDD admission: first on PR metadata fields, then on a duplicate SDD prefix because `025-tool-routing-contract` already occupies `025` on `main`.
- Fresh path-correction authorization moved the branch-only SDD triplet to unique prefix `026`. Final GitHub changed-file inspection shows exactly five paths: Objects frontend, frontend contract test and `specs/026-domain-scoped-object-registry/{spec,plan,tasks}.md`.
- Change Contract admission now passes with derived impact `VPS` and five changed files. The remaining remediation is completion of the repository-mandated SDD quality structure followed by normal behavioral CI.
- No production mutation is claimed or authorized during source integration. VPS deployment remains a later exact-SHA transaction after merge and exact-main Quality.
