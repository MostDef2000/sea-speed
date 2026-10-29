"""Executed twins for the Authentik logout contract (issue #398 wave 4).

The wave-3 revision of this file pinned blueprint/operation semantics with
raw source-text substrings. Every retired pin now has an executable twin in
this file:

- the blueprint YAMLs are parsed with ``yaml.safe_load`` through a loader
  that resolves the ``!KeyOf``/``!Find`` tags Authentik blueprints use, and
  the flow/stage/binding/provider structure is asserted on the parsed
  objects (comment-blind, rename-tolerant, stronger than byte matching);
- the three protected frontends execute their real inline scripts under the
  ``frontend_html`` node shim: the session watchdog is identified
  behaviorally (the interval registered at the protected cadence re-fetches
  the trusted identity), identity loss after establishment must rebuild the
  current URL from ``pathname+search+hash`` and hand it to
  ``window.top.location.replace``, and the provider logout link must be a
  real anchor attribute in the page markup;
- the worker operation script runs for real under
  ``unshare --user --map-root-user`` (root-gated EUID flow) with recording
  ``docker``/``curl``/``hostname`` stubs on PATH and a disposable runtime
  root — the apply/rollback/idempotence/drift/auto-rollback flows execute
  against the REAL blueprint files, and the secret-ban is proven by running
  with credential variables set and asserting they never reach the recorded
  docker invocations.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.support import frontend_html, relay_shell

ROOT = Path(__file__).resolve().parents[1]
FRONTENDS = (
    ROOT / "frontend/sea-speed/index.html",
    ROOT / "frontend/sea-speed/cameras/index.html",
    ROOT / "frontend/sea-speed/objects/index.html",
)
LOGOUT_BLUEPRINT = ROOT / "deploy/vps/authentik/blueprints/sea-speed-logout-v1.yaml"
ROLLBACK_BLUEPRINT = ROOT / "deploy/vps/authentik/blueprints/sea-speed-logout-rollback-v1.yaml"
WORKER_OPERATION = ROOT / "deploy/worker/ubuntu/authentik/apply-logout-flow.sh"

SIGN_OUT_HREF = "/outpost.goauthentik.io/sign_out"
SESSION_WATCHDOG_MS = 15000
PROVIDER_NAME = "Provider for Sea Speed"
SEA_SPEED_FLOW = "sea-speed-provider-invalidation"
DEFAULT_FLOW = "default-provider-invalidation-flow"
EXPECTED_PROVIDER_MODE = "forward_single"
SOURCE_SHA = "a" * 40


class BlueprintLoader(yaml.SafeLoader):
    """SafeLoader that resolves Authentik's custom tags into tagged dicts so
    the parsed structure keeps the !KeyOf/!Find references inspectable."""


BlueprintLoader.add_constructor(
    "!KeyOf", lambda loader, node: {"!KeyOf": loader.construct_scalar(node)}
)
BlueprintLoader.add_constructor(
    "!Find", lambda loader, node: {"!Find": loader.construct_sequence(node, deep=True)}
)


def load_blueprint(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=BlueprintLoader)


# Executed session-watchdog twin, run in the page's own scope: the interval
# registered at the protected cadence must re-fetch the trusted identity,
# identity must populate the trusted element, and identity loss AFTER
# establishment must rebuild the current URL (pathname+search+hash) and hand
# it to window.top.location.replace. Storage globals must stay undefined in
# the page scope (any module-level or watchdog-path access would throw under
# the shim, which has no storage globals).
LOGOUT_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  assert(typeof localStorage === "undefined", "localStorage must not exist in the page scope");
  assert(typeof sessionStorage === "undefined", "sessionStorage must not exist in the page scope");
  const watchdogs = __record.intervals.filter(([, ms]) => ms === __WATCHDOG_MS);
  assert(watchdogs.length >= 1, "no " + __WATCHDOG_MS + " ms interval registered (session watchdog missing)");
  // The watchdog may be an async loader or a `() => void loader()` wrapper;
  // firing it yields a macrotask so the identity fetch settles either way.
  const fireWatchdogs = async () => {
    for (const watchdog of watchdogs) {
      await watchdog[0]();
      await new Promise((r) => setImmediate(r));
    }
  };
  const fetchCountBefore = __record.fetch.length;
  await fireWatchdogs();
  assert(
    __record.fetch.slice(fetchCountBefore).some((c) => c.url === __SESSION_PATH),
    "the " + __WATCHDOG_MS + " ms interval does not re-fetch the trusted identity"
  );
  assert(
    __record.elements.sessionUser && __record.elements.sessionUser.textContent === __sessionUser,
    "success path does not populate the trusted identity"
  );
  location.search = "?probe=1";
  location.hash = "#frag";
  __sessionFail = true;
  await fireWatchdogs();
  const expected = location.pathname + "?probe=1" + "#frag";
  assert(
    __record.replaces.includes(expected),
    "identity loss after establishment must window.top.location.replace to the current URL (" +
      expected + "); recorded: " + JSON.stringify(__record.replaces)
  );
  console.log("###" + JSON.stringify({
    sessionFetches: __record.fetch.filter((c) => c.url === __SESSION_PATH).map((c) => c.options),
    intervals: __record.intervals.map(([fn, ms]) => ({ fn: (fn && fn.name) || "?", ms })),
    replaces: __record.replaces,
    sessionUser: __record.elements.sessionUser ? __record.elements.sessionUser.textContent : null,
  }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


class AuthLogoutBlueprintTests(unittest.TestCase):
    def test_sea_speed_specific_invalidation_flow_ends_browser_session_and_redirects_root(self) -> None:
        data = load_blueprint(LOGOUT_BLUEPRINT)
        entries = data["entries"]
        flow = next(e for e in entries if e["model"] == "authentik_flows.flow")
        self.assertEqual(flow["identifiers"]["slug"], SEA_SPEED_FLOW)
        self.assertEqual(flow["attrs"]["designation"], "invalidation")
        next(e for e in entries if e["model"] == "authentik_stages_user_logout.userlogoutstage")
        redirect = next(e for e in entries if e["model"] == "authentik_stages_redirect.redirectstage")
        self.assertEqual(redirect["attrs"]["mode"], "static")
        self.assertEqual(redirect["attrs"]["target_static"], "https://mostdef.ru/")
        provider = next(e for e in entries if e["model"] == "authentik_providers_proxy.proxyprovider")
        self.assertEqual(provider["identifiers"]["name"], PROVIDER_NAME)
        self.assertEqual(provider["attrs"]["mode"], "forward_single")
        self.assertEqual(
            provider["attrs"]["invalidation_flow"], {"!KeyOf": "sea-speed-invalidation-flow"}
        )
        self.assertNotIn("internal_host", provider["attrs"])
        self.assertNotIn("external_host", provider["attrs"])
        # The global default invalidation flow is never touched or referenced
        # by the apply blueprint (no slug identifier, no !Find reference).
        self.assertNotIn(DEFAULT_FLOW, json.dumps(data))

    def test_logout_flow_stage_order_is_user_logout_then_redirect(self) -> None:
        data = load_blueprint(LOGOUT_BLUEPRINT)
        bindings = [e for e in data["entries"] if e["model"] == "authentik_flows.flowstagebinding"]
        self.assertEqual(len(bindings), 2)
        for binding in bindings:
            self.assertEqual(binding["identifiers"]["target"], {"!KeyOf": "sea-speed-invalidation-flow"})
        by_order = sorted(bindings, key=lambda b: b["identifiers"]["order"])
        self.assertEqual(by_order[0]["identifiers"]["order"], 10)
        self.assertEqual(by_order[0]["identifiers"]["stage"], {"!KeyOf": "sea-speed-user-logout"})
        self.assertEqual(by_order[1]["identifiers"]["order"], 20)
        self.assertEqual(by_order[1]["identifiers"]["stage"], {"!KeyOf": "sea-speed-logout-redirect"})

    def test_rollback_blueprint_restores_only_sea_speed_provider_to_default(self) -> None:
        data = load_blueprint(ROLLBACK_BLUEPRINT)
        entries = data["entries"]
        self.assertEqual(len(entries), 1)
        provider = entries[0]
        self.assertEqual(provider["model"], "authentik_providers_proxy.proxyprovider")
        self.assertEqual(provider["identifiers"]["name"], PROVIDER_NAME)
        self.assertEqual(provider["attrs"]["mode"], "forward_single")
        self.assertEqual(
            provider["attrs"]["invalidation_flow"],
            {"!Find": ["authentik_flows.flow", ["slug", DEFAULT_FLOW]]},
        )
        self.assertNotIn("internal_host", provider["attrs"])
        self.assertNotIn("external_host", provider["attrs"])
        models = {entry["model"] for entry in entries}
        self.assertNotIn("authentik_stages_user_logout.userlogoutstage", models)
        self.assertNotIn("authentik_stages_redirect.redirectstage", models)
        self.assertNotIn("target_static", json.dumps(data))


class FrontendLogoutExecutedTests(unittest.TestCase):
    def test_frontends_preserve_provider_logout_and_watch_trusted_session(self) -> None:
        for path in FRONTENDS:
            with self.subTest(path=path.relative_to(ROOT)):
                html = path.read_text(encoding="utf-8-sig")
                # The provider logout link is a real anchor attribute in the
                # markup, not a stray string.
                self.assertRegex(html, r'<a[^>]*href="' + re.escape(SIGN_OUT_HREF) + '"')
                evidence = frontend_html.run_inline_scripts(source=path, scenario=LOGOUT_SCENARIO)
                self.assertEqual(evidence["sessionUser"], "operator")
                self.assertTrue(
                    any(ms == SESSION_WATCHDOG_MS for ms in (i["ms"] for i in evidence["intervals"])),
                    "no session watchdog interval registered",
                )
                self.assertTrue(
                    any("probe=1#frag" in replaced for replaced in evidence["replaces"]),
                    f"identity loss did not replace to the current URL: {evidence['replaces']}",
                )
                self.assertTrue(
                    all(fetch.get("credentials") == "same-origin" for fetch in evidence["sessionFetches"]),
                    "session fetches must stay same-origin",
                )


# Recording docker stub: answers the compose/inspect/exec probes the real
# operation makes, records every cp and ak invocation to $DOCKER_LOG, and
# keeps the provider flow/mode in a state file so the operation's
# query-apply-verify cycle observes real state transitions.
DOCKER_STUB = r"""#!/usr/bin/env bash
log="${DOCKER_LOG:-/dev/null}"
case "$1" in
  compose)
    case "$2" in
      version|config) exit 0 ;;
      ps) printf 'id-%s\n' "$4" ;;
      *) exit 0 ;;
    esac ;;
  inspect) printf 'true\n' ;;
  cp)
    printf 'docker cp %s %s\n' "$2" "$3" >> "$log"
    # Remember which source blueprint was copied: apply_blueprint only sees
    # the fixed container path, so the copied source decides the new state.
    [[ -n "${AK_FLOW_STATE:-}" ]] && printf '%s\n' "$2" > "${AK_FLOW_STATE}.copied"
    exit 0 ;;
  exec)
    case "$4" in
      test|rm) exit 0 ;;
      shell)
        code="$6"
        printf 'ak shell -c %s\n' "$code" >> "$log"
        if [[ "$code" == *SEA_SPEED_PROVIDER_MODE* ]]; then
          # Mode is stateful like the flow: AK_PROVIDER_MODE seeds it, a
          # written AK_MODE_STATE file (see apply_blueprint below) overrides —
          # so the post-apply verify can observe a drifted mode.
          mode="${AK_PROVIDER_MODE:-forward_single}"
          [[ -n "${AK_MODE_STATE:-}" && -f "$AK_MODE_STATE" ]] && mode="$(cat "$AK_MODE_STATE")"
          printf 'SEA_SPEED_PROVIDER_MODE=%s\n' "$mode"
        elif [[ "$code" == *SEA_SPEED_PROVIDER_FLOW* ]]; then
          flow="default-provider-invalidation-flow"
          [[ -n "${AK_FLOW_STATE:-}" && -f "$AK_FLOW_STATE" ]] && flow="$(cat "$AK_FLOW_STATE")"
          printf 'SEA_SPEED_PROVIDER_FLOW=%s\n' "$flow"
        fi
        exit 0 ;;
      apply_blueprint)
        printf 'ak apply_blueprint %s\n' "$5" >> "$log"
        if [[ "${AK_APPLY_FAIL:-}" == "1" ]]; then exit 1; fi
        if [[ "${AK_APPLY_NOOP:-}" != "1" ]]; then
          copied="$(cat "${AK_FLOW_STATE}.copied" 2>/dev/null || true)"
          case "$copied" in
            *logout-rollback-v1.yaml*) printf 'default-provider-invalidation-flow\n' > "$AK_FLOW_STATE" ;;
            *sea-speed-logout-v1.yaml*) printf 'sea-speed-provider-invalidation\n' > "$AK_FLOW_STATE" ;;
          esac
        fi
        # Simulated post-apply provider-mode drift: the apply "succeeded" but
        # the provider mode no longer matches — the operation's post-apply
        # verify must observe the drift through the state file.
        if [[ -n "${AK_MODE_AFTER_APPLY:-}" && -n "${AK_MODE_STATE:-}" ]]; then
          printf '%s\n' "$AK_MODE_AFTER_APPLY" > "$AK_MODE_STATE"
        fi
        exit 0 ;;
      *) exit 0 ;;
    esac ;;
  *) exit 0 ;;
