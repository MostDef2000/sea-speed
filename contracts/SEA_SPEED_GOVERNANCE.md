# Sea Speed Governance

Version: 1.7.0
Status: Active
Source of truth: GitHub `main`

## 1. Core rules

- `main` is the only long-term source of truth.
- GitHub Issues are the canonical persistent backlog, authorization record and task history. Chat context may assist execution but must not replace durable Issue state for implementation work.
- Feature specifications under `specs/**` are the canonical durable product-intent artifacts for their feature. They complement Issues and do not replace governance contracts.
- All GitHub repository lifecycle and source-control operations must use the connected GitHub Connector. GitHub CLI `gh`, local GitHub authentication, `git push`, and direct local repository publication are not part of the Sea Speed delivery workflow. The only machine-side GitHub exception is the narrowly scoped runtime-agent mailbox described below.
- VPS and worker hosts are runtime environments, not editable source stores.
- Task Intake is read-only and produces a canonical Task Brief plus an Outcome Contract before implementation.
- Repository writes require valid source authorization issued after the Implementation Scope Check. `OUTCOME APPROVED` is the preferred authorization; legacy `COMMIT APPROVED` remains valid during transition.
- Changes under `skills/**` additionally require `SKILL UPDATE APPROVED`.
- Every task uses a fresh branch created from current `main`.
- Material product-scope expansion, destructive action, secret use/security-boundary change, protected behavior change, schema incompatibility, data migration, or behavior redesign requires fresh authorization.
- Secrets, credentials, runtime logs, snapshots, overlays, videos, model binaries, `.env`, and local virtual environments must never be committed.

### Runtime-agent GitHub mailbox exception

A dedicated Sea Speed runtime-agent may use GitHub directly only as a bounded command/result mailbox when all of the following are true:

- the mailbox is a predeclared GitHub Issue in `MostDef2000/sea-speed` whose Issue number is configured explicitly for that runtime-agent;
- the runtime-agent uses a dedicated least-privilege machine identity, preferably a GitHub App installation identity rather than a personal user credential;
- the identity may read only the designated mailbox Issue and its comments as needed to receive runtime commands;
- the identity may create new comments only on that designated mailbox Issue to publish sanitized runtime results/evidence;
- mailbox content contains no passwords, tokens, private keys, TOTP material, populated environment values, raw private media, credentials, or unsanitized runtime logs;
- runtime commands executed through the mailbox remain subject to normal source authorization, exact-SHA binding, production safety-envelope, protected-boundary and runtime-acceptance rules. The mailbox is transport only and grants no production authority by itself.

The runtime-agent exception does **not** authorize any other GitHub mutation. In particular, the runtime-agent must not:

- read or write repository Contents except through ordinary unauthenticated/trusted exact-source retrieval already allowed by the deployment model;
- create, update or delete branches, commits, tags, pull requests or releases;
- merge pull requests or alter branch protection/rulesets;
- create, edit, close, reopen, label, assign, lock or delete Issues;
- edit or delete mailbox comments;
- mutate GitHub Actions workflows/runs, environments, repository settings, secrets, variables, deploy keys or permissions;
- use its mailbox credential for `git push`, `gh`, local repository publication or general GitHub API access outside the designated mailbox operations.

Any expansion beyond the two permitted mailbox operations — read the designated Issue/comments and create sanitized result comments on that same Issue — is a security-boundary change and requires a new governance authorization.

## 2. Outcome Contract and source authorization

Before source authorization, the Project Manager records a concise Outcome Contract in the canonical Issue or equivalent durable task record:

```text
Outcome Contract
- Product outcome:
- Protected things that must not change:
- Main constraints:
- Approved repository scope:
- Runtime contour:
- Production involved: YES/NO
- Acceptance evidence:
```

`OUTCOME APPROVED` authorizes the complete bounded, reversible repository lifecycle needed to deliver that Outcome Contract:

```text
fresh branch
→ source/SDD writes
→ commits
→ integrity verification
→ pull request
→ PR metadata correction
→ CI validation
→ in-scope CI remediation
→ exact-green-head merge
```

This authorization remains valid across implementation and CI-remediation commits when all of the following remain true:

