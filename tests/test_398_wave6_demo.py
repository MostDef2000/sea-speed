"""Issue #398 wave 6 demo: section-scoped text twins vs raw source-text pins.

Target check: the converted MediaMTX compatibility-remediation runbook
contract (docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md — the blocker
classification co-located in "Why this exists", the official-release
provenance co-located in "Candidate provenance", the canary contract in its
dedicated section, the final rollout scope bundle in its own section, the
worker non-mutation ban and the rollback prohibition co-located in
"Production binary activation").

Two-direction proof, mirroring the wave-1..5 demos, with one wave-6-specific
honesty note: the wave-6 twins are SECTION-SCOPED TEXT anchors whose needles
ARE the retired pin strings (case-insensitive per tests/support/markdown_docs.py,
with the gate/policy tokens enforced EXACT-CASE against the raw section text —
"MoQ", "CONFIRM_NEW_CAMERA", "one OpenCode rollout scope"), unlike the
parsed/executed twins of waves 4/5. The 12 retired pins therefore split into
two verdict classes under a refactor:

- 10 "vocabulary" pins whose strings are contract identifiers the twins
  match on: they fail only under refactors that ALTER those identifiers —
  including case changes, which the twins enforce exact-case for the
  gate/policy tokens above. An identifier-preserving refactor passes them,
  so they CANNOT fail Direction A without dishonestly mangling identifiers
  the contract itself matches on (deviation from the wave-4/5 "every pin
  fails" letter, flagged to the orchestrator);
- 2 "prose-form" pins whose exact casing/wording is editorial while the twin
  matches case-insensitively or via the section heading: the lowercase
  "loopback-only compatibility canary" prose references (the twin anchors on
  the case-insensitive HEADING) and the sentence-initial capital of
  "Automatic rollback remains prohibited" (the twin matches
  case-insensitively). These fail under editorial rewording the twins
  tolerate.

- Direction A (refactor tolerance): a tmp copy of the real runbook rewritten
  meaning-preservingly (the two lowercase canary prose references reworded to
  "compatibility trial", the rollback prohibition joined into the preceding
  sentence so it is no longer sentence-initial) still satisfies every
  section-scoped twin, while EXACTLY the 2 prose-form retired pins fail on it
  and the 10 vocabulary pins still pass.
- Direction B (dead-marker intolerance): a tmp copy that keeps ALL 12 retired
  markers verbatim but breaks the placement contract six ways (the
  classification clause, the checksums sentence, the canary proof item, the
  confirmation-gate step, the worker non-mutation sentence and the rollback
  caveat each separated from their required co-marker or section) passes
  every retired text pin — the false green the conversion removes — and
  FAILS all six twin groups.

Inverted-mutation proofs are asserted in-demo for both directions: skipping
the rollback sentence-join makes the rollback pin pass again (Direction A
verdict inverts to 1 of 2), and skipping the rollback-caveat split makes the
rollback twin pass again (Direction B verdict inverts to 5 of 6).

Both directions run against tmp copies only; docs/ is never modified.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.support import markdown_docs  # noqa: E402

DOC = ROOT / "docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md"

# The retired raw-text pins of the converted documentation test (issue #398
# wave 6, test_mediamtx_compatibility_remediation.py), restated here for the
# two-direction proof.
RETIRED_TEXT_PINS = (
    "E_RTSP_HANDSHAKE_COMPATIBILITY",
    "official `bluenviron/mediamtx` release",
    "checksums.sha256",
    "loopback-only compatibility canary",
    "sandboxed active-config compatibility proof",
    "MoQ",
    "/cams/hls/cam1/index.m3u8",
    "CONFIRM_NEW_CAMERA",
    "cam1-new",
    "sea-speed-worker.service",
    "Automatic rollback remains prohibited",
    "one OpenCode rollout scope",
)

# The subset whose exact form is editorial prose rather than contract
# vocabulary: these fail under editorial rewording the twins tolerate, while
# the vocabulary pins fail only under refactors that alter the contract
# identifiers themselves (see module docstring).
PROSE_FORM_PINS = (
    "loopback-only compatibility canary",
    "Automatic rollback remains prohibited",
)

# The six section-scoped twin groups of the converted test, in assertion
# order.
TWIN_GROUPS = (
    "blocker-classification-co-location",
    "provenance-co-location",
    "canary-section-contract",
    "final-scope-bundle",
    "worker-non-mutation-co-location",
    "rollback-prohibition-co-location",
)


def _replace_exact(source: str, old: str, new: str) -> str:
    assert old in source, f"demo anchor drifted: {old[:70]!r}"
    return source.replace(old, new, 1)


def _ss_twin_failures(source: str) -> list[str]:
    """Run the converted section-scoped twins against a doc copy.

    1:1 replica of the frozen twins in
    test_mediamtx_compatibility_remediation.py
    (test_documentation_defines_single_final_live_completion_flow).
    """
    failed: list[str] = []
    if (
        markdown_docs.section_containing(
            source, "E_RTSP_HANDSHAKE_COMPATIBILITY", "required action class"
        )
        is None
    ):
        failed.append("blocker-classification-co-location")
    if (
        markdown_docs.section_containing(
            source, "official `bluenviron/mediamtx` release", "checksums.sha256"
        )
        is None
    ):
        failed.append("provenance-co-location")
    canary_section = markdown_docs.section_titled(
        source, "loopback-only compatibility canary"
    )
    if canary_section is None:
        failed.append("canary-section-contract")
    else:
        canary_lower = (canary_section[0] + canary_section[1]).lower()
        if (
            "moq" not in canary_lower
            or "disabled" not in canary_lower
            or "127.0.0.1:18954" not in canary_section[1]
            or "sandboxed active-config compatibility proof" not in canary_lower
        ):
            failed.append("canary-section-contract")
    scope_section = markdown_docs.section_titled(
        source, "one final camera 1 completion scope"
    )
    if scope_section is None:
        failed.append("final-scope-bundle")
    else:
        scope_lower = (scope_section[0] + scope_section[1]).lower()
        for marker in (
            "one opencode rollout scope",
            "confirm_new_camera",
            "cam1-new",
            "/cams/hls/cam1/index.m3u8",
            "basic auth challenge",
            "human visual acceptance",
        ):
            if marker not in scope_lower:
                failed.append("final-scope-bundle")
                break
    if (
        markdown_docs.section_containing(
            source, "sea-speed-worker.service", "never starts, stops, restarts or enables"
        )
        is None
    ):
        failed.append("worker-non-mutation-co-location")
    if (
        markdown_docs.section_containing(
            source, "Automatic rollback remains prohibited", "separate governed decision"
        )
        is None
    ):
        failed.append("rollback-prohibition-co-location")
    return failed


def _retired_pin_failures(source: str) -> list[str]:
    """Run the RETIRED raw-text pins against a doc copy (demo only)."""
    return [pin for pin in RETIRED_TEXT_PINS if pin not in source]


def _refactored_doc(source: str, rollback_rewrite: bool = True) -> str:
    """Direction A: meaning-preserving editorial refactor of a tmp copy.

    Each rewrite preserves meaning exactly: the two lowercase prose
    references to the canary are reworded to an equivalent noun phrase (the
    twin anchors on the case-insensitive section HEADING, not this prose),
    and the rollback prohibition is joined into the preceding sentence so it
    is no longer sentence-initial (the twin matches case-insensitively).
    """
    source = _replace_exact(
        source,
        "performs a loopback-only compatibility canary and,"
        " only after that canary succeeds,",
        "performs a loopback-only compatibility trial and,"
        " only after that trial succeeds,",
    )
    source = _replace_exact(
        source,
        "then run the loopback-only compatibility canary;",
        "then run the loopback-only compatibility trial;",
    )
    if rollback_rewrite:
        source = _replace_exact(
            source,
            "without another restart. Automatic rollback remains prohibited;"
            " rollback is a separate governed decision.",
            "without another restart; automatic rollback remains prohibited,"
            " and rollback is a separate governed decision.",
        )
    return source


def _marker_only_broken_doc(source: str, split_rollback: bool = True) -> str:
    """Direction B: keep ALL retired markers verbatim, break placement 6 ways.

    B1 the blocker classification clause leaves "Why this exists" (its
    "required action class" co-marker moves to Components); B2 the
    checksums.sha256 provenance sentence leaves "Candidate provenance"; B3
    the sandboxed active-config proof item leaves the canary section; B4 the
    confirmation-gate step leaves the final scope list; B5 the worker
    non-mutation sentence is split from the ``sea-speed-worker.service`` unit
    name; B6 the rollback caveat is separated from the prohibition. Every
    retired marker survives byte-for-byte, so the raw pins stay green (the
    false-green the conversion removes) while each co-location twin fails.
    """
    # B1: classification clause out of "Why this exists" ...
    source = _replace_exact(
        source,
        "classified the failure as `E_RTSP_HANDSHAKE_COMPATIBILITY` and the"
        " required action class as a MediaMTX version or compatibility change.",
        "classified the failure as `E_RTSP_HANDSHAKE_COMPATIBILITY`.",
    )
    # B5: worker non-mutation sentence split from the unit name ...
    source = _replace_exact(
        source,
        "The script never starts, stops, restarts or enables"
        " `sea-speed-worker.service`.",
        "The script never starts, stops, restarts or enables the AI worker unit.",
    )
    # ... and both markers re-located verbatim into Components.
    source = _replace_exact(
        source,
        "- `docs/operations/CAMERA1_LIVE_REPLACEMENT.md` remains the base"
        " live-source runbook; this document is the compatibility-remediation"
        " supplement for the confirmed source-pull blocker.\n",
        "- `docs/operations/CAMERA1_LIVE_REPLACEMENT.md` remains the base"
        " live-source runbook; this document is the compatibility-remediation"
        " supplement for the confirmed source-pull blocker.\n"
        "\n"
        "The required action class is a MediaMTX version or compatibility"
        " change.\n"
        "\n"
        "`sea-speed-worker.service` is governed separately and is never touched"
        " by this remediation.\n",
    )
    # B2: checksums sentence out of "Candidate provenance" (verbatim move).
    source = _replace_exact(
        source,
        " release for the VPS architecture. OpenCode must obtain the release"
        " archive and the corresponding upstream `checksums.sha256` from the"
        " official release, verify the archive checksum before invoking"
        " repository tooling, and record the exact release version and archive"
        " SHA-256 in sanitized rollout evidence.",
        " release for the VPS architecture.",
    )
    source = _replace_exact(
        source,
        "The canary now explicitly disables MoQ and every other unused server"
        " instead of relying on version-specific defaults.\n",
        "The canary now explicitly disables MoQ and every other unused server"
        " instead of relying on version-specific defaults.\n"
        "\n"
        "OpenCode must obtain the release archive and the corresponding upstream"
        " `checksums.sha256` from the official release, verify the archive"
        " checksum before invoking repository tooling, and record the exact"
        " release version and archive SHA-256 in sanitized rollout evidence.\n",
    )
    # B3: canary proof item out of the canary section ...
    source = _replace_exact(
        source,
        "- exact credential-free relay URL and canonical loopback HLS URL;\n"
        "- a successful sandboxed active-config compatibility proof.\n",
        "- exact credential-free relay URL and canonical loopback HLS URL;\n",
    )
    # B4: confirmation-gate step out of the final scope list ...
    source = _replace_exact(
        source,
        "9. pause for human visual acceptance on `mostdef.ru` and require the"
        " exact text `CONFIRM_NEW_CAMERA` only when the new physical camera is"
        " visibly moving and the AI worker remains offline;\n",
        "",
    )
    # ... and the relocated markers land verbatim in their new (wrong)
    # sections: the proof item in Production binary activation, the
    # confirmation gate in a new trailing section.
    source = _replace_exact(
        source,
        "\n## One final Camera 1 completion scope\n",
        "\nActivation also revalidates a successful sandboxed active-config"
        " compatibility proof.\n\n## One final Camera 1 completion scope\n",
    )
    boundary = (
        "\n## Acceptance boundary\n\nThe rollout pauses for human visual"
        " acceptance on `mostdef.ru` and requires the exact text"
        " `CONFIRM_NEW_CAMERA` only when the new physical camera is visibly"
        " moving and the AI worker remains offline.\n"
    )
    if split_rollback:
        # B6: rollback caveat separated from the prohibition.
        source = _replace_exact(
            source,
            "Automatic rollback remains prohibited; rollback is a separate"
            " governed decision.",
            "Automatic rollback remains prohibited.",
        )
        boundary += "\nRollback remains a separate governed decision.\n"
    source = _replace_exact(
        source,
        "\n## Ubuntu Worker relay API profile\n",
        boundary + "\n## Ubuntu Worker relay API profile\n",
    )
    return source


class Test398Wave6Demo(unittest.TestCase):
    def test_refactor_tolerance_and_dead_marker_intolerance(self) -> None:
        real_doc = DOC.read_text(encoding="utf-8")
        # Sanity: the real runbook satisfies every section-scoped twin and
        # (trivially) every retired pin.
        self.assertEqual(
            _ss_twin_failures(real_doc),
            [],
            "real runbook must satisfy the section-scoped twins",
        )
        self.assertEqual(
            _retired_pin_failures(real_doc),
            [],
            "real runbook must satisfy the retired pins",
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Direction A: meaning-preserving refactor of a tmp copy.
            refactored = _refactored_doc(real_doc)
            (tmp_path / "refactored.md").write_text(refactored, encoding="utf-8")
            twin_failed = _ss_twin_failures(refactored)
            pin_failed = _retired_pin_failures(refactored)
            self.assertEqual(
                twin_failed,
                [],
                f"section-scoped twins must tolerate a pure refactor: {twin_failed}",
            )
            # Exactly the 2 prose-form pins fail; the 10 vocabulary pins
            # carry the contract identifiers the twins match on, so they fail
            # only under refactors that alter those identifiers (including
            # case drift, enforced exact-case by the twins) — not under the
            # identifier-preserving editorial rewording this direction
            # applies (documented deviation, see module docstring).
            self.assertEqual(
                pin_failed,
                list(PROSE_FORM_PINS),
                "exactly the prose-form pins must fail the refactor: "
                f"{pin_failed}",
            )
            # Inverted mutation (Direction A): keep the rollback sentence
            # verbatim and the rollback pin's verdict inverts back to pass.
            refactored_kept = _refactored_doc(real_doc, rollback_rewrite=False)
            self.assertEqual(_ss_twin_failures(refactored_kept), [])
            self.assertEqual(
                _retired_pin_failures(refactored_kept),
                ["loopback-only compatibility canary"],
                "with the rollback rewrite flipped off, the rollback pin must "
                "pass again (inverted-mutation proof)",
            )
            # Direction B: markers verbatim, placement broken six ways.
            broken = _marker_only_broken_doc(real_doc)
            (tmp_path / "broken.md").write_text(broken, encoding="utf-8")
            broken_twin_failed = _ss_twin_failures(broken)
            broken_pin_failed = _retired_pin_failures(broken)
            self.assertEqual(
                broken_pin_failed,
                [],
                "all 12 retired pins pass the marker-only copy (the false "
                f"green the conversion removes): {broken_pin_failed}",
            )
            self.assertEqual(
                broken_twin_failed,
                list(TWIN_GROUPS),
                "every section-scoped twin must fail the placement-broken "
                f"copy: {broken_twin_failed}",
            )
            # Inverted mutation (Direction B): keep the rollback caveat
            # co-located and the rollback twin's verdict inverts back to pass.
            broken_kept = _marker_only_broken_doc(real_doc, split_rollback=False)
            self.assertEqual(
                _ss_twin_failures(broken_kept),
                [
                    group
                    for group in TWIN_GROUPS
                    if group != "rollback-prohibition-co-location"
                ],
                "with the rollback split flipped off, the rollback twin must "
                "pass again (inverted-mutation proof)",
            )
        # The repo doc was never mutated by the demo.
        self.assertEqual(DOC.read_text(encoding="utf-8"), real_doc)


if __name__ == "__main__":
    unittest.main()
