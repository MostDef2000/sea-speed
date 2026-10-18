"""RBAC matrix tests for issue #530 — server-side role authorization.

Covers plan TEST-001 (19 browser mutations x viewer/operator/admin with the
REAL guards), TEST-002 (resolver semantics + env-list parsing), TEST-003
(identity-first ordering) and TEST-008 (mutation-attempt audit records).

House constraints (see tests/test_auth_session_identity.py and
tests/test_api_contract.py): ``api/app/config.py`` import creates /opt
directories and FAILS in the sandbox, so nothing here imports the package.
The identity policy (``require_operator_identity``/``resolve_role``/
``require_role``) is AST-extracted from ``identity.py`` verbatim — the real
guards run. The 19 mutation handlers are AST-extracted from ``main.py``
(decorators stripped) and executed against recording stubs for every
side-effect collaborator (storage writes, process control, outbound worker
calls), so every denial can assert that ZERO effects were recorded.
"""

from __future__ import annotations

import ast
import copy
import hmac
import logging
import os
import re
import threading
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
MAIN_SOURCE = ROOT / "api/app/main.py"
IDENTITY_SOURCE = ROOT / "api/app/identity.py"
ANALYTICS_SOURCE = ROOT / "api/app/analytics.py"
CONFIG_SOURCE = ROOT / "api/app/config.py"

EDGE_AUTH_ENV = "SEA_SPEED_EDGE_AUTH_SECRET"
STRICT_EDGE_FIXTURE = "edge-fixture-530"
RBAC_TEST_LOGGER_NAME = "sea_speed_rbac_under_test"

SESSION_ID = "abcdef012345"  # matches config's CAMERA_PREVIEW_SESSION_RE

# Recognized authentik group names (deploy/vps/authentik/blueprints/
# sea-speed-auth-v1.yaml, mirrored by identity.py).
GROUP_OWNER = "Sea Speed Owner"
GROUP_ADMIN = "Sea Speed Admin"
GROUP_OPERATOR = "Sea Speed Operator"
GROUP_VIEWER = "Sea Speed Viewer"

ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _parse(source: Path) -> ast.Module:
    return ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))


def _select(
    tree: ast.Module,
    function_names: set[str],
    assign_names: set[str],
    *,
    required: bool = True,
) -> list[ast.stmt]:
    """Pick module-level defs/assigns in source order (import-free load)."""
    body: list[ast.stmt] = []
    found_functions: set[str] = set()
    found_assigns: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in function_names:
            cloned = copy.deepcopy(node)
            cloned.decorator_list = []
            body.append(cloned)
            found_functions.add(node.name)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in assign_names
        ):
            body.append(copy.deepcopy(node))
            found_assigns.add(node.targets[0].id)
    if required:
        missing = (function_names - found_functions) | (assign_names - found_assigns)
        if missing:
            raise AssertionError(f"missing API symbols: {sorted(missing)}")
    return body


def load_identity_policy(
    admin_users: frozenset = frozenset(),
    operator_users: frozenset = frozenset(),
    edge_secret: str = STRICT_EDGE_FIXTURE,
) -> dict[str, Any]:
    """Exec the REAL #530 policy from identity.py in a stub namespace.

    Fresh per call, so the transitional latch and the captured logger are
    order-independent (same contract as load_require_operator_identity in
    tests/test_auth_session_identity.py).
    """
    functions = {
        "require_operator_identity",
        "resolve_role",
        "require_role",
        "_escape_audit_text",
    }
    assigns = {
        "_LOGGER",
        "_EDGE_AUTH_TRANSITIONAL_WARNING_EMITTED",
        "AUTHENTIK_GROUP_OWNER",
        "AUTHENTIK_GROUP_ADMIN",
        "AUTHENTIK_GROUP_OPERATOR",
        "AUTHENTIK_GROUP_VIEWER",
        "_GROUP_ROLES",
        "_ROLE_RANK",
        "_AUDIT_CONTROL_CHARS_RE",
    }
    body = _select(_parse(IDENTITY_SOURCE), functions, assigns)
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "__name__": RBAC_TEST_LOGGER_NAME,
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "EDGE_AUTH_SECRET": edge_secret,
        "ADMIN_USERS": admin_users,
        "OPERATOR_USERS": operator_users,
        "HTTPException": HTTPExceptionStub,
        "hmac": hmac,
        "logging": logging,
        "re": re,
    }
    exec(compile(module, str(IDENTITY_SOURCE), "exec"), namespace)
    return namespace


# ---------------------------------------------------------------------------
# Structurally valid payloads (plan: "denial tests must use structurally
# valid inputs" so framework validation can never mask a guard).
# ---------------------------------------------------------------------------

def _norm_point(x: float, y: float) -> dict[str, float]:
    return {"x_norm": x, "y_norm": y}


