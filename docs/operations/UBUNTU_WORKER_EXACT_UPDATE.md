# Ubuntu worker exact-commit update

Status: repository-owned production update flow; runtime mutation requires a current exact-SHA production safety envelope and explicit execution intent.

## Scope

The low-level `update-exact.sh` prepares or activates one exact Sea Speed Ubuntu worker commit. Normal production delivery should not expose preparation and activation as separate operator confirmations. The preferred production entrypoint is `deploy-authorized.sh`, which composes admission, exact-source staging, authorization/execution-intent verification, activation, post-verification evidence and rollback into one transaction.

Explicit transactional rollback remains documented in `UBUNTU_WORKER_ROLLBACK.md`.

## Security and quality boundary

The exact updater accepts only a full lowercase 40-character SHA that:

1. is reachable from the current `origin/main` history;
2. has a completed successful `push/main` run of `quality-integration.yml` for that exact SHA;
3. can be prepared by the existing exact-release installer.

The updater calls the repository-owned quality verifier with its supported CLI contract:

```text
verify_quality_status.py --repository <repo> --commit <sha> --workflow-file quality-integration.yml
```

The removed/unsupported `--required-name` argument must not be used.

Quality and production-authorization verification use a read-only GitHub token stored outside the worker installation tree:

```text
/etc/sea-speed/github-read-token
```

The file must be owned by root with mode `0600` and contain only the token. Do not place the token in `worker.env`, command arguments, shell history, logs, or the repository. Use the minimum GitHub read permissions needed to inspect workflow runs, Issue/PR authorization evidence and exact main provenance for `MostDef2000/sea-speed`.

Updater lock and staging state are kept in a root-only directory outside the service user's writable `shared/` tree:

```text
/opt/sea-speed-worker/updater
```

## Normal authorized deployment

For a new release, the canonical Issue may combine durable authority and execution intent in one exact record:

```text
PRODUCTION APPROVED <commit>
Authorization-Fingerprint: <sha256>
Execution-Intent: EXECUTE
```

`.github/workflows/deploy-runtime-request.yml` parses and independently verifies that record, then routes an applicable Ubuntu contour to `.github/workflows/deploy-ubuntu-worker.yml`.

The Ubuntu workflow validates current-main first-parent identity, exact `push/main` quality, durable production authorization, exact artifacts and release-manifest v2 before resolving runtime transport. If a separately provisioned restricted production transport is available, it may execute zero-touch. This repository does not create or weaken that privilege boundary.

If restricted transport is not available, the workflow produces one exact server-pull bootstrap action. The bootstrap only stages the authorized current-main source and hands off to the repository-owned transaction:

```text
deploy/worker/ubuntu/deploy-authorized.sh
```

The target launcher then:

1. stages the exact target from current `origin/main` and proves first-parent membership;
2. re-verifies durable production authorization plus exact `Execution-Intent: EXECUTE`;
3. captures the currently active exact release and desired worker state;
4. invokes the target `update-exact.sh --activate`, so preparation and activation remain one guarded transaction;
5. verifies exact active source, immutable runtime binding and independent worker-control service identity;
6. preserves intentional `running` or `stopped` worker state;
7. writes `deployment-manifest-ubuntu-worker.json` under the root-owned updater state;
8. if verification fails after the target became active, invokes exact rollback to the previously active source before returning failure.

A normal successful Ubuntu rollout therefore requires zero operator runtime commands when the restricted transport is provisioned, or one copy-paste bootstrap when it is not. Do not ask separately for preparation, activation and verification approval.

## Low-level preparation mode

`update-exact.sh` remains available as a diagnostic/recovery primitive. From a trusted exact checkout:

```bash
sudo bash deploy/worker/ubuntu/update-exact.sh \
  <commit> \
  --install-root /opt/sea-speed-worker \
  --service-user sea-speed \
  --token-file /etc/sea-speed/github-read-token
```

