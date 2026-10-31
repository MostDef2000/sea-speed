# Spec: #573 — residual parsed-twin conversion (follow-up from the #398 inventory)

- Issue: #573
- Specification: specs/573-residual-parsed-twins/spec.md
- Authorization: the #573 scope presented in chat (three files, tests-only,
  #398 house rules) and approved by the owner phrase `commit approved`
  2026-10-31; base dfbe094 (the #398 wave-8 merge).

## Product outcome

The genuinely-convertible residual from the #398 outside-D inventory
(specs/398-wave8/plan.md) stops pinning raw source text and starts reading
PARSED structure:

- tests/test_water_recall_ubuntu_ipc.py — the raw `read_text()` + `assertIn`
  pins on the worker Python sources (ubuntu_worker_entrypoint.py,
  ubuntu_ai_inference_worker.py) become ast.parse structural twins: function
  existence with exact parameter names/kinds/defaults, return/call structure,
  assignment targets, the exact `4 * 1024 * 1024` arithmetic ceiling, the
  single `model.track(...)` inference pass, and the side-by-side
  detections/diagnostics response payload. Same-or-stronger upgrades: the
  retired `diagnostics=None` substring pin now requires EVERY `diagnostics`
  parameter in the entrypoint to default to None (a comment or call site could
  satisfy the old substring); the `frame: np.ndarray` annotation pin is kept.
- tests/quality/test_exact_artifact_convergence.py — the two validator-source
  name pins become ast.parse twins (both helpers defined at top level AND
  `main()` invoking `validate_vps_module_convergence` exactly once); the
  executed validator run stays the RB leg of the same test.
- tests/test_sea_speed_auth_v1.py — the compose.yml subset becomes
  yaml.safe_load parsed twins: image pinning (2× goauthentik server, postgres),
  every published port explicitly loopback-bound (parsed superset of the
  retired `9000:9000`/`5432:5432` regex bans), no docker.sock mount on either
  side of any volume (parsed superset of the substring ban), and the
  same-or-stronger `:latest` upgrade: every service image must carry an
  explicit non-latest tag (an image with NO tag defaults to latest at pull
  time, which the retired byte-ban missed).

Pins whose textual presence IS the contract stay verbatim SP with in-code
rationale: the child-source secret/media env-name byte-bans (ast.parse drops
comments — parsed-absence would be weaker), the env.example empty-value dotenv
pins, and the stage.sh shell-contract byte pins.

## User scenarios

- SC-1: a developer refactors ubuntu_worker_entrypoint.py (adds comments,
  reindents, renames an unrelated local) — the IPC contract tests stay green;
  when they actually change the diagnostics sink signature, the tests fail
  with a message naming the broken structural fact.
- SC-2: an operator edits the auth compose.yml — bumping an image tag, dropping
  a tag (silently defaulting to latest), publishing a port without a loopback
  bind, or mounting the docker socket each fail the pinned test with the
  offending service named.
- SC-3: the exact-artifact validator's wiring (helpers defined, main() calling
  the convergence check) is verified structurally, so a rename that breaks the
  wiring fails the test even when the executed-validator leg happens to pass.

## Acceptance criteria

- AC-001: all three files adjudicated per-site in specs/573-residual-parsed-twins/plan.md
  (converted / SP-kept with rationale), focused runs green.
- AC-002 battery identity vs baseline 1231/2/306 recorded in tasks.md with the
  per-site twin mapping and the accounted delta (+1 demo method).
- AC-003 the SP-terminal categories (shell/systemd contracts, security
  byte-bans, executed-output false positives) recorded as out-of-scope with
  the one-line why, matching the #398 closure adjudication.

## Requirements

- R-1: tests/test_water_recall_ubuntu_ipc.py converts every raw Python-source
  pin to an ast.parse structural twin (function existence with exact
  parameter names/order/defaults, return/call structure, assignment targets,
  the exact `4 * 1024 * 1024` BinOp, exactly one `model.track(...)` Call, the
  side-by-side response Dict) with meaningful AssertionErrors; the
  backward-compat twin is STRONGER than the retired substring (EVERY
  `diagnostics` parameter defaults to None; exact function set; single
  rebind); the child-source secret/media env-name byte-bans stay verbatim
  with a STATIC_POLICY annotation (ast.parse drops comments — parsed-absence
  would be weaker); test method count unchanged.
- R-2: tests/quality/test_exact_artifact_convergence.py converts the two
  validator-source name pins to ast.parse twins (top-level FunctionDef names;
  `main()` invokes `validate_vps_module_convergence` exactly once) while the
  executed validator subprocess run stays untouched as the RB leg; the
  markdown convergence pins are not touched.
- R-3: tests/test_sea_speed_auth_v1.py converts the compose.yml subset to
  yaml.safe_load twins (per-service images with explicit non-latest tags —
  closing the no-tag-defaults-to-latest gap the raw ban missed; every
  published port explicitly loopback-bound; the env-tunable loopback 9000
  mapping pinned; no docker.sock on either volume side in any service) and
  keeps the env.example dotenv pins and the stage.sh shell-contract pins
  verbatim with STATIC_POLICY annotations; renderer/doc sections and all
  other tests untouched.
- R-4: tests/test_573_demo.py proves the conversion two-directionally on
  in-memory fixtures using the REAL helpers from the converted module (no
  mocking): reformat-equivalence (twin green, verbatim retired raw pin
  false-fails) and teeth (signature mutation → twin RED).

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only (CONTROL_PLANE); no
  deploy and no production artifact changes. Runtime acceptance = exact-head
  CI green on the merge PR (the battery, including the demo, runs in CI;
  PyYAML is already available in the CI test env).
- RF-002: post-conversion focused run over the three files + demo: 31 passed
  + 10 subtests (30 + 1 demo); the battery delta is +1 (demo only) — all
  three converted files keep their test method counts (conversion in place);
  every delta is recorded in the tasks.md ledger.

## NFRs

- Tests-only: no product, deploy, workflow, or validator file changes.
- No new dependencies (ast is stdlib; PyYAML already used by wave-5+ files).
- Wall time bounded: the converted tests stay sub-second (focused run
  observed 30 passed + 10 subtests + 1 demo in <1s).
