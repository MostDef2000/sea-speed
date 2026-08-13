from __future__ import annotations

import ipaddress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOVER = ROOT / "deploy/vps/sea-speed-auth-cutover.sh"


def test_ipv4_mapped_ipv6_classification() -> None:
    mapped = ipaddress.ip_address("::ffff:82.146.37.153")
    native = ipaddress.ip_address("2001:db8::1")
    assert mapped.ipv4_mapped == ipaddress.ip_address("82.146.37.153")
    assert native.ipv4_mapped is None


def test_public_dns_verifier_keeps_native_ipv6_fail_closed() -> None:
    source = CUTOVER.read_text(encoding="utf-8")
    assert 'getent ahostsv4 "$auth_public_host"' in source
    assert 'getent ahostsv6 "$auth_public_host"' in source
    assert "address.ipv4_mapped is None" in source
    assert "real_ipv6.append(str(address))" in source
    assert "has IPv6 DNS but bootstrap-public has no approved IPv6 ingress" in source
