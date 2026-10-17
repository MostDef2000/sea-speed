# Tasks: #520 — operator identity: edge-secret enforcement at the API

- Specification: specs/520-operator-edge-auth/spec.md

## Delivery tasks

- [ ] T-1: config — add `EDGE_AUTH_SECRET` (env `SEA_SPEED_EDGE_AUTH_SECRET`,
  default empty) to `api/app/config.py` (R-1 prerequisite)
- [ ] T-2: identity — `require_operator_identity` gains the edge-header
  parameter; strict mode (compare_digest, 403 before username check) +
  transitional mode (legacy semantics, one-shot warning) (R-1, R-2, R-3)
- [ ] T-3: main — six `/api/worker/control*` routes + `/api/session` add the
  edge Header parameter and pass it through; `/api/session` delegates to
  `require_operator_identity` (R-3, R-4)
- [ ] T-4: tests — behavioral coverage of both env states (transitional pins
  unchanged; strict: absent/incorrect header → 403, correct → identity,
  correct + blank username → 503); route/contract fingerprints updated only
  if required, deliberately (R-4, R-5, D-6)
- [ ] T-5: PR Change Contract (exact file match, VPS REQUIRED, Risk profile
  REQUIRED), CI green on exact head, merge
- [ ] T-6 (runtime-manual): phase 2 edge handoff (sysadmin, полоса C) →
  phase 3 API env + deploy + forged/normal acceptance probes on #520;
  ИБ-этап applies

## Completion gate

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [x] Required CI green — auto-synced on merge to main (0a5d7553)
- [x] Exact-green-head merge complete — auto-synced on merge to main (0a5d7553)
- [ ] Deployment state resolved (phases 2-3, runtime-manual)
- [ ] Runtime acceptance resolved (AC-005)
- [ ] Deferred work recorded (transitional-mode removal after phase 3;
      objects/media app-layer auth as separate issue)
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current

## Requirements traceability

- AC-001 | Task: T-2, T-4 | Evidence: transitional pins unchanged, one-shot warning test green | Coverage: COVERED
- AC-002 | Task: T-2, T-3, T-4 | Evidence: strict tests RED at base then green, orchestrator-verified | Coverage: COVERED
- AC-003 | Task: T-4 | Evidence: full battery, validate_sdd, validate_repo in PR | Coverage: COVERED
- AC-004 | Task: T-5 | Evidence: Change Contract validation, CI on exact head | Coverage: COVERED
- AC-005 | Task: T-6 | Evidence: sysadmin probes (forged 403, flow OK) on #520 | Coverage: RUNTIME-MANUAL | Reason: edge and API env reachable only through the sysadmin session (polosa C)

## Definition of Done

- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
