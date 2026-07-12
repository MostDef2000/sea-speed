# Sea Speed VPS Deployment

## Purpose

Deploy the API and operator frontend from one exact Git commit after changes reach `main`.

The deployment model keeps only two code releases:

- current release;
- previous release used for rollback.

It does not create a full backup archive for every deployment.

## Runtime paths

Default live targets:

```text
/opt/sea-speed-api/app/main.py
/var/www/mostdef.ru/sea-speed/index.html
```

Deployment state:

```text
/opt/sea-speed-deploy/releases/
/opt/sea-speed-deploy/state/current-release
/opt/sea-speed-deploy/state/previous-release
```

The existing live API and frontend are copied once on the first deployment into a bootstrap release. Future deployments retain only the current and previous Git releases.

The script does not modify or archive:

```text
/opt/sea-speed-api/data/
/opt/sea-speed-api/media/
.env files
Nginx configuration
systemd unit files
```

Data backups remain a separate operation required only before schema migrations, destructive data changes or explicitly risky infrastructure work.

## Deployment flow

```text
exact commit SHA
→ download GitHub source archive
→ stage API and frontend release
→ atomically replace live code files
→ restart sea-speed-api
→ API health check
→ frontend smoke check
→ keep current and previous releases only
```

If either runtime check fails:

```text
restore previous code release
→ restart service
→ repeat health and frontend checks
→ fail the workflow
```

## Least-privilege model

GitHub Actions connects as a dedicated unprivileged SSH user, recommended name:

```text
sea-speed-deploy
```

The SSH session runs the deployment script without `sudo`. The user receives write access only to:

```text
/opt/sea-speed-deploy/
/opt/sea-speed-api/app/
/var/www/mostdef.ru/sea-speed/
```

The only passwordless `sudo` command is:

```text
/usr/bin/systemctl restart sea-speed-api
```

The deploy user must not receive unrestricted `sudo`, root shell access, access to `.env`, API data, media, Nginx configuration or unrelated services.

## One-time VPS preparation

Run these commands as `root` or an existing administrator. Review paths before execution.

```bash
useradd --create-home --shell /bin/bash sea-speed-deploy

install -d -o sea-speed-deploy -g sea-speed-deploy -m 0750 /opt/sea-speed-deploy

chown sea-speed-deploy:sea-speed-deploy /opt/sea-speed-api/app
chmod 0750 /opt/sea-speed-api/app

chown sea-speed-deploy:sea-speed-deploy /var/www/mostdef.ru/sea-speed
chmod 0755 /var/www/mostdef.ru/sea-speed

SYSTEMCTL_PATH="$(command -v systemctl)"
printf 'sea-speed-deploy ALL=(root) NOPASSWD: %s restart sea-speed-api\n' "$SYSTEMCTL_PATH" \
  > /etc/sudoers.d/sea-speed-deploy
chmod 0440 /etc/sudoers.d/sea-speed-deploy
visudo -cf /etc/sudoers.d/sea-speed-deploy
```

Confirm the actual systemctl path. The deployment script defaults to `/usr/bin/systemctl`. If the VPS uses another path, set `SEA_SPEED_SYSTEMCTL_BIN` for direct script execution or update the script and sudoers rule together through a reviewed change.

### SSH key

Generate a dedicated key on a trusted administrator machine:

```bash
ssh-keygen -t ed25519 -f sea-speed-deploy -C sea-speed-github-actions
```

Install only the public key on the VPS:

```bash
install -d -o sea-speed-deploy -g sea-speed-deploy -m 0700 /home/sea-speed-deploy/.ssh
cat sea-speed-deploy.pub >> /home/sea-speed-deploy/.ssh/authorized_keys
chown sea-speed-deploy:sea-speed-deploy /home/sea-speed-deploy/.ssh/authorized_keys
chmod 0600 /home/sea-speed-deploy/.ssh/authorized_keys
```

Do not copy the private key to the repository or VPS.

### Verify VPS permissions

Run as the deploy user:

```bash
sudo -n /usr/bin/systemctl restart sea-speed-api
test -w /opt/sea-speed-api/app
test -w /var/www/mostdef.ru/sea-speed
test -w /opt/sea-speed-deploy
```

Verify that unrelated privileged commands are denied:

```bash
sudo -n id
```

The last command must fail.

## GitHub configuration

Configure repository secrets:

- `VPS_HOST` — VPS hostname or IP address;
- `VPS_USER` — `sea-speed-deploy`;
- `VPS_SSH_PRIVATE_KEY` — private dedicated deploy key;
- `VPS_SSH_KNOWN_HOSTS` — trusted `known_hosts` entry for the VPS.

Optional repository variable:

- `VPS_SSH_PORT` — SSH port, default `22`.

Generate the known-hosts value from a trusted network and verify the fingerprint before saving it:

```bash
ssh-keyscan -p 22 <VPS_HOST>
```

After secrets are configured, run the workflow manually once while deployment remains disabled only if testing validation. To perform the first production deployment, set:

```text
VPS_DEPLOY_ENABLED=true
```

Then run `Deploy VPS` manually for the full current `main` commit SHA. Verify the API, frontend and release-state files before relying on automatic pushes.

## Manual run

The workflow supports `workflow_dispatch`. A full 40-character commit SHA may be supplied. If omitted, GitHub deploys the selected branch SHA.

Automatic production deployment runs only for pushes to `main` affecting:

- `api/**`;
- `frontend/**`;
- `deploy/vps/**`;
- `.github/workflows/deploy-vps.yml`.

Worker-only and documentation-only changes do not deploy the VPS.

## Acceptance checks

After the first deployment verify:

```bash
curl --fail https://mostdef.ru/sea-speed/api/health
curl --fail https://mostdef.ru/sea-speed/ >/dev/null
systemctl status sea-speed-api --no-pager
cat /opt/sea-speed-deploy/state/current-release
cat /opt/sea-speed-deploy/state/previous-release
```

Also confirm that existing files under `/opt/sea-speed-api/data/` and `/opt/sea-speed-api/media/` remain unchanged.

## Configuration overrides

The deployment script supports these environment overrides when executed directly on the VPS:

- `SEA_SPEED_REPOSITORY`;
- `SEA_SPEED_DEPLOY_ROOT`;
- `SEA_SPEED_API_TARGET`;
- `SEA_SPEED_FRONTEND_TARGET`;
- `SEA_SPEED_SYSTEMCTL_BIN`;
- `SEA_SPEED_HEALTH_URL`;
- `SEA_SPEED_FRONTEND_URL`.

The GitHub workflow intentionally uses the project defaults to keep production behavior deterministic.
