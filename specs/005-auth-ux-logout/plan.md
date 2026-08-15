# Implementation Plan: Sea Speed Auth UX logout

Issue: #152
Specification: `specs/005-auth-ux-logout/spec.md`

## Architecture

The correction stays inside the existing Authentik Forward Auth topology. The browser continues to enter logout through `/outpost.goauthentik.io/sign_out`; the existing Sea Speed Proxy Provider is assigned a dedicated invalidation flow containing User Logout followed by a static redirect to `https://mostdef.ru/`. The global provider invalidation flow is not modified.

Operator, Cameras, and Objects continue to obtain display identity from the existing trusted `/sea-speed/api/session` endpoint. Each page adds a bounded 15-second probe after identity establishment. If that trusted probe is lost, the page navigates the top-level browsing context to its current protected path and lets nginx Forward Auth perform the authentication redirect.

Production rollout follows the repository-owned server-pull model. The VPS uses the existing exact-SHA `deploy/vps/deploy.sh` release entrypoint. The Ubuntu-worker Authentik contour uses `deploy/worker/ubuntu/authentik/apply-logout-flow.sh`, which applies or rolls back only the Sea Speed provider invalidation-flow assignment against the already-running Authentik worker.

The worker operation does not alter Compose topology or persist another bind mount. It copies the exact repository-owned blueprint to a temporary hidden file under Authentik's configured `/blueprints` directory, invokes Authentik's native `ak apply_blueprint` management command synchronously, removes the temporary file, and verifies the provider's actual `invalidation_flow` through Authentik's Django shell. Using a hidden temporary filename without a `.yaml` suffix keeps the operation explicit rather than relying on asynchronous filesystem blueprint discovery.

Authentik 2026.5.6 requires one compatibility constraint for the existing `Provider for Sea Speed`: the provider is already `forward_single`, while its serializer validates an omitted `mode` as the default proxy mode during a partial blueprint update. Both apply and rollback blueprints therefore declare `mode: forward_single` explicitly while changing only `invalidation_flow`. The worker operation reads the actual provider mode before mutation, fails closed unless it is exactly `forward_single`, and verifies the mode remains unchanged afterward.

## Decisions

- Keep the existing provider sign-out URL rather than implementing a client-only logout redirect.
- Use a Sea Speed-specific Authentik invalidation flow so other applications do not inherit full browser-session logout behavior.
- Run User Logout before Redirect to ensure the Authentik browser session is invalidated before the user reaches the public root.
- Use the current protected path for session-loss recovery so normal Forward Auth return-to behavior remains authoritative.
- Do not introduce `localStorage`, `sessionStorage`, client identity headers, browser-readable authentication state, or a Sea Speed session store.
- Use the existing running Authentik worker to apply the blueprint; do not recreate server, worker, PostgreSQL, private proxy, or nginx solely for this provider configuration change.
- Fail closed if `Provider for Sea Speed` is bound to an unexpected invalidation flow before mutation.
- Fail closed if `Provider for Sea Speed` is not already `forward_single`; explicit `mode: forward_single` in the apply/rollback blueprints preserves the existing topology and satisfies Authentik 2026.5.6 partial-update validation.
- Verify both provider invalidation-flow assignment and provider mode after apply because Authentik's management command performs validation/import internally while runtime acceptance must observe the actual resulting relation without topology drift.
- Provide a repository-owned rollback blueprint that restores only `Provider for Sea Speed` to `default-provider-invalidation-flow` without changing that global flow.
- Require fresh exact merged-SHA production authorization after each source remediation merge; an authorization bound to an earlier SHA is not used for continuation.

## Affected contours

