"""Login popup (window.SeaSpeedAuth) — RED tests for the agreed contract.

Contract under test (agreed design, branch agent/auth-login-popup, base
main ca679e69):

* New file ``frontend/sea-speed/login-popup.js`` (deployed to the public web
  root as ``/login-popup.js``, mirroring how
  ``frontend/sea-speed/unavailable.js`` deploys to
  ``/var/www/mostdef.ru/unavailable.js``) defines ``window.SeaSpeedAuth``
  with:
  - ``LOGIN_URL`` = ``/outpost.goauthentik.io/start?rd=`` +
    encodeURIComponent(target), target defaulting to ``/sea-speed/``;
  - ``openLogin()``: ``window.open(LOGIN_URL, "sea-speed-login",
    "width=520,height=680")``, then polls ``/sea-speed/api/session`` every
    1500 ms (bounded); on the first successful response it navigates:
    ``location.reload()`` when ``location.pathname`` starts with
    ``/sea-speed/``, else ``location.href = "/sea-speed/"``;
  - ``showOverlay()``: creates a fixed full-screen overlay (id
    ``seaSpeedLoginOverlay``) with a button (id ``seaSpeedLoginBtn``)
    labelled "Войти" that calls ``openLogin()``; calling it twice must not
    create a second overlay;
  - auto-wiring: on ``DOMContentLoaded``, an existing ``#loginBtn`` gets
    its click bound to ``openLogin()``.
* Landing ``frontend/root/index.html`` gains
  ``<button id="loginBtn" type="button">Войти</button>`` and
  ``<script src="/login-popup.js"></script>``.
* The four app pages load ``/login-popup.js`` BEFORE their own page script,
  and each page's ``redirectForReauthentication()`` calls
  ``SeaSpeedAuth.showOverlay()`` instead of ``location.assign(...)`` /
  ``window.top.location.replace(...)``.
* ``deploy/vps/deploy.sh`` carries ``frontend/sea-speed/login-popup.js`` at
  every touchpoint the ``unavailable.js`` module has (TARGET var,
  release_complete -f check, required-file loop, install-to-release,
  bootstrap capture with ``.absent``, install_release module-state check,
  conditional staging, mv-promote, verify_frontends smoke), and both
  exact-artifact vps lists carry it.

RED status on the current tree (base ca679e69): every test in this module
fails, because

* ``frontend/sea-speed/login-popup.js`` does not exist (tests 1, 5, 6, 7 —
  the node twins exit 3 with HELPER_MISSING);
* ``frontend/root/index.html`` has no ``loginBtn`` and no
  ``/login-popup.js`` script tag (test 2);
* none of the four app pages loads ``/login-popup.js`` (test 3);
* all four ``redirectForReauthentication`` bodies still use
  ``location.assign(`` / ``location.replace(`` and none calls
  ``SeaSpeedAuth.showOverlay()`` (test 4);
* ``deploy/vps/deploy.sh`` has zero occurrences of
  ``frontend/sea-speed/login-popup.js`` and no ``LOGIN_POPUP_TARGET``
  variable (test 8);
* neither exact-artifact list mentions the helper (test 9).

Oracle: ``python -m unittest tests.test_login_popup -v`` (the CI battery
runs ``python -m unittest discover -s tests -p "test_*.py" -v``). The three
behavioural twins (tests 5-7) are node-based, following the style of
``tests/test_679_680_road_main_js.py``: the real helper source is loaded
under Node with stubbed ``window``/``document``/``location``/``fetch`` and
fake timers (recorded, never fired on a real clock), so the runs are
deterministic — no network, no sleeps. Node is required; if it is missing
or fails to start the tests fail loudly instead of skipping.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGIN_POPUP_JS = ROOT / "frontend" / "sea-speed" / "login-popup.js"
LANDING_HTML = ROOT / "frontend" / "root" / "index.html"
DEPLOY_SH = ROOT / "deploy" / "vps" / "deploy.sh"
BUILD_ARTIFACTS = ROOT / "scripts" / "quality" / "build_exact_artifacts.py"
VALIDATE_ARTIFACTS = ROOT / "scripts" / "quality" / "validate_exact_artifacts.py"

NODE_TIMEOUT_S = 30

HELPER_SCRIPT_TAG = 'src="/login-popup.js"'
HELPER_REPO_PATH = "frontend/sea-speed/login-popup.js"
REDIRECT_MARKER = "function redirectForReauthentication"

# (page html, the page's own main script src) — the helper must load first.
APP_PAGES = [
    (ROOT / "frontend" / "sea-speed" / "road" / "index.html", "./main.js"),
    (ROOT / "frontend" / "sea-speed" / "index.html", "/sea-speed/main.js"),
    (ROOT / "frontend" / "sea-speed" / "objects" / "index.html", "./registry.js"),
    (ROOT / "frontend" / "sea-speed" / "cameras" / "index.html", "./cameras.js"),
]

# The four page scripts carrying redirectForReauthentication.
PAGE_SCRIPTS = [
    ROOT / "frontend" / "sea-speed" / "road" / "main.js",
    ROOT / "frontend" / "sea-speed" / "main.js",
    ROOT / "frontend" / "sea-speed" / "objects" / "registry.js",
    ROOT / "frontend" / "sea-speed" / "cameras" / "cameras.js",
]


def _skip_string(source: str, i: int) -> int:
    """Return the index just past the string/template literal starting at source[i]."""
    quote = source[i]
    i += 1
    while i < len(source):
        ch = source[i]
        if ch == "\\":
            i += 2
            continue
        if quote == "`" and ch == "$" and source[i + 1 : i + 2] == "{":
            i += 2
            depth = 1
            while i < len(source) and depth:
                inner = source[i]
                if inner in "\"'`":
                    i = _skip_string(source, i)
                    continue
                if inner == "{":
                    depth += 1
                elif inner == "}":
                    depth -= 1
                i += 1
            continue
        if ch == quote:
            return i + 1
        i += 1
    raise AssertionError("unterminated string literal while brace-matching a page script")


def _extract_block(source: str, marker: str) -> str:
    """Extract the function starting at marker, brace-matched to its closing brace."""
    start = source.index(marker)
    i = source.index("{", start)
    depth = 0
    while i < len(source):
        ch = source[i]
        if ch in "\"'`":
            i = _skip_string(source, i)
            continue
        if ch == "/" and source[i + 1 : i + 2] == "/":
            newline = source.find("\n", i)
            i = len(source) if newline == -1 else newline
            continue
        if ch == "/" and source[i + 1 : i + 2] == "*":
            i = source.index("*/", i) + 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"closing brace not found for block starting at {marker!r}")


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=NODE_TIMEOUT_S,
        )
    except OSError as exc:  # node missing / not executable — fail loudly, never skip
        raise AssertionError(
            "node is required for the login-popup behavioural oracle (the CI "
            f"battery installs node 22 before running the tests) but running it failed: {exc}"
        ) from exc


def _fail_detail(proc: subprocess.CompletedProcess[str]) -> str:
    return f"node exit={proc.returncode}\n--- node stdout ---\n{proc.stdout}\n--- node stderr ---\n{proc.stderr}"


def _node_script(test_body: str) -> str:
    """Assemble the node twin: stubs, then the real helper source, then the test body.

    The helper is loaded with an indirect eval so its top-level code runs in
    the global scope where window/document/location/fetch are the stubs.
    Timers are faked (recorded, fired only by the test body's settle loop),
    so the runs are deterministic: no network, no real sleeps.
    """
    lines = [
        "const fs=require('fs');",
        "let source;",
        "try{source=fs.readFileSync(" + json.dumps(str(LOGIN_POPUP_JS)) + ",'utf8');}",
        "catch(e){console.error('HELPER_MISSING: '+e.message);process.exit(3);}",
        # --- fake timers: recorded, never fired on a real clock ---
        "const timers=[];let timerId=0;",
        "function fakeSet(fn,ms,repeat){const id=++timerId;timers.push({id,fn,ms,repeat:!!repeat,cancelled:false,fired:false});return id;}",
        "global.setTimeout=(fn,ms)=>fakeSet(fn,ms,false);",
        "global.setInterval=(fn,ms)=>fakeSet(fn,ms,true);",
        "global.clearTimeout=(id)=>{const t=timers.find(x=>x.id===id);if(t)t.cancelled=true;};",
        "global.clearInterval=global.clearTimeout;",
        # --- location stub (a /sea-speed/ page, so the contract branch is reload) ---
        "const location={pathname:'/sea-speed/road/',search:'',hash:'',href:'https://mostdef.ru/sea-speed/road/',reloadCalls:0,reload(){this.reloadCalls++;}};",
        # --- document stub ---
        "const created=[];",
        "function makeEl(tag){const el={tagName:tag,id:'',textContent:'',innerHTML:'',className:'',style:{},children:[],listeners:{},attrs:{},setAttribute(k,v){this.attrs[k]=String(v);},getAttribute(k){return Object.prototype.hasOwnProperty.call(this.attrs,k)?this.attrs[k]:null;},appendChild(c){this.children.push(c);return c;},addEventListener(t,f){(this.listeners[t]=this.listeners[t]||[]).push(f);},click(){(this.listeners['click']||[]).slice().forEach(f=>f());}};return el;}",
        "const body=makeEl('body');",
        "const docListeners={};",
        "const document={body:body,visibilityState:'visible',createElement:t=>{const el=makeEl(t);created.push(el);return el;},getElementById:id=>created.find(e=>e.id===id||e.getAttribute('id')===id)||null,addEventListener:(t,f)=>{(docListeners[t]=docListeners[t]||[]).push(f);},querySelector:()=>null,querySelectorAll:()=>[]};",
        # --- window stub ---
        "const openCalls=[];",
        "const winListeners={};",
        "const window={open:(url,name,features)=>{openCalls.push({url:String(url),name:name===undefined?null:String(name),features:features===undefined?null:String(features)});return null;},location:location,document:document,setTimeout:global.setTimeout,setInterval:global.setInterval,clearTimeout:global.clearTimeout,clearInterval:global.clearInterval,addEventListener:(t,f)=>{(winListeners[t]=winListeners[t]||[]).push(f);}};",
        "global.window=window;global.self=window;global.document=document;global.location=location;global.addEventListener=window.addEventListener;",
        # --- fetch stub (default: unauthenticated 401) ---
        "const fetchCalls=[];",
        "let fetchImpl=()=>Promise.resolve({ok:false,status:401,json:async()=>({})});",
        "const fetchStub=(url,opts)=>{fetchCalls.push(String(url));return fetchImpl(url,opts);};",
        "global.fetch=fetchStub;window.fetch=fetchStub;",
        # --- load the real helper under the stubs ---
        "(0,eval)(source);",
    ]
    lines.append(test_body)
    return "\n".join(lines) + "\n"


# Test 5 body: openLogin must open the outpost popup exactly once.
_OPEN_LOGIN_POPUP_BODY = """
(async()=>{
  const api=window.SeaSpeedAuth;
  if(!api){console.error('SeaSpeedAuth is not defined on window');process.exit(4);}
  api.openLogin();
  await new Promise(r=>setImmediate(r));
  await new Promise(r=>setImmediate(r));
  console.log(JSON.stringify({openCalls:openCalls}));
  process.exit(0);
})().catch(e=>{console.error('NODE_ERROR: '+(e&&(e.stack||String(e))));process.exit(1);});
"""

# Test 6 body: with a successful session poll, navigation must happen.
# The settle loop fires the fake timers (bounded, 300 ticks) and flushes
# microtasks between ticks; the fetch stub resolves immediately.
_NAVIGATE_AFTER_SESSION_BODY = """
(async()=>{
  const api=window.SeaSpeedAuth;
  if(!api){console.error('SeaSpeedAuth is not defined on window');process.exit(4);}
  fetchImpl=()=>Promise.resolve({ok:true,status:200,json:async()=>({username:'operator'})});
  api.openLogin();
  for(let i=0;i<300;i++){
    const pending=timers.filter(t=>!t.cancelled&&(t.repeat||!t.fired));
    for(const t of pending){t.fired=true;t.fn();}
    await new Promise(r=>setImmediate(r));
    if(location.reloadCalls>0||location.href==='/sea-speed/')break;
  }
  console.log(JSON.stringify({reloadCalls:location.reloadCalls,href:location.href,fetchCalls:fetchCalls.length}));
  process.exit(0);
})().catch(e=>{console.error('NODE_ERROR: '+(e&&(e.stack||String(e))));process.exit(1);});
"""

# Test 7 body: showOverlay twice must yield exactly one overlay + one button.
_SHOW_OVERLAY_BODY = """
(async()=>{
  const api=window.SeaSpeedAuth;
  if(!api){console.error('SeaSpeedAuth is not defined on window');process.exit(4);}
  api.showOverlay();
  api.showOverlay();
  const byId=id=>created.filter(e=>e.id===id||e.getAttribute('id')===id);
  const overlays=byId('seaSpeedLoginOverlay');
  const buttons=byId('seaSpeedLoginBtn');
  console.log(JSON.stringify({
    overlays:overlays.length,
    buttons:buttons.length,
    buttonLabel:buttons.length?buttons[0].textContent:null,
    overlayInBody:body.children.some(c=>c.id==='seaSpeedLoginOverlay'||c.getAttribute('id')==='seaSpeedLoginOverlay')
  }));
  process.exit(0);
})().catch(e=>{console.error('NODE_ERROR: '+(e&&(e.stack||String(e))));process.exit(1);});
"""


class LoginPopupContract(unittest.TestCase):
    """The login-popup helper, its page wiring, and its deploy touchpoints."""

    def test_helper_file_exists_and_exposes_api(self) -> None:
        # Contract: frontend/sea-speed/login-popup.js exists, is non-empty,
        # and defines the SeaSpeedAuth API with the outpost start URL.
        self.assertTrue(
            LOGIN_POPUP_JS.is_file(),
            f"{LOGIN_POPUP_JS} does not exist — the login-popup helper is not implemented",
        )
        text = LOGIN_POPUP_JS.read_text(encoding="utf-8")
        self.assertTrue(text.strip(), "login-popup.js must not be empty")
        for token in ("SeaSpeedAuth", "openLogin", "showOverlay", "/outpost.goauthentik.io/start"):
            self.assertIn(
                token,
                text,
                f"login-popup.js must expose {token!r} (window.SeaSpeedAuth contract)",
            )

    def test_landing_has_login_button_and_loads_helper(self) -> None:
        # Contract: the landing page gains a #loginBtn button and loads the
        # helper from the public web root.
        html = LANDING_HTML.read_text(encoding="utf-8")
        self.assertIn(
            'id="loginBtn"',
            html,
            "frontend/root/index.html must contain the login button (id=\"loginBtn\")",
        )
        self.assertIn(
            HELPER_SCRIPT_TAG,
            html,
            "frontend/root/index.html must load <script src=\"/login-popup.js\">",
        )

    def test_app_pages_load_helper_before_page_script(self) -> None:
        # Contract: each of the four app pages loads /login-popup.js BEFORE
        # its own page script, so SeaSpeedAuth exists when the page script
        # runs.
        for page, own_script in APP_PAGES:
            html = page.read_text(encoding="utf-8")
            self.assertIn(
                HELPER_SCRIPT_TAG,
                html,
                f"{page.relative_to(ROOT)} must load <script src=\"/login-popup.js\">",
            )
            self.assertIn(
                f'src="{own_script}"',
                html,
                f"{page.relative_to(ROOT)} must load its own page script {own_script!r}",
            )
            self.assertLess(
                html.index(HELPER_SCRIPT_TAG),
                html.index(f'src="{own_script}"'),
                f"{page.relative_to(ROOT)}: /login-popup.js must appear BEFORE the "
                f"page's own script {own_script!r}",
            )

    def test_app_pages_use_overlay_instead_of_redirect(self) -> None:
        # Contract: each page's redirectForReauthentication() shows the
        # SeaSpeedAuth overlay instead of navigating away (location.assign /
        # window.top.location.replace).
        for script in PAGE_SCRIPTS:
            source = script.read_text(encoding="utf-8")
            self.assertIn(
                REDIRECT_MARKER,
                source,
                f"{script.relative_to(ROOT)} must define redirectForReauthentication",
            )
            body = _extract_block(source, REDIRECT_MARKER)
            self.assertIn(
                "SeaSpeedAuth.showOverlay()",
                body,
                f"{script.relative_to(ROOT)}: redirectForReauthentication must call "
                f"SeaSpeedAuth.showOverlay(); got: {body}",
            )
            self.assertNotIn(
                "location.assign(",
                body,
                f"{script.relative_to(ROOT)}: redirectForReauthentication must not "
                f"call location.assign(); got: {body}",
            )
            self.assertNotIn(
                "location.replace(",
                body,
                f"{script.relative_to(ROOT)}: redirectForReauthentication must not "
                f"call location.replace(); got: {body}",
            )

    def test_open_login_opens_popup_with_outpost_url(self) -> None:
        # Behavioural twin: with stubbed window.open/fetch/location/document,
        # openLogin() must call window.open exactly once with the outpost
        # start URL carrying the rd= return-to parameter.
        proc = _run_node(_node_script(_OPEN_LOGIN_POPUP_BODY))
        self.assertEqual(proc.returncode, 0, _fail_detail(proc))
        payload = json.loads(proc.stdout)
        self.assertEqual(
            len(payload["openCalls"]),
            1,
            "openLogin() must call window.open exactly once\n" + _fail_detail(proc),
        )
        url = payload["openCalls"][0]["url"]
        self.assertIn(
            "/outpost.goauthentik.io/start",
            url,
            f"window.open URL must target the outpost start endpoint, got: {url!r}",
        )
        self.assertIn(
            "rd=",
            url,
            f"window.open URL must carry the rd= return-to parameter, got: {url!r}",
        )

    def test_open_login_navigates_after_session_success(self) -> None:
        # Behavioural twin: with the session poll resolving successfully,
        # openLogin() must navigate — location.reload() (the stubbed page is
        # under /sea-speed/) or location.href set to /sea-speed/.
        proc = _run_node(_node_script(_NAVIGATE_AFTER_SESSION_BODY))
        self.assertEqual(proc.returncode, 0, _fail_detail(proc))
        payload = json.loads(proc.stdout)
        self.assertTrue(
            payload["reloadCalls"] >= 1 or payload["href"] == "/sea-speed/",
            "after a successful /sea-speed/api/session poll the page must navigate "
            "(location.reload() or location.href='/sea-speed/'); observed "
            f"reloadCalls={payload['reloadCalls']}, href={payload['href']!r}, "
            f"fetchCalls={payload['fetchCalls']}\n" + _fail_detail(proc),
        )

    def test_show_overlay_creates_single_overlay_with_login_button(self) -> None:
        # Behavioural twin: showOverlay() called twice must create exactly one
        # overlay (id seaSpeedLoginOverlay, appended to body) and exactly one
        # button (id seaSpeedLoginBtn) labelled "Войти".
        proc = _run_node(_node_script(_SHOW_OVERLAY_BODY))
        self.assertEqual(proc.returncode, 0, _fail_detail(proc))
        payload = json.loads(proc.stdout)
        self.assertEqual(
            payload["overlays"],
            1,
            "showOverlay() called twice must create exactly one overlay element "
            f"(id seaSpeedLoginOverlay), got {payload['overlays']}\n" + _fail_detail(proc),
        )
        self.assertEqual(
            payload["buttons"],
            1,
            "exactly one button (id seaSpeedLoginBtn) must exist, "
            f"got {payload['buttons']}\n" + _fail_detail(proc),
        )
        self.assertEqual(
            payload["buttonLabel"],
            "Войти",
            f"the overlay button must be labelled 'Войти', got {payload['buttonLabel']!r}\n"
            + _fail_detail(proc),
        )
        self.assertTrue(
            payload["overlayInBody"],
            "the overlay must be appended to document.body\n" + _fail_detail(proc),
        )

    def test_deploy_script_copies_login_popup(self) -> None:
        # Contract: deploy/vps/deploy.sh carries frontend/sea-speed/login-popup.js
        # at every touchpoint the unavailable.js module has — release_complete
        # -f check, required-file loop, install-to-release, bootstrap capture
        # (file + .absent), install_release module-state check (file + .absent),
        # conditional staging, mv-promote, verify_frontends smoke — plus a
        # LOGIN_POPUP_TARGET-style variable.
        text = DEPLOY_SH.read_text(encoding="utf-8")
        count = text.count(HELPER_REPO_PATH)
        self.assertGreaterEqual(
            count,
            8,
            f"deploy/vps/deploy.sh must carry {HELPER_REPO_PATH!r} at every "
            f"unavailable.js-style touchpoint (>= 8 occurrences), found {count}",
        )
        self.assertIn(
            "LOGIN_POPUP_TARGET",
            text,
            "deploy/vps/deploy.sh must define a LOGIN_POPUP_TARGET-style variable "
            "(mirroring UNAVAILABLE_JS_TARGET)",
        )

    def test_exact_artifact_lists_carry_login_popup(self) -> None:
        # Contract: both exact-artifact vps lists carry the helper so the
        # release archive and the validation gate agree on it.
        for path in (BUILD_ARTIFACTS, VALIDATE_ARTIFACTS):
            self.assertIn(
                HELPER_REPO_PATH,
                path.read_text(encoding="utf-8"),
                f"{path.relative_to(ROOT)} must list {HELPER_REPO_PATH!r} in its vps "
                "exact-artifact set",
            )


if __name__ == "__main__":
    unittest.main()
