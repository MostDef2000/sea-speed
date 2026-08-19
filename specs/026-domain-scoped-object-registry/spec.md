# Feature Specification: Domain-scoped Object Registry

- Feature: 026-domain-scoped-object-registry
- Issue: #223
- Status: Production-learning delivery correction
- Owner outcome: Water and Road operators open a registry that remains locked to the domain they came from, without changing backend storage or retention.

## Product outcome

The Water operator opens a Water registry scoped to `camera_id=cam1` and `domain=water`. The Road operator opens a Road registry scoped to `camera_id=road1` and `domain=road`. The shared Objects page remains one frontend and one existing SQLite/API contract, but its ordinary navigation and reset flow cannot silently broaden a domain-scoped view into the combined registry.

Existing Water/Road operator markup may keep the common `/sea-speed/objects/` destination. When that destination has no explicit `scope`, the Objects page derives the initial scope only from the same-origin operator referrer (`/sea-speed/road/` -> Road; otherwise Water), immediately canonicalizes the current URL to `?scope=water|road`, and thereafter treats that explicit scope as authoritative across reload/reset. The Objects page itself exposes explicit Water/Road scoped links.

The product/runtime target remains exact merged SHA `0af31b5e2516fb0d529228a51025693e7a932779`. Production learning from Request runtime deployment run `32219455747` changes only the documented delivery capability: the VPS root-owned Auth privilege bundle must be refreshed to the exact runtime target before the canonical Connector deployment can continue. This corrective source change does not alter product bytes, the runtime target, the authorization fingerprint, or Ubuntu Worker state.

## User scenarios

### Scenario 1 - Water operator opens the Water registry

Given an authenticated operator is on `/sea-speed/`, when the operator opens `Реестр объектов`, then the shared Objects page resolves to Water scope, canonicalizes the URL to `?scope=water`, and every list request remains locked to `camera_id=cam1` and `domain=water`.

### Scenario 2 - Road operator opens the Road registry

Given an authenticated operator is on `/sea-speed/road/`, when the operator opens `Реестр объектов`, then the shared Objects page resolves to Road scope, canonicalizes the URL to `?scope=road`, and every list request remains locked to `camera_id=road1` and `domain=road`.

### Scenario 3 - Scope survives ordinary navigation and reset

Given either scoped registry is open, when the operator reloads the page, copies the scoped URL, changes ordinary filters, paginates or presses Reset, then the selected Water/Road domain remains authoritative while search/date/speed/status filters and object detail operations continue to work within that domain.

### Scenario 4 - Existing backend and retention remain unchanged

Given the scoped registry UI is deployed, the generic `/sea-speed/api/objects` endpoint, SQLite schema, newest-100 Objects retention, newest-300 Water Passage retention, object edit/delete semantics, workers and analytics runtime remain unchanged.

### Scenario 5 - Exact-source VPS privilege bootstrap precedes deployment retry

Given the authorized target `0af31b5e2516fb0d529228a51025693e7a932779` has passed exact-main Quality and durable production authorization, when the VPS privilege bundle still identifies an older source SHA, then the canonical deployment must fail closed before accepting the candidate. The operator performs exactly one repository-owned root bootstrap from the authorized exact source, after which the failed VPS deployment job may be retried for the same target SHA.

## Requirements

- FR-001: Entry from Water Operator MUST resolve to Water scope and entry from Road Operator MUST resolve to Road scope; this MAY be implemented by same-origin operator-referrer inference when the existing navigation URL has no explicit `scope`.
- FR-002: `scope=water` MUST force `camera_id=cam1` and `domain=water` on every Objects list request.
- FR-003: `scope=road` MUST force `camera_id=road1` and `domain=road` on every Objects list request.
- FR-004: Camera and domain controls MUST visibly reflect the locked scope and MUST NOT allow ordinary form interaction to remove or cross the domain lock.
- FR-005: Reset MUST clear ordinary filters while preserving the active domain lock.
- FR-006: A valid explicit scope MUST be authoritative. When scope is absent, only a same-origin Road operator referrer MAY select Road; otherwise Water is the default. An unsupported explicit scope MUST canonicalize to Water rather than expose the combined registry.
- FR-007: The page MUST canonicalize the selected scope into `?scope=water|road` so reload and copied scoped URLs preserve the domain without depending on referrer state.
- FR-008: Search, date, speed, status, pagination, detail, edit and delete behavior MUST remain compatible.
- FR-009: The implementation MUST reuse the existing generic `/sea-speed/api/objects` endpoint; `api/app/main.py`, SQLite schema and retention behavior are out of scope.
- FR-010: Existing combined newest-100 retention and Water Passage newest-300 retention MUST remain unchanged.
- FR-011: Product runtime deployment MUST remain VPS-only for exact target `0af31b5e2516fb0d529228a51025693e7a932779`; Ubuntu Worker/relay update remains NOT REQUIRED.
- FR-012: The production-learning corrective source PR MUST change only this SDD triplet and MUST NOT become a replacement runtime release for the already authorized target.
- FR-013: VPS execution capability for the authorized target MUST be treated as `ONE_COMMAND_FALLBACK` with exactly one expected operator action when the root-owned privilege bundle source SHA differs from the requested exact target.
- FR-014: After the repository-owned privilege-boundary installer reports exact-source PASS, the canonical GitHub Actions VPS deployment MUST be retried for the same authorized target and must reach accepted `runtime_verified` evidence before browser acceptance.

## Acceptance criteria