- VPS frontend release: `frontend/sea-speed/index.html`, `frontend/sea-speed/cameras/index.html`, `frontend/sea-speed/objects/index.html`.
- Authentik apply source: `deploy/vps/authentik/blueprints/sea-speed-logout-v1.yaml`.
- Authentik rollback source: `deploy/vps/authentik/blueprints/sea-speed-logout-rollback-v1.yaml`.
- Ubuntu-worker operation: `deploy/worker/ubuntu/authentik/apply-logout-flow.sh` and its runbook in `deploy/worker/ubuntu/authentik/README.md`.
- Source validation: `tests/test_auth_logout_contract.py`.
- SDD: `specs/005-auth-ux-logout/**`.
- Explicitly unaffected: nginx topology, Authentik Compose topology, fail-closed and forged-header boundary, Camera 1 media path, credentials, TOTP, roles/groups, invitations, recovery, worker M2M, camera/AI/detection/tracking/speed behavior.

## Validation

1. Verify exact remediation diff remains inside the approved Authentik operations/blueprint/test/SDD contour and the branch stays current with `main` before merge.
2. Run repository SDD, Change Contract, behavioral, security and quality checks through PR Validation and Quality integration on the exact final head.
3. Focused tests assert all three protected frontends keep provider logout, add bounded trusted-session loss recovery, and do not introduce browser-local auth state.
4. Focused tests assert the Sea Speed invalidation flow uses User Logout before static Redirect to `https://mostdef.ru/` and is assigned only to `Provider for Sea Speed`.
5. Focused tests assert the apply and rollback provider patches preserve `mode: forward_single`, do not introduce provider host/topology changes, and the rollback restores only the Sea Speed provider to `default-provider-invalidation-flow`.
6. Focused tests assert the worker operation is exact-SHA-bound, has idempotent apply/rollback modes, checks the runtime provider mode before mutation, uses Authentik's native apply path, verifies provider flow/mode and runtime-container continuity, and does not reference runtime secret values.
7. Runtime/browser acceptance is deferred until the final remediation merge receives fresh exact-SHA production authorization.

## Rollout and rollback

1. Under fresh `PRODUCTION APPROVED <final-main-sha>`, use the target-local server-pull bootstrap on the Production VPS to invoke the exact source's `deploy/vps/deploy.sh <final-main-sha>` with the production origin-health override for `127.0.0.1:8010` until the deploy default is separately aligned.
2. Verify VPS source/frontend health and protected-route behavior before changing the worker contour.
3. Use the target-local server-pull bootstrap on `sea-speed-worker` to invoke `apply-logout-flow.sh apply --source-sha <final-main-sha>`.
4. Verify the operation reports provider mode `forward_single`, invalidation flow `sea-speed-provider-invalidation`, unchanged Authentik/PostgreSQL container identities, and loopback readiness.
5. Perform browser acceptance for explicit logout-to-root, fresh login on return, bounded session-loss reauthentication, trusted username, Camera 1 continuity, forged-header rejection, and fail-closed behavior.
6. If the provider change must be reverted inside the approved rollback envelope, invoke the same exact source operation in `rollback` mode and verify mode remains `forward_single` while invalidation flow returns to `default-provider-invalidation-flow`. The prior VPS release remains the independent frontend rollback target.

## Runtime feedback

The first production pass on `be98b94b7d8c7f37f94c067dfa4fca3c961f474e` successfully deployed the VPS release after using the supported production origin-health override `http://127.0.0.1:8010/api/health`. The VPS release state moved to that exact SHA with the prior `62e1c52f285e08dbb86c946d307e74f58225704b` release retained as rollback target.

The first Ubuntu-worker logout-flow attempt on the same SHA stopped during Authentik blueprint validation before apply. The observed provider invalidation flow remained `default-provider-invalidation-flow`; no provider assignment was committed. Investigation localized the source defect to Authentik 2026.5.6 partial ProxyProvider update validation when `mode` is omitted, with the runtime provider already known to be `forward_single`. This compatibility remediation preserves that mode explicitly in source and adds fail-closed mode verification to the repo-owned worker operation.

Production continuation is paused until this remediation is merged, exact-main quality is green, and a fresh `PRODUCTION APPROVED <merged-sha>` is recorded. No secrets, browser cookies, TOTP material, tokens or populated `.env` values are recorded as evidence.
