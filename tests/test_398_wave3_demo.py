"""Issue #398 wave 3 demo: executed shell twins vs raw source-text pins.

Target check: the converted reader-ip forwarding contract for
deploy/worker/ubuntu/camera-relay.sh (executed via tests/support/relay_shell.py:
the REAL script bytes run from a copy tree with a recording renderer stub, and
the check asserts the renderer received EVERY accumulated --reader-ip
occurrence in input order — the #372 contract the wave retired from text).

Two-direction proof, mirroring the wave-1/wave-2 demos:

- Direction A (refactor tolerance): a tmp copy of the real script whose
  accumulation idioms are rewritten behavior-preservingly (fused `read -ra`,
  indexed assignment instead of `+=`, two-string forwarding pair) still
  satisfies the EXECUTED check, while the retired raw-text pins
  (``IFS=',' read -r -a __reader_ip_parts``,
  ``reader_ips+=("$__reader_ip_part")``,
  ``reader_ip_args+=(--reader-ip "$reader_ip")``) would fail on it.
- Direction B (dead-marker intolerance): a tmp copy that keeps every retired
  marker verbatim but breaks the wiring (the forwarding loop's result is
  truncated to the first reader pair) passes the retired text pins and FAILS
  the executed check.

Both directions run against tmp copies only; deploy/ is never modified.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.support import relay_shell

CAMERA_RELAY = ROOT / "deploy/worker/ubuntu/camera-relay.sh"

RETIRED_TEXT_PINS = (
    "IFS=',' read -r -a __reader_ip_parts",
    'reader_ips+=("$__reader_ip_part")',
    'reader_ip_args+=(--reader-ip "$reader_ip")',
)

READER_IP_A = "10.123.239.101"
READER_IP_B = "10.123.239.102"


def _refactored_script(source: str) -> str:
    """Rewrite the accumulation idioms; identical parse/forward behavior."""
    source = source.replace(
        "IFS=',' read -r -a __reader_ip_parts <<< \"$2\"",
        "IFS=',' read -ra __reader_ip_parts <<<\"$2\"",
    )
    source = source.replace(
        'reader_ips+=("$__reader_ip_part")',
        'reader_ips[${#reader_ips[@]}]="$__reader_ip_part"',
    )
    source = source.replace(
        'reader_ip_args+=(--reader-ip "$reader_ip")',
        'reader_ip_args+=("--reader-ip" "$reader_ip")',
    )
    return source


def _marker_only_broken_script(source: str) -> str:
    """Keep ALL retired marker text verbatim but break the forwarding.

    An interceptor right after the (verbatim) forwarding loop truncates the
    forwarded pairs to the first reader IP. The retired text pins pass — every
    marker survives byte-for-byte — while the executed check fails because the
    second reader IP never reaches the renderer.
    """
    anchor = 'for reader_ip in "${reader_ips[@]}"; do\n  reader_ip_args+=(--reader-ip "$reader_ip")\ndone'
    replacement = (
        anchor
        + '\n  # demo interceptor: break forwarding while keeping every marker\n'
        + '  reader_ip_args=("${reader_ip_args[0]}" "${reader_ip_args[1]}")'
    )
    assert anchor in source, "forwarding loop anchor changed; demo needs an update"
    return source.replace(anchor, replacement, 1)


def _run_executed_forwarding_check(script_text: str, tmp: Path) -> tuple[bool, str]:
    """Run the converted behavioral check against a script copy.

    Copy-tree layout so the script resolves tmp as its repo root; the
    recording renderer stub answers every renderer mode and logs its argv.
    The check passes iff the prepare flow forwarded BOTH reader IPs, in input
    order, to the renderer invocation.
    """
    tree = tmp / "isolated"
    target = tree / "deploy" / "worker" / "ubuntu"
    target.mkdir(parents=True, exist_ok=True)
    (tree / "scripts" / "operations").mkdir(parents=True, exist_ok=True)
    # The renderer gate requires the renderer FILE to exist at the resolved
    # repo path; the recording stub rides PATH as `python3`, so a placeholder
    # file satisfies the gate while every renderer invocation is recorded.
    (tree / "scripts" / "operations" / "mediamtx_path_config.py").write_text(
        "# demo placeholder: the recording renderer stub is on PATH as python3\n",
        encoding="utf-8",
    )
    copied = target / CAMERA_RELAY.name
    copied.write_text(script_text, encoding="utf-8")
    copied.chmod(0o755)
    # Each check run observes ONLY its own invocation (the tmp tree is reused
    # across demo directions; the recorder appends).
    args_log = tmp / "renderer-args.log"
    args_log.unlink(missing_ok=True)

    config = tmp / "mediamtx.yml"
    config.write_text("logLevel: info\npaths:\n  cam1:\n", encoding="utf-8")
    env_file = tmp / "worker.env"
    env_file.write_text("HLS_URL=rtsp://camera_user:camera_key@10.0.0.21/live\n", encoding="utf-8")
    env_file.chmod(0o600)

    result = relay_shell.run_shell(
        copied,
        [
            "prepare",
            "--config", str(config),
            "--private-rtsp-address", "10.0.0.8:8554",
            "--reader-ip", READER_IP_A,
            "--reader-ip", READER_IP_B,
            "--source-env-file", str(env_file),
            "--state-root", str(tmp / "state"),
        ],
        tmp,
        env_extra=relay_shell.recording_renderer_env(args_log),
    )
    if result.returncode != 0:
        return False, f"prepare exited {result.returncode}: {result.stderr[-300:]}"
    if not args_log.exists():
        return False, "the renderer stub was never invoked"
    forwarded = args_log.read_text(encoding="utf-8")
    marker_a = f"--reader-ip {READER_IP_A}"
    marker_b = f"--reader-ip {READER_IP_B}"
    if marker_a not in forwarded or marker_b not in forwarded:
        return False, f"renderer did not receive both reader IPs: {forwarded}"
    if forwarded.index(marker_a) > forwarded.index(marker_b):
        return False, f"reader IPs were reordered: {forwarded}"
    return True, ""


def _run_retired_text_pins(script_text: str) -> tuple[bool, list[str]]:
    """Run the RETIRED raw-text pins against a script copy (demo only)."""
    failed = [marker for marker in RETIRED_TEXT_PINS if marker not in script_text]
    return (not failed), failed


class Test398Wave3Demo(unittest.TestCase):
    def test_refactor_tolerance_and_dead_marker_intolerance(self) -> None:
        # The executed checks run the real script under a user namespace.
        relay_shell.skip_without_user_namespace(self)
        real_script = CAMERA_RELAY.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            # Direction A: behavior-preserving refactor.
            refactored_ok, refactored_error = _run_executed_forwarding_check(
                _refactored_script(real_script), tmp
            )
            retired_ok, retired_failed = _run_retired_text_pins(
                _refactored_script(real_script)
            )
            self.assertTrue(
                refactored_ok,
                f"executed check must tolerate a pure refactor: {refactored_error}",
            )
            self.assertFalse(
                retired_ok,
                f"retired text pins would fail the refactor (expected): {retired_failed}",
            )
            # Direction B: markers kept, wiring broken.
            broken_script = _marker_only_broken_script(real_script)
            broken_ok, broken_error = _run_executed_forwarding_check(broken_script, tmp)
            broken_retired_ok, _ = _run_retired_text_pins(broken_script)
            self.assertFalse(
                broken_ok,
                "executed check must fail a script whose forwarding is broken "
                f"despite intact marker text: {broken_error}",
            )
            self.assertTrue(
                broken_retired_ok,
                "retired text pins pass the marker-only script (the false-green "
                "the conversion removes)",
            )
            # Sanity: the real script satisfies the executed check (copy-tree,
            # recording renderer — no repo mutation).
            real_ok, real_error = _run_executed_forwarding_check(real_script, tmp)
            self.assertTrue(real_ok, f"real script must satisfy the executed check: {real_error}")


if __name__ == "__main__":
    unittest.main()
