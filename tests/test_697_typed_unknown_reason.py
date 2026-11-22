"""Issue #697: every unknown vessel speed status carries a typed reason.

The production side (``api/app/unknown_reason.py`` + the worker/API/transport
wiring) landed with the code worker; these tests pin the OUTCOMES, never the
mechanism beyond what an observable requires.

Sections (one class each):

* ``TypedUnknownReasonEnumOracleTests`` — the closed vocabulary is asserted
  from LITERALS written here first, so the module cannot redefine the truth
  and pass its own oracle.
* ``WorkerUnknownReasonPathTests`` — drives the real estimator/engine with
  deterministic timestamps: initial default, disabled/unusable gate,
  finalize branches, measured/measuring (no reason) and the selection
  contract (a discarded candidate never overwrites the selected result).
* ``ApiBoundaryUnknownReasonTests`` — the AST/exec harness the repo already
  uses for ``water_passages`` (real function source, ``HTTPExceptionStub``
  carrying the real status code): boundary 400s, legacy read, known-status
  drop, rank-merge.
* ``PostPassageLogLineTests`` — the success log line, byte-exact.
* ``UnknownReasonPackagingTests`` — count 11, all three inventories, the
  deploy.sh mirror sites and the boot ordering.
* ``UnknownReasonScopeGuardTests`` — the working tree touches only the
  admitted #697 surface (modelled on tests/test_687 ScopeGuardTests).

RED spot-check (what fails on base 83e8851, before the production change;
measured by running this file against a ``git archive`` of base):

* Enum oracle — ``api.app.unknown_reason`` does not exist, so every test that
  reads the module raises ModuleNotFoundError at ``_vocab()``; the
  release-relative subprocess probe fails (the base worker cannot import the
  vocabulary at all); the reserved-frame source guard is a keeps.
* Worker paths — the estimator/engine meta carries no ``unknown_reason``:
  ``meta.get("unknown_reason")`` is None, the literal-dict equality and the
  ``water_passage.TOO_FEW_OBSERVATIONS`` attribute access fail; the
  measured/measuring/incomplete "no reason" assertions are keeps (green on
  base) and exist to stop a future over-broad reason from leaking.
* API boundary — the harness cannot even be built on base (its namespace
  imports the vocabulary module), so all six tests fail at setup; a direct
  probe of the base source shows the behaviour gap independently:
  ``_validate_passage_payload`` ACCEPTS ``unknown_reason="bogus_reason"``
  (no 400) and ``passage_row_to_dict`` reads a legacy unknown row back as
  ``{'samples_used': 1}`` (no ``legacy_unspecified``).
* Log line — base prints no token, so the byte-exact line equality fails.
* Packaging — base mirror count is 10 and the inventories lack the module, so
  the count and membership assertions fail.
* Scope guard — keeps (passes on a clean tree, fails if an out-of-scope path
  appears in the working tree).
"""

from __future__ import annotations

import ast
import copy
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Guarded-optional (tests/test_worker_transport_module.py idiom): CI installs
# only pyyaml, and worker_transport pulls worker_media -> numpy transitively.
# The stubs keep the module importable there; where the real packages exist
# (this environment) they are used untouched.
try:
    import numpy  # noqa: F401  # guarded-optional probe (CI has no numpy)
except ModuleNotFoundError:
    sys.modules["numpy"] = mock.MagicMock()
try:
    import requests  # noqa: F401  # guarded-optional probe (CI has no requests)
except ModuleNotFoundError:
    sys.modules["requests"] = mock.MagicMock()

if str(ROOT / "worker") not in sys.path:
    sys.path.insert(0, str(ROOT / "worker"))

import water_passage as water_passage_module  # noqa: E402  (repo-local worker/)
import worker_transport  # noqa: E402  (repo-local worker/)
from water_passage import (  # noqa: E402
    Observation,
    TwoGateSpeedEstimator,
    WaterPassageEngine,
)
from scripts.quality.build_exact_artifacts import COMPONENT_FILES  # noqa: E402
from scripts.quality.validate_exact_artifacts import (  # noqa: E402
    REQUIRED_BY_COMPONENT,
    deploy_app_module_targets,
)

# ---------------------------------------------------------------------------
# Literals: the oracle. Written from the issue text FIRST — never derived from
# the module under test.
# ---------------------------------------------------------------------------

# Emitted/applied by #697 (worker emissions + the API's legacy read-path fill).
EMITTED_REASONS = ("too_few_observations", "gate_unavailable", "legacy_unspecified")
# Reserved for #700 frame-quality explanations: part of the closed set, never
# emitted by #697.
RESERVED_REASONS = ("black_frame", "slate_frame", "frozen_frame")
CLOSED_REASONS = EMITTED_REASONS + RESERVED_REASONS

