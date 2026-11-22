"""Issue #706 — unified speed-config loader and `.bak` backup.

Production under test (never imported as a package — ``import api.app.main``
creates /opt dirs and fails in this sandbox, see tests/test_sea_speed_rbac.py):

* ``_load_speed_config`` + the GET/POST speed-config handlers are
  AST-extracted from ``api/app/main.py`` (repo idiom: tests/
  test_numeric_input_validation.py, tests/test_sea_speed_rbac.py);
* ``store.write_json_file``/``read_json_file`` are the REAL fastapi-free
  primitives imported as ``from api.app import store`` (precedent:
  tests/test_617_analytics_state_nonfinite.py).

Test groups and their RED condition (base b774ecb — no production change):

* ``LoaderOracleTests`` — direct loader calls with hand-computed literal
  expectations (exact ``ValueError`` strings from spec FR-002/FR-006).
  RED: base main.py has no ``_load_speed_config`` → extraction fails with
  ``missing API functions: ['_load_speed_config']``.
* ``GetPostParityTests`` — the same invalid candidate through GET (stored
  record) and POST (request) yields the same loader verdict: the loader's
  ``ValueError`` message IS the POST 400 detail, while GET maps the same
  stored rejection to HTTP 500 ``speed-config storage is corrupted``; a
  valid POST reads back through GET as an identical document.
  RED: same missing-loader extraction failure; additionally base GET never
  validates stored factors (invalid disk content answered 200, not 500).
* ``BackupLifecycleTests`` — real temp files: first ``backup=True`` write
  creates no ``.bak``; second write publishes byte-equal-to-first ``.bak``;
  third write replaces the single slot byte-equal-to-second; default
  ``backup=False`` never creates ``.bak``; concurrent writers leave valid
  JSON and no ``*.tmp``.
  RED: base ``write_json_file`` has no ``backup`` parameter →
  ``TypeError: write_json_file() got an unexpected keyword argument``.
* ``BackupFailureMatrixTests`` — ``.bak`` as a directory aborts with the
  primary untouched; a simulated final ``os.replace`` failure leaves the
  primary old AND ``.bak`` byte-equal to the primary (the one documented
  non-atomic state, spec AC-005); a corrupt predecessor is backed up as raw
  bytes; ``.bak`` carries only the calibration document (no secret material).
  RED: same missing-``backup``-parameter TypeError.
* ``ScopeGuardTests`` — exactly one ``write_json_file`` call in the whole
  ``api/app`` tree passes ``backup=True`` and it is the speed-config POST;
  both speed-config handlers reference the shared loader; the speed-lines
  family keeps its own inline validation and carries no backup/loader.
  RED: base has zero ``backup=True`` call sites → the exact-one-site
  assertion fails.

No assertion here duplicates a spec document as an oracle: every expected
value is a literal written independently of the production source.
"""

from __future__ import annotations

import ast
import copy
import fcntl
import json
import os
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_SOURCE = ROOT / "api" / "app" / "main.py"
STORE_SOURCE = ROOT / "api" / "app" / "store.py"
API_APP_DIR = ROOT / "api" / "app"

from api.app import store  # repo-local; fastapi-free by contract (issue #617)


