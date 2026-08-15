# Tasks: Sea Speed Auth UX logout

Issue: #152
Specification: `specs/005-auth-ux-logout/spec.md`

## Delivery tasks

- [x] Create a fresh branch from the authorized current `main` SHA.
- [x] Preserve provider logout entry points on Operator, Cameras, and Objects.
- [x] Add bounded trusted-session loss detection and top-level re-authentication on all three pages.
- [x] Define a Sea Speed-specific Authentik invalidation flow with User Logout then static root Redirect.
- [x] Bind only `Provider for Sea Speed` to that invalidation flow in source configuration.
- [x] Add focused source-contract tests.
- [x] Verify exact diff/scope from current `main`.
- [x] Open one bounded PR linked to Issue #152 and this specification.
- [x] Align the PR Change Contract and SDD artifacts with repository validator schemas.
- [ ] Require PR Validation and Quality integration on the exact PR head.
- [ ] Merge exact green head.

## Completion gate

- [ ] Source is merged only after exact-head PR Validation and Quality integration are green and the branch remains fresh against `main`.
- [ ] Obtain separate `PRODUCTION APPROVED <merged-sha>` authorization before any runtime mutation.
- [ ] Deploy the exact merged release and dedicated Authentik logout flow only under that production authorization.
- [ ] Record browser acceptance for logout-to-root, fresh login on return, session-loss reauthentication, username rendering, Camera 1 continuity, forged-header rejection, and fail-closed behavior.
- [ ] Close Issue #152 only after runtime evidence passes; otherwise record BLOCKED/FAILED evidence and rollback as required.