GATE_LINES = ([(0, 20), (100, 20)], [(0, 80), (100, 80)], 60.0)


def _vocab():
    """The #697 vocabulary module.

    Resolved at call time (repo precedent: tests/test_water_passage.py
    imports ``Observation`` inside ``_obs``) so a missing module fails the
    enum/API classes individually instead of erroring the whole file at
    collection time — the failure stays attributable to the section that
    needs the vocabulary.
    """
    from api.app import unknown_reason

    return unknown_reason


def _obs(ts: float, y: float) -> Observation:
    return Observation(ts, 1, 50.0, y, (40.0, y - 10, 60.0, y), 0.8)


def _det(track_id: int, y: float, *, kmh: Optional[float] = None) -> Dict[str, object]:
    detection: Dict[str, object] = {
        "track_id": track_id,
        "class_name": "vessel",
        "bbox_xyxy": [40, y - 10, 60, y],
        "confidence": 0.8,
    }
    if kmh is not None:
        detection["_line_speed_info"] = {"speed_sample_fresh": True, "speed_instant_kmh": kmh}
    return detection


def _gate(enabled: bool = True) -> TwoGateSpeedEstimator:
    return TwoGateSpeedEstimator(*GATE_LINES, enabled)


# ---------------------------------------------------------------------------
# 1. Enum oracle — literal expectations, both directions of the split.
# ---------------------------------------------------------------------------


class TypedUnknownReasonEnumOracleTests(unittest.TestCase):
    def test_module_constants_match_the_written_literals(self) -> None:
        vocab = _vocab()
        self.assertEqual(vocab.TOO_FEW_OBSERVATIONS, "too_few_observations")
        self.assertEqual(vocab.GATE_UNAVAILABLE, "gate_unavailable")
        self.assertEqual(vocab.LEGACY_UNSPECIFIED, "legacy_unspecified")
        self.assertEqual(vocab.BLACK_FRAME, "black_frame")
        self.assertEqual(vocab.SLATE_FRAME, "slate_frame")
        self.assertEqual(vocab.FROZEN_FRAME, "frozen_frame")

    def test_closed_set_is_exactly_the_written_literal_tuple(self) -> None:
        vocab = _vocab()
        self.assertEqual(vocab.UNKNOWN_REASONS, CLOSED_REASONS)
        self.assertEqual(vocab.UNKNOWN_REASON_SET, frozenset(CLOSED_REASONS))

    def test_emitted_and_reserved_split_is_exactly_the_written_literals(self) -> None:
        vocab = _vocab()
        self.assertEqual(vocab.EMITTED_UNKNOWN_REASONS, frozenset(EMITTED_REASONS))
        self.assertEqual(vocab.RESERVED_UNKNOWN_REASONS, frozenset(RESERVED_REASONS))
        # The split is a partition of the closed set: no overlap, no leak.
        self.assertEqual(
            vocab.EMITTED_UNKNOWN_REASONS | vocab.RESERVED_UNKNOWN_REASONS,
            frozenset(CLOSED_REASONS),
        )
        self.assertEqual(
            vocab.EMITTED_UNKNOWN_REASONS & vocab.RESERVED_UNKNOWN_REASONS, frozenset()
        )

    def test_reserved_frame_reasons_are_not_emitted_by_697(self) -> None:
        # The worker only ever imports the two emitted values; #700 owns the
        # frame-quality trio.
        worker_source = (ROOT / "worker" / "water_passage.py").read_text(encoding="utf-8")
        for reserved in RESERVED_REASONS:
            self.assertNotIn(f'"{reserved}"', worker_source)
        transport_source = (ROOT / "worker" / "worker_transport.py").read_text(encoding="utf-8")
        for reserved in RESERVED_REASONS:
            self.assertNotIn(f'"{reserved}"', transport_source)

    def test_is_unknown_reason_accepts_every_closed_member(self) -> None:
        vocab = _vocab()
        for reason in CLOSED_REASONS:
            with self.subTest(reason=reason):
                self.assertTrue(vocab.is_unknown_reason(reason))

    def test_is_unknown_reason_rejects_non_strings(self) -> None:
        vocab = _vocab()
        rejects: List[Any] = [
            None,
            123,
            0,
            True,
            b"gate_unavailable",
            ["gate_unavailable"],
            {"unknown_reason": "gate_unavailable"},
            1.5,
        ]
        for value in rejects:
            with self.subTest(value=repr(value)):
                self.assertFalse(vocab.is_unknown_reason(value))

    def test_is_unknown_reason_rejects_unknown_or_mangled_strings(self) -> None:
        vocab = _vocab()
        rejects = [
            "",
            "made_up_reason",
            "TOO_FEW_OBSERVATIONS",  # wrong case
            "Too_Few_Observations",
            "gate-unavailable",  # wrong separator
            " gate_unavailable",  # leading whitespace
            "gate_unavailable ",  # trailing whitespace
            "legacy_unspecified.",
            "unknown",
        ]
        for value in rejects:
            with self.subTest(value=value):
                self.assertFalse(vocab.is_unknown_reason(value))

    def test_worker_imports_the_shared_vocabulary_release_relative(self) -> None:
        # The worker resolves api/app from ITS OWN file location, not from
        # cwd: run the import from an unrelated working directory.
        probe = (
            "import sys\n"
            f"sys.path.insert(0, {str(ROOT / 'worker')!r})\n"
            "import water_passage\n"
            "import unknown_reason\n"
            "print(unknown_reason.__file__)\n"
            "print(water_passage.TOO_FEW_OBSERVATIONS)\n"
            "print(water_passage.GATE_UNAVAILABLE)\n"
        )
        with tempfile.TemporaryDirectory(prefix="sea-speed-697-cwd-") as temp_dir:
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                env={**os.environ},
                timeout=120,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(Path(lines[0]).resolve(), (ROOT / "api" / "app" / "unknown_reason.py").resolve())
        self.assertEqual(lines[1], "too_few_observations")
        self.assertEqual(lines[2], "gate_unavailable")


