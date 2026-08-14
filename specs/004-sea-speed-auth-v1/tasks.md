# Tasks: Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Plan: `specs/004-sea-speed-auth-v1/plan.md`
- Original Issue: #115
- Original Pull Request: #116
- Runtime topology revision: #122
- Cutover split-layout remediation: #140
- Browser-routing remediation: #146
- Authenticated header UX: #148
- Status: Authentik/nginx boundary active; Issue #148 source integration and final application/browser/fail-closed acceptance pending

## Delivery tasks

### Original Auth v1 delivery tasks

- [x] T001 Create canonical Issue, approved feature specification and fresh implementation branch from exact `main`.
- [x] T002 Add pinned Authentik runtime template with secrets outside Git and no Docker socket dependency.
- [x] T003 Add Authentik blueprint for Owner/Admin/Operator/Viewer groups, invite-only role enrollment, strong password policy and Owner-only TOTP authentication.
- [x] T004 Add bounded nginx renderer/verifier for `/sea-speed/**` Forward Auth, `/outpost.goauthentik.io/**`, `/cams/**` retirement and spoof-resistant identity headers.
- [x] T005 Add SHA-bound Auth v1 VPS status/prepare/activate tooling with protected backup, `nginx -t`, nginx-only reload and no automatic public-route rollback.
- [x] T006 Move Camera 1 browser HLS identity to `/sea-speed/media/cam1/index.m3u8` while preserving the loopback H.264 upstream and AI independence; retire standalone public Camera 1 nginx activation.
- [x] T007 Remove the public `/cams/` root-page link and all browser references to the old Camera 1 HLS URL.
- [x] T008 Update Camera 1 accepted SDD/docs/tests to record that Issue #115 supersedes only the public browser identity/security boundary.
- [x] T009 Update VPS deploy health/smoke behavior so FastAPI origin health is local and protected `/sea-speed/api/health` no longer requires anonymous success.
- [x] T010 Preserve existing worker M2M traffic through an exact private VPS listener restricted to one private worker peer, exact methods/paths and the existing Bearer token for writes.
- [x] T011 Add Auth v1 behavioral/security tests, deployment assertions and production runbook.
- [x] T012 Original repository validation and CI completed.
- [x] T013 Original bounded PR #116 completed.
- [x] T014 Original exact green Auth v1 source merged.

### Issue #122 - Worker-hosted Authentik topology

- [x] T122-01 Record fresh worker capacity evidence and approve the topology revision after VPS CPU preflight failure.
- [x] T122-02 Add canonical `deploy/worker/ubuntu/authentik/**` Compose/env/runbook with Authentik `2026.5.6`, PostgreSQL 16, loopback-only Docker publish and no Docker socket.
- [x] T122-03 Add one-stage worker helper that validates `sea-speed-worker`, private addresses/resources, installs Docker/Compose when absent, stages Authentik and proves health/exposure invariants.
- [x] T122-04 Add source-restricted worker private Authentik proxy bound to one literal worker private IP and exact VPS peer.
- [x] T122-05 Parameterize nginx Authentik/outpost upstream and require the production cutover to use a validated non-loopback RFC1918 worker origin.
- [x] T122-06 Update SDD and operations guidance for worker-hosted identity while preserving Camera 1, gallery, AI and private M2M behavior.
- [x] T122-07 Update focused Auth v1 tests for worker Compose/stage/private-origin behavior and legacy regression coverage.
- [x] T122-08 Verify approved changed-file scope against `main` and run required repository validation for the worker topology source.
- [x] T122-09 Complete bounded source PR lifecycle for the worker-hosted topology and subsequent in-scope corrections.
- [x] T122-10 Merge exact green worker-topology source and track exact-main production approvals per correction.

### Issue #140 - Split nginx cutover remediation

- [x] T140-01 Record the production split-layout blocker and Implementation Scope Check without expanding the #122 security/product boundary.
- [x] T140-02 Add exact TLS `mostdef.ru` source discovery and bounded direct `/etc/nginx/snippets/sea-speed-*.conf` materialization.
- [x] T140-03 Feed the materialized source into the existing Camera 1 then Auth v1 render/verify pipeline while keeping `prepare` non-active and `activate` expected-SHA guarded.
- [x] T140-04 Add regression coverage for production-style split layout plus wildcard/nested/out-of-root fail-closed cases and record the intentional `12 hours` browser session / `96 hours` Proxy Provider token distinction.
- [x] T140-05 Verify exact changed-file scope, run required CI and resolve only in-scope findings.
- [x] T140-06 Merge the exact green head, record the new exact `main` SHA and obtain fresh exact-SHA production authorization before runtime mutation.

### Issue #146 - Browser routing remediation

