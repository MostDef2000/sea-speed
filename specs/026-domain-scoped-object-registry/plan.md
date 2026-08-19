# Implementation Plan: Domain-scoped Object Registry

- Specification: specs/026-domain-scoped-object-registry/spec.md
- Issue: #223
- Status: Production-learning delivery correction

## Architecture

The product architecture remains unchanged: one shared Objects frontend uses the existing generic `/sea-speed/api/objects` API and SQLite storage, with immutable Water (`cam1` / `water`) or Road (`road1` / `road`) scope in the browser. This corrective PR changes no frontend, backend, storage, Worker, camera, authentication, proxy, media or analytics source.

The production runtime target remains exact merged product SHA `0af31b5e2516fb0d529228a51025693e7a932779`. Request runtime deployment run `32219455747` proved that source admission, authorization, quality, provenance and transport were valid, but the protected VPS privilege bundle was still bound to the prior source SHA. The deployment therefore stopped before candidate acceptance.

The production-learning correction records the effective VPS capability for this rollout as `ONE_COMMAND_FALLBACK` with one operator action: refresh the repository-owned protected privilege boundary to the exact authorized product target, then retry the existing canonical VPS deployment for the same target. Ubuntu Worker remains NOT REQUIRED. The corrective merge SHA is control-plane evidence only and is not a replacement runtime release.

## Decisions

- D-001: Keep the original product implementation and exact runtime target unchanged; corrective source is SDD-only.
- D-002: Preserve one shared Objects page and existing API/storage implementation.
- D-003: Treat run `32219455747` as authoritative production-learning evidence: admission and transport passed, candidate acceptance did not.
- D-004: Correct rollout capability from `CONNECTOR` to `ONE_COMMAND_FALLBACK` because the protected privilege bundle is exact-source-bound.
- D-005: Require exactly one operator action to refresh that repository-owned boundary to target `0af31b5e2516fb0d529228a51025693e7a932779`.
- D-006: After refresh evidence, retry failed VPS deployment job `95967126921` / run `32219455747`; do not create another production authorization record and do not deploy Ubuntu Worker.
- D-007: Preserve authorization fingerprint semantics; Issue #223 Outcome Contract and merged PR #224 authorization-bound fields remain unchanged.
- D-008: Final runtime acceptance still requires accepted `runtime_verified` VPS evidence followed by authenticated Water/Road browser smoke.

## Affected contours

- Corrective source PR: CONTROL_PLANE / NONE; exactly the `026` SDD triplet.
- Existing authorized product target: VPS REQUIRED for `0af31b5e2516fb0d529228a51025693e7a932779`.
- VPS execution capability for this rollout: ONE_COMMAND_FALLBACK.
- Operator actions expected: 1.
- Ubuntu Worker/relay: NOT REQUIRED.
- Backend/API/storage: unchanged.
- Camera/media and authentication/proxy topology: unchanged and out of scope.

## Validation

Corrective source validation requires the final base-to-head diff to contain exactly three paths: `spec.md`, `plan.md`, and `tasks.md` in `specs/026-domain-scoped-object-registry/`. PR Validation and aggregate Quality must pass on the same exact corrective head. Before merge, refresh current `main`, exact head, changed-file set and review state; merge only with expected-head protection. Exact-main Quality must then pass on the corrective merge SHA.

The corrective merge does not replace production authorization for the product target and does not deploy the corrective SHA. After corrective source evidence is durable, the one repository-owned protected-boundary refresh must report exact-target PASS markers. Then retry failed VPS job `95967126921` in request run `32219455747`. Accepted deployment evidence must validate `runtime_verified` for the exact authorized target. Browser acceptance then proves Water entry shows only `cam1/water`, Road entry shows only `road1/road`, scope survives Reset/reload, and ordinary scoped operations remain usable.

## Risk profile

- Risk profile: NOT REQUIRED

The corrective source change is SDD-only and introduces no new security boundary, runtime code, schema, destructive data change, secret or MIXED runtime requirement. The production-learning trigger still requires a complete Deployment Transaction Audit. Runtime risk remains bounded by the existing fail-closed exact-source boundary, exact target authorization, one repository-owned operator action, canonical deployment retry, rollback identity and browser acceptance.

## Test design

