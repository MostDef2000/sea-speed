"""RED regression tests for MostDef2000/sea-speed#617 (wave-2 task B).

Issue #617: ``post_analytics_state`` (api/app/main.py:748) accepts free-form
worker JSON in the ``metadata`` form field and persists it verbatim via
``store.upsert_camera_state`` (api/app/store.py:704, ``json.dumps`` default
``allow_nan=True``) — bare ``NaN``/``Infinity`` tokens (including the
``1e999`` overflow literal, which ``json.loads`` parses to ``inf``) land in
``camera_state.payload_json``: invalid strict JSON for JS clients. The #587
wave delivered the boundary helper ``store.find_nonfinite_json_value``
(api/app/store.py:390 — returns the offending dotted path or None) and wired
it into the sibling persist sites (measurement_meta, deliver_event); the
analytics-state upsert was left unguarded.

Desired behavior pinned here: a non-finite numeric leaf anywhere in the
payload is rejected with HTTP 400 BEFORE the upsert (detail names the
offending path into the payload structure, same idiom as the #587 sites),
the rejected input causes NO state change (no ``camera_state`` row created
or changed), and finite payloads persist exactly as before.

This file pins the DESIRED behavior. On base 358a2ff every rejection test
FAILS for the documented current-vs-desired reason (the handler returns
``{"ok": True}`` and the bare NaN/Infinity token is persisted); once the fix
lands the tests pass unchanged. No test is weakened, skipped, or xfailed,
and no code under test is mocked.

Harness variant — handler-level exec harness, NOT TestClient (same decision
as tests/test_616_optional_int_overflow.py, documented there): the
TestClient variant used by tests/test_587_nonfinite_residual_paths.py needs
the guarded-optional ``fastapi``/``httpx`` probe whose exact per-file
registry is pinned by tests/test_run_tests_script.py's import-hygiene scan
(test_guarded_optional_probe_is_the_fastapi_stub_fallback) — registering a
new guarded-optional file means extending that pinned list, which lives
outside this fix's allowed paths. The exec harness below pins the same
defect without a third-party import, so the one-process battery stays green
and the import-hygiene gate is not gamed with scanner-invisible dynamic
imports. Unlike #616 (which stubs the sinks), this file binds the REAL
``api.app.store`` module — store.py is deliberately fastapi-free and
stdlib-only (importable in CI), so the actual ``upsert_camera_state``
persist path, the actual ``find_nonfinite_json_value`` scan and the actual
``camera_state.payload_json`` bytes are exercised, not a sink stub.

    Stubbed seams (never the code under test): ``require_auth`` (auth
boundary), ``analytics_identity`` (identity seam), ``analytics_default_state``
(default-state factory), ``now_iso`` (clock), the schema constants, and the
fastapi Form/File/Header decorator-arg seam (evaluated at def time by the
exec'd handler signature; never called — all handler args are passed
positionally). The extracted handler's ``@app.post`` route decorator is
stripped (route-registration seam, not handler code — the route adds no
exception handling of its own, same #616 precedent).

Characterization notes (observed on base 358a2ff):

* ``json.loads`` ACCEPTS bare ``NaN`` / ``Infinity`` tokens (they reach the
  handler as ``float('nan')`` / ``float('inf')``); ``1e999`` parses to
  ``inf``; there is no 422 parser-rejection path.
* On base the handler returns 200 and PERSISTS: ``camera_state.payload_json``
  contains bare ``NaN`` / ``Infinity`` tokens (invalid strict JSON). The RED
  signal is the no-state-change assertion (state changed) — that is the
  point; it is asserted FIRST, same persist-site idiom as the #587 sites 4-5
  in tests/test_587_nonfinite_residual_paths.py.
* The handler injects only finite values into the payload before the persist
  (camera_id/analytics_profile/domain strings, schema constants, ISO
  timestamp, bools, ints), so the offending path reported by the guard always
  points into the worker-supplied payload structure.
* The overlay branch (multipart file write) is exercised by one pin: the
  EARLY scan rejects before the overlay media write (tmp write + os.replace
  of ``{camera_id}_latest_overlay.jpg``), so a rejected request carrying an
  overlay leaves the previous overlay file byte-unchanged with no ``.tmp``
  stray; the remaining rejection pins send ``overlay=None``. The final scan
  (right before the persist) stays because the no-overlay branch merges
  ``overlay_rev`` from ``old_state``, which can carry NaN from pre-fix rows.

One-process battery contract: this file imports only stdlib plus the
repo-local ``api.app.store`` (fastapi-free by contract, see store.py's
``find_nonfinite_json_value`` docstring) — no guarded-optional probe, no
sys.modules eviction needed; the api.app.* names cached here are stateless
(store.py reads no environment at import time), so sibling files that
re-import api.app.* with their own env overrides are unaffected.
"""

