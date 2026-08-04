# Sea Speed Release Readiness Gate

Version: 1.3.0
Status: Active

## Gate

Before release execution verify:

```text
Release Readiness Gate
- Canonical Issue linked: YES/NO
- Approved source committed to main: YES/NO
- Changed files match scope: YES/NO
- Aggregate quality context successful for exact commit: YES/NO
- Secrets/runtime artifacts absent: YES/NO
- Exact artifact inventory and SHA-256 valid: YES/NO/NOT APPLICABLE
- Quality evidence valid: YES/NO/NOT APPLICABLE
- Release manifest valid: YES/NO/NOT APPLICABLE
- VPS deployment required: YES/NO
- Worker update required: YES/NO
- Mixed-contour compatibility declared: YES/NO/NOT APPLICABLE
- Rollout and rollback order declared: YES/NO/NOT APPLICABLE
- Explicit deployment approval available: YES/NO/NOT APPLICABLE
- Acceptance evidence available: YES/NO
- Rollback target available: YES/NO/NOT APPLICABLE
- Safe to continue: YES/NO
```

## Capability preflight

Before implementation begins, verify that the complete approved file set can be written and reviewed and that required branch, PR, CI, merge, release, delivery, verification and rollback operations are available. Do not accept a partial multi-file delivery as a substitute for a blocked mandatory path.

## Aggregate quality gate

The merge-facing context is:

```text
Quality integration gate / quality-integration
```

It succeeds only when all four independent domains succeed:

- `static-contract-security`;
- `property-fuzz-reliability`;
- `exact-artifact-e2e`;
- `release-deployment-evidence`.

The aggregate workflow must run without path filters and its final job must use `if: always()`. A skipped, cancelled or failed dependency is not success.

Repository source may declare `aggregate_installed_not_enforced`. Do not claim branch-protection enforcement until GitHub settings are independently verified and the state in `data/quality/quality-gates-v1.json` is updated through an approved change.

## Release provenance gate

When runtime delivery applies, validate:

- exact base and source commits;
- canonical Issue and scope hash;
- approved changed-file set;
- exact deployable artifact inventory;
- deterministic rebuild where supported;
- artifact SHA-256 and size;
- component classification and release state;
- versioned contract set and compatibility mode;
- quality evidence against `schemas/quality-evidence.schema.json`.

Use `schemas/release-manifest.schema.json` semantics. Package creation is not deployment evidence.

## Deployment authorization gate

Production deployment must not run because of a pull request, push or merge alone. It requires:

- explicit manual dispatch or an equivalent separately approved release action;
- a full exact source commit SHA;
- successful aggregate quality status for that commit;
- production-environment approval;
- validated release and quality evidence;
- a known rollback target.

## VPS gate

When VPS deployment is required, verify:

- deployment automation actually ran after explicit approval;
- deployment manifest source commit matches the approved exact commit;
- API process and health endpoint;
- `api_schema` and health `source_commit`;
- frontend smoke check when applicable;
- storage compatibility and rollback target.

## Worker gate

When a worker update is required, verify:

- package checksum, exact-artifact inventory and release manifest;
- controlled installation of the exact commit;
- preservation of local secrets/model/environment/output;
- valid deployment manifest;
- successful restart;
- state `worker_source_commit` matches the installed commit;
- fresh `updated_at`, `worker_online=true`, and advancing `frame_no`;
- telemetry schema validation;
- affected overlay/event behavior.

A GitHub-hosted exact-artifact check does not prove NVIDIA/CUDA, physical camera or RTSP operation. Those require target or self-hosted runtime evidence.

## Mixed-contour gate

When both VPS and worker updates are required, verify compatibility for old/new component combinations and execute the declared rollout order. The default is backward-compatible VPS/API first, API acceptance second, worker update third, and worker runtime acceptance last.

## Media-boundary gate

The active `mvp_v1` contract temporarily permits durable VPS event media and is recorded as `RISK-MEDIA-001`. The target `edge_v2` contract requires durable images and video on the edge node and forbids durable VPS media while permitting controlled byte streaming.

Do not report the target boundary as active before the separately approved storage migration and runtime verification complete.

## Telemetry gate

State and event evidence must satisfy `schemas/telemetry.schema.json` semantics. Identity fields are additive and must not contain secrets. Invalid records are excluded from product evidence and require a linked diagnostic or regression task when material.

## Evidence review gate

After runtime verification, complete `docs/evidence/POST_RELEASE_REVIEW.md` and return one verdict:

- `accepted`;
- `regressed`;
- `insufficient_evidence`.

A `regressed` verdict requires a linked Issue and rollback decision. An `insufficient_evidence` verdict cannot be reported as accepted.

## Documentation-only rule

Changes limited to contracts, documentation, quality tooling, skills or README require aggregate PR validation and merge only. VPS and worker release states must be `NOT REQUIRED`.

## Evidence rule

A green PR is not evidence of deployment. Merge is not release. Release is not deployment. Packaging is not installation. Deployment is not acceptance. Report only verified state. `COMPLETE` requires evidence for every applicable transition.

## Verdicts

The release gate ends with exactly one verdict:

- `APPROVED FOR RELEASE`
- `CHANGES REQUIRED`
- `BLOCKED`
