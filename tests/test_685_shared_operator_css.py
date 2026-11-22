"""Issue #685 — shared operator CSS extraction (Water/Road prefix → one asset).

The 22-rule stylesheet prefix both operator pages shared inline was extracted
verbatim into ``frontend/sea-speed/operator-common.css`` and linked from each
page with an absolute ``<link>`` immediately before the residual ``<style>``.
These tests pin the extraction itself and the deploy transaction around it:

- ORDERED RULE EQUIVALENCE: ``linked prefix + residual inline`` must equal the
  pre-#685 page's whole-rule sequence, in order, for both pages — parsed from
  git (``git show <base>:frontend/...``), with literal expectations 22 / 129 /
  130 (not derived from the CSS file).
- PREFIX BOUNDARY: ``:root`` first, the base ``.objects-link{...}`` rule
  last, no ``.objects-link:hover`` / video / canvas / fullscreen / breakpoints
  inside the shared asset; both residual styles start at ``.objects-link:hover``.
- LINK TAG: exactly one absolute link per operator page, before ``<style>``,
  none on the cameras/objects pages.
- INVENTORIES: the path is in both VPS required lists, not in edge/ubuntu-worker.
- DEPLOY TRANSACTION: release completeness + download required-list, live
  promotion, bootstrap/capture fail-closed rules for the rollback release,
  empty-asset rejection, upgrade/downgrade activation ordering, and the
  post-activation public smoke (``VpsDeployFixture`` is the repo's existing
  harness, code-motion-only refactor).
- SCOPE GUARD: the working tree touches only the #685 surface + tests.

RED on the pre-#685 tree: the CSS file and the link tag do not exist, so the
equivalence/boundary/link/inventory tests fail outright, and the deploy tests
fail because the pre-#685 ``deploy.sh`` has no operator-common.css handling
(never promotes it, never records a marker, never orders it before the HTML).
The two ``.operator-header`` structural pins in ``test_frontend_contract.py``
were likewise RED against the extracted pages until they were repointed at the
page-plus-linked-stylesheet text.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import tarfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.quality.build_exact_artifacts import COMPONENT_FILES  # noqa: E402
from scripts.quality.validate_exact_artifacts import REQUIRED_BY_COMPONENT  # noqa: E402
from tests.test_vps_deploy_transaction import (  # noqa: E402
    CANDIDATE,
    DEPLOY_SCRIPT,
    OLD,
    VpsDeployFixture,
)

WATER_PAGE = ROOT / "frontend/sea-speed/index.html"
ROAD_PAGE = ROOT / "frontend/sea-speed/road/index.html"
CAMERAS_PAGE = ROOT / "frontend/sea-speed/cameras/index.html"
OBJECTS_PAGE = ROOT / "frontend/sea-speed/objects/index.html"

CSS_RELATIVE = "frontend/sea-speed/operator-common.css"
WATER_RELATIVE = "frontend/sea-speed/index.html"
ROAD_RELATIVE = "frontend/sea-speed/road/index.html"
LINK_TAG = '<link rel="stylesheet" href="/sea-speed/operator-common.css">'

# Literal expectations for the extraction (issue #685 SDD): 22 shared rules,
# Water 129 total, Road 130 total. Never derived from the shipped CSS file —
# a CSS file that shrank would otherwise "pass" by being shorter.
LINKED_RULES = 22
WATER_BASE_RULES = 129
ROAD_BASE_RULES = 130

# Read tolerantly so a missing asset is a per-test failure with a clear
# message instead of a collection error (the RED tree has no such file).
COMMON_CSS_PATH = ROOT / CSS_RELATIVE
SHARED_CSS = (
    COMMON_CSS_PATH.read_text(encoding="utf-8") if COMMON_CSS_PATH.is_file() else ""
)

# The working-tree surface this issue is allowed to touch (plus tests/).
ALLOWED_CHANGE_PREFIXES = (
    "tests/",
    "deploy/vps/deploy.sh",
    "frontend/sea-speed/index.html",
    "frontend/sea-speed/road/index.html",
    "frontend/sea-speed/operator-common.css",
    "scripts/quality/build_exact_artifacts.py",
    "scripts/quality/validate_exact_artifacts.py",
    "specs/685-shared-operator-css/",
)
FORBIDDEN_CHANGE_PREFIXES = (".github/", "api/", "deploy/worker/", "worker/")


def git_show(spec: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "show", spec],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def base_page_text(relative: str) -> str:
    """Pre-#685 page text from git.

    While the landing is uncommitted, HEAD *is* the pre-#685 state; once the
    landing commits, HEAD references the asset and the base becomes the parent
    of the commit that introduced the reference (found with ``git log -S``).
    Either way the base is read back with ``git show <base>:<path>``.
    """
    head = git_show(f"HEAD:{relative}")
    if "operator-common.css" not in head:
        return head
    result = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "log",
            "-S",
            "operator-common.css",
            "--format=%H",
            "--",
            relative,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    for rev in result.stdout.split():
        if "operator-common.css" in git_show(f"{rev}:{relative}"):
            return git_show(f"{rev}^:{relative}")
    raise AssertionError(f"no pre-#685 revision found for {relative}")


def top_level_rules(css: str) -> list[str]:
    """Split CSS into whole top-level rules (at-rules keep their block).

    Brace depth is tracked with string- and comment-awareness so declarations
    such as ``content:"}"`` or ``background:url({)`` cannot split a rule.
    """
    rules: list[str] = []
    depth = 0
    start = 0
    index = 0
    in_string: str | None = None
    escaped = False
    in_comment = False
    while index < len(css):
        char = css[index]
        if in_comment:
            if char == "*" and index + 1 < len(css) and css[index + 1] == "/":
                in_comment = False
                index += 2
                continue
            index += 1
            continue
        if in_string is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            index += 1
            continue
        if char == "/" and index + 1 < len(css) and css[index + 1] == "*":
            in_comment = True
            index += 2
            continue
        if char in "\"'":
            in_string = char
            index += 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                segment = css[start : index + 1]
                if segment.strip():
                    rules.append(segment)
                start = index + 1
        index += 1
    tail = css[start:]
    if tail.strip():
        rules.append(tail)
    return rules


def normalize_rule(rule: str) -> str:
    """Whitespace between tokens may differ; nothing else may."""
    return re.sub(r"\s+", " ", rule).strip()


def inline_style(page_text: str) -> str:
    start = page_text.find("<style>")
    end = page_text.find("</style>")
    if start == -1 or end == -1 or end < start:
        raise AssertionError("page has no inline <style> block")
    return page_text[start + len("<style>") : end]


# ---------------------------------------------------------------------------
# 1. Ordered rule equivalence, 2. prefix boundary, 3. link tag,
# 4. inventories, 6. scope guard.
# ---------------------------------------------------------------------------


class SharedCssEquivalenceTests(unittest.TestCase):
    PAGES = (
        (WATER_PAGE, WATER_RELATIVE, WATER_BASE_RULES),
        (ROAD_PAGE, ROAD_RELATIVE, ROAD_BASE_RULES),
    )

    def test_linked_prefix_plus_residual_equals_the_pre_685_rule_sequence(self) -> None:
        """AC: reconstruction from the shipped files is byte-equivalent (rules)
        to the pre-#685 page, in order, with the literal rule counts."""
        self.assertTrue(
            SHARED_CSS.strip(),
            f"{CSS_RELATIVE} is missing or empty — the extraction did not land",
        )
        linked = top_level_rules(SHARED_CSS)
        self.assertEqual(
            len(linked),
            LINKED_RULES,
            f"the shared stylesheet must carry exactly {LINKED_RULES} extracted rules",
        )
        for page, relative, expected_total in self.PAGES:
            with self.subTest(page=relative):
                base_rules = top_level_rules(inline_style(base_page_text(relative)))
                residual = top_level_rules(
                    inline_style(page.read_text(encoding="utf-8-sig"))
                )
                self.assertEqual(
                    len(base_rules),
                    expected_total,
                    f"pre-#685 {relative} must have {expected_total} whole rules",
                )
                reconstructed = [normalize_rule(r) for r in linked + residual]
                original = [normalize_rule(r) for r in base_rules]
                self.assertEqual(
                    reconstructed,
                    original,
                    f"ordered rule sequence changed for {relative}: the shared "
                    "prefix + residual inline must equal the pre-#685 page rule "
                    "for rule (selectors, declaration order, literals, "
                    "importance and at-rules all included)",
                )


class SharedCssPrefixBoundaryTests(unittest.TestCase):
    def test_shared_css_runs_from_root_to_the_base_objects_link_rule(self) -> None:
        self.assertTrue(SHARED_CSS.strip(), f"{CSS_RELATIVE} is missing or empty")
        rules = top_level_rules(SHARED_CSS)
        self.assertEqual(
            rules[0].split("{", 1)[0].strip(),
            ":root",
            "the shared prefix must start with the :root variable block",
        )
        self.assertTrue(
            rules[-1].startswith(".objects-link{"),
            f"the shared prefix must end with the base .objects-link rule, got: "
            f"{rules[-1][:70]}",
        )
        self.assertNotIn(
            ".objects-link:hover",
            SHARED_CSS,
            "the boundary rule .objects-link:hover belongs to the page-specific "
            "residual, not the shared asset",
        )
        lowered = SHARED_CSS.lower()
        for token in ("video", "canvas", "fullscreen", "@media", "prefers-reduced-motion"):
            self.assertNotIn(
                token,
                lowered,
                f"domain-specific rule leaked into the shared prefix: {token}",
            )
        # The final rule must be the pre-#685 base rule verbatim, on both pages.
        for _, relative, _ in SharedCssEquivalenceTests.PAGES:
            with self.subTest(base=relative):
                base_rules = top_level_rules(inline_style(base_page_text(relative)))
                base_objects = [r for r in base_rules if r.startswith(".objects-link{")]
                self.assertEqual(
                    len(base_objects),
                    1,
                    f"pre-#685 {relative} must contain exactly one base .objects-link rule",
                )
                self.assertEqual(
                    normalize_rule(rules[-1]),
                    normalize_rule(base_objects[0]),
                    f"the shared CSS must end with the pre-#685 .objects-link "
                    f"rule of {relative} unchanged",
                )

    def test_residual_inline_styles_start_at_the_boundary_rule(self) -> None:
        for page in (WATER_PAGE, ROAD_PAGE):
            with self.subTest(page=page.name):
                residual = top_level_rules(
                    inline_style(page.read_text(encoding="utf-8-sig"))
                )
                self.assertTrue(
                    residual[0].lstrip().startswith(".objects-link:hover"),
                    "the residual <style> must start exactly where the shared "
                    f"prefix stopped, got: {residual[0][:70]}",
                )


class OperatorCssLinkTagTests(unittest.TestCase):
    def test_each_operator_page_links_the_shared_css_once_before_the_style_block(
        self,
    ) -> None:
        for page in (WATER_PAGE, ROAD_PAGE):
            with self.subTest(page=page.name):
                text = page.read_text(encoding="utf-8-sig")
                self.assertEqual(
                    text.count(LINK_TAG),
                    1,
                    f"{page.name}: expected exactly one {LINK_TAG}",
                )
                self.assertLess(
                    text.index(LINK_TAG),
                    text.index("<style>"),
                    "the shared stylesheet must be linked before the residual "
                    "<style> so page rules override the shared prefix",
                )
                self.assertEqual(
                    text.count("operator-common.css"),
                    1,
                    "the absolute link must be the only reference to the asset",
                )
                href = re.search(r'href="([^"]*)operator-common\.css"', text)
                self.assertIsNotNone(href, f"{page.name}: no href for the shared CSS")
                self.assertEqual(
                    href.group(1),
                    "/sea-speed/",
                    "the link must be an absolute site path (both pages resolve "
                    "it from /sea-speed/ and /sea-speed/road/)",
                )

    def test_secondary_pages_do_not_link_the_shared_css(self) -> None:
        for page in (CAMERAS_PAGE, OBJECTS_PAGE):
            with self.subTest(page=page.name):
                text = page.read_text(encoding="utf-8-sig")
                self.assertNotIn(
                    "operator-common.css",
                    text,
                    "only the two operator pages carry the shared stylesheet",
                )


class OperatorCssInventoryTests(unittest.TestCase):
    def test_both_vps_required_lists_carry_the_shared_css(self) -> None:
        self.assertIn(
            CSS_RELATIVE,
            COMPONENT_FILES["vps"]["required"],
            "build_exact_artifacts vps required list must ship the shared CSS",
        )
        self.assertIn(
            CSS_RELATIVE,
            REQUIRED_BY_COMPONENT["vps"],
            "validate_exact_artifacts vps required set must ship the shared CSS",
        )

    def test_edge_and_ubuntu_worker_lists_do_not_carry_it(self) -> None:
        for component in ("edge", "ubuntu-worker"):
            with self.subTest(component=component):
                self.assertNotIn(CSS_RELATIVE, COMPONENT_FILES[component]["required"])
                self.assertNotIn(
                    CSS_RELATIVE, COMPONENT_FILES[component].get("optional", [])
                )
                self.assertNotIn(CSS_RELATIVE, REQUIRED_BY_COMPONENT[component])


class OperatorCssScopeGuardTests(unittest.TestCase):
    def test_working_tree_touches_only_the_685_surface_and_tests(self) -> None:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        paths: list[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            paths.append(path.strip().strip('"'))
        offenders = [
            path
            for path in paths
            if not any(
                path == prefix or path.startswith(prefix)
                for prefix in ALLOWED_CHANGE_PREFIXES
            )
        ]
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope working-tree changes for #685: {offenders}",
        )
        for forbidden in FORBIDDEN_CHANGE_PREFIXES:
            self.assertFalse(
                any(path.startswith(forbidden) for path in paths),
                f"forbidden path changed: {forbidden}",
            )
        self.assertFalse(
            any(path.endswith(".lock") or path.endswith(".lock.txt") for path in paths),
            f"lockfile changed: {paths}",
        )
        self.assertNotIn("package-lock.json", paths)


# ---------------------------------------------------------------------------
# 5. Deploy transaction (existing VpsDeployFixture harness).
# ---------------------------------------------------------------------------


class OperatorCssDeployTests(VpsDeployFixture):
    """#685 behavior of deploy/vps/deploy.sh on the shared sandbox fixture."""

    def release_css(self, sha: str) -> Path:
        return self.releases / sha / CSS_RELATIVE

    def build_archive_without_css(self, sha: str) -> bytes:
        # Same GitHub archive shape as the harness builder, minus the shared
        # CSS: the download required-list must reject it by name.
        top = self.root / "archive-src-no-css" / f"sea-speed-{sha}"
        files = self.release_files(sha)
        files.pop("commit-sha")
        files.pop("archive-sha256")
        files.pop(CSS_RELATIVE)
        for relative, content in files.items():
            path = top / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            archive.add(top, arcname=f"sea-speed-{sha}")
        return buffer.getvalue()

    def install_activation_order_log(self) -> Path:
        # Log every mv/rm the deploy performs into ONE file so the relative
        # order of the CSS and HTML activations is observable, not inferred
        # from source text. Both wrappers still exec the real binaries.
        log_path = self.root / "activation-order.log"
        self.write_executable(
            "mv",
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf '%s\\n' \"mv $*\" >> \"$FAKE_ORDER_LOG\"\n"
            "exec /bin/mv \"$@\"\n",
        )
        existing_rm = (self.fake_bin / "rm").read_text(encoding="utf-8")
        rm_body = existing_rm.split("\n", 1)[1]
        self.write_executable(
            "rm",
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf '%s\\n' \"rm $*\" >> \"$FAKE_ORDER_LOG\"\n" + rm_body,
        )
        return log_path

    def install_css_status_curl(self) -> None:
        # Like the login-popup status fake: answer FAKE_CSS_URL_STATUS for the
        # shared-CSS URL only, keyed on the live asset content so the rollback
        # re-verification (live = old release) sees a healthy 200 again.
        existing = (self.fake_bin / "curl").read_text(encoding="utf-8")
        body = existing.split("\n", 1)[1]
        branch = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "if [[ \"${@: -1}\" == \"${SEA_SPEED_OPERATOR_COMMON_CSS_URL:-}\" ]]; then\n"
            "  if grep -Fq \"$FAKE_CANDIDATE_SHA\" \"$SEA_SPEED_OPERATOR_COMMON_CSS_TARGET\" "
            "2>/dev/null; then\n"
            "    printf '%s' \"${FAKE_CSS_URL_STATUS:-500}\"\n"
            "  else\n"
            "    printf '200'\n"
            "  fi\n"
            "  exit 0\n"
            "fi\n" + body
        )
        self.write_executable("curl", branch)

    # -- release completeness / download ------------------------------------

    def test_release_complete_and_download_reject_a_release_without_the_css(
        self,
    ) -> None:
        # release_complete's required list must include the asset: without it
        # completeness fails and download_release runs; the pre-placed archive
        # (no curl involved) is then rejected by the download required-list
        # check with the asset named. If release_complete had wrongly passed,
        # the script would log "already exists" and never reach this message.
        shutil.rmtree(self.releases / CANDIDATE)
        archive_path = self.root / f"sea-speed-vps-{CANDIDATE}.tar.gz"
        archive_path.write_bytes(self.build_archive_without_css(CANDIDATE))
        result = self.run_deploy(
            extra_env={"SEA_SPEED_RELEASE_ARCHIVE": str(archive_path)}
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            f"Release does not contain {CSS_RELATIVE}",
            result.stdout,
            "download_release must require the shared stylesheet by path",
        )
        self.assertEqual(self.current(), OLD)
        # no live mutation happened
        self.assertEqual(
            self.operator_css.read_text(encoding="utf-8"),
            f"/* operator-common-css {OLD} */\n",
        )

    def test_success_promotes_the_shared_css_into_the_live_tree(self) -> None:
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            self.operator_css.read_text(encoding="utf-8"),
            f"/* operator-common-css {CANDIDATE} */\n",
            "the candidate release's stylesheet must reach the live target",
        )
        self.assertFalse(
            (self.live / f"{CSS_RELATIVE}.next").exists(),
            "the staged .next stylesheet must not survive activation",
        )
        self.assertEqual(self.current(), CANDIDATE)
        # The env() URL override is honored: the post-activation smoke hit it.
        self.assertIn(
            "Operator common stylesheet public smoke check passed with HTTP 200",
            result.stdout,
        )

    # -- ensure_current_release_has_operator_css ----------------------------

    def test_capture_records_absent_marker_for_genuine_prefeature_release(
        self,
    ) -> None:
        # The rollback release carries NEITHER the file nor a marker and the
        # live tree has no stylesheet either: a genuine pre-#685 release whose
        # HTML does not reference the asset must be accepted by recording the
        # .absent marker, so the rollback path stays alive.
        self.release_css(OLD).unlink()
        self.operator_css.unlink()
        result = self.run_deploy(mode="fail-candidate")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(
            (self.releases / OLD / f"{CSS_RELATIVE}.absent").is_file(),
            "the capture must record the .absent marker: " + result.stdout,
        )
        self.assertIn("Rollback successful", result.stdout)
        self.assertIn(
            "Operator common stylesheet is absent in this rollback release",
            result.stdout,
        )
        self.assertFalse(self.operator_css.exists())
        self.assertEqual(self.manifest()["state"], "rolled_back")

    def test_capture_fails_closed_when_rollback_html_references_missing_css(
        self,
    ) -> None:
        # Neither file nor marker AND the release HTML already links the
        # asset: activating that rollback target would ship a page linking a
        # missing stylesheet, so the capture must fail closed pre-mutation
        # instead of recording .absent.
        self.release_css(OLD).unlink()
        self.operator_css.unlink()
        (self.releases / OLD / WATER_RELATIVE).write_text(
            f"{LINK_TAG}\noperator {OLD}\n", encoding="utf-8"
        )
        result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "references operator-common.css but ships neither the asset nor an "
            ".absent marker",
            result.stdout,
        )
        self.assertEqual(self.current(), OLD)
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    # -- install_release css_state validation -------------------------------

    def test_install_release_fails_closed_on_an_empty_shared_css(self) -> None:
        # release_complete only checks presence (-f); install_release must
        # additionally reject an empty stylesheet before any activation.
        self.release_css(CANDIDATE).write_text("", encoding="utf-8")
        result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            f"Release {CANDIDATE} operator-common.css is empty", result.stdout
        )
        self.assertEqual(self.current(), OLD)
        self.assertFalse((self.state / "deployment-manifest.json").exists())
        self.assertEqual(
            self.operator_css.read_text(encoding="utf-8"),
            f"/* operator-common-css {OLD} */\n",
            "a rejected release must not touch the live stylesheet",
        )

    def test_install_release_fails_closed_when_release_references_missing_css(
        self,
    ) -> None:
        # Explicit .absent state (known "no asset") + HTML that links the
        # asset: activating it would break the live page, so install_release
        # must refuse — here on the rollback target, after the candidate
        # already mutated the tree.
        self.release_css(OLD).unlink()
        (self.releases / OLD / f"{CSS_RELATIVE}.absent").touch()
        (self.releases / OLD / WATER_RELATIVE).write_text(
            f"{LINK_TAG}\noperator {OLD}\n", encoding="utf-8"
        )
        result = self.run_deploy(mode="fail-candidate")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            f"Release {OLD} frontend references operator-common.css but ships "
            "no CSS asset",
            result.stdout,
        )
        self.assertEqual(self.current(), OLD)
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    def test_install_release_accepts_a_prefeature_release_without_the_css(
        self,
    ) -> None:
        # deploy.sh sets css_state=prefeature for a release carrying NEITHER
        # the CSS file NOR a .absent marker (deploy.sh:764-766). main() can
        # never hand install_release such a release today — release_complete
        # and the download list both require the file, and the capture
        # annotates the current release first — so the branch has no coverage
        # through a full run. Call install_release directly (byte-identical
        # deploy.sh copy minus the trailing `main "$@"`, sourced in bash) on a
        # neither-state, non-referencing release: it must activate cleanly.
        release_css = self.release_css(CANDIDATE)
        release_css.unlink()
        self.assertFalse(
            (release_css.parent / "operator-common.css.absent").exists(),
            "the fixture release must be in the neither state (no marker)",
        )
        self.assertNotIn(
            "operator-common.css",
            (self.releases / CANDIDATE / WATER_RELATIVE).read_text(encoding="utf-8"),
            "the fixture release HTML must not reference the stylesheet",
        )

        driver = self.root / "deploy-no-main.sh"
        source = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        stripped = re.sub(r'\nmain "\$@"\s*$', "\n", source)
        self.assertNotEqual(
            stripped, source, "the trailing main invocation must be removed"
        )
        driver.write_text(stripped, encoding="utf-8")
        result = subprocess.run(
            ["bash", "-c", 'source "$0"; install_release "$1"', str(driver), CANDIDATE],
            cwd=ROOT,
            env=self.env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn(
            "operator-common.css",
            result.stdout,
            "a non-referencing neither-state release must not be rejected: "
            + result.stdout,
        )
        # Coherent live state: the non-referencing page is promoted ...
        self.assertEqual(
            self.operator.read_text(encoding="utf-8"), f"operator {CANDIDATE}\n"
        )
        # ... the stylesheet it does not link is removed (no dangling asset,
        # and no staged .next survives activation) ...
        self.assertFalse(
            self.operator_css.exists(),
            "the live stylesheet must be removed for a prefeature release",
        )
        self.assertFalse((self.live / f"{CSS_RELATIVE}.next").exists())
        # ... and the release itself keeps its neither state (install_release
        # must not silently annotate it — that is the capture's job).
        self.assertFalse(release_css.exists())
        self.assertFalse((release_css.parent / "operator-common.css.absent").exists())

    # -- activation ordering -------------------------------------------------

    def test_upgrade_activates_the_shared_css_before_the_operator_html(
        self,
    ) -> None:
        order_log = self.install_activation_order_log()
        result = self.run_deploy(extra_env={"FAKE_ORDER_LOG": str(order_log)})
        self.assertEqual(result.returncode, 0, result.stdout)
        order = order_log.read_text(encoding="utf-8").splitlines()
        css_mv = f"mv -f {self.operator_css}.next {self.operator_css}"
        html_mv = f"mv -f {self.operator}.next {self.operator}"
        self.assertIn(css_mv, order, "the staged stylesheet must be promoted: " + result.stdout)
        self.assertIn(html_mv, order, result.stdout)
        self.assertLess(
            order.index(css_mv),
            order.index(html_mv),
            "the shared CSS must be live BEFORE the HTML that links it",
        )

    def test_downgrade_restores_the_html_before_removing_the_shared_css(
        self,
    ) -> None:
        # Rollback target: explicit .absent marker, non-referencing HTML, and
        # a live stylesheet left behind by the candidate upgrade — the real
        # removal case. The referencing HTML must be restored first.
        self.release_css(OLD).unlink()
        (self.releases / OLD / f"{CSS_RELATIVE}.absent").touch()
        order_log = self.install_activation_order_log()
        result = self.run_deploy(
            mode="fail-candidate", extra_env={"FAKE_ORDER_LOG": str(order_log)}
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Rollback successful", result.stdout)
        order = order_log.read_text(encoding="utf-8").splitlines()
        html_mv = f"mv -f {self.operator}.next {self.operator}"
        css_rm = f"rm -f {self.operator_css} {self.operator_css}.next"
        self.assertIn(html_mv, order, result.stdout)
        self.assertIn(css_rm, order, "the live stylesheet must be removed: " + result.stdout)
        last_html_restore = max(
            index for index, line in enumerate(order) if line == html_mv
        )
        self.assertLess(
            last_html_restore,
            order.index(css_rm),
            "the HTML must be restored BEFORE the shared CSS is removed",
        )
        self.assertFalse(self.operator_css.exists())
        self.assertEqual(self.operator.read_text(encoding="utf-8"), f"operator {OLD}\n")
        self.assertIn(
            "Operator common stylesheet is absent in this rollback release",
            result.stdout,
        )

    # -- post-activation public smoke ----------------------------------------

    def test_verify_frontends_smoke_accepts_auth_redirect_but_fails_on_broken_css(
        self,
    ) -> None:
        # Corrected contract after the production incident (deploy run
        # 45075776142): the whole /sea-speed/* tree sits behind the operator
        # auth boundary, so the stylesheet URL answers the same 302 auth
        # redirect as every sibling operator asset. verify_public_url
        # (200|301|302|307|308|401|403) is the correct bar for it — a strict
        # 200-only check rejected the expected redirect and rolled back a
        # healthy deploy — while `|| return 1` keeps genuinely broken
        # responses (404/500) fail-closed, which is what SDD TX-004's FATAL
        # disposition is about: not rejecting auth redirects.
        #
        # The failure line is matched in both message shapes because
        # verify_public_url says "public smoke check failed" while
        # verify_public_asset_200 says "public asset smoke check failed" —
        # RED against a strict-200 variant, whose rejection of 302/401 fails
        # the accepted-redirect subtests below. The empty-live-file guard IS
        # fatal and stays source-pinned (the harness cannot produce an empty
        # live asset).
        self.install_css_status_curl()

        # Broken responses must fail closed: nonzero rc, rollback to OLD,
        # manifest rolled_back.
        for status in ("500", "404"):
            with self.subTest(broken=status):
                result = self.run_deploy(extra_env={"FAKE_CSS_URL_STATUS": status})
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertRegex(
                    result.stdout,
                    rf"Operator common stylesheet public(?: asset)? smoke check "
                    rf"failed with HTTP {status}\b",
                    "verify_frontends must report the stylesheet verdict",
                )
                self.assertEqual(self.current(), OLD, result.stdout)
                self.assertIn("Rollback successful", result.stdout)
                self.assertEqual(
                    self.manifest()["state"], "rolled_back", result.stdout
                )

        # Auth-boundary answers are the healthy contract for an operator
        # asset: the deploy succeeds and the accepted verdict is reported.
        for status in ("302", "401"):
            with self.subTest(auth=status):
                result = self.run_deploy(extra_env={"FAKE_CSS_URL_STATUS": status})
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn(
                    f"Operator common stylesheet public smoke check passed with "
                    f"HTTP {status}",
                    result.stdout,
                )
                self.assertEqual(self.current(), CANDIDATE, result.stdout)
                self.assertEqual(
                    self.manifest()["state"], "runtime_verified", result.stdout
                )

        result = self.run_deploy(extra_env={"FAKE_CSS_URL_STATUS": "200"})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "Operator common stylesheet public smoke check passed with HTTP 200",
            result.stdout,
        )
        self.assertEqual(self.current(), CANDIDATE, result.stdout)
        self.assertEqual(self.manifest()["state"], "runtime_verified", result.stdout)

    # -- source pins with stated reason -------------------------------------

    def test_deploy_defines_the_css_targets_and_verify_guard(self) -> None:
        # Behavioral tests prove promotion, ordering and the URL smoke; they
        # cannot prove the deploy's DEFAULT target/URL defaults (the harness
        # overrides both) nor the empty-file guard inside verify_frontends
        # (the harness never produces an empty live asset), so those stay
        # source pins with this stated reason.
        source = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            'OPERATOR_COMMON_CSS_TARGET="${SEA_SPEED_OPERATOR_COMMON_CSS_TARGET:'
            '-/var/www/mostdef.ru/sea-speed/operator-common.css}"',
            source,
        )
        self.assertIn(
            'OPERATOR_COMMON_CSS_URL="${SEA_SPEED_OPERATOR_COMMON_CSS_URL:'
            '-https://mostdef.ru/sea-speed/operator-common.css}"',
            source,
        )
        bodies = self.shell_function_bodies()
        self.assertIn(
            '-f "$root/frontend/sea-speed/operator-common.css"',
            bodies["release_complete"],
            "release_complete must require the shared stylesheet file",
        )
        download = bodies["download_release"]
        self.assertIn("frontend/sea-speed/operator-common.css", download)
        self.assertIn(
            f'install -m 0644 "$extracted/{CSS_RELATIVE}" "$TARGET_RELEASE/{CSS_RELATIVE}"',
            download,
            "download_release must install the shared stylesheet into the release",
        )
        verify = bodies["verify_frontends"]
        self.assertIn(
            '[[ -s "$OPERATOR_COMMON_CSS_TARGET" ]]',
            verify,
            "verify_frontends must reject an empty live stylesheet",
        )
        # Issue #685 corrected contract (production run 45075776142): the
        # stylesheet sits behind the operator auth boundary like every sibling
        # operator asset, so the smoke uses the permissive operator-asset
        # verifier (200|301|302|307|308|401|403) — a strict 200-only bar
        # rejected the expected auth redirect and rolled back a healthy
        # deploy — while `|| return 1` keeps broken responses fail-closed.
        self.assertIn(
            'verify_public_url "Operator common stylesheet" '
            '"$OPERATOR_COMMON_CSS_URL" || return 1',
            verify,
            "verify_frontends must smoke-check the stylesheet with the "
            "operator-asset verifier and fail closed on a broken response",
        )


if __name__ == "__main__":
    unittest.main()
