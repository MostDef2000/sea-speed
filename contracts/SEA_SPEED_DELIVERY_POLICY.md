# Sea Speed Delivery Policy

Version: 1.8.0
Status: Active

## 1. Purpose

Define quality admission, release applicability, provenance, rollout ordering and completion evidence for the independent VPS and worker runtime contours, including the production safety-envelope model.

## 2. Applicability

| Changed paths | VPS deployment | Worker update | Default rollout |
|---|---:|---:|---|
| `api/**` | YES | NO unless compatibility requires it | VPS, then API acceptance |
| `frontend/**` | YES | NO | VPS, then browser smoke |
| `worker/**` | NO | YES | worker package/update, then fresh-state acceptance |
| API contract plus worker consumer | YES | YES | backward-compatible VPS first, verify API, then worker |
| `deploy/vps/**` | YES | NO | VPS release gate |
| worker updater/package workflow | NO | YES | package validation, controlled install, runtime gate |
| other `deploy/**` | according to affected target | according to affected target | declare explicitly |
| `.github/workflows/**` | according to workflow scope | according to workflow scope | declare explicitly |
| `contracts/**`, `data/**`, `docs/**`, `specs/**`, `skills/**`, README-only | NO | NO | aggregate PR validation and merge only |

Mixed runtime changes require both release paths unless the approved scope proves one contour is unaffected.

## 3. Pull request quality admission

PR checks validate only. They must not deploy production runtime.

The single merge-facing context is:

```text
Quality integration gate / quality-integration
```

It aggregates independently executed static/security, reliability, exact-artifact and release-evidence domains. Only success for every domain permits aggregate success.

The static contract domain validates the pull-request Change Contract against the exact base-to-head Git diff, including the declared source-authorization model. CI validation proves gate state; it does not itself create user authorization.

## 4. Release and deployment identity

Every applicable release must identify:

- canonical Issue;
- final exact source commit;
- approved Outcome Contract / scope identity;
- approved changed-file set and scope hash;
- component and exact artifact inventory;
- artifact SHA-256 and size;
- applicable contract versions;
- quality evidence.

Every applicable deployment must identify installed source commit, previous version/rollback target, artifact digest when available, health/process checks and runtime-verification state.

Schemas and policies remain:

- `schemas/release-manifest.schema.json`;
- `schemas/deployment-manifest.schema.json`;
- `schemas/quality-evidence.schema.json`;
- `data/contracts/contract-policy-v1.json`;
- `data/contracts/change-control-policy-v1.json`;
- `data/quality/reliability-budget-v1.json`;
- `data/quality/accepted-risks-v1.json`.

## 5. Production authorization and safety envelope

Production deployment is separate from source authorization, merge and release packaging. It must not run automatically because of a push or merge.

A production mutation requires a separately recorded production safety envelope, normally `PRODUCTION APPROVED`, that identifies the canonical task/outcome and authorized runtime contour. The envelope may cover, when explicitly declared:

- the final exact gated deployment for that task;
- normal restart/reload operations necessary for the deployment;
- bounded smoke and health checks;
- a specific safe rollback to a known target under a declared failure condition.

The envelope does not authorize arbitrary later SHAs. Immediately before execution, release readiness must verify and bind:

- the final full 40-character source SHA;
- successful aggregate quality for that exact SHA;
- validated exact artifacts, release manifest and quality evidence;
- unchanged product outcome, runtime contour and protected boundaries;
- the known rollback target and approved rollback semantics.

Bounded implementation or CI-remediation commits do not by themselves invalidate an earlier production envelope when they remain inside the same approved Outcome Contract, runtime contour, deployment method and protected boundaries. A material change to any of those requires fresh production authorization.

## 6. Mixed-contour rollout

Before merging a mixed API/worker change, document old/new compatibility, schema/migration requirements, deployment order, acceptance checks and rollback order. The default safe order remains backward-compatible VPS/API first, API acceptance second, worker update third, worker runtime acceptance last.

VPS and worker are independent execution and failure domains unless the approved architecture explicitly requires host-to-host orchestration. A mixed deployment therefore normally exposes one independently executable command/entrypoint per affected contour in the declared rollout order, not one host acting as the other host's deployment controller solely to reduce operator actions.

## 7. VPS release evidence

