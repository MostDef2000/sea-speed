# Sea Speed Agent Entry Point

Status: Active

This file is a concise adapter for coding agents. The canonical rules remain:

- `contracts/SEA_SPEED_GOVERNANCE.md`;
- `contracts/SEA_SPEED_DELIVERY_POLICY.md`;
- `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`;
- `contracts/runtime/RELEASE_READINESS_GATE.md`.

## Mandatory operating rules

1. Treat GitHub `main` as the only long-term source of truth.
2. Start implementation from a canonical Issue and an explicit approved scope.
3. Do not perform repository writes without `COMMIT APPROVED` or an approved equivalent recorded after the Implementation Scope Check.
4. Use one fresh branch and one bounded pull request for one canonical task.
5. Stop and obtain new approval before scope expansion, destructive action, protected behavior changes, secret use, or edits under `skills/**`.
6. Keep the PR Change Contract synchronized with the exact Git diff and the derived production-impact class.
7. Do not merge without successful required CI, a fresh head-SHA check, no unresolved review threads, and separate `MERGE APPROVED` authorization.
8. Do not treat merge, packaging, deployment, installation, or runtime acceptance as equivalent states.
9. Never commit secrets, local runtime data, private media, model binaries, `.env`, virtual environments, snapshots, overlays, logs, or generated output.
10. Production deployment and Windows worker installation are separate protected operations and require the evidence defined by the delivery policy.

Valid terminal execution states are `COMPLETE`, `BLOCKED`, and `FAILED`. `PLAN READY` may be used before repository writes when an implementation plan awaits approval.
