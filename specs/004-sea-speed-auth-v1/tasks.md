# Tasks: Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Plan: `specs/004-sea-speed-auth-v1/plan.md`
- Issue: #115
- Pull Request: #116
- Status: Implementing

## Delivery tasks

- [x] T001 Create canonical Issue, approved feature specification and fresh implementation branch from exact `main`.
- [x] T002 Add pinned Authentik VPS compose/runtime template with secrets outside Git and no Docker socket dependency.
- [x] T003 Add Authentik blueprint for Owner/Admin/Operator/Viewer groups, invite-only role enrollment, strong password policy and Owner-only TOTP authentication.
- [x] T004 Add bounded nginx renderer/verifier for `/sea-speed/**` Forward Auth, `/outpost.goauthentik.io/**`, `/cams/**` retirement and spoof-resistant identity headers.
- [x] T005 Add SHA-bound Auth v1 VPS status/prepare/activate tooling with protected backup, `nginx -t`, nginx-only reload and no automatic public-route rollback.
- [x] T006 Move Camera 1 browser HLS identity to `/sea-speed/media/cam1/index.m3u8` while preserving the loopback H.264 upstream and AI independence; retire standalone public Camera 1 nginx activation.
- [x] T007 Remove the public `/cams/` root-page link and all browser references to the old Camera 1 HLS URL.
- [x] T008 Update Camera 1 accepted SDD/docs/tests to record that Issue #115 supersedes only the public browser identity/security boundary.
- [x] T009 Update VPS deploy health/smoke behavior so FastAPI origin health is local and protected `/sea-speed/api/health` no longer requires anonymous success.
- [x] T010 Preserve existing worker M2M traffic through an exact private VPS listener restricted to one private worker peer, exact methods/paths and the existing Bearer token for writes; document runtime URL migration without a worker source/package change.
- [x] T011 Add Auth v1 behavioral/security tests, deployment assertions and production runbook.
- [ ] T012 Run repository validation and resolve findings within approved scope.
- [ ] T013 Open one bounded PR linked to Issue #115 and `specs/004-sea-speed-auth-v1/spec.md`; resolve CI/review findings within approved scope.
- [ ] T014 Merge exact green head into `main` and record source-integration evidence.

## Production tasks - separately authorized

- [ ] T101 Obtain exact-SHA `PRODUCTION APPROVED` after merge.
- [ ] T102 Stage Authentik runtime secrets, SMTP and Owner bootstrap without disclosure.
- [ ] T103 Prove Authentik, blueprint, Forward Auth application and embedded outpost on loopback.
- [ ] T104 Enroll/configure Owner TOTP and prove password-only Owner login is rejected.
- [ ] T105 Prove a single-use role invitation, cross-device email/password login and password recovery.
- [ ] T106 Discover exact private VPS/worker peer addresses; prepare the worker runtime URL switch while preserving the existing private Bearer token.
- [ ] T107 Prepare and activate the exact SHA-bound nginx/auth/media/private-M2M candidate.
- [ ] T108 Prove anonymous root access, `/cams/**` retirement, `/sea-speed/**` protection, header-spoof resistance and no direct backend/media exposure.
- [ ] T109 Prove authenticated Camera 1 advancing H.264 playback and existing Cameras/Objects/API behavior.
- [ ] T110 Prove worker ROI/speed GETs and Bearer-authenticated state/events POSTs continue through the exact private listener; unrelated peers/methods/paths remain denied.
- [ ] T111 Record runtime acceptance or explicit blocker/rollback evidence in Issue #115.

## Completion gate

`COMPLETE` requires source integration plus every applicable production acceptance item. Merge alone is not deployment, and deployment alone is not runtime acceptance.
