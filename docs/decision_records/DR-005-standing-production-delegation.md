# DR-005: Standing Production Delegation

Status: Accepted
Date: 2026-08-19
Issue: #229

## Decision

Sea Speed replaces per-release GitHub-comment production authorization with a standing production delegation administered outside ordinary repository lifecycle writes.

The effective delegation is trusted system state associated with the GitHub `production` environment. Repository source defines only policy constraints, schemas, evaluators and evidence. Effective permissions are the intersection of trusted delegation permissions and repository allowed actions. Repository content can narrow authority but cannot widen the independently administered delegation.

Production decisions are typed `allow` / `deny` records bound to exact source SHA, canonical Issue, merged PR, Outcome/Change Contract hashes, approved paths, runtime contours, policy version/hash and delegation ID. New release provenance uses `sea_speed_release_manifest_v3`; successful runtime execution additionally produces a typed execution audit.

## Trust boundary

Authoritative for runtime execution:

```text
independently administered production environment state
  + exact merged current-main release metadata
  + repository policy constraints
  + exact-main Quality / artifact / rollback gates
```

Non-authoritative for runtime execution:

```text
Issue/PR/comment/README/repository prose
PRODUCTION APPROVED ...
Authorization-Fingerprint: ...
Execution-Intent: EXECUTE
DEPLOY VPS ...
Policy-Hash or Decision-ID by itself
```

`OUTCOME APPROVED` remains the source-change authorization boundary. This decision does not delegate IAM, secrets, environment settings, branch protection or arbitrary infrastructure mutation.

## Consequences

- Normal runtime releases no longer require per-release production approval text after standing delegation is activated.
- Missing, disabled, stale, policy-hash-mismatched or scope-mismatched standing delegation fails closed before transport.
- Protected VPS and Ubuntu workflows independently re-evaluate policy so direct workflow dispatch cannot bypass authority.
- Historical Issue comments and release v1/v2 evidence remain immutable/readable history but no longer grant new production authority.
- Activation requires one administrator action in trusted environment settings after source integration; environment settings remain outside Delivery Orchestrator authority.
- If the `production` environment has a required reviewer gate, autonomous operation is not achieved; activation must remove the per-run reviewer requirement while preserving independent administration of the standing delegation.

## Rejected alternatives

- Keep exact three-line per-release comments: rejected because authority, execution intent and audit transport remain coupled and agent-created comments are not an independent root of trust.
- Store effective delegation in repository JSON: rejected because repository source is not independent authority state.
- Treat policy hash or decision ID as a bearer credential: rejected because hashes are integrity identifiers, not authority.
- Give the agent environment/IAM administration rights: rejected because it collapses the trust boundary the standing delegation is intended to create.
