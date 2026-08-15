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
- [x] Open bounded PR #155 linked to Issue #152 and this specification.
- [x] PR Validation #251 and Quality integration #201 passed on exact PR #155 head `0f263e2411266b1c9edf0232790af7250df4e763`.
- [x] Merge exact green PR #155 head after fresh base/diff/review-thread verification.
- [x] Record merged `main` `be98b94b7d8c7f37f94c067dfa4fca3c961f474e` and supersede the earlier production approval for `093fb0892f4d66b4a4dfda1effdb46acac711232`.

### Authentik 2026.5 compatibility remediation

- [x] Record the successful exact-SHA VPS rollout and the fail-closed Ubuntu-worker blueprint-validation failure on `be98b94b7d8c7f37f94c067dfa4fca3c961f474e`.
- [x] Confirm the failed worker attempt stopped inside Authentik blueprint validation before provider assignment was applied.
- [x] Localize the compatibility defect to Authentik 2026.5.6 partial ProxyProvider validation when the existing `forward_single` provider patch omits `mode`.
- [x] Record the bounded source remediation and pause worker production continuation until a new exact merged SHA is authorized.
- [x] Create fresh branch `agent/auth-logout-authentik-2026-5-compat` from exact current `main` `be98b94b7d8c7f37f94c067dfa4fca3c961f474e`.
- [x] Preserve `mode: forward_single` explicitly in both apply and rollback provider patches without changing provider hosts/topology.
- [x] Make the repo-owned worker operation fail closed unless the current provider mode is exactly `forward_single` and verify it remains unchanged after apply/rollback.
- [x] Extend focused tests and implementation-plan evidence for the Authentik 2026.5.6 compatibility regression.
- [ ] Verify the exact six-file remediation diff/scope and branch freshness against current `main`.
- [ ] Open one bounded compatibility PR linked to Issue #152 and this specification.
- [ ] Require PR Validation and Quality integration on the exact final compatibility-remediation head.
- [ ] Merge the exact green compatibility-remediation head after fresh base/diff/review-thread verification.
- [ ] Record the new exact merged `main` SHA and mark `PRODUCTION APPROVED be98b94b7d8c7f37f94c067dfa4fca3c961f474e` superseded for worker continuation.

## Completion gate

- [ ] Obtain fresh `PRODUCTION APPROVED <new-merged-sha>` authorization before further worker mutation.
- [ ] Deploy the exact new merged VPS release through its repo-owned server-pull entrypoint using the production `127.0.0.1:8010` origin-health override while that default remains source-drifted.
- [ ] Apply the dedicated Authentik logout flow through the exact source's repo-owned Ubuntu-worker operation and verify provider mode remains `forward_single`.
- [ ] Record browser acceptance for logout-to-root, fresh login on return, session-loss reauthentication, username rendering, Camera 1 continuity, forged-header rejection, and fail-closed behavior.
- [ ] Close Issue #152 only after runtime evidence passes; otherwise record BLOCKED/FAILED evidence and use the declared rollback operations as required.
