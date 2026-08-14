from __future__ import annotations

import ast
import copy
import unittest
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "api/app/main.py"


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_session_identity_function():
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
    namespace: dict[str, Any] = {
        "Any": Any,
        "Dict": Dict,
        "Optional": Optional,
        "HTTPException": HTTPExceptionStub,
        "Header": lambda default=None: default,
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["get_session_identity"]


class AuthSessionIdentityTests(unittest.TestCase):
    def test_returns_only_trimmed_trusted_username(self) -> None:
        get_session_identity = load_session_identity_function()
        self.assertEqual(
            get_session_identity("  owner@example.test  "),
            {"ok": True, "username": "owner@example.test"},
        )

    def test_missing_or_blank_trusted_username_fails_closed(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
