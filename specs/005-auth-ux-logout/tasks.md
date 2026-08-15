# Tasks: Sea Speed Auth UX logout

Issue: #152
Specification: `specs/005-auth-ux-logout/spec.md`

## Delivery tasks

### Initial source integration

- [x] Create a fresh branch from the authorized current `main` SHA.
- [x] Preserve provider logout entry points on Operator, Cameras, and Objects.
- [x] Add bounded trusted-session loss detection and top-level re-authentication on all three pages.
- [x] Define a Sea Speed-specific Authentik invalidation flow with User Logout then static root Redirect.
- [x] Bind only `Provider for Sea Speed` to that invalidation flow in source configuration.
- [x] Add focused source-contract tests.
- [x] Verify exact diff/scope from current `main`.
- [x] Open one bounded PR linked to Issue #152 and this specification.
- [x] Align the PR Change Contract and SDD artifacts with repository validator schemas.
- [x] PR Validation and Quality integration passed on the exact PR #153 head.
- [x] Merge exact green PR #153 head to `main` as `093fb0892f4d66b4a4dfda1effdb46acac711232`.

### Server-pull remediation

- [x] Re-evaluate production handoff after Issue #135 made repository-owned server-pull the normal runtime model.
- [x] Identify the missing Ubuntu-worker entrypoint for applying the Issue #152 Authentik blueprint.
- [x] Record the bounded operations/runbook/test/SDD remediation in Issue #152 under the existing approved outcome.
- [x] Create a fresh remediation branch from current `main` `aea74fa26a23f5c9723b178bd5a3edb7ec84dfe2`.
- [x] Add repo-owned `apply-logout-flow.sh` with exact-SHA, host/runtime-drift, idempotency, post-apply verification and bounded rollback behavior.
- [x] Add a repository-owned rollback blueprint that restores only `Provider for Sea Speed` to `default-provider-invalidation-flow`.
- [x] Update the Ubuntu-worker Authentik runbook and implementation plan for server-pull apply/rollback.
- [x] Extend focused tests for the worker operation and rollback contract.
- [x] Verify exact remediation diff/scope and branch freshness against current `main`.
- [x] Open one bounded remediation PR linked to Issue #152 and this specification.
- [ ] Require PR Validation and Quality integration on the exact final remediation head.
- [ ] Merge the exact green remediation head after fresh base/diff/review-thread verification.
- [ ] Record the new exact merged `main` SHA and mark the earlier production approval for `093fb0892f4d66b4a4dfda1effdb46acac711232` superseded for continuation.

## Completion gate

- [ ] Obtain fresh `PRODUCTION APPROVED <new-merged-sha>` authorization before any runtime mutation.
- [ ] Deploy the exact merged VPS release through its repo-owned server-pull entrypoint.
- [ ] Apply the dedicated Authentik logout flow through the exact source's repo-owned Ubuntu-worker operation.
- [ ] Record browser acceptance for logout-to-root, fresh login on return, session-loss reauthentication, username rendering, Camera 1 continuity, forged-header rejection, and fail-closed behavior.
- [ ] Close Issue #152 only after runtime evidence passes; otherwise record BLOCKED/FAILED evidence and use the declared rollback operations as required.
