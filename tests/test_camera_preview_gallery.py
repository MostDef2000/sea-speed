from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Issue #396 wave 1: preview/snapshot tuning constants moved to config.py.
# Issue #396 wave 4: the camera preview/snapshot service slice moved to
# camera_preview.py. Issue #398 wave 4: the API sources are PARSED once at
# import (a syntax error fails the whole module) and every retired
# source-text pin is asserted on the AST — function slices by stable def
# name, decorator route constants, call/keyword shapes — comment-blind and
# rename-tolerant. The frontend pins became executed twins: the cameras page
# and the operator page run their real inline scripts under the html shim
# (tests/support/frontend_html.py) and the batch preview flow is driven end
# to end. Shell/renderer/SDD-prose pins stay source scans (SP/SS/NO-CHANGE —
# see specs/398-wave4 mapping table).
API_PATHS = (
    ROOT / "api/app/main.py",
    ROOT / "api/app/camera_preview.py",
    ROOT / "api/app/identity.py",
    ROOT / "api/app/config.py",
)
OPERATOR = (ROOT / "frontend/sea-speed/index.html").read_text(encoding="utf-8-sig")
CAMERAS = (ROOT / "frontend/sea-speed/cameras/index.html").read_text(encoding="utf-8-sig")
RELAY = (ROOT / "deploy/worker/ubuntu/camera-preview-relay.sh").read_text(encoding="utf-8-sig")
# Issue #442: the preview config+catalog literals are owned by the canonical
# renderer now; the shell keeps structural pins only.
RENDERER_SRC = (ROOT / "scripts/operations/mediamtx_path_config.py").read_text(encoding="utf-8-sig")
DEPLOY = (ROOT / "deploy/vps/deploy.sh").read_text(encoding="utf-8-sig")
SPEC = (ROOT / "specs/002-camera-preview-gallery/spec.md").read_text(encoding="utf-8-sig")
PLAN = (ROOT / "specs/002-camera-preview-gallery/plan.md").read_text(encoding="utf-8-sig")
TASKS = (ROOT / "specs/002-camera-preview-gallery/tasks.md").read_text(encoding="utf-8-sig")
QUICKSTART = (ROOT / "specs/002-camera-preview-gallery/quickstart.md").read_text(encoding="utf-8-sig")

from tests.support import frontend_html, worker_source  # noqa: E402  (needs ROOT on sys.path)

WATER_PAGE = ROOT / "frontend/sea-speed/index.html"
CAMERAS_PAGE = ROOT / "frontend/sea-speed/cameras/index.html"


def parse_module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


API_TREES = [parse_module(path) for path in API_PATHS if path.exists()]
RENDERER_TREE = parse_module(ROOT / "scripts/operations/mediamtx_path_config.py")


def api_fn(name: str):
    for tree in API_TREES:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return node
    raise AssertionError(f"api function {name!r} not found")


def api_has_expr(snippet: str) -> bool:
    return any(worker_source.contains_expr(tree, snippet) for tree in API_TREES)


def fn_strings(fn) -> set[str]:
    return set(worker_source.string_constants(fn))


def fn_dict_keys(scope) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(scope):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def dict_value(scope, key: str):
    for node in ast.walk(scope):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == key and isinstance(v, ast.Constant):
                    return v.value
    return None


def has_payload_get(scope, field: str) -> bool:
    """True if ``payload.get("<field>")`` is called anywhere in scope — the
    request-body shape the API must never accept for the private source."""
    for node in ast.walk(scope):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "payload"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == field
        ):
            return True
    return False


def calls_named(scope, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(scope) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name]


def popen_call(scope):
    for node in ast.walk(scope):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Popen":
            return node
    return None


def has_keyword(scope, name: str) -> bool:
    return any(isinstance(kw, ast.keyword) and kw.arg == name for node in ast.walk(scope) for kw in getattr(node, "keywords", []))


def decorator_paths(tree) -> set[str]:
    paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    for argument in decorator.args:
                        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                            paths.add(argument.value)
    return paths


def anchor_tags(html: str) -> list[str]:
    return re.findall(r"<a\b[^>]*>[^<]*</a>", html)


def anchor_attr(tag: str, name: str) -> str | None:
    match = re.search(rf'\b{name}="([^"]*)"', tag)
    return match.group(1) if match else None


def anchor_text(tag: str) -> str:
    return re.sub(r"^<a\b[^>]*>", "", tag).removesuffix("</a>")