- the canonical Issue and product outcome are unchanged;
- changed files remain within the approved repository scope;
- runtime contour and protected boundaries are unchanged;
- no destructive, secret/security, incompatible-schema or migration boundary is crossed;
- the final PR head passes all required merge gates.

A new source authorization is required when any of those conditions becomes false.

Legacy `COMMIT APPROVED` authorizes repository writes but retains the legacy separate merge-authorization rule described in section 14.

## 3. Controlled delivery

After valid source authorization, the Project Manager continues through all deterministic safe repository steps without asking for another technical confirmation.

```text
implementation
→ integrity verification
→ pull request
→ CI validation/remediation
→ merge into main when authorized and gated
→ applicable release readiness
→ separately authorized production deployment and/or worker installation
→ deployment evidence
→ runtime verification
→ post-release evidence review
→ COMPLETE
```

Do not stop at commit, PR, CI, merge, package creation, deployment start or process start when the next transition is already authorized and can continue safely.

## 4. Capability preflight

Before the first repository write, verify that the complete approved lifecycle is feasible through the GitHub Connector:

- every planned file can be read and safely written;
- Issue, branch, file update, commit, PR, CI-status, workflow evidence and merge operations required by the task are available through the Connector;
- the full mandatory multi-file set can be updated without partial delivery;
- applicable VPS and worker delivery mechanisms are known;
- release/deployment manifests, acceptance evidence and rollback paths are available or explicitly classified as manual fallback.

The absence of GitHub CLI `gh`, a local GitHub login, a local git remote, or permission to run `git push` is not a blocker and must not be presented as one. Do not ask the user to install or authenticate `gh`. Do not fall back to `gh`, local GitHub commands or direct local publication.

If a required Connector operation is unavailable, identify the exact missing capability and end as `BLOCKED` before repository writes or before any partial multi-file delivery.

## 5. Branch policy

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

Before merge, re-check current `main`, exact changed-file scope and head identity. A materially changed base or conflict must be resolved inside the authorized outcome or escalated if it changes the Outcome Contract.

## 6. Domain boundaries

- `worker/**`: Windows AI worker.
- `api/**`: VPS FastAPI backend.
- `frontend/**`: operator UI.
- `deploy/**`: deployment, service, updater, health and rollback infrastructure.
- `schemas/**`: release, deployment and telemetry contracts.
- `contracts/**`, `docs/**`, `specs/**`, `.specify/**`, `skills/**`: governance, SDD and documentation.

Domain agents edit only approved files. Cross-domain changes must be declared in scope.

## 7. Protected behavior and re-authorization triggers

Fresh authorization is mandatory before:

- material product-outcome or approved-scope expansion;
- destructive or irreversible action not already in the Outcome Contract;
- secret disclosure/use outside an already approved protected runtime mechanism;
- security-boundary weakening or credential-handling redesign;
- protected Camera/runtime behavior change;
- incompatible API/state/storage/session schema change;
- data migration or destructive state transformation;
- detection, tracking, scoring, speed or calibration formula redesign;
- event-semantics redesign;
- deployment-target redesign;
- edits under `skills/**` without the additional skill authorization.

Ordinary bug fixes, test corrections, PR metadata repair and CI remediation that remain within the Outcome Contract do not require re-authorization.

## 8. Provenance and runtime identity

Applicable delivery work must use:

- `schemas/release-manifest.schema.json` for source, approved file set, scope hash and artifact identity;
- `schemas/deployment-manifest.schema.json` for installed version, checks and rollback identity;
- `schemas/telemetry.schema.json` for worker state and vehicle-event identity.

`packaged`, `installed`, `deployed` and `runtime_verified` are different states. A green workflow, uploaded ZIP or running process does not prove runtime acceptance.

Runtime telemetry may expose only non-secret identities such as source commit, schema ID and calibration hash. It must not expose credentials, environment values, private keys, raw private media or model contents.

## 9. Integrity gate

After repository writes and before PR creation:

1. Fetch the complete written files.
2. Verify beginnings, endings, required sections and closing syntax.
3. Validate executable syntax where applicable.
4. Compare branch with `main`.
5. Confirm all changed files remain inside approved scope.
6. Confirm no secrets or runtime artifacts were introduced.

A failed check returns the task to implementation. In-scope repair remains covered by the active Outcome Authorization.

## 10. Evidence and feedback

