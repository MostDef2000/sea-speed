# Feature Specification: Delivery Control Hardening

- Issue: #172
- Status: Active

## Product outcome

Sea Speed delivery controls fail closed and produce machine-verifiable provenance for three explicit production runtime contours: VPS, Ubuntu Worker/relay, and Windows AI Worker. Production admission must prove an exact current-main merge commit, an exact successful aggregate quality push run, canonical Issue/PR/Outcome linkage, and durable exact-SHA production authorization before any SSH/runtime mutation.

## User scenarios

1. A change under Ubuntu worker deployment code is classified as Ubuntu Worker/relay, never as control-plane-only, and requires a production safety envelope.
2. An operator dispatching VPS production must supply a lowercase full SHA on current `main` first-parent history and the canonical Issue carrying durable authorization.
3. A release auditor can distinguish approved Change Contract scope from the actual Git diff and verify Issue, PR, Outcome Contract, artifacts, and quality-evidence bindings.
4. A significant PR cannot obtain the aggregate quality result when its required SDD linkage is absent or invalid.

## Requirements

- The change classifier MUST distinguish VPS, Ubuntu Worker/relay, and Windows AI Worker, and MUST represent multi-contour changes as MIXED while retaining the exact applicable deployment flags.
- Ubuntu-only production-impact source MUST NOT be classified as CONTROL_PLANE.
- Every runtime-impact contour MUST require `Production safety envelope: REQUIRED`.
- `deploy-vps.yml` MUST remain manual and keep the `production` environment.
- Production dispatch MUST reject non-lowercase, short, feature/synthetic, or non-main SHA input before SSH configuration.
- Production dispatch MUST require a successful `quality-integration` workflow run whose event is `push`, branch is `main`, and head SHA exactly equals the selected commit.
- Production dispatch MUST resolve a canonical Issue through the applicable merged PR Change Contract and MUST require durable `PRODUCTION APPROVED <full-sha>` evidence from a source-controlled authorized actor.
- Production authorization MUST become stale when the bound Outcome Contract, runtime contour set, security impact, deployment target, rollback target, PR, Issue, or source SHA changes.
- New release provenance MUST use release manifest v2 and MUST separately record approved files and actual files, bind the canonical Issue/PR/Outcome/Change Contract, and include SHA-256 evidence/artifact bindings.
- A non-governance release in `ready_for_deployment` state MUST contain at least one exact artifact.
- Existing persisted release/deployment v1 evidence MUST remain readable for compatibility and rollback.
- The aggregate quality workflow MUST execute SDD validation for PR linkage while preserving the existing lightweight docs/spec exception in `scripts/ci/validate_sdd.py`.
- Stage A MUST NOT mutate VPS, Ubuntu Worker/relay, or Windows AI Worker runtime state.

## Acceptance criteria

- Targeted tests prove all single contours, pairwise mixed contours, and all-three mixed contours use exact deployment flags.
- A VPS+Ubuntu change declaring Ubuntu+Windows flags fails.
- Uppercase SHA and PR-only quality evidence fail admission.
- Production authorization fingerprint changes when authorization-bound semantics change.
- Release manifest v2 rejects scope mismatch and empty deployable artifacts while v1 remains readable.
- Deployment manifest v1 accepts historical VPS/Windows targets and the explicit Ubuntu target.
- Aggregate quality statically and behaviorally proves SDD validation is part of the merge-facing aggregate dependency.
- PR Validation and Quality integration are successful for the exact final PR head before merge.
- No production workflow is dispatched as part of this feature.

## Runtime feedback

Stage A is a control-plane/source change. Runtime acceptance and production deployment are NOT REQUIRED. Runtime feedback is limited to preserving existing runtime contracts and proving through CI that no runtime payload paths are changed.
