"""HTML inline-script node-exec harness for protected frontend pages (issue
#398 wave 2).

Converts the auth-session frontend contract's raw source-text pins (assertIn
on frontend/sea-speed/road/index.html text) into an execution of the page's
real inline script. The HTML under frontend/ is a READ-ONLY input: the inline
<script> blocks are extracted from the real bytes (never copied into the
tests), concatenated in document order, and executed in one node scope under
the smallest browser shim that lets the page's module level run:

- a memoizing ``document.getElementById`` stub that fabricates a full element
  stub for any id (textContent/className/classList/style/handlers/2d context),
- a recording ``fetch`` that answers the session endpoint with a trusted
  ``username`` (and, when the scenario flips ``__sessionFail``, fails closed
  so the identity-loss path can be exercised),
- recording ``setInterval``/``setTimeout`` (real timers never tick, so node
  exits deterministically) and a recording ``location.assign``,
- stubs for the page's external collaborators (``SeaSpeedOverlayCanvas`` and
  the HLS globals) — wave-1 tests already cover those through the real modules.

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

SESSION_PATH = "/sea-speed/api/session"
REDIRECT_PATH = "/sea-speed/road/"
WATCHDOG_MS = 15000


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
# recording fetch/timers/location, stub overlay module. The scenario and the
# page script share one scope, so page functions stay directly callable.
PRELUDE = r"""
const __record = { fetch: [], intervals: [], timeouts: [], locations: [], elements: {} };
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
  return {
    id, textContent: "", className: "", title: "", innerHTML: "", value: "",
    disabled: false, style: {}, readyState: 2, paused: true, currentTime: 0,
    videoWidth: 1920, videoHeight: 1080, naturalWidth: 1920, naturalHeight: 1080,
    classList: { add() {}, remove() {}, toggle() {} },
    setAttribute() {}, removeAttribute() {}, getAttribute() { return null; },
    addEventListener() {}, appendChild() {}, focus() {}, requestFullscreen() {},
    getBoundingClientRect() {
      return { width: 1920, height: 1080, left: 0, top: 0, x: 0, y: 0, right: 1920, bottom: 0 };
    },
    getContext() { return __makeCtx(); },
    pause() {}, load() {}, play() { return Promise.resolve(); },
    canPlayType() { return ""; },
  };
}
globalThis.document = {
  readyState: "complete",
  fullscreenElement: null,
  exitFullscreen() {},
  getElementById(id) {
    if (!__record.elements[id]) __record.elements[id] = __makeElement(id);
    return __record.elements[id];
  },
  // Issue #398 wave 4: pages may build DOM nodes at boot (the water operator
  // page appends a crossing-line canvas inside the overlay wrap) — fabricate
  // the same full element stub for any created tag.
  createElement(tag) {
    const element = __makeElement("");
    element.tagName = String(tag || "").toUpperCase();
    return element;
  },
};
globalThis.window = globalThis;
globalThis.addEventListener = function () {};
globalThis.devicePixelRatio = 1;
globalThis.location = { assign(p) { __record.locations.push(String(p)); } };
globalThis.SeaSpeedOverlayCanvas = {
  init() { return { setWorkerActive() {}, accept() {}, renderForVideoFrame() {} }; },
};
globalThis.fetch = async function (url, options) {
  const call = { url: String(url), options: options || {} };
  __record.fetch.push(call);
  if (call.url === __SESSION_PATH && !__sessionFail) {
    return { ok: true, json: async () => ({ username: __sessionUser }) };
  }
  return { ok: false, status: 401, json: async () => ({}) };
};
globalThis.setInterval = function (fn, ms) { __record.intervals.push([fn, Number(ms)]); return 0; };
globalThis.clearInterval = function () {};
globalThis.setTimeout = function (fn, ms) { __record.timeouts.push([fn, Number(ms)]); return 0; };
globalThis.clearTimeout = function () {};
"""

# Scenario assertions that need the page's own closures (the watchdog wiring
# and the identity-loss redirect) run in node; everything JSON-recordable is
# printed for the Python-side asserts.
DEFAULT_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
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
    intervals: __record.intervals.map(([fn, ms]) => ({ fn: (fn && fn.name) || "?", ms })),
    redirects: __record.locations,
    sessionUser: __record.elements.sessionUser ? __record.elements.sessionUser.textContent : null,
  }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def run_inline_scripts(
    source: Path = ROAD_PAGE,
    scenario: str = DEFAULT_SCENARIO,
    session_username: str = "operator",
    timeout: int = 30,
) -> dict:
    """Execute the page's real inline scripts under the shim and run
    ``scenario`` after the boot asyncs settle. Returns the recorded evidence:
    session fetch options, registered intervals, redirects, identity text.
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
    )
    script = PRELUDE + bootstrap + "\n;\n".join(scripts) + "\n" + scenario
    out = run_node(script, timeout=timeout)
    marker = out.rfind("###")
    if marker < 0:
        raise AssertionError(f"html harness produced no evidence record: {out!r}")
    return json.loads(out[marker + 3 :])
