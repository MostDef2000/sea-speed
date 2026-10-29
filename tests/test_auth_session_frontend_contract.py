"""Executed twins for the protected-frontends session contract (issue #398
waves 2 and 4).

Wave 2 converted the road page's watchdog semantics to an execution of the
page's real inline scripts. Wave 4 retires the remaining raw source-text
pins: every protected frontend now boots under the frontend_html shim and
the session contract is asserted on the executed page — the same-origin
session endpoint is the only identity source (every recorded fetch stays on
relative /sea-speed/ paths, credentials stay same-origin, the trusted
username populates the page), web storage never exists in the page scope,
the provider logout link and the project-home link are real anchor
attributes in the markup, and the operator page's HLS stream loads the
protected camera media path (loadSource is driven through the recorded
MEDIA_ATTACHED handler, so a rewired stream URL fails the test even when the
historical marker text survives).
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.support import frontend_html

FRONTENDS = (
    ROOT / "frontend/sea-speed/index.html",
    ROOT / "frontend/sea-speed/cameras/index.html",
    ROOT / "frontend/sea-speed/objects/index.html",
    ROOT / "frontend/sea-speed/road/index.html",
)
WATER_PAGE = ROOT / "frontend/sea-speed/index.html"
SESSION_PATH = frontend_html.SESSION_PATH
PROTECTED_HLS = "/sea-speed/media/cam1/index.m3u8"
RETIRED_HLS = "/cams/hls/cam1/index.m3u8"

# Drive the water page's real stream wiring: drain the recorded boot timeout
# (connectStream), then fire the recorded HLS MEDIA_ATTACHED handlers so the
# page calls loadSource itself — the recorded sources are the executed
# evidence for which media path the operator stream uses.
WATER_HLS_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await new Promise((r) => setImmediate(r));
  const instances = __record.hlsInstances;
  assert(instances.length >= 1, "no HLS instance was created at boot");
  const attached = instances.flatMap((inst) => inst.attached.map((el) => el && el.id));
  assert(attached.includes("waterMainVideo"), "HLS was not attached to the waterMainVideo element");
  for (const inst of instances) {
    for (const handler of inst.handlers.hlsMediaAttached || []) await handler();
  }
  const sources = instances.flatMap((inst) => inst.sources);
  assert(
    sources.includes("/sea-speed/media/cam1/index.m3u8"),
    "HLS loadSource must use the protected media path /sea-speed/media/cam1/index.m3u8; got " + JSON.stringify(sources)
  );
  assert(
    sources.every((source) => !source.includes("/cams/hls/")),
    "the retired camera media path must not be loaded"
  );
  assert(
    window.hls === window.waterHls && window.hls === instances[instances.length - 1],
    "the live HLS instance must be published as window.hls and window.waterHls"
  );
  console.log("###" + JSON.stringify({ sources, attached }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def anchor_attribute(tag: str, name: str) -> str | None:
    match = re.search(rf'\b{name}="([^"]*)"', tag)
    return match.group(1) if match else None


# Page-agnostic executed session twin: every protected frontend must watch
# its trusted identity on the 15 s watchdog, fetch it same-origin, populate
# the trusted element, and on identity loss AFTER establishment redirect to
# the page's own protected URL (road pages location.assign the road path;
# water/cameras/objects window.top.location.replace the current
# pathname+search+hash — the assertion accepts the recorded evidence of
# either wiring, so a page that switches between them stays green).
SESSION_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  assert(typeof localStorage === "undefined", "localStorage must not exist in the page scope");
  assert(typeof sessionStorage === "undefined", "sessionStorage must not exist in the page scope");
  const watchdogs = __record.intervals.filter(([, ms]) => ms === __WATCHDOG_MS);
  assert(watchdogs.length >= 1, "no " + __WATCHDOG_MS + " ms interval registered (session watchdog missing)");
  const fireWatchdogs = async () => {
    for (const watchdog of watchdogs) {
      await watchdog[0]();
      await new Promise((r) => setImmediate(r));
    }
  };
  const fetchCountBefore = __record.fetch.length;
  await fireWatchdogs();
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
  await fireWatchdogs();
  assert(
    __record.locations.includes(__REDIRECT) ||
      __record.replaces.includes(location.pathname + location.search + location.hash),
    "identity loss after establishment must redirect to the protected URL"
  );
  console.log("###" + JSON.stringify({
    sessionFetches: __record.fetch.filter((c) => c.url === __SESSION_PATH).map((c) => c.options),
    fetchUrls: __record.fetch.map((c) => c.url),
    intervals: __record.intervals.map(([fn, ms]) => ({ fn: (fn && fn.name) || "?", ms })),
    redirects: __record.locations,
    replaces: __record.replaces,
    sessionUser: __record.elements.sessionUser ? __record.elements.sessionUser.textContent : null,
  }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


class AuthSessionFrontendContractTests(unittest.TestCase):
    def test_all_protected_frontends_use_same_origin_session_api(self) -> None:
        for path in FRONTENDS:
            with self.subTest(path=path.relative_to(ROOT)):
                evidence = frontend_html.run_inline_scripts(source=path, scenario=SESSION_SCENARIO)
                session_fetches = evidence["sessionFetches"]
                self.assertTrue(session_fetches, "session endpoint never fetched")
                for options in session_fetches:
                    self.assertEqual(options.get("credentials"), "same-origin")
                self.assertEqual(evidence["sessionUser"], "operator")
                # Every recorded fetch stays on the same-origin relative API
                # namespace: no absolute URLs, no authentik outpost detour.
                self.assertTrue(evidence["fetchUrls"], "no fetches recorded")
                for url in evidence["fetchUrls"]:
                    self.assertTrue(
                        url.startswith("/sea-speed/"),
                        f"fetch left the same-origin /sea-speed/ namespace: {url}",
                    )
                    self.assertNotIn("outpost.goauthentik.io", url)
                # The identity comes from the session payload, never from a
                # spoofable request header.
                scripts = "\n".join(frontend_html.extract_inline_scripts(path.read_text(encoding="utf-8-sig")))
                self.assertNotIn("X-authentik-username", scripts)

    def test_logout_and_lighthouse_contract_is_preserved(self) -> None:
        for path in FRONTENDS:
            with self.subTest(path=path.relative_to(ROOT)):
                html = path.read_text(encoding="utf-8-sig")
                # The provider logout link is a real anchor attribute.
                anchors = re.findall(r"<a\b[^>]*>", html)
                self.assertTrue(
                    any(anchor_attribute(anchor, "href") == "/outpost.goauthentik.io/sign_out" for anchor in anchors),
                    "no anchor links the authentik provider sign_out endpoint",
                )
                # The lighthouse/nav contract: a project-home anchor to /.
                project_home = [anchor for anchor in anchors if "project-home" in (anchor_attribute(anchor, "class") or "")]
                self.assertTrue(project_home, "no project-home anchor in the header")
                self.assertTrue(
                    any(anchor_attribute(anchor, "href") == "/" for anchor in project_home),
                    "project-home anchor must link to /",
                )
                # Storage ban: asserted in the executed page scope by the
                # session scenario (no storage globals may exist or be used).
                evidence = frontend_html.run_inline_scripts(source=path, scenario=SESSION_SCENARIO)
                self.assertEqual(evidence["sessionUser"], "operator")

    def test_operator_keeps_protected_camera_media_path(self) -> None:
        # Executed twin: the water page's real stream wiring must loadSource
        # the protected /sea-speed/media/ HLS path (and never the retired
        # /cams/hls/ path) and publish the instance as window.hls/waterHls.
        evidence = frontend_html.run_inline_scripts(source=WATER_PAGE, scenario=WATER_HLS_SCENARIO)
        self.assertEqual(evidence["sources"], [PROTECTED_HLS])
        self.assertIn("waterMainVideo", evidence["attached"])

    def test_road_session_watchdog_matches_protected_operator_semantics(self) -> None:
        # Behavioral conversion (issue #398 wave 2): the page's real inline
        # scripts execute in node under the frontend_html shim — the 15 s
        # watchdog wiring, the same-origin session fetch, the identity
        # population and the identity-loss redirect are asserted on the
        # executed page, not on its formatting (reformatting or renaming
        # internals keeps this green; breaking the wiring fails it even when
        # the historical marker text survives).
        evidence = frontend_html.run_inline_scripts()
        self.assertIn(
            frontend_html.WATCHDOG_MS,
            [interval["ms"] for interval in evidence["intervals"]],
            "15 s session watchdog interval missing",
        )
        self.assertTrue(evidence["sessionFetches"], "session endpoint never fetched")
        self.assertEqual(evidence["sessionFetches"][0].get("credentials"), "same-origin")
        self.assertEqual(evidence["sessionUser"], "operator")
        self.assertEqual(evidence["redirects"], [frontend_html.REDIRECT_PATH])


if __name__ == "__main__":
    unittest.main()