# ---------------------------------------------------------------------------
# 2. Worker paths — real estimator/engine, deterministic timestamps.
# ---------------------------------------------------------------------------


class WorkerUnknownReasonPathTests(unittest.TestCase):
    def test_fresh_estimator_defaults_to_too_few_observations(self) -> None:
        estimator = _gate()
        self.assertEqual(estimator.result.speed_status, "unknown")
        self.assertEqual(
            estimator.result.measurement_meta,
            {"unknown_reason": "too_few_observations"},
        )

    def test_disabled_gate_update_emits_gate_unavailable(self) -> None:
        estimator = _gate(enabled=False)
        result = estimator.update(_obs(0.0, 10))
        self.assertEqual(result.speed_status, "unknown")
        self.assertEqual(result.speed_method, "two_gate")
        self.assertEqual(
            result.measurement_meta,
            {"unknown_reason": "gate_unavailable", "enabled": False, "samples_used": 1},
        )

    def test_unusable_gate_configuration_is_gate_unavailable(self) -> None:
        # enabled=True is requested, but a missing line or a non-positive
        # distance makes the gate unusable — a configuration gap.
        unusable = (
            TwoGateSpeedEstimator(None, [(0, 80), (100, 80)], 60.0, True),
            TwoGateSpeedEstimator([(0, 20), (100, 20)], None, 60.0, True),
            TwoGateSpeedEstimator([(0, 20), (100, 20)], [(0, 80), (100, 80)], 0.0, True),
        )
        for estimator in unusable:
            with self.subTest(lines=estimator.line_a, distance=estimator.distance_m):
                self.assertFalse(estimator.enabled)
                result = estimator.update(_obs(0.0, 10))
                self.assertEqual(result.speed_status, "unknown")
                self.assertEqual(
                    result.measurement_meta.get("unknown_reason"), "gate_unavailable"
                )

    def test_disabled_gate_finalize_emits_gate_unavailable_not_too_few(self) -> None:
        # Samples exist but the gate is off: the reason is the configuration
        # gap, not a lack of observations.
        estimator = _gate(enabled=False)
        estimator.update(_obs(0.0, 10))
        estimator.update(_obs(1.0, 30))
        result = estimator.finalize()
        self.assertEqual(result.speed_status, "unknown")
        self.assertEqual(result.measurement_meta.get("unknown_reason"), "gate_unavailable")
        self.assertEqual(result.measurement_meta.get("samples_used"), 2)

    def test_enabled_gate_with_zero_samples_finalizes_to_too_few_observations(self) -> None:
        result = _gate().finalize()
        self.assertEqual(result.speed_status, "unknown")
        self.assertEqual(
            result.measurement_meta,
            {"unknown_reason": "too_few_observations", "distance_m": 60.0, "samples_used": 0},
        )

    def test_enabled_gate_with_observations_but_no_gate_finalize_is_incomplete(self) -> None:
        estimator = _gate()
        estimator.update(_obs(0.0, 10))
        estimator.update(_obs(1.0, 30))
        result = estimator.finalize()
        self.assertEqual(result.speed_status, "incomplete")
        self.assertNotIn("unknown_reason", result.measurement_meta)

    def test_engine_passage_carries_gate_unavailable_for_disabled_gate(self) -> None:
        engine = WaterPassageEngine(
            lambda: _gate(enabled=False), id_factory=lambda _ts: "P-697-DISABLED"
        )
        passage = engine.update([_det(1, 10)], 1.0)[-1]["passage"]
        self.assertEqual(passage["speed_status"], "unknown")
        self.assertEqual(passage["speed_method"], "two_gate")
        self.assertEqual(passage["measurement_meta"].get("unknown_reason"), "gate_unavailable")

    def test_engine_finalized_passage_carries_no_reason_when_incomplete(self) -> None:
        engine = WaterPassageEngine(lambda: _gate(), id_factory=lambda _ts: "P-697-INCOMPLETE")
        engine.update([_det(1, 10)], 0.0)
        engine.update([_det(1, 30)], 1.0)
        passage = engine.finalize_all(2.0)[0]["passage"]
        self.assertEqual(passage["speed_status"], "incomplete")
        self.assertIsNone(passage["speed_kmh"])
        self.assertNotIn("unknown_reason", passage["measurement_meta"])

    def test_measuring_and_measured_results_carry_no_reason(self) -> None:
        measuring = _gate().update(_obs(0.0, 10))
        self.assertEqual(measuring.speed_status, "measuring")
        self.assertNotIn("unknown_reason", measuring.measurement_meta)

        measured = _gate()
        for ts, y in ((0.0, 10), (1.0, 30), (2.0, 70), (3.0, 90)):
            result = measured.update(_obs(ts, y))
        self.assertEqual(result.speed_status, "measured")
        self.assertNotIn("unknown_reason", result.measurement_meta)

        engine = WaterPassageEngine(lambda: _gate(), id_factory=lambda _ts: "P-697-MEASURED")
        engine.update([_det(1, 10)], 0.0)
        engine.update([_det(1, 30)], 1.0)
        engine.update([_det(1, 70)], 2.0)
        passage = engine.update([_det(1, 90)], 3.0)[-1]["passage"]
        self.assertEqual(passage["speed_status"], "measured")
        self.assertNotIn("unknown_reason", passage["measurement_meta"])

    def test_selected_gate_reason_survives_a_discarded_calibrated_candidate(self) -> None:
        # The calibrated candidate is in "measuring" (discarded by
        # _select_measurement): the selected gate result keeps ITS reason.
        engine = WaterPassageEngine(
            lambda: _gate(enabled=False),
            id_factory=lambda _ts: "P-697-SELECT",
            calibrated_min_samples=3,
        )
        passage = engine.update([_det(1, 10, kmh=12.0)], 0.0)[-1]["passage"]
        self.assertEqual(passage["speed_method"], "two_gate")
        self.assertEqual(passage["speed_status"], "unknown")
        self.assertEqual(
            passage["measurement_meta"].get("unknown_reason"), "gate_unavailable"
        )

    def test_promoted_result_does_not_inherit_the_discarded_unknown_reason(self) -> None:
        engine = WaterPassageEngine(
            lambda: _gate(enabled=False),
            id_factory=lambda _ts: "P-697-PROMOTE",
            calibrated_min_samples=3,
        )
        first = engine.update([_det(1, 10, kmh=12.0)], 0.0)[-1]["passage"]
        self.assertEqual(first["speed_status"], "unknown")
        self.assertEqual(first["measurement_meta"].get("unknown_reason"), "gate_unavailable")
        # Two samples: the calibrated candidate is still "measuring" and is
        # discarded, so the gate reason must survive unchanged.
        second = engine.update([_det(1, 12, kmh=12.0)], 1.0)[-1]["passage"]
        self.assertEqual(second["speed_status"], "unknown")
        self.assertEqual(second["measurement_meta"].get("unknown_reason"), "gate_unavailable")
        # Third sample promotes the row to measured: the promoted result must
        # NOT carry the discarded gate candidate's reason.
        third = engine.update([_det(1, 14, kmh=12.0)], 2.0)[-1]["passage"]
        self.assertEqual(third["speed_status"], "measured")
        self.assertEqual(third["speed_method"], "detection_first_calibrated")
        self.assertEqual(third["speed_kmh"], 12.0)
        self.assertNotIn("unknown_reason", third["measurement_meta"])
        # Finalize keeps the promoted measurement reason-free.
        finalized = engine.finalize_all(3.0)[0]["passage"]
        self.assertEqual(finalized["speed_status"], "measured")
        self.assertNotIn("unknown_reason", finalized["measurement_meta"])

    def test_worker_module_exposes_the_shared_reason_values(self) -> None:
        # The worker binds the vocabulary names from the shared module.
        self.assertEqual(water_passage_module.TOO_FEW_OBSERVATIONS, "too_few_observations")
        self.assertEqual(water_passage_module.GATE_UNAVAILABLE, "gate_unavailable")


