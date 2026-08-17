from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "deploy" / "worker" / "ubuntu" / "worker-control-agent.py"
API_PATH = ROOT / "api" / "app" / "main.py"
FRONTEND_PATH = ROOT / "frontend" / "sea-speed" / "index.html"
ROAD_FRONTEND_PATH = ROOT / "frontend" / "sea-speed" / "road" / "index.html"


def load_agent():
    spec = importlib.util.spec_from_file_location("sea_speed_worker_control_agent", AGENT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_surface_is_fixed_to_two_services_and_six_paths():
    module = load_agent()
    assert module.SERVICE_NAME == "sea-speed-worker.service"
    assert module.ROAD_SERVICE_NAME == "sea-speed-road-worker.service"
    assert module.WORKER_CONTROL_PROTOCOL == "sea_speed_worker_control_v1"
    assert set(module.CONTROL_TARGETS) == {"water", "road1"}
    assert module.service_name("water") == module.SERVICE_NAME
    assert module.service_name("road1") == module.ROAD_SERVICE_NAME
    assert module.ALLOWED_PATHS == {
        "/v1/status", "/v1/start", "/v1/stop",
        "/v1/road1/status", "/v1/road1/start", "/v1/road1/stop",
    }
    source = AGENT_PATH.read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "mediamtx" not in source.lower()
    assert "camera-relay" not in source.lower()
    assert "/v1/{" not in source


def test_unknown_control_target_fails_closed():
    module = load_agent()
    try:
        module.service_name("arbitrary")
    except ValueError:
        pass
    else:
        raise AssertionError("arbitrary service target accepted")


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


def test_water_start_failure_restores_previous_desired_state(monkeypatch, tmp_path):
    module = load_agent()
    monkeypatch.setenv("SEA_SPEED_WORKER_INSTALL_ROOT", str(tmp_path))
    module.write_desired_state("stopped", "water")

    def fake_systemctl(*args, **_kwargs):
        if args == ("start", module.SERVICE_NAME):
            return subprocess.CompletedProcess(args, 1, "", "failed")
        raise AssertionError(args)

    monkeypatch.setattr(module, "systemctl", fake_systemctl)
    try:
        module.start_worker("water")
    except RuntimeError:
        pass
    else:
        raise AssertionError("failed systemctl start must fail closed")
    assert module.read_desired_state("water") == "stopped"


def test_water_stop_records_intent_before_fixed_service_stop(monkeypatch, tmp_path):
    module = load_agent()
    monkeypatch.setenv("SEA_SPEED_WORKER_INSTALL_ROOT", str(tmp_path))
    observed = []

    def fake_systemctl(*args, **_kwargs):
        observed.append((args, module.read_desired_state("water")))
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
    status = module.stop_worker("water")
    assert status["active"] is False
    assert status["desired_state"] == "stopped"
    assert status["target"] == "water"
    assert status["protocol"] == module.WORKER_CONTROL_PROTOCOL
    assert observed[0] == (("stop", module.SERVICE_NAME), "stopped")


def test_road_desired_state_is_independent_from_water(monkeypatch, tmp_path):
    module = load_agent()
    monkeypatch.setenv("SEA_SPEED_WORKER_INSTALL_ROOT", str(tmp_path))
    module.write_desired_state("running", "water")
    module.write_desired_state("stopped", "road1")
    assert module.desired_state_path("water") == tmp_path / "shared" / "runtime" / "operator-desired-state"
    assert module.desired_state_path("road1") == tmp_path / "shared" / "road-runtime" / "operator-desired-state"
    assert module.read_desired_state("water") == "running"
    assert module.read_desired_state("road1") == "stopped"


def test_road_stop_touches_only_fixed_road_service(monkeypatch, tmp_path):
    module = load_agent()
    monkeypatch.setenv("SEA_SPEED_WORKER_INSTALL_ROOT", str(tmp_path))
    calls = []

    def fake_systemctl(*args, **_kwargs):
        calls.append(args)
        if args == ("stop", module.ROAD_SERVICE_NAME):
            return subprocess.CompletedProcess(args, 0, "", "")
        if args == ("is-active", "--quiet", module.ROAD_SERVICE_NAME):
            return subprocess.CompletedProcess(args, 3, "", "")
        if args == ("is-enabled", module.ROAD_SERVICE_NAME):
            return subprocess.CompletedProcess(args, 0, "enabled\n", "")
        if args == ("show", "--property=ActiveState,SubState", "--value", module.ROAD_SERVICE_NAME):
            return subprocess.CompletedProcess(args, 0, "inactive\ndead\n", "")
        raise AssertionError(args)

    monkeypatch.setattr(module, "systemctl", fake_systemctl)
    status = module.stop_worker("road1")
    assert status["target"] == "road1"
    assert status["service"] == module.ROAD_SERVICE_NAME
    assert module.read_desired_state("road1") == "stopped"
    assert all(module.SERVICE_NAME not in call for call in calls)


def test_vps_api_contract_is_fixed_private_proxy_with_trusted_identity():
    source = API_PATH.read_text(encoding="utf-8")
    for marker in (
        '"/api/worker/control"', '"/api/worker/control/start"', '"/api/worker/control/stop"',
        '"/api/worker/control/road1"', '"/api/worker/control/road1/start"', '"/api/worker/control/road1/stop"',
        '"/v1/road1/status"', '"/v1/road1/start"', '"/v1/road1/stop"',
    ):
        assert marker in source
    assert "SEA_SPEED_WORKER_CONTROL_URL" in source
    assert "require_operator_identity" in source
    assert "http.client.HTTPConnection" in source
    assert "SEA_SPEED_API_TOKEN" in source
    assert "worker_control_origin" in source
    assert '/api/worker/control/{' not in source


def test_worker_control_protocol_is_fixed_and_mismatch_fails_closed():
    agent = AGENT_PATH.read_text(encoding="utf-8")
    api = API_PATH.read_text(encoding="utf-8")
    marker = 'WORKER_CONTROL_PROTOCOL = "sea_speed_worker_control_v1"'
    assert marker in agent
    assert marker in api
    assert '"protocol": WORKER_CONTROL_PROTOCOL' in agent
    assert 'payload.get("protocol") != WORKER_CONTROL_PROTOCOL' in api
    assert 'detail="Worker control protocol mismatch"' in api


def test_worker_control_never_owns_camera_hls_or_preview():
    agent = AGENT_PATH.read_text(encoding="utf-8").lower()
    api = API_PATH.read_text(encoding="utf-8").lower()
    frontend = FRONTEND_PATH.read_text(encoding="utf-8")
    road = ROAD_FRONTEND_PATH.read_text(encoding="utf-8")
    assert "mediamtx" not in agent
    assert "camera-relay" not in agent
    assert 'const HLS_URL = "/sea-speed/media/cam1/index.m3u8";' in frontend
    assert 'const PREVIEW_START_URL="/sea-speed/api/cameras/road1/preview/start"' in road
    assert 'const WORKER_CONTROL_URL="/sea-speed/api/worker/control/road1"' in road
    assert "systemctl" not in api