from __future__ import annotations

import ast
import asyncio
import copy
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import store  # repo-local; the real persist path under test

MAIN_SOURCE = ROOT / "api" / "app" / "main.py"

# Gitleaks-safe fixture values (same convention as the #587/#616 files):
# low-entropy throwaway constants for a disposable temp environment.
ANALYTICS_PROFILE_FIXTURE = "water-v1"
WORKER_STATE_SCHEMA_FIXTURE = "worker-state-schema-617"
TELEMETRY_SCHEMA_FIXTURE = "telemetry-schema-617"
STUB_NOW_ISO = "2026-11-09T00:00:00+00:00"

# Placeholder used to inject a raw non-finite literal (``1e999``) into a JSON
# document that ``json.dumps`` cannot emit from a Python value (a float
# cannot represent 1e999 — it overflows to inf). The placeholder is a quoted
# JSON string in the serialized document and is replaced by the bare literal
# before the metadata string reaches the handler. Same idiom as
# tests/test_587_nonfinite_residual_paths.py.
RAW_LITERAL_PLACEHOLDER = "__RAW_NONFINITE_617__"


class HTTPExceptionStub(Exception):
    """Stand-in for fastapi.HTTPException in the exec'd handler body."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class OverlayUploadStub:
    """Stand-in for fastapi's UploadFile: the handler only awaits read()."""

    def __init__(self, payload: bytes):
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


def load_handler_functions(sources: list, names: set, namespace: dict) -> dict:
    """AST-extract the named (async) handlers and exec them into ``namespace``.

    Same harness idiom as tests/test_616_optional_int_overflow.py (which
    follows tests/test_numeric_input_validation.py): the extracted function
    bodies run against a stub namespace, so they must stay module-import-free
    (any module-level reference raises NameError at call time). The #617
    guard under test calls ``store.find_nonfinite_json_value`` /
    ``store.upsert_camera_state`` through the REAL api.app.store module bound
    into the namespace by the test class below.
    """
    selected = []
    found = set()
    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
        for node in tree.body:
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in names
                and node.name not in found
            ):
                node = copy.deepcopy(node)
                # Strip the fastapi route decorator (@app.post(...)): the
                # decorator is the route-registration seam, not handler code —
                # executing it would need the live ``app`` object. The exec'd
                # statement is the bare handler, called exactly as the route
                # calls it (all args positional).
                node.decorator_list = []
                selected.append(node)
                found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing handler functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(sources[0]), "exec"), namespace)
    return namespace