# ---------------------------------------------------------------------------
# 3. API boundary — real water_passages source through the AST/exec harness.
# ---------------------------------------------------------------------------

HTTP_SOURCE = ROOT / "api" / "app" / "main.py"
OBJECTS_REGISTRY_SOURCE = ROOT / "api" / "app" / "objects_registry.py"
PASSAGE_MIRRORS_SOURCE = ROOT / "api" / "app" / "passage_mirrors.py"
WATER_PASSAGES_SOURCE = ROOT / "api" / "app" / "water_passages.py"


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_api_functions(names: set, namespace: Dict[str, Any]) -> Dict[str, Any]:
    selected = []
    found = set()
    for source in (HTTP_SOURCE, OBJECTS_REGISTRY_SOURCE, PASSAGE_MIRRORS_SOURCE, WATER_PASSAGES_SOURCE):
        if not source.exists():
            continue
        tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names and node.name not in found:
                cloned = copy.deepcopy(node)
                cloned.decorator_list = copy.deepcopy(node.decorator_list) if node.name in {"open_passages_db"} else []
                selected.append(cloned)
                found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(WATER_PASSAGES_SOURCE), "exec"), namespace)
    return namespace


API_FUNCTIONS = {
    "optional_float",
    "optional_int",
    "open_passages_db",
    "cleanup_passage_media",
    "prune_water_passages",
    "initialize_water_passages_db",
    "passage_row_to_dict",
    # Issue #697: passage_row_to_dict calls the read-path normalizer.
    "_normalize_unknown_reason",
    "_validate_passage_payload",
    "upsert_water_passage",
    "list_water_passages",
    "_delete_passage_mirrors",
    "open_objects_db",
}