- [x] T146-01 Capture production evidence for `www.mostdef.ru` auth-request 404 and `/sea-speed/outpost.goauthentik.io/**` callback recursion.
- [x] T146-02 Make `www.mostdef.ru` canonicalize to `https://mostdef.ru$request_uri` before Forward Auth.
- [x] T146-03 Record Proxy Provider External host as origin-only `https://mostdef.ru` while the Sea Speed application launch path remains `/sea-speed/`.
- [x] T146-04 Preserve the root `/outpost.goauthentik.io/**` contour and regression-test the canonical host/outpost invariants.
- [x] T146-05 Pass exact-head PR Validation/Quality integration and merge PR #147.
- [x] T146-06 Prepare, SHA-review and activate the exact production nginx candidate; verify canonical `www`, anonymous gate, root outpost, spoof resistance and private M2M listener.

### Issue #148 - Authenticated header UX

- [x] T148-01 Record the product-scope expansion and `OUTCOME APPROVED` from exact base `main`.
- [x] T148-02 Create fresh implementation branch `agent/auth-header-ux` and canonical Issue #148.
- [x] T148-03 Add common lighthouse home, trusted Authentik username display and provider logout action to Operator, Cameras and Objects.
- [x] T148-04 Use only the existing same-origin `/outpost.goauthentik.io/auth/nginx` response for displayed username; do not add a Sea Speed session endpoint/store or browser-local auth fallback.
- [x] T148-05 Add focused frontend regression coverage and update canonical spec/plan/tasks.
- [ ] T148-06 Verify exact diff/source contracts and run required PR Validation + Quality integration.
- [ ] T148-07 Merge the exact green head, record the new exact `main` SHA and require fresh `PRODUCTION APPROVED <new-main-sha>` before application deployment.

## Production tasks

### Completed staged identity/runtime work

- [x] T201-stage Worker Authentik/PostgreSQL runtime is healthy on `sea-speed-worker`; Authentik Docker HTTP is worker-loopback-only and private VPS access is source-restricted.
- [x] T202-stage VPS reaches the worker private Authentik origin and public `https://auth.mostdef.ru` is healthy through VPS TLS.
- [x] T203-stage Owner TOTP login, Sea Speed provider/application/policy binding and role groups are proven.
- [x] T204-stage SMTP test delivery and real invitation email delivery are proven; single-use Viewer enrollment, password-only Viewer login, disable/session-revocation behavior are proven.
- [x] T205-stage Deep password-recovery acceptance is explicitly deferred/non-blocking by current operator decision; the product requirement remains documented for later verification if needed.

### Auth v1 activation checkpoints completed

- [x] T206 Obtain fresh exact-SHA production authorizations after source remediations.
- [x] T207 Run split-layout-aware `prepare`; review exact flattened candidate SHA-256 without changing active nginx.
- [x] T208 Switch Sea Speed worker runtime API/config URLs to the exact private VPS M2M listener while preserving the existing `SEA_SPEED_API_TOKEN`.
- [x] T209 Activate only the exact reviewed candidate; prove `nginx -t`, nginx-only reload, `/cams/**` retirement, anonymous `/sea-speed/**` gating, root outpost health, forged-header resistance and private-peer restriction.
- [x] T211 Prove worker private M2M read contour and at least one successful worker state publication through the private path; deeper AI/video continuity remains a separate camera runtime concern.

### Remaining final rollout after Issue #148 source merge

- [ ] T214 Obtain fresh exact-SHA `PRODUCTION APPROVED` for the merged #148 application release.
- [ ] T215 Synchronize the VPS application/frontend release with the exact merged SHA using the normal deployer while preserving the already active nginx SHA/security boundary.
- [ ] T216 Prove deployed `/api/health` exact source, protected `/sea-speed/media/cam1/index.m3u8`, Operator/Cameras/Objects navigation, trusted username display and lighthouse home link.
- [ ] T217 Prove provider `Выйти` terminates the current Sea Speed session so a fresh protected request requires Authentik again.
- [ ] T218 Prove advancing authenticated Camera 1 H.264 playback. Diagnose stale worker/overlay output separately if the AI worker is not producing current frames.
- [ ] T219 Prove no direct public backend/media/Auth origin exposure and perform the controlled worker/Auth/ZeroTier fail-closed test without affecting public `/`.
- [ ] T220 Record sanitized final runtime evidence and close/cross-reference #148, #146, #140, #122 and #115 as applicable.

## Seven-stage rollout view

1. Worker Authentik runtime: COMPLETE.
2. Identity/access contour sufficient for integration rollout: COMPLETE; password-recovery deep test deferred.
3. Split nginx/browser-routing source remediation: COMPLETE and merged.
4. CI/merge/exact-SHA production authorization for current active nginx boundary: COMPLETE.
5. SHA-reviewed nginx `prepare`: COMPLETE.
6. Nginx activation + private M2M + primary auth browser boundary: COMPLETE enough to proceed; application release synchronization with #148 UX remains pending.
7. Exact application deploy, authenticated Camera 1/browser logout acceptance, controlled fail-closed test and final evidence: PENDING.

## Completion gate

`COMPLETE` for Auth v1 requires Issue #148 exact-source integration, fresh exact-SHA application deployment, final authenticated Camera 1/logout acceptance and controlled fail-closed dependency evidence. Merge alone is not deployment, deployment alone is not runtime acceptance, and no remaining production mutation may reuse an exact-SHA approval that predates the #148 merge.