class HTTPExceptionStub(Exception):
    """Stand-in for fastapi.HTTPException in the exec'd handler bodies."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_api_functions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    """AST-extract the named top-level functions from main.py (decorators stripped)."""
    tree = ast.parse(API_SOURCE.read_text(encoding="utf-8-sig"), filename=str(API_SOURCE))
    selected: list[ast.stmt] = []
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names and node.name not in found:
            cloned = copy.deepcopy(node)
            cloned.decorator_list = []
            selected.append(cloned)
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(API_SOURCE), "exec"), namespace)
    return namespace


# ---------------------------------------------------------------------------
# 1. Loader oracle — literal expectations, computed by hand from FR-002/FR-006.
# ---------------------------------------------------------------------------


class LoaderOracleTests(unittest.TestCase):
    """``_load_speed_config`` in isolation: exact outputs, exact error strings."""

    def setUp(self) -> None:
        namespace: dict[str, Any] = {"Any": Any, "Dict": Dict, "Optional": Optional}
        load_api_functions({"_load_speed_config"}, namespace)
        self.loader = namespace["_load_speed_config"]

    def test_valid_record_projects_exact_response_shape(self) -> None:
        record = {
            "enabled": True,
            "kmh_per_px_s": 1.5,
            "updated_at": "2026-11-22T00:00:00+00:00",
        }
        self.assertEqual(
            self.loader("cam1", record),
            {
                "enabled": True,
                "kmh_per_px_s": 1.5,
                "updated_at": "2026-11-22T00:00:00+00:00",
                "ok": True,
                "camera_id": "cam1",
            },
        )
        # camera_id is the argument, not the record's own claim
        self.assertEqual(self.loader("road1", record)["camera_id"], "road1")

    def test_loader_is_side_effect_free_and_returns_a_new_record(self) -> None:
        record = {"enabled": True, "kmh_per_px_s": 2.0, "updated_at": "2026-11-22T00:00:00+00:00"}
        snapshot = dict(record)
        result = self.loader("cam1", record)
        self.assertIsNot(result, record)
        self.assertEqual(record, snapshot, "loader must not mutate its input")

    def test_non_dict_record_rejected_with_object_message(self) -> None:
        for record in ([], "x", None, 3, ("kmh_per_px_s", 1.0)):
            with self.subTest(record=record):
                with self.assertRaises(ValueError) as raised:
                    self.loader("cam1", record)  # type: ignore[arg-type]
                self.assertEqual(str(raised.exception), "speed-config record must be an object")

    def test_non_numeric_factor_rejected_with_number_message(self) -> None:
        for value in ("abc", None, [1.5], {"v": 1.5}, 10**400, object()):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as raised:
                    self.loader("cam1", {"kmh_per_px_s": value})
                self.assertEqual(str(raised.exception), "kmh_per_px_s must be a number")

    def test_non_finite_factor_rejected_with_finite_message(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf"), "nan", "inf", "1e999"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as raised:
                    self.loader("cam1", {"kmh_per_px_s": value})
                self.assertEqual(str(raised.exception), "kmh_per_px_s must be a finite number")

    def test_negative_factor_rejected_with_range_message(self) -> None:
        for value in (-1, -0.5, "-2", -1e-300):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as raised:
                    self.loader("cam1", {"kmh_per_px_s": value})
                self.assertEqual(str(raised.exception), "kmh_per_px_s must be >= 0")

    def test_enabled_true_with_zero_factor_normalises_to_disabled(self) -> None:
        # FR-004/FR-002: enabled is normalised against a positive factor.
        self.assertEqual(
            self.loader("cam1", {"enabled": True, "kmh_per_px_s": 0}),
            {"enabled": False, "kmh_per_px_s": 0.0, "ok": True, "camera_id": "cam1", "updated_at": None},
        )
        self.assertTrue(self.loader("cam1", {"enabled": True, "kmh_per_px_s": 0.5})["enabled"])
        # storage default: enabled absent → False regardless of factor
        self.assertFalse(self.loader("cam1", {"kmh_per_px_s": 0.5})["enabled"])

    def test_missing_updated_at_defaults_to_none(self) -> None:
        self.assertIsNone(self.loader("cam1", {"kmh_per_px_s": 1.0})["updated_at"])
        # storage defaults stay distinct from POST candidate defaults (FR-004)
        self.assertFalse(self.loader("cam1", {"kmh_per_px_s": 1.0})["enabled"])

    def test_compatible_extra_stored_keys_are_preserved(self) -> None:
        # FR-003: compatible extras survive the projection unchanged.
        record = {
            "enabled": True,
            "kmh_per_px_s": 2.0,
            "updated_at": "2026-11-22T00:00:00+00:00",
            "operator_note": "calibrated-706",
            "legacy_flag": True,
        }
        result = self.loader("cam1", record)
        self.assertEqual(result["operator_note"], "calibrated-706")
        self.assertIs(result["legacy_flag"], True)
        self.assertEqual(result["kmh_per_px_s"], 2.0)
        self.assertEqual(result["ok"], True)

    def test_numeric_strings_are_coerced_to_float(self) -> None:
        # float("1.25") is legal input — only non-numeric strings are rejected.
        self.assertEqual(self.loader("cam1", {"kmh_per_px_s": "1.25"})["kmh_per_px_s"], 1.25)
        self.assertEqual(self.loader("cam1", {"kmh_per_px_s": True})["kmh_per_px_s"], 1.0)


# ---------------------------------------------------------------------------
# 2. GET/POST parity — one loader verdict, two documented HTTP mappings.
# ---------------------------------------------------------------------------


class GetPostParityTests(unittest.TestCase):
    """The same invalid candidate: POST → 400 with the loader message, GET → 500."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "cam1_speed_config.json"
        self.writes: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []

        def recording_write(path: Any, data: Any, **kwargs: Any) -> None:
            self.writes.append((Path(path), data, kwargs))
            store.write_json_file(path, data, **kwargs)

        namespace: dict[str, Any] = {
            "Any": Any,
            "Dict": Dict,
            "Optional": Optional,
            "HTTPException": HTTPExceptionStub,
            "Header": lambda default=None: default,
            "require_role": lambda *args, **kwargs: None,
            "analytics_identity": lambda camera_id: None,
            "analytics_data_file": lambda camera_id, kind: self.path,
            "read_json_file": store.read_json_file,
            "write_json_file": recording_write,
            "now_iso": lambda: "2026-11-22T00:00:00+00:00",
            "store": store,
        }
        load_api_functions(
            {"_load_speed_config", "get_analytics_speed_config", "post_analytics_speed_config"},
            namespace,
        )
        self.get = namespace["get_analytics_speed_config"]
        self.post = namespace["post_analytics_speed_config"]
        self.loader = namespace["_load_speed_config"]

    # literal verdict table: value → exact loader message (spec FR-006)
    INVALID_CANDIDATES = (
        ("abc", "kmh_per_px_s must be a number"),
        (None, "kmh_per_px_s must be a number"),
        (float("nan"), "kmh_per_px_s must be a finite number"),
        (float("inf"), "kmh_per_px_s must be a finite number"),
        (-1.0, "kmh_per_px_s must be >= 0"),
    )

    def test_invalid_request_maps_loader_message_to_400_and_writes_nothing(self) -> None:
        for value, message in self.INVALID_CANDIDATES:
            with self.subTest(value=value):
                with self.assertRaises(HTTPExceptionStub) as raised:
                    self.post("cam1", {"enabled": True, "kmh_per_px_s": value})
                self.assertEqual(raised.exception.status_code, 400)
                self.assertEqual(raised.exception.detail, message)
                self.assertEqual(self.writes, [])
                self.assertFalse(self.path.exists(), "invalid request must never reach disk")

    def test_invalid_stored_record_maps_to_500_with_same_loader_verdict(self) -> None:
        for value, message in self.INVALID_CANDIDATES:
            with self.subTest(value=value):
                self.path.write_text(
                    json.dumps({"enabled": True, "kmh_per_px_s": value}), encoding="utf-8"
                )
                # the verdict itself is the loader's message …
                with self.assertRaises(ValueError) as direct:
                    self.loader("cam1", {"enabled": True, "kmh_per_px_s": value})
                self.assertEqual(str(direct.exception), message)
                # … POST exposes it as 400 with that exact detail …
                with self.assertRaises(HTTPExceptionStub) as post_raised:
                    self.post("cam1", {"enabled": True, "kmh_per_px_s": value})
                self.assertEqual(post_raised.exception.status_code, 400)
                self.assertEqual(post_raised.exception.detail, message)
                # … and GET maps the same rejection to the storage 500.
                with self.assertRaises(HTTPExceptionStub) as get_raised:
                    self.get("cam1")
                self.assertEqual(get_raised.exception.status_code, 500)
                self.assertEqual(get_raised.exception.detail, "speed-config storage is corrupted")

    def test_corrupt_json_on_disk_maps_to_500_not_a_document(self) -> None:
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(HTTPExceptionStub) as raised:
            self.get("cam1")
        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(raised.exception.detail, "speed-config storage is corrupted")

    def test_missing_file_returns_storage_defaults_through_loader(self) -> None:
        self.assertEqual(
            self.get("cam1"),
            {"ok": True, "camera_id": "cam1", "enabled": False, "kmh_per_px_s": 0.0, "updated_at": None},
        )

    def test_valid_post_persists_loader_output_and_get_reads_it_back_identically(self) -> None:
        posted = self.post("cam1", {"enabled": True, "kmh_per_px_s": 1.5})
        self.assertEqual(
            posted,
            {
                "enabled": True,
                "kmh_per_px_s": 1.5,
                "updated_at": "2026-11-22T00:00:00+00:00",
                "ok": True,
                "camera_id": "cam1",
            },
        )
        # the handler opts into the single-slot backup (FR-007/FR-008)
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.writes[0][0], self.path)
        self.assertEqual(self.writes[0][2], {"backup": True})
        self.assertEqual(store.read_json_file(self.path, None), posted)
        # what the operator reads back is exactly what the writer produced
        self.assertEqual(self.get("cam1"), posted)

    def test_valid_post_without_factor_defaults_to_disabled_zero(self) -> None:
        posted = self.post("cam1", {})
        self.assertEqual(posted["kmh_per_px_s"], 0.0)
        self.assertIs(posted["enabled"], False)
        self.assertEqual(self.get("cam1"), posted)


