# Sea Speed release and deployment provenance

Status: Active operational contract  
Issue: #24

## Identity model

Sea Speed uses two related records:

1. a release manifest proves which repository scope and artifacts were prepared from an exact source commit;
2. a deployment manifest proves which version was installed on one runtime contour and which checks passed.

`packaged`, `installed`, `deployed` and `runtime_verified` are distinct states. A package artifact is not evidence that the Windows worker is installed. A successful VPS validation job is not evidence that production deployment ran.

## Release manifest

Schema: `schemas/release-manifest.schema.json`

Required provenance:

- canonical Issue number when discoverable;
- exact base and source commits;
- sorted unique changed-file set;
- deterministic scope hash;
- component classification;
- artifact path, SHA-256 and size;
- state: `validated`, `packaged` or `ready_for_deployment`.

Generate with `scripts/release/build_release_manifest.py` and validate with `scripts/release/validate_release_manifest.py`.

## Deployment manifest

Schema: `schemas/deployment-manifest.schema.json`

The VPS writes `/opt/sea-speed-deploy/state/deployment-manifest.json` only after API health and frontend smoke checks. The Windows updater writes `D:\sea-speed\.sea-speed-worker-deployment.json` after managed files are installed and records whether process verification was performed.

Deployment evidence must not contain tokens, environment values, camera credentials, SSH configuration, runtime images or model content.

## VPS evidence

The VPS workflow collects the target deployment manifest after the deploy command, validates it and uploads it as a workflow artifact. If `VPS_DEPLOY_ENABLED` is not `true`, the workflow reports `NOT DEPLOYED`; validation success must not be presented as production deployment.

## Windows evidence

The package workflow produces:

- `sea-speed-worker.zip`;
- `sea-speed-worker.zip.sha256`;
- `release-manifest-windows-worker.json`.

Installation remains a controlled local operation. The updater records the downloaded source archive digest, previous version, rollback target and process-check result.

## Completion rule

A runtime contour can advance to `runtime_verified` only when its deployment manifest is valid and all required checks are `passed`. Merge and packaging alone do not satisfy runtime acceptance.
