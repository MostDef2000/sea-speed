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
2. Start implementation from a canonical Issue and an explicit approved scope.
3. Do not perform repository writes without `COMMIT APPROVED` or an approved equivalent recorded after the Implementation Scope Check.
4. For significant implementation/control-plane work, create or update the linked feature specification, plan and tasks in `specs/**`; do not leave accepted product or architecture decisions only in chat, Issue comments or code.
5. Use one fresh branch and one bounded pull request for one canonical task.
6. Stop and obtain new approval before scope expansion, destructive action, secrets, protected behavior changes, schema incompatibility, data migration, behavior redesign, or edits under `skills/**`.
7. Keep the PR Change Contract synchronized with the exact Git diff and the derived production-impact class. Significant PRs must also link the active specification with `- Specification: specs/<feature>/spec.md`.
8. Do not merge without successful required CI, a fresh head-SHA check, no unresolved review threads, and separate `MERGE APPROVED` authorization.
9. Do not treat merge, packaging, deployment, installation, or runtime acceptance as equivalent states.
10. Feed production acceptance, regressions and architectural learning back into the linked feature artifacts when they change accepted behavior or design.
11. Never commit secrets, local runtime data, private media, model binaries, `.env`, virtual environments, snapshots, overlays, logs, or generated output.
12. Production deployment and Windows worker installation are separate protected operations and require the evidence defined by the delivery policy.

Valid terminal execution states are `COMPLETE`, `BLOCKED`, and `FAILED`. `PLAN READY` may be used before repository writes when an implementation plan awaits approval.
