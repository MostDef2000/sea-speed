# Ubuntu worker storage lifecycle

Status: guarded lifecycle tooling is prepared in the repository. Runtime remains `UNKNOWN` until the physical Ubuntu worker is installed and commissioned.

## Safety model

Storage management is deliberately split into three operations:

1. `inventory` records current storage state and protected release identities;
2. `plan` creates a dry-run deletion plan and changes nothing;
3. `apply` accepts only a previously saved plan and revalidates every guard before deleting any item.

The daily systemd timer runs `inventory` only. It never deletes automatically. There is no unattended apply mode, retention cron, low-disk trigger, or remote deletion endpoint.

The lifecycle command does not read `worker.env`, API/HLS credentials, model contents, dataset contents, images, JSON media payloads, or journal contents. It reads only names, stat metadata, exact release provenance markers, quality markers, active-state markers and systemd state.

## Protected data

The lifecycle command cannot plan deletion of:

- the active release from `shared/runtime/active-source-commit`;
- the release referenced by the installed worker unit and running `ExecStart`;
- SHAs listed in the root-owned protected releases file;
- the configured number of newest quality-approved rollback candidates;
- `shared/config`;
- `shared/models`;
- `shared/datasets`;
- `shared/output/latest`;
- heartbeat and health reports;
- active-source markers;
- updater lock state;
- unknown files or directories.

Only these roots are eligible:

```text
/opt/sea-speed-worker/releases/<exact-sha>
/opt/sea-speed-worker/shared/output/events/<old-regular-file>
/opt/sea-speed-worker/updater/<known-stale-temporary>
```

A release is eligible only when its directory name is a full lowercase SHA, `source-commit` matches that SHA, and its root-owned `quality-approved` marker exactly records `quality-integration`.

Event cleanup accepts only regular `.jpg`, `.jpeg`, `.png`, or `.json` files directly under `shared/output/events`. Symlinks, nested directories, recent files and unknown extensions are ignored.

Updater cleanup accepts only stale `staging.*` directories and `unit-backup.*` or `active-marker.*` files. `update.lock` and unknown names are preserved.

## Installation

Run from the active exact release checkout after the worker and observability units are installed:

```bash
sudo bash deploy/worker/ubuntu/install-storage-lifecycle.sh \
  <active-commit> \
  /opt/sea-speed-worker
```

The installer:

- validates exact release provenance and quality approval;
- validates that the installed worker unit references the same commit;
- creates `/opt/sea-speed-worker/storage` as root-owned mode `0700`;
- creates `protected-releases` as root-owned mode `0600` when absent;
- installs exact-release audit service and timer units;
- verifies the units with `systemd-analyze verify`;
- enables the timer;
- does not start the timer.

Timer activation is deferred to Stage 8 commissioning.

## Pin rollback releases

Edit only as root:

```bash
sudoedit /opt/sea-speed-worker/storage/protected-releases
```

Use one full lowercase SHA per line. Blank lines and `#` comments are allowed. Keep mode `0600` and owner `root:root`. An invalid line causes inventory and planning to fail closed.

## Inventory

```bash
sudo /opt/sea-speed-worker/releases/<active-commit>/venv/bin/python \
  /opt/sea-speed-worker/releases/<active-commit>/source/deploy/worker/ubuntu/manage-storage.py \
  inventory \
  --install-root /opt/sea-speed-worker \
  --keep-releases 2 \
  --report-file /opt/sea-speed-worker/storage/storage-inventory.json
```

The report contains exact commit identities, protection reasons, release validity, directory sizes and filesystem free bytes. It contains no secrets or media bytes.

## Create a dry-run plan

```bash
sudo /opt/sea-speed-worker/releases/<active-commit>/venv/bin/python \
  /opt/sea-speed-worker/releases/<active-commit>/source/deploy/worker/ubuntu/manage-storage.py \
  plan \
  --install-root /opt/sea-speed-worker \
  --plan-file /opt/sea-speed-worker/storage/cleanup-plan.json \
  --keep-releases 2 \
  --release-min-age-days 14 \
  --event-retention-days 30 \
  --updater-temp-retention-days 7
```

Planning writes a root-owned mode-`0600` JSON file containing:

- the active SHA;
- all protected and retained rollback SHAs;
- exact deletion paths;
- allowed roots;
- file type, inode, device, size, mode and mtime fingerprints;
- planned reclaimable bytes;
- a SHA-256 plan digest.

Review the plan without exposing protected configuration:

```bash
sudo python3 -m json.tool /opt/sea-speed-worker/storage/cleanup-plan.json
```

## Apply an approved plan

There is intentionally no `--apply` switch on the planning command. Apply requires a saved plan and the expected active SHA:

```bash
sudo /opt/sea-speed-worker/releases/<active-commit>/venv/bin/python \
  /opt/sea-speed-worker/releases/<active-commit>/source/deploy/worker/ubuntu/manage-storage.py \
  apply \
  --install-root /opt/sea-speed-worker \
  --apply-plan /opt/sea-speed-worker/storage/cleanup-plan.json \
  --expected-active <active-commit>
```

Before any deletion, apply:

1. acquires the same root-only `updater/update.lock` used by update and rollback;
2. verifies the plan owner, mode, schema and digest;
3. requires the plan SHA, requested SHA, active marker, installed unit and running `ExecStart` to agree;
4. reloads pins and recalculates retained rollback candidates;
5. rejects paths outside allowed roots;
6. rejects symlinks and changed fingerprints;
7. revalidates release provenance and quality approval;
8. validates every planned item before deleting the first item.

If any guard fails, nothing is deleted.

## Commissioning checks

Stage 8 must verify on the physical server:

- audit timer installation and manual start;
- inventory report permissions and contents;
- exact active/unit/`ExecStart` agreement;
- pin-file behavior;
- plan dry-run with representative releases and event snapshots;
- changed-active and changed-fingerprint rejection;
- controlled apply against disposable test artifacts;
- preservation of active, pinned and retained rollback releases;
- preservation of config, models, datasets, latest output and observability evidence;
- audit timer behavior across reboot.

Until those checks run, repository CI proves only syntax, deterministic behavior and contract boundaries. Runtime remains `UNKNOWN`.
