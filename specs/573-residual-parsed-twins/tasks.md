# Tasks — Issue #573 residual parsed-twin conversion

- Issue: #573
- Specification: specs/573-residual-parsed-twins/spec.md

## Delivery tasks

- T-1: tests/test_water_recall_ubuntu_ipc.py — all raw Python-source pins
  converted to ast.parse structural twins via shared helpers
  (`_parse_module`, `_find_function_def`, `_parameter_facts`): wrapper
  signature (names/order/None default), single Return with the pinned
  `_supervisor.detect` call structure, `detect` method in BoundedYoloSupervisor
  with the KEPT `np.ndarray` annotation, tuple-target `_roundtrip` assign,
  `diagnostics.extend`, `payload.get("diagnostics", [])`, exact
  `4 * 1024 * 1024` BinOp, exactly one `model.track(...)` Call, the
  side-by-side detections/diagnostics response Dict, and the STRONGER
  backward-compat twin (EVERY `diagnostics` parameter defaults to None; exact
  set {detect, supervised_detect_vehicles}; single worker.detect_vehicles
  rebind). SP-KEEP with STATIC_POLICY annotation: child-source
  HLS_URL/SEA_SPEED_API_TOKEN/SEA_SPEED_API_URL byte-bans (comments included —
  ast.parse drops comments). 4 test methods, 0 count delta. DONE (focused
  green).
- T-2: tests/quality/test_exact_artifact_convergence.py — the two
  validator-source name pins converted to ast.parse twins (top-level
  FunctionDef names; STRONGER: main() must invoke
  validate_vps_module_convergence exactly once); the executed validator
  subprocess run untouched (RB leg). DONE (focused green).
- T-3: tests/test_sea_speed_auth_v1.py — compose.yml subset converted to
  yaml.safe_load twins (per-service images with explicit non-latest tags —
  same-or-stronger upgrade over the `:latest` byte-ban; every published port
  loopback-bound — superset of the 9000/5432 regex bans; the env-tunable
  loopback 9000 mapping pinned as a tuple; no docker.sock on either volume
  side in any service). SP-KEEP with annotations: env.example empty-value
  dotenv pins; stage.sh shell-contract byte pins. Renderer/doc sections and
  all other tests untouched. DONE (focused green).
- T-4: tests/test_573_demo.py — one-test two-direction demo on in-memory
  fixtures using the REAL helpers from tests/test_water_recall_ubuntu_ipc.py:
  Direction A reformat-equivalence (comment + whitespace drift → twin green,
  verbatim retired raw pin false-fails — demo-twin-копия, documented pattern),
  Direction B teeth (diagnostics=None removed from the signature → twin RED).
  DONE (1 passed).
- T-5: specs/573-residual-parsed-twins/ trio (this spec/plan/tasks) with the
  per-site mapping table and the SP-terminal out-of-scope record. DONE.

## Battery identity

Baseline on base dfbe094: 1231 passed / 2 skipped / 306 subtests
(orchestrator-observed). After #573: expected 1232 / 2 / 306 (+1 demo method;
all three converted files at 0 count delta — conversion in place).
Observed: recorded by the orchestrator in the delivery record.

## Completion gate

- Focused `python3 -m pytest -p no:cacheprovider
  --basetemp=/tmp/opencode/573/pytest-tmp tests/test_water_recall_ubuntu_ipc.py
  tests/quality/test_exact_artifact_convergence.py tests/test_sea_speed_auth_v1.py
  tests/test_573_demo.py -q`: OBSERVED 31 passed + 10 subtests (30 across the
  three converted files + 1 demo).
- Full battery `python3 -m pytest -p no:cacheprovider
  --basetemp=/tmp/opencode/573/pytest-tmp tests/ -q`: recorded in the
  delivery record (base 1231 passed / 2 skipped / 306 subtests on dfbe094,
  orchestrator-provided baseline; identity 1231 + 1 demo method = 1232;
  subtests unchanged).

## Implementation record (honesty)

T-1..T-3 authored by the code worker (profile-worker-code), which completed
the three file conversions and died mid-task on a subagent-provider quota
limit before T-4/T-5/probes; the delivery orchestrator verified the completed
conversions (full diff inspection + focused runs: 30 passed / 10 subtests
across the three files, before the demo landed) and completed T-4/T-5 plus
the mutation probes itself (documented orchestrator-fallback precedent from
#398 waves 5–8).

Peer review (independent reviewer, read-only): REQUEST_CHANGES with two
BLOCKERs, both verified by the orchestrator against the code and FIXED:

- the `model.track(` twin required receiver `Name(id="model")`, so a
  regression via `self.model.track(` / `_model.track(` stayed green while the
  retired raw count went red — fixed: the twin now counts ANY `.track(...)`
  attribute call (strictly stronger); probes (1b)/(1c) RED.
- the `:latest` twin compared the tag to the exact string `"latest"`, so an
  env-default image `${AUTHENTIK_TAG:-latest}` stayed green while the retired
  raw ban went red — fixed: the tag check bans the `latest` SUBSTRING and the
  raw `:latest` / `/var/run/docker.sock` byte-bans are RETAINED as global
  catch-alls alongside the parsed walks; probes (2b)/(6b) RED, regression
  guards (5r) no-tag RED and (8r) reformat GREEN unchanged.

Two CONCERNs addressed: the docker.sock global catch-all (above) and the demo
header now states explicitly that RED-sensitivity of the wired test methods is
proven by the recorded mutation probes. Post-fix focused run: 31 passed +
10 subtests. Peer-review status: fixes verified, ready for merge.