esac
"""

CURL_STUB = "#!/usr/bin/env bash\nexit 0\n"
HOSTNAME_STUB = "#!/usr/bin/env bash\necho sea-speed-worker\n"


class WorkerLogoutOperationExecutedTests(unittest.TestCase):
    def setUp(self) -> None:
        relay_shell.skip_without_user_namespace(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        stubs = tmp / "stubs"
        stubs.mkdir()
        for name, body in (("docker", DOCKER_STUB), ("curl", CURL_STUB), ("hostname", HOSTNAME_STUB)):
            stub = stubs / name
            stub.write_text(body, encoding="utf-8")
            stub.chmod(0o755)
        self.stubs = stubs
        self.runtime_root = tmp / "runtime"
        self.runtime_root.mkdir()
        (self.runtime_root / "compose.yml").write_text("services: {}\n", encoding="utf-8")
        (self.runtime_root / ".env").write_text("AUTHENTIK_TAG=2026.5.1\n", encoding="utf-8")
        self.docker_log = tmp / "docker-log"
        self.flow_state = tmp / "flow-state"
        self.mode_state = tmp / "mode-state"

    def run_operation(self, args: list[str], *, flow: str | None = None, mode: str | None = None,
                      apply_noop: bool = False, mode_after_apply: str | None = None,
                      extra_env: dict[str, str] | None = None):
        env = dict(os.environ)
        env["PATH"] = f"{self.stubs}:{os.environ['PATH']}"
        env["DOCKER_LOG"] = str(self.docker_log)
        env["AK_FLOW_STATE"] = str(self.flow_state)
        env["AK_MODE_STATE"] = str(self.mode_state)
        if flow is not None:
            self.flow_state.write_text(flow + "\n", encoding="utf-8")
        if mode is not None:
            env["AK_PROVIDER_MODE"] = mode
        if apply_noop:
            env["AK_APPLY_NOOP"] = "1"
        if mode_after_apply is not None:
            env["AK_MODE_AFTER_APPLY"] = mode_after_apply
        env.update(extra_env or {})
        return relay_shell.run_shell(
            WORKER_OPERATION, args, Path(self._tmp.name),
            env_extra=env, use_unshare=True, with_stubs=False,
        )

    def docker_log_lines(self) -> list[str]:
        if not self.docker_log.exists():
            return []
        return self.docker_log.read_text(encoding="utf-8").splitlines()

    def test_usage_and_unknown_command_exit_codes(self) -> None:
        usage = self.run_operation([])
        self.assertEqual(usage.returncode, 0)
        self.assertIn("Usage:", usage.stdout)
        unknown = self.run_operation(["reboot"])
        self.assertEqual(unknown.returncode, 2)
        self.assertIn("ERROR unknown command: reboot", unknown.stderr)

    def test_source_sha_gate_rejects_non_full_sha(self) -> None:
        bad = self.run_operation(["apply", "--source-sha", "tooshort"])
        self.assertEqual(bad.returncode, 42)
        self.assertIn("AUTHENTIK_LOGOUT_FAIL=SOURCE_SHA_INVALID", bad.stderr)

    def test_apply_happy_path_applies_real_blueprint_and_reports_pass(self) -> None:
        proc = self.run_operation(
            ["apply", "--source-sha", SOURCE_SHA, "--runtime-root", str(self.runtime_root)],
            flow=DEFAULT_FLOW,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        evidence = proc.stdout
        self.assertIn("SOURCE_REPOSITORY=MostDef2000/sea-speed", evidence)
        self.assertIn(f"SOURCE_COMMIT={SOURCE_SHA}", evidence)
        self.assertIn("AUTHENTIK_PROVIDER_MODE_BEFORE=forward_single", evidence)
        self.assertIn("AUTHENTIK_PROVIDER_MODE_AFTER=forward_single", evidence)
        self.assertIn("AUTHENTIK_PROVIDER_INVALIDATION_FLOW_BEFORE=default-provider-invalidation-flow", evidence)
        self.assertIn("AUTHENTIK_PROVIDER_INVALIDATION_FLOW_AFTER=sea-speed-provider-invalidation", evidence)
        self.assertIn("AUTHENTIK_RUNTIME_CONTAINERS_UNCHANGED=YES", evidence)
        self.assertIn("AUTHENTIK_LOGOUT_OPERATION=PASS", evidence)
        # The blueprint digest is the REAL file's sha256 (read-back twin).
        expected_digest = hashlib.sha256(LOGOUT_BLUEPRINT.read_bytes()).hexdigest()
        self.assertIn(f"AUTHENTIK_BLUEPRINT_SHA256={expected_digest}", evidence)
        # The mutation copied the real apply blueprint into the container and
        # ran ak apply_blueprint on the fixed container path.
        log = self.docker_log_lines()
        self.assertTrue(
            any(
                line.startswith("docker cp ")
                and line.endswith(f"id-worker:{'/blueprints/.sea-speed-logout-operation'}")
                and str(LOGOUT_BLUEPRINT) in line
                for line in log
            ),
            f"apply did not copy the real blueprint: {log}",
        )
        self.assertTrue(any("ak apply_blueprint /blueprints/.sea-speed-logout-operation" in line for line in log))
        # The provider queries address the real provider by name.
        self.assertTrue(
            any('ProxyProvider.objects.get(name="Provider for Sea Speed")' in line for line in log)
        )

    def test_apply_is_idempotent_when_already_applied(self) -> None:
        proc = self.run_operation(
            ["apply", "--source-sha", SOURCE_SHA, "--runtime-root", str(self.runtime_root)],
            flow=SEA_SPEED_FLOW,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("AUTHENTIK_LOGOUT_OPERATION=ALREADY_APPLIED", proc.stdout)
        self.assertNotIn("AUTHENTIK_LOGOUT_OPERATION=PASS", proc.stdout)
        self.assertEqual([line for line in self.docker_log_lines() if "docker cp" in line], [])

    def test_rollback_restores_default_flow_via_rollback_blueprint(self) -> None:
        proc = self.run_operation(
            ["rollback", "--source-sha", SOURCE_SHA, "--runtime-root", str(self.runtime_root)],
            flow=SEA_SPEED_FLOW,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("AUTHENTIK_PROVIDER_INVALIDATION_FLOW_AFTER=default-provider-invalidation-flow", proc.stdout)
        self.assertIn("AUTHENTIK_LOGOUT_OPERATION=PASS", proc.stdout)
        log = "\n".join(self.docker_log_lines())
        self.assertIn(str(ROLLBACK_BLUEPRINT), log)
        self.assertNotIn(str(LOGOUT_BLUEPRINT), log)

    def test_provider_mode_drift_fails_closed_before_mutation(self) -> None:
        proc = self.run_operation(
            ["apply", "--source-sha", SOURCE_SHA, "--runtime-root", str(self.runtime_root)],
            flow=DEFAULT_FLOW,
            mode="proxy",
        )
        self.assertEqual(proc.returncode, 61)
        self.assertIn("AUTHENTIK_LOGOUT_FAIL=UNEXPECTED_PROVIDER_MODE_proxy", proc.stderr)
        self.assertEqual([line for line in self.docker_log_lines() if "docker cp" in line], [])

    def test_provider_mode_drift_after_apply_fails_closed(self) -> None:
        # rc62 POST-apply twin: the apply blueprint is really copied and
        # applied, but the post-apply provider-mode verify must still observe
        # forward_single — a drifted mode fails closed AFTER the mutation
        # (rc62, distinct from the rc61 pre-mutation gate above; fail() prints
        # the drift literal to stderr).
        proc = self.run_operation(
            ["apply", "--source-sha", SOURCE_SHA, "--runtime-root", str(self.runtime_root)],
            flow=DEFAULT_FLOW,
            mode_after_apply="proxy",
        )
        self.assertEqual(proc.returncode, 62)
        self.assertIn("AUTHENTIK_LOGOUT_FAIL=PROVIDER_MODE_DRIFT_proxy", proc.stderr)
        self.assertIn("AUTHENTIK_LOGOUT_OPERATION=FAIL", proc.stderr)
        # The mutation happened before the drift was detected: this is the
        # post-apply guard, not the pre-mutation one.
        self.assertTrue(
            any("docker cp" in line for line in self.docker_log_lines()),
            "the rc62 drift twin must run after a real blueprint apply",
        )

    def test_unexpected_current_flow_fails_closed(self) -> None:
        proc = self.run_operation(
            ["apply", "--source-sha", SOURCE_SHA, "--runtime-root", str(self.runtime_root)],
            flow="some-unrelated-flow",
        )
        self.assertEqual(proc.returncode, 54)
        self.assertIn("AUTHENTIK_LOGOUT_FAIL=UNEXPECTED_CURRENT_FLOW_some-unrelated-flow", proc.stderr)

    def test_failed_verification_auto_rolls_back_to_the_default_flow(self) -> None:
        # AK_APPLY_NOOP=1: apply_blueprint reports success but the provider
        # keeps its old flow — the operation must detect the verify miss and
        # restore the rollback blueprint before failing closed.
        proc = self.run_operation(
            ["apply", "--source-sha", SOURCE_SHA, "--runtime-root", str(self.runtime_root)],
            flow=DEFAULT_FLOW,
            apply_noop=True,
        )
        self.assertEqual(proc.returncode, 56, proc.stderr)
        self.assertIn("AUTHENTIK_LOGOUT_AUTO_ROLLBACK=PASS", proc.stderr)
        log = "\n".join(self.docker_log_lines())
        self.assertIn(str(ROLLBACK_BLUEPRINT), log)

    def test_operation_never_moves_credential_material_through_docker(self) -> None:
        proc = self.run_operation(
            ["apply", "--source-sha", SOURCE_SHA, "--runtime-root", str(self.runtime_root)],
            flow=DEFAULT_FLOW,
            extra_env={
                "PG_PASS": "super-secret-pg",
                "AUTHENTIK_SECRET_KEY": "super-secret-key",
                "AUTHENTIK_BOOTSTRAP_PASSWORD": "super-bootstrap",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        log = "\n".join(self.docker_log_lines())
        for banned in ("PG_PASS", "AUTHENTIK_SECRET_KEY", "AUTHENTIK_BOOTSTRAP_PASSWORD"):
            self.assertNotIn(banned, log)

    def test_worker_operation_shell_syntax(self) -> None:
        subprocess.run(
            ["bash", "-n", str(WORKER_OPERATION)],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
