from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

import analytics_profiles as profiles

try:
    from tests.support import frontend_html, worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import frontend_html, worker_source

CONFIGURE = ROOT / "deploy/worker/ubuntu/configure-analytics-profiles.py"
configure_spec = importlib.util.spec_from_file_location("configure_analytics_profiles", CONFIGURE)
assert configure_spec and configure_spec.loader
configure = importlib.util.module_from_spec(configure_spec)
configure_spec.loader.exec_module(configure)

API_DIR = ROOT / "api/app"
API_MODULES = (
    "main.py",
    "objects_registry.py",
    "passage_mirrors.py",
    "water_passages.py",
    "analytics.py",
    "identity.py",
    "config.py",
)
FRONTEND_PATHS = (
    ROOT / "frontend/sea-speed/index.html",
    ROOT / "frontend/sea-speed/objects/index.html",
    ROOT / "frontend/sea-speed/cameras/index.html",
    ROOT / "frontend/sea-speed/road/index.html",
)


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def decorator_paths(tree: ast.AST) -> set[str]:
    """String-literal positional args of every decorator call (route paths)."""
    paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    for argument in decorator.args:
                        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                            paths.add(argument.value)
    return paths


def code_without_comment_lines(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


def anchor_tags(html: str) -> list[str]:
    return re.findall(r"<a\b[^>]*>", html)


def anchor_attr(tag: str, name: str) -> str | None:
    match = re.search(rf'\b{name}="([^"]*)"', tag)
    return match.group(1) if match else None


# Minimal executed-boot scenario for pages whose wiring is proven by which
# endpoints they fetch (objects registry page): no watchdog/redirect asserts.
BOOT_SCENARIO = """
;(async () => {
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  console.log("###" + JSON.stringify({ fetchUrls: __record.fetch.map((c) => c.url) }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


class AnalyticsProfilesTests(unittest.TestCase):
    def test_profile_defaults_are_exact(self) -> None:
        water = profiles.get_profile("water-v1")
        road = profiles.get_profile("road-v1")
        self.assertEqual(profiles.DEFAULT_PROFILE, "water-v1")
        self.assertEqual(profiles.get_profile(), water)
        for profile, camera, domain in ((water, "cam1", "water"), (road, "road1", "road")):
            self.assertEqual(profile.default_camera_id, camera)
            self.assertEqual(profile.domain, domain)
            self.assertEqual(profile.model_name, "models/yolo26x.pt")
            self.assertEqual(profile.image_size, 960)
            self.assertEqual(profile.tracker, "bytetrack.yaml")
            self.assertEqual(profile.sample_fps, 10.0)
        self.assertEqual(water.confidence, 0.10)
        self.assertEqual(road.confidence, 0.15)
        self.assertEqual(set(profiles.PROFILES), {"water-v1", "road-v1"})

    def test_water_normalizes_boat_and_rejects_road_classes(self) -> None:
        self.assertEqual(
            profiles.normalize_model_class("boat", "water-v1"),
            {
                "analytics_profile": "water-v1",
                "domain": "water",
                "object_type": "vessel",
                "model_class": "boat",
                "class_name": "vessel",
            },
        )
        for raw in ("car", "truck", "bus", "motorcycle", "bicycle"):
            self.assertIsNone(profiles.normalize_model_class(raw, "water-v1"), raw)

    def test_road_accepts_only_road_baseline_classes(self) -> None:
        for raw in ("car", "truck", "bus", "motorcycle", "bicycle"):
            semantic = profiles.normalize_model_class(raw, "road-v1")
            self.assertIsNotNone(semantic)
            self.assertEqual(semantic["analytics_profile"], "road-v1")
            self.assertEqual(semantic["domain"], "road")
            self.assertEqual(semantic["object_type"], raw)
            self.assertEqual(semantic["model_class"], raw)
            self.assertEqual(semantic["class_name"], raw)
        self.assertIsNone(profiles.normalize_model_class("boat", "road-v1"))

    def test_unknown_profile_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            profiles.get_profile("unknown")

    def test_worker_and_ai_child_share_profile_boundary(self) -> None:
        # AST twin (issue #398 wave 4): the worker cluster and the AI child
        # process must both reference the shared profile boundary helpers and
        # field names (as names, attributes or string-constant dict keys), the
        # child must forward the full semantic mapping as **semantic, and the
        # entrypoint must resolve the profile through get_profile + the
        # --analytics-profile CLI flag without hardcoding a legacy model name.
        worker_trees = worker_source.module_trees()
        child_tree = parse(ROOT / "worker/ubuntu_ai_inference_worker.py")
        entry_tree = parse(ROOT / "worker/ubuntu_worker_entrypoint.py")
        for label, trees in (("worker", worker_trees), ("ai child", [child_tree])):
            with self.subTest(part=label):
                self.assertTrue(
                    worker_source.references_name(trees, "normalize_model_class"),
                    f"{label} must reference normalize_model_class",
                )
                self.assertTrue(
                    worker_source.references_name(trees, "analytics_profile"),
                    f"{label} must reference analytics_profile",
                )
        self.assertTrue(worker_source.references_name(worker_trees, "object_type"))
        self.assertTrue(worker_source.references_name(worker_trees, "model_class"))
        # **semantic forwarding: a keyword argument without a name.
        self.assertTrue(
            any(isinstance(node, ast.keyword) and node.arg is None for node in ast.walk(child_tree)),
            "ai child must forward the semantic mapping as **semantic",
        )
        self.assertIn("--analytics-profile", worker_source.string_constants(entry_tree))
        profile_assignments = [
            node
            for node in ast.walk(entry_tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "profile" for target in node.targets)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "get_profile"
        ]
        self.assertTrue(
            profile_assignments,
            "entrypoint must resolve the profile via profile = get_profile(...)",
        )
        self.assertNotIn(
            "yolo11s",
            [constant.lower() for constant in worker_source.string_constants(entry_tree)],
            "entrypoint must not hardcode the legacy yolo11s model",
        )

    def test_worker_separates_water_continuous_detection_from_road_motion_policy(self) -> None:
        # 398-wave-a: converted from source-text pin (was L87-94) — the
        # water/road split must hold structurally so the #397 decomposition
        # can move the code between files: water runs continuous detection
        # (profile-gated, ROI-filtered), road stays motion-gated
        # (filter_detections_by_motion), water events are vessel-only, and
        # the water branch iterates water_event_candidates(profile,
        # detections) — the structural form of the 2-line indentation-coupled
        # pin (byte-identical twin of the pin converted at
        # test_water_passage.py IntegrationContractTests).
        select_node = worker_source.function_node("select_profile_detections")
        water_node = worker_source.function_node("water_event_candidates")
        self.assertTrue(
            worker_source.contains_expr(select_node, 'profile.domain == "water"'),
            "select_profile_detections must gate water on profile.domain",
        )
        self.assertTrue(
            worker_source.contains_expr(select_node, "filter_detections_by_motion(raw_detections, motion_boxes)"),
            "road path must stay motion-filtered",
        )
        self.assertTrue(
            worker_source.contains_expr(select_node, "detect_vehicles(model, processing_frame)"),
            "water path must run continuous detection",
        )
        self.assertEqual([arg.arg for arg in water_node.args.args], ["profile", "detections"])
        self.assertTrue(
            worker_source.contains_expr(water_node, 'det.get("class_name") != "vessel"'),
            "water events must be vessel-only",
        )
        main_node = worker_source.function_node("main")
        water_branches = [
            node
            for node in ast.walk(main_node)
            if isinstance(node, ast.If)
            and worker_source.contains_expr(node.test, 'profile.domain == "water"')
            and any(
                isinstance(loop, ast.For)
                and isinstance(loop.target, ast.Name)
                and loop.target.id == "vessel"
                and worker_source.dump(loop.iter) == worker_source.expr_dump("water_event_candidates(profile, detections)")
                for branch_stmt in node.body
                for loop in ast.walk(branch_stmt)
            )
        ]
        self.assertTrue(water_branches, "water event branch must iterate water_event_candidates(profile, detections)")

    def test_api_is_additive_and_camera_isolated(self) -> None:
        # AST twin (issue #398 wave 4): the additive per-camera API surface is
        # asserted on the parsed api/app modules — every route must be a
        # decorator path constant, the road1 analytics identity must be a real
        # dict literal entry, the analytics data file must be built from
        # DATA_DIR / f"{camera_id}_{kind}.json", the objects registry
        # migration must be an ALTER TABLE f-string, and the semantic field
        # names must appear as string constants (comment-blind, so a route or
        # identity that survives only in a comment fails).
        trees = [
            parse(API_DIR / name) for name in API_MODULES if (API_DIR / name).exists()
        ]
        paths: set[str] = set()
        for tree in trees:
            paths |= decorator_paths(tree)
        for route in (
            '/api/analytics/{camera_id}/state',
            '/api/analytics/{camera_id}/events',
            '/api/analytics/{camera_id}/roi',
            '/api/analytics/{camera_id}/speed-config',
            '/api/analytics/{camera_id}/speed-lines',
            '/api/analytics/{camera_id}/objects',
            '/api/objects',
            '/api/cam1/state',
            '/api/cam1/events',
            '/api/cam1/objects',
        ):
            self.assertIn(route, paths, f"route {route} is not a decorator path constant")
        road1_identities = []
        for tree in trees:
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "road1"
                        and isinstance(value, ast.Dict)
                    ):
                        fields = {
                            field_key.value: field_value.value
                            for field_key, field_value in zip(value.keys, value.values)
                            if isinstance(field_key, ast.Constant) and isinstance(field_value, ast.Constant)
                        }
                        if (
                            fields.get("analytics_profile") == "road-v1"
                            and fields.get("domain") == "road"
                        ):
                            road1_identities.append(node)
        self.assertTrue(road1_identities, "road1 analytics identity dict entry missing")
        analytics_tree = parse(API_DIR / "analytics.py")
        data_file_expressions = [
            node
            for node in ast.walk(analytics_tree)
            if isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Div)
            and isinstance(node.left, ast.Name)
            and node.left.id == "DATA_DIR"
            and isinstance(node.right, ast.JoinedStr)
            and [
                formatted.value.id
                for formatted in node.right.values
                if isinstance(formatted, ast.FormattedValue)
            ]
            == ["camera_id", "kind"]
        ]
        self.assertTrue(
            data_file_expressions,
            'analytics data file must be DATA_DIR / f"{camera_id}_{kind}.json"',
        )
        all_constants: list[str] = []
        all_joined_parts: list[str] = []
        for tree in trees:
            all_constants.extend(worker_source.string_constants(tree))
            all_joined_parts.extend(worker_source.joined_string_constants(tree))
        self.assertTrue(
            any("ALTER TABLE objects ADD COLUMN" in part for part in all_joined_parts),
            "objects registry migration must stay an ALTER TABLE ADD COLUMN statement",
        )
        for field in ("analytics_profile", "domain", "object_type", "model_class"):
            self.assertIn(field, all_constants, f"semantic field {field} missing from api sources")

    def test_frontends_have_synchronized_road_navigation_and_bounded_road_control(self) -> None:
        # DOM + executed twins (issue #398 wave 4): the road navigation is
        # asserted on parsed anchor attributes (class/href/text), the road
        # page's camera wiring is proven by its executed boot (the recorded
        # fetch calls must address the road1 analytics API, POST the road1
        # preview start endpoint and hit the worker control endpoint exactly
        # once), and the objects registry page must boot-fetch the objects
        # API and expose camera_id/domain filter fields. The rtsp credential
        # ban stays a source regex (SP: security ban, regex IS the artifact).
        for path in FRONTEND_PATHS:
            with self.subTest(page=path.parent.name):
                html = path.read_text(encoding="utf-8")
                self.assertNotRegex(html, r'rtsp://[^\s"\']+:[^\s"\']+@')
        for path in FRONTEND_PATHS[:-1]:
            html = path.read_text(encoding="utf-8")
            self.assertTrue(
                any(anchor_attr(anchor, "href") == "/sea-speed/road/" for anchor in anchor_tags(html)),
                f"{path.parent.name} must link the road page",
            )
        road = FRONTEND_PATHS[-1].read_text(encoding="utf-8")
        full_anchors = re.findall(r"<a\b[^>]*>.*?</a>", road, re.S)
        active_road_links = [
            anchor
            for anchor in full_anchors
            if "objects-link" in (anchor_attr(anchor, "class") or "").split()
            and "road-link" in (anchor_attr(anchor, "class") or "").split()
            and "active" in (anchor_attr(anchor, "class") or "").split()
        ]
        self.assertTrue(
            any(
                anchor_attr(anchor, "href") == "/sea-speed/" and anchor.rstrip("</a>").endswith("Вода")
                for anchor in active_road_links
            ),
            "road page nav must mark /sea-speed/ as the active water link",
        )
        self.assertFalse(
            any(anchor_attr(anchor, "href") == "/sea-speed/road/" for anchor in active_road_links),
            "the road page must not mark itself active",
        )
        evidence = frontend_html.run_inline_scripts(
            frontend_html.ROAD_PAGE, drain_timeouts=True
        )
        analytics_calls = [
            call for call in evidence["fetchCalls"] if call["url"].startswith("/sea-speed/api/analytics/road1")
        ]
        self.assertTrue(analytics_calls, "road boot must address the road1 analytics API")
        self.assertTrue(
            any(
                call["url"] == "/sea-speed/api/cameras/road1/preview/start" and call["method"] == "POST"
                for call in evidence["fetchCalls"]
            ),
            "road boot must POST the road1 preview start endpoint",
        )
        worker_control = [
            call for call in evidence["fetchCalls"] if call["url"] == "/sea-speed/api/worker/control/road1"
        ]
        self.assertEqual(
            len(worker_control),
            1,
            f"the road worker control endpoint must be wired exactly once: {evidence['fetchCalls']}",
        )
        self.assertNotIn("/v1/road1/", road)
        self.assertNotIn("10.123.239.101", road)
        self.assertNotIn("SEA_SPEED_API_TOKEN", road)
        objects_html = FRONTEND_PATHS[1].read_text(encoding="utf-8")
        objects_evidence = frontend_html.run_inline_scripts(
            source=FRONTEND_PATHS[1], scenario=BOOT_SCENARIO
        )
        self.assertTrue(
            any(url.startswith("/sea-speed/api/objects") for url in objects_evidence["fetchUrls"]),
            f"objects page must boot-fetch the objects API: {objects_evidence['fetchUrls']}",
        )
        for field in ("camera_id", "domain"):
            self.assertRegex(objects_html, rf'<[a-zA-Z]+\b[^>]*\bname="{field}"')

    def test_runtime_assets_do_not_embed_protected_road_source(self) -> None:
        # AST twin for the configure script's road1 wiring (comparison
        # expression + constants); the rtsp/mostdef.ru bans stay source
        # regexes/substring bans (SP: security bans).
        files = [
            ROOT / "deploy/worker/ubuntu/road-worker.env.example",
            CONFIGURE,
            ROOT / "deploy/worker/ubuntu/sea-speed-road-worker.service.template",
        ]
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"rtsp://[^\s\"']+:[^\s\"']+@")
        configure_tree = parse(files[1])
        self.assertTrue(
            worker_source.contains_expr(configure_tree, 'item.get("camera_id") == "road1"'),
            "configure must select the road1 catalog entry by camera_id comparison",
        )
        self.assertIn("/preview_road1", worker_source.string_constants(configure_tree))
        self.assertTrue(
            any("worker.env must be mode 600" in constant for constant in worker_source.string_constants(configure_tree))
        )
        road_example = files[0].read_text(encoding="utf-8")
        self.assertNotIn("https://mostdef.ru/sea-speed/api/analytics/road1", road_example)
        self.assertIn("private Worker->VPS M2M endpoint", road_example)

    def test_road_worker_api_urls_derive_only_from_exact_private_cam1_m2m_endpoint(self) -> None:
        state_url, event_url = configure.road_worker_api_urls(
            {"SEA_SPEED_API_URL": "http://10.123.239.101:18080/api/cam1/state"}
        )
        self.assertEqual(state_url, "http://10.123.239.101:18080/api/analytics/road1/state")
        self.assertEqual(event_url, "http://10.123.239.101:18080/api/analytics/road1/events")
        for invalid in (
            "https://mostdef.ru/sea-speed/api/cam1/state",
            "http://user:pass@10.123.239.101:18080/api/cam1/state",
            "http://203.0.113.10:18080/api/cam1/state",
            "http://127.0.0.1:18080/api/cam1/state",
            "http://10.123.239.101/api/cam1/state",
            "http://10.123.239.101:18080/api/cam1/events",
            "http://10.123.239.101:18080/api/cam1/state?redirect=1",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(SystemExit):
                    configure.road_worker_api_urls({"SEA_SPEED_API_URL": invalid})

    def test_configure_profiles_writes_private_road_m2m_urls_and_mode_600(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            install_root = root / "install"
            config_root = install_root / "shared/config"
            config_root.mkdir(parents=True)
            worker_env = config_root / "worker.env"
            worker_env.write_text(
                "SEA_SPEED_API_URL=http://10.123.239.101:18080/api/cam1/state\n"
                "SEA_SPEED_API_TOKEN=test-token\n"
                "FRAME_WIDTH=704\n"
                "FRAME_HEIGHT=576\n",
                encoding="utf-8",
            )
            os.chmod(worker_env, 0o600)
            catalog = root / "camera-preview-catalog.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema": "sea_speed_camera_preview_catalog_v1",
                        "cameras": [
                            {
                                "camera_id": "road1",
                                "source": "rtsp://10.123.239.102:8555/preview_road1",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(CONFIGURE),
                    "--install-root",
                    str(install_root),
                    "--preview-catalog",
                    str(catalog),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("ROAD_API=protected_private_worker_ingress", result.stdout)
            road_env = config_root / "road-worker.env"
            water_values = configure.read_env(worker_env)
            road_values = configure.read_env(road_env)
            self.assertEqual(water_values["ANALYTICS_PROFILE"], "water-v1")
            self.assertEqual(water_values["YOLO_CONFIDENCE"], "0.10")
            self.assertEqual(water_values["YOLO_IMAGE_SIZE"], "960")
            self.assertEqual(road_values["ANALYTICS_PROFILE"], "road-v1")
            self.assertEqual(road_values["YOLO_CONFIDENCE"], "0.15")
            self.assertEqual(road_values["YOLO_IMAGE_SIZE"], "960")
            self.assertEqual(road_values["SEA_SPEED_API_URL"], "http://10.123.239.101:18080/api/analytics/road1/state")
            self.assertEqual(road_values["SEA_SPEED_EVENT_API_URL"], "http://10.123.239.101:18080/api/analytics/road1/events")
            self.assertEqual(road_values["HLS_URL"], "rtsp://10.123.239.102:8555/preview_road1")
            self.assertEqual(stat.S_IMODE(road_env.stat().st_mode), 0o600)
            self.assertNotIn("mostdef.ru", road_env.read_text(encoding="utf-8"))

    def test_model_preparation_is_digest_bound_cuda_fail_closed(self) -> None:
        # AST twin (issue #398 wave 4): the digest binding, CUDA self-test and
        # predict parameters live inside the python -c snippet string
        # constants — asserted on the parsed constants; the download/yolo11
        # bans are asserted over every code token (constants, names,
        # attributes, argument names), so a ban violation survives neither in
        # a literal nor in an identifier, while comments stay exempt.
        prepare_tree = parse(ROOT / "deploy/worker/ubuntu/prepare-yolo-model.py")
        constants = worker_source.string_constants(prepare_tree)
        for marker in (
            "expected-sha256",
            "torch.cuda.is_available()",
            "YOLO26x CUDA load/self-test failed",
            "imgsz=960",
            "conf=0.15",
        ):
            self.assertTrue(
                any(marker in constant for constant in constants),
                f"prepare-yolo-model must carry {marker!r} in a code constant",
            )
        tokens: set[str] = set(constants)
        for node in ast.walk(prepare_tree):
            if isinstance(node, ast.Name):
                tokens.add(node.id)
            elif isinstance(node, ast.Attribute):
                tokens.add(node.attr)
            elif isinstance(node, ast.arg):
                tokens.add(node.arg)
        lowered = {token.lower() for token in tokens}
        for banned in ("download", "yolo11"):
            self.assertFalse(
                any(banned in token for token in lowered),
                f"prepare-yolo-model must not reference {banned!r} in code",
            )

    def test_exact_artifacts_include_profiles_and_road_but_not_model_binaries(self) -> None:
        # AST twin: the artifact manifests must reference the road frontend,
        # profile module and deploy assets as string constants, and must
        # exclude model binary suffixes by exact constant.
        build_tree = parse(ROOT / "scripts/quality/build_exact_artifacts.py")
        validate_tree = parse(ROOT / "scripts/quality/validate_exact_artifacts.py")
        for marker in (
            "frontend/sea-speed/road/index.html",
            "worker/analytics_profiles.py",
            "deploy/worker/ubuntu/sea-speed-road-worker.service.template",
            "deploy/worker/ubuntu/configure-analytics-profiles.py",
            "deploy/worker/ubuntu/prepare-yolo-model.py",
        ):
            for label, tree in (("build", build_tree), ("validate", validate_tree)):
                self.assertIn(
                    marker,
                    worker_source.string_constants(tree),
                    f"{label} manifest must reference {marker}",
                )
        for suffix in (".pt", ".onnx", ".engine"):
            for label, tree in (("build", build_tree), ("validate", validate_tree)):
                self.assertIn(
                    suffix,
                    worker_source.string_constants(tree),
                    f"{label} manifest must exclude {suffix} binaries",
                )

    def test_vps_deployer_tracks_road_frontend_transactionally(self) -> None:
        # Structural shell twin (issue #398 wave 4): comment lines are
        # stripped before scanning, so the road frontend transaction must
        # hold in real code — a dedicated ensure function, a .next staging
        # path paired with an atomic mv, the public URL probe with the Road
        # frontend label, and the release evidence recording the road state.
        text = (ROOT / "deploy/vps/deploy.sh").read_text(encoding="utf-8")
        code = code_without_comment_lines(text)
        functions = set(re.findall(r"^(\w+)\(\) \{", code, re.M))
        self.assertIn("ensure_current_release_has_road_frontend", functions)
        self.assertIn('ROAD_FRONTEND_TARGET="${SEA_SPEED_ROAD_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/road/index.html}"', code)
        self.assertIn('ROAD_FRONTEND_URL="${SEA_SPEED_ROAD_FRONTEND_URL:-https://mostdef.ru/sea-speed/road/}"', code)
        self.assertIn("${ROAD_FRONTEND_TARGET}.next", code)
        self.assertIn('mv -f "${ROAD_FRONTEND_TARGET}.next" "$ROAD_FRONTEND_TARGET"', code)
        self.assertIn('verify_public_url "Road frontend" "$ROAD_FRONTEND_URL"', code)
        self.assertIn('{"name": "road_frontend_release_state", "status": "passed"}', code)

    def test_ubuntu_service_is_isolated_but_shares_runtime_and_models(self) -> None:
        # Structural twins: the systemd unit's Environment directives are
        # parsed (not substring-matched), the ExecStart must run the pinned
        # runtime venv python with the road heartbeat, and the installer must
        # symlink the SAME shared models store into both the water runtime
        # state root and the road runtime root.
        unit = (ROOT / "deploy/worker/ubuntu/sea-speed-road-worker.service.template").read_text(encoding="utf-8")
        unit_lines = [
            line.strip()
            for line in unit.splitlines()
            if line.strip() and not line.strip().startswith(("#", ";"))
        ]
        environment: dict[str, str] = {}
        for line in unit_lines:
            if line.startswith("Environment="):
                key, _, value = line[len("Environment=") :].partition("=")
                environment[key] = value
        self.assertEqual(environment.get("ANALYTICS_PROFILE"), "road-v1")
        self.assertEqual(environment.get("CAMERA_ID"), "road1")
        exec_start = next(line for line in unit_lines if line.startswith("ExecStart="))
        self.assertIn("__RUNTIME_ID__/venv/bin/python", exec_start)
        self.assertIn("road-worker-heartbeat.json", exec_start)
        install = (ROOT / "deploy/worker/ubuntu/install-systemd.sh").read_text(encoding="utf-8")
        install_code = code_without_comment_lines(install)
        self.assertIn('ln -sfn "$install_root/shared/models" "$runtime_state_root/models"', install_code)
        self.assertIn('ln -sfn "$install_root/shared/models" "$road_runtime_root/models"', install_code)
        self.assertIn("road-worker.env", install_code)


if __name__ == "__main__":
    unittest.main()
