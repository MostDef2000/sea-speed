# Sea Speed Delivery Policy

Version: 1.10.0
Status: Active

## 1. Purpose

Define quality admission, release applicability, provenance, rollout ordering and completion evidence for three explicit production runtime contours: VPS, Ubuntu Worker/relay, and Windows AI Worker, including the production safety-envelope model.

## 2. Applicability

| Changed paths | VPS deployment | Ubuntu Worker/relay | Windows AI Worker | Default rollout |
|---|---:|---:|---:|---|
| `api/**` | YES | NO unless compatibility requires it | NO unless compatibility requires it | VPS, then API acceptance |
| `frontend/**` | YES | NO | NO | VPS, then browser smoke |
| `deploy/vps/**` | YES | NO | NO | VPS release gate |
| `deploy/worker/ubuntu/**` | NO | YES | NO | Ubuntu Worker/relay release gate |
| Windows-specific `worker/*.ps1`, `worker/*.cmd`, `worker/windows/**` | NO | NO | YES | Windows package/update, then fresh-state acceptance |
| shared `worker/**` runtime source | NO | YES | YES | declare compatibility and exact rollout order |
| API contract plus shared worker consumer | YES | YES | YES | backward-compatible VPS first, then affected workers |
| other `deploy/**` | according to affected target | according to affected target | according to affected target | declare explicitly after specific rules |
| `.github/workflows/**` | according to workflow scope | according to workflow scope | according to workflow scope | declare explicitly |
| `contracts/**`, `data/**`, `docs/**`, `specs/**`, `skills/**`, README-only | NO | NO | NO | aggregate PR validation and merge only |

`MIXED` means two or more production contours apply. The exact VPS, Ubuntu Worker/relay and Windows AI Worker fields must still identify the exact affected set. Ubuntu-only production-impact source must never be reduced to CONTROL_PLANE because of a generic `deploy/**` rule.

Every non-empty runtime contour set requires a production safety envelope.

## 3. Pull request quality admission

PR checks validate only. They must not deploy production runtime.

The single merge-facing context is:

```text
Quality integration gate / quality-integration
```

It aggregates independently executed static/security, reliability, exact-artifact and release-evidence domains. Only success for every domain permits aggregate success.

The static contract domain validates the pull-request Change Contract against the exact base-to-head Git diff, including the declared source-authorization model and exact runtime contour fields. It also executes `scripts/ci/validate_sdd.py` for pull requests. A significant PR without one valid linked specification cannot obtain aggregate success; the validator's narrow docs/spec-only exception remains supported.

CI validation proves gate state; it does not itself create user authorization. The workflow is the canonical merge-facing repository gate, but its presence does not prove GitHub branch-protection settings.

## 4. Release and deployment identity

Every applicable new release uses `sea_speed_release_manifest_v2` and identifies:

- canonical Issue;
- applicable merged PR;
- final exact source commit and base commit;
- approved Outcome Contract hash and Change Contract hash;
- approved changed-file set and actual Git diff as separate fields;
- deterministic approved-scope hash binding Issue/PR/commits/contracts/scope;
- component and exact artifact inventory;
- artifact SHA-256 and size;
- exact-artifact and quality-evidence bindings;
- current production-authorization fingerprint when production applies.

Approved scope and actual Git diff must match before deployable readiness. A PR number parsed from a merge message is never a canonical Issue substitute. `ready_for_deployment` for a runtime component requires at least one exact artifact.

Persisted release/deployment v1 evidence remains readable for rollback and compatibility. New provenance must not rewrite historical persisted records solely to adopt v2.

Every applicable deployment must identify installed source commit, previous version/rollback target, artifact digest when available, health/process checks and runtime-verification state. Deployment manifest v1 accepts explicit targets `vps`, `ubuntu-worker`, and `windows-worker` without invalidating historical VPS/Windows manifests.

Schemas and policies remain:

- `schemas/release-manifest.schema.json`;
- `schemas/deployment-manifest.schema.json`;
- `schemas/quality-evidence.schema.json`;
- `data/contracts/contract-policy-v1.json`;
- `data/contracts/change-control-policy-v1.json`;
- `data/contracts/production-authorization-policy-v1.json`;
- `data/quality/reliability-budget-v1.json`;
- `data/quality/accepted-risks-v1.json`.

## 5. Production authorization and safety envelope

Production deployment is separate from source authorization, merge and release packaging. It must not run automatically because of a push or merge.

A production mutation requires a separately recorded production safety envelope with durable exact-SHA approval, normally:

