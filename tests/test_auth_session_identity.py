from __future__ import annotations

import ast
import copy
import hmac
import logging
import os
import unittest
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "api/app/main.py"
IDENTITY_SOURCE = ROOT / "api/app/identity.py"
EDGE_AUTH_ENV = "SEA_SPEED_EDGE_AUTH_SECRET"
STRICT_EDGE_FIXTURE = "edge-fixture-520"
IDENTITY_TEST_LOGGER_NAME = "sea_speed_identity_under_test"
_IDENTITY_MODULE_GLOBALS = {"_LOGGER", "_EDGE_AUTH_TRANSITIONAL_WARNING_EMITTED"}


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_require_operator_identity():
    """AST-extract the operator trust primitive from identity.py (issue #520).

    Mirrors ``load_session_identity_function``: import-free extraction, so
    the harness never imports ``config`` (whose import-time side effects
    bind it to /opt state absent in the test environment). ``EDGE_AUTH_SECRET``
    mirrors the config.py env read at load time, so monkeypatching
    ``SEA_SPEED_EDGE_AUTH_SECRET`` and reloading switches between the
    transitional and strict enforcement modes. The module-level logger and
    the one-shot transitional latch are extracted together with the
    function, so every load is a fresh "process" and tests stay
    order-independent.
    """
    tree = ast.parse(IDENTITY_SOURCE.read_text(encoding="utf-8-sig"), filename=str(IDENTITY_SOURCE))
    body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "require_operator_identity":
            body.append(copy.deepcopy(node))
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in _IDENTITY_MODULE_GLOBALS
        ):
            body.append(copy.deepcopy(node))
    if not any(isinstance(node, ast.FunctionDef) for node in body):
        raise AssertionError("missing require_operator_identity identity function")
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "__name__": IDENTITY_TEST_LOGGER_NAME,
        "Any": Any,
        "Dict": Dict,
        "Optional": Optional,
        "EDGE_AUTH_SECRET": os.environ.get(EDGE_AUTH_ENV, ""),
        "HTTPException": HTTPExceptionStub,
        "hmac": hmac,
        "logging": logging,
    }
    exec(compile(module, str(IDENTITY_SOURCE), "exec"), namespace)
    return namespace


def load_session_identity_function(require_operator_identity=None):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    selected = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "get_session_identity":
            selected = copy.deepcopy(node)
            selected.decorator_list = []
            break
    if selected is None:
        raise AssertionError("missing get_session_identity API function")
    module = ast.Module(body=[selected], type_ignores=[])
    ast.fix_missing_locations(module)
    if require_operator_identity is None:
        # Issue #520: the route delegates to the shared trust primitive; bind
        # the real (transitional-mode) primitive so the pins below exercise
        # the unified path instead of an inline duplication.
        require_operator_identity = load_require_operator_identity()[
            "require_operator_identity"
        ]
    namespace: dict[str, Any] = {
        "Any": Any,
        "Dict": Dict,
        "Optional": Optional,
        "HTTPException": HTTPExceptionStub,
        "Header": lambda default=None: default,
        "require_operator_identity": require_operator_identity,
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["get_session_identity"]


class EdgeSecretEnvMixin(unittest.TestCase):
    """Shared env helper for edge-secret tests (issue #520).

    Sets/unsets ``SEA_SPEED_EDGE_AUTH_SECRET`` and registers restore via
    ``addCleanup`` so every test is order-independent regardless of shell
    exports. No test methods of its own — concrete classes combine it with
    their own tests.
    """

    def _set_edge_secret_env(self, value: Optional[str]) -> None:
        previous = os.environ.get(EDGE_AUTH_ENV)
        if value is None:
            os.environ.pop(EDGE_AUTH_ENV, None)
        else:
            os.environ[EDGE_AUTH_ENV] = value
        self.addCleanup(self._restore_edge_secret_env, previous)

    @staticmethod
    def _restore_edge_secret_env(previous: Optional[str]) -> None:
        if previous is None:
            os.environ.pop(EDGE_AUTH_ENV, None)
        else:
            os.environ[EDGE_AUTH_ENV] = previous


class AuthSessionIdentityTests(EdgeSecretEnvMixin, unittest.TestCase):
    def test_returns_only_trimmed_trusted_username(self) -> None:
        self._set_edge_secret_env(None)  # transitional mode regardless of shell exports
        get_session_identity = load_session_identity_function()
        self.assertEqual(
            get_session_identity("  owner@example.test  "),
            {"ok": True, "username": "owner@example.test"},
        )

    def test_missing_or_blank_trusted_username_fails_closed(self) -> None:
        self._set_edge_secret_env(None)  # transitional mode regardless of shell exports
        get_session_identity = load_session_identity_function()
        for value in (None, "", "   "):
            with self.subTest(value=value):
                with self.assertRaises(HTTPExceptionStub) as raised:
                    get_session_identity(value)
                self.assertEqual(raised.exception.status_code, 503)
                self.assertEqual(
                    raised.exception.detail,
                    "Trusted Authentik identity is unavailable",
                )

    def test_session_route_uses_forwarded_authentik_header(self) -> None:
        tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
        target = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "get_session_identity"
            ),
            None,
        )
        self.assertIsNotNone(target)
        assert target is not None
        routes = []
        for decorator in target.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "get"
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            ):
                routes.append(decorator.args[0].value)
        self.assertEqual(routes, ["/api/session"])
        self.assertEqual(target.args.args[0].arg, "x_authentik_username")


