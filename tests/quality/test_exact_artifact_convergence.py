"""D-6 (#396 follow-up): exact-artifact convergence is bidirectional.

The vps required list in scripts/quality/build_exact_artifacts.py and the
api/app module mirror sites (<NAME>_TARGET variables) in deploy/vps/deploy.sh
must stay equal in BOTH directions. Before D-6 the exact-artifact validator
checked only the artifact-inventory side: a module added to one side without
the other passed validation and surfaced only at deploy time (or never).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "0123456789abcdef0123456789abcdef01234567"
sys.path.insert(0, str(ROOT))

from scripts.quality.build_exact_artifacts import COMPONENT_FILES  # noqa: E402
from scripts.quality.validate_exact_artifacts import (  # noqa: E402
    deploy_app_module_targets,
    validate_vps_module_convergence,
)

DEPLOY_SH = ROOT / "deploy/vps/deploy.sh"
VALIDATOR = ROOT / "scripts/quality/validate_exact_artifacts.py"


def vps_required_app_modules() -> set[str]:
    return {p for p in COMPONENT_FILES["vps"]["required"] if p.startswith("api/app/")}


class ExactArtifactConvergenceTests(unittest.TestCase):
    def test_real_repo_converges_in_both_directions(self) -> None:
        text = DEPLOY_SH.read_text(encoding="utf-8")
        mirrored = deploy_app_module_targets(text)
        required = vps_required_app_modules()
        self.assertEqual(
            len(mirrored), 10, f"unexpected api/app TARGET mirror set: {sorted(mirrored)}"
        )
        self.assertEqual(mirrored, required)

    def test_deploy_targets_parser_ignores_non_python_targets(self) -> None:
        text = DEPLOY_SH.read_text(encoding="utf-8")
        mirrored = deploy_app_module_targets(text)
        self.assertFalse(any(p.endswith((".html", ".js")) for p in mirrored))
        self.assertIn("api/app/main.py", mirrored)
        self.assertIn("api/app/live_feeds.py", mirrored)

    def test_direction_a_build_module_without_deploy_mirror_fails_closed(self) -> None:
        text = DEPLOY_SH.read_text(encoding="utf-8")
        required = vps_required_app_modules() | {"api/app/ghost_module.py"}
        with self.assertRaises(SystemExit) as ctx:
            validate_vps_module_convergence(required, text)
        self.assertIn("not mirrored", str(ctx.exception))
        self.assertIn("api/app/ghost_module.py", str(ctx.exception))

    def test_direction_b_deploy_target_without_build_entry_fails_closed(self) -> None:
        text = DEPLOY_SH.read_text(encoding="utf-8")
        mutated = text.replace(
            'LIVE_FEEDS_TARGET="$(dirname "$API_TARGET")/live_feeds.py"',
            'LIVE_FEEDS_TARGET="$(dirname "$API_TARGET")/live_feeds.py"\n'
            'GHOST_TARGET="$(dirname "$API_TARGET")/ghost_module.py"',
            1,
        )
        self.assertIn("GHOST_TARGET", mutated)
        with self.assertRaises(SystemExit) as ctx:
            validate_vps_module_convergence(vps_required_app_modules(), mutated)
        self.assertIn("missing from", str(ctx.exception))
        self.assertIn("api/app/ghost_module.py", str(ctx.exception))

    def test_validator_end_to_end_and_check_is_wired(self) -> None:
        source = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn("validate_vps_module_convergence", source)
        self.assertIn("deploy_app_module_targets", source)
        with tempfile.TemporaryDirectory() as temp_dir:
            out = Path(temp_dir)
            subprocess.run(
                [sys.executable, "scripts/quality/build_exact_artifacts.py",
                 "--source-commit", COMMIT, "--output-dir", str(out)],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            subprocess.run(
                [sys.executable, "scripts/quality/validate_exact_artifacts.py",
                 "--manifest", str(out / "exact-artifacts.json")],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            manifest = json.loads((out / "exact-artifacts.json").read_text(encoding="utf-8"))
            vps = next(a for a in manifest["artifacts"] if a["component"] == "vps")
            shipped = {f["path"] for f in vps["files"] if f["path"].startswith("api/app/")}
            self.assertEqual(shipped, vps_required_app_modules())
            self.assertEqual(shipped, deploy_app_module_targets(DEPLOY_SH.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
