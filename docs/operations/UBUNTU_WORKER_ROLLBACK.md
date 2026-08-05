# Ubuntu worker exact-release rollback

Status: repository rollback contract prepared; physical worker server is not commissioned.

## Scope

This procedure explicitly switches an active Ubuntu worker service to a previously prepared exact release. It preserves shared configuration, models, datasets, output and every release directory.

It does not schedule rollback, choose a release automatically, delete data, install GPU software or prove production runtime behavior.

## Required release evidence

A rollback target must already have been prepared by the current `update-exact.sh`. Preparation writes two local non-secret evidence files:

```text
/opt/sea-speed-worker/releases/<commit>/source-commit
/opt/sea-speed-worker/releases/<commit>/quality-approved
```

The rollback command requires:

- a full lowercase 40-character target SHA;
- exact target provenance in `source-commit`;
- a root-owned mode-`0644` quality marker naming the same SHA and `quality-integration`;
- the target virtual environment and worker source;
- the target release's systemd installer;
- the protected worker environment file with mode `0600`.

A release copied manually or prepared before the quality marker existed is rejected. Re-prepare it through `update-exact.sh` before relying on it as a rollback target.

## Preflight inspection

Identify the current active commit without printing secrets:

```bash
cat /opt/sea-speed-worker/shared/runtime/active-source-commit
sudo systemctl show -p ExecStart --value sea-speed-worker.service
sudo systemctl is-active sea-speed-worker.service
```

The active marker, installed unit and running `ExecStart` must reference the same commit. Rollback fails closed when these sources disagree.

Inspect the target evidence:

```bash
cat /opt/sea-speed-worker/releases/<target>/source-commit
cat /opt/sea-speed-worker/releases/<target>/quality-approved
```

These files contain only commit and quality-check identity. They contain no credentials.

## Execute rollback

Use `--expected-current` to prevent a stale operator command from switching a service that changed after inspection:

```bash
sudo bash deploy/worker/ubuntu/rollback-exact.sh \
  <target-commit> \
  --install-root /opt/sea-speed-worker \
  --service-user sea-speed \
  --expected-current <current-commit>
```

The command:

1. acquires the same root-only lock used by `update-exact.sh`;
2. validates the active marker, installed unit and running service identity;
3. validates the exact target release and quality marker;
4. stores a root-only backup of the currently installed unit;
5. installs the systemd unit from the target exact release;
6. restarts the worker;
7. requires the service to become active;
8. confirms that `ExecStart` contains the target commit;
9. atomically updates the active source marker only after success.

Successful output includes:

```text
ROLLED_BACK from=<current> to=<target>
SERVICE_ACTIVE sea-speed-worker.service
ACTIVE_SOURCE_COMMIT <target>
```

## Failed target restoration

If target unit installation, restart, active-state validation or exact `ExecStart` validation fails, the command restores the backed-up previous unit, reloads systemd and restarts the previous service.

When restoration succeeds, it exits nonzero and prints:

```text
ROLLBACK_ABORTED target=<target> restored=<previous>
```

The active source marker remains unchanged because the target never passed acceptance.

If previous-service restoration also fails, the command reports `CRITICAL previous service restoration failed`. Treat this as an incident: do not alter release or shared directories, inspect the unit and journal, and restore service operation manually.

## Concurrency and protected state

Update and rollback share this lock:

```text
/opt/sea-speed-worker/updater/update.lock
```

The lock, temporary unit backup and temporary active marker are under the root-only updater directory. The worker service account cannot modify them.

The rollback command contains no deletion of:

```text
/opt/sea-speed-worker/shared
/opt/sea-speed-worker/releases
```

Release retention and disk-space cleanup are Stage 7 storage lifecycle responsibilities.

## Post-rollback validation

After a successful rollback, verify only non-secret service facts:

```bash
sudo systemctl is-active sea-speed-worker.service
sudo systemctl show -p ExecStart --value sea-speed-worker.service
cat /opt/sea-speed-worker/shared/runtime/active-source-commit
sudo journalctl -u sea-speed-worker.service -n 100 --no-pager
```

During physical-server commissioning, also verify GPU access, model loading, HLS frame progression, API connectivity, worker health and event publishing.

## Runtime boundary

Repository CI validates shell syntax and rollback contracts. Runtime remains `UNKNOWN` until the physical Ubuntu server exists and both successful rollback and failed-target restoration are exercised under commissioning controls.
