# Sea Speed VPS Deployment

## Purpose

Deploy the API, public root landing page and authenticated Sea Speed frontend from one exact Git commit after changes reach `main`.

The deployment model keeps only two code releases:

- current release;
- previous release used for rollback.

It does not create a full backup archive for every deployment.

## Runtime paths

Default live targets:

```text
/opt/sea-speed-api/app/main.py
/var/www/mostdef.ru/index.html
/var/www/mostdef.ru/sea-speed/index.html
/var/www/mostdef.ru/sea-speed/objects/index.html
/var/www/mostdef.ru/sea-speed/cameras/index.html
```

The root page at `https://mostdef.ru/` is the public entry point. Its primary action opens `/sea-speed/`. After Issue #115 there is no `/cams/` frontend/link and all browser-facing Sea Speed UI/API/media lives under the authenticated `/sea-speed/**` contour.

Deployment state:

```text
/opt/sea-speed-deploy/releases/
/opt/sea-speed-deploy/state/current-release
/opt/sea-speed-deploy/state/previous-release
```

The existing live API and frontends are copied once on the first deployment into a bootstrap release. Future deployments retain only the current and previous Git releases.

The normal code deploy script does not modify or archive:

```text
/opt/sea-speed-api/data/
/opt/sea-speed-api/media/
.env files
Nginx configuration
Authentik runtime/database/secrets
systemd unit files
```

Issue #115 adds a separate, explicitly production-gated nginx/Auth deployment helper: `deploy/vps/sea-speed-auth-cutover.sh`. It is not invoked by the normal code deployment workflow. See `docs/operations/SEA_SPEED_AUTH_V1.md`.

Data backups remain a separate operation required only before schema migrations, destructive data changes or explicitly risky infrastructure work.

## Deployment flow

```text
exact commit SHA
→ download GitHub source archive
→ stage API and frontend release
→ preserve current files in rollback release when needed
→ atomically replace live code files
→ restart sea-speed-api
→ API origin health check on loopback
→ public root + private-surface smoke checks
→ keep current and previous releases only
```

### Origin health vs public auth boundary

The deploy script deliberately separates these concerns:

```text
API health proof:
  http://127.0.0.1:8000/api/health
  expected: successful FastAPI response

Public private-surface smoke:
  https://mostdef.ru/sea-speed/api/health
  before Auth v1 cutover: may be 200 under the legacy boundary
  after Auth v1 cutover: authentication redirect/deny is expected
```

A public `200` from `/sea-speed/api/health` is therefore not required and is not used as proof that the API restarted correctly. No user credential or Authentik session is stored in GitHub Actions for deployment health checks.

The loopback default can be changed for a nonstandard VPS API listener with `SEA_SPEED_ORIGIN_HEALTH_URL`; the production default must match the actual nginx/FastAPI origin.

If any runtime check fails:

```text
restore previous code release
→ restart service
→ repeat origin health and frontend checks
→ fail the workflow
```

This code rollback is distinct from the Auth v1 nginx security rollback. The normal deploy script never changes the nginx/auth boundary.

## Least-privilege model

GitHub Actions connects as a dedicated unprivileged SSH user, recommended name:

```text
sea-speed-deploy
```

The SSH session runs the deployment script without a root shell. The user receives write access only to:

```text
/opt/sea-speed-deploy/
/opt/sea-speed-api/app/
/var/www/mostdef.ru/
/var/www/mostdef.ru/sea-speed/
```

The only passwordless `sudo` command required by the normal deploy is:

```text
/usr/bin/systemctl restart sea-speed-api
```

The deploy user must not receive unrestricted `sudo`, access to `.env`, API data, media, nginx configuration, Authentik secrets/database or unrelated services.

## One-time VPS preparation

Run these commands as `root` or an existing administrator. Review paths before execution.

```bash
useradd --create-home --shell /bin/bash sea-speed-deploy

install -d -o sea-speed-deploy -g sea-speed-deploy -m 0750 /opt/sea-speed-deploy

chown sea-speed-deploy:sea-speed-deploy /opt/sea-speed-api/app
chmod 0750 /opt/sea-speed-api/app

chown sea-speed-deploy:sea-speed-deploy /var/www/mostdef.ru
chmod 0755 /var/www/mostdef.ru

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
test -w /var/www/mostdef.ru
test -w /var/www/mostdef.ru/sea-speed
test -w /opt/sea-speed-deploy
curl --fail --silent --show-error http://127.0.0.1:8000/api/health >/dev/null
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

Production deployment always remains an explicit action against an exact full `main` SHA with the required quality/production controls. Merge does not itself authorize a deployment.

## Manual run

The workflow supports `workflow_dispatch` with a required full 40-character commit SHA. The selected commit is checked out exactly, the aggregate quality status is verified, exact artifacts/evidence are built, and only then the VPS deployment script is invoked.

Relevant VPS source contours include:

- `api/**`;
- `frontend/**`;
- `deploy/vps/**`;
- `.github/workflows/deploy-vps.yml`.

Worker-only and documentation-only changes do not imply a normal VPS code deployment.

## Acceptance checks

For a normal code deployment, verify at minimum:

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/api/health >/dev/null
curl --fail --silent --show-error https://mostdef.ru/ >/dev/null
systemctl status sea-speed-api --no-pager
cat /opt/sea-speed-deploy/state/current-release
cat /opt/sea-speed-deploy/state/previous-release
```

For `/sea-speed/**`, a post-Auth-v1 anonymous redirect/401/403 is expected and is not an API health failure. Authenticated product/security acceptance is a separate step documented in `docs/operations/SEA_SPEED_AUTH_V1.md`.

Also confirm that existing files under `/opt/sea-speed-api/data/` and `/opt/sea-speed-api/media/` remain unchanged by the normal code deploy.

## Configuration overrides

The deployment script supports these environment overrides when executed directly on the VPS:

- `SEA_SPEED_REPOSITORY`;
- `SEA_SPEED_DEPLOY_ROOT`;
- `SEA_SPEED_API_TARGET`;
- `SEA_SPEED_FRONTEND_TARGET`;
- `SEA_SPEED_OBJECTS_FRONTEND_TARGET`;
- `SEA_SPEED_CAMERAS_FRONTEND_TARGET`;
- `SEA_SPEED_ROOT_FRONTEND_TARGET`;
- `SEA_SPEED_SYSTEMCTL_BIN`;
- `SEA_SPEED_ORIGIN_HEALTH_URL` — local FastAPI health proof, default `http://127.0.0.1:8000/api/health`;
- `SEA_SPEED_HEALTH_URL` — public `/sea-speed/api/health` security smoke URL;
- `SEA_SPEED_FRONTEND_URL`;
- `SEA_SPEED_OBJECTS_FRONTEND_URL`;
- `SEA_SPEED_CAMERAS_FRONTEND_URL`;
- `SEA_SPEED_ROOT_FRONTEND_URL`.

The GitHub workflow intentionally uses the project defaults to keep production behavior deterministic.