The updater creates root-owned staging/lock state, fetches current `origin/main`, proves exact source reachability, verifies exact quality, invokes `install-manual.sh`, binds the deterministic immutable shared runtime, writes a root-owned `quality-approved` marker, preserves shared config/models/datasets/output and exits without changing the active systemd service.

When the runtime definition is unchanged and the ready runtime already exists, preparation must report `RUNTIME_REUSED runtime_id=<id>` and must not reinstall or download the heavyweight CUDA/PyTorch environment.

A successful preparation prints lines including:

```text
RUNTIME_REUSED runtime_id=<runtime-id>
PREPARED source_commit=<commit>
QUALITY_APPROVED source_commit=<commit> check=quality-integration
NOT_ACTIVATED explicit_flag_required=--activate
```

The quality marker is stored at:

```text
/opt/sea-speed-worker/releases/<commit>/quality-approved
```

Preparation mode is not a product acceptance milestone and is not a reason for a new user confirmation when the authorized `deploy-authorized.sh` transaction is available. Runtime remains `UNKNOWN` for a merely prepared release until separately authorized production activation and runtime acceptance prove the release.

## Low-level explicit activation

For diagnostics/recovery, an already prepared exact release may still be activated directly:

```bash
sudo bash deploy/worker/ubuntu/update-exact.sh \
  <commit> \
  --install-root /opt/sea-speed-worker \
  --service-user sea-speed \
  --token-file /etc/sea-speed/github-read-token \
  --activate
```

Activation requires a complete modern worker-control target: both `sea-speed-worker-control.service.template` and `worker-control-agent.py` must be present. Legacy releases that predate the control service are rollback targets, not forward activation targets.

Before mutation the updater records the current worker source/runtime binding and whether the current control unit is present, enabled and active. It rejects an installed or running control unit whose exact source identity disagrees with the active source marker.

Activation renders/verifies and enables exact worker/control units, restarts the independent control service, preserves desired worker state, requires exact-SHA frame/state progression when running, confirms source/runtime binding and atomically records the new active source only after verification succeeds.

## Automatic activation rollback

Any activation failure before the active marker is committed restores the exact previous worker unit/runtime and desired worker state.

Control-service topology is also transactional:

- if the previous release had a control unit, its exact unit is restored together with its previous enabled/active state;
- if the previous release was a legacy baseline with no control unit, any newly installed control service is stopped, disabled and removed, `daemon-reload` is run, and absence/inactivity are verified.

`deploy-authorized.sh` adds a second post-activation guard. If the updater succeeds but the enclosing deployment transaction cannot prove exact source/runtime/control identity, the launcher invokes `rollback-exact.sh` to the previously captured source and returns failure instead of committing false acceptance.

## Concurrency and protected state

Update and rollback share the exclusive lock:

```text
/opt/sea-speed-worker/updater/update.lock
```

The authorized deployment launcher uses a separate transaction lock:

```text
/opt/sea-speed-worker/updater/deploy-authorized.lock
```

The root-only updater directory prevents the worker service account from modifying staged source, quality evidence, deployment evidence, locks or temporary unit backups. The update path contains no deletion of protected shared config/models/datasets/output, source releases, or immutable runtime directories.

## Runtime validation boundary

Repository CI executes the real `deploy-authorized.sh` transaction in an isolated sandbox with fake Git/systemd/runtime boundaries. It covers normal running-state success, intentional stopped state, authorization failure before mutation and post-activation verification failure with rollback. This shifts deterministic transaction defects left without touching production.

Hosted CI still does not prove physical GPU/camera behavior. Runtime remains `UNKNOWN` for a new release until separately authorized production acceptance verifies exact source/runtime identity, NVIDIA/PyTorch/model readiness, worker progression when desired state is running, independent control protocol compatibility, bounded worker stop/start behavior, continuous Camera 1 HLS availability across worker transitions, and explicit rollback/restoration where applicable.
