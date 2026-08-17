# Retire Windows Worker production contour

- Issue: #199
- Status: Active implementation

## Product outcome

Sea Speed canonical governance and delivery treat only **VPS** and **Ubuntu Worker/relay** as active production/runtime contours. Shared executable Worker changes require Ubuntu acceptance, not a nonexistent Windows deployment. Windows-specific `.cmd`/`.ps1` assets remain deprecated non-production local/archive tooling so source portability and historical auditability are preserved without inventing a runtime target.

## User scenarios

1. A shared `worker/**` Python change is classified as Ubuntu Worker/relay only and can pass Change Contract validation without a Windows deployment field.
2. A VPS + shared Worker change is classified `MIXED` with exactly VPS and Ubuntu as the required contours.
3. A Windows helper script/documentation-only change is control-plane/archive work and does not require production authorization or runtime acceptance.
4. Historical Windows release/deployment manifests and old authorization fingerprints remain readable exactly as historical evidence.
5. Production execution requests route only the active VPS/Ubuntu contours.

## Requirements

- REQ-001: Active runtime topology MUST be VPS + Ubuntu Worker/relay only across canonical governance, Task Intake, PM/Delivery/Runtime/Release contracts and active operational documentation.
- REQ-002: `data/contracts/change-control-policy-v1.json` MUST map shared executable `worker/**` to Ubuntu Worker/relay and more-specific Windows `.cmd`/`.ps1`/`worker/windows/**` plus Windows helper documentation to non-runtime CONTROL_PLANE/archive semantics.
- REQ-003: New PR Change Contracts MUST expose only VPS and Ubuntu deployment/execution fields and MUST reject legacy Windows runtime fields.
- REQ-004: Modern production-authorization fingerprints MUST bind only VPS/Ubuntu runtime contour fields. Historical immutable PRs containing legacy Windows fields MUST continue to reproduce their historical payload shape.
- REQ-005: `.github/workflows/deploy-runtime-request.yml` MUST route only VPS and Ubuntu. `.github/workflows/package-worker.yml` MUST be absent.
- REQ-006: New release tooling MUST reject `windows-worker` as a new release component, while historical schemas/validators remain capable of reading persisted Windows release/deployment manifests.
- REQ-007: Exact `edge` quality artifacts MUST exclude `.cmd`, `.ps1`, and `worker/windows/**` content.
- REQ-008: Historical Issues, PRs, accepted decision records and Windows evidence MUST NOT be rewritten to imply the two-contour topology existed earlier.
- REQ-009: No API/frontend/analytics runtime behavior, Ubuntu deployment transaction, VPS/Auth boundary, secrets, physical camera/model configuration, or production host state changes under this Issue.

## Acceptance criteria

- AC-001: Shared `worker/hls_motion_yolo_worker_events.py` derives `UBUNTU_WORKER`; VPS + that shared Worker path derives `MIXED` with runtime contour set exactly `{VPS, UBUNTU_WORKER}`.
- AC-002: Windows `.ps1`/`.cmd`/`worker/windows/**` and Windows helper docs derive no runtime contour and new Change Contracts containing Windows runtime fields fail closed.
- AC-003: The PR template, active governance/contracts/docs, Task Runtime and Release Readiness describe exactly two active production contours and no normal Windows acceptance requirement.
- AC-004: Runtime execution routing has no Windows output/fallback and the obsolete Windows package workflow is absent.
- AC-005: Modern production authorization payloads omit Windows; historical PR bodies with legacy Windows fields reproduce the legacy payload shape and therefore preserve historical fingerprint verification semantics.
- AC-006: New release builder rejects `windows-worker`, while legacy Windows release/deployment manifest validation remains readable.
- AC-007: Deterministic exact artifacts remain valid and the edge artifact contains no `.cmd`, `.ps1`, or `worker/windows/**` path.
- AC-008: Exact source diff is the approved 40/40 paths; PR Validation and aggregate Quality integration are green on the exact final head and post-merge `main`; Issue #199 receives migration evidence and closes without production deployment.

## NFR assessment

- NFR-001 | Area: Security | Target: New Change Contracts and runtime routing expose exactly two active runtime contours and zero Windows execution path | Validation: unit and workflow-policy regression | Evidence: `tests/test_change_contract.py`, `tests/test_delivery_contract_convergence.py`, `scripts/quality/validate_workflow_policy.py` | Status: PASS
- NFR-002 | Area: Compatibility | Target: Historical Windows-bound authorization payloads and persisted release/deployment manifests remain readable without rewriting historical records | Validation: authorization and manifest compatibility tests | Evidence: `tests/test_production_authorization.py`, `tests/test_release_manifest.py` | Status: PASS
- NFR-003 | Area: Supply chain | Target: New exact edge artifacts contain zero `.cmd`, `.ps1`, or `worker/windows/**` entries | Validation: deterministic exact-artifact build and validator | Evidence: `scripts/quality/validate_exact_artifacts.py`, `tests/quality/test_quality_architecture.py` | Status: PASS
- NFR-004 | Area: Operations | Target: Governance migration requires zero VPS/Ubuntu production mutations and zero operator runtime actions | Validation: Change Contract derived CONTROL_PLANE and post-merge evidence | Evidence: PR Change Contract and Issue #199 terminal evidence | Status: PASS

## Runtime feedback

This feature encodes an already-decided architecture reality: Windows Worker is not an active production component. The migration itself is CONTROL_PLANE only; VPS and Ubuntu runtime state remain unchanged. Historical Windows evidence is retained strictly as audit/read compatibility. Any later request to introduce another runtime target requires a new explicitly approved architecture/outcome rather than reusing deprecated Windows tooling.
