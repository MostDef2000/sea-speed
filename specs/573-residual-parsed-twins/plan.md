# Plan — Issue #573 residual parsed-twin conversion

- Issue: #573
- Specification: specs/573-residual-parsed-twins/spec.md

## Architecture

Follow the #398 house model: RB (execute the real thing) > SS (structured
parse/scan) > SP (STATIC_POLICY pins kept verbatim with justification) >
NO-CHANGE (recorded rationale). The #573 surface is the convertible subset of
the #398 outside-D residual: raw source-text pins on refactor-prone STRUCTURED
sources (Python modules, compose.yml). Shell/systemd contracts, security
byte-bans, and executed-output pins are SP-terminal / NO-CHANGE per the #398
closure adjudication — out of scope here.

Implementation note (honest record): the code worker completed T-1..T-3 (the
three file conversions) and died mid-task on a subagent-provider quota limit
before the demo, trio, and mutation probes; the delivery orchestrator verified
the completed conversions (diff inspection + focused runs) and completed
T-4..T-5 plus the probes itself — the documented orchestrator-fallback
precedent from #398 waves 5–8.

## Conversion approach

- Python-source pins (water_recall, exact_artifact_convergence): parse once
  per test with `ast.parse(source, filename=...)`, walk the tree, assert on
  structure with messages that name the broken fact. Shared helpers
  (`_parse_module`, `_find_function_def`, `_parameter_facts`) live at module
  level in tests/test_water_recall_ubuntu_ipc.py; the convergence test keeps
  its ast walk inline (single use). Parameter facts map name → default
  expression (positional offset arithmetic handles posonly/args; kwonly via
  kw_defaults), so `diagnostics=None` pins check the DEFAULT, not the text.
- compose.yml pins (auth_v1): `yaml.safe_load` once, walk `services`; images
  checked per service (explicit non-latest tag required — the no-tag gap the
  raw ban missed); ports parsed with `rpartition(":")` so the
  `${AUTHENTIK_HTTP_PORT:-9000}` host-side default's colons don't break the
  container-port extraction; volumes checked on both source and target sides.
- Executed legs stay untouched: the convergence test's subprocess validator
  run (RB), the stage.sh `bash -n` syntax gate.

## Per-site mapping

| File | Site (retired pin) | Verdict | Twin / rationale |
|---|---|---|---|
| tests/test_water_recall_ubuntu_ipc.py | `def supervised_detect_vehicles(_model, frame, diagnostics=None):` | CONVERT | FunctionDef + parameter facts (names, order, None default) |
| tests/test_water_recall_ubuntu_ipc.py | `return _supervisor.detect(frame, diagnostics=diagnostics)` | CONVERT | single Return, Call on `_supervisor.detect`, args/keywords structure |
| tests/test_water_recall_ubuntu_ipc.py | `def detect(self, frame: np.ndarray, diagnostics=None)` | CONVERT | method def in BoundedYoloSupervisor + facts + KEPT `np.ndarray` annotation pin |
| tests/test_water_recall_ubuntu_ipc.py | `detections, diagnostic_records = self._roundtrip(frame, timeout_sec)` | CONVERT | tuple-target Assign with exact names + Call args |
| tests/test_water_recall_ubuntu_ipc.py | `diagnostics.extend(diagnostic_records)` | CONVERT | Call on `diagnostics.extend` with the pinned name arg |
| tests/test_water_recall_ubuntu_ipc.py | `payload.get("diagnostics", [])` | CONVERT | Call on `payload.get`, Constant "diagnostics", empty List default |
| tests/test_water_recall_ubuntu_ipc.py | `4 * 1024 * 1024` | CONVERT | exact BinOp structure via ast.dump comparison |
| tests/test_water_recall_ubuntu_ipc.py | `child_source.count("model.track(") == 1` | CONVERT (stronger) | exactly one `.track(...)` attribute Call in the child AST, ANY receiver (peer-review fix: the receiver-name constraint let `self.model.track(` dodge the count) |
| tests/test_water_recall_ubuntu_ipc.py | `"detections": detections` / `"diagnostics": diagnostics` | CONVERT | one Dict literal carrying both keys side by side (Name values) |
| tests/test_water_recall_ubuntu_ipc.py | assertNotIn HLS_URL / SEA_SPEED_API_TOKEN / SEA_SPEED_API_URL | SP-KEEP | secret/media env-name byte-bans: absence ANYWHERE incl. comments IS the contract; ast.parse drops comments → parsed-absence weaker |
| tests/test_water_recall_ubuntu_ipc.py | `diagnostics=None` (backward-compat pin) | CONVERT (stronger) | EVERY `diagnostics` parameter defaults to None; exact set {detect, supervised_detect_vehicles} |
| tests/test_water_recall_ubuntu_ipc.py | `worker.detect_vehicles = supervised_detect_vehicles` | CONVERT | module-level Assign, Attribute target worker.detect_vehicles, Name value |
| tests/quality/test_exact_artifact_convergence.py | 2 name pins on validator source (L77–78) | CONVERT (stronger) | top-level FunctionDef names + main() invokes validate_vps_module_convergence exactly once; executed validator run stays RB |
| tests/test_sea_speed_auth_v1.py | compose image count (2× goauthentik) + postgres image | CONVERT | parsed per-service image map |
| tests/test_sea_speed_auth_v1.py | `"127.0.0.1:${AUTHENTIK_HTTP_PORT:-9000}:9000"` pin | CONVERT | parsed published-ports tuple check (env-tunable host side preserved) |
| tests/test_sea_speed_auth_v1.py | assertNotIn /var/run/docker.sock | CONVERT (stronger) + retained raw catch-all | no volume part on either side matches in ANY service; the raw byte-ban stays as the global net for non-volume locations (peer-review fix: environment/build args) |
| tests/test_sea_speed_auth_v1.py | regex bans `9000:9000` / `5432:5432` unbound publish | CONVERT (stronger) | EVERY published port must bind 127.0.0.1 (superset of the two named ports) |
| tests/test_sea_speed_auth_v1.py | assertNotIn `:latest` | CONVERT (stronger) + retained raw catch-all | every image carries an explicit tag whose text bans the `latest` SUBSTRING (no-tag defaults to latest; `${X:-latest}` env-defaults caught — peer-review fix); the raw byte-ban stays as the global net |
| tests/test_sea_speed_auth_v1.py | env.example empty-value secret pins | SP-KEEP | dotenv byte contract: keys present with EMPTY values; parsed-absence N/A for prose/dotenv |
| tests/test_sea_speed_auth_v1.py | stage.sh byte pins | SP-KEEP + annotation | shell deploy script: byte-identity IS the contract, any change must fail review |

