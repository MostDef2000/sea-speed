# Tasks: Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Plan: `specs/004-sea-speed-auth-v1/plan.md`
- Issue: #115
- Status: Implementing

## Source tasks

- [x] T001 Create canonical Issue, approved feature specification and fresh implementation branch from exact `main`.
- [ ] T002 Add pinned Authentik VPS compose/runtime template with secrets outside Git and no Docker socket dependency.
- [ ] T003 Add Authentik blueprint for Owner/Admin/Operator/Viewer groups, invite-only role enrollment, strong password policy and Owner-only TOTP authentication.
- [ ] T004 Add bounded nginx renderer/verifier for `/sea-speed/**` forward auth, `/outpost.goauthentik.io/**`, `/cams/**` retirement and spoof-resistant identity headers.
- [ ] T005 Add bounded Auth v1 VPS status/prepare/activate tooling with protected backup, `nginx -t`, nginx-only reload and no automatic public-route rollback.
- [ ] T006 Move Camera 1 browser HLS identity to `/sea-speed/media/cam1/index.m3u8` while preserving the loopback H.264 upstream and AI independence.
- [ ] T007 Remove the public `/cams/` root-page link and all browser references to the old Camera 1 HLS URL.
- [ ] T008 Update Camera 1 accepted SDD/docs/tests to record that Issue #115 supersedes only the public browser identity/security boundary.
- [ ] T009 Update VPS deploy health/smoke behavior so protected `/sea-speed/api/health` does not require anonymous success.
- [ ] T010 Add Auth v1 behavioral/security tests and run repository validation.
- [ ] T011 Open one bounded PR linked to Issue #115 and `specs/004-sea-speed-auth-v1/spec.md`; resolve CI/review findings within approved scope.
- [ ] T012 Merge exact green head into `main` and record source-integration evidence.

## Production tasks - separately authorized

- [ ] T101 Obtain exact-SHA `PRODUCTION APPROVED` after merge.
- [ ] T102 Stage Authentik runtime secrets, SMTP and Owner bootstrap without disclosure.
- [ ] T103 Prove Authentik, blueprint, Forward Auth application and embedded outpost on loopback.
- [ ] T104 Enroll/configure Owner TOTP and prove password-only Owner login is rejected.
- [ ] T105 Prove a single-use role invitation, cross-device email/password login and password recovery.
- [ ] T106 Activate the prepared nginx/auth/media cutover.
- [ ] T107 Prove anonymous root access, `/cams/**` retirement, `/sea-speed/**` protection, header-spoof resistance and no direct backend/media exposure.
- [ ] T108 Prove authenticated Camera 1 advancing H.264 playback and existing Cameras/Objects/API behavior.
- [ ] T109 Record runtime acceptance or explicit blocker/rollback evidence in Issue #115.

## Completion gate

`COMPLETE` requires source integration plus every applicable production acceptance item. Merge alone is not deployment, and deployment alone is not runtime acceptance.