# Executed water-page media twin: the boot connectStream timeout is drained,
# the recorded HLS MEDIA_ATTACHED handlers fire loadSource, and the recorded
# sources prove the operator stream uses the protected media path (and never
# the retired /cams/hls/ path).
WATER_MEDIA_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await new Promise((r) => setImmediate(r));
  const instances = __record.hlsInstances;
  assert(instances.length >= 1, "no HLS instance was created at boot");
  for (const inst of instances) {
    for (const handler of inst.handlers.hlsMediaAttached || []) await handler();
  }
  const sources = instances.flatMap((inst) => inst.sources);
  assert(
    sources.includes("/sea-speed/media/cam1/index.m3u8"),
    "HLS loadSource must use the protected media path; got " + JSON.stringify(sources)
  );
  assert(
    sources.every((source) => !source.includes("/cams/hls/")),
    "the retired camera media path must not be loaded"
  );
  assert(window.hls === window.waterHls, "window.hls must alias the operator player");
  console.log("###" + JSON.stringify({
    sources,
    attached: instances.flatMap((inst) => inst.attached.map((el) => el && el.id)),
    fetchUrls: __record.fetch.map((c) => c.url),
  }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""

# Fabricates a full preview card subtree for the cameras grid (updateUi walks
# [data-frame]/[data-state]/[data-error]/[data-play]/[data-stop] on every
# catalog camera; attachActivePlayer appends the created video to [data-frame]).
CAMERAS_CARD_FACTORY = """
  const mkCard = (id) => {
    const frame = {
      appended: [],
      appendChild(el) { this.appended.push(el); },
      classList: { add() {}, remove() {}, toggle() {} },
    };
    const card = {
      __query: {
        "[data-frame]": frame,
        "[data-snapshot]": { dataset: {}, src: "" },
        "[data-snapshot-time]": { textContent: "" },
        "[data-state]": { textContent: "", className: "" },
        "[data-error]": { textContent: "" },
        "[data-play]": { disabled: false },
        "[data-stop]": { disabled: false },
      },
      querySelector(sel) {
        const q = this.__query;
        return q && Object.prototype.hasOwnProperty.call(q, sel) ? q[sel] : null;
      },
    };
    const grid = __record.elements.cameraGrid;
    grid.__query = grid.__query || {};
    grid.__query['[data-camera-id="' + id + '"]'] = card;
    return card.__query["[data-snapshot]"];
  };
"""

# Executed cameras-boot twin: web storage stays undefined in the page scope,
# boot issues zero POSTs (no autostart), the catalog endpoint is fetched
# same-origin with cache:"no-store" via the api() helper, the grid renders
# the runtime catalog cards with the last-good snapshot image, the batch
# progress shows the VPS snapshot count, the recorded 3 s interval polls the
# preview status endpoint, and re-driving loadCatalog with an active preview
# auto-attaches the HLS player to the created video element.
CAMERAS_BOOT_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  assert(typeof localStorage === "undefined", "localStorage must not exist in the page scope");
  assert(typeof sessionStorage === "undefined", "sessionStorage must not exist in the page scope");
  assert(typeof indexedDB === "undefined", "indexedDB must not exist in the page scope");
  assert(typeof caches === "undefined", "caches must not exist in the page scope");
  const posts = __record.fetch.filter((c) => (c.options.method || "GET") === "POST");
  assert(posts.length === 0, "boot must not POST (no autostart): " + JSON.stringify(posts.map((p) => p.url)));
  const catalogFetch = __record.fetch.find((c) => c.url === "/sea-speed/api/cameras");
  assert(catalogFetch, "catalog endpoint not fetched at boot");
  assert(catalogFetch.options.credentials === "same-origin", "catalog fetch must be same-origin");
  assert(catalogFetch.options.cache === "no-store", "catalog fetch must be no-store");
  const gridHTML = __record.elements.cameraGrid.innerHTML;
  assert(gridHTML.includes('data-camera-id="cam-a"'), "catalog render missing the cam-a card");
  assert(gridHTML.includes("<img data-snapshot"), "catalog render missing the snapshot image");
  assert(
    __record.elements.batchProgress.textContent.includes("Последних кадров на VPS: 1 / 2"),
    "last-good snapshot progress not shown: " + __record.elements.batchProgress.textContent
  );
  const statusInterval = __record.intervals.find((entry) => entry[1] === 3000);
  assert(statusInterval, "preview status polling interval missing");
  const before = __record.fetch.length;
  await statusInterval[0]();
  await new Promise((r) => setImmediate(r));
  assert(
    __record.fetch.slice(before).some((c) => c.url === "/sea-speed/api/cameras/preview"),
    "the status interval must poll the preview status endpoint"
  );
""" + CAMERAS_CARD_FACTORY + """
  mkCard("cam-a");
  await loadCatalog();
  const video = activeVideo;
  assert(video, "loadCatalog with an active preview must attach the player");
  const instance = __record.hlsInstances[__record.hlsInstances.length - 1];
  assert(
    instance && instance.sources.length === 1 && instance.sources[0].startsWith("/sea-speed/media/camera-preview/sess-a/index.m3u8"),
    "HLS loadSource must use the active preview url: " + JSON.stringify(instance && instance.sources)
  );
  assert(instance.attached.includes(video), "HLS must attach to the created video element");
  console.log("###" + JSON.stringify({ fetchUrls: __record.fetch.map((c) => c.url) }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""

# Executed batch-flow twin: camera A's start fails (URL-substring response),
# camera B runs the full single-active cycle. The recorded POST order proves
# the sequential one-active contract (start -> commit -> stop, next camera
# only after the previous finished, operator stopAllPreviews last), the
# commit waits for the pinned 3 s playback advance (rAF bump +1 s per frame
# -> commit at exactly 3), the commit response updates the card snapshot
# image, and the failed camera is recorded without aborting the catalog.
CAMERAS_FLOW_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
""" + CAMERAS_CARD_FACTORY + """
  const snapshotA = mkCard("cam-a");
  const snapshotB = mkCard("cam-b");
  __rafBump = () => { if (activeVideo) activeVideo.currentTime += 1; };
  let advanceAtCommit = null;
  const realCommit = commitActiveSnapshot;
  commitActiveSnapshot = async (...args) => {
    advanceAtCommit = activeVideo ? activeVideo.currentTime : null;
    return realCommit(...args);
  };
  await runPreviewAll();
  await stopAllPreviews();
  const posts = __record.fetch.filter((c) => (c.options.method || "GET") === "POST").map((c) => c.url);
  assert(posts.length === 5, "unexpected POST sequence: " + JSON.stringify(posts));
  assert(posts[0].includes("/cam-a/preview/start"), "first POST must be cam-a start: " + posts[0]);
  assert(posts[1].includes("/cam-b/preview/start"), "second POST must be cam-b start: " + posts[1]);
  assert(posts[2].includes("/cam-b/snapshot/commit?session_id=sess-b"), "third POST must be the cam-b commit: " + posts[2]);
  assert(posts[3] === "/sea-speed/api/cameras/preview/stop", "batch tail must stop the preview: " + posts[3]);
  assert(posts[4] === "/sea-speed/api/cameras/preview/stop", "operator stopAllPreviews must stop again: " + posts[4]);
  assert(advanceAtCommit === 3, "commit must wait for the pinned 3 s playback advance, got " + advanceAtCommit);
  assert(snapshotB.src === "/sea-speed/api/cameras/cam-b/snapshot", "commit response must update the card snapshot image");
  assert(snapshotA.src === "", "a failed camera must not commit a snapshot");
  assert(cameraErrors.get("cam-a") === "preview start failed", "failed start must be recorded on the camera: " + JSON.stringify([...cameraErrors.entries()]));
  assert(!cameraErrors.has("cam-b"), "the healthy camera must stay error-free");
  assert(
    __record.elements.batchProgress.textContent.includes("Последних кадров на VPS: 1 / 2"),
    "batch progress must fall back to the VPS snapshot count: " + __record.elements.batchProgress.textContent
  );
  console.log("###" + JSON.stringify({
    posts,
    advanceAtCommit,
    snapshotSrcA: snapshotA.src,
    snapshotSrcB: snapshotB.src,
    errors: [...cameraErrors.entries()],
    batchProgress: __record.elements.batchProgress.textContent,
  }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""

# Stable-wait timeout twin: performance.now is shifted past the deadline so
# the rAF stabilization loop resolves false on its first tick — the camera
# must be recorded as "не успело стабилизироваться" and no snapshot commit
# may be issued for it.
CAMERAS_STABLE_TIMEOUT_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
""" + CAMERAS_CARD_FACTORY + """
  mkCard("cam-a");
  const realCommit = commitActiveSnapshot;
  commitActiveSnapshot = async () => false;
  const realNow = performance.now.bind(performance);
  performance.now = () => realNow() + 1e9;
  await runPreviewAll();
  const posts = __record.fetch.filter((c) => (c.options.method || "GET") === "POST").map((c) => c.url);
  assert(
    posts.length === 2 && posts[0].includes("/cam-a/preview/start") && posts[1] === "/sea-speed/api/cameras/preview/stop",
    "a camera that never stabilizes must not commit: " + JSON.stringify(posts)
  );
  assert(
    cameraErrors.get("cam-a") === "Видео не успело стабилизироваться",
    "stable timeout must be recorded: " + JSON.stringify([...cameraErrors.entries()])
  );
  console.log("###" + JSON.stringify({ errors: [...cameraErrors.entries()], posts }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""

# Video-ready timeout twin: the created player video is patched to never be
# ready (readyState 0 / videoWidth 0), so waitForVideoFrame can only resolve
# via its recorded timeout — draining the recorded timers must produce the
# pinned "не успело показать кадр" error and no commit.
CAMERAS_VIDEO_READY_TIMEOUT_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
""" + CAMERAS_CARD_FACTORY + """
  mkCard("cam-a");
  const realCreate = document.createElement.bind(document);
  document.createElement = (tag) => {
    const element = realCreate(tag);
    if (String(tag).toLowerCase() === "video") { element.readyState = 0; element.videoWidth = 0; }
    return element;
  };
  const run = runPreviewAll();
  for (let i = 0; i < 5; i++) await new Promise((r) => setImmediate(r));
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await run;
  const posts = __record.fetch.filter((c) => (c.options.method || "GET") === "POST").map((c) => c.url);
  assert(
    posts.length === 2 && posts[0].includes("/cam-a/preview/start") && posts[1] === "/sea-speed/api/cameras/preview/stop",
    "a camera whose video never readies must not commit: " + JSON.stringify(posts)
  );
  assert(
    cameraErrors.get("cam-a") === "Видео не успело показать кадр",
    "video-ready timeout must be recorded: " + JSON.stringify([...cameraErrors.entries()])
  );
  console.log("###" + JSON.stringify({ errors: [...cameraErrors.entries()], posts }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""

CAM_A_PREVIEW_FAIL = {"match": "cam-a/preview/start", "ok": False, "json": {"detail": "preview start failed"}}
CAM_A_PREVIEW_OK = {
    "match": "cam-a/preview/start",
    "json": {
        "preview": {
            "camera_id": "cam-a",
            "session_id": "sess-a",
            "hls_url": "/sea-speed/media/camera-preview/sess-a/index.m3u8",
            "display_name": "Cam A",
            "expires_at": "2026-10-29T12:00:00Z",
        }
    },
}
CAM_B_PREVIEW_OK = {
    "match": "cam-b/preview/start",
    "json": {
        "preview": {
            "camera_id": "cam-b",
            "session_id": "sess-b",
            "hls_url": "/sea-speed/media/camera-preview/sess-b/index.m3u8",
            "display_name": "Cam B",
            "expires_at": "2026-10-29T12:00:00Z",
        }
    },
}
COMMIT_OK = {
    "match": "snapshot/commit",
    "json": {"snapshot": {"available": True, "url": "/sea-speed/api/cameras/cam-b/snapshot", "captured_at": "2026-10-29T12:00:00Z"}},
}
STOP_OK = {"match": "/preview/stop", "json": {}}
STATUS_EMPTY = {"match": "/api/cameras/preview", "json": {"active": None}}
CATALOG_TWO = {
    "match": "/api/cameras",
    "json": {
        "cameras": [
            {"camera_id": "cam-a", "display_name": "Cam A"},
            {"camera_id": "cam-b", "display_name": "Cam B"},
        ],
        "active": None,
    },
}
CATALOG_ONE = {
    "match": "/api/cameras",
    "json": {"cameras": [{"camera_id": "cam-a", "display_name": "Cam A"}], "active": None},
}
CATALOG_WITH_SNAPSHOT_AND_ACTIVE = {
    "match": "/api/cameras",
    "json": {
        "cameras": [
            {
                "camera_id": "cam-a",
                "display_name": "Cam A",
                "snapshot": {"available": True, "url": "/sea-speed/api/cameras/cam-a/snapshot", "captured_at": "2026-10-29T11:00:00Z"},
            },
            {"camera_id": "cam-b", "display_name": "Cam B"},
        ],
        "active": {
            "camera_id": "cam-a",
            "session_id": "sess-a",
            "hls_url": "/sea-speed/media/camera-preview/sess-a/index.m3u8",
            "display_name": "Cam A",
            "expires_at": "2026-10-29T12:00:00Z",
        },
    },
}


class CameraPreviewGalleryTests(unittest.TestCase):
    def test_python_and_shell_sources_are_structurally_valid(self) -> None:
        # The API/renderer trees are parsed once at import: a syntax error in
        # any of them fails this module before any assertion runs.
        self.assertEqual(len(API_TREES), 4)
        self.assertTrue(RENDERER_TREE.body)
        self.assertTrue(RELAY.startswith("#!/usr/bin/env bash\nset -Eeuo pipefail"))
        self.assertTrue(DEPLOY.startswith("#!/usr/bin/env bash\nset -Eeuo pipefail"))

    def test_operator_preserves_objects_link_and_adds_cameras_link(self) -> None:
        # DOM twins: parsed anchor attributes (order-independent) plus the
        # static layout/canvas markup attributes; the HLS/state wiring is
        # proven by the executed water boot below (protected media path +
        # state fetch + no retired path).
        anchors = anchor_tags(OPERATOR)
        self.assertTrue(
            any(
                "objects-link" in (anchor_attr(anchor, "class") or "").split()
                and anchor_attr(anchor, "href") == "/sea-speed/objects/"
                and anchor_text(anchor) == "Реестр объектов"
                for anchor in anchors
            ),
            "operator nav must keep the objects link",
        )
        self.assertTrue(
            any(
                "objects-link" in (anchor_attr(anchor, "class") or "").split()
                and "cameras-link" in (anchor_attr(anchor, "class") or "").split()
                and anchor_attr(anchor, "href") == "/sea-speed/cameras/"
                and anchor_text(anchor) == "Камеры"
                for anchor in anchors
            ),
            "operator nav must add the cameras link",
        )
        for attribute in (
            'data-layout="primary-camera"',
            'data-layout="clean-live"',
            'id="roiCanvas"',
            'id="speedLinesCanvas"',
        ):
            self.assertIn(attribute, OPERATOR)
        evidence = frontend_html.run_inline_scripts(source=WATER_PAGE, scenario=WATER_MEDIA_SCENARIO)
        self.assertEqual(evidence["sources"], ["/sea-speed/media/cam1/index.m3u8"])
        self.assertIn("waterMainVideo", evidence["attached"])
        self.assertIn("/sea-speed/api/cam1/state", evidence["fetchUrls"])

    def test_gallery_uses_runtime_catalog_and_has_no_native_rtsp_source(self) -> None:
        # Executed boot twin: the catalog endpoint is fetched same-origin with
        # cache:"no-store" through the api() helper, the grid renders the
        # runtime catalog, and the status endpoint is polled. The
        # preview/start and snapshot/commit URL shapes are exercised by the
        # batch-flow test. The rtsp/private-subnet bans stay source regexes
        # (SP: security bans).
        evidence = frontend_html.run_inline_scripts(
            source=CAMERAS_PAGE,
            scenario=CAMERAS_BOOT_SCENARIO,
            responses=[STATUS_EMPTY, CATALOG_WITH_SNAPSHOT_AND_ACTIVE],
        )
        self.assertIn("/sea-speed/api/cameras", evidence["fetchUrls"])
        self.assertIn("/sea-speed/api/cameras/preview", evidence["fetchUrls"])
        self.assertNotIn("rtsp://", CAMERAS)
        self.assertNotRegex(CAMERAS, r"192\.168\.88\.\d+")
        self.assertIn('id="cameraGrid"', CAMERAS)

    def test_gallery_does_not_autostart_preview(self) -> None:
        # Executed twin: boot records zero POSTs (no startPreview/autoplay
        # path can have run), the catalog is loaded, and the active preview
        # from the catalog attaches the player only through loadCatalog.
        frontend_html.run_inline_scripts(
            source=CAMERAS_PAGE,
            scenario=CAMERAS_BOOT_SCENARIO,
            responses=[STATUS_EMPTY, CATALOG_WITH_SNAPSHOT_AND_ACTIVE],
        )

    def test_gallery_batch_preview_is_sequential_and_operator_controllable(self) -> None:
        # Markup ids stay structural; the sequential one-active flow, the
        # per-camera ordering and the operator stop control are proven by the
        # executed batch flow (the POST order rules out any Promise.all
        # parallelism by construction).
        for element_id in ("previewAllButton", "stopAllButton", "batchProgress"):
            self.assertIn(f'id="{element_id}"', CAMERAS)
        evidence = frontend_html.run_inline_scripts(
            source=CAMERAS_PAGE,
            scenario=CAMERAS_FLOW_SCENARIO,
            responses=[CAM_A_PREVIEW_FAIL, CAM_B_PREVIEW_OK, COMMIT_OK, STOP_OK, CATALOG_TWO],
        )
        self.assertEqual(len(evidence["posts"]), 5)
        self.assertIn("cam-a/preview/start", evidence["posts"][0])
        self.assertIn("cam-b/preview/start", evidence["posts"][1])

    def test_gallery_batch_snapshot_waits_for_actual_playback_progress(self) -> None:
        # Executed twins: the commit fires at exactly the pinned 3 s playback
        # advance (rAF-driven, not a dwell timer), and a camera whose
        # stabilization deadline passes is recorded with the pinned error and
        # never commits.
        evidence = frontend_html.run_inline_scripts(
            source=CAMERAS_PAGE,
            scenario=CAMERAS_FLOW_SCENARIO,
            responses=[CAM_A_PREVIEW_FAIL, CAM_B_PREVIEW_OK, COMMIT_OK, STOP_OK, CATALOG_TWO],
        )
        self.assertEqual(evidence["advanceAtCommit"], 3)
        stable = frontend_html.run_inline_scripts(
            source=CAMERAS_PAGE,
            scenario=CAMERAS_STABLE_TIMEOUT_SCENARIO,
            responses=[CAM_A_PREVIEW_OK, STOP_OK, CATALOG_ONE],
        )
        self.assertEqual(stable["errors"], [["cam-a", "Видео не успело стабилизироваться"]])
        self.assertEqual(len(stable["posts"]), 2)
        # Regression guards: the retired frame-dwell wait must not return.
        self.assertNotIn("const BATCH_FRAME_DWELL_MS=1200;", CAMERAS)
        self.assertNotIn("await delay(BATCH_FRAME_DWELL_MS);", CAMERAS)

    def test_gallery_uses_vps_last_good_snapshot_and_no_browser_persistent_storage(self) -> None:
        # Executed twins: the boot scenario proves web storage is undefined in
        # the page scope, the catalog snapshot metadata drives the batch
        # progress ("1 / 2") and the <img data-snapshot> render; the flow
        # scenario proves the commit response updates the card image via
        # setSnapshotMeta (server-side last-good store, no canvas capture).
        frontend_html.run_inline_scripts(
            source=CAMERAS_PAGE,
            scenario=CAMERAS_BOOT_SCENARIO,
            responses=[STATUS_EMPTY, CATALOG_WITH_SNAPSHOT_AND_ACTIVE],
        )
        evidence = frontend_html.run_inline_scripts(
            source=CAMERAS_PAGE,
            scenario=CAMERAS_FLOW_SCENARIO,
            responses=[CAM_A_PREVIEW_FAIL, CAM_B_PREVIEW_OK, COMMIT_OK, STOP_OK, CATALOG_TWO],
        )
        self.assertEqual(evidence["snapshotSrcB"], "/sea-speed/api/cameras/cam-b/snapshot")
        self.assertEqual(evidence["snapshotSrcA"], "")
        # Regression guards: snapshots come from the VPS store, not a canvas.
        self.assertNotIn("<canvas data-snapshot", CAMERAS)
        self.assertNotIn("context.drawImage(activeVideo", CAMERAS)

    def test_gallery_failed_batch_camera_does_not_abort_remaining_catalog(self) -> None:
        # Executed twin: cam-a's start fails, cam-b still runs its full cycle
        # (start -> commit -> stop) and the failure lands in cameraErrors.
        evidence = frontend_html.run_inline_scripts(
            source=CAMERAS_PAGE,
            scenario=CAMERAS_FLOW_SCENARIO,
            responses=[CAM_A_PREVIEW_FAIL, CAM_B_PREVIEW_OK, COMMIT_OK, STOP_OK, CATALOG_TWO],
        )
        self.assertEqual(evidence["errors"], [["cam-a", "preview start failed"]])
        self.assertIn("cam-b/snapshot/commit", evidence["posts"][2])
        video_ready = frontend_html.run_inline_scripts(
            source=CAMERAS_PAGE,
            scenario=CAMERAS_VIDEO_READY_TIMEOUT_SCENARIO,
            responses=[CAM_A_PREVIEW_OK, STOP_OK, CATALOG_ONE],
        )
        self.assertEqual(video_ready["errors"], [["cam-a", "Видео не успело показать кадр"]])
        self.assertEqual(len(video_ready["posts"]), 2)

    def test_api_exposes_catalog_preview_and_snapshot_contract(self) -> None:
        routes = set().union(*(decorator_paths(tree) for tree in API_TREES))
        for route in (
            "/api/cameras",
            "/api/cameras/{camera_id}/snapshot",
            "/api/cameras/{camera_id}/snapshot/commit",
            "/api/cameras/preview",
            "/api/cameras/{camera_id}/preview/start",
            "/api/cameras/preview/stop",
        ):
            self.assertIn(route, routes)
        self.assertTrue(api_has_expr('entry["camera_id"] == camera_id'))
        self.assertTrue(api_has_expr('{"max_active": 1, "ttl_sec": CAMERA_PREVIEW_TTL_SEC}'))
        # The API never accepts a client-supplied source/rtsp_url field.
        for tree in API_TREES:
            self.assertFalse(has_payload_get(tree, "source"))
            self.assertFalse(has_payload_get(tree, "rtsp_url"))

    def test_snapshot_commit_is_catalog_and_active_session_bound(self) -> None:
        fn = api_fn("commit_camera_snapshot")
        self.assertTrue(worker_source.contains_expr(fn, "load_camera_preview_catalog()"))
        self.assertTrue(worker_source.contains_expr(fn, "CAMERA_PREVIEW_SESSION_RE.fullmatch(session_id)"))
        self.assertTrue(worker_source.contains_stmt(fn, "state = active_camera_preview_locked()"))
        self.assertTrue(worker_source.contains_expr(fn, 'state.get("camera_id") != camera_id'))
        self.assertTrue(worker_source.contains_expr(fn, 'state.get("session_id") != session_id'))
        self.assertTrue(worker_source.contains_expr(fn, "commit_camera_snapshot_locked(state)"))
        for banned in ("source", "rtsp_url", "output_dir"):
            self.assertFalse(any(kw.arg == banned for node in ast.walk(fn) for kw in getattr(node, "keywords", [])))
        self.assertNotIn("rtsp_url", fn_strings(fn))

    def test_snapshot_store_is_atomic_last_good_and_quality_gated(self) -> None:
        self.assertTrue(api_has_expr('DATA_DIR / "camera-preview-snapshots"'))
        min_bytes = [a for tree in API_TREES for a in worker_source.find_assignments(tree, "CAMERA_SNAPSHOT_MIN_BYTES")]
        self.assertTrue(any(isinstance(a.value, ast.Constant) and a.value.value == 4096 for a in min_bytes))
        min_spread = [a for tree in API_TREES for a in worker_source.find_assignments(tree, "CAMERA_SNAPSHOT_MIN_LUMA_SPREAD")]
        self.assertTrue(any(isinstance(a.value, ast.Constant) and a.value.value == 12.0 for a in min_spread))
        luma = api_fn("camera_snapshot_luma_spread")
        self.assertIn("signalstats,metadata=print", fn_strings(luma))
        usable = api_fn("camera_snapshot_candidate_is_usable")
        self.assertTrue(worker_source.contains_expr(usable, "spread >= CAMERA_SNAPSHOT_MIN_LUMA_SPREAD"))
        locked = api_fn("commit_camera_snapshot_locked")
        self.assertTrue(worker_source.contains_expr(locked, 'CAMERA_SNAPSHOT_DIR / f".{camera_id}.{uuid.uuid4().hex}.jpg"'))
        self.assertTrue(worker_source.contains_expr(locked, "os.replace(temp_path, final_path)"))
        self.assertTrue(worker_source.contains_expr(locked, "temp_path.unlink(missing_ok=True)"))
        # The quality gate runs before the atomic replace.
        quality_lines = [call.lineno for call in calls_named(locked, "camera_snapshot_candidate_is_usable")]
        replace_lines = [
            node.lineno
            for node in ast.walk(locked)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "replace"
        ]
        self.assertTrue(quality_lines and replace_lines and min(quality_lines) < min(replace_lines))
        self.assertFalse(worker_source.references_name(API_TREES, "CAMERA_SNAPSHOT_HISTORY"))

    def test_snapshot_get_is_no_store_and_catalog_bound(self) -> None:
        fn = api_fn("get_camera_snapshot")
        self.assertTrue(calls_named(fn, "load_camera_preview_catalog"))
        self.assertIn("Camera snapshot is not available", fn_strings(fn))
        self.assertTrue(
            any(kw.arg == "media_type" and isinstance(kw.value, ast.Constant) and kw.value.value == "image/jpeg" for node in ast.walk(fn) for kw in getattr(node, "keywords", []))
        )
        self.assertEqual(dict_value(fn, "Cache-Control"), "no-store, max-age=0")

    def test_api_never_returns_private_source_field(self) -> None:
        public_state = api_fn("camera_preview_public_state")
        self.assertNotIn("source", fn_dict_keys(public_state))
        self.assertNotIn("source", fn_strings(public_state))
        get_cameras = api_fn("get_cameras")
        self.assertFalse(worker_source.contains_expr(get_cameras, 'camera["source"]'))

    def test_api_relay_source_is_private_credential_free_and_identity_bound(self) -> None:
        fn = api_fn("validate_camera_preview_source")
        self.assertTrue(worker_source.contains_expr(fn, 'parsed.scheme.lower() != "rtsp"'))
        self.assertTrue(any(isinstance(n, ast.Name) and n.id == "CAMERA_PREVIEW_RFC1918" for n in ast.walk(fn)))
        self.assertTrue(worker_source.contains_expr(fn, "parsed.username is not None or parsed.password is not None"))
        self.assertTrue(worker_source.contains_expr(fn, "parsed.query or parsed.fragment"))
        self.assertTrue(worker_source.contains_expr(fn, 'f"/preview_{camera_id}"'))

    def test_api_preview_is_one_process_bounded_h264_hls(self) -> None:
        self.assertTrue(api_has_expr('min(int(os.environ.get("SEA_SPEED_CAMERA_PREVIEW_TTL_SEC", "120")), 600)'))
        start_fn = api_fn("start_camera_preview_locked")
        self.assertTrue(calls_named(start_fn, "terminate_camera_preview_locked"))
        popen = popen_call(start_fn)
        self.assertIsNotNone(popen)
        keywords = {kw.arg: kw.value for kw in popen.keywords if kw.arg}
        for name in ("stdin", "stdout", "stderr"):
            self.assertIsInstance(keywords.get(name), ast.Attribute)
            self.assertEqual(keywords[name].attr, "DEVNULL")
        self.assertIsInstance(keywords.get("close_fds"), ast.Constant)
        self.assertIs(keywords["close_fds"].value, True)
        self.assertNotIn("shell", keywords)
        for tree in API_TREES:
            self.assertFalse(has_keyword(tree, "shell"))
        ffmpeg = api_fn("build_camera_preview_ffmpeg_args")
        constants = fn_strings(ffmpeg)
        for constant in ("scale=640:-2,fps=8", "-an", "libx264", "baseline", "-hls_segment_type", "fmp4"):
            self.assertIn(constant, constants)
        self.assertTrue(any(isinstance(n, ast.Name) and n.id == "CAMERA_PREVIEW_TTL_SEC" for n in ast.walk(ffmpeg)))
        self.assertTrue(api_has_expr('f"/sea-speed/media/camera-preview/{session_id}/index.m3u8"'))
        self.assertTrue(api_has_expr("output_dir.mkdir(mode=0o755, parents=False, exist_ok=False)"))
        self.assertFalse(api_has_expr("output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)"))

    def test_api_pid_cleanup_is_bound_to_exact_managed_output(self) -> None:
        fn = api_fn("camera_preview_pid_matches")
        self.assertTrue(worker_source.contains_expr(fn, "Path(CAMERA_PREVIEW_FFMPEG_BIN).name in cmdline"))
        self.assertTrue(worker_source.contains_expr(fn, "expected_playlist in cmdline"))
        self.assertTrue(api_has_expr("CAMERA_PREVIEW_SESSION_RE.fullmatch(session_id)"))

    def test_ubuntu_preview_relay_is_separate_source_on_demand_and_private(self) -> None:
        # Renderer-owned config literals (issue #442: canonical renderer module).
        for marker in (
            "sourceOnDemand: yes",
            "sourceOnDemandCloseAfter: 2s",
            "rtspTransports: [tcp]",
            r'"~^preview_[a-z0-9._-]+$"',
        ):
            self.assertIn(marker, RENDERER_SRC)
        # Shell structural pins (SP: deploy-transaction evidence literals).
        for marker in (
            'service_name="sea-speed-camera-preview-relay.service"',
            'cam1_service="sea-speed-stream.service"',
            "CAM1_RELAY_CHANGED=NO",
            "AI_WORKER_CHANGED=NO",
            "SECRETS_DISPLAYED=NO",
        ):
            self.assertIn(marker, RELAY)
        self.assertNotIn('systemctl restart "$cam1_service"', RELAY)
        self.assertNotIn('systemctl restart "$ai_service"', RELAY)
        self.assertIn('chmod 0750 "$state_root" "$active_root"', RELAY)

    def test_ubuntu_inventory_is_protected_and_catalog_is_sanitized(self) -> None:
        # Renderer-owned schema/validation literals (issue #442).
        for marker in (
            "sea_speed_camera_preview_inventory_v1",
            "sea_speed_camera_preview_catalog_v1",
            "if parsed.username is None:",
            '"source": f"rtsp://{relay_host}:{relay_port}/{path_name}"',
        ):
            self.assertIn(marker, RENDERER_SRC)
        # Shell structural pins.
        for marker in (
            "inventory mode must be 600",
            "inventory must be root-owned",
        ):
            self.assertIn(marker, RELAY)
        self.assertNotRegex(RELAY, r"192\.168\.88\.\d+")
        self.assertNotRegex(RENDERER_SRC, r"192\.168\.88\.\d+")

    def test_vps_deploy_installs_rolls_back_and_smokes_cameras_page(self) -> None:
        # SP: deploy.sh release/evidence literals are pinned by the deploy
        # transaction suite; the source scan stays the cheapest honest check.
        for marker in (
            'CAMERAS_FRONTEND_TARGET="${SEA_SPEED_CAMERAS_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/cameras/index.html}"',
            'CAMERAS_FRONTEND_URL="${SEA_SPEED_CAMERAS_FRONTEND_URL:-https://mostdef.ru/sea-speed/cameras/}"',
            "frontend/sea-speed/cameras/index.html",
            "frontend/sea-speed/cameras/.absent",
            "ensure_current_release_has_cameras_frontend",
            'verify_public_url "Cameras frontend" "$CAMERAS_FRONTEND_URL"',
            'ORIGIN_HEALTH_URL="${SEA_SPEED_ORIGIN_HEALTH_URL:-http://127.0.0.1:8010/api/health}"',
            'PUBLIC_HEALTH_URL="${SEA_SPEED_HEALTH_URL:-https://mostdef.ru/sea-speed/api/health}"',
            '"cameras_frontend_release_state"',
        ):
            self.assertIn(marker, DEPLOY)

    def test_sdd_links_snapshot_issue_and_preserves_camera1_media_and_storage_boundary(self) -> None:
        # NO-CHANGE: the SDD prose documents are themselves the artifact under
        # test; their text pins are the contract (see specs/398-wave4 mapping).
        for doc in (SPEC, PLAN, TASKS, QUICKSTART):
            self.assertIn("#112", doc)
        self.assertIn("#115", SPEC)
        self.assertIn("/sea-speed/media/cam1/index.m3u8", SPEC)
        self.assertIn("/cams/hls/cam1/index.m3u8", SPEC)
        self.assertIn("retired", SPEC.lower())
        self.assertIn("Camera 1", PLAN)
        self.assertIn("one-active-preview", SPEC.lower())
        self.assertIn("localStorage", SPEC)
        self.assertIn("camera-preview-snapshots", SPEC)
        self.assertIn("sequential", PLAN.lower())
        self.assertIn("Authentik", PLAN)


if __name__ == "__main__":
    unittest.main()
