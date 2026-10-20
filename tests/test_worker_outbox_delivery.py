"""Issue #537 wave 2 — durable outbox delivery + fault-injection suite.

TEST-001..TEST-009 / TEST-011 / TEST-013 of specs/537-wave2-worker-outbox/plan.md;
covers AC-001..AC-009, AC-010, AC-011, AC-013 of specs/537-wave2-worker-outbox/spec.md.

Conventions:
- tempfile.TemporaryDirectory for every DB (tests/test_road_event_delivery.py style);
- ``requests`` is NOT installed in this sandbox — the transport is stubbed at the
  module's own guarded seam: worker/worker_outbox.py imports requests in a
  try/except and reads it as a module global inside ``_post``, so the tests
  inject a requests-shaped stub via mock.patch.object(mod, "requests", stub)
  and drive the REAL response-handling code (status codes, JSON body,
  multipart layout, URL/token env derivation);
- the publisher daemon thread runs against a fake monotonic clock patched at
  ``worker_outbox.time`` (the module's only clock surface), so bounded-backoff
  waits never sleep for real and jitter is injected zero or seeded;
- the observability half reuses the subprocess + fake-worker + fake-PATH-tools
  convention of tests/test_ubuntu_worker_observability.py:47-92,94-182.

AC-012 (protected surfaces) is deliberately NOT asserted here: per the plan it
is verified by running the existing suites unmodified (regression guard).
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/worker/ubuntu"
RUNNER = DEPLOY / "observed-worker-runner.py"
CHECKER = DEPLOY / "check-worker-health.py"
COMPATIBILITY = ROOT / "scripts/worker/check_ubuntu_compatibility.py"
INSTALLER = DEPLOY / "install-systemd.sh"
BUILD_ARTIFACTS = ROOT / "scripts/quality/build_exact_artifacts.py"
VALIDATE_ARTIFACTS = ROOT / "scripts/quality/validate_exact_artifacts.py"
VALIDATE_REPO = ROOT / "scripts/ci/validate_repo.py"
COMMIT40 = "a" * 40

SNAPSHOT_BYTES = b"\xff\xd8\x00\xff\xe0jpeg-payload\xff\xd9"
EVENT_URL = "http://stub.invalid/api/analytics/road1/events"
API_TOKEN = "test-token-0000000000"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def load_outbox_module():
    """Import worker/worker_outbox.py by its runtime name (requests stays guarded)."""
    worker_dir = str(ROOT / "worker")
    if worker_dir not in sys.path:
        sys.path.insert(0, worker_dir)
    import worker_outbox

    return worker_outbox


def _wait_for(predicate, timeout=10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.002)
    return False


class _FakeClock:
    """time-surface stand-in: every monotonic read jumps past any 60s backoff."""

    def __init__(self) -> None:
        self._mono = 1_000_000.0

    def monotonic(self) -> float:
        self._mono += 1_000.0
        return self._mono

    def time(self) -> float:
        return 1_700_000_000.0

    def gmtime(self, t=None):
        return time.gmtime(self.time() if t is None else t)

    def strftime(self, fmt, t=None) -> str:
        return time.strftime(fmt, t if t is not None else self.gmtime())


class _StubResponse:
    def __init__(self, status_code: int, body=None, text: str = "") -> None:
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


class _TransportStub:
    """requests-shaped stub injected at the module's guarded ``requests`` seam.

    ``responder(call_index, metadata_str)`` returns a _StubResponse or raises
    (raising mirrors a transport-level connection error).
    """

    def __init__(self, responder) -> None:
        self._responder = responder
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def post(self, url, headers=None, data=None, files=None, timeout=None):
        with self._lock:
            index = len(self.calls)
            self.calls.append(
                {
                    "url": url,
                    "headers": dict(headers or {}),
                    "metadata": data["metadata"],
                    "snapshot": files["snapshot"],
                    "timeout": timeout,
                }
            )
        return self._responder(index, self.calls[index]["metadata"])


def _ok_body(metadata: str, duplicate: bool = False) -> dict:
    event_id = json.loads(metadata)["event_id"] if isinstance(metadata, str) else "?"
    return {"ok": True, "event": {"event_id": event_id}, "duplicate": duplicate}


def _event_metadata(event_id: str) -> str:
    return json.dumps(
        {"event_id": event_id, "camera_id": "road1", "class_name": "car", "confidence": 0.9},
        ensure_ascii=False,
    )


class _DiskFullConnection:
    """Delegating sqlite3-connection proxy: INSERTs into outbox_events fail.

    Stands in for disk-full/SQLite write failure at the seam (AC-005) without
    touching the schema-init path (which the tests construct first, for real).
    """

    def __init__(self, real) -> None:
        self._real = real

    def execute(self, sql, *args, **kwargs):
        if isinstance(sql, str) and sql.lstrip().upper().startswith("INSERT INTO OUTBOX_EVENTS"):
            raise sqlite3.OperationalError("database or disk is full")
        return self._real.execute(sql, *args, **kwargs)

    def __enter__(self):
        return self._real.__enter__()

    def __exit__(self, *exc):
        return self._real.__exit__(*exc)

    def commit(self):
        return self._real.commit()

    def close(self):
        return self._real.close()


class OutboxTestBase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db_path = self.tmp / "road-worker-outbox.sqlite3"
        self.snapshot = self.tmp / "event.jpg"
        self.snapshot.write_bytes(SNAPSHOT_BYTES)
        self.env = {"SEA_SPEED_EVENT_API_URL": EVENT_URL, "SEA_SPEED_API_TOKEN": API_TOKEN}

    def drive_publisher(self, outbox, stub, actions) -> dict:
        """Start the real publisher thread under the fake clock + stub transport.

        ``actions`` runs against the live outbox/stub (poll, assert, release
        gates); the transport/env/clock patches are managed here.
        """
        mod = load_outbox_module()
        summary: dict = {}
        with (
            mock.patch.dict(os.environ, self.env, clear=False),
            mock.patch.object(mod, "requests", stub),
            mock.patch.object(mod, "time", _FakeClock()),
        ):
            outbox.start()
            try:
                actions(outbox, stub, summary)
            finally:
                outbox.close()
        return summary


class OutboxDurabilityTests(OutboxTestBase):
    def test_enqueue_persists_metadata_and_snapshot_before_returning_true(self) -> None:
        """AC-001 / TEST-001: durable-before-report at the module surface.

        enqueue() returns True only after the metadata JSON string and the
        snapshot JPEG bytes are readable from the SQLite file (independent
        connection), and a 'crash' right after (fresh instance, publisher never
        started) still finds the exact row.
        """
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(outbox.close)
        metadata = _event_metadata("evt-durable")
        self.assertIs(outbox.enqueue("evt-durable", metadata, self.snapshot), True)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT event_id, metadata, snapshot_bytes, status FROM outbox_events"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "evt-durable")
        self.assertEqual(rows[0][1], metadata, "metadata must be stored byte-verbatim")
        self.assertEqual(rows[0][2], SNAPSHOT_BYTES, "snapshot bytes must be stored verbatim")
        self.assertEqual(rows[0][3], "pending")
        # crash immediately after acceptance: new instance, publisher stopped
        reopened = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(reopened.close)
        self.assertIsNone(reopened._thread)
        self.assertEqual(reopened.pending_count(), 1)

    def test_sqlite_write_failure_raises_and_leaves_no_partial_row(self) -> None:
        """AC-005 / TEST-005 (module half): the seam contract is raise-not-accept.

        worker_outbox.enqueue RAISES on SQLite write failure (the entrypoint
        seam converts that to False — see EntrypointSeamTests); nothing may be
        reported accepted and no partial row may exist.
        """
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(outbox.close)
        outbox._conn = _DiskFullConnection(outbox._conn)
        with self.assertRaises(sqlite3.OperationalError):
            outbox.enqueue("evt-diskfull", _event_metadata("evt-diskfull"), self.snapshot)
        self.assertEqual(outbox.pending_count(), 0)
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM outbox_events WHERE event_id = 'evt-diskfull'"
            ).fetchone()[0]
        self.assertEqual(count, 0, "failed enqueue must leave no partial row")

    def test_missing_snapshot_file_raises_oserror_and_leaves_no_row(self) -> None:
        """AC-005 / TEST-005 (module half, OSError arm): snapshot byte capture is
        part of the atomic enqueue — a lost file fails closed, no row."""
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(outbox.close)
        with self.assertRaises(OSError):
            outbox.enqueue("evt-nofile", _event_metadata("evt-nofile"), self.tmp / "rotated.jpg")
        self.assertEqual(outbox.pending_count(), 0)


class OutboxFaultInjectionTests(OutboxTestBase):
    def test_outage_keeps_rows_pending_and_recovery_delivers_all_fifo(self) -> None:
        """AC-002 / TEST-002: outage -> recovery fault injection.

        Transport raises connection errors for the first three attempts: rows
        stay pending and nothing is discarded; after recovery every pending
        row is delivered byte-verbatim in FIFO order and confirmed
        (delete-on-confirm), and the lifetime heartbeat counters survive.
        """
        gate = threading.Event()

        def responder(index: int, metadata: str):
            if index < 3:
                raise ConnectionError("connection refused")
            if index == 3:
                self.assertTrue(gate.wait(timeout=10.0), "recovery gate never released")
            return _StubResponse(200, _ok_body(metadata))

        stub = _TransportStub(responder)
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        expected = {}
        for i in range(3):
            event_id = f"evt-{i}"
            metadata = _event_metadata(event_id)
            outbox.enqueue(event_id, metadata, self.snapshot)
            expected[event_id] = metadata

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: len(live_stub.calls) >= 4))
            # outage in progress: nothing discarded, all rows still pending
            self.assertEqual(live.pending_count(), 3)
            gate.set()
            self.assertTrue(_wait_for(lambda: live.pending_count() == 0))
            summary.update(live.snapshot())

        summary = self.drive_publisher(outbox, stub, actions)
        order = [json.loads(call["metadata"])["event_id"] for call in stub.calls]
        self.assertEqual(order, ["evt-0", "evt-0", "evt-0", "evt-0", "evt-1", "evt-2"])
        for call in stub.calls:
            event_id = json.loads(call["metadata"])["event_id"]
            self.assertEqual(call["metadata"], expected[event_id], "byte-verbatim delivery")
            self.assertEqual(call["snapshot"][1], SNAPSHOT_BYTES)
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0], 0)
        self.assertEqual(summary["send_errors"], 3)
        self.assertEqual(summary["pending"], 0)
        self.assertIsNotNone(summary["last_confirmed_epoch"])

    def test_duplicate_redelivery_is_confirmed_and_row_deleted(self) -> None:
        """AC-003 / TEST-003 (+AC-013 family): receipt-path duplicate collapse.

        A retry of the row is answered 200 duplicate=true by the server
        receipt path: the row is deleted on confirm, no further retry is
        posted, and the metadata string stays byte-identical across attempts.
        """

        def responder(index: int, metadata: str):
            if index == 0:
                raise ConnectionError("connection reset")
            return _StubResponse(200, _ok_body(metadata, duplicate=True))

        stub = _TransportStub(responder)
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        metadata = _event_metadata("evt-dup")
        outbox.enqueue("evt-dup", metadata, self.snapshot)

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: live.pending_count() == 0))
            time.sleep(0.3)  # settle: a deleted row must never be re-picked
            self.assertEqual(len(live_stub.calls), 2)
            summary.update(live.snapshot())

        summary = self.drive_publisher(outbox, stub, actions)
        self.assertEqual([call["metadata"] for call in stub.calls], [metadata, metadata])
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0], 0)
        self.assertEqual(summary["accept_errors"], 0)
        self.assertEqual(summary["send_errors"], 1)

    def test_restart_drains_pending_rows_without_new_detections(self) -> None:
        """AC-004 / TEST-004: restart recovery.

        Rows accepted by a previous instance (publisher stopped) are drained
        by a fresh instance on the same file with NO new enqueue/detection.
        """
        mod = load_outbox_module()
        first = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        for i in range(2):
            first.enqueue(f"evt-boot-{i}", _event_metadata(f"evt-boot-{i}"), self.snapshot)
        first.close()  # process boundary: rows stay in the file, no publisher

        stub = _TransportStub(lambda index, metadata: _StubResponse(200, _ok_body(metadata)))
        second = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: live.pending_count() == 0))

        self.drive_publisher(second, stub, actions)
        order = [json.loads(call["metadata"])["event_id"] for call in stub.calls]
        self.assertEqual(order, ["evt-boot-0", "evt-boot-1"])

    def test_backoff_envelope_is_bounded_exponential_with_zero_jitter(self) -> None:
        """AC-006 / TEST-006: base 1s, factor x2, cap 60s (delay = min(60, 2^(n-1))).

        Asserted at the module's documented deterministic boundary — the
        injectable ``jitter_function`` (D-104: "jitter must be injectable (seeded
        RNG) so tests are deterministic"). Zero jitter reproduces the exact
        envelope; the public API cannot expose per-attempt delays without real
        multi-minute sleeps.
        """
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(outbox.close)
        delays = [outbox._backoff_delay(n) for n in range(1, 11)]
        self.assertEqual(delays, [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0, 60.0, 60.0])

    def test_seeded_jitter_is_additive_and_capped_at_sixty_seconds(self) -> None:
        """AC-006 / TEST-006: jitter determinism + bounded envelope.

        With a fixed seed (random.Random(0)) across 20 attempts: jitter is
        additive (delay >= raw) and the total never exceeds the 60s cap; the
        same seed reproduces the identical sequence.
        """
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=random.Random(0).random)
        self.addCleanup(outbox.close)
        twin = mod.WorkerOutbox(self.tmp / "twin.sqlite3", jitter_function=random.Random(0).random)
        self.addCleanup(twin.close)
        delays = [outbox._backoff_delay(n) for n in range(1, 21)]
        self.assertEqual(delays, [twin._backoff_delay(n) for n in range(1, 21)])
        for attempts, delay in enumerate(delays, start=1):
            raw = min(60.0, 2.0 ** (attempts - 1))
            self.assertGreaterEqual(delay, raw)
            self.assertLessEqual(delay, min(60.0, raw * 1.25))
            self.assertLessEqual(delay, 60.0)

    def test_no_attempt_based_discard_after_twelve_failures(self) -> None:
        """AC-006 / TEST-006 (no-discard arm): 12 consecutive send errors.

        The row survives with attempts=12, status pending, and is delivered
        once the transport recovers — no row is discarded after any number of
        attempts (FR-005/D-104).
        """
        gate = threading.Event()

        def responder(index: int, metadata: str):
            if index < 12:
                raise ConnectionError("connection refused")
            if index == 12:
                self.assertTrue(gate.wait(timeout=10.0), "recovery gate never released")
            return _StubResponse(200, _ok_body(metadata))

        stub = _TransportStub(responder)
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        outbox.enqueue("evt-patience", _event_metadata("evt-patience"), self.snapshot)

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: len(live_stub.calls) >= 13))
            self.assertEqual(live.pending_count(), 1, "row must never be discarded")
            with sqlite3.connect(self.db_path) as conn:
                attempts, status = conn.execute(
                    "SELECT attempts, status FROM outbox_events WHERE event_id = 'evt-patience'"
                ).fetchone()
            self.assertEqual(attempts, 12)
            self.assertEqual(status, "pending")
            gate.set()
            self.assertTrue(_wait_for(lambda: live.pending_count() == 0))

        self.drive_publisher(outbox, stub, actions)
        self.assertEqual(len(stub.calls), 13)

    def test_409_conflict_is_terminal_and_does_not_block_the_queue(self) -> None:
        """AC-007 / TEST-007: 409 is a terminal accept-error.

        The row is retained (status terminal_error, never re-posted), the
        accept-error counter increments, it keeps counting as pending /
        oldest-unconfirmed, and the next event is still delivered — a terminal
        head row does not block the publisher.
        """

        def responder(index: int, metadata: str):
            event_id = json.loads(metadata)["event_id"]
            if event_id == "evt-conflict":
                return _StubResponse(409, text="event_id accepted with different content")
            return _StubResponse(200, _ok_body(metadata))

        stub = _TransportStub(responder)
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        outbox.enqueue("evt-conflict", _event_metadata("evt-conflict"), self.snapshot)
        outbox.enqueue("evt-next", _event_metadata("evt-next"), self.snapshot)

        def actions(live, live_stub, summary):
            # evt-next confirmed, evt-conflict retained as terminal
            self.assertTrue(_wait_for(lambda: live.pending_count() == 1))
            time.sleep(0.3)  # settle: the terminal row must not be re-picked
            conflict_calls = [
                c for c in live_stub.calls if json.loads(c["metadata"])["event_id"] == "evt-conflict"
            ]
            self.assertEqual(len(conflict_calls), 1, "409 row must never be retried")
            summary.update(live.snapshot())

        summary = self.drive_publisher(outbox, stub, actions)
        delivered = [json.loads(c["metadata"])["event_id"] for c in stub.calls]
        self.assertIn("evt-next", delivered, "terminal head row must not block the queue")
        self.assertEqual(summary["accept_errors"], 1)
        self.assertEqual(summary["pending"], 1, "terminal row stays unconfirmed")
        self.assertIsNotNone(summary["oldest_unconfirmed_sec"])
        with sqlite3.connect(self.db_path) as conn:
            status, attempts, accept_errors = conn.execute(
                "SELECT status, attempts, accept_errors FROM outbox_events"
                " WHERE event_id = 'evt-conflict'"
            ).fetchone()
        self.assertEqual(status, "terminal_error")
        self.assertEqual(attempts, 1)
        self.assertEqual(accept_errors, 1)

    def test_person_filter_ok_event_null_is_terminal_success(self) -> None:
        """AC-008 / TEST-008: 200 {"ok": true, "event": null} (person-filtered).

        Terminal success: the row is deleted, no retry is posted, and nothing
        is counted as an accept/send error.
        """
        stub = _TransportStub(
            lambda index, metadata: _StubResponse(200, {"ok": True, "event": None})
        )
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        outbox.enqueue("evt-person", _event_metadata("evt-person"), self.snapshot)

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: live.pending_count() == 0))
            time.sleep(0.3)
            self.assertEqual(len(live_stub.calls), 1, "terminal success must not retry")
            summary.update(live.snapshot())

        summary = self.drive_publisher(outbox, stub, actions)
        self.assertEqual(summary["accept_errors"], 0)
        self.assertEqual(summary["send_errors"], 0)
        self.assertEqual(summary["retries"], 0)
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0], 0)

    def test_retry_posts_identical_metadata_string_and_snapshot_bytes(self) -> None:
        """AC-013 / TEST-013: byte-verbatim retries.

        Across three attempts of the same row the posted metadata JSON string
        (including non-ASCII) and snapshot bytes are identical to the accepted
        delivery, and the multipart/URL/auth shape matches FR-006.
        """
        metadata = json.dumps(
            {"event_id": "evt-verbatim", "camera_id": "дорога-1", "snapshot_url": "/a/б.jpg"},
            ensure_ascii=False,
        )

        def responder(index: int, md: str):
            if index < 2:
                raise ConnectionError("connection reset")
            return _StubResponse(200, _ok_body(md))

        stub = _TransportStub(responder)
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        outbox.enqueue("evt-verbatim", metadata, self.snapshot)

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: live.pending_count() == 0))

        self.drive_publisher(outbox, stub, actions)
        self.assertEqual(len(stub.calls), 3)
        for call in stub.calls:
            self.assertEqual(call["metadata"], metadata, "re-posted metadata must be byte-verbatim")
            self.assertEqual(call["snapshot"], ("event.jpg", SNAPSHOT_BYTES, "image/jpeg"))
            self.assertEqual(call["url"], EVENT_URL)
            self.assertEqual(call["headers"]["Authorization"], f"Bearer {API_TOKEN}")

    def test_confirmed_retry_increments_lifetime_retries_metric(self) -> None:
        """DEF-1 pin (confirmed branch): the lifetime ``retries`` metric counts
        successful re-deliveries. The module docstring — "``retries`` counts
        re-delivery attempts of a row that already failed at least once (a
        retry that succeeds still counts)" (lines 74-75 of the module
        docstring) — states the intended semantics; the initial implementation
        dropped the increment in the confirmed branch of _deliver (defect
        DEF-1, discovered by this suite and reported to the delivery
        orchestrator).

        Fixture: transport stub raises a connection error on the first
        attempt of row 1, then succeeds; row 2 is confirmed on its first
        attempt. Assertions: the lifetime heartbeat metric snapshot()["retries"]
        is exactly 1 after both rows confirm — row 1's successful re-delivery
        contributes 1 and survives delete-on-confirm, row 2's first-attempt
        success contributes 0 (a combined total of 1 pins both halves). The
        heartbeat marker is fed by snapshot() via _emit_marker_if_due, so the
        last emitted marker's retries field must carry the same value.

        RED was verified against the pre-fix tree (suite state then:
        1 failed / 20 passed); the fix landed in-wave in the confirmed branch
        of _deliver (worker/worker_outbox.py:372-373, guarded ``if is_retry:
        _meta_increment("outbox_retries_total")``) and this pin is GREEN in
        the current tree. Do NOT weaken this test to make it pass.
        """
        import contextlib
        import io

        def responder(index: int, metadata: str):
            if index == 0:
                raise ConnectionError("connection reset")
            return _StubResponse(200, _ok_body(metadata))

        stub = _TransportStub(responder)
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        # row 1: fails once, then re-delivered and confirmed -> +1 retry
        outbox.enqueue("evt-retry-counted", _event_metadata("evt-retry-counted"), self.snapshot)
        # row 2: confirmed on the first attempt -> contributes 0
        outbox.enqueue("evt-first-try", _event_metadata("evt-first-try"), self.snapshot)

        marker_buffer = io.StringIO()

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: live.pending_count() == 0))
            time.sleep(0.3)  # settle: the final-state marker is already emitted
            summary.update(live.snapshot())

        with contextlib.redirect_stdout(marker_buffer):
            summary = self.drive_publisher(outbox, stub, actions)

        self.assertEqual(len(stub.calls), 3)
        self.assertEqual(summary["pending"], 0)
        self.assertEqual(summary["send_errors"], 1)
        self.assertEqual(
            summary["retries"],
            1,
            "DEF-1: a re-delivery that succeeds must count in the lifetime retries metric",
        )
        markers = [
            line
            for line in marker_buffer.getvalue().splitlines()
            if line.startswith("outbox pending=")
        ]
        self.assertTrue(markers, "publisher must emit the heartbeat marker")
        fields = dict(fragment.split("=", 1) for fragment in markers[-1].split()[1:])
        self.assertEqual(int(fields["retries"]), summary["retries"])
        self.assertEqual(int(fields["retries"]), 1)

    def test_terminal_409_on_redelivery_increments_lifetime_retries_metric(self) -> None:
        """DEF-1 pin (terminal branch): a 409 answered on a re-delivery
        attempt counts in the lifetime ``retries`` metric too
        (reviewer-flagged same-class gap). The module docstring — "``retries``
        counts re-delivery attempts of a row that already failed at least
        once" — is outcome-agnostic: the send-error branch has always
        incremented the lifetime outbox_retries_total and the confirmed
        branch does since the DEF-1 fix; the TERMINAL branch (409 answered on
        a re-delivery, attempts>0) initially did not (DEF-1, discovered by
        this suite).

        Fixture mirrors the 409 terminal test's transport stub: attempt 0
        raises a connection error, attempt 1 (a re-delivery, attempts>0) is
        answered HTTP 409 -> terminal. Assertions: accept_errors == 1
        (existing semantics), the row is retained with status terminal_error
        (its per-row retries column already reads 1 — only the lifetime meta
        counter is missing the increment), and the lifetime metric
        snapshot()["retries"] == 1.

        RED was verified against the pre-fix tree (suite state then:
        1 failed / 21 passed); the fix landed in-wave in the terminal branch
        of _deliver (worker/worker_outbox.py:384-385, the same guarded
        ``if is_retry: _meta_increment("outbox_retries_total")``) and this
        pin is GREEN in the current tree. Do NOT weaken this test.
        """

        def responder(index: int, metadata: str):
            if index == 0:
                raise ConnectionError("connection reset")
            return _StubResponse(409, text="event_id accepted with different content")

        stub = _TransportStub(responder)
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        outbox.enqueue("evt-terminal-retry", _event_metadata("evt-terminal-retry"), self.snapshot)

        def row_is_terminal() -> bool:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT status FROM outbox_events WHERE event_id = 'evt-terminal-retry'"
                ).fetchone()
            return row is not None and row[0] == "terminal_error"

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: len(live_stub.calls) >= 2))
            # pending_count stays 1 across the pending->terminal transition;
            # the row status is the real sync point
            self.assertTrue(_wait_for(row_is_terminal))
            time.sleep(0.3)  # settle: the terminal row must never be re-picked
            self.assertEqual(len(live_stub.calls), 2)
            summary.update(live.snapshot())

        summary = self.drive_publisher(outbox, stub, actions)
        self.assertEqual(summary["accept_errors"], 1, "existing terminal semantics intact")
        self.assertEqual(summary["send_errors"], 1)
        self.assertEqual(summary["pending"], 1, "409 row stays unconfirmed")
        self.assertEqual(
            summary["retries"],
            1,
            "a 409 on a re-delivery must count in the lifetime retries metric "
            "(docstring: re-delivery attempts of a row that already failed count)",
        )
        with sqlite3.connect(self.db_path) as conn:
            status, attempts, row_retries = conn.execute(
                "SELECT status, attempts, retries FROM outbox_events"
                " WHERE event_id = 'evt-terminal-retry'"
            ).fetchone()
        self.assertEqual(status, "terminal_error")
        self.assertEqual(attempts, 2)
        self.assertEqual(row_retries, 1, "per-row retries column already counts the attempt")

    def test_backoff_survives_extreme_attempt_counts_without_overflow(self) -> None:
        """Validator finding #2 pin (pre-merge static rejection of the wave-2
        head): _backoff_delay evaluates ``_BACKOFF_FACTOR ** (attempts - 1)``
        BEFORE the min(..., 60) cap, so attempts-1 >= 1024 raises
        OverflowError. The publisher retries indefinitely by design (no
        attempt-based discard — pinned by the existing no-discard test), so a
        prolonged outage persists attempt counts into that range. The
        exception then escapes _deliver into the publisher's generic handler:
        unbounded "outbox publisher error" spam on a ~1s real-clock rhythm
        instead of the promised 60s capped backoff, and the send-error
        bookkeeping UPDATE is skipped entirely.

        Pin (RED by design; the fix goes to a code order — do NOT weaken):
        (a) _backoff_delay(5000) with the zero-jitter function (constructed
            the same way as the backoff-envelope test) returns exactly the
            60s cap and does not raise;
        (b) end-to-end: a row whose persisted attempts column is synthetically
            raised to 5000 (separate sqlite connection UPDATE — standing in
            for a long outage) still flows through the real publisher: the
            failed send is recorded in the lifetime metric (send_errors == 1),
            the re-delivery is confirmed, and the publisher loop is NOT broken
            into exception spam (no "outbox publisher error" line emitted).
        """
        import contextlib
        import io

        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(outbox.close)

        # (a) the documented deterministic boundary must return the cap
        self.assertEqual(outbox._backoff_delay(5000), 60.0)

        # (b) end-to-end with an extreme persisted attempts value
        def responder(index: int, metadata: str):
            if index == 0:
                raise ConnectionError("connection reset")
            return _StubResponse(200, _ok_body(metadata))

        stub = _TransportStub(responder)
        outbox.enqueue("evt-extreme", _event_metadata("evt-extreme"), self.snapshot)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE outbox_events SET attempts = 5000 WHERE event_id = 'evt-extreme'"
            )
            conn.commit()

        publisher_stdout = io.StringIO()

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: live.pending_count() == 0))
            time.sleep(0.3)  # settle
            summary.update(live.snapshot())

        with contextlib.redirect_stdout(publisher_stdout):
            summary = self.drive_publisher(outbox, stub, actions)

        self.assertEqual(len(stub.calls), 2)
        self.assertEqual(summary["pending"], 0)
        self.assertEqual(
            summary["send_errors"],
            1,
            "the failed send of the extreme-attempts row must be recorded "
            "(the OverflowError path skips the send-error bookkeeping UPDATE)",
        )
        self.assertNotIn(
            "outbox publisher error",
            publisher_stdout.getvalue(),
            "backoff must not escape into the publisher's generic exception spam",
        )


class EntrypointSeamTests(OutboxTestBase):
    """post_event seam semantics (FR-003/D-106) via the provenance load pattern
    (tests/test_ubuntu_worker_runtime_provenance.py:17-60)."""

    def load_entrypoint(self):
        import importlib.util
        import types

        worker = types.ModuleType("hls_motion_yolo_worker_events")
        worker.start_media_reader = lambda av_module=None: None
        worker.post_state = lambda metadata, overlay_path: "state-ok"
        worker.post_event = lambda metadata, snapshot_path: "event-ok"
        profiles = types.ModuleType("analytics_profiles")
        profiles.get_profile = lambda _name: types.SimpleNamespace(
            sample_fps=5.0,
            model_name="models/yolo26x.pt",
            tracker="bytetrack.yaml",
            image_size=960,
            confidence=0.15,
            name="road-v1",
        )
        load_outbox_module()  # ensure worker/ is importable for the seam's lazy import
        spec = importlib.util.spec_from_file_location(
            f"entrypoint_seam_{id(self)}", ROOT / "worker/ubuntu_worker_entrypoint.py"
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(
            sys.modules,
            {
                "analytics_profiles": profiles,
                "hls_motion_yolo_worker_events": worker,
                "numpy": types.ModuleType("numpy"),
            },
        ):
            spec.loader.exec_module(module)
        return module

    def test_post_event_returns_true_only_after_durable_persistence(self) -> None:
        """AC-001 / TEST-001 (seam half): post_event True implies the row is
        already readable from the SQLite file; a 'crash' right after (publisher
        stopped, fresh instance) still finds it."""
        mod = load_outbox_module()
        with mock.patch.dict(
            os.environ,
            {"SEA_SPEED_SOURCE_COMMIT": SOURCE_COMMIT, "SEA_SPEED_OUTBOX_DB": str(self.db_path)},
            clear=False,
        ):
            os.environ.pop("SEA_SPEED_SYNC_PUBLISH", None)
            entrypoint = self.load_entrypoint()
            try:
                self.assertIs(
                    entrypoint.post_event(
                        {"event_id": "evt-seam-1", "camera_id": "road1"}, self.snapshot
                    ),
                    True,
                )
                with sqlite3.connect(self.db_path) as conn:
                    rows = conn.execute(
                        "SELECT event_id, metadata, snapshot_bytes FROM outbox_events"
                    ).fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][0], "evt-seam-1")
                self.assertEqual(rows[0][2], SNAPSHOT_BYTES)
                stored = json.loads(rows[0][1])
                self.assertEqual(stored["worker_source_commit"], SOURCE_COMMIT)
            finally:
                entrypoint._close_outbox()  # publisher stopped = crash boundary
            reopened = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
            self.addCleanup(reopened.close)
            self.assertEqual(reopened.pending_count(), 1)

    def test_post_event_returns_false_when_sqlite_write_fails(self) -> None:
        """AC-005 / TEST-005 (seam half): disk-full at the seam returns False
        (fail-closed) and nothing is reported accepted — no row appears."""
        with mock.patch.dict(
            os.environ,
            {"SEA_SPEED_SOURCE_COMMIT": SOURCE_COMMIT, "SEA_SPEED_OUTBOX_DB": str(self.db_path)},
            clear=False,
        ):
            os.environ.pop("SEA_SPEED_SYNC_PUBLISH", None)
            entrypoint = self.load_entrypoint()
            try:
                self.assertIs(
                    entrypoint.post_event(
                        {"event_id": "evt-seam-ok", "camera_id": "road1"}, self.snapshot
                    ),
                    True,
                )
                outbox = entrypoint._outbox
                outbox._conn = _DiskFullConnection(outbox._conn)
                try:
                    result = entrypoint.post_event(
                        {"event_id": "evt-seam-full", "camera_id": "road1"}, self.snapshot
                    )
                finally:
                    outbox._conn = outbox._conn._real
                self.assertIs(result, False, "disk-full must fail closed at the seam")
                with sqlite3.connect(self.db_path) as conn:
                    count = conn.execute(
                        "SELECT COUNT(*) FROM outbox_events WHERE event_id = 'evt-seam-full'"
                    ).fetchone()[0]
                self.assertEqual(count, 0)
            finally:
                entrypoint._close_outbox()


class OutboxHeartbeatObservabilityTests(unittest.TestCase):
    """AC-009 / TEST-009: the six-field heartbeat marker is emitted by the real
    module, parsed by observed-worker-runner.py into six state keys, surfaced
    additively by check-worker-health.py, and schema_version stays 1."""

    PRODUCER_SCRIPT = textwrap.dedent(
        """
        import json
        import time
        from pathlib import Path
        from worker_outbox import WorkerOutbox

        snapshot = Path("event.jpg")
        snapshot.write_bytes(b"\\xff\\xd8heartbeat")
        outbox = WorkerOutbox(Path("heartbeat-outbox.sqlite3"), jitter_function=lambda: 0.0)
        outbox.enqueue(
            "evt-hb", json.dumps({"event_id": "evt-hb", "camera_id": "road1"}), snapshot
        )
        outbox.start()
        time.sleep(0.4)
        outbox.close()
        """
    )

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def emit_real_marker_line(self) -> str:
        script = self.tmp / "producer.py"
        script.write_text(self.PRODUCER_SCRIPT, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(script)],
            check=False,
            capture_output=True,
            text=True,
            cwd=self.tmp,
            timeout=30,
            env={**os.environ, "PYTHONPATH": str(ROOT / "worker")},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        marker_lines = [
            line for line in result.stdout.splitlines() if line.startswith("outbox pending=")
        ]
        self.assertTrue(marker_lines, f"no heartbeat marker emitted; stdout={result.stdout!r}")
        return marker_lines[0]

    def run_runner_with_lines(self, lines: list) -> dict:
        heartbeat = self.tmp / "worker-heartbeat.json"
        overlay = self.tmp / "latest_overlay.jpg"
        fake_worker = self.tmp / "fake_worker.py"
        printed = "\n".join(f"print({line!r}, flush=True)" for line in lines)
        fake_worker.write_text("import time\n" + printed + "\ntime.sleep(1.25)\n", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--source-commit",
                COMMIT40,
                "--heartbeat",
                str(heartbeat),
                "--overlay",
                str(overlay),
                "--heartbeat-interval-sec",
                "1",
                str(fake_worker),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(heartbeat.read_text(encoding="utf-8"))

    def test_real_marker_line_parses_into_six_runner_state_keys(self) -> None:
        """AC-009: the exact stdout line produced by worker_outbox.py (real
        subprocess) is parsed by observed-worker-runner.py into the six outbox
        state keys; schema_version stays 1."""
        marker = self.emit_real_marker_line()
        fields = dict(fragment.split("=", 1) for fragment in marker.split()[1:])
        self.assertEqual(
            sorted(fields),
            sorted(
                ["pending", "oldest", "send_errors", "retries", "accept_errors", "last_confirmed"]
            ),
            f"marker must carry the six fields: {marker!r}",
        )
        payload = self.run_runner_with_lines([marker])
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["outbox_pending"], int(fields["pending"]))
        self.assertEqual(payload["outbox_pending"], 1)
        oldest = payload["outbox_oldest_unconfirmed_sec"]
        self.assertIsInstance(oldest, float)
        self.assertGreaterEqual(oldest, 0.0)
        self.assertEqual(payload["outbox_send_errors"], int(fields["send_errors"]))
        self.assertEqual(payload["outbox_retries"], int(fields["retries"]))
        self.assertEqual(payload["outbox_accept_errors"], int(fields["accept_errors"]))
        self.assertIsNone(payload["outbox_last_confirmed_at"], "none -> null")

    def test_runner_parses_none_values_and_ignores_non_marker_outbox_lines(self) -> None:
        """AC-009: oldest/last_confirmed 'none' parse to null, and the
        'outbox send error'/'outbox accept_error'/'outbox publisher error' lines
        are no-ops that must not corrupt the six state keys."""
        marker = (
            "outbox pending=2 oldest=10.5 send_errors=5 retries=3"
            " accept_errors=1 last_confirmed=1700000000.500"
        )
        noise = [
            "outbox send error event_id=x attempt=1 content=deadbeef delay=0.5s reason=HTTP 500 x",
            "outbox accept_error event_id=x reason=HTTP 409 y",
            "outbox publisher error reason=RuntimeError",
            "outbox pending=0 oldest=none send_errors=0 retries=0"
            " accept_errors=0 last_confirmed=none",
        ]
        payload = self.run_runner_with_lines([marker] + noise)
        self.assertEqual(payload["schema_version"], 1)
        # last marker wins; noise lines changed nothing on the way
        self.assertEqual(payload["outbox_pending"], 0)
        self.assertIsNone(payload["outbox_oldest_unconfirmed_sec"])
        self.assertEqual(payload["outbox_send_errors"], 0)
        self.assertEqual(payload["outbox_retries"], 0)
        self.assertEqual(payload["outbox_accept_errors"], 0)
        self.assertIsNone(payload["outbox_last_confirmed_at"])

    def build_checker_environment(self, heartbeat_payload: dict) -> dict:
        root = self.tmp
        install_root = root / "install"
        release_root = install_root / "releases" / COMMIT40
        runtime_root = install_root / "shared/runtime"
        bin_root = root / "bin"
        report = install_root / "observability/worker-health-report.json"
        unit = root / "sea-speed-worker.service"
        heartbeat = runtime_root / "worker-heartbeat.json"
        release_root.mkdir(parents=True)
        runtime_root.mkdir(parents=True)
        bin_root.mkdir(parents=True)
        (release_root / "source-commit").write_text(COMMIT40 + "\n", encoding="utf-8")
        (release_root / "quality-approved").write_text(
            f"source_commit={COMMIT40}\nquality_check=quality-integration\n", encoding="utf-8"
        )
        (runtime_root / "active-source-commit").write_text(COMMIT40 + "\n", encoding="utf-8")
        unit.write_text(
            f"ExecStart=/venv/python observed-worker-runner.py --source-commit {COMMIT40}\n",
            encoding="utf-8",
        )
        heartbeat.write_text(json.dumps(heartbeat_payload), encoding="utf-8")
        import stat

        systemctl = bin_root / "systemctl"
        systemctl.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "if len(sys.argv) > 1 and sys.argv[1] == 'is-active':\n"
            "    raise SystemExit(0)\n"
            "if len(sys.argv) > 1 and sys.argv[1] == 'show':\n"
            f"    print('/venv/python observed-worker-runner.py --source-commit {COMMIT40}')\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(1)\n",
            encoding="utf-8",
        )
        nvidia = bin_root / "nvidia-smi"
        nvidia.write_text("#!/bin/sh\nprintf '0\\n'\n", encoding="utf-8")
        for executable in (systemctl, nvidia):
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        environment = dict(os.environ)
        environment["PATH"] = str(bin_root) + os.pathsep + environment.get("PATH", "")
        result = subprocess.run(
            [
                sys.executable,
                str(CHECKER),
                "--install-root",
                str(install_root),
                "--unit-path",
                str(unit),
                "--expected-commit",
                COMMIT40,
                "--heartbeat",
                str(heartbeat),
                "--write-report",
                str(report),
                "--min-free-gib",
                "0",
                "--require-gpu",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads(report.read_text(encoding="utf-8"))

    def base_heartbeat(self) -> dict:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        return {
            "source_commit": COMMIT40,
            "observed_at": now,
            "phase": "running",
            "frame_progress_sequence": 5,
            "last_frame_at": now,
            "last_state_post_at": now,
            "last_state_post_ok": True,
            "state_post_success_count": 5,
            "state_post_failure_count": 0,
            "event_post_success_count": 1,
        }

    def test_health_checker_surfaces_outbox_fields_additively(self) -> None:
        """AC-009: check-worker-health.py copies the six heartbeat outbox keys
        into the report (additive fields), keeps schema_version 1 and the
        overall verdict healthy; a heartbeat WITHOUT the keys still validates
        with null outbox fields (backward compatible)."""
        heartbeat = self.base_heartbeat()
        heartbeat.update(
            {
                "outbox_pending": 7,
                "outbox_oldest_unconfirmed_sec": 12.5,
                "outbox_send_errors": 3,
                "outbox_retries": 4,
                "outbox_accept_errors": 1,
                "outbox_last_confirmed_at": 1700000000.123,
            }
        )
        report = self.build_checker_environment(heartbeat)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["overall"], "healthy")
        self.assertEqual(report["outbox_pending"], 7)
        self.assertEqual(report["outbox_oldest_unconfirmed_sec"], 12.5)
        self.assertEqual(report["outbox_send_errors"], 3)
        self.assertEqual(report["outbox_retries"], 4)
        self.assertEqual(report["outbox_accept_errors"], 1)
        self.assertEqual(report["outbox_last_confirmed_at"], 1700000000.123)

    def test_health_checker_without_outbox_keys_stays_compatible(self) -> None:
        """AC-009: additive-only contract — an old-shape heartbeat (no outbox
        keys) still produces a healthy report with null outbox fields and
        schema_version 1."""
        report = self.build_checker_environment(self.base_heartbeat())
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["overall"], "healthy")
        for key in (
            "outbox_pending",
            "outbox_oldest_unconfirmed_sec",
            "outbox_send_errors",
            "outbox_retries",
            "outbox_accept_errors",
            "outbox_last_confirmed_at",
        ):
            self.assertIsNone(report[key], f"{key} must default to null, not crash")


class OutboxConvergencePinTests(unittest.TestCase):
    """AC-010 / AC-011 (TEST-010, TEST-011): convergence-list pins in the
    pin-test style of the five worker module suites."""

    def test_compatibility_gate_union_includes_outbox_with_nine_sources(self) -> None:
        """AC-010 / D-101: MODULE_SOURCES is the nine-file union including
        worker/worker_outbox.py and the gate stays compatible."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ubuntu_worker_compatibility_537w2", COMPATIBILITY
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(len(module.MODULE_SOURCES), 9)
        self.assertIn(ROOT / "worker" / "worker_outbox.py", list(module.MODULE_SOURCES))
        findings = module.inspect_worker(list(module.MODULE_SOURCES))
        self.assertTrue(findings["compatible"], findings)

    def test_installer_and_artifact_lists_include_worker_outbox(self) -> None:
        """AC-011 / D-108: the fail-closed installer/artifact lists gained
        worker/worker_outbox.py together — source-text pins."""
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('"$source_root/worker/worker_outbox.py"', installer)
        builder = BUILD_ARTIFACTS.read_text(encoding="utf-8")
        self.assertIn('"worker/worker_outbox.py"', builder)
        validator = VALIDATE_ARTIFACTS.read_text(encoding="utf-8")
        self.assertIn('"worker/worker_outbox.py"', validator)
        repo_validator = VALIDATE_REPO.read_text(encoding="utf-8")
        self.assertIn('"worker/worker_outbox.py"', repo_validator)


if __name__ == "__main__":
    unittest.main()
