# Ubuntu worker exact-release rollback

Status: repository-owned production rollback flow; runtime mutation requires an applicable exact-SHA production/recovery authorization.

## Scope

This procedure explicitly switches an active Ubuntu worker service to a previously prepared exact release. It preserves shared configuration, models, datasets, output, source releases and immutable shared runtimes.

It supports both:

- a modern target that contains the independent `sea-speed-worker-control.service`; and
- a legacy target that intentionally predates that control service.

It does not schedule rollback, choose a release automatically, delete protected data, install GPU software or by itself prove final production acceptance.

## Required release evidence

A rollback target must already have exact local release evidence:

```text
/opt/sea-speed-worker/releases/<commit>/source-commit
/opt/sea-speed-worker/releases/<commit>/quality-approved
```

The rollback command requires:

- a full lowercase 40-character target SHA;
- exact target provenance in `source-commit`;
- a root-owned mode-`0644` quality marker naming the same SHA and `quality-integration`;
- a valid target source plus worker installer;
- either a ready recorded shared runtime or a supported legacy per-release runtime;
- the protected worker environment file with mode `0600`.

Worker-control capability is determined from the target release itself. Both the control service template and control agent must exist for a modern target. If only one is present, or the target installer does not manage the declared control unit, rollback fails closed as an incomplete target.

## Preflight inspection

Identify current non-secret state:

```bash
cat /opt/sea-speed-worker/shared/runtime/active-source-commit
sudo systemctl show -p ExecStart --value sea-speed-worker.service
sudo systemctl is-active sea-speed-worker.service
sudo systemctl is-enabled sea-speed-worker-control.service || true
sudo systemctl is-active sea-speed-worker-control.service || true
sudo systemctl show -p ExecStart --value sea-speed-worker-control.service || true
```

The active marker, installed worker unit and worker `ExecStart` must reference the same commit. If a current control unit exists, its unit and any running `ExecStart` must also reference that exact current commit. A running/enabled control service without an installed control unit is rejected.

Inspect target evidence:

```bash
cat /opt/sea-speed-worker/releases/<target>/source-commit
cat /opt/sea-speed-worker/releases/<target>/quality-approved
cat /opt/sea-speed-worker/releases/<target>/runtime-id 2>/dev/null || true
```

These files contain no credentials.

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
2. validates current source/runtime identity, desired worker state and current control topology;
3. validates exact target provenance, quality and runtime evidence;
4. classifies target control topology as modern or legacy and rejects partial control components;
5. stores root-only backups of the currently installed worker unit and, when present, control unit;
6. installs the target exact worker unit(s);
7. for a modern target, starts the target control service and verifies its exact target `ExecStart`;
8. for a legacy target, stops/disables/removes any newer control unit and verifies `CONTROL_SERVICE_ABSENT`;
9. applies the existing operator desired worker state;
10. confirms worker `ExecStart` contains the target source and applicable runtime ID;
11. atomically updates the active source marker only after target acceptance.

Successful modern-target output includes:

```text
ROLLED_BACK from=<current> to=<target> desired_state=<running|stopped>
CONTROL_SERVICE_ACTIVE sea-speed-worker-control.service
ACTIVE_SOURCE_COMMIT <target>
```

Successful legacy target output includes:

```text
ROLLED_BACK from=<current> to=<target> desired_state=<running|stopped>
CONTROL_SERVICE_ABSENT sea-speed-worker-control.service
ACTIVE_SOURCE_COMMIT <target>
```

## Failed target restoration

If target installation or acceptance fails, the command restores the exact previous worker unit/runtime and desired worker state.

The previous control topology is restored exactly:

- if a current control unit existed before rollback, its backed-up unit plus enabled/active state are restored and any running `ExecStart` must match the previous current commit;
- if the current release was a legacy baseline with no control unit, a partially introduced target control service is stopped, disabled and removed and absence is verified.

When restoration succeeds, rollback exits nonzero and prints:

```text
ROLLBACK_ABORTED target=<target> restored=<previous>
```

The active source marker remains unchanged because the target never passed acceptance.

If previous-service/topology restoration also fails, the command reports `CRITICAL previous service restoration failed`. Treat this as an incident: stop further automated mutation, recover actual service/unit/source state read-only, and use separately authorized recovery rather than guessing another target.

## Concurrency and protected state

Update and rollback share:

```text
/opt/sea-speed-worker/updater/update.lock
```

The lock, temporary unit backups and temporary active marker are under the root-only updater directory. The worker service account cannot modify them.

The rollback command contains no deletion of:

```text
/opt/sea-speed-worker/shared
/opt/sea-speed-worker/releases
/opt/sea-speed-worker/runtimes
```

Removal of `/etc/systemd/system/sea-speed-worker-control.service` is permitted only when restoring a target/current topology that intentionally has no control unit; it is not release/data cleanup. Release retention and disk-space cleanup remain Stage 7 storage lifecycle responsibilities.

## Post-rollback validation

After a successful rollback verify non-secret facts:

```bash
sudo systemctl is-active sea-speed-worker.service
sudo systemctl show -p ExecStart --value sea-speed-worker.service
cat /opt/sea-speed-worker/shared/runtime/active-source-commit
sudo systemctl is-active sea-speed-worker-control.service || true
sudo systemctl show -p ExecStart --value sea-speed-worker-control.service || true
sudo journalctl -u sea-speed-worker.service -n 100 --no-pager
```

For a modern target the control service must be present/active and exact-source bound. For a legacy target the control service must be absent/inactive. Production acceptance also verifies GPU/model/frame progression and Camera 1 HLS continuity as applicable.

## Runtime boundary

Repository CI validates shell syntax, exact identity/quality/runtime contracts, modern-vs-legacy target classification, legacy control-service removal and failed-target restoration topology. Runtime remains `UNKNOWN` for a rollback attempt until separately authorized production evidence confirms the actual worker/control/source/runtime state.
