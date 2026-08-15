# Implementation Plan: Sea Speed Auth UX logout

Issue: #152
Specification: `specs/005-auth-ux-logout/spec.md`

## Architecture

The correction stays inside the existing Authentik Forward Auth topology. The browser continues to enter logout through `/outpost.goauthentik.io/sign_out`; the existing Sea Speed Proxy Provider is assigned a dedicated invalidation flow containing User Logout followed by a static redirect to `https://mostdef.ru/`. The global provider invalidation flow is not modified.

Operator, Cameras, and Objects continue to obtain display identity from the existing trusted `/sea-speed/api/session` endpoint. Each page adds a bounded 15-second probe after identity establishment. If that trusted probe is lost, the page navigates the top-level browsing context to its current protected path and lets nginx Forward Auth perform the authentication redirect.

Production rollout follows the repository-owned server-pull model. The VPS uses the existing exact-SHA `deploy/vps/deploy.sh` release entrypoint. The Ubuntu-worker Authentik contour uses `deploy/worker/ubuntu/authentik/apply-logout-flow.sh`, which applies or rolls back only the Sea Speed provider invalidation-flow assignment against the already-running Authentik worker.

The worker operation does not alter Compose topology or persist another bind mount. It copies the exact repository-owned blueprint to a temporary hidden file under Authentik's configured `/blueprints` directory, invokes Authentik's native `ak apply_blueprint` management command synchronously, removes the temporary file, and verifies the provider's actual `invalidation_flow` through Authentik's Django shell. Using a hidden temporary filename without a `.yaml` suffix keeps the operation explicit rather than relying on asynchronous filesystem blueprint discovery.

## Decisions

- Keep the existing provider sign-out URL rather than implementing a client-only logout redirect.
- Use a Sea Speed-specific Authentik invalidation flow so other applications do not inherit full browser-session logout behavior.
- Run User Logout before Redirect to ensure the Authentik browser session is invalidated before the user reaches the public root.
- Use the current protected path for session-loss recovery so normal Forward Auth return-to behavior remains authoritative.
- Do not introduce `localStorage`, `sessionStorage`, client identity headers, browser-readable authentication state, or a Sea Speed session store.
- Use the existing running Authentik worker to apply the blueprint; do not recreate server, worker, PostgreSQL, private proxy, or nginx solely for this provider configuration change.
- Fail closed if `Provider for Sea Speed` is bound to an unexpected invalidation flow before mutation.
- Verify the provider assignment after apply because Authentik's management command performs validation/import internally while runtime acceptance must observe the actual resulting relation.
- Provide a repository-owned rollback blueprint that restores only `Provider for Sea Speed` to `default-provider-invalidation-flow` without changing that global flow.
- Require fresh exact merged-SHA production authorization after the worker-operation remediation merges; the earlier production approval for `093fb0892f4d66b4a4dfda1effdb46acac711232` is not used for continuation.

## Affected contours

- VPS frontend release: `frontend/sea-speed/index.html`, `frontend/sea-speed/cameras/index.html`, `frontend/sea-speed/objects/index.html`.
- Authentik apply source: `deploy/vps/authentik/blueprints/sea-speed-logout-v1.yaml`.
- Authentik rollback source: `deploy/vps/authentik/blueprints/sea-speed-logout-rollback-v1.yaml`.
- Ubuntu-worker operation: `deploy/worker/ubuntu/authentik/apply-logout-flow.sh` and its runbook in `deploy/worker/ubuntu/authentik/README.md`.
- Source validation: `tests/test_auth_logout_contract.py`.
- SDD: `specs/005-auth-ux-logout/**`.
- Explicitly unaffected: nginx topology, Authentik Compose topology, fail-closed and forged-header boundary, Camera 1 media path, credentials, TOTP, roles/groups, invitations, recovery, worker M2M, camera/AI/detection/tracking/speed behavior.

## Validation

1. Verify exact remediation diff remains inside the approved Authentik operations/runbook/test/SDD contour and the branch stays current with `main` before merge.
2. Run repository SDD, Change Contract, behavioral, security and quality checks through PR Validation and Quality integration on the exact final head.
3. Focused tests assert all three protected frontends keep provider logout, add bounded trusted-session loss recovery, and do not introduce browser-local auth state.
4. Focused tests assert the Sea Speed invalidation flow uses User Logout before static Redirect to `https://mostdef.ru/` and is assigned only to `Provider for Sea Speed`.
5. Focused tests assert the rollback blueprint restores only the Sea Speed provider to `default-provider-invalidation-flow`.
6. Focused tests assert the worker operation is exact-SHA-bound, has idempotent apply/rollback modes, uses Authentik's native apply path, verifies provider assignment and runtime-container continuity, and does not reference runtime secret values.
7. Runtime/browser acceptance is deferred until the final remediation merge receives fresh exact-SHA production authorization.

## Rollout and rollback

1. Under fresh `PRODUCTION APPROVED <final-main-sha>`, use the target-local server-pull bootstrap on the Production VPS to invoke the exact source's `deploy/vps/deploy.sh <final-main-sha>`.
2. Verify VPS source/frontend health and protected-route behavior before changing the worker contour.
3. Use the target-local server-pull bootstrap on `sea-speed-worker` to invoke `apply-logout-flow.sh apply --source-sha <final-main-sha>`.
4. Verify the operation reports `sea-speed-provider-invalidation`, unchanged Authentik/PostgreSQL container identities, and loopback readiness.
5. Perform browser acceptance for explicit logout-to-root, fresh login on return, bounded session-loss reauthentication, trusted username, Camera 1 continuity, forged-header rejection, and fail-closed behavior.
6. If the provider change must be reverted inside the approved rollback envelope, invoke the same exact source operation in `rollback` mode and verify `default-provider-invalidation-flow`. The prior VPS release remains the independent frontend rollback target.

## Runtime feedback

Current production is intentionally unchanged during this source remediation. After the final source merge and a fresh `PRODUCTION APPROVED <merged-sha>`, rollout and browser acceptance will determine completion. No secrets, browser cookies, TOTP material, tokens or populated `.env` values are recorded as evidence.
