# Feature Specification: Road Operator parity

- Feature: 020-road-operator-parity
- Issue: #206
- Status: Implementing
- Owner outcome: Make the Road operator surface visually and functionally equivalent to the canonical Sea Speed Operator while keeping Road analytics, preview and worker control fixed to `road1` / `road-v1`.

## Product outcome

`/sea-speed/road/` uses the canonical Operator interaction model rather than a separate simplified UI. It retains the same header/session/navigation, compact six-item status strip, three-column workspace, AI overlay, utility controls, adjacent clean live preview, diagnostics and detection history. Road-specific adapters remain fixed to `road1` and `road-v1`.

Stream and Worker remain independent. The Road clean preview is present beside the AI image, auto-connects on page load, and has exactly one contextual Play/Stop action. Road Worker has exactly one contextual Play/Stop action and controls only `sea-speed-road-worker.service`. Stopping Road Worker does not stop Road preview and does not alter the Water worker.

Road operator desired state is independently persisted as `running|stopped` under the Road runtime state and is preserved by exact update, deployment verification and rollback.

## User scenarios

### Scenario 1 - Road page looks and behaves like Operator
Given an authenticated operator opens `/sea-speed/road/`, the page presents the same Operator layout and interaction hierarchy as `/sea-speed/`, with Road-specific labels and `road1` data only.

### Scenario 2 - clean Road preview remains independent of AI
Given the Road page is open, clean live preview auto-connects and remains visible beside the AI overlay. When the operator stops Road Worker, clean preview remains independently available. Stream Stop/Play controls preview without changing Road Worker desired state.

### Scenario 3 - bounded Road worker control
Given trusted Authentik identity and the fixed private control origin, the browser can request Road status/start/stop only through fixed `/api/worker/control/road1*` routes. No arbitrary service, path or systemd command is accepted.

### Scenario 4 - Road desired state survives release transitions
Given Road Worker is intentionally running or stopped before an authorized exact release update or rollback, the same Road desired state is preserved unless the operator explicitly changes it.

### Scenario 5 - private Worker M2M remains telemetry/config only
Given the Worker-to-VPS private ingress is rendered, Road browser-control routes are not part of that allowlist. Existing exact analytics telemetry/config endpoints remain the only private Worker ingress.

## Requirements

- FR-001: Road MUST use the canonical Operator visual hierarchy: lighthouse/header/session/navigation, compact `STREAM / WORKER / MOTION / AI / DETECTIONS / TRACKS`, three-column workspace, utility rail, primary AI panel, adjacent clean live panel and Detection History.
- FR-002: Road MUST expose exactly one contextual `streamControlBtn` and one contextual `workerControlBtn`; duplicate preview/worker action buttons are forbidden.
- FR-003: Road clean preview MUST remain permanently represented in the layout, auto-connect on page load, and use only `/api/cameras/road1/preview/start` plus the existing bounded global preview stop route.
- FR-004: Road Stream MUST retain bounded HLS retry/recovery/watchdog behavior and MUST be independent of Road Worker state.
- FR-005: Road browser analytics MUST use `/api/analytics/road1` for state/events/ROI/speed configuration and MUST not expose protected RTSP sources.
- FR-006: VPS browser worker-control API MUST expose only fixed Road `status/start/stop` routes in addition to the existing Water routes and MUST require trusted Authentik identity.
- FR-007: Ubuntu control agent MUST accept only the fixed targets `water` and `road1`, mapping them to literal `sea-speed-worker.service` and `sea-speed-road-worker.service`; arbitrary service names/commands are forbidden.
- FR-008: Water desired state MUST remain `shared/runtime/operator-desired-state`; Road desired state MUST be independent at `shared/road-runtime/operator-desired-state` and both MUST allow only `running|stopped`.
- FR-009: Exact updater, deployment verification and rollback MUST preserve both independent desired states, including Road intentionally stopped without requiring Road runtime progression.
- FR-010: The hardened control service MAY write only Water and Road runtime desired-state roots; protected config/models/output/media MUST not become writable through the control unit.
- FR-011: Existing Worker-to-VPS private ingress MUST remain an exact telemetry/config allowlist and MUST explicitly exclude all Water and Road browser worker-control routes.
- FR-012: Existing Water Operator UI, AI detection/tracking semantics, analytics schemas, protected runtime configuration, MediaMTX/relay topology and Authentik topology MUST remain unchanged.
- FR-013: Source integration MUST not mutate production. Mixed runtime execution requires a fresh exact-main production safety envelope after exact-green merge.
- FR-014: Mixed rollout MUST update Ubuntu first and VPS second so the new Road browser control never precedes the compatible Ubuntu control surface.
- FR-015: For exact runtime release `fd449af7bdbd4036517f321b96de31fe206f623b`, VPS execution MUST be classified as `ONE_COMMAND_FALLBACK` because PR #207 changed `scripts/operations/nginx_sea_speed_auth.py`, an asset of the exact root-owned Auth privilege bundle. The VPS root bootstrap MUST install the exact-source privilege bundle before the canonical Connector VPS deployment is retried. Combined with the Ubuntu `ONE_COMMAND_FALLBACK`, operator actions expected MUST be `2`.

## Acceptance criteria