def _namespace(temp_dir: str) -> Dict[str, Any]:
    from api.app.log_redaction import redact_log_text
    from api.app.unknown_reason import LEGACY_UNSPECIFIED, is_unknown_reason

    media = Path(temp_dir) / "media"
    media.mkdir()
    return {
        "Any": Any, "Dict": Dict, "List": List, "Optional": Optional,
        "Path": Path, "json": json, "sqlite3": sqlite3, "contextmanager": contextmanager,
        "HTTPException": HTTPExceptionStub,
        "PASSAGES_DB_FILE": Path(temp_dir) / "water_passages.sqlite3",
        "OBJECTS_DB_FILE": Path(temp_dir) / "objects.sqlite3",
        "sys": sys,
        "PASSAGE_MEDIA_DIR": media,
        "PASSAGES_RETENTION_LIMIT": 300,
        "PASSAGE_STATUSES": {"tracking", "measuring", "measured", "completed"},
        "PASSAGE_SPEED_STATUSES": {"unknown", "measuring", "measured", "incomplete"},
        "PASSAGE_ID_RE": re.compile(r"^P-[A-Za-z0-9][A-Za-z0-9._-]{1,78}$"),
        "now_iso": lambda: "2026-11-22T00:00:00+00:00",
        "redact_log_text": redact_log_text,
        # Issue #697: passage_row_to_dict -> _normalize_unknown_reason needs
        # the closed-set helpers from this namespace.
        "is_unknown_reason": is_unknown_reason,
        "LEGACY_UNSPECIFIED": LEGACY_UNSPECIFIED,
    }


@contextmanager
def _store():
    with tempfile.TemporaryDirectory(prefix="sea-speed-697-api-") as temp_dir:
        namespace = _namespace(temp_dir)
        load_api_functions(API_FUNCTIONS, namespace)
        namespace["initialize_water_passages_db"]()
        yield namespace