ROI_PAYLOAD = {
    "enabled": True,
    "polygon_norm": [_norm_point(0.1, 0.2), _norm_point(0.5, 0.2), _norm_point(0.5, 0.8)],
}
SPEED_CONFIG_PAYLOAD = {"enabled": True, "kmh_per_px_s": 1.5}
SPEED_LINES_PAYLOAD = {
    "enabled": True,
    "distance_m": 57.0,
    "line_a_norm": [_norm_point(0.1, 0.1), _norm_point(0.9, 0.1)],
    "line_b_norm": [_norm_point(0.1, 0.9), _norm_point(0.9, 0.9)],
}
CROSSING_LINE_PAYLOAD = {
    "enabled": True,
    "line_norm": [_norm_point(0.05, 0.5), _norm_point(0.95, 0.5)],
}
OBJECT_PATCH_PAYLOAD = {"status": "reviewed", "comment": "rbac-530"}


# handler -> (method, path, minimum, invoke, effect_keys)
# effect_keys name the recording buckets that a successful call must fill.
MUTATION_MATRIX: dict[str, tuple[str, str, str, str, tuple[str, ...]]] = {
    "patch_cam1_object": ("PATCH", "/api/cam1/objects/{object_id}", "operator", "objects", ("objects",)),
    "patch_object": ("PATCH", "/api/objects/{object_id}", "operator", "objects", ("objects",)),
    "delete_cam1_object": ("DELETE", "/api/cam1/objects/{object_id}", "admin", "objects", ("objects",)),
    "delete_object": ("DELETE", "/api/objects/{object_id}", "admin", "objects", ("objects",)),
    "commit_camera_snapshot": ("POST", "/api/cameras/{camera_id}/snapshot/commit", "operator", "preview", ("preview",)),
    "start_camera_preview": ("POST", "/api/cameras/{camera_id}/preview/start", "operator", "preview", ("preview",)),
    "stop_camera_preview": ("POST", "/api/cameras/preview/stop", "operator", "preview", ("preview",)),
    "post_cam1_roi": ("POST", "/api/cam1/roi", "admin", "calibration", ("writes",)),
    "post_cam1_speed_config": ("POST", "/api/cam1/speed-config", "admin", "calibration", ("writes",)),
    "post_cam1_speed_lines": ("POST", "/api/cam1/speed-lines", "admin", "calibration", ("writes",)),
    "post_cam1_crossing_line": ("POST", "/api/cam1/crossing-line", "admin", "crossing", ("writes",)),
    "post_analytics_roi": ("POST", "/api/analytics/{camera_id}/roi", "admin", "calibration", ("writes",)),
    "post_analytics_speed_config": ("POST", "/api/analytics/{camera_id}/speed-config", "admin", "calibration", ("writes",)),
    "post_analytics_speed_lines": ("POST", "/api/analytics/{camera_id}/speed-lines", "admin", "calibration", ("writes",)),
    "api_post_crossing_line": ("POST", "/api/analytics/{camera_id}/crossing-line", "admin", "crossing", ("writes",)),
    "start_worker_control": ("POST", "/api/worker/control/start", "admin", "worker", ("worker",)),
    "stop_worker_control": ("POST", "/api/worker/control/stop", "admin", "worker", ("worker",)),
    "start_road_worker_control": ("POST", "/api/worker/control/road1/start", "admin", "worker", ("worker",)),
    "stop_road_worker_control": ("POST", "/api/worker/control/road1/stop", "admin", "worker", ("worker",)),
}

# Role fixtures: strict edge mode is satisfied by every case; only the
# resolved role varies (spec route table "Minimum role" column).
ROLE_IDENTITIES = {
    "viewer": ("viewer@example.test", GROUP_VIEWER),
    "operator": ("operator@example.test", GROUP_OPERATOR),
    "admin": ("admin@example.test", GROUP_ADMIN),
}


def _headers_for(role: str) -> dict[str, Optional[str]]:
    username, groups = ROLE_IDENTITIES[role]
    return {
        "x_authentik_username": username,
        "x_sea_speed_edge_auth": STRICT_EDGE_FIXTURE,
        "x_authentik_groups": groups,
    }