- AC-001: Static frontend contract proves the unchanged Water/Road registry links plus contextual Objects entry logic resolve Water to `cam1/water` and Road to `road1/road`.
- AC-002: Objects frontend contract proves every list request contains the locked `camera_id` and `domain` and ignores form attempts to override those two keys.
- AC-003: Reset contract proves the domain scope is reapplied after form reset.
- AC-004: Camera/domain controls are locked while ordinary filters and pagination remain present.
- AC-005: The selected scope is canonicalized into the page URL and therefore survives reload/direct scoped navigation.
- AC-006: PATCH/DELETE detail workflow and same-origin session behavior remain present.
- AC-007: Original product PR #224 exact diff is a subset of the authorized paths and passed PR Validation plus aggregate Quality on one exact head.
- AC-008: Original product PR #224 expected-head merge is followed by exact-main Quality on `0af31b5e2516fb0d529228a51025693e7a932779`.
- AC-009: After the authorized VPS target is successfully deployed, browser acceptance proves Water and Road navigation each show only their own domain and scope survives reload/reset.
- AC-010: Production-learning corrective PR changes exactly `spec.md`, `plan.md`, and `tasks.md`; records the observed run `32219455747` root cause, `ONE_COMMAND_FALLBACK`, one operator action, full adjacent-stage transaction review, and passes exact-head PR Validation + aggregate Quality followed by exact-main Quality after merge.
- AC-011: Repository-owned VPS privilege bootstrap reports `SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS`, exact target SHA, fixed helper/no-args sudo scope, no root shell and fixed privileged topology before failed VPS deployment job `95967126921` is retried.
- AC-012: Retried VPS deployment for exact target `0af31b5e2516fb0d529228a51025693e7a932779` reaches `runtime_verified`; no Ubuntu Worker deployment is executed for this Outcome.

## NFR assessment

- NFR-001 | Area: BACKWARD_COMPATIBILITY | Target: no backend/API/storage contract change | Validation: exact original product diff plus frontend behavioral tests | Evidence: `api/app/main.py` and storage paths were absent from PR #224 diff; `tests/test_frontend_contract.py` retained edit/delete/session assertions | Status: PASS
- NFR-002 | Area: DATA_SAFETY | Target: no retention or schema mutation | Validation: exact changed-file scope | Evidence: original product PR changed only one frontend file, one test file and the linked SDD triplet; corrective PR is SDD-only | Status: PASS
- NFR-003 | Area: UX_SAFETY | Target: ordinary navigation, reload and Reset cannot silently broaden a scoped registry | Validation: focused frontend contract plus authenticated browser acceptance | Evidence: source tests passed on PR #224; runtime/browser acceptance remains pending until exact target is accepted on VPS | Status: CONCERNS
- NFR-004 | Area: OPERABILITY | Target: fail closed when the root-owned VPS privilege bundle is stale and require exact-source bootstrap before retry | Validation: run `32219455747`, repository-owned installer markers, retried deployment manifest | Evidence: authorization, exact-main Quality, provenance and SSH passed; deployment stopped at `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES` / `ERROR privileged bundle source SHA does not match request` before accepted candidate state | Status: CONCERNS
- NFR-005 | Area: PROVENANCE | Target: corrective source must not replace or silently re-authorize the existing runtime target | Validation: three-path corrective diff, unchanged Issue Outcome Contract/PR #224 authorization-bound fields, deployment retry uses original target | Evidence: target remains `0af31b5e2516fb0d529228a51025693e7a932779` with fingerprint `487789eafd52efddcc65da67bc119a98743d63567a699561da35a222ad056f26` | Status: PASS

## Runtime feedback

- Source authorization for the original seven-path outcome was granted with exact `OUTCOME APPROVED` after the operator-visible Scope on Issue #223.
- Initial CI admission exposed only Change Contract metadata defects and then an SDD numeric-prefix collision because `025-tool-routing-contract` already exists on `main`; no product-source behavioral failure was observed in those attempts.
- Fresh path-correction Scope was approved with exact `OUTCOME APPROVED`; the SDD triplet moved from branch-only `025-domain-scoped-object-registry` to unique `026-domain-scoped-object-registry` while the product outcome and runtime contour remained unchanged.
- PR #224 merged as exact main `0af31b5e2516fb0d529228a51025693e7a932779`; exact-main Quality run `32218234279` succeeded, and durable production authorization was recorded with execution intent for the same target.
- Request runtime deployment run `32219455747` validated the exact three-line request, durable authorization, exact-main Quality, deployment tooling, exact artifacts, quality evidence, release manifest and SSH configuration. Ubuntu Worker contour was correctly skipped.
- VPS job `95967126921` then failed at the deployment mutation boundary with `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES` and `ERROR privileged bundle source SHA does not match request`. No accepted deployment manifest was produced for the candidate.
- Production learning: the PR #224 Change Contract declared VPS execution capability `CONNECTOR` and zero operator actions, but the protected root-owned privilege bundle is intentionally exact-source-bound and therefore requires one repository-owned root bootstrap whenever that bundle source SHA differs from the requested authorized target. Effective capability for this rollout is `ONE_COMMAND_FALLBACK`; operator actions expected is `1`.
- Corrective source scope is exactly this SDD triplet. Product bytes, deploy scripts, workflows, Issue Outcome Contract, immutable PR #224 authorization-bound fields, production fingerprint, runtime target and Ubuntu Worker state remain unchanged.
- After corrective source CI/merge evidence, the operator performs the exact-source privilege bootstrap once; the failed VPS deployment job is then retried for the existing authorized target. Browser acceptance remains the final runtime evidence for Issue #223.
