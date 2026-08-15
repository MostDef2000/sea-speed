import importlib.util
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "deploy" / "worker" / "ubuntu" / "worker-control-agent.py"
API_PATH = ROOT / "api" / "app" / "main.py"
FRONTEND_PATH = ROOT / "frontend" / "sea-speed" / "index.html"


def load_agent():
    spec = importlib.util.spec_from_file_location("sea_speed_worker_control_agent", AGENT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_surface_is_fixed_to_one_service_and_three_paths():
    module = load_agent()
    assert module.SERVICE_NAME == "sea-speed-worker.service"
    assert module.ALLOWED_PATHS == {"/v1/status", "/v1/start", "/v1/stop"}
    source = AGENT_PATH.read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "mediamtx" not in source.lower()
    assert "camera-relay" not in source.lower()
    assert "service_name =" not in source.lower()


def test_private_listener_rejects_public_loopback_and_privileged_ports():
    module = load_agent()
    assert module.parse_private_listen("10.123.239.102:19001") == ("10.123.239.102", 19001)
    for value in ("127.0.0.1:19001", "8.8.8.8:19001", "10.0.0.2:80", "host:19001"):
        try:
            module.parse_private_listen(value)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"unsafe listener accepted: {value}")


def test_bearer_auth_fails_closed(monkeypatch):
    module = load_agent()
    monkeypatch.setenv("SEA_SPEED_API_TOKEN", "test-secret")
    assert module.authorized(None) is False
    assert module.authorized("Bearer wrong") is False
    assert module.authorized("Basic test-secret") is False
    assert module.authorized("Bearer test-secret") is True


def test_start_failure_restores_previous_desired_state(monkeypatch, tmp_path):
    module = load_agent()
    monkeypatch.setenv("SEA_SPEED_WORKER_INSTALL_ROOT", str(tmp_path))
    module.write_desired_state("stopped")

    def fake_systemctl(*args, **_kwargs):
        if args == ("start", module.SERVICE_NAME):
            return subprocess.CompletedProcess(args, 1, "", "failed")
        raise AssertionError(args)

    monkeypatch.setattr(module, "systemctl", fake_systemctl)
    try:
        module.start_worker()
    except RuntimeError:
        pass
    else:
        raise AssertionError("failed systemctl start must fail closed")
    assert module.read_desired_state() == "stopped"


def test_stop_records_intent_before_fixed_service_stop(monkeypatch, tmp_path):
    module = load_agent()
    monkeypatch.setenv("SEA_SPEED_WORKER_INSTALL_ROOT", str(tmp_path))
    observed = []

    def fake_systemctl(*args, **_kwargs):
        observed.append((args, module.read_desired_state()))
        if args == ("stop", module.SERVICE_NAME):
            return subprocess.CompletedProcess(args, 0, "", "")
        if args == ("is-active", "--quiet", module.SERVICE_NAME):
            return subprocess.CompletedProcess(args, 3, "", "")
        if args == ("is-enabled", module.SERVICE_NAME):
            return subprocess.CompletedProcess(args, 0, "enabled\n", "")
        if args == ("show", "--property=ActiveState,SubState", "--value", module.SERVICE_NAME):
            return subprocess.CompletedProcess(args, 0, "inactive\ndead\n", "")
        raise AssertionError(args)

    monkeypatch.setattr(module, "systemctl", fake_systemctl)
    status = module.stop_worker()
    assert status["active"] is False
    assert status["desired_state"] == "stopped"
    assert observed[0] == (("stop", module.SERVICE_NAME), "stopped")


def test_vps_api_contract_is_fixed_private_proxy_with_trusted_identity():
    source = API_PATH.read_text(encoding="utf-8")
    assert '"/api/worker/control"' in source
    assert '"/api/worker/control/start"' in source
    assert '"/api/worker/control/stop"' in source
    assert "SEA_SPEED_WORKER_CONTROL_URL" in source
    assert "require_operator_identity" in source
    assert "http.client.HTTPConnection" in source
    assert "SEA_SPEED_API_TOKEN" in source
    assert "worker_control_origin" in source


def test_worker_control_never_owns_camera_hls():
    agent = AGENT_PATH.read_text(encoding="utf-8").lower()
    api = API_PATH.read_text(encoding="utf-8").lower()
    frontend = FRONTEND_PATH.read_text(encoding="utf-8")
    assert "mediamtx" not in agent
    assert "camera-relay" not in agent
    assert 'const HLS_URL = "/sea-speed/media/cam1/index.m3u8";' in frontend
    assert "WORKER_CONTROL_URL" in frontend
    assert "systemctl" not in api