def _payload(
    index: int,
    *,
    speed_status: str = "unknown",
    speed_kmh: Optional[float] = None,
    measurement_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ts = f"2026-11-22T00:00:{index:02d}+00:00"
    passage_id = f"P-697-{index:04d}"
    return {
        "passage_id": passage_id,
        "status": "completed",
        "started_at": ts,
        "last_seen_at": ts,
        "completed_at": ts,
        "track_fragments": [index],
        "confidence": 0.8,
        "speed_status": speed_status,
        "speed_kmh": speed_kmh,
        "speed_method": "two_gate",
        "direction": "A->B" if speed_kmh is not None else None,
        "measurement_meta": {"samples_used": 2} if measurement_meta is None else measurement_meta,
        "observation_count": 2,
        "snapshot_score": 10 + index,
        "snapshot_url": f"/sea-speed/media/passages/{passage_id}.jpg",
    }


class ApiBoundaryUnknownReasonTests(unittest.TestCase):
    def test_non_string_supplied_reason_is_rejected_400(self) -> None:
        rejects: List[Any] = [123, 0, 1.5, None, True, ["gate_unavailable"], {"reason": "x"}]
        with _store() as namespace:
            for value in rejects:
                with self.subTest(value=repr(value)):
                    with self.assertRaises(HTTPExceptionStub) as ctx:
                        namespace["_validate_passage_payload"](
                            _payload(1, measurement_meta={"unknown_reason": value})
                        )
                    self.assertEqual(ctx.exception.status_code, 400)
                    self.assertIn("unknown_reason", ctx.exception.detail)

    def test_non_enum_supplied_reason_is_rejected_400(self) -> None:
        rejects = ["made_up_reason", "", "TOO_FEW_OBSERVATIONS", "gate-unavailable", "gate_unavailable "]
        with _store() as namespace:
            for value in rejects:
                with self.subTest(value=value):
                    with self.assertRaises(HTTPExceptionStub) as ctx:
                        namespace["_validate_passage_payload"](
                            _payload(1, measurement_meta={"unknown_reason": value})
                        )
                    self.assertEqual(ctx.exception.status_code, 400)
                    self.assertIn("unknown_reason", ctx.exception.detail)

    def test_absent_reason_is_accepted_and_reads_back_as_legacy_unspecified(self) -> None:
        with _store() as namespace:
            returned = namespace["upsert_water_passage"](_payload(1, measurement_meta={"samples_used": 1}))
            self.assertEqual(returned["speed_status"], "unknown")
            # The READ presents the legacy row as typed legacy_unspecified...
            self.assertEqual(returned["measurement_meta"]["unknown_reason"], "legacy_unspecified")
            listed = namespace["list_water_passages"](10)
            self.assertEqual(len(listed), 1)
            self.assertEqual(
                listed[0]["measurement_meta"]["unknown_reason"], "legacy_unspecified"
            )
            self.assertEqual(listed[0]["passage_id"], returned["passage_id"])
            # ...while the stored history is NOT rewritten: the row on disk
            # still carries the meta the legacy writer supplied.
            connection = sqlite3.connect(
                f"file:{namespace['PASSAGES_DB_FILE']}?mode=ro", uri=True
            )
            try:
                raw_meta = json.loads(
                    connection.execute(
                        "SELECT measurement_meta_json FROM water_passages WHERE passage_id = ?",
                        (returned["passage_id"],),
                    ).fetchone()[0]
                )
            finally:
                connection.close()
            self.assertEqual(raw_meta, {"samples_used": 1})
            self.assertNotIn("unknown_reason", raw_meta)

    def test_every_closed_enum_value_is_accepted_on_write(self) -> None:
        for index, reason in enumerate(CLOSED_REASONS, start=1):
            with _store() as namespace, self.subTest(reason=reason):
                returned = namespace["upsert_water_passage"](
                    _payload(index, measurement_meta={"unknown_reason": reason})
                )
                self.assertEqual(returned["measurement_meta"]["unknown_reason"], reason)
                listed = namespace["list_water_passages"](10)
                self.assertEqual(listed[0]["measurement_meta"]["unknown_reason"], reason)

    def test_known_status_row_drops_the_reason_on_read(self) -> None:
        with _store() as namespace:
            returned = namespace["upsert_water_passage"](
                _payload(
                    1,
                    speed_status="measured",
                    speed_kmh=9.9,
                    measurement_meta={"unknown_reason": "gate_unavailable", "samples_used": 2},
                )
            )
            self.assertEqual(returned["speed_status"], "measured")
            self.assertNotIn("unknown_reason", returned["measurement_meta"])
            self.assertEqual(returned["measurement_meta"], {"samples_used": 2})
            listed = namespace["list_water_passages"](10)
            self.assertEqual(len(listed), 1)
            self.assertNotIn("unknown_reason", listed[0]["measurement_meta"])
            self.assertEqual(listed[0]["measurement_meta"], {"samples_used": 2})

    def test_late_unknown_update_does_not_demote_a_measured_row(self) -> None:
        with _store() as namespace:
            first = namespace["upsert_water_passage"](
                _payload(1, speed_status="measured", speed_kmh=9.9, measurement_meta={"samples_used": 2})
            )
            self.assertEqual(first["speed_status"], "measured")
            late = namespace["upsert_water_passage"](
                _payload(
                    1,
                    speed_status="unknown",
                    measurement_meta={"unknown_reason": "too_few_observations", "samples_used": 1},
                )
            )
            self.assertEqual(late["speed_status"], "measured")
            self.assertEqual(late["speed_kmh"], 9.9)
            self.assertEqual(late["measurement_meta"], {"samples_used": 2})
            listed = namespace["list_water_passages"](10)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["speed_status"], "measured")
            self.assertEqual(listed[0]["speed_kmh"], 9.9)
            self.assertEqual(listed[0]["measurement_meta"], {"samples_used": 2})