def _invoke_handler(api_ns: dict[str, Any], handler: str, invoke: str, headers: dict[str, Optional[str]]):
    call = api_ns[handler]
    if invoke == "objects" and handler.startswith("patch"):
        return call("obj-530", dict(OBJECT_PATCH_PAYLOAD), **headers)
    if invoke == "objects":
        return call("obj-530", **headers)
    if invoke == "preview":
        if handler == "commit_camera_snapshot":
            return call("cam1", SESSION_ID, **headers)
        if handler == "start_camera_preview":
            return call("cam1", **headers)
        return call(**headers)
    if invoke == "calibration":
        if handler == "post_cam1_roi":
            return call(dict(ROI_PAYLOAD), **headers)
        if handler == "post_cam1_speed_config":
            return call(dict(SPEED_CONFIG_PAYLOAD), **headers)
        if handler == "post_cam1_speed_lines":
            return call(dict(SPEED_LINES_PAYLOAD), **headers)
        if handler == "post_analytics_roi":
            return call("cam1", dict(ROI_PAYLOAD), **headers)
        if handler == "post_analytics_speed_config":
            return call("cam1", dict(SPEED_CONFIG_PAYLOAD), **headers)
        return call("cam1", dict(SPEED_LINES_PAYLOAD), **headers)
    if invoke == "crossing":
        if handler == "post_cam1_crossing_line":
            return call(dict(CROSSING_LINE_PAYLOAD), **headers)
        return call("cam1", dict(CROSSING_LINE_PAYLOAD), **headers)
    return call(**headers)  # worker control


class ApiHarness(unittest.TestCase):
    """Shared builder: real guards + recording side-effect collaborators."""

    def build_api(self, admin_users=frozenset(), operator_users=frozenset(), edge_secret=STRICT_EDGE_FIXTURE):
        policy_ns = load_identity_policy(
            admin_users=frozenset(admin_users),
            operator_users=frozenset(operator_users),
            edge_secret=edge_secret,
        )
        effects: dict[str, list] = {
            "objects": [],
            "preview": [],
            "writes": [],
            "worker": [],
            "crossing": [],
            "identity_reads": [],
        }

        def patch_object_record(object_id, payload, camera_id=None):
            effects["objects"].append(("patch", object_id, camera_id, payload))
            return {"ok": True, "object": {"object_id": object_id}}

        def delete_object_record(object_id, camera_id=None):
            effects["objects"].append(("delete", object_id, camera_id))
            return {"ok": True, "object_id": object_id, "deleted_at": "2026-10-18T00:00:00+00:00"}

        def call_worker_control(method, path):
            effects["worker"].append((method, path))
            return {"ok": True, "protocol": "sea_speed_worker_control_v1", "active": True}

        def load_camera_preview_catalog():
            effects["identity_reads"].append("catalog")
            return [{"camera_id": "cam1", "label": "Cam 1"}]

        def active_camera_preview_locked():
            return {"camera_id": "cam1", "session_id": SESSION_ID, "pid": 4242}

        def commit_camera_snapshot_locked(state):
            effects["preview"].append(("commit", state["camera_id"]))
            return {"path": f"/media/camera-preview/{state['session_id']}/last-good.jpg", "updated_at": "x"}

        def start_camera_preview_locked(camera):
            effects["preview"].append(("start", camera["camera_id"]))
            return {"camera_id": camera["camera_id"], "session_id": SESSION_ID, "pid": 4242}

        def terminate_camera_preview_locked():
            effects["preview"].append(("terminate", None))
            return "cam1"

        def camera_preview_public_state(state):
            return state

        def analytics_identity(camera_id):
            effects["identity_reads"].append(("analytics_identity", camera_id))
            if camera_id not in ("cam1", "road1"):
                raise HTTPExceptionStub(404, "Unknown analytics camera")
            return {"analytics_profile": "water-v1", "domain": "water"}

        def analytics_data_file(camera_id, kind):
            return Path(f"/sea-speed-test-data/{camera_id}_{kind}.json")

        def write_json_file(path, data):
            effects["writes"].append((path, data))

        def read_json_file(path, default):
            return copy.deepcopy(default)

        def now_iso():
            return "2026-10-18T00:00:00+00:00"

        def subprocess_tripwire(*_args, **_kwargs):
            raise AssertionError("subprocess must never be reached from RBAC handlers")

        api_namespace: dict[str, Any] = {
            "Any": Any,
            "Dict": Dict,
            "List": List,
            "Optional": Optional,
            "Path": Path,
            "HTTPException": HTTPExceptionStub,
            "Header": lambda default=None: default,
            "re": re,
            "json": __import__("json"),
            "store": type("store", (), {"JSON_READ_ERRORS": (OSError, ValueError)})(),
            "CAMERA_PREVIEW_LOCK": threading.Lock(),
            "CAMERA_PREVIEW_SESSION_RE": re.compile(r"^[0-9a-f]{12}$"),
            "DEFAULT_ROI_REF_W": 1920,
            "DEFAULT_ROI_REF_H": 1080,
            "LEGACY_ROI_W": 704,
            "LEGACY_ROI_H": 576,
            "patch_object_record": patch_object_record,
            "delete_object_record": delete_object_record,
            "call_worker_control": call_worker_control,
            "load_camera_preview_catalog": load_camera_preview_catalog,
            "active_camera_preview_locked": active_camera_preview_locked,
            "commit_camera_snapshot_locked": commit_camera_snapshot_locked,
            "start_camera_preview_locked": start_camera_preview_locked,
            "terminate_camera_preview_locked": terminate_camera_preview_locked,
            "camera_preview_public_state": camera_preview_public_state,
            "analytics_identity": analytics_identity,
            "analytics_data_file": analytics_data_file,
            "write_json_file": write_json_file,
            "read_json_file": read_json_file,
            "now_iso": now_iso,
            "subprocess": subprocess_tripwire,
        }
        # The REAL #530 guards execute inside the handler namespace.
        for name in ("require_operator_identity", "resolve_role", "require_role"):
            api_namespace[name] = policy_ns[name]

        main_body = _select(_parse(MAIN_SOURCE), set(MUTATION_MATRIX), set(), required=False)
        missing = set(MUTATION_MATRIX) - {node.name for node in main_body}
        if missing:
            raise AssertionError(f"missing mutation handlers in main.py: {sorted(missing)}")
        analytics_functions = {
            "clean_points_list",
            "_is_normalized_point",
            "_clean_norm_points",
            "_infer_legacy_ref_w_h",
            "_normalize_from_absolute",
            "_denormalize_to_absolute",
            "_normalize_legacy_polygon",
            "post_analytics_crossing_line",
        }
        analytics_body = _select(_parse(ANALYTICS_SOURCE), analytics_functions, set())
        module = ast.Module(body=main_body + analytics_body, type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(MAIN_SOURCE), "exec"), api_namespace)
        return policy_ns, api_namespace, effects

    def assert_no_effects(self, effects: dict[str, list]) -> None:
        """AC-003: a denial must not reach ANY side-effect collaborator."""
        for bucket in ("objects", "preview", "writes", "worker", "crossing"):
            self.assertEqual(effects[bucket], [], f"denied mutation recorded {bucket} effects")


