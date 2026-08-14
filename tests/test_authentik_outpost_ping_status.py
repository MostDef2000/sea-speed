from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CUTOVER = ROOT / "deploy/vps/sea-speed-auth-cutover.sh"


def test_authentik_outpost_ping_requires_canonical_204() -> None:
    # Authentik Forward Auth documents HTTP 204 as the healthy ping response.
    source = CUTOVER.read_text(encoding="utf-8")

    assert '[[ "$outpost_status" == "204" ]]' in source
    assert "Authentik outpost ping expected 204" in source
    assert '[[ "$outpost_status" == "200" ]]' not in source
    assert "Authentik outpost ping expected 200" not in source
