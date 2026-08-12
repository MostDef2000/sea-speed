# Sea Speed Governance

Version: 1.5.0
Status: Active
Source of truth: GitHub `main`

## 1. Core rules

- `main` is the only long-term source of truth.
- GitHub Issues are the canonical persistent backlog, approval record and task history. Chat context may assist execution but must not replace durable issue state for implementation work.
- Feature specifications under `specs/**` are the canonical durable product-intent artifacts for their feature. They complement Issues and do not replace governance contracts.
- All GitHub repository operations must use the connected GitHub Connector. GitHub CLI `gh`, local GitHub authentication, `git push`, and direct local repository publication are not part of the Sea Speed delivery workflow.
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

Before the first repository write, verify that the complete approved lifecycle is feasible through the GitHub Connector:

- every planned file can be read and safely written;
- Issue, branch, file update, commit, PR, CI-status, workflow evidence and merge operations required by the task are available through the Connector;
- the full mandatory multi-file set can be updated without partial delivery;
- applicable VPS and Windows delivery mechanisms are known;
- release/deployment manifests, acceptance evidence and rollback paths are available or explicitly classified as manual fallback.

The absence of GitHub CLI `gh`, a local GitHub login, a local git remote, or permission to run `git push` is not a blocker and must not be presented as one. Do not ask the user to install or authenticate `gh`. Do not fall back to `gh`, local GitHub commands or direct local publication.

If a required Connector operation is unavailable, identify the exact missing capability and end as `BLOCKED` before repository writes or before any partial multi-file delivery. Local tools may be used to prepare content and run validation, but repository reading, writing, publication and lifecycle state changes remain Connector-only.

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
- `contracts/**`, `docs/**`, `specs/**`, `.specify/**`, `skills/**`: governance, SDD and documentation.

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

## 11. Spec-Driven Development artifact layer

Sea Speed uses GitHub Spec Kit concepts as a parallel artifact layer for product intent, architecture and execution while keeping this governance contract authoritative for approvals and delivery.

The hierarchy is:

- `contracts/**`: process authority, protected boundaries and delivery/evidence rules;
- `.specify/memory/constitution.md`: Sea Speed SDD principles used by Spec Kit-compatible agents;
- `.specify/templates/overrides/**`: project-local SDD artifact templates;
- `specs/<feature>/spec.md`: canonical WHAT/WHY and acceptance criteria for a feature;
- `specs/<feature>/plan.md`: accepted architecture, decisions and validation strategy;
- `specs/<feature>/tasks.md`: bounded execution plan;
- optional `research.md`, `quickstart.md` and `contracts/`: durable supporting evidence and normative feature contracts;
- code: implementation of the linked feature specification;
- runtime acceptance: operational truth that must feed back into the feature artifacts when it changes accepted behavior or architecture.

Significant implementation and control-plane PRs must declare exactly one active specification in the PR body using `- Specification: specs/<feature>/spec.md`. The feature directory must contain at least `spec.md`, `plan.md` and `tasks.md`. `scripts/ci/validate_sdd.py` enforces the baseline and PR linkage.

Narrow documentation/spec-only maintenance does not require recursively creating a new feature spec. Emergency runtime recovery may begin from an already approved Issue when production restoration is the immediate goal, but any accepted behavior or architecture change must be written back to the linked SDD artifacts before the task is represented as complete.

Historical Issues remain audit history. If runtime evidence proves that an original technical assumption is obsolete, the accepted feature spec/plan may supersede that assumption explicitly without rewriting history.

Spec Kit tooling is optional local/agent tooling. CI validates repository artifacts directly and must not depend on a specific local AI agent or Spec Kit installation.

## 12. Executable Change Contract

Every implementation pull request must keep a machine-readable Change Contract in its body. The canonical template is `.github/pull_request_template.md`, the versioned path policy is `data/contracts/change-control-policy-v1.json`, and enforcement is implemented by `scripts/ci/validate_change_contract.py`.

The Change Contract must include:

- one canonical Issue reference;
- the linked feature specification when required by the SDD policy;
- the approved scope and acceptance criteria;
- `YES` for the Implementation Scope Check approval;
- the exact changed-file set, matching the Git diff without missing or extra paths;
- one derived production-impact class: `NONE`, `CONTROL_PLANE`, `VPS`, `WINDOWS_WORKER`, or `MIXED`;
- production-impact rationale and compatibility statements;
- deployment applicability, rollout, evidence and rollback declarations;
- local, CI and applicable runtime-validation plans.

A changed-file mismatch, placeholder field, missing required section, incorrect production-impact class, incorrect SDD linkage when required, or incorrect deterministic deployment declaration fails the pull-request quality gate. Scope expansion requires new approval and a synchronized Issue and PR body before implementation continues.

`AGENTS.md` is an agent-facing entry point only. It must point to this contract and must not become an independent source of governance truth.

## 13. Merge authorization

Successful CI does not authorize merge by itself. Merge requires:

- a fresh comparison against current `main`;
- the approved exact changed-file scope;
- successful required checks for the current head SHA;
- no unresolved review threads;
- separate `MERGE APPROVED` authorization or an approved equivalent issued after CI evidence is available.

If the PR head changes after merge authorization, the authorization is stale and must be obtained again. The merge operation must use an expected-head-SHA guard when supported.

Repository rulesets, branch protection, required approvals and protected environments are GitHub settings, not facts proven by source installation. They may be reported as enforced only after independent settings verification and durable evidence.