# ---------------------------------------------------------------------------
# 4. Log line — post_passage success output, byte-exact.
# ---------------------------------------------------------------------------


class PostPassageLogLineTests(unittest.TestCase):
    def _post(self, passage: Dict[str, Any]) -> tuple:
        buffer = io.StringIO()
        with mock.patch.dict(
            os.environ,
            {
                "SEA_SPEED_API_URL": "http://127.0.0.1:1/api",
                "SEA_SPEED_API_TOKEN": "transport-fixture-token",
            },
        ), mock.patch.object(worker_transport.requests, "post") as post, redirect_stdout(buffer):
            post.return_value = mock.Mock(status_code=200)
            ok = worker_transport.post_passage(passage)
        self.assertEqual(post.call_count, 1)
        return ok, buffer.getvalue()

    def test_success_log_appends_the_typed_reason_token(self) -> None:
        ok, output = self._post(
            {
                "passage_id": "P-697-LOG-1",
                "status": "completed",
                "speed_status": "unknown",
                "speed_kmh": None,
                "measurement_meta": {"unknown_reason": "gate_unavailable", "samples_used": 1},
            }
        )
        self.assertTrue(ok)
        self.assertEqual(
            output.strip(),
            "POST passage ok id=P-697-LOG-1 status=completed speed_status=unknown "
            "speed_kmh=- unknown_reason=gate_unavailable",
        )
        self.assertIn(" unknown_reason=gate_unavailable", output)

    def test_success_log_has_no_reason_token_when_the_reason_is_absent(self) -> None:
        ok, output = self._post(
            {
                "passage_id": "P-697-LOG-2",
                "status": "completed",
                "speed_status": "measured",
                "speed_kmh": 9.5,
                "measurement_meta": {"samples_used": 3},
            }
        )
        self.assertTrue(ok)
        self.assertEqual(
            output.strip(),
            "POST passage ok id=P-697-LOG-2 status=completed speed_status=measured speed_kmh=9.500",
        )
        self.assertNotIn("unknown_reason", output)

    def test_success_log_has_no_reason_token_when_meta_is_absent_or_not_a_dict(self) -> None:
        for meta in (None, "not-a-dict", {"unknown_reason": ""}):
            with self.subTest(meta=meta):
                passage: Dict[str, Any] = {
                    "passage_id": "P-697-LOG-3",
                    "status": "measuring",
                    "speed_status": "measuring",
                    "speed_kmh": None,
                }
                if meta is not None:
                    passage["measurement_meta"] = meta
                ok, output = self._post(passage)
                self.assertTrue(ok)
                self.assertNotIn("unknown_reason", output)
                self.assertIn("POST passage ok id=P-697-LOG-3", output)


# ---------------------------------------------------------------------------
# 5. Packaging — count 11, three inventories, deploy.sh mirror sites.
# ---------------------------------------------------------------------------