class AnalyticsStateNonFiniteTests(unittest.TestCase):
    """RED pins: non-finite payload JSON must be 400 with no state change.

    The REAL ``post_analytics_state`` (api/app/main.py:748) runs against the
    REAL store module (``upsert_camera_state`` / ``read_camera_state`` /
    ``find_nonfinite_json_value``) with a fresh temp ``STATE_DB_FILE`` per
    test; only the auth/identity/clock seams and the fastapi decorator-arg
    seam are stubbed.
    """

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="sea-speed-617-state-")
        self.addCleanup(temp.cleanup)
        self.state_db = Path(temp.name) / "state" / "state.sqlite3"
        self.overlay_dir = Path(temp.name) / "overlays"
        self.ns: Dict[str, Any] = {
            "Any": Any,
            "Dict": Dict,
            "Optional": Optional,
            "HTTPException": HTTPExceptionStub,
            # fastapi decorator-arg seam: evaluated at def time only.
            "Form": lambda *args, **kwargs: None,
            "File": lambda *args, **kwargs: None,
            "Header": lambda *args, **kwargs: None,
            "UploadFile": object,  # annotation-only placeholder
            # Seams (not the code under test):
            "require_auth": lambda authorization: None,
            "analytics_identity": lambda camera_id: {
                "analytics_profile": ANALYTICS_PROFILE_FIXTURE,
                "domain": "water",
            },
            "analytics_default_state": lambda camera_id: {
                "camera_id": camera_id,
                "last_overlay_url": None,
                "overlay_rev": 0,
                "frame_no": 0,
            },
            "now_iso": lambda: STUB_NOW_ISO,
            "WORKER_STATE_SCHEMA": WORKER_STATE_SCHEMA_FIXTURE,
            "TELEMETRY_SCHEMA": TELEMETRY_SCHEMA_FIXTURE,
            # Real production state surface (fresh temp DB per test).
            "STATE_DB_FILE": self.state_db,
            "OVERLAY_DIR": self.overlay_dir,
            "store": store,
            "json": json,
            "os": os,
        }
        load_handler_functions([MAIN_SOURCE], {"post_analytics_state"}, self.ns)
        self.handler = self.ns["post_analytics_state"]

    # -- helpers -----------------------------------------------------------

    def call_state(self, camera_id: str, raw_metadata: str) -> Any:
        # The route is async; drive it the way the server would. overlay=None
        # and authorization=None (both seams stubbed).
        return asyncio.run(self.handler(camera_id, raw_metadata, None, None))

    def raw_json(self, payload: Dict[str, Any]) -> str:
        # json.dumps(allow_nan=True) emits bare NaN/Infinity tokens for
        # float('nan')/float('inf') — exactly the non-strict JSON a Python
        # worker would ship in the metadata form field.
        return json.dumps(payload)

    def raw_json_with_literal(self, payload: Dict[str, Any], literal: str) -> str:
        # Replace the quoted placeholder with a bare non-finite literal
        # (e.g. 1e999) that json.dumps cannot emit from a Python value.
        return json.dumps(payload).replace(f'"{RAW_LITERAL_PLACEHOLDER}"', literal)

    def _stored_payload_json(self, camera_id: str) -> Optional[str]:
        """Raw ``camera_state.payload_json`` text for a camera, or None."""
        if not self.state_db.exists():
            return None
        connection = sqlite3.connect(f"file:{self.state_db}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT payload_json FROM camera_state WHERE camera_id = ?", (camera_id,)
            ).fetchone()
            return None if row is None else row[0]
        finally:
            connection.close()

    def _overlay_tree(self) -> list:
        if not self.overlay_dir.is_dir():
            return []
        return sorted(
            str(p.relative_to(self.overlay_dir))
            for p in self.overlay_dir.rglob("*")
            if p.is_file()
        )

    def state_snapshot(self) -> Dict[str, Any]:
        """Every state surface post_analytics_state can touch.

        The full ``camera_state`` table (camera_id, payload_json, updated_at)
        plus the overlay media tree. Asserted equal before/after each
        rejection case to pin "no state change" (no upsert of any kind).
        """
        rows: list = []
        if self.state_db.exists():
            connection = sqlite3.connect(f"file:{self.state_db}?mode=ro", uri=True)
            try:
                rows = sorted(
                    connection.execute(
                        "SELECT camera_id, payload_json, updated_at FROM camera_state"
                    ).fetchall()
                )
            finally:
                connection.close()
        return {"camera_state_rows": rows, "overlay_tree": self._overlay_tree()}

    def assert_no_state_change(self, before: Dict[str, Any], label: str) -> None:
        after = self.state_snapshot()
        self.assertEqual(
            after,
            before,
            f"state changed for {label}: "
            f"before={json.dumps(before, sort_keys=True, default=str)} "
            f"after={json.dumps(after, sort_keys=True, default=str)}",
        )

    def rejection_with_no_state_change(
        self,
        camera_id: str,
        raw: str,
        label: str,
        before: Dict[str, Any],
        overlay: Optional[OverlayUploadStub] = None,
    ) -> Any:
        """Run the handler on a non-finite payload; pin no-state-change FIRST.

        Persist-site idiom (#587 sites 4-5 in
        tests/test_587_nonfinite_residual_paths.py): the no-state assertion
        comes FIRST — on base the NaN payload is persisted (200 + row), and
        that failure is the RED signal; with the fix the rejection precedes
        any write. Returns the caught HTTPExceptionStub (asserts not-None,
        i.e. the 400 actually happened, after the state pin).
        """
        rejection: Optional[HTTPExceptionStub] = None
        try:
            asyncio.run(self.handler(camera_id, raw, overlay, None))
        except HTTPExceptionStub as exc:
            rejection = exc
        self.assert_no_state_change(before, label)
        self.assertIsNotNone(
            rejection,
            f"{label}: non-finite payload must be rejected with 400, not persisted",
        )
        return rejection

    # -- rejection pins (RED on base: 200 + persisted bare NaN/Infinity) ----

    def test_nan_nested_in_payload_rejected_400_with_offending_path(self):
        # NaN nested in the worker payload (dict / list / top level) must be
        # rejected with 400 and an accurate offending path, before any write.
        cases = [
            ("nested-dict-NaN", {"telemetry": {"speed_kmh": float("nan")}}, "metadata.telemetry.speed_kmh"),
            ("nested-list-NaN", {"detections": [{"conf": 0.9}, {"conf": float("nan")}]}, "metadata.detections[1].conf"),
            ("top-level-NaN", {"quality": float("nan")}, "metadata.quality"),
        ]
        for label, payload, expected_path in cases:
            with self.subTest(label=label):
                raw = self.raw_json(payload)
                before = self.state_snapshot()
                rejection = self.rejection_with_no_state_change("cam1", raw, label, before)
                self.assertEqual(rejection.status_code, 400, f"{label}: detail={rejection.detail!r}")
                self.assertEqual(
                    rejection.detail,
                    f"{expected_path} must be a finite number",
                    f"{label}: offending path must point into the payload structure",
                )

    def test_infinity_nested_in_payload_rejected_400_with_offending_path(self):
        # ±Infinity anywhere in the payload (including the 1e999 / -1e999
        # overflow literals, parsed by json.loads to ±inf) → 400, no write.
        cases = [
            ("nested-inf", {"telemetry": {"nested": {"deep": float("inf")}}}, "metadata.telemetry.nested.deep", None),
            ("nested-list--inf", {"values": [1.5, float("-inf")]}, "metadata.values[1]", None),
            ("1e999-literal", {"speed": RAW_LITERAL_PLACEHOLDER}, "metadata.speed", "1e999"),
            ("-1e999-literal", {"speed": RAW_LITERAL_PLACEHOLDER}, "metadata.speed", "-1e999"),
        ]
        for case in cases:
            label, payload, expected_path = case[0], case[1], case[2]
            literal = case[3] if len(case) > 3 else None
            with self.subTest(label=label):
                raw = (
                    self.raw_json_with_literal(payload, literal)
                    if literal is not None
                    else self.raw_json(payload)
                )
                before = self.state_snapshot()
                rejection = self.rejection_with_no_state_change("cam1", raw, label, before)
                self.assertEqual(rejection.status_code, 400, f"{label}: detail={rejection.detail!r}")
                self.assertEqual(
                    rejection.detail,
                    f"{expected_path} must be a finite number",
                    f"{label}: offending path must point into the payload structure",
                )

    def test_rejection_causes_no_state_change(self):
        # The rejection must happen BEFORE the upsert: a seeded finite state
        # stays byte-identical after a rejected non-finite POST, and a fresh
        # camera gets NO row at all (no upsert happened).
        seed_payload = {"frame_no": 7, "sample_fps": 10.5, "message": "finite seed"}
        result = self.call_state("cam1", self.raw_json(seed_payload))
        self.assertTrue(result["ok"])
        seeded_json = self._stored_payload_json("cam1")
        self.assertIsNotNone(seeded_json, "seed must persist before the rejection pins")
        before = self.state_snapshot()
        for label, payload in (
            ("seeded-camera-NaN", {"motion_area": float("nan")}),
            ("fresh-camera-1e999", {"speed": RAW_LITERAL_PLACEHOLDER}),
        ):
            with self.subTest(label=label):
                camera_id = "cam1" if label.startswith("seeded") else "cam2"
                raw = (
                    self.raw_json_with_literal(payload, "1e999")
                    if RAW_LITERAL_PLACEHOLDER in json.dumps(payload)
                    else self.raw_json(payload)
                )
                rejection = self.rejection_with_no_state_change(camera_id, raw, label, before)
                self.assertEqual(rejection.status_code, 400, f"{label}: detail={rejection.detail!r}")
        # The seeded finite state is byte-identical after the rejections and
        # the fresh camera still has no row — no upsert ran for either.
        self.assertEqual(self._stored_payload_json("cam1"), seeded_json)
        self.assertIsNone(self._stored_payload_json("cam2"), "rejected input must not create a state row")

    def test_rejection_with_overlay_writes_nothing(self):
        # Early-scan pin: a rejected request CARRYING an overlay must not
        # touch the overlay media file — the handler writes the overlay
        # (tmp write + os.replace of {camera_id}_latest_overlay.jpg) AFTER
        # the early scan, so the 400 must land before it. On base (no
        # guard) the request succeeds: the sentinel overlay is overwritten
        # with the uploaded bytes and the NaN payload is persisted.
        sentinel = b"sentinel-jpeg-617"
        overlay_path = self.overlay_dir / "cam1_latest_overlay.jpg"
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        overlay_path.write_bytes(sentinel)
        before = self.state_snapshot()
        raw = self.raw_json({"motion_area": float("nan")})
        rejection = self.rejection_with_no_state_change(
            "cam1",
            raw,
            "overlay-carrier-NaN",
            before,
            overlay=OverlayUploadStub(b"uploaded-by-rejected-request"),
        )
        self.assertEqual(rejection.status_code, 400, f"detail={rejection.detail!r}")
        # The previous overlay file is byte-unchanged and no .tmp stray is
        # left behind (the handler's tmp path is cam1_latest_overlay.tmp).
        self.assertEqual(overlay_path.read_bytes(), sentinel, "rejected request overwrote the overlay media file")
        self.assertEqual(self._overlay_tree(), ["cam1_latest_overlay.jpg"], "stray .tmp or extra media file left behind")

    def test_final_scan_rejects_nan_overlay_rev_from_dirty_stored_row(self):
        # Final-scan-only pin: the early scan sees only the finite worker
        # payload; the NaN enters LATER via the no-overlay branch merging
        # overlay_rev from old_state (a pre-fix dirty row). The final scan
        # (right before the upsert) must reject before the persist. Seeded
        # through the REAL store.upsert_camera_state (real sqlite). On base
        # (no guards) the finite POST succeeds and re-persists the NaN.
        dirty = {
            "camera_id": "cam1",
            "frame_no": 9,
            "overlay_rev": float("nan"),
            "message": "pre-fix dirty row",
        }
        store.upsert_camera_state(self.state_db, "cam1", dirty)
        seeded_json = self._stored_payload_json("cam1")
        self.assertIsNotNone(seeded_json, "dirty seed row must persist")
        self.assertIn("NaN", seeded_json, "seed must carry a bare NaN token (pre-fix dirty row)")
        before = self.state_snapshot()
        # Finite worker payload WITHOUT overlay_rev: the merge copies the
        # dirty overlay_rev from the stored row.
        raw = self.raw_json({"frame_no": 10, "message": "finite post"})
        rejection = self.rejection_with_no_state_change("cam1", raw, "dirty-stored-overlay-rev", before)
        self.assertEqual(rejection.status_code, 400, f"detail={rejection.detail!r}")
        self.assertEqual(
            rejection.detail,
            "metadata.overlay_rev must be a finite number",
            "the offending path must name the merged overlay_rev, not a payload key",
        )
        # The dirty row is byte-unchanged: the finite POST did not upsert.
        self.assertEqual(self._stored_payload_json("cam1"), seeded_json)

    # -- finite-payload pin (behavior unchanged) ----------------------------

    def test_finite_payload_persists_exactly_as_before(self):
        # Finite payloads — floats (1.5, 10.5), ints, strings, null, bools,
        # nested lists/dicts, exact large ints — persist exactly as before
        # the guard: the merged state round-trips through
        # camera_state.payload_json as strict JSON.
        payload = {
            "frame_no": 42,
            "sample_fps": 10.5,
            "ratio": 1.5,
            "motion_area": 0,
            "message": "ok",
            "note": None,
            "tags": ["a", "b"],
            "nested": {"x": 1.5, "y": None, "z": [1, 2.5, "s", None, {"k": 3}]},
            "big_int": 10**30,
        }
        result = self.call_state("cam1", self.raw_json(payload))
        self.assertTrue(result["ok"])
        expected = dict(payload)
        expected["camera_id"] = "cam1"
        expected["analytics_profile"] = ANALYTICS_PROFILE_FIXTURE
        expected["domain"] = "water"
        expected["state_schema"] = WORKER_STATE_SCHEMA_FIXTURE
        expected["telemetry_schema"] = TELEMETRY_SCHEMA_FIXTURE
        expected["worker_source_commit"] = None
        expected["updated_at"] = STUB_NOW_ISO
        expected["worker_online"] = True
        expected["last_overlay_url"] = None
        expected["overlay_rev"] = 0
        self.assertEqual(result["state"], expected)
        stored_json = self._stored_payload_json("cam1")
        self.assertIsNotNone(stored_json)
        # Strict-JSON persist contract: no bare NaN/Infinity tokens.
        self.assertNotIn("NaN", stored_json)
        self.assertNotIn("Infinity", stored_json)
        self.assertEqual(json.loads(stored_json), expected)


if __name__ == "__main__":
    unittest.main()
