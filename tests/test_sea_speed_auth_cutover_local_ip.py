from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOVER = ROOT / "deploy/vps/sea-speed-auth-cutover.sh"


class SeaSpeedAuthCutoverLocalIpTests(unittest.TestCase):
    def test_local_ipv4_predicate_is_pipefail_safe_and_exact(self) -> None:
        source = CUTOVER.read_text(encoding="utf-8")
        match = re.search(r"(?ms)^ipv4_is_local\(\) \{.*?^\}", source)
        self.assertIsNotNone(match)
        helper = match.group(0)

        script = f'''\
set -euo pipefail
{helper}

ip() {{
  printf '%s\\n' \
    '1: lo    inet 127.0.0.1/8 scope host lo' \
    '2: zt0   inet 10.123.239.101/24 brd 10.123.239.255 scope global zt0'
  i=0
  while [ "$i" -lt 12000 ]; do
    printf '3: dummy%s    inet 10.200.%s.%s/32 scope global dummy%s\\n' \
      "$i" "$((i % 250))" "$((i % 251))" "$i"
    i=$((i + 1))
  done
}}

ipv4_is_local 10.123.239.101
if ipv4_is_local 10.123.239.10; then
  echo 'substring match must not pass' >&2
  exit 41
fi
if ipv4_is_local 10.123.239.103; then
  echo 'non-local address must not pass' >&2
  exit 42
fi
'''
        subprocess.run(["bash", "-c", script], check=True, text=True, capture_output=True)

    def test_cutover_uses_shared_predicate_for_both_security_checks(self) -> None:
        subprocess.run(["bash", "-n", str(CUTOVER)], check=True)
        source = CUTOVER.read_text(encoding="utf-8")

        self.assertIn('if ipv4_is_local "$host"; then', source)
        self.assertIn('ipv4_is_local "$listen_ip" || {', source)
        self.assertNotIn('grep -Fq " ${host}/"', source)
        self.assertNotIn('grep -Fq " ${listen_ip}/"', source)
        self.assertIn('split($4, parts, "/")', source)
        self.assertIn('parts[1] == needle', source)


if __name__ == "__main__":
    unittest.main()
