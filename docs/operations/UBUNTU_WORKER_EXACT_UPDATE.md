# Ubuntu worker exact-commit update

Status: repository update flow prepared; physical worker server is not commissioned.

## Scope

This procedure prepares or activates one exact Sea Speed worker commit. It does not follow a branch, run `git pull`, schedule updates, remove previous releases, or automatically choose a rollback target.

Explicit transactional rollback is documented in `UBUNTU_WORKER_ROLLBACK.md`.

## Security and quality boundary

The updater accepts only a full lowercase 40-character SHA that:

1. is reachable from the current `origin/main` history;
2. has a completed successful GitHub check named `quality-integration`;
3. can be prepared by the existing exact-release installer.

Quality verification uses a read-only GitHub token stored outside the worker installation tree:

```text
/etc/sea-speed/github-read-token
```

Create this file directly on the server. It must be owned by root with mode `0600` and contain only the token. Do not place the token in `worker.env`, command arguments, shell history, logs, or the repository. Use the minimum GitHub read permissions needed to inspect commit checks for `MostDef2000/sea-speed`.

Updater lock and staging state are kept in a root-only directory outside the service user's writable `shared/` tree:

```text
/opt/sea-speed-worker/updater
```

## Preparation mode

Run the updater from a trusted checkout containing the updater script:

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
7. verifies `quality-integration=success` for the exact commit;
8. invokes `install-manual.sh` from that exact staged checkout;
9. writes a root-owned `quality-approved` marker for the exact release;
10. preserves shared config, models, datasets and output;
11. exits without changing or restarting the active systemd service.

The first preparation attempt can stop with exit code `20` when the new release virtual environment does not yet contain a hardware-compatible PyTorch build. Install the verified build into that exact release environment, then rerun the same updater command. The existing prepared source and protected shared state are reused.

A successful preparation prints:

```text
PREPARED source_commit=<commit>
QUALITY_APPROVED source_commit=<commit> check=quality-integration
NOT_ACTIVATED explicit_flag_required=--activate
```

The quality marker is stored at:

```text
/opt/sea-speed-worker/releases/<commit>/quality-approved
```

It contains only the source commit and quality-check name. It is required before that release can be selected by `rollback-exact.sh`.

## Explicit activation

After inspecting the prepared release and completing server-side dependency checks, rerun with `--activate`:

```bash
sudo bash deploy/worker/ubuntu/update-exact.sh \
  <commit> \
  --install-root /opt/sea-speed-worker \
  --service-user sea-speed \
  --token-file /etc/sea-speed/github-read-token \
  --activate
```

Activation:

1. renders and verifies the systemd unit for the exact commit;
2. enables the unit through the existing systemd installer;
3. restarts `sea-speed-worker.service`;
4. requires the service to become active;
5. confirms that `ExecStart` references the requested commit;
6. records the non-secret active commit in:

```text
/opt/sea-speed-worker/shared/runtime/active-source-commit
```

## Failure behavior

If restart, active-state verification or exact `ExecStart` verification fails, the updater exits nonzero. It does not silently select another release.

Use `rollback-exact.sh` with an explicitly selected, previously prepared and quality-approved target. The rollback command validates the current active identity and restores the previous unit if the selected target fails acceptance.

Do not delete previous release directories. They are rollback inputs and remain protected until the Stage 7 storage lifecycle policy is implemented.

## Concurrency

Update and rollback use the same exclusive lock:

```text
/opt/sea-speed-worker/updater/update.lock
```

A concurrent operation fails instead of modifying release or service state. The root-only updater directory prevents the worker service account from modifying staged source, quality evidence, lock or temporary unit backups.

## Runtime validation boundary

Repository CI proves the updater contract, syntax, source selection and quality-gate integration. Runtime remains `UNKNOWN` until the physical server is installed and commissioning verifies:

- NVIDIA and PyTorch compatibility;
- model loading;
- HLS frame progression;
- API connectivity;
- worker health and event publishing;
- service restart behavior;
- exact active commit reporting;
- successful rollback and failed-target restoration.
