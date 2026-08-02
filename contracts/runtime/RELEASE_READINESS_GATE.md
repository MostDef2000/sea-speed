# Sea Speed Release Readiness Gate

Version: 1.2.0
Status: Active

## Gate

Before release execution verify:

```text
Release Readiness Gate
- Canonical Issue linked: YES/NO
- Approved source committed to main: YES/NO
- Changed files match scope: YES/NO
- Secrets/runtime artifacts absent: YES/NO
- Release manifest valid: YES/NO/NOT APPLICABLE
- VPS deployment required: YES/NO
- Windows worker update required: YES/NO
- Mixed-contour compatibility declared: YES/NO/NOT APPLICABLE
- Rollout and rollback order declared: YES/NO/NOT APPLICABLE
- Acceptance evidence available: YES/NO
- Rollback target available: YES/NO/NOT APPLICABLE
- Safe to continue: YES/NO
```

## Capability preflight

Before implementation begins, verify that the complete approved file set can be written and reviewed and that required branch, PR, CI, merge, release, delivery, verification and rollback operations are available. Do not accept a partial multi-file delivery as a substitute for a blocked mandatory path.

## Release provenance gate

When runtime delivery applies, validate:

- exact base and source commits;
- canonical Issue and scope hash;
- approved changed-file set;
- artifact SHA-256 and size when an artifact exists;
- component classification and release state.

Use `schemas/release-manifest.schema.json` semantics. Package creation is not deployment evidence.

## VPS gate

When VPS deployment is required, verify:

- deployment automation actually ran rather than the disabled path;
- deployment manifest source commit matches the approved merge commit;
- API process and health endpoint;
- `api_schema` and health `source_commit`;
- frontend smoke check when applicable;
- storage compatibility and rollback target.

## Worker gate

When a worker update is required, verify:

- package checksum and release manifest;
- controlled installation of the exact commit;
- preservation of local secrets/model/environment/output;
- valid Windows deployment manifest;
- successful restart;
- state `worker_source_commit` matches the installed commit;
- fresh `updated_at`, `worker_online=true`, and advancing `frame_no`;
- telemetry schema validation;
- affected overlay/event behavior.

## Mixed-contour gate

When both VPS and worker updates are required, verify compatibility for old/new component combinations and execute the declared rollout order. The default is backward-compatible VPS/API first, API acceptance second, worker update third, and worker runtime acceptance last.

## Telemetry gate

State and event evidence must satisfy `schemas/telemetry.schema.json` semantics. Identity fields are additive and must not contain secrets. Invalid records are excluded from product evidence and require a linked diagnostic or regression task when material.

## Evidence review gate

After runtime verification, complete `docs/evidence/POST_RELEASE_REVIEW.md` and return one verdict:

- `accepted`;
- `regressed`;
- `insufficient_evidence`.

A `regressed` verdict requires a linked Issue and rollback decision. An `insufficient_evidence` verdict cannot be reported as accepted.

## Documentation-only rule

Changes limited to contracts, documentation, skills or README require PR validation and merge only. VPS and worker release states must be `NOT REQUIRED`.

## Evidence rule

A green PR is not evidence of deployment. Merge is not deployment. Packaging is not installation. Deployment is not acceptance. Report only verified state. `COMPLETE` requires evidence for every applicable transition.

## Verdicts

The release gate ends with exactly one verdict:

- `APPROVED FOR RELEASE`
- `CHANGES REQUIRED`
- `BLOCKED`
