# Sea Speed Delivery Policy

Version: 1.3.0
Status: Active

## 1. Purpose

Define quality admission, release applicability, provenance, rollout ordering and completion evidence for the independent VPS and worker runtime contours.

## 2. Applicability

| Changed paths | VPS deployment | Worker update | Default rollout |
|---|---:|---:|---|
| `api/**` | YES | NO unless compatibility requires it | VPS, then API acceptance |
| `frontend/**` | YES | NO | VPS, then browser smoke |
| `worker/**` | NO | YES | worker package/update, then fresh-state acceptance |
| API contract plus worker consumer | YES | YES | backward-compatible VPS first, verify API, then worker |
| `deploy/vps/**` | YES | NO | VPS release gate |
| worker updater/package workflow | NO | YES | package validation, controlled install, runtime gate |
| other `deploy/**` | according to affected target | according to affected target | declare explicitly |
| `.github/workflows/**` | according to workflow scope | according to workflow scope | declare explicitly |
| `contracts/**`, `data/**`, `docs/**`, `skills/**`, README-only | NO | NO | aggregate PR validation and merge only |

Mixed runtime changes require both release paths unless the approved scope proves one contour is unaffected.

## 3. Pull request quality admission

PR checks validate only. They must not deploy production runtime.

The single merge-facing context is:

```text
Quality integration gate / quality-integration
```

It aggregates these independently executed domains:

- static, contracts and security boundaries;
- property, deterministic fuzz and reliability;
- exact-artifact E2E;
- release and deployment evidence tooling.

The aggregate workflow has no path filters and its final job runs with `if: always()`. Only `success` for every domain permits an aggregate success.

A PR may create exact test artifacts and evidence, but their states remain `built` or `ready_for_deployment`, never `installed` or `runtime_verified`.

## 4. Release and deployment identity

Every applicable release must identify:

- canonical Issue;
- exact base and source commits;
- approved changed-file set and scope hash;
- component and exact artifact inventory;
- artifact SHA-256 and size;
- applicable contract versions;
- quality evidence.

Every applicable deployment must identify:

- installed source commit;
- previous version and rollback target;
- artifact digest when available;
- health/process checks;
- runtime-verification state.

Schemas and policies:

- `schemas/release-manifest.schema.json`;
- `schemas/deployment-manifest.schema.json`;
- `schemas/quality-evidence.schema.json`;
- `data/contracts/contract-policy-v1.json`;
- `data/quality/reliability-budget-v1.json`;
- `data/quality/accepted-risks-v1.json`.

## 5. Deployment authorization

Production deployment is a separate operation from merge and release. It must not run automatically after a push or merge to `main`.

Deployment requires:

- an explicit manual dispatch or equivalent approved release action;
- a full 40-character source commit SHA;
- a successful aggregate quality check for that exact commit;
- production-environment approval;
- validated exact artifacts, release manifest and quality evidence;
- a known rollback target.

## 6. Mixed-contour rollout

Before merging a mixed API/worker change, document:

- whether old worker/new API is supported;
- whether new worker/old API is supported;
- schema or behavior migration requirements;
- deployment order;
- acceptance checks after each step;
- rollback order and compatibility window.

The default safe order is:

```text
backward-compatible VPS/API deployment
→ API health and source identity verification
→ worker update
→ worker source, freshness, frame and event verification
→ post-release evidence review
```

A different order requires explicit rationale and approval.

## 7. VPS release evidence

A VPS release is complete only when applicable evidence confirms:

- deployed source corresponds to the explicitly approved exact commit;
- aggregate quality status for that commit was successful;
- exact artifact, release, quality and deployment evidence validate;
- API process is running when API changed;
- health endpoint succeeds and reports the expected `api_schema` and `source_commit`;
- frontend smoke check succeeds when frontend changed;
- storage/config compatibility is preserved;
- rollback target is known;
- no secret is printed or committed.

A successful quality workflow or merge is not deployment evidence.

## 8. Worker release evidence

A worker release is complete only when applicable evidence confirms:

- packaged and installed worker correspond to the approved exact commit;
- package checksum, exact inventory and release manifest validate;
- local `.env`, model, environment, output and runtime data remain untouched;
- deployment manifest identifies the installed and previous versions;
- worker restarts successfully;
- VPS receives state with matching `worker_source_commit`;
- `updated_at` advances and `worker_online` is true;
- `frame_no` advances between observations;
- state and sampled events pass `schemas/telemetry.schema.json` semantics;
- overlay/events work when affected;
- rollback package or prior commit is available.

Hosted CI does not prove NVIDIA, CUDA, physical-camera or RTSP runtime. Such claims require target or self-hosted evidence.

## 9. Media-storage transition

Versioned media modes are defined in `data/contracts/contract-policy-v1.json`.

Current mode:

```text
mvp_v1: durable VPS event media temporarily permitted
```

Target mode:

```text
edge_v2: durable edge media required; durable VPS media forbidden; controlled stream proxy allowed
```

The current mismatch is accepted only under `RISK-MEDIA-001`. Activating `edge_v2` requires a separate approved migration, merge-blocking boundary tests and runtime evidence.

## 10. Telemetry, reliability and evidence

Runtime identity fields are additive and must not change speed, tracking, calibration or event formulas. Reliability limits are versioned in `data/quality/reliability-budget-v1.json`. Evidence review follows `docs/evidence/POST_RELEASE_REVIEW.md`.

A product verdict must be one of:

- `accepted`;
- `regressed`;
- `insufficient_evidence`.

Do not compare quality windows that use incompatible camera, ROI, calibration or review procedures.

## 11. Enforcement state

The target required branch context is `Quality integration gate / quality-integration`. Source installation does not prove branch protection. Enforcement may be reported only after independent GitHub settings verification and an approved update of `data/quality/quality-gates-v1.json` from `aggregate_installed_not_enforced` to `aggregate_enforced`.

## 12. Manual fallback

Manual deployment or worker update is fallback-only when automation is unavailable. Provide the exact target, commit, commands or UI path, health checks, manifest locations, rollback steps and expected result.

## 13. Documentation-only changes

Governance, quality architecture and documentation-only tasks complete after aggregate PR validation and merge. They must not claim a VPS or worker release and must report both as `NOT REQUIRED`.
