from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "deploy/worker/ubuntu/authentik/stage.sh"
COMPOSE = ROOT / "deploy/worker/ubuntu/authentik/compose.yml"


def test_authentik_bind_mount_permissions_are_source_managed() -> None:
    # Regression coverage for non-root Authentik bind-mount ownership.
    stage = STAGE.read_text(encoding="utf-8")
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "./data:/data" in compose
    assert "./custom-templates:/templates" in compose
    assert "-o 1000 -g 1000 -m 0700" in stage
    assert '"$runtime_root/data"' in stage
    assert '"$runtime_root/custom-templates"' in stage