# ---------------------------------------------------------------------------
# 3. Backup lifecycle — real store, real temp files, byte-exact assertions.
# ---------------------------------------------------------------------------


class BackupLifecycleTests(unittest.TestCase):
    """FR-008/FR-010: first write has no predecessor, later writes fill one slot."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.path = self.dir / "speed_config.json"
        self.bak = self.dir / "speed_config.json.bak"

    def tmp_leftovers(self) -> list[str]:
        return sorted(p.name for p in self.dir.iterdir() if p.name.endswith(".tmp"))

    def test_first_backup_write_creates_no_bak(self) -> None:
        store.write_json_file(self.path, {"kmh_per_px_s": 1.0}, backup=True)
        self.assertTrue(self.path.is_file())
        self.assertFalse(self.bak.exists(), "a genuinely absent predecessor creates no .bak")
        self.assertEqual(self.tmp_leftovers(), [])

    def test_second_write_publishes_exact_first_bytes_then_third_replaces_slot(self) -> None:
        store.write_json_file(self.path, {"kmh_per_px_s": 1.0}, backup=True)
        first_bytes = self.path.read_bytes()
        store.write_json_file(self.path, {"kmh_per_px_s": 2.0}, backup=True)
        self.assertTrue(self.bak.is_file())
        self.assertEqual(self.bak.read_bytes(), first_bytes, ".bak must be byte-equal to the first document")
        second_bytes = self.path.read_bytes()
        self.assertEqual(json.loads(second_bytes), {"kmh_per_px_s": 2.0})
        store.write_json_file(self.path, {"kmh_per_px_s": 3.0}, backup=True)
        self.assertEqual(self.bak.read_bytes(), second_bytes, ".bak must be byte-equal to the second document")
        self.assertEqual(json.loads(self.path.read_bytes()), {"kmh_per_px_s": 3.0})
        # one slot only — no multi-generation history (FR-010)
        bak_files = sorted(p.name for p in self.dir.iterdir() if ".bak" in p.name)
        self.assertEqual(bak_files, ["speed_config.json.bak"])
        self.assertEqual(self.tmp_leftovers(), [])

    def test_default_backup_flag_never_creates_bak(self) -> None:
        store.write_json_file(self.path, {"kmh_per_px_s": 1.0})
        store.write_json_file(self.path, {"kmh_per_px_s": 2.0})
        store.write_json_file(self.path, {"kmh_per_px_s": 3.0})
        self.assertTrue(self.path.is_file())
        self.assertFalse(self.bak.exists(), "backup is opt-in; the default must never create .bak")
        self.assertEqual(self.tmp_leftovers(), [])

    def test_backup_is_keyword_only_with_false_default(self) -> None:
        signature = __import__("inspect").signature(store.write_json_file)
        parameter = signature.parameters["backup"]
        self.assertEqual(parameter.kind, __import__("inspect").Parameter.KEYWORD_ONLY)
        self.assertIs(parameter.default, False)

    def test_concurrent_backup_writers_leave_valid_json_and_no_tmp(self) -> None:
        errors: list[BaseException] = []

        def writer(index: int) -> None:
            try:
                for round_no in range(10):
                    store.write_json_file(
                        self.path, {"writer": index, "round": round_no, "kmh_per_px_s": float(round_no)},
                        backup=True,
                    )
            except BaseException as error:  # pragma: no cover - failure path
                errors.append(error)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        payload = store.read_json_file(self.path, None)
        self.assertIsInstance(payload, dict)
        self.assertIn("writer", payload)
        self.assertEqual(self.tmp_leftovers(), [], "no staging .tmp may survive concurrent writers")
        self.assertTrue(self.bak.is_file(), "two+ writes must leave exactly one backup slot")
        backup_payload = json.loads(self.bak.read_bytes())
        self.assertIsInstance(backup_payload, dict)
        bak_files = sorted(p.name for p in self.dir.iterdir() if ".bak" in p.name)
        self.assertEqual(bak_files, ["speed_config.json.bak"])


# ---------------------------------------------------------------------------
# 4. Backup failure matrix — spec §`.bak` transaction failure matrix.
# ---------------------------------------------------------------------------


class _PrimaryReplaceFailer:
    """Test-owned ``os`` stand-in used via the extracted function's namespace.

    Only the final ``os.replace`` whose destination is the primary file
    fails; every other replace (notably the ``.bak`` publish inside the real
    ``store.atomic_write_bytes``) delegates to the genuine ``os.replace``.
    Because this object is injected through the exec namespace below, the
    real ``os`` module is never mutated (peer review F2).
    """

    def __init__(self, primary: Path) -> None:
        self._primary = primary

    def replace(self, src: Any, dst: Any, *args: Any, **kwargs: Any) -> None:
        if Path(dst) == self._primary:
            raise OSError("simulated final replace failure")
        return os.replace(src, dst, *args, **kwargs)


def _extract_write_json_file(os_proxy: Any) -> Any:
    """Re-exec store.write_json_file against a test-owned ``os`` alias.

    The body is AST-extracted verbatim from store.py (repo idiom), so the
    assertions still exercise the real production code — only the module
    global ``os`` it closes over is swapped for ``os_proxy``.
    """
    tree = ast.parse(STORE_SOURCE.read_text(encoding="utf-8-sig"), filename=str(STORE_SOURCE))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "write_json_file"
    )
    cloned = copy.deepcopy(function)
    cloned.decorator_list = []
    module = ast.Module(body=[cloned], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Path": Path,
        "fcntl": fcntl,
        "json": json,
        "os": os_proxy,
        "uuid": uuid,
        "atomic_write_bytes": store.atomic_write_bytes,
    }
    exec(compile(module, str(STORE_SOURCE), "exec"), namespace)
    return namespace["write_json_file"]


class BackupFailureMatrixTests(unittest.TestCase):
    """FR-009/AC-005: only an absent predecessor is ignored; the rest abort."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.path = self.dir / "speed_config.json"
        self.bak = self.dir / "speed_config.json.bak"

    def tmp_leftovers(self) -> list[str]:
        return sorted(p.name for p in self.dir.iterdir() if p.name.endswith(".tmp"))

    def test_bak_as_directory_aborts_with_primary_untouched(self) -> None:
        store.write_json_file(self.path, {"kmh_per_px_s": 1.0}, backup=True)
        primary_before = self.path.read_bytes()
        self.bak.mkdir()  # backup publish target is a directory
        with self.assertRaises(OSError):
            store.write_json_file(self.path, {"kmh_per_px_s": 2.0}, backup=True)
        self.assertEqual(self.path.read_bytes(), primary_before, "failed backup must abort publication")
        self.assertTrue(self.bak.is_dir(), "the blocking directory must not be replaced")
        self.assertEqual(self.tmp_leftovers(), [], "staging tmp must be cleaned on abort")

    def test_final_replace_failure_leaves_primary_old_and_bak_equal_to_primary(self) -> None:
        store.write_json_file(self.path, {"kmh_per_px_s": 1.0}, backup=True)
        store.write_json_file(self.path, {"kmh_per_px_s": 2.0}, backup=True)
        primary_before = self.path.read_bytes()
        # Fault injection stays inside this test: the real function body is
        # re-executed against a test-owned os proxy, so the process-global
        # ``os`` module (which ``store.os`` IS) is never patched and parallel
        # tests cannot observe the failure (peer review F2). The .bak publish
        # still goes through the real store.atomic_write_bytes/real os.
        injected_write = _extract_write_json_file(_PrimaryReplaceFailer(self.path))
        with self.assertRaises(OSError):
            injected_write(self.path, {"kmh_per_px_s": 3.0}, backup=True)
        self.assertEqual(self.path.read_bytes(), primary_before, "primary keeps its prior content")
        self.assertEqual(
            self.bak.read_bytes(),
            self.path.read_bytes(),
            "documented inconsistent state: primary old and .bak equal to the primary",
        )
        self.assertEqual(self.tmp_leftovers(), [])

    def test_corrupt_predecessor_is_backed_up_as_raw_bytes(self) -> None:
        corrupt = b'{"kmh_per_px_s": not-a-number'
        self.path.write_bytes(corrupt)
        store.write_json_file(self.path, {"kmh_per_px_s": 5.0}, backup=True)
        self.assertEqual(self.bak.read_bytes(), corrupt, "backup publishes exact old bytes, never re-serialised")
        self.assertEqual(json.loads(self.path.read_bytes()), {"kmh_per_px_s": 5.0})
        self.assertEqual(self.tmp_leftovers(), [])

    def test_bak_carries_only_the_calibration_document(self) -> None:
        # No secret material: .bak is byte-identical to the predecessor and
        # the predecessor contains exactly the calibration keys written here.
        predecessor = {"enabled": True, "kmh_per_px_s": 1.25, "updated_at": "2026-11-22T00:00:00+00:00"}
        store.write_json_file(self.path, predecessor, backup=True)
        predecessor_bytes = self.path.read_bytes()
        store.write_json_file(self.path, {"enabled": True, "kmh_per_px_s": 2.5, "updated_at": "2026-11-22T00:00:00+00:00"}, backup=True)
        self.assertEqual(self.bak.read_bytes(), predecessor_bytes)
        backup_document = json.loads(self.bak.read_bytes())
        self.assertEqual(set(backup_document), {"enabled", "kmh_per_px_s", "updated_at"})
        forbidden_key_fragments = (
            "password", "secret", "token", "credential", "apikey", "api_key", "authorization",
        )
        for key in backup_document:
            for fragment in forbidden_key_fragments:
                self.assertNotIn(fragment, key.lower(), f"credential-shaped key {key!r} leaked into .bak")


