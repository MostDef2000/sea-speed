"""Issues #679 + #680: two swallowed ReferenceErrors in the road operator page.

frontend/sea-speed/road/main.js carries two real runtime bugs, both silent
because the surrounding catch swallows the throw:

* #679 — loadSpeedConfig() was copy-pasted from frontend/sea-speed/main.js:38,
  where the fetched payload is named ``d``. The road copy declares ``f``
  (``const f=await jsonReq(SPEED_CONFIG_URL)``) but then reads the undeclared
  ``d`` — ``d.enabled`` and ``Number(d.kmh_per_px_s)`` inside the template
  literal. Every call throws ``ReferenceError: d is not defined``; the
  function's own catch turns that into "Speed config: ошибка загрузки", so
  the operator sees a load failure even when the API is healthy.
* #680 — the ``cxOffBtn.onclick`` re-enable branch posts
  ``{enabled:true,line}``, but ``line`` is a local of the neighbouring
  ``cxSaveBtn.onclick`` handler and does not exist in this scope. Turning a
  crossing line back on after turning it off throws
  ``ReferenceError: line is not defined``, is caught, and surfaces as
  "ошибка переключения" — the line can never be re-enabled.

The oracle is behavioural, not a grep: each test extracts the real function
source from frontend/sea-speed/road/main.js (marker locate + brace matching
that skips string/template literals and comments), evals it under Node with
stubbed DOM elements and stubbed jsonReq/postJson, runs it, and asserts on
the observed behaviour (input value, status text, posted payload). Node is
required — the CI battery installs node 22 before running the tests; if node
is missing or fails to start, the tests fail loudly instead of skipping.

On base 30773ae both tests are RED: the swallowed ReferenceErrors leave the
fallback status text ("Speed config: ошибка загрузки" / "ошибка
переключения") and an empty calls array. After the two identifier fixes they
pass unchanged (GREEN). A diagnostic raw run with the swallowing catch
stripped (best-effort, guarded on the exact catch shape, never affecting
pass/fail) surfaces the underlying ``ReferenceError: d is not defined`` /
``ReferenceError: line is not defined`` on stderr so a failure points at the
real cause instead of only at the fallback text.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROAD_MAIN_JS = ROOT / "frontend" / "sea-speed" / "road" / "main.js"
NODE_TIMEOUT_S = 30

LOAD_SPEED_CONFIG_MARKER = "async function loadSpeedConfig"
CX_OFF_HANDLER_MARKER = "cxOffBtn.onclick="

# Exact wrapper shapes of the two blocks, used only by the diagnostic raw run
# to strip the swallowing catch. The behavioural assertions never depend on
# them: if the shape ever changes, the diagnostic is skipped silently.
LOAD_FN_PREFIX = "async function loadSpeedConfig(){try{"
LOAD_CATCH_SUFFIX = '}catch(e){speedConfigStatus.textContent="Speed config: ошибка загрузки"}}'
CX_HANDLER_PREFIX = "cxOffBtn.onclick=async()=>{try{"
CX_CATCH_SUFFIX = '}catch(e){cxStatus.textContent="ошибка переключения"}}'

EXPECTED_POSTED_LINE = [{"x": 10, "y": 20}, {"x": 30, "y": 40}]


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
            # Template substitution: scan the ${...} code, honouring nested
            # strings and braces, then resume scanning the template text.
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
    raise AssertionError("unterminated string literal while brace-matching road/main.js")


def _extract_block(source: str, marker: str) -> str:
    """Extract the statement/function starting at marker, brace-matched to its closing brace."""
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


def _strip_swallowing_catch(block: str, prefix: str, suffix: str) -> str | None:
    """Rebuild the block without its outer try/catch, or None if the shape changed."""
    if not (block.startswith(prefix) and block.endswith(suffix)):
        return None
    body = block[len(prefix) : len(block) - len(suffix)]
    return prefix[: -len("try{")] + body + "}"


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
            "node is required for the behavioural #679/#680 oracle (the CI battery "
            f"installs node 22 before running the tests) but running it failed: {exc}"
        ) from exc


def _fail_detail(proc: subprocess.CompletedProcess[str]) -> str:
    return f"node exit={proc.returncode}\n--- node stdout ---\n{proc.stdout}\n--- node stderr ---\n{proc.stderr}"


def _diagnostic_lines(raw_source: str | None, call: str) -> list[str]:
    """JS lines that re-run the block with the swallowing catch stripped.

    Purely diagnostic: a throw is caught and reported on stderr so a RED run
    shows the underlying ReferenceError, and it can never change the exit
    code or the JSON the assertions read.
    """
    if raw_source is None:
        return []
    return [
        "  try{",
        "    eval(" + json.dumps(raw_source) + ");",
        "    await " + call + ";",
        "  }catch(e){console.error('DIAGNOSTIC raw run (swallowing catch stripped) threw: '+(e&&(e.stack||String(e))));}",
    ]


def _speed_config_script(extracted: str, payload: dict) -> str:
    raw = _strip_swallowing_catch(extracted, LOAD_FN_PREFIX, LOAD_CATCH_SUFFIX)
    lines = [
        'const SPEED_CONFIG_URL="/x";',
        "const jsonReq=async()=>(" + json.dumps(payload) + ");",
        'const speedFactorInput={value:""};',
        'const speedConfigStatus={textContent:""};',
        "eval(" + json.dumps(extracted) + ");",
        "(async()=>{",
        "  await loadSpeedConfig();",
        "  console.log(JSON.stringify({value:speedFactorInput.value,status:speedConfigStatus.textContent}));",
        *_diagnostic_lines(raw, "loadSpeedConfig()"),
        "})().catch(e=>{console.error(e&&(e.stack||String(e)));process.exit(1)});",
    ]
    return "\n".join(lines) + "\n"


def _cx_off_script(extracted: str) -> str:
    raw = _strip_swallowing_catch(extracted, CX_HANDLER_PREFIX, CX_CATCH_SUFFIX)
    lines = [
        'const CROSSING_LINE_URL="/x";',
        "let crossingCfg={enabled:false,line:[{x:10,y:20},{x:30,y:40}]};",
        "const calls=[];",
        "const postJson=async(u,b)=>{calls.push(b);return {enabled:b.enabled,line:b.line}};",
        'const cxStatus={textContent:""};',
        'const cxOffBtn={textContent:""};',
        "const drawCrossing=()=>{};",
        "eval(" + json.dumps(extracted) + ");",
        "(async()=>{",
        "  await cxOffBtn.onclick();",
        "  console.log(JSON.stringify({calls:calls,status:cxStatus.textContent,btn:cxOffBtn.textContent}));",
        *_diagnostic_lines(raw, "cxOffBtn.onclick()"),
        "})().catch(e=>{console.error(e&&(e.stack||String(e)));process.exit(1)});",
    ]
    return "\n".join(lines) + "\n"


class RoadMainJsReferenceErrors(unittest.TestCase):
    """The road page's loadSpeedConfig and cxOffBtn.onclick run without ReferenceErrors."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ROAD_MAIN_JS.read_text(encoding="utf-8")

    def test_679_load_speed_config_uses_declared_payload(self) -> None:
        # AC-001/AC-002 (issue #679): loadSpeedConfig must read the payload
        # variable it actually declares (f), not the undeclared d copied from
        # the water page.
        # Behavioural proof: with a healthy API the input shows the formatted
        # coefficient and the status reports the enabled state instead of the
        # "ошибка загрузки" fallback the swallowed ReferenceError produces.
        extracted = _extract_block(self.source, LOAD_SPEED_CONFIG_MARKER)
        self.assertTrue(
            extracted.startswith(LOAD_SPEED_CONFIG_MARKER),
            "extracted loadSpeedConfig source does not start at its marker",
        )
        proc_on = _run_node(_speed_config_script(extracted, {"enabled": True, "kmh_per_px_s": 12.5}))
        self.assertEqual(proc_on.returncode, 0, _fail_detail(proc_on))
        payload_on = json.loads(proc_on.stdout)
        self.assertEqual(
            payload_on["value"],
            "12.500",
            "speedFactorInput.value must show the API coefficient formatted to "
            f"3 decimals\n{_fail_detail(proc_on)}",
        )
        self.assertIn(
            "включен",
            payload_on["status"],
            "speedConfigStatus must report the enabled state for a healthy API; "
            f"the 'ошибка загрузки' fallback means the ReferenceError is still "
            f"swallowed\n{_fail_detail(proc_on)}",
        )
        proc_off = _run_node(_speed_config_script(extracted, {"enabled": False, "kmh_per_px_s": 12.5}))
        self.assertEqual(proc_off.returncode, 0, _fail_detail(proc_off))
        payload_off = json.loads(proc_off.stdout)
        self.assertIn(
            "выключен",
            payload_off["status"],
            "speedConfigStatus must report the disabled state\n" + _fail_detail(proc_off),
        )

    def test_680_cx_off_reenable_posts_persisted_line(self) -> None:
        # AC-003 (issue #680): re-enabling a disabled crossing line must post
        # the persisted crossingCfg.line, not the undeclared line borrowed
        # from the cxSaveBtn handler (ReferenceError -> "ошибка
        # переключения", no call).
        extracted = _extract_block(self.source, CX_OFF_HANDLER_MARKER)
        self.assertTrue(
            extracted.startswith(CX_OFF_HANDLER_MARKER),
            "extracted cxOffBtn.onclick source does not start at its marker",
        )
        proc = _run_node(_cx_off_script(extracted))
        self.assertEqual(proc.returncode, 0, _fail_detail(proc))
        payload = json.loads(proc.stdout)
        self.assertEqual(
            len(payload["calls"]),
            1,
            "re-enabling must issue exactly one POST\n" + _fail_detail(proc),
        )
        self.assertEqual(
            payload["calls"][0],
            {"enabled": True, "line": EXPECTED_POSTED_LINE},
            "the re-enable POST must carry enabled:true and the persisted "
            f"crossingCfg.line\n{_fail_detail(proc)}",
        )


if __name__ == "__main__":
    unittest.main()
