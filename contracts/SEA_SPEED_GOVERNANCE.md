# Sea Speed Governance

Version: 1.2.0
Status: Active
Source of truth: GitHub `main`

## 1. Core rules

- `main` is the only long-term source of truth.
- GitHub Issues are the canonical persistent backlog and task history. Chat context may assist execution but must not replace durable issue state for implementation work.
- VPS and Windows laptop are runtime environments, not editable source stores.
- Task Intake is read-only and produces a canonical Task Brief before implementation planning.
- Repository writes require `COMMIT APPROVED` or an approved equivalent issued after the Implementation Scope Check.
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
→ applicable release manifest
→ applicable VPS deployment and/or Windows worker installation
→ deployment manifest
→ runtime verification
→ post-release evidence review
→ COMPLETE
```

Do not stop at commit, PR, CI, merge, package creation, deployment start or process start when the workflow can continue safely.

## 3. Capability preflight

Before the first repository write, verify that the complete approved lifecycle is feasible:

- every planned file can be read and safely written;
- branch, commit, PR, CI-status and merge operations are available;
- the full mandatory multi-file set can be updated without partial delivery;
- applicable VPS and Windows delivery mechanisms are known;
- release/deployment manifests, acceptance evidence and rollback paths are available or explicitly classified as manual fallback.

Do not begin a partial multi-file implementation when a safe path for the full mandatory set is unavailable. End as `BLOCKED` before writes, or request a smaller approved scope.

## 4. Branch policy

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

## 5. Domain boundaries

- `worker/**`: Windows AI worker.
- `api/**`: VPS FastAPI backend.
- `frontend/**`: operator UI.
- `deploy/**`: deployment, service, updater, health and rollback infrastructure.
- `schemas/**`: release, deployment and telemetry contracts.
- `contracts/**`, `docs/**`, `skills/**`: governance and documentation.

Domain agents edit only approved files. Cross-domain changes must be declared in scope.

## 6. Protected behavior

Without explicit approval, do not change:

- API or VPS storage schema;
- detection, tracking, scoring, speed or calibration formulas;
- event semantics;
- deployment targets or secrets handling;
- compatibility guarantees between worker and API.

Incompatible state or session schema changes must invalidate or migrate old data explicitly.

## 7. Provenance and runtime identity

Applicable delivery work must use:

- `schemas/release-manifest.schema.json` for source, approved file set, scope hash and artifact identity;
- `schemas/deployment-manifest.schema.json` for installed version, checks and rollback identity;
- `schemas/telemetry.schema.json` for worker state and vehicle-event identity.

`packaged`, `installed`, `deployed` and `runtime_verified` are different states. A green workflow, uploaded ZIP or running process does not prove runtime acceptance.

Runtime telemetry may expose only non-secret identities such as source commit, schema ID and calibration hash. It must not expose credentials, environment values, private keys, raw private media or model contents.

## 8. Integrity gate

After each repository file write and before PR creation:

1. Fetch the complete written file.
2. Verify beginning, ending, required sections, and closing syntax.
3. Validate executable syntax where applicable.
4. Compare branch with `main`.
5. Confirm all changed files remain inside approved scope.
6. Confirm no secrets or runtime artifacts were introduced.

A failed check returns the task to implementation.

## 9. Evidence and feedback

Post-release evidence follows `docs/evidence/POST_RELEASE_REVIEW.md` and ends with exactly one product verdict:

- `accepted`;
- `regressed`;
- `insufficient_evidence`.

A regression requires a linked Issue and an explicit rollback decision. Insufficient evidence must not be represented as acceptance.

## 10. Completion

Valid terminal states are only:

- `COMPLETE`;
- `BLOCKED`;
- `FAILED`.

Merge is not deployment. Packaging is not installation. Deployment is not runtime acceptance. Evidence determines completion.
