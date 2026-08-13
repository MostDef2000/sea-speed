# Tasks: Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Plan: `specs/004-sea-speed-auth-v1/plan.md`
- Original Issue: #115
- Original Pull Request: #116
- Runtime topology revision: #122
- Status: Issue #122 worker-hosted Authentik revision in implementation

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
- [ ] T122-08 Verify exact approved changed-file scope against `main` and run required repository validation.
- [ ] T122-09 Open one bounded PR linked to Issue #122 and `specs/004-sea-speed-auth-v1/spec.md`; resolve CI/review findings only inside approved scope.
- [ ] T122-10 Merge exact green head and record the new exact source SHA.

## Production tasks - separately authorized for the new merged SHA

- [ ] T201 Obtain fresh exact-SHA `PRODUCTION APPROVED` for the Issue #122 MIXED worker+VPS topology.
- [ ] T202 Run the fastest-safe worker stage: protected env -> Docker/Compose if absent -> Authentik/PostgreSQL -> private source-restricted proxy -> health acceptance.
- [ ] T203 Prove VPS-to-worker private Authentik health and configure `auth.mostdef.ru` HTTPS through the VPS only.
- [ ] T204 Configure Owner email/TOTP and prove password-only Owner login is rejected.
- [ ] T205 Prove a single-use role invitation, cross-device email/password login and password recovery.
- [ ] T206 Discover/confirm exact private VPS M2M listen and worker peer addresses; prepare the Sea Speed worker runtime URL switch while preserving the existing Bearer token.
- [ ] T207 Prepare and activate the exact SHA-bound nginx/auth/media/private-M2M candidate using the exact worker private Authentik origin.
- [ ] T208 Prove anonymous root access, `/cams/**` retirement, `/sea-speed/**` protection, header-spoof resistance and no direct backend/media/Auth exposure.
- [ ] T209 Prove authenticated Camera 1 advancing H.264 playback and existing Cameras/Objects/API behavior.
- [ ] T210 Prove worker ROI/speed GETs and Bearer-authenticated state/events POSTs continue through the exact private VPS listener; unrelated peers/methods/paths remain denied.
- [ ] T211 Prove worker/Auth/ZeroTier loss fails `/sea-speed/**` closed without affecting the public `/` landing page.
- [ ] T212 Record runtime acceptance or explicit blocker/rollback evidence in Issue #122 and cross-reference Issue #115.

## Completion gate

`COMPLETE` for the revised Auth v1 topology requires Issue #122 source integration plus every applicable separately authorized production acceptance item. Merge alone is not deployment, and deployment alone is not runtime acceptance.
