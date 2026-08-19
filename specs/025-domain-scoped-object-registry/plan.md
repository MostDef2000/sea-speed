# Implementation Plan: Domain-scoped Object Registry

## Scope

Implement Issue #223 within the authorized seven-path union. Reuse the existing generic Objects API and shared Objects page. No backend, database, worker, camera, auth or deployment-script changes are permitted. A final diff may be a strict subset of the authorized path union when operator-page bytes do not need to change.

## Design

1. Preserve the existing Water/Road operator registry links and use same-origin referrer context only when the Objects URL has no explicit scope.
2. Add a small frontend scope table mapping `water -> cam1/water` and `road -> road1/road`.
3. Resolve a valid explicit `scope` first; otherwise infer Road only from `/sea-speed/road/`, default Water in all other cases, and canonicalize the result into `?scope=water|road`.
4. Update domain-specific title/copy and lock camera/domain selects to the resolved scope.
5. Build every list query with mandatory scoped `camera_id` and `domain`; ignore any form attempt to override those two keys.
6. Reset ordinary filters and immediately reapply the same scope.
7. Preserve existing detail/PATCH/DELETE/session/pagination behavior and existing responsive layout.
8. Validate with focused frontend contract assertions, exact authorized-subset diff, PR Validation and aggregate Quality.

## Delivery

- Production impact: VPS.
- VPS deployment: REQUIRED after separate exact-SHA production authorization.
- Ubuntu Worker/relay update: NOT REQUIRED.
- Rollback target: the accepted VPS release immediately preceding the later authorized rollout.
- Production mutation does not occur during source integration.
