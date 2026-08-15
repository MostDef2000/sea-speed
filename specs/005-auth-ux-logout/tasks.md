# Tasks: Sea Speed Auth UX logout

Issue: #152
Specification: `specs/005-auth-ux-logout/spec.md`

- [x] Create a fresh branch from the authorized current `main` SHA.
- [x] Preserve provider logout entry points on Operator, Cameras, and Objects.
- [x] Add bounded trusted-session loss detection and top-level re-authentication on all three pages.
- [x] Define a Sea Speed-specific Authentik invalidation flow with User Logout then static root Redirect.
- [x] Bind only `Provider for Sea Speed` to that invalidation flow in source configuration.
- [x] Add focused source-contract tests.
- [x] Verify exact diff/scope from current `main`.
- [x] Open one bounded PR linked to Issue #152 and this specification.
- [ ] Require PR Validation and Quality integration on the exact PR head.
- [ ] Merge exact green head.
- [ ] Obtain separate exact merged-SHA production authorization before runtime mutation.
- [ ] Perform production/browser acceptance and close Issue #152 only after runtime evidence passes.
