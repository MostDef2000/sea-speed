from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTENDS = (
    ROOT / "frontend/sea-speed/index.html",
    ROOT / "frontend/sea-speed/cameras/index.html",
    ROOT / "frontend/sea-speed/objects/index.html",
)
LOGOUT_BLUEPRINT = ROOT / "deploy/vps/authentik/blueprints/sea-speed-logout-v1.yaml"
ROLLBACK_BLUEPRINT = ROOT / "deploy/vps/authentik/blueprints/sea-speed-logout-rollback-v1.yaml"
WORKER_OPERATION = ROOT / "deploy/worker/ubuntu/authentik/apply-logout-flow.sh"


class AuthLogoutContractTests(unittest.TestCase):
    def test_frontends_preserve_provider_logout_and_watch_trusted_session(self) -> None:
        for path in FRONTENDS:
            with self.subTest(path=path.relative_to(ROOT)):
                source = path.read_text(encoding="utf-8-sig")
                self.assertIn('href="/outpost.goauthentik.io/sign_out"', source)
                self.assertIn('const SESSION_WATCHDOG_MS=15000;', source)
                self.assertIn('sessionIdentityEstablished', source)
                self.assertIn('window.top.location.replace(protectedUrl)', source)
                self.assertIn('window.location.pathname+window.location.search+window.location.hash', source)
                self.assertIn('setInterval(()=>void loadSessionIdentity(),SESSION_WATCHDOG_MS)', source)
                self.assertNotIn("localStorage", source)
                self.assertNotIn("sessionStorage", source)

    def test_sea_speed_specific_invalidation_flow_ends_browser_session_and_redirects_root(self) -> None:
        source = LOGOUT_BLUEPRINT.read_text(encoding="utf-8")
        self.assertIn("slug: sea-speed-provider-invalidation", source)
        self.assertIn("designation: invalidation", source)
        self.assertIn("model: authentik_stages_user_logout.userlogoutstage", source)
        self.assertIn("model: authentik_stages_redirect.redirectstage", source)
        self.assertIn("mode: static", source)
        self.assertIn("target_static: https://mostdef.ru/", source)
        self.assertIn("name: Provider for Sea Speed", source)
        self.assertIn("invalidation_flow: !KeyOf sea-speed-invalidation-flow", source)
        self.assertNotIn("slug: default-provider-invalidation-flow", source)
        self.assertNotIn(
            "invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]",
            source,
        )

    def test_logout_flow_stage_order_is_user_logout_then_redirect(self) -> None:
        source = LOGOUT_BLUEPRINT.read_text(encoding="utf-8")
        logout_binding = source.index("stage: !KeyOf sea-speed-user-logout")
        redirect_binding = source.index("stage: !KeyOf sea-speed-logout-redirect")
        self.assertLess(logout_binding, redirect_binding)
        self.assertIn("order: 10", source[logout_binding : logout_binding + 100])
        self.assertIn("order: 20", source[redirect_binding : redirect_binding + 100])

    def test_rollback_blueprint_restores_only_sea_speed_provider_to_default(self) -> None:
        source = ROLLBACK_BLUEPRINT.read_text(encoding="utf-8")
        self.assertIn("name: Provider for Sea Speed", source)
        self.assertIn(
            "invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]",
            source,
        )
        self.assertNotIn("model: authentik_stages_user_logout.userlogoutstage", source)
        self.assertNotIn("model: authentik_stages_redirect.redirectstage", source)
        self.assertNotIn("target_static:", source)

    def test_worker_operation_is_repo_owned_idempotent_apply_and_rollback(self) -> None:
        source = WORKER_OPERATION.read_text(encoding="utf-8")
        self.assertIn("apply|rollback", source)
        self.assertIn("--source-sha", source)
        self.assertIn("SOURCE_REPOSITORY=MostDef2000/sea-speed", source)
        self.assertIn("sea-speed-logout-v1.yaml", source)
        self.assertIn("sea-speed-logout-rollback-v1.yaml", source)
        self.assertIn("docker cp", source)
        self.assertIn('ak apply_blueprint "$container_path"', source)
        self.assertIn("from authentik.providers.proxy.models import ProxyProvider", source)
        self.assertIn('ProxyProvider.objects.get(name="Provider for Sea Speed")', source)
        self.assertIn("sea-speed-provider-invalidation", source)
        self.assertIn("default-provider-invalidation-flow", source)
        self.assertIn("UNEXPECTED_CURRENT_FLOW_", source)
        self.assertIn("AUTHENTIK_LOGOUT_AUTO_ROLLBACK=PASS", source)
        self.assertIn("AUTHENTIK_RUNTIME_CONTAINERS_UNCHANGED=YES", source)
        self.assertIn("AUTHENTIK_LOGOUT_OPERATION=PASS", source)
        self.assertNotIn("PG_PASS", source)
        self.assertNotIn("AUTHENTIK_SECRET_KEY", source)
        self.assertNotIn("AUTHENTIK_BOOTSTRAP_PASSWORD", source)


if __name__ == "__main__":
    unittest.main()