A VPS release is complete only when applicable evidence confirms:

- deployed source corresponds to the final exact commit bound by release readiness;
- aggregate quality status for that commit succeeded;
- exact artifact, release, quality and deployment evidence validate;
- API process and health are correct when API changed;
- health reports expected `api_schema` and `source_commit`;
- frontend smoke succeeds when frontend changed;
- storage/config compatibility is preserved;
- rollback target is known;
- no secret is printed or committed.

## 8. Worker release evidence

A worker release is complete only when applicable evidence confirms exact package/install identity, preservation of local secrets/model/environment/output, valid deployment evidence, successful restart, matching `worker_source_commit`, advancing freshness/frame state and valid telemetry for affected behavior.

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

- Prefer one short target-local server-pull bootstrap command per deployment contour whenever technically possible.
- Keep substantive implementation inside the reviewed repository entrypoint. One-command UX is not permission to paste a large shell program into chat.
- Move deterministic integrity/exact-SHA checks, archive handling, prerequisite checks, known-path resolution, host validation, backups/rollback preparation and health/smoke checks inside the approved repository entrypoint instead of making the operator run them manually.
- Do not ask the operator to repeat canonical host/user/path values, export redundant environment variables or perform a manual hash check when the repo-owned entrypoint can derive and validate the same information safely.
- Do not make a later or independent runtime contour a prerequisite for the current stage. An unavailable worker, camera or auxiliary route must not block an independent VPS-only stage unless that contour is required for the stage's safety or acceptance result.
- Keep human checkpoints only where a person is genuinely required, including production authorization, local secret/password entry, TOTP or IdP enrollment, provider setup, host-key trust decisions, or equivalent protected-boundary actions that cannot be automated safely.
- Preserve exact-SHA binding, artifact/source integrity, security checks, backups, rollback semantics, host identity validation and fail-closed behavior even when the operator flow is compressed.
- Repeated entry of the same non-secret deployment data, unnecessary control-laptop downloads/unpacking, manual preflight/hash steps and manual diagnostics that repository automation can perform are deployment-UX defects and should be removed from the normal path.
- On failure, stop fail-closed and report the smallest concrete next action. Prefer repository-owned diagnostics and remediation evidence over a long sequence of operator-run troubleshooting commands.

A manual multi-command or control-laptop-artifact workflow is acceptable only as an explicit fallback when the bounded repository-owned server-pull path is unavailable or unsafe. Simplicity never authorizes skipping a required safety or evidence gate.

## 9. Media-storage transition

The current `mvp_v1` / target `edge_v2` boundary and `RISK-MEDIA-001` remain unchanged. Activating `edge_v2` remains a separate protected migration.

## 10. Telemetry, reliability and evidence

Runtime identity fields are additive and must not change speed, tracking, calibration or event formulas. Evidence review follows `docs/evidence/POST_RELEASE_REVIEW.md` and returns `accepted`, `regressed` or `insufficient_evidence`.

## 11. Enforcement state

The target required branch context remains `Quality integration gate / quality-integration`. Source contracts do not prove GitHub settings enforcement; branch protection, required approvals, protected environments and other rulesets require independent settings evidence.

## 12. Manual fallback

Manual deployment, control-laptop artifact staging or worker update is fallback-only when the repository-owned server-pull path is unavailable or demonstrably unsafe. The fallback must identify the reason, exact target and commit/release, artifact/source provenance and integrity, health checks, manifest locations, rollback steps and expected result, and remain within the approved production safety envelope.

Fallback artifacts should be exact repository-derived archives/files or CI-produced artifacts pinned to the approved source/release. Do not introduce new substantive deployment logic only in chat or a transient local file.

## 13. Documentation-only changes

Governance, quality architecture, SDD and documentation-only tasks complete after aggregate PR validation and authorized merge. VPS and worker release states are `NOT REQUIRED`.

## 14. Production-impact classification

`data/contracts/change-control-policy-v1.json` derives `NONE`, `CONTROL_PLANE`, `VPS`, `WINDOWS_WORKER`, or `MIXED` from exact changed paths. Deterministic deployment declarations remain enforced for runtime contours. `CONTROL_PLANE` requires explicit rationale.

Production-impact classification never authorizes production mutation; it only determines applicable evidence obligations.
