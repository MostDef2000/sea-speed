"""HTML inline-script node-exec harness for protected frontend pages (issue
#398 waves 2 and 4).

Converts raw source-text pins on frontend/sea-speed pages into executions of
the pages' real inline scripts. The HTML under frontend/ is a READ-ONLY
input: the inline <script> blocks are extracted from the real bytes (never
copied into the tests), concatenated in document order, and executed in one
node scope under the smallest browser shim that lets the page's module level
run:

- a memoizing ``document.getElementById`` stub that fabricates a full element
  stub for any id (textContent/className/classList/style/handlers/2d context,
  plus wave-4 additions: dataset/querySelector/querySelectorAll/remove/reset,
  recorded per-element listeners and child-tracking append/appendChild),
- a recording ``fetch`` that answers the session endpoint with a trusted
  ``username``; every other URL fails closed unless the scenario seeded a
  programmable response (``__setResponse`` / the ``responses`` argument), so
  page data paths can be driven end-to-end,
- recording ``setInterval``/``setTimeout`` (real timers never tick, so node
  exits deterministically) and recording ``location.assign``/``replace`` with
  per-page href/pathname/search/hash defaults (``window.top`` is ``window``),
  plus an overridable ``document.referrer`` for boot-time referrer inference,
- recording ``addEventListener`` at window/document level (the water and
  road pages defer their crossing-line panel behind a DOMContentLoaded
  listener when ``readyState`` is ``"loading"``),
- a recording ``SeaSpeedOverlayCanvas.init``/``setWorkerActive`` and an HLS
  stub that records ``loadSource``/``attachMedia``/handlers so scenarios can
  fire the MEDIA_ATTACHED/MANIFEST_PARSED events the real HLS.js would,
- stubs for the pages' other external collaborators (``history.replaceState``,
  ``scrollTo``, ``confirm``, ``CSS.escape``, a ``FormData`` stub accepting
  plain element stubs, ``requestAnimationFrame`` with a scenario-settable
  ``__rafBump`` hook for the cameras batch-preview stabilization loop).

``scenario`` runs in the SAME scope as the page script, so it can await the
page's own functions and assert against the live closures; any failure exits
node non-zero and surfaces as a normal test failure. Behavior regressions fail
even when the historical marker text survives; harmless reformatting of the
page keeps passing.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "sea-speed"
ROAD_PAGE = FRONTEND / "road" / "index.html"
WATER_PAGE = FRONTEND / "index.html"
CAMERAS_PAGE = FRONTEND / "cameras" / "index.html"
OBJECTS_PAGE = FRONTEND / "objects" / "index.html"

SESSION_PATH = "/sea-speed/api/session"
REDIRECT_PATH = "/sea-speed/road/"
WATCHDOG_MS = 15000

# Per-page location defaults: the protected pages read
# window.location.pathname/search/hash (the auth-loss redirect rebuilds the
# current URL) and the objects page parses window.location.href with the URL
# constructor, so the shim needs absolute per-page defaults.
PAGE_LOCATION_DEFAULTS = {
    "water": {
        "href": "http://localhost/sea-speed/",
        "origin": "http://localhost",
        "pathname": "/sea-speed/",
        "search": "",
        "hash": "",
    },
    "road": {
        "href": "http://localhost/sea-speed/road/",
        "origin": "http://localhost",
        "pathname": "/sea-speed/road/",
        "search": "",
        "hash": "",
    },
    "cameras": {
        "href": "http://localhost/sea-speed/cameras/",
        "origin": "http://localhost",
        "pathname": "/sea-speed/cameras/",
        "search": "",
        "hash": "",
    },
    "objects": {
        "href": "http://localhost/sea-speed/objects/",
        "origin": "http://localhost",
        "pathname": "/sea-speed/objects/",
        "search": "",
        "hash": "",
    },
}


def page_key(source: Path) -> str:
    """Classify a page path into a PAGE_LOCATION_DEFAULTS key.

    Content markers win so tmp copies (the wave-2/wave-4 demos copy pages
    into tmp dirs) still get their real page's location defaults; the source
    path is the fallback.
    """
    try:
        marker_hits = source.read_text(encoding="utf-8-sig")
    except OSError:
        marker_hits = ""
    if "waterMainVideo" in marker_hits:
        return "water"
    if "cameraGrid" in marker_hits:
        return "cameras"
    if "registryScope" in marker_hits:
        return "objects"
    if "road1" in marker_hits or "/sea-speed/road/" in marker_hits:
        return "road"
    resolved = source.resolve()
    if resolved == ROAD_PAGE.resolve():
        return "road"
    if resolved.parent == FRONTEND.resolve():
        return "water"
    return resolved.parent.name


def node_available() -> bool:
    return shutil.which("node") is not None


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
            "node harness failed (rc=%s)\n--- stderr ---\n%s" % (proc.returncode, proc.stderr)
        )
    return proc.stdout.strip()


def extract_inline_scripts(html: str) -> list[str]:
    """Inline <script> block bodies in document order (src= tags excluded)."""
    return [
        match.group(1)
        for match in re.finditer(
            r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.DOTALL | re.IGNORECASE
        )
    ]


# Browser shim installed before the page script: element stubs for every id,
# recording fetch/timers/location/listeners, programmable fetch responses,
# stub overlay module and HLS global. The scenario and the page script share
# one scope, so page functions stay directly callable.
PRELUDE = r"""
const __record = {
  fetch: [], intervals: [], timeouts: [], locations: [], replaces: [],
  listeners: [], overlayInits: [], workerActive: [], hlsInstances: [],
  history: [], scrolls: [], confirms: [], elements: {},
};
const __responses = [];
function __makeCtx() {
  const ctx = {};
  for (const m of ["setTransform","clearRect","beginPath","moveTo","lineTo","closePath",
                   "fill","stroke","fillRect","strokeRect","fillText","save","restore"]) {
    ctx[m] = function () {};
  }
  ctx.measureText = () => ({ width: 42 });
  return ctx;
}
function __makeElement(id) {
  const element = {
    id, textContent: "", className: "", title: "", innerHTML: "",
    disabled: false, style: {}, readyState: 2, paused: true, currentTime: 0,
    videoWidth: 1920, videoHeight: 1080, naturalWidth: 1920, naturalHeight: 1080,
    src: "", error: null, name: "", dataset: {},
    classList: { add() {}, remove() {}, toggle() {} },
    setAttribute() {}, removeAttribute() {}, getAttribute() { return null; },
    // Child tracking: the pages build DOM subtrees at runtime (the water
    // passages list appends event cards node-by-node), so append/appendChild
    // record the fabricated children instead of dropping them.
    appendChild(k) { (element.__children = element.__children || []).push(k); return k; },
    append(...kids) { for (const k of kids) element.appendChild(k); },
    appendTo(parent) { return parent.appendChild(element); },
    focus() {}, requestFullscreen() {}, remove() {}, reset() {},
    removeEventListener() {},
    // Wave 4: programmable sub-DOM. By default every query misses (the
    // cameras grid renders no cards for an empty catalog); a scenario can
    // attach __query/__queryAll maps to fabricate card subtrees.
    querySelector(sel) {
      const q = element.__query;
      return q && Object.prototype.hasOwnProperty.call(q, sel) ? q[sel] : null;
    },
    querySelectorAll(sel) {
      const q = element.__queryAll;
      return q && Object.prototype.hasOwnProperty.call(q, sel) ? q[sel] : [];
    },
    getBoundingClientRect() {
      return { width: 1920, height: 1080, left: 0, top: 0, x: 0, y: 0, right: 1920, bottom: 0 };
    },
    getContext() { return __makeCtx(); },
    pause() {}, load() {}, play() { return Promise.resolve(); },
    canPlayType() { return __canPlayType; },
  };
  element.__listeners = {};
  // Real DOM inputs coerce ``value`` assignments to strings (the objects
  // registry writes the numeric speed_kmh into editSpeed.value and then reads
  // ``.trim()``), so the stub mirrors the Web IDL DOMString semantics.
  let __value = "";
  Object.defineProperty(element, "value", {
    get() { return __value; },
    set(v) { __value = v == null ? "" : String(v); },
    enumerable: true,
    configurable: true,
  });
  element.__query = null;
  element.__queryAll = null;
  element.addEventListener = function (type, fn) {
    const key = String(type);
    (element.__listeners[key] = element.__listeners[key] || []).push(fn);
  };
  return element;
}
globalThis.document = {
  readyState: "complete",
  referrer: "",
  title: "",
  fullscreenElement: null,
  exitFullscreen() {},
  getElementById(id) {
    if (!__record.elements[id]) __record.elements[id] = __makeElement(id);
    return __record.elements[id];
  },
  // Pages may build DOM nodes at boot (the water operator page appends a
  // crossing-line canvas inside the overlay wrap; the cameras page builds
  // video elements per preview card) — fabricate the same full element stub
  // for any created tag.
  createElement(tag) {
    const element = __makeElement("");
    element.tagName = String(tag || "").toUpperCase();
    return element;
  },
  addEventListener(type, fn) { __record.listeners.push(["document", String(type), fn]); },
  removeEventListener() {},
  querySelector() { return null; },
  querySelectorAll() { return []; },
};
document.body = __makeElement("body");
globalThis.window = globalThis;
globalThis.top = globalThis; // window.top === window for the auth-loss redirect
globalThis.devicePixelRatio = 1;
globalThis.location = {
  href: "http://localhost/sea-speed/",
  origin: "http://localhost",
  pathname: "/sea-speed/",
  search: "",
  hash: "",
  assign(p) { __record.locations.push(String(p)); },
  replace(p) { __record.replaces.push(String(p)); },
  toString() { return this.href; },
};
globalThis.CSS = { escape: (s) => String(s).replace(/[^a-zA-Z0-9_-]/g, "\\$&") };
// Node's built-in FormData rejects plain objects; the pages only ever hand it
// our element stubs, so provide a recording-friendly stand-in.
class __FormDataStub {
  constructor(form) {
    this._entries = [];
    if (form && Array.isArray(form.elements)) {
      for (const el of form.elements) {
        this._entries.push([String(el.name ?? el.id ?? ""), String(el.value ?? "")]);
      }
    }
  }
  append(k, v) { this._entries.push([String(k), String(v)]); }
  get(k) { const hit = this._entries.find(([key]) => key === String(k)); return hit ? hit[1] : null; }
  has(k) { return this._entries.some(([key]) => key === String(k)); }
  * entries() { yield* this._entries; }
  * keys() { for (const [k] of this._entries) yield k; }
  * values() { for (const [, v] of this._entries) yield v; }
}
globalThis.FormData = __FormDataStub;
globalThis.requestAnimationFrame = function (cb) {
  return setImmediate(() => {
    if (typeof __rafBump === "function") __rafBump();
    cb(performance.now());
  });
};
globalThis.cancelAnimationFrame = function () {};
globalThis.SeaSpeedOverlayCanvas = {
  init(opts) {
    __record.overlayInits.push(
      opts && typeof opts === "object" ? JSON.parse(JSON.stringify(opts)) : opts === undefined ? null : opts
    );
    return {
      setWorkerActive(v) { __record.workerActive.push(Boolean(v)); },
      accept() {},
      renderForVideoFrame() {},
    };
  },
};
globalThis.Hls = function Hls(config) {
  this.config = config || {};
  this.handlers = {};
  this.sources = [];
  this.attached = [];
  this.destroyed = false;
  __record.hlsInstances.push(this);
};
Hls.isSupported = () => __hlsSupported;
Hls.Events = { MEDIA_ATTACHED: "hlsMediaAttached", MANIFEST_PARSED: "hlsManifestParsed", ERROR: "hlsError" };
Hls.ErrorTypes = { NETWORK_ERROR: "networkError", MEDIA_ERROR: "mediaError", OTHER_ERROR: "otherError" };
Hls.prototype.on = function (event, cb) {
  (this.handlers[event] = this.handlers[event] || []).push(cb);
  return this;
};
Hls.prototype.loadSource = function (src) { this.sources.push(String(src)); };
Hls.prototype.attachMedia = function (media) { this.attached.push(media); };
Hls.prototype.destroy = function () { this.destroyed = true; };
Hls.prototype.startLoad = function () {};
Hls.prototype.stopLoad = function () {};
Hls.prototype.recoverMediaError = function () {};
globalThis.fetch = async function (url, options) {
  const call = { url: String(url), options: options || {} };
  __record.fetch.push(call);
  if (call.url === __SESSION_PATH && !__sessionFail) {
    return { ok: true, json: async () => ({ username: __sessionUser }) };
  }
  for (const r of __responses) {
    if (call.url.includes(r.match)) {
      const payload = typeof r.json === "function" ? r.json(call) : r.json;
      return {
        ok: r.ok !== false,
        status: r.status || (r.ok === false ? 503 : 200),
        json: async () =>
          payload && typeof payload === "object" ? JSON.parse(JSON.stringify(payload)) : payload,
      };
    }
  }
  return { ok: false, status: 401, json: async () => ({}) };
};
globalThis.__setResponse = function (match, json, ok, status) {
  __responses.push({
    match: String(match),
    json,
    ok: ok !== false,
    status: status || (ok === false ? 503 : 200),
  });
};
globalThis.setInterval = function (fn, ms) { __record.intervals.push([fn, Number(ms)]); return 0; };
globalThis.clearInterval = function () {};
globalThis.setTimeout = function (fn, ms) { __record.timeouts.push([fn, Number(ms)]); return 0; };
globalThis.clearTimeout = function () {};
globalThis.addEventListener = function (type, fn) {
  __record.listeners.push(["window", String(type), fn]);
};
globalThis.removeEventListener = function () {};
globalThis.scrollTo = function (...args) { __record.scrolls.push(args); };
globalThis.confirm = function (msg) { __record.confirms.push(String(msg)); return true; };
globalThis.history = {
  replaceState(...args) { __record.history.push(args.map((a) => String(a))); },
  pushState(...args) { __record.history.push(args.map((a) => String(a))); },
};
globalThis.requestAnimationFrame = function (cb) {
  return setImmediate(() => {
    if (typeof __rafBump === "function") __rafBump();
    cb(performance.now());
  });
};
globalThis.cancelAnimationFrame = function () {};
"""

# Scenario assertions that need the page's own closures (the watchdog wiring
# and the identity-loss redirect) run in node; everything JSON-recordable is
# printed for the Python-side asserts.
DEFAULT_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  // Wave 4: the pages must never touch web storage (identity lives only in
  // the same-origin session endpoint) — the shim defines no storage globals,
  // so any page-introduced binding or unguarded access fails here.
  assert(typeof localStorage === "undefined", "localStorage must not exist in the page scope");
  assert(typeof sessionStorage === "undefined", "sessionStorage must not exist in the page scope");
  // The watchdog is identified behaviorally: the interval registered at the
  // protected cadence must re-fetch the trusted identity when it fires —
  // the loader's name is an implementation detail.
  const watchdog = __record.intervals.find(([, ms]) => ms === __WATCHDOG_MS);
  assert(watchdog, "no " + __WATCHDOG_MS + " ms interval registered (session watchdog missing)");
  const fetchCountBefore = __record.fetch.length;
  await watchdog[0]();
  assert(
    __record.fetch.slice(fetchCountBefore).some((c) => c.url === __SESSION_PATH),
    "the " + __WATCHDOG_MS + " ms interval does not re-fetch the trusted identity"
  );
  const sessionFetch = __record.fetch.find((c) => c.url === __SESSION_PATH);
  assert(sessionFetch, "session endpoint not fetched at boot");
  assert(sessionFetch.options.credentials === "same-origin", "session fetch is not same-origin");
  assert(
    __record.elements.sessionUser && __record.elements.sessionUser.textContent === __sessionUser,
    "success path does not populate the trusted identity"
  );
  __sessionFail = true;
  await watchdog[0]();
  assert(
    __record.locations.includes(__REDIRECT),
    "identity loss after establishment must redirect to " + __REDIRECT
  );
  console.log("###" + JSON.stringify({
    sessionFetches: __record.fetch.filter((c) => c.url === __SESSION_PATH).map((c) => c.options),
    fetchUrls: __record.fetch.map((c) => c.url),
    fetchCalls: __record.fetch.map((c) => ({ url: c.url, method: (c.options && c.options.method) || "GET" })),
    intervals: __record.intervals.map(([fn, ms]) => ({ fn: (fn && fn.name) || "?", ms })),
    redirects: __record.locations,
    sessionUser: __record.elements.sessionUser ? __record.elements.sessionUser.textContent : null,
    replaces: __record.replaces,
    overlayInits: __record.overlayInits,
    workerActive: __record.workerActive,
    hlsInstances: __record.hlsInstances.map((inst) => ({
      sources: inst.sources,
      attached: inst.attached.map((el) => (el && el.id) || "?"),
      handlers: Object.keys(inst.handlers),
      config: inst.config,
    })),
    listeners: __record.listeners.map(([target, type]) => ({ target, type })),
  }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def run_inline_scripts(
    source: Path = ROAD_PAGE,
    scenario: str = DEFAULT_SCENARIO,
    session_username: str = "operator",
    timeout: int = 30,
    ready_state: str = "complete",
    responses: list | None = None,
    hls_supported: bool = True,
    drain_timeouts: bool = False,
    location_overrides: dict | None = None,
    referrer: str | None = None,
) -> dict:
    """Execute the page's real inline scripts under the shim and run
    ``scenario`` after the boot asyncs settle. Returns the recorded evidence:
    session fetch options, registered intervals, redirects, identity text,
    plus the wave-4 records (location.replace calls, overlay init args,
    worker-active flips, HLS instances, window/document listeners).

    ``ready_state`` lets a scenario boot the page while
    ``document.readyState`` is ``"loading"`` (deferred init paths);
    ``responses`` seeds programmable fetch replies (``{match, json, ok,
    status}`` matched by URL substring, first match wins) before the page
    script runs; ``drain_timeouts`` fires the boot-batch recorded timeouts
    (one pass, exactly as scheduled at boot — reconnect timers recorded
    during the pass stay unfired) before the scenario runs;
    ``location_overrides`` merges fields into the page's default location
    (e.g. ``{"search": "?scope=road"}`` for the objects registry scope);
    ``referrer`` overrides ``document.referrer`` BEFORE the page script runs
    (the objects registry infers its scope from the same-origin referrer at
    boot, so a scenario cannot set it later).
    """
    html = source.read_text(encoding="utf-8-sig")
    scripts = extract_inline_scripts(html)
    if not scripts:
        raise AssertionError(f"no inline scripts found in {source}")
    bootstrap = (
        f"const __WATCHDOG_MS = {json.dumps(WATCHDOG_MS)};\n"
        f"const __SESSION_PATH = {json.dumps(SESSION_PATH)};\n"
        f"const __REDIRECT = {json.dumps(REDIRECT_PATH)};\n"
        f"const __sessionUser = {json.dumps(session_username)};\n"
        "let __sessionFail = false;\n"
        f"const __readyState = {json.dumps(ready_state)};\n"
        f"const __hlsSupportedInit = {json.dumps(bool(hls_supported))};\n"
        "let __hlsSupported = __hlsSupportedInit;\n"
        "let __canPlayType = '';\n"
        "let __rafBump = null;\n"
        f"const __locationDefaults = {json.dumps({**PAGE_LOCATION_DEFAULTS[page_key(source)], **(location_overrides or {})})};\n"
        "document.readyState = __readyState;\n"
        "Object.assign(globalThis.location, __locationDefaults);\n"
        f"document.referrer = {json.dumps(referrer or '')};\n"
    )
    for response in responses or []:
        bootstrap += "__responses.push(%s);\n" % json.dumps(response)
    drain = ""
    if drain_timeouts:
        # No top-level await (node -e is CommonJS): the drain IIFE starts
        # before the scenario IIFE and chains purely on microtasks, while the
        # scenario's first setImmediate yield is a macrotask barrier — so the
        # boot-batch drain always completes before scenario assertions run.
        drain = (
            ";(async () => { const __bootTimeouts = __record.timeouts.splice(0);"
            " for (const [fn] of __bootTimeouts) { await fn(); } })();\n"
        )
    script = PRELUDE + bootstrap + "\n;\n".join(scripts) + "\n" + drain + scenario
    out = run_node(script, timeout=timeout)
    marker = out.rfind("###")
    if marker < 0:
        raise AssertionError(f"html harness produced no evidence record: {out!r}")
    return json.loads(out[marker + 3 :])