class RbacMatrixTests(ApiHarness):
    """TEST-001: every route x every role against the real guards."""

    def test_all_mutations_matrix_three_roles(self) -> None:
        for handler, (method, path, minimum, invoke, effect_keys) in MUTATION_MATRIX.items():
            for role in ("viewer", "operator", "admin"):
                with self.subTest(route=f"{method} {path}", role=role):
                    _policy, api_ns, effects = self.build_api()
                    headers = _headers_for(role)
                    allowed = ROLE_RANK[role] >= ROLE_RANK[minimum]
                    if allowed:
                        result = _invoke_handler(api_ns, handler, invoke, headers)
                        self.assertIsInstance(result, dict)
                        self.assertTrue(result.get("ok"), f"{handler} positive must return ok")
                        for bucket in effect_keys:
                            self.assertTrue(effects[bucket], f"{handler} positive must record {bucket} effect")
                        if bucket_worker := (invoke == "worker"):
                            self.assertEqual(effects["worker"][0][0], "POST")
                            self.assertEqual(result.get("requested_by"), headers["x_authentik_username"])
                        del bucket_worker
                    else:
                        with self.assertRaises(HTTPExceptionStub) as raised:
                            _invoke_handler(api_ns, handler, invoke, headers)
                        self.assertEqual(raised.exception.status_code, 403)
                        self.assertEqual(raised.exception.detail, "Forbidden")
                        self.assert_no_effects(effects)

    def test_guards_run_before_any_side_effect(self) -> None:
        # A viewer denial on commit_camera_snapshot must not even read the
        # catalog/lock collaborators (plan: guard first, before catalog access,
        # locks, validation helpers with side effects, persistence).
        _policy, api_ns, effects = self.build_api()
        with self.assertRaises(HTTPExceptionStub) as raised:
            api_ns["commit_camera_snapshot"]("cam1", SESSION_ID, **_headers_for("viewer"))
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(effects["identity_reads"], [])
        self.assert_no_effects(effects)

    def test_route_table_minima_match_spec(self) -> None:
        """Every spec route-table row is wired with require_role(minimum=...)."""
        tree = _parse(MAIN_SOURCE)
        for node in tree.body:
            if not (isinstance(node, ast.FunctionDef) and node.name in MUTATION_MATRIX):
                continue
            expected_minimum = MUTATION_MATRIX[node.name][2]
            guard = next(
                (
                    child
                    for child in ast.walk(node)
                    if isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "require_role"
                ),
                None,
            )
            self.assertIsNotNone(guard, f"{node.name} must call require_role")
            assert guard is not None
            keywords = {kw.arg: kw.value for kw in guard.keywords}
            self.assertIsInstance(keywords.get("minimum"), ast.Constant)
            self.assertEqual(keywords["minimum"].value, expected_minimum, node.name)
            self.assertIsInstance(keywords.get("action"), ast.Constant)
            self.assertEqual(keywords["action"].value, node.name)
            # guard must be the FIRST statement of the handler body
            # (bare call, or `username = require_role(...)` in worker handlers)
            first = node.body[0]
            guard_expr = first.value if isinstance(first, ast.Expr) else (
                first.value if isinstance(first, ast.Assign) else None
            )
            self.assertIs(guard_expr, guard, f"{node.name}: require_role must run first")

    def test_calibration_alias_forwards_headers_to_delegated_guard(self) -> None:
        # cam1 aliases delegate to the analytics handlers and must forward all
        # three identity/group header values explicitly (plan D-4).
        tree = _parse(MAIN_SOURCE)
        aliases = {
            "post_cam1_roi": "post_analytics_roi",
            "post_cam1_speed_config": "post_analytics_speed_config",
            "post_cam1_speed_lines": "post_analytics_speed_lines",
        }
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in aliases:
                delegated = next(
                    (
                        child
                        for child in ast.walk(node)
                        if isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Name)
                        and child.func.id == aliases[node.name]
                    ),
                    None,
                )
                self.assertIsNotNone(delegated, f"{node.name} must delegate to {aliases[node.name]}")
                assert delegated is not None
                forwarded = {arg.id for arg in delegated.args if isinstance(arg, ast.Name)}
                for header in ("x_authentik_username", "x_sea_speed_edge_auth", "x_authentik_groups"):
                    self.assertIn(header, forwarded, f"{node.name} must forward {header}")

    def test_crossing_line_alias_guards_http_handler_only(self) -> None:
        # post_cam1_crossing_line delegates to the UN-decorated analytics
        # helper (main.py:599-601); the HTTP handler itself carries the guard.
        _policy, api_ns, effects = self.build_api()
        with self.assertRaises(HTTPExceptionStub) as raised:
            api_ns["post_cam1_crossing_line"](dict(CROSSING_LINE_PAYLOAD), **_headers_for("operator"))
        self.assertEqual(raised.exception.status_code, 403)
        self.assert_no_effects(effects)
        result = api_ns["post_cam1_crossing_line"](dict(CROSSING_LINE_PAYLOAD), **_headers_for("admin"))
        self.assertTrue(result["ok"])
        self.assertTrue(effects["writes"], "crossing-line alias must persist through the delegated helper")
        self.assertEqual(effects["writes"][0][0], Path("/sea-speed-test-data/cam1_crossing_line.json"))


