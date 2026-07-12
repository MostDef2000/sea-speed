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

## GitHub configuration

The workflow is disabled until the following repository secrets are configured:

- `VPS_HOST` — VPS hostname or IP address;
- `VPS_USER` — SSH user with passwordless `sudo` access for the deployment command;
- `VPS_SSH_PRIVATE_KEY` — private SSH key dedicated to deployment;
- `VPS_SSH_KNOWN_HOSTS` — trusted `known_hosts` entry for the VPS.

Optional repository variable:

- `VPS_SSH_PORT` — SSH port, default `22`.

After the secrets are configured, set:

```text
VPS_DEPLOY_ENABLED=true
```

as a repository variable.

Until that variable is enabled, the workflow completes successfully with a message that deployment is disabled.

## Required VPS permissions

The deployment user must be able to run the script through:

```text
sudo -n bash -s -- <commit-sha>
```

The command needs permission to:

- write the API and frontend target files;
- create `/opt/sea-speed-deploy`;
- restart the `sea-speed-api` systemd service;
- call the public API health and frontend URLs.

Use a dedicated deployment SSH key. Do not place the private key, tokens or passwords in this repository.

## Manual run

The workflow supports `workflow_dispatch`. A full 40-character commit SHA may be supplied. If omitted, GitHub deploys the selected branch SHA.

Automatic production deployment runs only for pushes to `main` affecting:

- `api/**`;
- `frontend/**`;
- `deploy/vps/**`;
- `.github/workflows/deploy-vps.yml`.

Worker-only and documentation-only changes do not deploy the VPS.

## Configuration overrides

The deployment script supports these environment overrides when executed directly on the VPS:

- `SEA_SPEED_REPOSITORY`;
- `SEA_SPEED_DEPLOY_ROOT`;
- `SEA_SPEED_API_TARGET`;
- `SEA_SPEED_FRONTEND_TARGET`;
- `SEA_SPEED_SERVICE`;
- `SEA_SPEED_HEALTH_URL`;
- `SEA_SPEED_FRONTEND_URL`.

The GitHub workflow intentionally uses the project defaults to keep production behavior deterministic.