- TEST-001 | Covers: AC-001,AC-002,AC-003,AC-004,AC-005,AC-006 | Level: integration | Priority: P0 | Evidence: previously green frontend contract tests on product PR #224; no product bytes change in corrective PR
- TEST-002 | Covers: AC-007,AC-008 | Level: integration | Priority: P0 | Evidence: PR #224 exact-head CI and exact-main Quality run `32218234279` for product target `0af31b5e2516fb0d529228a51025693e7a932779`
- TEST-003 | Covers: AC-010 | Level: integration | Priority: P0 | Evidence: exact three-path corrective diff plus PR Validation and aggregate Quality on one exact corrective head, expected-head merge and exact-main Quality
- TEST-004 | Covers: AC-011 | Level: runtime-manual | Priority: P0 | Evidence: repository-owned protected-boundary refresh markers proving exact target and fixed privilege topology
- TEST-005 | Covers: AC-012 | Level: end-to-end | Priority: P0 | Evidence: retried VPS job `95967126921` reaches accepted `runtime_verified` for exact product target while Ubuntu contour remains skipped
- TEST-006 | Covers: AC-009 | Level: runtime-manual | Priority: P0 | Evidence: authenticated Water/Road browser acceptance after accepted VPS deployment

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #223 keeps the same product Outcome; runtime acceptance now records one required operator boundary refresh before canonical VPS retry.
- Specification impact: delivery requirements now distinguish the unchanged product target from the SDD-only corrective merge and record `ONE_COMMAND_FALLBACK`.
- Plan impact: rollout sequence is corrected to source-learning CI/merge -> protected-boundary refresh -> retry existing authorized VPS job -> browser acceptance.
- Tasks impact: corrective source CI/merge tasks and the one operator-action/retry evidence path are added; previously completed product source tasks are marked complete.
- Authorization impact: corrective source has fresh `OUTCOME APPROVED`; existing production authorization for target `0af31b5e2516fb0d529228a51025693e7a932779` remains unchanged because authorization-bound Issue/PR fields are not modified.
- Follow-up: merge the three-path corrective PR, obtain exact-target protected-boundary PASS evidence, retry failed VPS job `95967126921`, validate `runtime_verified`, complete authenticated browser acceptance, then persist final Issue #223 evidence.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: the protected VPS privilege bundle is intentionally bound to an exact source SHA; run `32219455747` requested `0af31b5e2516fb0d529228a51025693e7a932779` while the installed bundle still identified the previous source, so deployment failed closed before candidate acceptance.
- Production-learning adjacent-stage findings: admission, exact-main Quality, durable authorization, exact artifacts, quality evidence, release provenance, transport configuration and Ubuntu contour routing behaved correctly; the stale element was delivery capability classification because one repository-owned protected-boundary refresh is required before retry.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on the previous accepted VPS release and candidate is not admitted | Retry: only with exact authorized target, exact-main Quality and durable production authorization intact | Rollback: not applicable before runtime mutation | Evidence: request job `95967088051` success, target `0af31b5e2516fb0d529228a51025693e7a932779`, Quality run `32218234279`
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate remains unaccepted and previous production remains active | Retry: refresh repository-owned protected boundary to exact target, require PASS evidence, then retry failed VPS job | Rollback: protected-boundary installer is transactional; product runtime rollback is not required before candidate activation | Evidence: run `32219455747` reported a required privilege-boundary bootstrap and source-SHA mismatch; later PASS markers unblock retry
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: canonical deployment rejects candidate and preserves or restores previous accepted VPS release | Retry: only after actual runtime state and exact boundary identity are verified | Rollback: restore exact previous accepted VPS release through canonical deployment transaction | Evidence: retried VPS deployment logs and previous/current release markers
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: unverified candidate is not accepted as production | Retry: only after protected frontend/API/auth verification failures are resolved | Rollback: canonical transaction restores previous accepted release if verification cannot pass | Evidence: deployment checks, protected health and exact release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment manifest/current-release state cannot claim acceptance unless verification passed | Retry: only after exact candidate verification is re-established | Rollback: restore previous current-release/manifest state through canonical deployment transaction | Evidence: deployment manifest with exact source commit, `runtimeVerified=true`, `state=runtime_verified`
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified active runtime remains accepted while stale cleanup may remain pending | Retry: safe after accepted runtime without changing active release | Rollback: no rollback solely for housekeeping failure after verified acceptance | Evidence: release cleanup output from retried deployment
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: runtime may be healthy but Issue #223 remains open until durable deployment and browser evidence are recorded | Retry: re-read machine-observable state and persist sanitized evidence without redeploying solely for evidence | Rollback: not applicable to evidence recording | Evidence: corrective CI/merge IDs, protected-boundary PASS markers, retried deployment IDs and browser acceptance recorded on Issue #223
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: previous accepted VPS release is restored or unresolved critical state remains fail-closed and documented | Retry: prohibited until actual runtime and rollback state are verified | Rollback: use exact previous accepted VPS release recorded by canonical transaction | Evidence: rollback markers, previous source/current-release identity and protected health smoke

## Runtime feedback

- Product PR #224 merged as `0af31b5e2516fb0d529228a51025693e7a932779`; exact-main Quality run `32218234279` succeeded.
- Issue #223 carries exact production authorization for the same target with execution intent `EXECUTE`.
- Request runtime deployment run `32219455747` validated authorization, target, Quality, tooling, exact artifacts, quality evidence and release provenance; transport configuration succeeded and Ubuntu Worker was skipped.
- VPS job `95967126921` then failed before accepted candidate state because the protected privilege bundle source SHA did not match the authorized target.
- Root cause is delivery capability metadata, not product code or transport. Effective capability for this rollout is `ONE_COMMAND_FALLBACK`, operator actions expected `1`.
- Corrective source is limited to this SDD triplet and does not modify product code, deploy scripts, workflows, Issue Outcome Contract, PR #224 fields, production fingerprint, target SHA or Ubuntu Worker state.
- After corrective merge and exact-main Quality, perform the one repository-owned protected-boundary refresh and retry existing failed VPS job `95967126921`; do not create a duplicate production authorization comment. Final completion still requires `runtime_verified` and authenticated Water/Road registry acceptance.