class ResolverSemanticsTests(ApiHarness):
    """TEST-002: env precedence + exact group parsing (spec R-2)."""

    def resolve(self, username, groups, admin=frozenset(), operator=frozenset()):
        return load_identity_policy(admin_users=admin, operator_users=operator)["resolve_role"](username, groups)

    def test_env_admin_list_wins(self) -> None:
        self.assertEqual(self.resolve("u1", None, admin=frozenset({"u1"})), "admin")
        self.assertEqual(self.resolve("u1", GROUP_VIEWER, admin=frozenset({"u1"})), "admin")

    def test_env_operator_override_beats_admin_group(self) -> None:
        # The env override tier is authoritative, not additive.
        self.assertEqual(self.resolve("u2", GROUP_ADMIN, operator=frozenset({"u2"})), "operator")
        self.assertEqual(self.resolve("u2", GROUP_OWNER, operator=frozenset({"u2"})), "operator")

    def test_both_env_lists_resolve_admin(self) -> None:
        self.assertEqual(self.resolve("u3", None, admin=frozenset({"u3"}), operator=frozenset({"u3"})), "admin")

    def test_absent_from_env_falls_through_to_groups(self) -> None:
        self.assertEqual(self.resolve("u4", GROUP_OPERATOR, admin=frozenset({"other"}), operator=frozenset({"other"})), "operator")

    def test_exact_case_sensitive_group_tokens(self) -> None:
        for group, expected in ((GROUP_OWNER, "admin"), (GROUP_ADMIN, "admin"), (GROUP_OPERATOR, "operator"), (GROUP_VIEWER, "viewer")):
            with self.subTest(group=group):
                self.assertEqual(self.resolve("u", group), expected)
        # case mismatch grants nothing
        self.assertEqual(self.resolve("u", "sea speed admin"), "viewer")
        self.assertEqual(self.resolve("u", "SEA SPEED OPERATOR"), "viewer")
        # near-miss whole-token mismatch grants nothing
        self.assertEqual(self.resolve("u", "Sea Speed Admins"), "viewer")
        self.assertEqual(self.resolve("u", "Speed Admin"), "viewer")

    def test_comma_only_split_with_trim(self) -> None:
        self.assertEqual(self.resolve("u", " Sea Speed Operator , junk "), "operator")
        self.assertEqual(self.resolve("u", "junk,,Sea Speed Admin,"), "admin")
        # space-delimited junk is ONE token, never split on spaces
        self.assertEqual(self.resolve("u", "Sea Speed Admin Sea Speed Operator"), "viewer")

    def test_multiple_roles_highest_wins(self) -> None:
        self.assertEqual(self.resolve("u", f"{GROUP_VIEWER},{GROUP_OPERATOR}"), "operator")
        self.assertEqual(self.resolve("u", f"{GROUP_OPERATOR},{GROUP_ADMIN}"), "admin")
        self.assertEqual(self.resolve("u", f"{GROUP_ADMIN},{GROUP_OWNER}"), "admin")

    def test_unknown_blank_absent_resolve_viewer(self) -> None:
        for groups in (None, "", "   ", "Unknown Group,Also Unknown"):
            with self.subTest(groups=groups):
                self.assertEqual(self.resolve("u", groups), "viewer")

    def test_env_list_parsing_whitespace_and_comma(self) -> None:
        # config._parse_user_set is the import-time env owner; extract it
        # without importing config (the /opt side effects).
        functions = {"_parse_user_set"}
        body = _select(_parse(CONFIG_SOURCE), functions, set())
        module = ast.Module(body=body, type_ignores=[])
        ast.fix_missing_locations(module)
        namespace: dict[str, Any] = {"os": os, "re": re}
        exec(compile(module, str(CONFIG_SOURCE), "exec"), namespace)
        parse_user_set = namespace["_parse_user_set"]
        cases = {
            "a,b": {"a", "b"},
            "a b": {"a", "b"},
            " a , b ,, c ": {"a", "b", "c"},
            "a,\tb\n c": {"a", "b", "c"},
            "": set(),
            "   ": set(),
            ",,,": set(),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                os.environ["SEA_SPEED_TEST_LIST_530"] = raw
                try:
                    self.assertEqual(set(parse_user_set("SEA_SPEED_TEST_LIST_530")), expected)
                finally:
                    del os.environ["SEA_SPEED_TEST_LIST_530"]
        self.assertEqual(set(parse_user_set("SEA_SPEED_TEST_LIST_530_MISSING")), set())


class IdentityFirstOrderingTests(ApiHarness):
    """TEST-003: identity verification precedes role resolution."""

    def test_privileged_identity_rejected_without_edge_secret(self) -> None:
        _policy, api_ns, effects = self.build_api()
        for edge in (None, "", "wrong", "ä- forged"):
            with self.subTest(edge=edge):
                with self.assertRaises(HTTPExceptionStub) as raised:
                    api_ns["delete_object"](
                        "obj-530",
                        x_authentik_username="admin@example.test",
                        x_sea_speed_edge_auth=edge,
                        x_authentik_groups=GROUP_ADMIN,
                    )
                self.assertEqual(raised.exception.status_code, 403)
                self.assert_no_effects(effects)

    def test_identity_failure_prevents_role_resolution(self) -> None:
        policy_ns = load_identity_policy()
        calls: list = []
        real_resolve = policy_ns["resolve_role"]

        def spy(username, groups):
            calls.append((username, groups))
            return real_resolve(username, groups)

        policy_ns["resolve_role"] = spy
        # require_role resolves resolve_role from the module globals at call
        # time, so the spy observes ordering inside the real guard.
        with self.assertRaises(HTTPExceptionStub) as raised:
            policy_ns["require_role"](
                "admin@example.test", "wrong-edge", GROUP_ADMIN, minimum="admin", action="x",
            )
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(calls, [], "identity failure must prevent role resolution")

    def test_valid_edge_blank_username_still_503(self) -> None:
        _policy, api_ns, effects = self.build_api()
        for username in (None, "", "   "):
            with self.subTest(username=username):
                with self.assertRaises(HTTPExceptionStub) as raised:
                    api_ns["start_worker_control"](
                        x_authentik_username=username,
                        x_sea_speed_edge_auth=STRICT_EDGE_FIXTURE,
                        x_authentik_groups=GROUP_ADMIN,
                    )
                self.assertEqual(raised.exception.status_code, 503)
                self.assertEqual(raised.exception.detail, "Trusted Authentik identity is unavailable")
                self.assert_no_effects(effects)

    def test_valid_identity_blank_groups_resolves_viewer_403(self) -> None:
        # Basic-auth renderer blanks identity fields; a verified identity with
        # blank groups and no env override is a role denial 403 (spec: do not
        # mislabel the 503 branch as role denial).
        _policy, api_ns, effects = self.build_api()
        for groups in (None, "", "   "):
            with self.subTest(groups=groups):
                with self.assertRaises(HTTPExceptionStub) as raised:
                    api_ns["patch_object"](
                        "obj-530",
                        dict(OBJECT_PATCH_PAYLOAD),
                        x_authentik_username="someone@example.test",
                        x_sea_speed_edge_auth=STRICT_EDGE_FIXTURE,
                        x_authentik_groups=groups,
                    )
                self.assertEqual(raised.exception.status_code, 403)
                self.assertEqual(raised.exception.detail, "Forbidden")
                self.assert_no_effects(effects)

    def test_unsupported_minimum_fails_closed(self) -> None:
        policy_ns = load_identity_policy()
        with self.assertRaises(HTTPExceptionStub) as raised:
            policy_ns["require_role"](
                "admin@example.test", STRICT_EDGE_FIXTURE, GROUP_ADMIN, minimum="viewer", action="x",
            )
        self.assertEqual(raised.exception.status_code, 500)
        with self.assertRaises(HTTPExceptionStub) as raised:
            policy_ns["require_role"](
                "admin@example.test", STRICT_EDGE_FIXTURE, GROUP_ADMIN, minimum="owner", action="x",
            )
        self.assertEqual(raised.exception.status_code, 500)

    def test_transitional_mode_preserved(self) -> None:
        # Edge secret unset: identity is accepted without edge verification
        # (existing #520 semantics); role enforcement still applies normally.
        policy_ns = load_identity_policy(edge_secret="")
        with self.assertLogs(RBAC_TEST_LOGGER_NAME, level="WARNING"):
            username = policy_ns["require_role"](
                "operator@example.test", None, GROUP_OPERATOR, minimum="operator", action="patch_object",
            )
        self.assertEqual(username, "operator@example.test")
        with self.assertRaises(HTTPExceptionStub) as raised:
            policy_ns["require_role"](
                "viewer@example.test", None, GROUP_VIEWER, minimum="operator", action="patch_object",
            )
        self.assertEqual(raised.exception.status_code, 403)


class AuditRecordTests(ApiHarness):
    """TEST-008: mutation-attempt audit records (spec R-5, AC-005)."""

    EDGE_SECRET_MARKER = "SECR[E]T-MARKER-530"

    def capture(self, func, *args, **kwargs):
        logger = logging.getLogger(RBAC_TEST_LOGGER_NAME)
        records: list[logging.LogRecord] = []

        class Collect(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = Collect(level=logging.INFO)
        previous_propagate = logger.propagate
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        try:
            outcome = func(*args, **kwargs)
        finally:
            logger.removeHandler(handler)
            logger.propagate = previous_propagate
        attempts = [r.getMessage() for r in records if "authorized mutation attempt" in r.getMessage()]
        return outcome, attempts, [r.getMessage() for r in records]

    def test_authorized_routes_record_attempt(self) -> None:
        authorized = {
            "patch_cam1_object": "operator",
            "patch_object": "operator",
            "commit_camera_snapshot": "operator",
            "start_camera_preview": "operator",
            "stop_camera_preview": "operator",
            "delete_cam1_object": "admin",
            "delete_object": "admin",
            "post_cam1_roi": "admin",
            "post_cam1_speed_config": "admin",
            "post_cam1_speed_lines": "admin",
            "post_cam1_crossing_line": "admin",
            "post_analytics_roi": "admin",
            "post_analytics_speed_config": "admin",
            "post_analytics_speed_lines": "admin",
            "api_post_crossing_line": "admin",
            "start_worker_control": "admin",
            "stop_worker_control": "admin",
            "start_road_worker_control": "admin",
            "stop_road_worker_control": "admin",
        }
        self.assertEqual(set(authorized), set(MUTATION_MATRIX))
        for handler_name, role in authorized.items():
            with self.subTest(handler=handler_name):
                _policy, api_ns, _effects = self.build_api()
                method = MUTATION_MATRIX[handler_name][3]
                headers = _headers_for(role)
                _result, attempts, _all = self.capture(
                    lambda: _invoke_handler(api_ns, handler_name, method, headers)
                )
                self.assertGreaterEqual(len(attempts), 1, "authorized attempt must record")
                message = attempts[0]
                self.assertIn(f"user={headers['x_authentik_username']}", message)
                self.assertIn(f"role={role}", message)
                self.assertIn(f"action={handler_name}", message)
                self.assertIn("attempt", message)

    def test_calibration_alias_records_attempt(self) -> None:
        # One calibration alias route emits two attempt records (outer alias +
        # delegated handler, plan D-4) — never counted as two mutations.
        _policy, api_ns, effects = self.build_api()
        headers = _headers_for("admin")
        _result, attempts, _all = self.capture(
            lambda: _invoke_handler(api_ns, "post_cam1_roi", "calibration", headers)
        )
        self.assertEqual(len(attempts), 2)
        self.assertIn("action=post_cam1_roi", attempts[0])
        self.assertIn("action=post_analytics_roi", attempts[1])
        self.assertEqual(len(effects["writes"]), 1, "two attempt records, one completed write")

    def test_denied_routes_record_no_attempt(self) -> None:
        _policy, api_ns, _effects = self.build_api()
        headers = _headers_for("viewer")
        with self.assertRaises(HTTPExceptionStub):
            self.capture(lambda: _invoke_handler(api_ns, "delete_object", "objects", headers))
        _policy, api_ns, _effects = self.build_api()
        headers = _headers_for("viewer")
        with self.assertRaises(HTTPExceptionStub) as raised:
            self.capture(
                lambda: _invoke_handler(api_ns, "patch_object", "objects", headers)
            )
        self.assertEqual(raised.exception.status_code, 403)
        # No attempt record was emitted before the denial was raised.
        _policy, api_ns, _effects = self.build_api()
        logger = logging.getLogger(RBAC_TEST_LOGGER_NAME)
        records: list[logging.LogRecord] = []

        class Collect(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = Collect(level=logging.INFO)
        previous_propagate = logger.propagate
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        try:
            with self.assertRaises(HTTPExceptionStub):
                api_ns["patch_object"]("obj-530", dict(OBJECT_PATCH_PAYLOAD), **headers)
        finally:
            logger.removeHandler(handler)
            logger.propagate = previous_propagate
        self.assertEqual([r.getMessage() for r in records if "authorized mutation attempt" in r.getMessage()], [])

    def test_control_characters_escaped_and_single_line(self) -> None:
        policy_ns = load_identity_policy()
        # Built at runtime: newline + ANSI escape sequence inside the
        # verified username must render as escapes, never raw control chars.
        forged = "admin" + chr(10) + chr(27) + "[0muser"
        with self.assertLogs(RBAC_TEST_LOGGER_NAME, level="INFO") as captured:
            policy_ns["require_role"](
                forged, STRICT_EDGE_FIXTURE, GROUP_ADMIN, minimum="admin", action="delete_object",
            )
        attempt_messages = [m for m in captured.output if "authorized mutation attempt" in m]
        self.assertEqual(len(attempt_messages), 1)
        message = attempt_messages[0]
        self.assertNotIn("\n", message, "audit record must stay single-line")
        self.assertIn("\\x0a", message)
        self.assertIn("\\x1b", message)
        self.assertIn("admin", message)

    def test_record_never_leaks_secrets_headers_groups_or_payloads(self) -> None:
        _policy, api_ns, _effects = self.build_api(edge_secret=self.EDGE_SECRET_MARKER)
        headers = {**_headers_for("admin"), "x_sea_speed_edge_auth": self.EDGE_SECRET_MARKER}
        payload = dict(OBJECT_PATCH_PAYLOAD)
        payload["comment"] = "PAYLOAD-MARKER-530"
        groups_marker = "Sea Speed Admin,SECRET-GROUP-MARKER"
        _result, attempts, all_messages = self.capture(
            lambda: api_ns["patch_object"]("obj-530", payload, **{**headers, "x_authentik_groups": groups_marker})
        )
        self.assertEqual(len(attempts), 1)
        joined = "\n".join(all_messages)
        self.assertNotIn(self.EDGE_SECRET_MARKER, joined, "edge secret must never be logged")
        self.assertNotIn("SECRET-GROUP-MARKER", joined, "raw groups must never be logged")
        self.assertNotIn("Sea Speed", joined, "group names must never be logged")
        self.assertNotIn("PAYLOAD-MARKER-530", joined, "request payload must never be logged")
        self.assertNotIn("x_authentik", joined.lower(), "header names/material must never be logged")

    def test_attempt_is_not_a_success_claim(self) -> None:
        # Downstream failure after authorization: the record stays an ATTEMPT.
        _policy, api_ns, _effects = self.build_api()

        def boom(object_id, payload, camera_id=None):
            raise HTTPExceptionStub(404, "Object not found")

        api_ns["patch_object_record"] = boom
        headers = _headers_for("operator")
        with self.assertRaises(HTTPExceptionStub):
            self.capture(lambda: api_ns["patch_object"]("obj-530", dict(OBJECT_PATCH_PAYLOAD), **headers))
        # And the successful path's wording is unchanged: "attempt", never
        # "completed"/"success".
        _policy, api_ns, _effects = self.build_api()
        _result, attempts, _all = self.capture(
            lambda: api_ns["patch_object"]("obj-530", dict(OBJECT_PATCH_PAYLOAD), **headers)
        )
        self.assertEqual(len(attempts), 1)
        self.assertNotIn("success", attempts[0].lower())
        self.assertNotIn("completed", attempts[0].lower())


if __name__ == "__main__":
    unittest.main()
