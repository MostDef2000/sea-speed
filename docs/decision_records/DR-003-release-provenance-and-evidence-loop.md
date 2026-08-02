# DR-003: Release provenance and evidence loop

Status: Accepted  
Date: 2026-08-02

## Context

Sea Speed has independent VPS and Windows worker runtime contours. Source merge, package creation, runtime installation and product acceptance are separate events. Before this decision, those events could be documented independently without one consistent provenance and telemetry identity model.

## Decision

Sea Speed adopts:

1. release manifests that bind an Issue, exact source/base commits, changed files, scope hash and artifact digests;
2. deployment manifests that record the installed version, previous version, checks, rollback target and runtime-verification state;
3. additive API, worker-state and vehicle-event schema identities;
4. worker source commit and calibration identity in runtime telemetry;
5. a post-release review with `accepted`, `regressed` or `insufficient_evidence` verdicts;
6. a linked regression Issue whenever evidence shows a material regression;
7. evidence-based completion after every applicable runtime contour is installed and verified.

## Scope

Applies to API/frontend deployment, Windows worker packaging and installation, runtime verification, telemetry validation, rollback evidence and final task status.

## Compatibility

Telemetry identity fields are additive. Old worker/new API remains supported because the API supplies schema defaults and permits an unknown worker source. New worker/old API remains structurally compatible because the old API stores additional JSON fields. The default rollout remains VPS/API first, then Windows worker.

## Consequences

- Packaging cannot be represented as installation.
- A successful validation job cannot be represented as production deployment.
- Runtime reports can be traced to exact source and calibration identities.
- Product-quality claims require a compatible evidence window.
- Missing evidence produces `insufficient_evidence`, not a fabricated acceptance claim.
- Detection, tracking, calibration and speed formulas are unchanged by this decision.

## Security impact

Manifests and telemetry may contain commit IDs, schema IDs and calibration hashes only. They must not contain tokens, credentials, environment values, private keys, raw private media or model contents.

## Rollback

Each applicable deployment manifest retains a rollback target. Reverting this architecture requires removing the wrapper and additive fields after ensuring active consumers do not depend on them; runtime formulas remain unaffected.

## Acceptance evidence

- repository, schema and behavioral CI;
- exact-source Windows package and checksum;
- VPS and Windows deployment manifests;
- API health source identity;
- advancing worker state and validated event telemetry;
- post-release review verdict.

## Related contracts

- `contracts/SEA_SPEED_GOVERNANCE.md`
- `contracts/SEA_SPEED_DELIVERY_POLICY.md`
- `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`
- `contracts/runtime/RELEASE_READINESS_GATE.md`
- `schemas/release-manifest.schema.json`
- `schemas/deployment-manifest.schema.json`
- `schemas/telemetry.schema.json`
- `docs/evidence/POST_RELEASE_REVIEW.md`