- AC-001: Frontend contract proves Road has canonical compact six-status strip, three-column workspace, AI panel, always-present adjacent clean-live panel, utility controls, State JSON, Operator log and Detection History.
- AC-002: Road source contains exactly one Stream action and one Worker action; no separate preview Start/Stop controls remain in the live card.
- AC-003: Road preview auto-connects, has retry/recovery/watchdog markers, uses only logical `road1` preview endpoints, and worker Stop does not own preview lifecycle.
- AC-004: VPS and Ubuntu tests prove Road browser worker control maps only to fixed `road1` paths and literal `sea-speed-road-worker.service`, while legacy Water control remains compatible.
- AC-005: Tests prove Water and Road desired-state files are independent and Road Stop/Start cannot mutate Water desired state or service target.
- AC-006: Exact updater and rollback tests prove Road running/stopped state is preserved and Road runtime progression is skipped only when Road is intentionally stopped.
- AC-007: Authorized Ubuntu deployment verification and manifest accept either Road desired running or stopped while preserving exact source/runtime identity.
- AC-008: Systemd tests prove the control agent can write only `shared/runtime` and `shared/road-runtime`, without writable protected config/models/output paths.
- AC-009: Auth regression proves all six browser worker-control routes are excluded from private Worker M2M ingress while the existing exact telemetry/config allowlist is unchanged.
- AC-010: PR Validation and aggregate Quality integration succeed on the same exact final head; exact approved 21-path scope is verified, including the synchronized analytics-profile Road control regression, then expected-head merge and post-merge exact-main Quality succeed.
- AC-011: After separate exact-SHA production authorization, Ubuntu-first/VPS-second runtime acceptance proves Road preview is adjacent and auto-available, Road Worker Stop leaves preview and Water unchanged, Road Start resumes advancing exact-source `road1` state, and public Authentik remains protected.
- AC-012: Production-learning correction is merged as an exact three-path SDD-only change and records VPS `ONE_COMMAND_FALLBACK`, Ubuntu `ONE_COMMAND_FALLBACK`, operator actions expected `2`, Ubuntu action `1/2` already accepted, and VPS exact root privilege-bundle bootstrap as action `2/2` before Connector retry. No runtime-installed source, protected topology or authorization-fingerprint field changes as part of this correction.

## NFR assessment

- NFR-001 | Area: OPERATOR_UX | Target: Road interaction hierarchy and controls match canonical Operator while remaining Road-specific | Validation: frontend contract plus authenticated production browser smoke | Evidence: tests/test_frontend_contract.py and Issue #206 runtime evidence | Status: CONCERNS
- NFR-002 | Area: SECURITY | Target: fixed two-service control allowlist with no arbitrary systemd/service/path input | Validation: agent/API/auth regression tests | Evidence: tests/test_worker_operator_control.py, tests/test_api_contract.py, tests/test_sea_speed_auth_v1.py | Status: PASS
- NFR-003 | Area: RELIABILITY | Target: independent Water/Road desired states survive exact update/rollback | Validation: updater/rollback/deploy tests | Evidence: Ubuntu transaction tests | Status: PASS
- NFR-004 | Area: AVAILABILITY | Target: Road clean preview remains independent of AI Worker start/stop | Validation: frontend lifecycle contract and runtime smoke | Evidence: frontend tests plus Issue #206 runtime evidence | Status: CONCERNS
- NFR-005 | Area: RELEASE_PROVENANCE | Target: mixed release remains exact-main, quality-gated, rollback-capable, separately production-authorized and correctly classified for required privileged bootstrap actions | Validation: PR/post-merge quality, production-learning correction and deployment manifests | Evidence: GitHub Actions plus Issue #206/runtime manifests | Status: CONCERNS
- NFR-006 | Area: SECURITY | Target: private Worker M2M remains exact telemetry/config allowlist and excludes browser control | Validation: nginx renderer and analytics-profile regressions | Evidence: tests/test_sea_speed_auth_v1.py and tests/test_analytics_profiles.py | Status: PASS

## Runtime feedback

- The canonical Water Operator already provides the target visual hierarchy and contextual Stream/Worker interaction.
- The pre-change Road page used a separate simplified layout, hid clean preview until manual start, and did not expose Road Worker control.
- Existing Road analytics and protected preview paths are retained; this feature changes presentation and bounded operator control rather than AI semantics.
- Exact-head CI exposed a stale blanket Road `/api/worker/control` prohibition in `tests/test_analytics_profiles.py`; the approved source scope was expanded from 20 to 21 paths solely to synchronize that historical regression with the already approved fixed `road1` browser-control surface while retaining private/protected-source checks.
- Production authorization for exact runtime release `fd449af7bdbd4036517f321b96de31fe206f623b` is durable with execution intent. Ubuntu action `1/2` completed successfully: exact source/runtime identity was accepted, Water desired state remained `stopped`, Road desired state remained `running`, Road runtime progression passed and protected configuration was reconciled.
- Runtime orchestrator run #115 / `32022719065` verified the exact authorization/quality/provenance gates. Its VPS contour failed closed before completed release activation with `ERROR privileged bundle source SHA does not match request` and `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES`.
- Historical least-privilege PR #202 established that the root-owned Auth privilege bundle is exact-source bound and requires one root bootstrap before Connector deployment when bundle source changes. PR #207 changed `scripts/operations/nginx_sea_speed_auth.py`, which is included in that bundle. Outcome #206 therefore requires VPS `ONE_COMMAND_FALLBACK`, not `CONNECTOR`; combined operator actions expected are `2`.
- This production-learning source correction changes only `spec.md`, `plan.md` and `tasks.md`. It does not mutate production, alter the Outcome Contract, change the authorized runtime target, or modify protected runtime/security semantics.
