# Sea Speed Quality Gate Architecture

Status: Active
Version: 1.1.0

## Delivery flow

```text
feature branch
  -> pull request
  -> versioned contracts
  -> four independent quality domains
  -> aggregate quality context
  -> merge to main
  -> deterministic exact artifacts and evidence
  -> explicitly approved deployment
  -> post-deploy verification
```

## Stage 1: contracts and aggregate workflow

The canonical contract set defines edge events, media references, sync deliveries, worker state, operator objects, release manifests and the media-storage boundary. Positive and negative fixtures are executable.

The aggregate workflow runs on pull requests, pushes to `main` and manual dispatch. It has no path filter. Only the aggregate context should become a required branch-protection check.

Rollout state begins as `aggregate_installed_not_enforced`. It may become `aggregate_enforced` only after GitHub branch protection is independently verified.

### GitHub Actions supply-chain boundary

Every external `uses:` reference in repository workflows is pinned to an immutable 40-character commit SHA. Mutable tags and branches are prohibited. Local actions may use `./` paths.

Every workflow declares explicit top-level permissions. `permissions: write-all`, `pull_request_target`, and downloads piped directly into `sh` or `bash` are prohibited. The policy validator scans every YAML workflow, not only the aggregate and deployment workflows.

Checkout steps disable persisted Git credentials because repository workflows do not publish source changes. Adding a new external action requires explicit allow-list review and an immutable SHA.

These source controls do not prove GitHub repository settings. Required checks, branch protection, code scanning and secret-scanning settings require separate settings evidence.

## Stage 2: property, fuzz and reliability

Deterministic checks protect identity stability, duplicate suppression, safe media keys, atomic-write recovery and corrupt-data handling. Reliability limits are versioned data; relaxing an upper limit requires explicit justification.

## Stage 3: exact-artifact E2E

CI builds deterministic archives for:

- VPS API, frontend and deployment source;
- edge worker runtime and update source.

The archives are built twice and compared byte-for-byte. Validation checks SHA-256, source inventory, safe extraction, Python syntax, deploy shell syntax and HTML boundaries.

Physical NVIDIA/CUDA and camera runtime remain a separate post-install/self-hosted gate.

## Stage 4: release and deployment evidence

Quality evidence binds the exact source commit to both artifact digests, dependency inventory, contract modes, manual deployment policy and rollback instructions.

VPS production deployment is available only through `workflow_dispatch` and a protected `production` environment. Pushes to `main` never initiate production deployment.

## Stage 5: enforcement

Target repository rules:

- pull request required;
- `Quality integration gate / quality-integration` required;
- unresolved conversations block merge;
- force push disabled;
- deletion of `main` disabled;
- bypass restricted.

Repository settings enforcement is not inferred from source files or successful CI. It requires independent settings evidence.

## Edge migration boundary

Current mode:

```text
mvp_v1: VPS durable event media temporarily allowed
```

Target mode:

```text
edge_v2: edge durable media required; VPS durable media forbidden; streaming proxy allowed
```

The temporary mismatch is recorded as `RISK-MEDIA-001` until the edge-server migration is completed.