```text
PRODUCTION APPROVED <full-lowercase-40-character-sha>
Authorization-Fingerprint: <sha256>
```

The approval must be recorded on the canonical Issue by an actor allowed by `data/contracts/production-authorization-policy-v1.json`. The fingerprint binds canonical Issue, applicable merged PR, exact source SHA, Outcome Contract, exact runtime contour set, security impact, deployment target and rollback target.

The envelope may cover, when explicitly declared:

- the final exact gated deployment for that task;
- normal restart/reload operations necessary for the deployment;
- bounded smoke and health checks;
- a specific safe rollback to a known target under a declared failure condition.

The envelope does not authorize arbitrary later SHAs. Any material change to the Outcome Contract, runtime contour set, security boundary, deployment target or rollback semantics invalidates the previous fingerprint and requires fresh production authorization. Missing GitHub API data, ambiguous PR linkage or actor mismatch fails closed.

Immediately before execution, release readiness must verify and bind:

- input is already a lowercase full 40-character SHA;
- selected source is on current `main` first-parent history, rejecting feature-head/synthetic/non-main SHAs;
- a successful completed `quality-integration.yml` workflow run exists for event `push`, branch `main`, and the exact selected head SHA; a PR check-run name is insufficient;
- the exact selected commit resolves to exactly one applicable merged PR whose Change Contract binds the canonical Issue;
- durable approval fingerprint still matches;
- validated exact artifacts, release manifest and quality evidence;
- unchanged product outcome, runtime contours and protected boundaries;
- the known rollback target and approved rollback semantics.

For VPS, `.github/workflows/deploy-vps.yml` remains `workflow_dispatch` only and retains `environment: production`. Every provenance/admission check above must run before SSH configuration. The protected environment is defense in depth, not a substitute for durable authorization.

## 6. Mixed-contour rollout

Before merging a mixed runtime change, document old/new compatibility, schema/migration requirements, exact affected contour set, deployment order, acceptance checks and rollback order. The default safe order for backward-compatible API plus workers remains VPS/API first, API acceptance second, then the applicable Ubuntu Worker/relay and/or Windows AI Worker stages in the declared order.

VPS, Ubuntu Worker/relay and Windows AI Worker are independent execution and failure domains unless the approved architecture explicitly requires host-to-host orchestration. A mixed deployment therefore normally exposes one independently executable command/entrypoint per affected contour in the declared rollout order, not one host acting as another host's deployment controller solely to reduce operator actions.

## 7. VPS release evidence

A VPS release is complete only when applicable evidence confirms:

- deployed source corresponds to the final exact first-parent main commit bound by release readiness;
- aggregate quality `push/main` run for that exact commit succeeded;
- durable canonical Issue/PR production authorization is current;
- exact artifact, release, quality and deployment evidence validate;
- API process and health are correct when API changed;
- health reports expected `api_schema` and `source_commit`;
- frontend smoke succeeds when frontend changed;
- storage/config compatibility is preserved;
- rollback target is known;
- no secret is printed or committed.

## 8. Worker release evidence

An Ubuntu Worker/relay or Windows AI Worker release is complete only when applicable evidence confirms exact source/package/install identity, preservation of local secrets/model/environment/output, valid deployment evidence, successful restart, matching runtime source identity, advancing freshness/frame state and valid telemetry for affected behavior.

Hosted CI does not prove NVIDIA, CUDA, physical-camera or RTSP runtime. Such claims require target or self-hosted evidence.

### Worker remote-operations transport

The normal interactive administration path for the commissioned Ubuntu worker is the operator-managed Windows control laptop connecting over SSH. The primary connection target remains `seaspeedadmin@10.123.239.102:22` over ZeroTier, with the documented operator-owned VPS tunnel as fallback.

SSH access is execution transport only. It never replaces GitHub Connector source operations or grants production authorization. Root-required steps retain the local human sudo boundary; passwords, private keys, camera credentials and tokens must not be transferred through chat, repository or logs.

After the operator opens the worker shell, the normal deployment command runs target-local and follows the server-pull model below. The control laptop is not the normal staging location for deployment programs.

### Canonical operator execution context

For operator-facing runtime commands, the current canonical non-secret targets are:

```text
Production VPS: root@82.146.37.153:22
Expected VPS hostname: mostdef.fvds.ru
Ubuntu worker: seaspeedadmin@10.123.239.102:22
Worker transport: ZeroTier
```

