"""Node-exec harness for the frontend live-overlay JS (issue #398 wave 1).

Issue #398 wave 1 converts the overlay/live test cluster's raw source-text
pins (assertIn on frontend/sea-speed file text) into executions of the real
frontend JS. The JS sources under frontend/ are READ-ONLY inputs: they are
loaded by node exactly as the pages load them (live-sync.js included before
the page's main script; overlay-canvas.js before it), never copied into the
tests.

Executability facts (verified against the live modules):

- ``live-sync.js`` is node-executable as-is: its module level only guards on
  ``typeof document === "undefined"``, so a bare ``global.window = {}`` is
  the whole shim. ``window.SeaSpeedLiveSync`` exposes the shared math.
- ``overlay-canvas.js`` is node-LOADABLE as-is: the IIFE only defines
  ``init`` and assigns ``window.SeaSpeedOverlayCanvas`` (no document access
  at module level). ``init(opts)`` is exercised through ``__makeOverlayDom``,
  the smallest DOM stub the module needs: a recording canvas 2d context, a
  stub video (with a no-op ``requestVideoFrameCallback`` so the real render
  loop never schedules), a stub ``window.addEventListener`` and a stubbed
  ``setInterval`` (installed by :data:`PRELUDE` before any require) so the
  module's real timers never start and node exits deterministically.

Both modules are ``require``d from disk — the tests execute the real bytes,
so a refactor of the covered JS that preserves behavior keeps passing and a
behavior regression fails even when the historical marker text survives.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "sea-speed"
LIVE_SYNC_JS = FRONTEND / "live-sync.js"
OVERLAY_JS = FRONTEND / "overlay-canvas.js"

# Page init configs mirrored from frontend/sea-speed/index.html (water) and
# frontend/sea-speed/road/index.html (road) — the exact SeaSpeedOverlayCanvas
#.init(...) arguments the real pages pass.
WATER_PAGE_CONFIG = {
    "cameraId": "cam1",
    "videoId": "waterMainVideo",
    "canvasId": "liveOverlayCanvas",
    "wrapId": "roiEditorWrap",
    "isWater": True,
}
ROAD_PAGE_CONFIG = {
    "cameraId": "road1",
    "videoId": "roadMainVideo",
    "canvasId": "liveOverlayCanvas",
    "wrapId": "roiEditorWrap",
    "isWater": False,
}


def node_available() -> bool:
    return shutil.which("node") is not None


def js_literal(value) -> str:
    """Embed a Python value as a JS literal (paths, configs, envelope specs)."""
    return json.dumps(value)


def run_node(script: str, timeout: int = 30) -> str:
    """Execute a node script from the repo root; return stripped stdout.

    Fails closed on a non-zero exit (AssertionError carries stderr), so a
    scenario assertion inside node surfaces as a normal test failure.
    """
    node = shutil.which("node")
    if node is None:
        raise AssertionError("node is not available; frontend exec checks cannot run")
    proc = subprocess.run(
        [node, "-e", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        raise AssertionError(
            "node harness failed (rc=%s)\n--- stderr ---\n%s\n--- script ---\n%s"
            % (proc.returncode, proc.stderr, script)
        )
    return proc.stdout.strip()


# Installed before any require: browser-like global semantics (window is the
# real global object, so `window.SeaSpeedLiveSync = ...` is visible to
# overlay-canvas.js's bare `SeaSpeedLiveSync` references) plus a no-op
# setInterval so the modules' real timers (overlay startLoop / poll intervals)
# never tick.
PRELUDE = """
global.window = global;
global.setInterval = function () { return 0; };
"""


def run_live_sync(body: str, source: Path = LIVE_SYNC_JS, prelude: str = "") -> str:
    """Require live-sync.js (as the pages do) and run ``body`` with ``S`` bound."""
    script = (
        PRELUDE
        + prelude
        + "\nrequire(" + js_literal(str(source)) + ");\n"
        + "const S = window.SeaSpeedLiveSync;\n"
        + "if (!S) throw new Error('window.SeaSpeedLiveSync missing');\n"
        + body
    )
    return run_node(script)


# Minimal DOM stub for overlay-canvas.js init(): recording canvas 2d context,
# stub video (no-op requestVideoFrameCallback prevents the real render loop),
# stub window listeners. document.getElementById resolves the three ids the
# page config names.
DOM_STUB_JS = r"""
function __makeOverlayDom(config) {
  var RECT = { width: config.rectW, height: config.rectH };
  var calls = { clearRect: 0, strokeRect: [], fillText: [], fillRect: 0 };
  var ctx = {
    font: "", strokeStyle: "", lineWidth: 0, fillStyle: "",
    setTransform: function () {},
    clearRect: function () { calls.clearRect++; },
    strokeRect: function (x, y, w, h) { calls.strokeRect.push([x, y, w, h]); },
    fillRect: function () { calls.fillRect++; },
    fillText: function (t) { calls.fillText.push(String(t)); },
    measureText: function () { return { width: 42 }; }
  };
  var canvas = {
    width: 0, height: 0, style: {},
    getBoundingClientRect: function () { return RECT; },
    getContext: function () { return ctx; }
  };
  var wrap = { getBoundingClientRect: function () { return RECT; } };
  var video = Object.assign(
    { readyState: 2, paused: true, currentTime: 0,
      requestVideoFrameCallback: function () {} },
    config.video || {}
  );
  var byId = {};
  byId[config.videoId] = video;
  byId[config.canvasId] = canvas;
  byId[config.wrapId] = wrap;
  global.document = { getElementById: function (id) { return byId[id] || null; } };
  global.window.addEventListener = function () {};
  global.window.devicePixelRatio = config.dpr || 1;
  return { calls: calls, canvas: canvas, video: video, wrap: wrap };
}
"""


def overlay_render_calls(
    config: dict,
    envelopes: list[dict],
    raw_offset_ms: float | None = 0.0,
    water_latency_s: float | None = None,
    extra_scenario: str = "",
    live_source: Path = LIVE_SYNC_JS,
    overlay_source: Path = OVERLAY_JS,
) -> dict:
    """Init the REAL overlay module against the stub DOM, accept ``envelopes``,
    render one video frame, and return the recorded 2d-context calls.

    ``envelopes`` items carry ``offset_ms`` relative to ``Date.now()`` (the
    module prunes against the real clock, so absolute times must be live) and
    the detection geometry; ``raw_offset_ms``/``water_latency_s`` wire the
    media-time source exactly like the pages do: water gets
    ``window.waterHls = { media, playingDate, latency }`` (live-edge latency
    path), road gets ``window.hls = { media, playingDate }`` (absolute media
    time path). ``raw_offset_ms=None`` exercises the raw == null fallback.
    """
    page = {**(WATER_PAGE_CONFIG if config.get("isWater") else ROAD_PAGE_CONFIG), **config}
    # accept() drops envelopes whose camera_id misses the page camera, so any
    # envelope spec without an explicit camera_id/domain inherits the page's
    # defaults (water: cam1/sea, road: road1/road) — a road scenario built
    # from water-default envelopes must still render through the real filter.
    envelope_defaults = PAGE_ENVELOPE_DEFAULTS["road" if not page["isWater"] else "water"]
    envelopes = [
        {
            **envelope_defaults,
            **spec,
            "camera_id": spec.get("camera_id") or envelope_defaults["camera_id"],
            "domain": spec.get("domain") or envelope_defaults["domain"],
        }
        for spec in envelopes
    ]
    # Media-time wiring mirrors the pages: water reads window.waterHls
    # (playingDate for raw media time + latency for the live-edge path), road
    # reads window.hls (absolute media time only). raw_offset_ms=None drops
    # the media source entirely so the module's raw == null fallback runs.
    water_setup = ""
    if water_latency_s is not None:
        water_setup = (
            "window.waterHls = { media: H.video, playingDate: new Date(NOW + "
            + js_literal(raw_offset_ms)
            + "), latency: "
            + js_literal(water_latency_s)
            + " };"
        )
    hls_setup = ""
    if water_latency_s is None and raw_offset_ms is not None:
        hls_setup = (
            "window.hls = { media: H.video, playingDate: new Date(NOW + "
            + js_literal(raw_offset_ms)
            + ") };"
        )
    null_setup = "delete H.video.getStartDate;" if raw_offset_ms is None else ""
    scenario = f"""