## Decisions

- **Parsed twins, not assertion churn**: every converted site keeps its test
  method and its contract; only the pin mechanism changes (raw substring →
  structural check). Where the parsed form is strictly stronger, the upgrade
  is recorded at the site (every-`diagnostics`-defaults-None; main() invokes
  the convergence check exactly once; every published port loopback-bound;
  explicit non-latest tag per image).
- **SP where byte-presence IS the contract**: child-source secret/media
  env-name bans (ast.parse drops comments), env.example empty-value dotenv
  pins, stage.sh shell-contract pins — kept verbatim with STATIC_POLICY
  annotations, per the wave-7/8 canon that parsed-absence is weaker for these.
- **Shared ast helpers at module level** in tests/test_water_recall_ubuntu_ipc.py
  (`_parse_module`, `_find_function_def`, `_parameter_facts`) — the house
  pattern from the converted worker-module tests; the demo imports them for
  real (no mocking).
- **Validator untouched**: a single `573-*` spec dir has no prefix collision
  (validate_prefix_uniqueness skips prefixes with <2 dirs) — no grandfather
  line, no scripts/ci changes.

## Affected contours

- Tests only: tests/test_water_recall_ubuntu_ipc.py, tests/quality/test_exact_artifact_convergence.py,
  tests/test_sea_speed_auth_v1.py (compose subset + annotations), the new
  demo, this trio.
- Read-only inputs: worker/ubuntu_worker_entrypoint.py,
  worker/ubuntu_ai_inference_worker.py, deploy/** compose.yml, scripts/quality/validate_exact_artifacts.py,
  .github/** — parsed/executed at test time, never modified.

## Validation

- Focused run over the three converted files + demo: 31 passed + 10 subtests
  (orchestrator-observed).
- Full battery: recorded in the delivery record (expected 1232/2/306).
- Mutation probes on tmp copies (orchestrator): recorded in the delivery
  record — semantic mutations RED, harmless reformats green.
- ruff (CI config, repo-wide) clean; validate_sdd plain + --event green;
  validate_change_contract --event green before push.

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only; runtime acceptance =
  exact-head CI green on the merge PR.
- RF-002: the converted tests stay sub-second (focused run <1s); no new
  dependencies (ast stdlib; PyYAML already in the CI test env).

## Out of scope (adjudicated in the #398 closure, unchanged)

- Shell/systemd/installer byte contracts (deploy_authorized, zerotier_startup,
  control_token_separation, rollback, origin_health, blueprint_reconcile,
  watchdog unit/installer, auth_v1 stage.sh): byte-identity IS the contract.
- Security byte-bans (compatibility printenv/cat .env/echo $…TOKEN;
  outbox_delivery fail-closed lists; the child-source env-name bans kept here).
- Executed-output pins (watchdog `run_once` majority, compatibility
  `result[...]` pins) — already behavioral, heuristic false positives.