When a task uses these known targets and fresh runtime evidence has not invalidated them, operator instructions should identify the concrete target shell instead of placeholders such as `<VPS_HOST>`, `<VPS_USER>` or `<WORKER_HOST>`. The operator establishes the SSH/session boundary themselves; subsequent normal deployment bootstrap executes on that target.

The historical operator download directory remains defined for explicit fallback-only artifact transport:

```text
Windows / PowerShell UNC: \\wsl.localhost\Ubuntu\home\andrey_gubarev\downloads
WSL native: /home/andrey_gubarev/downloads
```

Do not make that directory a normal prerequisite for VPS/worker deployment. If fallback artifact transport is required, use an exact repository-derived or CI-produced artifact pinned to the approved source/release and verify its integrity/provenance before execution.

These values are execution context, not authorization. Before a protected runtime action, revalidate reachability and expected host identity, preserve normal SSH host-key verification, and stop fail-closed if current runtime evidence conflicts with the canonical target. Never place VPS passwords, sudo passwords, private SSH keys, camera credentials, populated `.env` values, TOTP material or API tokens in repository files, command arguments, prompts or logs.

### Server-pull deployment transport

The default interactive runtime transport for the production VPS and commissioned Ubuntu worker is **server-pull from the canonical GitHub repository at the exact approved source SHA** when technically available and safe.

The normal path is:

```text
operator opens the named target shell
  -> short copy-paste bootstrap selects canonical repository + exact approved 40-char SHA
  -> target retrieves/stages that exact reviewed source in a temporary local location
  -> target invokes a repository-owned deployment/operation entrypoint from that source
  -> entrypoint performs bounded preflight/mutation/verification and emits sanitized evidence
```

Requirements:

- Substantive deployment logic MUST be repository-owned before production handoff. If the exact approved SHA lacks the operation required for safe rollout, production is blocked on source implementation through the normal Issue/branch/PR/CI/merge lifecycle.
- The bootstrap command MUST be transport/bootstrap only. It may select repository/SHA, retrieve/extract exact source and invoke an entrypoint, but it MUST NOT embed a large ad-hoc deployment program, backup algorithm, configuration mutation or acceptance suite in chat.
- The canonical repository identity and full approved 40-character SHA MUST be explicit and immutable for the execution. Retrieval or identity mismatch MUST fail closed before mutation.
- The repository-owned entrypoint MUST own applicable deterministic prerequisite checks, host identity checks, exact-source/integrity/provenance verification, backup/rollback preparation, bounded mutation, restart/reload, smoke/health validation and sanitized evidence collection.
- When exact artifacts, release manifests, quality evidence or deployment manifests exist for the contour, the entrypoint SHOULD validate/reuse them rather than replacing them with manual control-laptop checks.
- Target-local temporary staging SHOULD be removed after the operation unless repository/runtime evidence rules require a retained exact release directory.
- Secrets remain target-local or in trusted external systems. Server-pull source retrieval MUST NOT require storing populated runtime secrets in GitHub or transmitting them through chat.
- GitHub Actions deployment remains an additional supported execution path when configured. It is not the only normal path when a safe repository-owned server-pull entrypoint exists, and an assistant connector lacking `workflow_dispatch` does not by itself justify an ad-hoc control-laptop launcher.
- Generated/downloaded `.sh`, `.ps1`, `.zip` or companion files on the control laptop are fallback-only. Fallback transport MUST be explicitly justified, pinned to the approved exact source/release, preserve integrity/provenance, and transport repository-owned logic rather than create new substantive deployment logic outside GitHub.

### Fastest safe deployment operator UX

Production rollout must default to the fastest and simplest operator path that still satisfies every applicable safety boundary.

The default operator-round-trip budget is **one copy-paste action and one returned sanitized result per deployment contour or independently authorized stage whenever technically safe**. This is a delivery requirement, not a stylistic preference. A second operator round trip needs a concrete protected-interaction, safety-decision or independent-failure-domain reason that cannot be encoded safely as a bounded internal guard.