class OperatorEdgeAuthTests(EdgeSecretEnvMixin):
    """Edge-secret enforcement for operator identity (issue #520).

    Strict mode — ``SEA_SPEED_EDGE_AUTH_SECRET`` set (monkeypatched env +
    reload): requests must carry ``X-Sea-Speed-Edge-Auth`` equal to the
    secret BEFORE the username is inspected; mismatch/absence is 403
    "Forbidden"; correct secret keeps the 503-on-blank-username semantics.
    Transitional mode — env unset/blank: legacy semantics byte-identical
    plus a one-shot WARNING per process. Each test restores the env and
    loads a fresh primitive (fresh latch), so tests are order-independent.
    """

    def test_transitional_mode_warns_exactly_once_per_process(self) -> None:
        self._set_edge_secret_env(None)
        namespace = load_require_operator_identity()
        require_operator_identity = namespace["require_operator_identity"]
        with self.assertLogs(IDENTITY_TEST_LOGGER_NAME, level="WARNING") as captured:
            self.assertEqual(
                require_operator_identity("  owner@example.test  "),
                "owner@example.test",
            )
            self.assertEqual(
                require_operator_identity("owner@example.test"),
                "owner@example.test",
            )
        self.assertEqual(
            len(captured.records), 1, "transitional warning must fire exactly once per process"
        )
        message = captured.records[0].getMessage()
        self.assertIn("SEA_SPEED_EDGE_AUTH_SECRET is not set", message)
        # Never log identity material: no username/header values in the warning.
        self.assertNotIn("owner@example.test", message)

    def test_transitional_mode_blank_secret_warns_set_but_blank(self) -> None:
        self._set_edge_secret_env("   ")
        namespace = load_require_operator_identity()
        require_operator_identity = namespace["require_operator_identity"]
        with self.assertLogs(IDENTITY_TEST_LOGGER_NAME, level="WARNING") as captured:
            # Set-but-blank secret keeps transitional acceptance semantics.
            self.assertEqual(
                require_operator_identity("owner@example.test"),
                "owner@example.test",
            )
            self.assertEqual(
                require_operator_identity("owner@example.test"),
                "owner@example.test",
            )
        self.assertEqual(
            len(captured.records), 1, "blank-secret warning must fire exactly once per process"
        )
        message = captured.records[0].getMessage()
        # The warning must distinguish "set but blank" from "not set" and
        # still never log the (whitespace) value or identity material.
        self.assertIn("SEA_SPEED_EDGE_AUTH_SECRET is set but blank", message)
        self.assertNotIn("is not set", message)
        self.assertNotIn("owner@example.test", message)

    def test_strict_mode_non_ascii_edge_header_rejected_before_username(self) -> None:
        self._set_edge_secret_env(STRICT_EDGE_FIXTURE)
        namespace = load_require_operator_identity()
        require_operator_identity = namespace["require_operator_identity"]
        get_session_identity = load_session_identity_function(require_operator_identity)
        forged_header = "ä- forged"
        with self.subTest(caller="route"):
            # A valid username is supplied: rejection must be the 403 edge
            # check, not a comparison crash (500) nor identity acceptance.
            with self.assertRaises(HTTPExceptionStub) as raised:
                get_session_identity("owner@example.test", forged_header)
            self.assertEqual(raised.exception.status_code, 403)
            self.assertEqual(raised.exception.detail, "Forbidden")
        with self.subTest(caller="primitive"):
            with self.assertRaises(HTTPExceptionStub) as raised_direct:
                require_operator_identity("owner@example.test", forged_header)
            self.assertEqual(raised_direct.exception.status_code, 403)
            self.assertEqual(raised_direct.exception.detail, "Forbidden")

    def test_strict_mode_missing_edge_header_rejected_before_username(self) -> None:
        self._set_edge_secret_env(STRICT_EDGE_FIXTURE)
        namespace = load_require_operator_identity()
        require_operator_identity = namespace["require_operator_identity"]
        get_session_identity = load_session_identity_function(require_operator_identity)
        for edge_header in (None, "", "   "):
            with self.subTest(edge_header=edge_header):
                # A valid username must still be rejected: 403 precedes any
                # username handling when the edge header is absent/blank.
                with self.assertRaises(HTTPExceptionStub) as raised:
                    get_session_identity("owner@example.test", edge_header)
                self.assertEqual(raised.exception.status_code, 403)
                self.assertEqual(raised.exception.detail, "Forbidden")
                with self.assertRaises(HTTPExceptionStub) as raised_direct:
                    require_operator_identity("owner@example.test", edge_header)
                self.assertEqual(raised_direct.exception.status_code, 403)
                self.assertEqual(raised_direct.exception.detail, "Forbidden")

    def test_strict_mode_wrong_edge_header_rejected_before_username(self) -> None:
        self._set_edge_secret_env(STRICT_EDGE_FIXTURE)
        namespace = load_require_operator_identity()
        require_operator_identity = namespace["require_operator_identity"]
        get_session_identity = load_session_identity_function(require_operator_identity)
        wrong_header = "edge-fixture-wrong-value"
        for username in ("owner@example.test", None, ""):
            with self.subTest(username=username):
                # Blank username + wrong secret must be 403, NOT 503: the
                # edge header is checked before the username is read.
                with self.assertRaises(HTTPExceptionStub) as raised:
                    get_session_identity(username, wrong_header)
                self.assertEqual(raised.exception.status_code, 403)
                self.assertEqual(raised.exception.detail, "Forbidden")

    def test_strict_mode_correct_edge_header_returns_trimmed_identity(self) -> None:
        self._set_edge_secret_env(STRICT_EDGE_FIXTURE)
        namespace = load_require_operator_identity()
        require_operator_identity = namespace["require_operator_identity"]
        get_session_identity = load_session_identity_function(require_operator_identity)
        self.assertEqual(
            get_session_identity("  owner@example.test  ", STRICT_EDGE_FIXTURE),
            {"ok": True, "username": "owner@example.test"},
        )
        self.assertEqual(
            require_operator_identity("  owner@example.test  ", STRICT_EDGE_FIXTURE),
            "owner@example.test",
        )

    def test_strict_mode_blank_username_still_fails_closed(self) -> None:
        self._set_edge_secret_env(STRICT_EDGE_FIXTURE)
        namespace = load_require_operator_identity()
        require_operator_identity = namespace["require_operator_identity"]
        get_session_identity = load_session_identity_function(require_operator_identity)
        for username in (None, "", "   "):
            with self.subTest(username=username):
                with self.assertRaises(HTTPExceptionStub) as raised:
                    get_session_identity(username, STRICT_EDGE_FIXTURE)
                self.assertEqual(raised.exception.status_code, 503)
                self.assertEqual(
                    raised.exception.detail,
                    "Trusted Authentik identity is unavailable",
                )

    def test_operator_routes_pass_edge_header_to_identity(self) -> None:
        tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
        expected_handlers = {
            "get_session_identity",
            "get_worker_control",
            "start_worker_control",
            "stop_worker_control",
            "get_road_worker_control",
            "start_road_worker_control",
            "stop_road_worker_control",
        }
        seen = set()
        for node in tree.body:
            if not (isinstance(node, ast.FunctionDef) and node.name in expected_handlers):
                continue
            seen.add(node.name)
            with self.subTest(handler=node.name):
                arg_names = [arg.arg for arg in node.args.args]
                self.assertIn("x_sea_speed_edge_auth", arg_names)
                passed = []
                for child in ast.walk(node):
                    if (
                        isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Name)
                        and child.func.id == "require_operator_identity"
                    ):
                        passed.extend(arg.id for arg in child.args if isinstance(arg, ast.Name))
                        passed.extend(keyword.arg for keyword in child.keywords if keyword.arg)
                self.assertIn("x_sea_speed_edge_auth", passed)
        self.assertEqual(seen, expected_handlers)


if __name__ == "__main__":
    unittest.main()
