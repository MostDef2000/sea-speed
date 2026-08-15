# Tasks: Sea Speed Auth UX logout

Issue: #152
Specification: `specs/005-auth-ux-logout/spec.md`

## Delivery tasks

- [x] Implement provider logout entry and bounded session-loss reauthentication on all protected pages.
- [x] Define Sea Speed-specific Authentik invalidation flow.
- [x] Merge initial source under exact-head quality gates.
- [x] Add repo-owned Ubuntu Worker apply/rollback operation required by server-pull policy.
- [x] Correct Authentik 2026.5 `forward_single` compatibility and fail-closed mode verification.
- [x] Merge final corrected source and obtain fresh exact-SHA production authorization.
- [x] Deploy exact VPS release and apply exact Ubuntu Authentik flow.
- [x] Complete browser acceptance: logout-to-root, fresh login, stale-session reauth, username, Camera 1.
- [x] Preserve forged-header/fail-closed security boundary.
- [x] Record final `accepted` evidence and close Issue #152 completed.

## Completion gate

- [x] Source + quality accepted.
- [x] Exact production authorization recorded for accepted release.
- [x] VPS and Ubuntu contours accepted.
- [x] Browser/runtime verdict `accepted`.
- [x] Issue #152 closed completed.
