# Ubuntu worker exact-commit update

Status: repository-owned production update flow; runtime mutation requires a current exact-SHA production safety envelope.

## Scope

This procedure prepares or activates one exact Sea Speed Ubuntu worker commit. It does not follow a branch, run `git pull`, schedule updates, remove previous releases, or automatically choose a rollback target.

Explicit transactional rollback is documented in `UBUNTU_WORKER_ROLLBACK.md`.

## Security and quality boundary

The updater accepts only a full lowercase 40-character SHA that:

1. is reachable from the current `origin/main` history;
2. has a completed successful `push/main` run of `quality-integration.yml` for that exact SHA;
3. can be prepared by the existing exact-release installer.

The updater calls the repository-owned verifier with its supported CLI contract:

```text
verify_quality_status.py --repository <repo> --commit <sha> --workflow-file quality-integration.yml
```

The removed/unsupported `--required-name` argument must not be used.

Quality verification uses a read-only GitHub token stored outside the worker installation tree:

```text
/etc/sea-speed/github-read-token
```

Create this file directly on the server. It must be owned by root with mode `0600` and contain only the token. Do not place the token in `worker.env`, command arguments, shell history, logs, or the repository. Use the minimum GitHub read permissions needed to inspect workflow runs for `MostDef2000/sea-speed`.

Updater lock and staging state are kept in a root-only directory outside the service user's writable `shared/` tree:

```text
/opt/sea-speed-worker/updater
```

## Preparation mode

Run the updater from a trusted exact checkout containing the updater script:

```bash
sudo bash deploy/worker/ubuntu/update-exact.sh \
  <commit> \
  --install-root /opt/sea-speed-worker \
  --service-user sea-speed \
  --token-file /etc/sea-speed/github-read-token
```

The updater:

1. creates a root-owned updater directory with mode `0700`;
2. acquires an exclusive update-and-rollback lock;
3. creates a temporary clean Git repository in the root-only updater directory;
4. fetches `origin/main` from the canonical repository;
5. proves that the requested commit is an ancestor of `origin/main`;
6. checks out that exact commit in detached mode;
7. verifies the exact `quality-integration.yml` push/main result through the supported verifier CLI;
8. invokes `install-manual.sh` from that exact staged checkout;
9. binds the exact source release to its deterministic immutable shared runtime;
10. writes a root-owned `quality-approved` marker for the exact release;
11. preserves shared config, models, datasets and output;
12. exits without changing or restarting the active systemd service.

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

It contains only the source commit and quality-check identity. It is required before that release can later be selected by `rollback-exact.sh`.

## Explicit activation

Activation is a production mutation and is allowed only after the exact target SHA has a current production safety envelope and the real current source/runtime/control-service topology has been inspected.

After inspecting the prepared release, rerun its exact updater with `--activate`:

```bash
sudo bash deploy/worker/ubuntu/update-exact.sh \
  <commit> \
  --install-root /opt/sea-speed-worker \
  --service-user sea-speed \
  --token-file /etc/sea-speed/github-read-token \
  --activate
```

Activation requires a complete modern worker-control target: both `sea-speed-worker-control.service.template` and `worker-control-agent.py` must be present. Legacy releases that predate the control service are rollback targets, not forward activation targets for this updater.

Before mutation the updater records the current worker source/runtime binding and whether the current control unit is present, enabled and active. It rejects an installed or running control unit whose exact source identity disagrees with the active source marker.

Activation then:

1. renders/verifies and enables the exact worker and control units;
2. starts/restarts the independent `sea-speed-worker-control.service` and proves its `ExecStart` references the target SHA;
3. preserves the operator desired worker state (`running` or `stopped`);
4. when desired state is `running`, restarts the AI worker and requires exact-SHA frame/state progression;
5. confirms worker `ExecStart` binds both requested source SHA and recorded runtime ID;
6. atomically records the new active source commit only after all applicable verification succeeds.

## Automatic activation rollback

Any activation failure before the active marker is committed restores the exact previous worker unit/runtime and desired worker state.

Control-service topology is also transactional:

- if the previous release had a control unit, its exact unit is restored together with its previous enabled/active state;
- if the previous release was a legacy baseline with no control unit, any newly installed control service is stopped, disabled and removed, `daemon-reload` is run, and absence/inactivity are verified.

This is required for migration from a legacy baseline such as a release that predates `sea-speed-worker-control.service`. A failed forward activation must not leave a new control service behind after the worker itself has rolled back.

Successful restoration reports the previous source/runtime and `control_present=true|false`. If exact restoration cannot be proven, the updater fails closed and the active marker remains unchanged.

## Concurrency and protected state

Update and rollback use the same exclusive lock:

```text
/opt/sea-speed-worker/updater/update.lock
```

The root-only updater directory prevents the worker service account from modifying staged source, quality evidence, lock or temporary unit backups. The update path contains no deletion of protected shared config/models/datasets/output, source releases, or immutable runtime directories.

## Runtime validation boundary

Repository CI proves shell syntax, caller/verifier CLI compatibility, exact source selection, quality-gate integration, shared-runtime binding, legacy control-topology restoration contracts and active-marker ordering. Hosted CI does not prove physical GPU/camera behavior.

Runtime remains `UNKNOWN` for a new release until separately authorized production acceptance verifies:

- exact source and runtime identity;
- NVIDIA/PyTorch and model readiness;
- worker frame/state progression when desired state is running;
- independent control-service identity and protocol compatibility;
- bounded worker stop/start behavior;
- continuous Camera 1 HLS availability across worker transitions;
- explicit rollback/failed-target restoration where applicable.