- The operator-facing action MUST represent the **largest safe authorized stage** that can be executed deterministically and fail-closed on the current contour. Do not expose internal implementation phases as separate operator steps merely because they are separate scripts or commands.
- Prefer one short target-local server-pull bootstrap command per deployment contour whenever technically possible.
- Keep substantive implementation inside the reviewed repository entrypoint. One-command UX is not permission to paste a large shell program into chat.
- Move deterministic integrity/exact-SHA checks, archive handling, prerequisite checks, known dependency preparation, known-path resolution, host validation, backups/rollback preparation, mutation, restart/reload, health/runtime checks, evidence collection and safe retry logic inside the approved repository entrypoint instead of making the operator run them manually.
- Do not ask the operator to repeat canonical host/user/path values, export redundant environment variables or perform a manual hash check when the repo-owned entrypoint can derive and validate the same information safely.
- Do not make a later or independent runtime contour a prerequisite for the current stage. An unavailable worker, camera or auxiliary route must not block an independent VPS-only stage unless that contour is required for the stage's safety or acceptance result.
- Keep human checkpoints only where a person is genuinely required, including production authorization, local secret/password entry, TOTP or IdP enrollment, provider setup, host-key trust decisions, explicit review before an irreversible/high-risk transition, or equivalent protected-boundary actions that cannot be automated safely.
- A predictable sequence such as `prepare -> install known dependency -> prepare again -> activate -> health check -> collect logs` MUST NOT be the normal operator path when the repository-owned entrypoint can perform the same sequence safely. Treat that pattern as a deployment-UX defect and improve the source tooling before the next normal rollout.
- Do not require the operator to manually download/unpack a bundle, compare hashes, export redundant environment variables, repeat the same non-secret input, run a known dependency bootstrap as a separate routine step, or run separate diagnostic probes when the target-local repository entrypoint can do the same work deterministically.
- On a known failure mode, prefer one bounded repository-owned diagnostic/remediation operation that gathers sanitized evidence, applies a deterministic reversible/idempotent repair, retries the failed stage and emits the final acceptance state in the same round trip when this remains inside the current production envelope.
- On an unknown or materially risky failure, stop fail-closed at the smallest real boundary; do not invent a chain of serial probes if one bounded diagnostic operation can gather the needed evidence safely.
- Preserve exact-SHA binding, artifact/source integrity, security checks, backups, rollback semantics, host identity validation and fail-closed behavior even when the operator flow is compressed.
- Repeated entry of the same non-secret deployment data, unnecessary control-laptop downloads/unpacking, manual preflight/hash steps, redundant preparatory commands and manual diagnostics that repository automation can perform are deployment-UX defects and should be removed from the normal path.

A manual multi-command or control-laptop-artifact workflow is acceptable only as an explicit fallback when the bounded repository-owned server-pull path is unavailable or unsafe. Simplicity never authorizes skipping a required safety or evidence gate.

## 9. Media-storage transition

The current `mvp_v1` / target `edge_v2` boundary and `RISK-MEDIA-001` remain unchanged. Activating `edge_v2` remains a separate protected migration.

## 10. Telemetry, reliability and evidence

Runtime identity fields are additive and must not change speed, tracking, calibration or event formulas. Evidence review follows `docs/evidence/POST_RELEASE_REVIEW.md` and returns `accepted`, `regressed` or `insufficient_evidence`.

## 11. Enforcement state

The target merge-facing context remains `Quality integration gate / quality-integration`. Source contracts do not prove GitHub settings enforcement; branch protection, required approvals, protected environments and other rulesets require independent settings evidence.

## 12. Manual fallback

Manual deployment, control-laptop artifact staging or worker update is fallback-only when the repository-owned server-pull path is unavailable or demonstrably unsafe. The fallback must identify the reason, exact target and commit/release, artifact/source provenance and integrity, health checks, manifest locations, rollback steps and expected result, and remain within the approved production safety envelope.

Fallback artifacts should be exact repository-derived archives/files or CI-produced artifacts pinned to the approved source/release. Do not introduce new substantive deployment logic only in chat or a transient local file.

## 13. Documentation/control-plane changes

Governance, quality architecture, SDD and delivery-control tooling tasks complete after aggregate PR validation and authorized merge when their derived production impact is CONTROL_PLANE. VPS, Ubuntu Worker/relay and Windows AI Worker release states plus the production safety envelope are `NOT REQUIRED`.

A path with actual runtime impact is not converted to CONTROL_PLANE by this documentation/control-plane rule.

## 14. Production-impact classification

`data/contracts/change-control-policy-v1.json` derives `NONE`, `CONTROL_PLANE`, `VPS`, `UBUNTU_WORKER`, `WINDOWS_WORKER`, or `MIXED` from exact changed paths. For `MIXED`, the deterministic VPS/Ubuntu/Windows deployment declarations must equal the exact derived contour set. Any non-empty runtime contour set requires `Production safety envelope: REQUIRED`; NONE/CONTROL_PLANE require all runtime deployment fields and the envelope to be `NOT REQUIRED`.

Production-impact classification never authorizes production mutation; it only determines applicable evidence obligations.
