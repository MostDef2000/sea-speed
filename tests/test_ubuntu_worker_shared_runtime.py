from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "deploy/worker/ubuntu/prepare-runtime.sh"
LOCK = ROOT / "deploy/worker/ubuntu/runtime-lock.json"
REQUIREMENTS = ROOT / "deploy/worker/ubuntu/requirements-runtime.txt"


class UbuntuWorkerSharedRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = PREPARE.read_text(encoding="utf-8")
        self.lock = json.loads(LOCK.read_text(encoding="utf-8"))

    def test_shell_syntax_is_valid(self) -> None:
        subprocess.run(["bash", "-n", str(PREPARE)], check=True)

    def test_runtime_lock_pins_python_and_cuda_pair(self) -> None:
        self.assertEqual(self.lock["schema_version"], 1)
        self.assertEqual(
            self.lock["python"],
            {"implementation": "CPython", "major": 3, "minor": 14},
        )
        self.assertEqual(
            self.lock["pytorch"]["index_url"],
            "https://download.pytorch.org/whl/cu130",
        )
        self.assertEqual(
            self.lock["pytorch"]["packages"],
            {"torch": "2.13.0+cu130", "torchvision": "0.28.0+cu130"},
        )
        self.assertEqual(self.lock["runtime_requirements"], "requirements-runtime.txt")

    def test_runtime_id_is_exact_definition_fingerprint(self) -> None:
        expected = hashlib.sha256(
            LOCK.read_bytes() + b"\0" + REQUIREMENTS.read_bytes()
        ).hexdigest()
        result = subprocess.run(
            ["bash", str(PREPARE), "--runtime-id-only"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), expected)
        self.assertRegex(expected, r"^[0-9a-f]{64}$")

    def test_ready_runtime_is_reused_before_any_pip_path(self) -> None:
        reuse = self.source.index("RUNTIME_REUSED runtime_id=")
        first_pip = self.source.index("-m pip install")
        self.assertLess(reuse, first_pip)
        self.assertIn('[[ -f "$runtime_root/ready" ]]', self.source)
        self.assertIn('cmp -s "$lock_path" "$runtime_root/runtime-lock.json"', self.source)
        self.assertIn("PASS shared_runtime_imports_and_versions", self.source)

    def test_legacy_migration_adopts_local_bytes_without_network_fallback(self) -> None:
        self.assertIn('active_release/venv', self.source)
        self.assertIn("--reflink=auto", self.source)
        self.assertIn("RUNTIME_ADOPTED runtime_id=", self.source)
        self.assertIn("network_download=false", self.source)
        self.assertIn("legacy migration cannot safely adopt a matching local runtime", self.source)
        self.assertIn("RUNTIME_NETWORK_FALLBACK_BLOCKED", self.source)
        adoption = self.source.index("RUNTIME_ADOPTED runtime_id=")
        blocked = self.source.index("RUNTIME_NETWORK_FALLBACK_BLOCKED")
        first_pip = self.source.index("-m pip install")
        self.assertLess(adoption, first_pip)
        self.assertLess(blocked, first_pip)

    def test_new_runtime_uses_persistent_cache_and_atomic_ready_marker(self) -> None:
        self.assertIn('wheel_cache="$install_root/cache/wheels"', self.source)
        self.assertIn('PIP_CACHE_DIR="$wheel_cache"', self.source)
        self.assertIn("RUNTIME_CREATED runtime_id=", self.source)
        self.assertIn('runtime_parent/.prepare.$runtime_id.XXXXXX', self.source)
        self.assertIn("runtime-manifest.json", self.source)
        self.assertIn("requirements-runtime.txt", self.source)
        self.assertIn('printf \'runtime_id=%s\\n\' "$runtime_id" > "$staged_root/ready"', self.source)
        self.assertIn('mv "$staged_root" "$runtime_root"', self.source)
        ready_write = self.source.index('> "$staged_root/ready"')
        publish = self.source.index('mv "$staged_root" "$runtime_root"')
        self.assertLess(ready_write, publish)

    def test_ready_runtime_is_made_non_writable(self) -> None:
        self.assertIn('chmod -R a-w "$staged_root/venv"', self.source)
        self.assertIn('chmod 0555 "$staged_root"', self.source)
        self.assertIn("PYTHONDONTWRITEBYTECODE", (ROOT / "deploy/worker/ubuntu/sea-speed-worker.service.template").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