class UnknownReasonPackagingTests(unittest.TestCase):
    DEPLOY_SH = ROOT / "deploy" / "vps" / "deploy.sh"

    def _vps_required_app_modules(self) -> set:
        return {p for p in COMPONENT_FILES["vps"]["required"] if p.startswith("api/app/")}

    def test_api_app_mirror_count_is_eleven_and_converges(self) -> None:
        text = self.DEPLOY_SH.read_text(encoding="utf-8")
        mirrored = deploy_app_module_targets(text)
        required = self._vps_required_app_modules()
        self.assertEqual(
            len(mirrored), 11, f"unexpected api/app TARGET mirror set: {sorted(mirrored)}"
        )
        self.assertEqual(mirrored, required)

    def test_module_is_required_by_all_three_inventories(self) -> None:
        module = "api/app/unknown_reason.py"
        self.assertIn(module, COMPONENT_FILES["vps"]["required"])
        self.assertIn(module, COMPONENT_FILES["ubuntu-worker"]["required"])
        self.assertIn(module, COMPONENT_FILES["edge"]["required"])
        # build and validate agree, both directions.
        self.assertIn(module, REQUIRED_BY_COMPONENT["vps"])
        self.assertIn(module, REQUIRED_BY_COMPONENT["ubuntu-worker"])
        self.assertIn(module, REQUIRED_BY_COMPONENT["edge"])

    def test_deploy_sh_declares_every_mirror_site(self) -> None:
        text = self.DEPLOY_SH.read_text(encoding="utf-8")
        sites = (
            'UNKNOWN_REASON_TARGET="$(dirname "$API_TARGET")/unknown_reason.py"',
            '-f "$root/api/app/unknown_reason.py"',
            "api/app/unknown_reason.py \\",
            'install -m 0644 "$extracted/api/app/unknown_reason.py" "$TARGET_RELEASE/api/app/unknown_reason.py"',
            'install -m 0644 "$UNKNOWN_REASON_TARGET" "$bootstrap_release/api/app/unknown_reason.py"',
            'if [[ -f "$release_dir/api/app/unknown_reason.py" ]]; then',
            'install -m 0644 "$release_dir/api/app/unknown_reason.py" "${UNKNOWN_REASON_TARGET}.next"',
            'mv -f "${UNKNOWN_REASON_TARGET}.next" "$UNKNOWN_REASON_TARGET"',
            'rm -f "$UNKNOWN_REASON_TARGET" "${UNKNOWN_REASON_TARGET}.next"',
        )
        for site in sites:
            with self.subTest(site=site):
                self.assertIn(site, text)
        # The module lands (and is activated) BEFORE main.py, because
        # water_passages.py imports it at boot.
        self.assertGreaterEqual(text.count("api/app/unknown_reason.py"), 8)
        self.assertLess(
            text.index('mv -f "${UNKNOWN_REASON_TARGET}.next" "$UNKNOWN_REASON_TARGET"'),
            text.index('mv -f "${API_TARGET}.next" "$API_TARGET"'),
        )

    def test_release_complete_requires_the_module(self) -> None:
        # The completeness gate is what makes a release without the module
        # (the pre-#697 shape) fail closed at deploy time.
        source = self.DEPLOY_SH.read_text(encoding="utf-8")
        complete = source.split("release_complete() {", 1)[1].split("\n}", 1)[0]
        self.assertIn('-f "$root/api/app/unknown_reason.py"', complete)


# ---------------------------------------------------------------------------
# 6. Scope guard — the working tree touches only the admitted #697 surface.
# ---------------------------------------------------------------------------


class UnknownReasonScopeGuardTests(unittest.TestCase):
    """No new workflow/lockfile/API-config change; only the admitted paths."""

    ALLOWED_CHANGE_PREFIXES = (
        "tests/",
        "api/app/unknown_reason.py",
        "api/app/water_passages.py",
        "worker/water_passage.py",
        "worker/worker_transport.py",
        "deploy/vps/deploy.sh",
        "scripts/quality/build_exact_artifacts.py",
        "scripts/quality/validate_exact_artifacts.py",
        "specs/697-typed-unknown-reason/",
    )
    FORBIDDEN_PREFIXES = (".github/", ".gitlab", "api/requirements", "api/app/config.py")

    def _changed_paths(self) -> List[str]:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        paths: List[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            paths.append(path.strip().strip('"'))
        return paths

    def test_working_tree_touches_only_the_697_surface_and_tests(self) -> None:
        changed = self._changed_paths()
        offenders = [
            path
            for path in changed
            if not any(path.startswith(prefix) for prefix in self.ALLOWED_CHANGE_PREFIXES)
        ]
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope working-tree changes (issue #697 surface only): {offenders}",
        )

    def test_no_workflow_lockfile_or_api_config_change(self) -> None:
        changed = self._changed_paths()
        for path in changed:
            with self.subTest(path=path):
                self.assertFalse(
                    any(path.startswith(prefix) for prefix in self.FORBIDDEN_PREFIXES),
                    f"forbidden path changed: {path}",
                )
                self.assertFalse(
                    path.endswith(".lock") or path.endswith(".lock.txt"),
                    f"lockfile changed: {path}",
                )
                self.assertNotIn("package-lock.json", path)
                self.assertNotIn("runtime-lock.json", path)


if __name__ == "__main__":
    unittest.main()
