from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_execution_cursor_protocol_exists():
    protocol = ROOT / "contracts" / "runtime" / "EXECUTION_CURSOR_PROTOCOL.md"
    assert protocol.exists()

    text = protocol.read_text(encoding="utf-8")

    required = (
        "EXECUTION_LOCKED",
        "execution_cursor",
        "Next admissible action",
        "DONE",
        "BLOCKED",
        "HUMAN DECISION REQUIRED",
    )

    for marker in required:
        assert marker in text


def test_approved_execution_requires_progress_not_status_only():
    text = (ROOT / "contracts" / "runtime" / "EXECUTION_CURSOR_PROTOCOL.md").read_text(
        encoding="utf-8"
    )

    assert "IMPLEMENTING -> STATUS REPORT ONLY" in text
    assert "IMPLEMENTING -> EXECUTE" not in text or "EXECUTION" in text
