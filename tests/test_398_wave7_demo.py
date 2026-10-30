"""Issue #398 wave 7 demo: the parsed-structure twins PROTECT the preview
profile contract in both directions (two-direction regression demonstration).

The wave-7 conversion retired the raw substring pins on the RENDERED preview
config (PreviewProfileContractTests in tests/test_mediamtx_preview_relay.py)
in favor of yaml.safe_load parsed twins. This demo proves the conversion
property on tmp copies of the real canonical render (the renderer CLI runs
for real; repo files are never modified — every mutation lands in a
TemporaryDirectory copy):

- Direction A (retired-pin protection carried by the twin): mutating
  `api: false` -> `api: yes` breaks the API-less contract; the parsed twin
  REJECTS the mutated config. The retired `api: yes` substring ban caught
  this drift too — the twin carries the same protection, formatting-
  insensitive. The inversion is asserted in-demo on the twin's verdict
  (twin(canonical) passes, twin(mutated) reports exactly the api-off
  violation) — the demo asserts the twin function's verdict, not a pytest
  subprocess.

- Direction B (the twin ADDS protection): mutating `srt: false` -> `srt: yes`
  leaves EVERY retired substring pin green (srt was unpinned by the old
  5-key loop and the api pins do not mention srt) — the old false-green —
  while the parsed twin REJECTS the mutated config via the strengthened
  FULL 9-key off-set (rtmp/hls/webrtc/srt/api/metrics/pprof/playback/moq
  all exactly False + rtsp exactly True).

Honest class-split note (recorded trade, proven in Direction A): the old
substring pins were FORMATTING-SENSITIVE — a render like `api:  false`
(double space) fails the retired `api: false\\n` byte pin while passing the
parsed twin (which asserts the boolean value, not the bytes). The twins are
comment-blind and formatting-insensitive by design; the byte-level contract
stays pinned by the untouched parity oracle (LEGACY_SINGLE_CAMERA_CONFIG
exact equality) and the SP-kept marker pin.

Manual flip-run evidence (recorded in tasks.md): flipping each direction's
mutation OFF (mutated = canonical) makes the corresponding direction RED with
the inverted verdict — in Direction A the retired-pin assertion fires FIRST
(`AssertionError: True is not false`: the retired api: yes ban passes the
unmutated bytes) before the twin-rejection assertion is reached, while in
Direction B the twin-rejection assertion fires with the retired-pin
assertions staying green; both restores are byte-identical and the focused
runs are green again.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/mediamtx_path_config.py"

_spec = importlib.util.spec_from_file_location("mediamtx_path_config", RENDERER)
mediamtx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mediamtx)

READER_IP = "10.123.239.101"
PRIVATE_ADDRESS = "10.0.0.8:8555"
# Runtime-assembled (never a literal credential shape in this file).
SOURCE_ROAD = "rtsp://" + "preview_user" + ":" + "preview_key" + "@10.0.0.31:554/road-stream"

# The strengthened FULL off-set (9 unused default servers) and the old
# loop's 5-key subset (the wave-7 strengthening delta).
FULL_OFF_SET = ("rtmp", "hls", "webrtc", "srt", "api", "metrics", "pprof", "playback", "moq")
OLD_LOOP_KEYS = ("api", "metrics", "pprof", "playback", "moq")

# The retired raw substring pins of PreviewProfileContractTests, restated
# verbatim (L345/L346/L349 api pins; L362-363 loop; L364 rtsp pin). The
# marker-line pin is SP-KEPT in the owning test (comment — dropped by
# yaml.safe_load) and is deliberately NOT restated here.
RETIRED_PINS = {
    "L345 api: yes ban": lambda text: "api: yes" not in text,
    "L346 apiAddress ban": lambda text: "apiAddress" not in text,
    "L349 api: false presence": lambda text: "api: false\n" in text,
    "L362-363 5-key off loop": lambda text: all(f"{key}: false\n" in text for key in OLD_LOOP_KEYS),
    "L364 rtsp: true presence": lambda text: "rtsp: true\n" in text,
}


def _render_canonical_preview_config() -> str:
    """Run the REAL renderer CLI for a one-camera inventory (tmp only)."""
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        inventory = root / "inventory.json"
        inventory.write_text(
            json.dumps(
                {
                    "schema": "sea_speed_camera_preview_inventory_v1",
                    "cameras": [
                        {
                            "camera_id": "road1",
                            "display_name": "Road worker preview",
                            "source": SOURCE_ROAD,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        inventory.chmod(0o600)
        config_out = root / "mediamtx.yml"
        result = subprocess.run(
            [
                sys.executable, str(RENDERER), "ubuntu-preview-relay",
                "--inventory", str(inventory),
                "--config-output", str(config_out),
                "--catalog-output", str(root / "camera-preview-catalog.json"),
                "--private-rtsp-address", PRIVATE_ADDRESS,
                "--reader-ip", READER_IP,
            ],
            text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        return config_out.read_text(encoding="utf-8")


def _mutated_copy(config_text: str, old: str, new: str) -> str:
    """Apply one mutation to a tmp copy of the rendered config (never repo files)."""
    assert config_text.count(old) == 1, f"mutation needle not unique: {old!r}"
    mutated = config_text.replace(old, new)
    with tempfile.TemporaryDirectory() as raw:
        copy = Path(raw) / "mutated-mediamtx.yml"
        copy.write_text(mutated, encoding="utf-8")
        return copy.read_text(encoding="utf-8")


def _preview_profile_twin(config_text: str) -> list[str]:
    """The wave-7 parsed twin (restated from PreviewProfileContractTests).

    Returns the list of twin violations; empty == the twin passes.
    """
    parsed = yaml.safe_load(config_text)
    failures: list[str] = []
    for key in FULL_OFF_SET:
        if parsed.get(key) is not False:
            failures.append(f"server-off twin: {key} must be exactly False, got {parsed.get(key)!r}")
    if parsed.get("rtsp") is not True:
        failures.append(f"rtsp twin: must be exactly True, got {parsed.get('rtsp')!r}")

    def walk_keys(node: object) -> list[str]:
        if isinstance(node, dict):
            keys: list[str] = []
            for key, value in node.items():
                if isinstance(key, str):
                    keys.append(key)
                keys.extend(walk_keys(key))
                keys.extend(walk_keys(value))
            return keys
        if isinstance(node, (list, tuple)):
            keys = []
            for item in node:
                keys.extend(walk_keys(item))
            return keys
        return []

    if "apiAddress" in walk_keys(parsed):
        failures.append("api-less twin: apiAddress key must be absent")
    return failures


class Wave7PreviewProfileDemo(unittest.TestCase):
    def test_direction_a_twin_carries_the_retired_api_pins_protection(self) -> None:
        # Direction A: api: false -> api: yes must make the parsed twin FAIL.
        # Manual flip-run evidence (tasks.md): with the mutation OFF
        # (mutated = canonical) the RETIRED-PIN assertion below goes RED
        # FIRST (`AssertionError: True is not false` — the retired api: yes
        # ban passes the unmutated bytes) before the twin-rejection assertion
        # is reached; restore is byte-identical and the focused run is green
        # again.
        canonical = _render_canonical_preview_config()
        # Sanity: the canonical render satisfies the twin AND every retired pin.
        self.assertEqual(_preview_profile_twin(canonical), [])
        for name, holds in RETIRED_PINS.items():
            self.assertTrue(holds(canonical), name)
        # The mutation on a tmp copy: api: false -> api: yes.
        mutated = _mutated_copy(canonical, "api: false\n", "api: yes\n")
        # The retired api: yes ban fails on the mutated text (the old pin
        # caught this drift too) — the twin must carry the same protection.
        self.assertFalse(RETIRED_PINS["L345 api: yes ban"](mutated))
        # Self-proving inversion, asserted on the twin's verdict (no pytest
        # subprocess): twin(canonical) passes, twin(mutated) rejects with
        # exactly the api-off violation.
        self.assertEqual(_preview_profile_twin(canonical), [])
        self.assertEqual(
            _preview_profile_twin(mutated),
            ["server-off twin: api must be exactly False, got True"],
        )
        # Documented class-split trade, proven: a formatting-only drift
        # (`api:  false`, double space) FAILS the retired byte pin but PASSES
        # the parsed twin (the boolean value is unchanged; the byte-level
        # contract stays with the untouched parity oracle).
        reformatted = _mutated_copy(canonical, "api: false\n", "api:  false\n")
        self.assertFalse(RETIRED_PINS["L349 api: false presence"](reformatted))
        self.assertEqual(_preview_profile_twin(reformatted), [])

    def test_direction_b_twin_adds_protection_the_retired_pins_lacked(self) -> None:
        # Direction B: srt: false -> srt: yes passes ALL retired-pin
        # equivalents while the parsed twin rejects it. Manual flip-run
        # evidence (tasks.md): with the mutation OFF (mutated = canonical)
        # the twin-rejection assertion below goes RED with the inverted
        # verdict (twin(canonical) == []) while the retired-pin assertions
        # stay green; restore is byte-identical and the focused run is green.
        canonical = _render_canonical_preview_config()
        # The mutation on a tmp copy: srt: false -> srt: yes.
        mutated = _mutated_copy(canonical, "srt: false\n", "srt: yes\n")
        # ALL retired substring pins hold on the mutated text — the old
        # false-green (srt was unpinned by the old 5-key loop; the api pins
        # do not mention srt; rtsp is untouched), asserted pin by pin.
        verdicts = {name: holds(mutated) for name, holds in RETIRED_PINS.items()}
        self.assertEqual(verdicts, {name: True for name in RETIRED_PINS})
        # The parsed twin REJECTS what every retired pin accepted — via the
        # strengthened FULL 9-key off-set (exactly the srt violation).
        self.assertEqual(
            _preview_profile_twin(mutated),
            ["server-off twin: srt must be exactly False, got True"],
        )
        # And the canonical render passes the twin (the verdict is
        # mutation-sensitive, not a constant).
        self.assertEqual(_preview_profile_twin(canonical), [])


if __name__ == "__main__":
    unittest.main()
