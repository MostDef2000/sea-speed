# Sea Speed Governance

Version: 1.0.0
Status: Active
Source of truth: GitHub `main`

## 1. Core rules

- `main` is the only long-term source of truth.
- VPS and Windows laptop are runtime environments, not editable source stores.
- Repository writes require `COMMIT APPROVED` or an approved equivalent.
- Changes under `skills/**` additionally require `SKILL UPDATE APPROVED`.
- Every task uses a fresh branch created from current `main`.
- Scope expansion, destructive action, secret use, protected-file access, API schema change, or behavior redesign requires new approval.
- Secrets, credentials, runtime logs, snapshots, overlays, videos, model binaries, `.env`, and local virtual environments must never be committed.

## 2. Controlled delivery

After approval, the Project Manager continues through all deterministic safe steps:

```text
implementation
→ integrity verification
→ pull request
→ CI validation
→ merge into main
→ applicable VPS deployment and/or Windows worker release
→ runtime verification
→ COMPLETE
```

Do not stop at commit, PR, CI, merge, or deployment start when the workflow can continue safely.

## 3. Branch policy

Before implementation verify:

```text
Branch Freshness Check
- Current main SHA:
- Task branch:
- Task branch HEAD SHA:
- merge-base(task branch, main):
- Is merge-base equal to current main SHA: YES/NO
- Branch behind main: 0/other
- Safe to implement: YES/NO
```

Before merge, re-check branch freshness and changed-file scope.

## 4. Domain boundaries

- `worker/**`: Windows AI worker.
- `api/**`: VPS FastAPI backend.
- `frontend/**`: operator UI.
- `deploy/**`: deployment, service, updater, health and rollback infrastructure.
- `contracts/**`, `docs/**`, `skills/**`: governance and documentation.

Domain agents edit only approved files. Cross-domain changes must be declared in scope.

## 5. Protected behavior

Without explicit approval, do not change:

- API or VPS storage schema;
- detection, tracking, scoring, speed or calibration formulas;
- event semantics;
- deployment targets or secrets handling;
- compatibility guarantees between worker and API.

Incompatible state or session schema changes must invalidate or migrate old data explicitly.

## 6. Integrity gate

After each repository file write and before PR creation:

1. Fetch the complete written file.
2. Verify beginning, ending, required sections, and closing syntax.
3. Validate executable syntax where applicable.
4. Compare branch with `main`.
5. Confirm all changed files remain inside approved scope.
6. Confirm no secrets or runtime artifacts were introduced.

A failed check returns the task to implementation.

## 7. Completion

Valid terminal states are only:

- `COMPLETE`;
- `BLOCKED`;
- `FAILED`.

Merge is not deployment. Deployment is not runtime acceptance. Evidence determines completion.