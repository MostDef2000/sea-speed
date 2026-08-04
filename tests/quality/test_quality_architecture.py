from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "0123456789abcdef0123456789abcdef01234567"


class QualityArchitectureTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )

    def test_contracts_properties_fuzz_and_workflow_policy(self) -> None:
        for command in (
            ("scripts/quality/validate_quality_contracts.py",),
            ("scripts/quality/validate_workflow_policy.py",),
            ("scripts/quality/test_properties.py",),
            ("scripts/quality/test_fuzz_recovery.py",),
        ):
            result = self.run_script(*command)
            self.assertIn("passed" if "test_" in command[0] else "valid", result.stdout.lower())

    def test_exact_artifacts_are_deterministic_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(first))
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(second))
            for component in ("vps", "edge"):
                filename = f"sea-speed-{component}-{COMMIT}.tar.gz"
                self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())
            self.assertEqual((first / "exact-artifacts.json").read_bytes(), (second / "exact-artifacts.json").read_bytes())
            self.run_script("scripts/quality/validate_exact_artifacts.py", "--manifest", str(first / "exact-artifacts.json"))

    def test_quality_evidence_binds_artifact_digests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exact = Path(temp_dir) / "exact"
            evidence = Path(temp_dir) / "quality-evidence.json"
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(exact))
            self.run_script(
                "scripts/quality/build_quality_evidence.py",
                "--source-commit", COMMIT,
                "--artifacts-manifest", str(exact / "exact-artifacts.json"),
                "--output", str(evidence),
            )
            self.run_script(
                "scripts/quality/validate_quality_evidence.py",
                "--evidence", str(evidence),
                "--artifacts-manifest", str(exact / "exact-artifacts.json"),
            )
            data = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(data["source_commit"], COMMIT)
            self.assertFalse(data["deployment"]["automatic_from_main"])
            self.assertEqual(data["contracts"]["target_media_mode"], "edge_v2")


if __name__ == "__main__":
    unittest.main()