Post-release evidence follows `docs/evidence/POST_RELEASE_REVIEW.md` and ends with exactly one product verdict:

- `accepted`;
- `regressed`;
- `insufficient_evidence`.

A regression requires a linked Issue and an explicit rollback decision unless the active production safety envelope already authorized that exact safe rollback condition. Insufficient evidence must not be represented as acceptance.

## 11. Completion

Valid terminal states are only:

- `COMPLETE`;
- `BLOCKED`;
- `FAILED`.

Merge is not deployment. Packaging is not installation. Deployment is not runtime acceptance. Evidence determines completion.

## 12. Spec-Driven Development artifact layer

Sea Speed uses GitHub Spec Kit concepts as a parallel artifact layer for product intent, architecture and execution while keeping this governance contract authoritative for authorization and delivery.

Significant implementation and control-plane PRs must declare exactly one active specification in the PR body using `- Specification: specs/<feature>/spec.md`. The feature directory must contain at least `spec.md`, `plan.md` and `tasks.md`. `scripts/ci/validate_sdd.py` enforces the baseline and PR linkage.

Narrow documentation/spec-only maintenance does not require recursively creating a new feature spec. Emergency runtime recovery may begin from an already authorized Issue when production restoration is the immediate goal, but any accepted behavior or architecture change must be written back to linked SDD artifacts before completion.

Historical Issues remain audit history. Runtime evidence may supersede an obsolete technical assumption in the feature spec/plan without rewriting history.

## 13. Executable Change Contract

Every implementation pull request must keep a machine-readable Change Contract in its body. The canonical template is `.github/pull_request_template.md`, the versioned path policy is `data/contracts/change-control-policy-v1.json`, and enforcement is implemented by `scripts/ci/validate_change_contract.py`.

The Change Contract must include:

- one canonical Issue reference;
- the linked feature specification when required by SDD policy;
- the approved scope and acceptance criteria;
- the source-authorization model (`OUTCOME APPROVED` or `LEGACY COMMIT APPROVED`);
- `YES` for the Implementation Scope Check approval;
- `NO` for material scope/protected-boundary change since that authorization;
- the exact changed-file set matching the Git diff;
- one derived production-impact class;
- production-impact rationale and compatibility statements;
- deployment applicability, rollout, evidence and rollback declarations;
- local, CI and applicable runtime-validation plans.

A changed-file mismatch, placeholder, missing section, invalid authorization declaration, material-boundary-change declaration, incorrect production-impact class, incorrect SDD linkage or incorrect deterministic deployment declaration fails the pull-request quality gate.

## 14. Merge authorization

Successful CI does not authorize merge by itself. Merge always requires:

- a fresh comparison against current `main`;
- the approved exact changed-file scope;
- successful required checks for the current head SHA;
- no unresolved review threads;
- expected-head-SHA protection when supported.

Authorization is then resolved by source-authorization model:

- `OUTCOME APPROVED`: no separate merge prompt is required while the Outcome Contract remains valid. The Project Manager may merge the exact green head automatically.
- `LEGACY COMMIT APPROVED`: separate `MERGE APPROVED` (or an equivalent issued after CI evidence) is still required.

If a head change introduces material scope or protected-boundary change, Outcome Authorization is stale and must be renewed. Ordinary in-scope CI remediation does not stale it.

## 15. Production safety envelope

Source authorization never authorizes production mutation.

A separately recorded `PRODUCTION APPROVED` safety envelope may authorize the bounded release execution for one canonical task and runtime contour, including:

- deployment of the final exact green source SHA attributable to the approved Outcome Contract;
- declared normal service restart/reload operations required by that deployment;
- declared smoke/health checks;
- an explicitly declared safe rollback to a known target when the stated rollback condition occurs.

The production envelope remains valid across bounded source/CI remediation only when product outcome, runtime contour, protected boundaries, deployment method and rollback semantics remain unchanged. Immediately before production execution, release readiness must bind the envelope to the final exact 40-character SHA, successful aggregate quality, validated artifacts/evidence and known rollback target.

Any material runtime-scope change, new destructive operation, changed secret/security boundary, changed deployment target or changed rollback semantics requires fresh production authorization.

Repository rulesets, branch protection, required approvals and protected environments are GitHub settings, not facts proven by source installation. They may be reported as enforced only after independent settings verification and durable evidence.
