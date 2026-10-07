from __future__ import annotations

import ast
import copy
import importlib.util
import ipaddress
import json
import os
import subprocess
import sys
import types
import unittest
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "deploy" / "worker" / "ubuntu" / "worker-control-agent.py"
CONTROL_UNIT = ROOT / "deploy" / "worker" / "ubuntu" / "sea-speed-worker-control.service.template"
CONTROL_ENV_EXAMPLE = ROOT / "deploy" / "worker" / "ubuntu" / "control.env.example"
WORKER_ENV_EXAMPLE = ROOT / "deploy" / "worker" / "ubuntu" / "worker.env.example"
ROAD_WORKER_ENV_EXAMPLE = ROOT / "deploy" / "worker" / "ubuntu" / "road-worker.env.example"
INSTALLER = ROOT / "deploy" / "worker" / "ubuntu" / "install-systemd.sh"
EXACT_UPDATER = ROOT / "deploy" / "worker" / "ubuntu" / "update-exact.sh"
API_PATH = ROOT / "api" / "app" / "main.py"

CONTROL_TOKEN = "control-token-393"
INGESTION_TOKEN = "ingest-token-393"
MANAGED_ENV_KEYS = (
    "SEA_SPEED_WORKER_CONTROL_TOKEN",
    "SEA_SPEED_API_TOKEN",
    "SEA_SPEED_WORKER_CONTROL_URL",
    "SEA_SPEED_WORKER_CONTROL_LISTEN",
    "SEA_SPEED_WORKER_INSTALL_ROOT",
)


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_agent_module():
    spec = importlib.util.spec_from_file_location("sea_speed_worker_control_agent_393", AGENT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_api_functions(names: set[str], namespace: dict[str, Any]) -> None:
    tree = ast.parse(API_PATH.read_text(encoding="utf-8-sig"), filename=str(API_PATH))
    selected = []
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            cloned = copy.deepcopy(node)
            cloned.decorator_list = []
            selected.append(cloned)
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(API_PATH), "exec"), namespace)


class FakeResponse:
    def __init__(self, body: bytes, status: int):
        self._body = body
        self.status = status

    def read(self, size: int = -1) -> bytes:
        return self._body


class FakeHTTPConnection:
    last_request: dict[str, Any] | None = None

    def __init__(self, host: str, port: int, timeout: float | None = None):
        self.host = host
        self.port = port
        self.timeout = timeout

    def request(self, method: str, path: str, body: Any = None, headers: Any = None) -> None:
        FakeHTTPConnection.last_request = {"method": method, "path": path, "headers": dict(headers or {})}

    def getresponse(self) -> FakeResponse:
        payload = json.dumps({"ok": True, "protocol": "sea_speed_worker_control_v1"}).encode("utf-8")
        return FakeResponse(payload, 200)

    def close(self) -> None:
        return None


FAKE_HTTP = types.ModuleType("http")
FAKE_HTTP_CLIENT = types.ModuleType("http.client")
FAKE_HTTP_CLIENT.HTTPConnection = FakeHTTPConnection  # type: ignore[attr-defined]
FAKE_HTTP.client = FAKE_HTTP_CLIENT  # type: ignore[attr-defined]


def api_namespace(control_token: str, ingestion_token: str) -> dict[str, Any]:
    return {
        "Any": Any,
        "Dict": Dict,
        "Optional": Optional,
        "HTTPException": HTTPExceptionStub,
        "http": FAKE_HTTP,
        "json": json,
        "ipaddress": ipaddress,
        "urlsplit": urllib.parse.urlsplit,
        "API_TOKEN": ingestion_token,
        "WORKER_CONTROL_TOKEN": control_token,
        "WORKER_CONTROL_URL": "http://10.123.239.102:19001",
        "WORKER_CONTROL_TIMEOUT_SEC": 1.0,
        "WORKER_CONTROL_PROTOCOL": "sea_speed_worker_control_v1",
        "CAMERA_PREVIEW_RFC1918": tuple(
            ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
        ),
    }


class WorkerControlTokenSeparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = {key: os.environ.get(key) for key in MANAGED_ENV_KEYS}
        for key in MANAGED_ENV_KEYS:
            os.environ.pop(key, None)
        FakeHTTPConnection.last_request = None

    def tearDown(self) -> None:
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # --- Agent side ---------------------------------------------------------

    def test_agent_bearer_auth_accepts_only_control_token(self) -> None:
        module = load_agent_module()
        os.environ["SEA_SPEED_WORKER_CONTROL_TOKEN"] = CONTROL_TOKEN
        os.environ["SEA_SPEED_API_TOKEN"] = INGESTION_TOKEN
        self.assertIs(module.authorized(None), False)
        self.assertIs(module.authorized(""), False)
        self.assertIs(module.authorized("Basic control-token-393"), False)
        self.assertIs(module.authorized("Bearer wrong"), False)
        self.assertIs(module.authorized("Bearer ingest-token-393"), False)
        self.assertIs(module.authorized("Bearer control-token-393"), True)

    def agent_startup_subprocess(self, extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        env = {key: value for key, value in os.environ.items() if not key.startswith("SEA_SPEED_")}
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(AGENT_PATH)],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def test_agent_startup_fails_closed_without_control_token(self) -> None:
        result = self.agent_startup_subprocess({})
        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertIn("SEA_SPEED_WORKER_CONTROL_TOKEN", combined)

    def test_agent_startup_fails_closed_even_with_ingestion_token(self) -> None:
        result = self.agent_startup_subprocess({"SEA_SPEED_API_TOKEN": INGESTION_TOKEN})
        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertIn("SEA_SPEED_WORKER_CONTROL_TOKEN", combined)
        self.assertNotIn("SEA_SPEED_API_TOKEN is required", combined)

    # --- Unit template ------------------------------------------------------

    def test_control_unit_loads_dedicated_control_env_only(self) -> None:
        source = CONTROL_UNIT.read_text(encoding="utf-8")
        self.assertIn("EnvironmentFile=__INSTALL_ROOT__/shared/config/control.env", source)
        self.assertNotIn("worker.env", source)

    # --- Example hygiene ----------------------------------------------------

    def test_control_env_example_is_control_plane_only(self) -> None:
        source = CONTROL_ENV_EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("SEA_SPEED_WORKER_CONTROL_TOKEN=", source)
        active_keys = []
        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            key = line.split("=", 1)[0].strip()
            if key:
                active_keys.append(key)
        self.assertEqual(active_keys, ["SEA_SPEED_WORKER_CONTROL_TOKEN"])
        for banned in ("HLS_URL", "BASIC_AUTH", "MODEL", "SEA_SPEED_API_URL", "_URL"):
            self.assertNotIn(banned, "\n".join(active_keys))

    def test_data_plane_env_examples_never_carry_control_token(self) -> None:
        for path in (WORKER_ENV_EXAMPLE, ROAD_WORKER_ENV_EXAMPLE):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("SEA_SPEED_WORKER_CONTROL_TOKEN", source)
            self.assertIn("SEA_SPEED_API_TOKEN=", source)

    # --- Installer gate -----------------------------------------------------

    def test_installer_gates_control_env_before_mutation(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('control_env_file="$install_root/shared/config/control.env"', source)
        gate_index = source.index('if [[ -L "$control_env_file" ]]')
        self.assertIn('if [[ ! -f "$control_env_file" ]]', source)
        self.assertIn('[[ "$(stat -c \'%a\' "$control_env_file")" != "600" ]]', source)
        self.assertIn("grep -Eq '^SEA_SPEED_WORKER_CONTROL_TOKEN=.+$' \"$control_env_file\"", source)
        self.assertIn("exit 8", source)
        self.assertIn("exit 6", source)
        self.assertIn("exit 7", source)
        self.assertLess(gate_index, source.index("useradd"))
        self.assertLess(gate_index, source.index("mkdir -p"))

    def test_installer_and_exact_updater_shell_syntax(self) -> None:
        for path in (INSTALLER, EXACT_UPDATER):
            subprocess.run(["bash", "-n", str(path)], check=True)

    # --- API side -----------------------------------------------------------

    def test_api_source_wires_control_token_constant(self) -> None:
        source = API_PATH.read_text(encoding="utf-8")
        self.assertIn('os.environ.get("SEA_SPEED_WORKER_CONTROL_TOKEN"', source)
        self.assertIn("if not WORKER_CONTROL_TOKEN:", source)
        self.assertIn('"SEA_SPEED_WORKER_CONTROL_TOKEN is not set"', source)
        self.assertIn('f"Bearer {WORKER_CONTROL_TOKEN}"', source)
        self.assertIn('os.environ.get("SEA_SPEED_API_TOKEN"', source)

    def test_api_control_path_uses_control_token_not_ingestion_token(self) -> None:
        namespace = api_namespace(CONTROL_TOKEN, INGESTION_TOKEN)
        load_api_functions({"worker_control_origin", "call_worker_control"}, namespace)
        payload = namespace["call_worker_control"]("GET", "/v1/status")
        self.assertTrue(payload["ok"])
        sent = FakeHTTPConnection.last_request
        assert sent is not None
        self.assertEqual(sent["method"], "GET")
        self.assertEqual(sent["path"], "/v1/status")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer control-token-393")
        self.assertNotEqual(sent["headers"]["Authorization"], "Bearer ingest-token-393")

    def test_api_control_path_fails_closed_without_control_token(self) -> None:
        namespace = api_namespace("", INGESTION_TOKEN)
        load_api_functions({"worker_control_origin", "call_worker_control"}, namespace)
        with self.assertRaises(HTTPExceptionStub) as context:
            namespace["call_worker_control"]("GET", "/v1/status")
        self.assertEqual(context.exception.status_code, 500)
        self.assertIn("SEA_SPEED_WORKER_CONTROL_TOKEN", context.exception.detail)

    def test_api_ingestion_auth_remains_ingestion_token(self) -> None:
        namespace = api_namespace(CONTROL_TOKEN, INGESTION_TOKEN)
        load_api_functions({"require_auth"}, namespace)
        namespace["require_auth"]("Bearer ingest-token-393")
        with self.assertRaises(HTTPExceptionStub) as context:
            namespace["require_auth"]("Bearer control-token-393")
        self.assertEqual(context.exception.status_code, 403)
        namespace["API_TOKEN"] = ""
        with self.assertRaises(HTTPExceptionStub) as context:
            namespace["require_auth"]("Bearer ingest-token-393")
        self.assertEqual(context.exception.status_code, 500)
        self.assertIn("SEA_SPEED_API_TOKEN", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
