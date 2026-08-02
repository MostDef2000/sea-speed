# Sea Speed Delivery Policy

Version: 1.2.0
Status: Active

## 1. Purpose

Define release applicability, provenance, rollout ordering and completion evidence for the independent VPS and Windows worker runtime contours.

## 2. Applicability

| Changed paths | VPS deployment | Windows worker update | Default rollout |
|---|---:|---:|---|
| `api/**` | YES | NO unless compatibility requires it | VPS, then API acceptance |
| `frontend/**` | YES | NO | VPS, then browser smoke |
| `worker/**` | NO | YES | worker package/update, then fresh-state acceptance |
| API contract plus worker consumer | YES | YES | backward-compatible VPS first, verify API, then worker |
| `deploy/vps/**` | YES | NO | VPS release gate |
| worker updater/package workflow | NO | YES | package validation, controlled install, runtime gate |
| other `deploy/**` | according to affected target | according to affected target | declare explicitly |
| `.github/workflows/**` | according to workflow scope | according to workflow scope | declare explicitly |
| `contracts/**`, `docs/**`, `skills/**`, README-only | NO | NO | PR validation and merge only |

Mixed runtime changes require both release paths unless the approved scope proves one contour is unaffected.

## 3. Pull request behavior

PR checks validate only. They must not deploy production runtime. Deployment is allowed only after approved changes reach `main` and the applicable release gate passes.

A PR may create a test package, but its state remains `packaged`, never `installed` or `runtime_verified`.

## 4. Release and deployment identity

Every applicable release must identify:

- canonical Issue;
- exact base and source commits;
- approved changed-file set and scope hash;
- component and artifact digest.

Every applicable deployment must identify:

- installed source commit;
- previous version and rollback target;
- artifact digest when available;
- health/process checks;
- runtime-verification state.

Schemas:

- `schemas/release-manifest.schema.json`;
- `schemas/deployment-manifest.schema.json`.

## 5. Mixed-contour rollout

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
→ Windows worker update
→ worker source, freshness, frame and event verification
→ post-release evidence review
```

A different order requires explicit rationale and approval.

## 6. VPS release evidence

A VPS release is complete only when applicable evidence confirms:

- deployed source corresponds to the approved merge commit;
- release and deployment manifests validate;
- API process is running when API changed;
- health endpoint succeeds and reports the expected `api_schema` and `source_commit`;
- frontend smoke check succeeds when frontend changed;
- storage/config compatibility is preserved;
- rollback target is known;
- no secret is printed or committed.

When deployment automation is disabled, report `NOT DEPLOYED`; validation success is not deployment evidence.

## 7. Windows worker release evidence

A worker release is complete only when applicable evidence confirms:

- packaged and installed worker correspond to the approved merge commit;
- package checksum and release manifest validate;
- local `.env`, model, `.venv`, output and runtime data remain untouched;
- deployment manifest identifies the installed and previous versions;
- worker restarts successfully;
- VPS receives state with matching `worker_source_commit`;
- `updated_at` advances and `worker_online` is true;
- `frame_no` advances between observations;
- state and sampled events pass `schemas/telemetry.schema.json` semantics;
- overlay/events work when affected;
- rollback package or prior commit is available.

## 8. Telemetry and evidence

Runtime identity fields are additive and must not change speed, tracking, calibration or event formulas. Evidence review follows `docs/evidence/POST_RELEASE_REVIEW.md`.

A product verdict must be one of:

- `accepted`;
- `regressed`;
- `insufficient_evidence`.

Do not compare quality windows that use incompatible camera, ROI, calibration or review procedures.

## 9. Compatibility

API schema, event schema, worker state schema, or storage schema changes require explicit approval and a declared rollout order. During transition, document whether old worker/new API and new worker/old API combinations are supported.

## 10. Manual fallback

Manual deployment or worker update is fallback-only when automation is unavailable. Provide the exact target, commit, commands or UI path, health checks, manifest locations, rollback steps and expected result.

## 11. Documentation-only changes

Governance and documentation-only tasks complete after PR validation and merge. They must not claim a VPS or worker release and must report both as `NOT REQUIRED`.
