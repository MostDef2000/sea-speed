# Sea Speed Delivery Policy

Version: 1.6.0
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

### Canonical operator execution context

For operator-facing runtime commands, the current canonical non-secret targets are:

```text
Production VPS: root@82.146.37.153:22
Expected VPS hostname: mostdef.fvds.ru
Ubuntu worker: seaspeedadmin@10.123.239.102:22
Worker transport: ZeroTier
```

Generated or downloaded operator artifacts are handed off through the canonical operator download directory:

```text
Windows / PowerShell UNC: \\wsl.localhost\Ubuntu\home\andrey_gubarev\downloads
WSL native: /home/andrey_gubarev/downloads
```

When a task uses these known targets and fresh runtime evidence has not invalidated them, operator instructions should use the concrete canonical host/user values instead of placeholders such as `<VPS_HOST>`, `<VPS_USER>` or `<WORKER_HOST>`. Commands for prepared `.ps1`, `.zip`, `.sh` or related artifacts should either first change to the canonical handoff directory or use the exact full path to the real artifact filename. Companion artifacts required by a launcher should be placed in the same directory unless the launcher contract states otherwise.

These values are execution context, not authorization. Before a protected runtime action, revalidate reachability and expected host identity, preserve normal SSH host-key verification, and stop fail-closed if current runtime evidence conflicts with the canonical target. Never place VPS passwords, sudo passwords, private SSH keys, camera credentials or tokens in repository files, command arguments, prompts or logs.

## 9. Media-storage transition

The current `mvp_v1` / target `edge_v2` boundary and `RISK-MEDIA-001` remain unchanged. Activating `edge_v2` remains a separate protected migration.

## 10. Telemetry, reliability and evidence

Runtime identity fields are additive and must not change speed, tracking, calibration or event formulas. Evidence review follows `docs/evidence/POST_RELEASE_REVIEW.md` and returns `accepted`, `regressed` or `insufficient_evidence`.

## 11. Enforcement state

The target required branch context remains `Quality integration gate / quality-integration`. Source contracts do not prove GitHub settings enforcement; branch protection, required approvals, protected environments and other rulesets require independent settings evidence.

## 12. Manual fallback

Manual deployment or worker update is fallback-only when automation is unavailable. It must identify exact target and commit, health checks, manifest locations, rollback steps and expected result, and remain within the approved production safety envelope.

## 13. Documentation-only changes

Governance, quality architecture, SDD and documentation-only tasks complete after aggregate PR validation and authorized merge. VPS and worker release states are `NOT REQUIRED`.

## 14. Production-impact classification

`data/contracts/change-control-policy-v1.json` derives `NONE`, `CONTROL_PLANE`, `VPS`, `WINDOWS_WORKER`, or `MIXED` from exact changed paths. Deterministic deployment declarations remain enforced for runtime contours. `CONTROL_PLANE` requires explicit rationale.

Production-impact classification never authorizes production mutation; it only determines applicable evidence obligations.
