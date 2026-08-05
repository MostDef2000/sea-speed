# Ubuntu worker systemd service

Status: repository service contract prepared; physical worker server is not commissioned.

## Scope

This procedure installs a systemd service for one exact release previously prepared by `install-manual.sh`. It creates a dedicated non-login user, installs and verifies the unit, reloads systemd, and enables the service for boot. It does not start the service.

Automatic updates, rollback, NVIDIA/CUDA/PyTorch selection, and production runtime verification are separate roadmap stages.

## Preconditions

The following must already exist:

- `/opt/sea-speed-worker/releases/<commit>/source`;
- `/opt/sea-speed-worker/releases/<commit>/venv/bin/python`;
- `/opt/sea-speed-worker/releases/<commit>/source-commit` containing the same full lowercase commit;
- `/opt/sea-speed-worker/shared/config/worker.env` populated locally with mode `0600`.

Never commit, print, or copy the populated environment file into a release directory.

## Install the unit

From the exact repository checkout:

```bash
sudo bash deploy/worker/ubuntu/install-systemd.sh \
  <commit> \
  /opt/sea-speed-worker \
  sea-speed
```

The installer:

1. validates the exact release and provenance marker;
2. verifies the protected environment file without reading its contents;
3. creates the `sea-speed` system user when absent;
4. prepares `shared/runtime` links to protected models, datasets, and output;
5. installs `/etc/systemd/system/sea-speed-worker.service`;
6. runs `systemd-analyze verify`;
7. reloads systemd and enables the unit;
8. does not start the service.

## Inspect before first start

```bash
sudo systemctl cat sea-speed-worker.service
sudo systemctl is-enabled sea-speed-worker.service
sudo systemd-analyze verify /etc/systemd/system/sea-speed-worker.service
```

Confirm that `ExecStart` contains the intended exact commit and that `EnvironmentFile` points to the protected local file. Do not use `systemctl show-environment` or any command that prints secret values.

## Start and stop during commissioning

Only after NVIDIA, PyTorch, HLS, API, and model checks are complete:

```bash
sudo systemctl start sea-speed-worker.service
sudo systemctl status sea-speed-worker.service --no-pager
sudo journalctl -u sea-speed-worker.service -n 100 --no-pager
```

Graceful stop:

```bash
sudo systemctl stop sea-speed-worker.service
```

The unit sends SIGTERM and allows 30 seconds before systemd escalates termination. It restarts only on failure, with a 10-second delay and start-rate limiting.

## Remove the service definition

Stop the service first, then disable and remove only the unit:

```bash
sudo systemctl stop sea-speed-worker.service || true
sudo systemctl disable sea-speed-worker.service
sudo rm -f /etc/systemd/system/sea-speed-worker.service
sudo systemctl daemon-reload
```

Do not remove `/opt/sea-speed-worker/shared/` during service removal.

## Runtime boundary

Runtime remains `UNKNOWN` until the physical server is installed and commissioning proves GPU access, model loading, HLS frame progression, API connectivity, `worker_online`, reboot recovery, and clean shutdown behavior.