const PAGE = {js_literal(page)};
const H = __makeOverlayDom({{
  videoId: PAGE.videoId, canvasId: PAGE.canvasId, wrapId: PAGE.wrapId,
  rectW: {js_literal(page.get("rectW", 720))}, rectH: {js_literal(page.get("rectH", 405))},
  dpr: {js_literal(page.get("dpr", 1))}, video: {js_literal(page.get("video") or {})}
}});
const NOW = Date.now();
const ENVELOPE_SPEC = {js_literal(envelopes)};
let __frame = 0;
const envelopes = ENVELOPE_SPEC.map(function (s) {{
  return {{
    id: s.id, camera_id: s.camera_id, domain: s.domain,
    generation: s.generation, frame_no: ++__frame,
    capture_time_unix_ms: NOW + s.offset_ms,
    frame_width: s.frame_width || 1920, frame_height: s.frame_height || 1080,
    detections: s.detections
  }};
}});
{water_setup}
{hls_setup}
{null_setup}
const overlay = window.SeaSpeedOverlayCanvas.init({{
  cameraId: PAGE.cameraId, videoId: PAGE.videoId, canvasId: PAGE.canvasId,
  wrapId: PAGE.wrapId, liveUrl: "/sea-speed/api/live/stream",
  livePollUrl: "/sea-speed/api/live?limit=1", isWater: PAGE.isWater
}});
envelopes.forEach(function (e) {{ overlay.accept(e); }});
overlay.renderForVideoFrame();
{extra_scenario}
console.log("###" + JSON.stringify(H.calls));
"""
    script = (
        PRELUDE
        + DOM_STUB_JS
        + "\nrequire(" + js_literal(str(live_source)) + ");\n"
        + "require(" + js_literal(str(overlay_source)) + ");\n"
        + "const S = window.SeaSpeedLiveSync;\n"
        + "if (!S) throw new Error('window.SeaSpeedLiveSync missing');\n"
        + scenario
    )
    out = run_node(script)
    marker = out.rfind("###")
    if marker < 0:
        raise AssertionError(f"overlay harness produced no call record: {out!r}")
    return json.loads(out[marker + 3 :])


# camera_id/domain defaults per page config: the overlay module's accept()
# drops any envelope whose camera_id does not match the init() cameraId, so a
# road scenario built from water-default envelopes would silently render
# nothing. Callers select the page with ``page=``; explicit camera_id/domain
# overrides still win.
PAGE_ENVELOPE_DEFAULTS = {
    "water": {"camera_id": "cam1", "domain": "sea"},
    "road": {"camera_id": "road1", "domain": "road"},
}


def envelope(offset_ms: float, page: str = "water", **detection) -> dict:
    """Build one water/road live-envelope spec for :func:`overlay_render_calls`.

    ``camera_id``/``domain`` default to the named page's camera (water: cam1,
    road: road1) so the envelope passes the real overlay accept() filter for
    that page config; explicit overrides win. The detection box defaults to a
    0.1-wide box at the given top-left so every envelope is drawable and the
    drawn box identifies which envelope was rendered.
    """
    page_defaults = PAGE_ENVELOPE_DEFAULTS[page]
    x1 = detection.pop("x1_norm", 0.1)
    coords = {
        "x1_norm": x1,
        "y1_norm": detection.pop("y1_norm", 0.1),
        "x2_norm": detection.pop("x2_norm", x1 + 0.1),
        "y2_norm": detection.pop("y2_norm", 0.2),
    }
    return {
        "camera_id": detection.pop("camera_id", page_defaults["camera_id"]),
        "domain": detection.pop("domain", page_defaults["domain"]),
        "generation": detection.pop("generation", 1),
        "offset_ms": offset_ms,
        **detection,
        "detections": [{**coords, "track_id": 5, "class_name": "vessel"}],
    }
