# Sea Speed Agent Entry Point

Status: Active

This file is a concise adapter for coding agents. The canonical rules remain:

- `contracts/SEA_SPEED_GOVERNANCE.md`;
- `contracts/SEA_SPEED_DELIVERY_POLICY.md`;
- `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`;
- `contracts/runtime/RELEASE_READINESS_GATE.md`.

The canonical SDD entry points are:

- `.specify/memory/constitution.md` for Sea Speed Spec Kit principles;
- `specs/README.md` for the feature-artifact model;
- `specs/<feature>/spec.md` for product intent;
- `specs/<feature>/plan.md` for architecture and decisions;
- `specs/<feature>/tasks.md` for bounded execution.

## Mandatory operating rules

1. Treat GitHub `main` as the only long-term source of truth.
2. Start implementation from a canonical Issue and an explicit Outcome Contract / Implementation Scope Check.
3. Do not perform repository writes without valid source authorization recorded after the Implementation Scope Check. The preferred model is `OUTCOME APPROVED`; legacy `COMMIT APPROVED` remains a valid transition authorization.
4. `OUTCOME APPROVED` authorizes the bounded, reversible repository lifecycle for the approved outcome: branch creation, source/SDD writes, commits, integrity checks, PR creation and metadata repair, in-scope CI remediation, and merge of the exact green head when all merge gates remain satisfied. It does not authorize production mutation.
5. For significant implementation/control-plane work, create or update the linked feature specification, plan and tasks in `specs/**`; do not leave accepted product or architecture decisions only in chat, Issue comments or code.
6. Use one fresh branch and one bounded pull request for one canonical task.
7. Stop and obtain fresh authorization before material product-scope expansion, destructive action, secrets/security-boundary changes, protected behavior changes, schema incompatibility, data migration, behavior redesign, or edits under `skills/**`.
8. Keep the PR Change Contract synchronized with the exact Git diff and the derived production-impact class. Significant PRs must also link the active specification with `- Specification: specs/<feature>/spec.md`.
9. Merge still requires successful required CI, a fresh head/base check, exact changed-file scope, no unresolved review threads, and an expected-head guard when supported. A still-valid `OUTCOME APPROVED` is sufficient merge authorization; legacy tasks require separate `MERGE APPROVED` after CI evidence.
10. Do not treat merge, packaging, deployment, installation, or runtime acceptance as equivalent states.
11. Feed production acceptance, regressions and architectural learning back into linked feature artifacts when they change accepted behavior or design.
12. Never commit secrets, local runtime data, private media, model binaries, `.env`, virtual environments, snapshots, overlays, logs, or generated output.
13. Production deployment and Windows worker installation are separate protected operations. They require the evidence defined by the delivery policy and a separate production safety-envelope authorization; source Outcome Authorization alone never authorizes production mutation.

Valid terminal execution states are `COMPLETE`, `BLOCKED`, and `FAILED`. `PLAN READY` may be used before repository writes when an implementation plan awaits authorization.
