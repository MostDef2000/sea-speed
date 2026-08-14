# Tasks: Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Plan: `specs/004-sea-speed-auth-v1/plan.md`
- Original Issue: #115
- Original Pull Request: #116
- Runtime topology revision: #122
- Cutover split-layout remediation: #140
- Status: worker identity/runtime stages complete enough for rollout; Issue #140 source integration pending PR/CI/merge

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
- [ ] T140-05 Verify exact changed-file scope, run required CI and resolve only in-scope findings.
- [ ] T140-06 Merge the exact green head, record the new exact `main` SHA and require a fresh `PRODUCTION APPROVED <new-main-sha>` before remaining runtime mutation.

## Production tasks

### Completed staged identity/runtime work

- [x] T201-stage Worker Authentik/PostgreSQL runtime is healthy on `sea-speed-worker`; Authentik Docker HTTP is worker-loopback-only and private VPS access is source-restricted.
- [x] T202-stage VPS reaches the worker private Authentik origin and public `https://auth.mostdef.ru` is healthy through VPS TLS.
- [x] T203-stage Owner TOTP login, Sea Speed provider/application/policy binding and role groups are proven.
- [x] T204-stage SMTP test delivery and real invitation email delivery are proven; single-use Viewer enrollment, password-only Viewer login, disable/session-revocation behavior are proven.
- [x] T205-stage Deep password-recovery acceptance is explicitly deferred/non-blocking by current operator decision; the product requirement remains documented for later verification if needed.

### Remaining separately authorized final rollout

- [ ] T206 Obtain fresh exact-SHA `PRODUCTION APPROVED` after Issue #140 merges.
- [ ] T207 Run split-layout-aware `prepare`; record/review the exact flattened candidate SHA-256 without changing active nginx.
- [ ] T208 Coordinate the Sea Speed worker runtime URL switch to the exact private VPS M2M listener while preserving the existing `SEA_SPEED_API_TOKEN`.
- [ ] T209 Activate only the exact reviewed candidate; require `nginx -t`, nginx-only reload, `/cams/**` retirement and anonymous `/sea-speed/**` gating.
- [ ] T210 Prove authenticated `/sea-speed/**`, Cameras/Objects/API behavior and advancing Camera 1 H.264 playback.
- [ ] T211 Prove worker ROI/speed GETs and Bearer-authenticated state/events POSTs continue through the exact private VPS listener; unrelated peers/methods/paths remain denied.
- [ ] T212 Prove no direct public backend/media/Auth origin exposure and perform the controlled worker/Auth/ZeroTier fail-closed test without affecting public `/`.
- [ ] T213 Record sanitized final runtime evidence and close/cross-reference #140, #122 and #115 as applicable.

## Seven-stage rollout view

1. Worker Authentik runtime: COMPLETE.
2. Identity/access contour sufficient for integration rollout: COMPLETE; password-recovery deep test deferred.
3. Split nginx source remediation and timing documentation: source implementation complete on #140 branch; PR/CI pending.
4. PR/CI/merge/new exact SHA/fresh production approval: PENDING.
5. SHA-reviewed `prepare`: PENDING.
6. Coordinated M2M + nginx production activation and primary runtime acceptance: PENDING.
7. Controlled fail-closed test, final evidence and Issue closure: PENDING.

## Completion gate

`COMPLETE` for Auth v1 requires the remaining final integration rollout and fail-closed acceptance after Issue #140 source integration. Merge alone is not deployment, deployment alone is not runtime acceptance, and no final production mutation may reuse an exact-SHA approval that predates the #140 merge.