# ---------------------------------------------------------------------------
# 5. Scope guard — speed_config only; speed_lines and every other writer untouched.
# ---------------------------------------------------------------------------


def _write_json_file_calls(function: ast.FunctionDef) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "write_json_file"
        ):
            calls.append(node)
    return calls


class ScopeGuardTests(unittest.TestCase):
    """FR-007/FR-011: exactly one opted-in writer, the speed-lines family unchanged."""

    def test_exactly_one_write_json_file_call_site_passes_backup_true(self) -> None:
        sites: list[tuple[str, str]] = []
        for source in sorted(API_APP_DIR.glob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
            for function in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
                for call in _write_json_file_calls(function):
                    keywords = {kw.arg: kw.value for kw in call.keywords}
                    if "backup" in keywords:
                        value = keywords["backup"]
                        self.assertIsInstance(value, ast.Constant, f"{source.name}:{function.name} backup must be a literal")
                        self.assertIs(value.value, True, f"{source.name}:{function.name} may only pass backup=True")
                        sites.append((source.name, function.name))
        self.assertEqual(
            sites,
            [("main.py", "post_analytics_speed_config")],
            "issue #706 admits exactly one backup=True call site: the speed-config POST",
        )

    def test_both_speed_config_handlers_call_the_shared_loader(self) -> None:
        tree = ast.parse(API_SOURCE.read_text(encoding="utf-8-sig"), filename=str(API_SOURCE))
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for handler in ("get_analytics_speed_config", "post_analytics_speed_config"):
            self.assertIn(handler, functions)
            referenced = {
                node.id for node in ast.walk(functions[handler]) if isinstance(node, ast.Name)
            }
            self.assertIn("_load_speed_config", referenced, f"{handler} must use the single loader (FR-001)")

    def test_speed_lines_family_is_untouched(self) -> None:
        tree = ast.parse(API_SOURCE.read_text(encoding="utf-8-sig"), filename=str(API_SOURCE))
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        speed_lines = sorted(name for name in functions if "speed_lines" in name)
        self.assertEqual(
            speed_lines,
            [
                "get_analytics_speed_lines",
                "get_cam1_speed_lines",
                "post_analytics_speed_lines",
                "post_cam1_speed_lines",
            ],
        )
        for name in speed_lines:
            referenced = {
                node.id for node in ast.walk(functions[name]) if isinstance(node, ast.Name)
            }
            self.assertNotIn("_load_speed_config", referenced, f"{name} belongs to the out-of-scope family")
            for call in _write_json_file_calls(functions[name]):
                self.assertNotIn(
                    "backup",
                    {kw.arg for kw in call.keywords},
                    f"{name} must keep the default backup=False",
                )
        # the speed-lines POST still owns its inline validation (no migration)
        post_source = ast.get_source_segment(
            API_SOURCE.read_text(encoding="utf-8-sig"), functions["post_analytics_speed_lines"]
        )
        assert post_source is not None
        for literal in (
            "distance_m must be a number",
            "distance_m must be a finite number",
            "distance_m must be > 0",
        ):
            self.assertIn(literal, post_source, "speed-lines keeps its own validator strings")


if __name__ == "__main__":
    unittest.main()
