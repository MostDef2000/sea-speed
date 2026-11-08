"""RED regression battery: Security scanning is causally required by Quality.

Issue #576 (source-only scope, base 60c17502).  Target contract under test:

* ``.github/workflows/security.yml`` keeps its existing events, scanner
  jobs, pins, commands, targets, timeouts, read permission and
  concurrency prefix; it gains ``workflow_call`` and a terminal
  ``security-result`` job that needs BOTH scanners, runs ``if: always()``,
  binds each scanner result through an actual ``needs.<id>.result`` env
  expression, and whose shell requires both to be literally ``success``.
* ``.github/workflows/quality-integration.yml`` gains an unconditional
  ``security`` job calling ``./.github/workflows/security.yml``; the
  ``quality-integration`` aggregate gains ``security`` as a fifth
  mandatory need with the same strict-success treatment.  The four
  existing domains stay mandatory.

On the current base none of that wiring exists, so the wiring and
security-rejection cases are RED now and turn GREEN only through the
production workflow edits.  The pin/protection and mutation-sensitivity
cases pass on the base and must keep passing.  Shell cases execute the
ACTUAL run blocks through bash with env built from the ACTUAL parsed
bindings; the merge decision is never re-implemented in Python.
"""

from __future__ import annotations

import copy
import os
import re
import subprocess
import unittest
from pathlib import Path
from typing import Any

try:
    import yaml  # noqa: F401
    HAS_YAML = True
except ModuleNotFoundError:  # pragma: no cover - PyYAML is installed in this repo
    HAS_YAML = False

ROOT = Path(__file__).resolve().parents[2]
SECURITY_YML = ROOT / ".github/workflows/security.yml"
QUALITY_YML = ROOT / ".github/workflows/quality-integration.yml"

SECURITY_TARGET = "./.github/workflows/security.yml"
SCANNER_JOBS = ("secret-scan", "dependency-audit")
TERMINAL_JOB = "security-result"
CALL_JOB = "security"
AGGREGATE_JOB = "quality-integration"
OLD_DOMAINS = (
    "static-contract-security",
    "property-fuzz-reliability",
    "exact-artifact-e2e",
    "release-deployment-evidence",
)
NON_SUCCESS = ("failure", "failed", "skipped", "cancelled", "", "unexpected")
GITLEAKS_VERSION = "8.30.0"
GITLEAKS_SHA256 = "79a3ab579b53f71efd634f3aaf7e04a0fa0cf206b7ed434638d1547a2470a66e"
CHECKOUT_PIN = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
UPLOAD_PIN = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
SETUP_PYTHON_PIN = "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065"
GITLEAKS_DETECT_LINE = "./gitleaks detect --source . --report-format sarif --report-path gitleaks-report.sarif --redact -v"
AUDIT_WORKER_LINE = "pip-audit -r deploy/worker/ubuntu/requirements-runtime.txt"
AUDIT_API_LINE = "pip-audit -r api/requirements-api.txt"
# Only a DIRECT `needs.<id>.result` expression counts as a binding: a masked
# expression such as `needs.x.result == 'success' && 'success' || 'success'`
# would always evaluate to success on GitHub, so it must fail the probes
# instead of being emulated as a raw result.
BINDING_RE = re.compile(r"\$\{\{\s*needs\.([A-Za-z0-9_-]+)\.result\s*\}\}")


def _binding_need(expr: str):
    match = BINDING_RE.fullmatch(str(expr))
    return match.group(1) if match else None


def _yaml_load(path: Path) -> Any:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _events(wf: dict) -> set:
    on = wf.get("on", wf.get(True))  # PyYAML reads the `on:` key as True
    if isinstance(on, dict):
        return set(on)
    if isinstance(on, list):
        return set(on)
    return {on}


def _needs(job: dict) -> list:
    needs = job.get("needs")
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    return list(needs)


def _job(wf: dict, job_id: str) -> dict:
    job = (wf.get("jobs") or {}).get(job_id)
    assert job is not None, f"job {job_id!r} is missing from the workflow"
    return job


def _run_block(job: dict) -> str:
    runs = [s.get("run") for s in (job.get("steps") or []) if isinstance(s, dict) and s.get("run")]
    assert len(runs) == 1, f"expected exactly one run step, found {len(runs)}"
    return runs[0]


def _bound_results(job: dict) -> dict:
    """need-id -> env var name, from the job's actual env binding expressions."""
    mapping = {}
    envs = [job.get("env")]
    for step in job.get("steps") or []:
        if isinstance(step, dict) and step.get("env"):
            envs.append(step["env"])
    for env in envs:
        for var, expr in (env or {}).items():
            need_id = _binding_need(expr)
            if need_id:
                mapping[need_id] = str(var)
    return mapping


def _run_shell(job: dict, results: dict) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "C.UTF-8",
    }
    for need_id, var in _bound_results(job).items():
        env[var] = results.get(need_id, "")
    return subprocess.run(
        ["bash", "-c", _run_block(job)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@unittest.skipUnless(HAS_YAML, "PyYAML not installed; this module requires the test-only parser")
class SecurityMergeGateTests(unittest.TestCase):
    # -- structural predicates (shared by baseline checks and mutants) ----

    def _assert_scanner_job_clean(self, job: dict) -> None:
        label = job.get("name", "scanner")
        self.assertNotIn("continue-on-error", job, f"{label} job has a continue-on-error bypass")
        self.assertNotIn("if", job, f"{label} job has a conditional bypass")
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            step_label = f"{label} step {step.get('name', '?')}"
            self.assertNotIn("continue-on-error", step, f"{step_label} has a continue-on-error bypass")
            if step.get("run"):
                self.assertNotIn("if", step, f"{step_label} run step has a conditional bypass")

    def _assert_scanner_pins(self, wf: dict) -> None:
        jobs = wf.get("jobs") or {}
        scan = jobs.get("secret-scan")
        self.assertIsNotNone(scan, "secret-scan job missing")
        self._assert_scanner_job_clean(scan)
        self.assertEqual(scan.get("name"), "Gitleaks full-history secret scan")
        self.assertEqual(scan.get("timeout-minutes"), 10)
        scan_runs = " ".join(s.get("run", "") for s in scan.get("steps", []) if isinstance(s, dict) and s.get("run"))
        self.assertIn(GITLEAKS_VERSION, scan_runs, "gitleaks version pin missing")
        self.assertIn(GITLEAKS_SHA256, scan_runs, "gitleaks checksum pin missing")
        scan_lines = [line for s in scan.get("steps", []) if isinstance(s, dict) and s.get("run") for line in str(s["run"]).splitlines()]
        self.assertIn(GITLEAKS_DETECT_LINE, scan_lines, "gitleaks detect command line altered or masked")
        audit = jobs.get("dependency-audit")
        self.assertIsNotNone(audit, "dependency-audit job missing")
        self._assert_scanner_job_clean(audit)
        self.assertEqual(audit.get("name"), "pip-audit worker runtime requirements")
        self.assertEqual(audit.get("timeout-minutes"), 10)
        audit_lines = [line for s in audit.get("steps", []) if isinstance(s, dict) and s.get("run") for line in str(s["run"]).splitlines()]
        self.assertIn(AUDIT_WORKER_LINE, audit_lines, "worker pip-audit command line altered or masked")
        self.assertIn(AUDIT_API_LINE, audit_lines, "api pip-audit command line altered or masked")
        for job, pins in ((scan, (CHECKOUT_PIN, UPLOAD_PIN)), (audit, (CHECKOUT_PIN, SETUP_PYTHON_PIN))):
            uses = [s.get("uses") for s in job.get("steps", []) if isinstance(s, dict) and s.get("uses")]
            for pin in pins:
                self.assertIn(pin, uses, f"action pin {pin} missing")

    def _assert_read_only(self, wf: dict) -> None:
        self.assertEqual(wf.get("permissions"), {"contents": "read"}, "workflow permissions must stay exactly contents: read")
        for job_id, job in (wf.get("jobs") or {}).items():
            if isinstance(job, dict):
                self.assertNotIn("permissions", job, f"job {job_id} overrides workflow permissions")

    def _assert_call_job_clean(self, job: dict) -> None:
        self.assertEqual(job.get("uses"), SECURITY_TARGET, "security call must use the local security workflow")
        self.assertNotIn("if", job, "security call must be unconditional")
        self.assertNotIn("continue-on-error", job, "security call must not swallow failures")
        self.assertNotIn("secrets", job, "security call must not inherit or request secrets")
        self.assertNotIn("permissions", job, "security call must not raise permissions")

    def _assert_gate_steps_clean(self, job: dict) -> None:
        for step in job.get("steps") or []:
            if isinstance(step, dict) and step.get("run"):
                label = f"gate step {step.get('name', '?')}"
                self.assertNotIn("if", step, f"{label} run step has a conditional bypass")
                self.assertNotIn("continue-on-error", step, f"{label} run step masks failures")

    def _assert_concurrency(self, wf: dict, prefix: str) -> None:
        group = str((wf.get("concurrency") or {}).get("group", ""))
        self.assertTrue(group.startswith(prefix), f"concurrency group {group!r} lost prefix {prefix!r}")

    def _assert_accepts_success(self, job: dict, results: dict) -> None:
        proc = _run_shell(job, results)
        self.assertEqual(proc.returncode, 0, f"shell rejected {results} (rc={proc.returncode})\n{proc.stdout}{proc.stderr}")

    def _assert_rejects_non_success(self, job: dict, results: dict) -> None:
        proc = _run_shell(job, results)
        self.assertNotEqual(proc.returncode, 0, f"shell accepted {results} (rc={proc.returncode})\n{proc.stdout}{proc.stderr}")

    # -- 1. security.yml wiring (RED on base: no workflow_call, no terminal) --

    def test_security_workflow_shape(self) -> None:
        wf = _yaml_load(SECURITY_YML)
        events = _events(wf)
        for kept in ("pull_request", "push", "workflow_dispatch"):
            with self.subTest(kept=kept):
                self.assertIn(kept, events, "existing security event removed")
        with self.subTest(event="workflow_call"):
            self.assertIn("workflow_call", events, "security.yml must be callable from Quality")
        job = _job(wf, TERMINAL_JOB)
        self.assertEqual(sorted(_needs(job)), sorted(SCANNER_JOBS), "terminal must need both scanners")
        self.assertEqual(str(job.get("if")), "always()", "terminal must run if: always()")
        self.assertNotIn("continue-on-error", job, "terminal must not swallow failures")
        self.assertNotIn("secrets", job, "terminal must not request secrets")
        self.assertNotIn("permissions", job, "terminal must not raise permissions")
        self._assert_gate_steps_clean(job)
        bound = _bound_results(job)
        run = _run_block(job)
        for sid in SCANNER_JOBS:
            var = bound.get(sid)
            with self.subTest(bound=sid):
                self.assertIsNotNone(var, f"no env binding for needs.{sid}.result")
            if var is not None:
                with self.subTest(run_ref=sid):
                    self.assertIn(var, run, f"run block does not reference {var}")
        self._assert_read_only(wf)

    # -- 2. security terminal shell behavior (RED on base: job missing) ----

    def test_security_terminal_shell_behavior(self) -> None:
        wf = _yaml_load(SECURITY_YML)
        job = _job(wf, TERMINAL_JOB)
        ok = {sid: "success" for sid in SCANNER_JOBS}
        self._assert_accepts_success(job, ok)
        for sid in SCANNER_JOBS:
            for value in NON_SUCCESS:
                results = dict(ok)
                results[sid] = value
                with self.subTest(scanner=sid, result=value):
                    self._assert_rejects_non_success(job, results)

    # -- 3. quality-integration.yml wiring (RED on base: no call job) ------

    def test_quality_wiring_shape(self) -> None:
        wf = _yaml_load(QUALITY_YML)
        events = _events(wf)
        for kept in ("pull_request", "push", "workflow_dispatch"):
            with self.subTest(kept=kept):
                self.assertIn(kept, events, "existing quality event removed")
        for dom in OLD_DOMAINS:
            with self.subTest(domain=dom):
                self.assertIn(dom, wf.get("jobs") or {}, f"domain job {dom} removed")
        call = _job(wf, CALL_JOB)
        self._assert_call_job_clean(call)
        agg = _job(wf, AGGREGATE_JOB)
        self.assertEqual(str(agg.get("if")), "always()")
        self.assertEqual(sorted(_needs(agg)), sorted(OLD_DOMAINS + (CALL_JOB,)), "aggregate must need the four domains plus security")
        self._assert_gate_steps_clean(agg)
        bound = _bound_results(agg)
        run = _run_block(agg)
        for need in OLD_DOMAINS + (CALL_JOB,):
            var = bound.get(need)
            with self.subTest(bound=need):
                self.assertIsNotNone(var, f"no env binding for needs.{need}.result")
            if var is not None:
                with self.subTest(run_ref=need):
                    self.assertIn(var, run, f"run block does not reference {var}")

    # -- 4. quality aggregate shell behavior (key RED: security ignored) ---

    def test_quality_aggregate_shell_behavior(self) -> None:
        wf = _yaml_load(QUALITY_YML)
        agg = _job(wf, AGGREGATE_JOB)
        all_ok = {need: "success" for need in OLD_DOMAINS + (CALL_JOB,)}
        self._assert_accepts_success(agg, all_ok)
        for value in NON_SUCCESS:
            results = dict(all_ok)
            results[CALL_JOB] = value
            with self.subTest(security=value):
                self._assert_rejects_non_success(agg, results)
        for dom in OLD_DOMAINS:
            results = dict(all_ok)
            results[dom] = "failure"
            with self.subTest(domain=dom):
                self._assert_rejects_non_success(agg, results)

    # -- 5. baseline protections (green on base, must stay green) ----------

    def test_baseline_protections(self) -> None:
        sec = _yaml_load(SECURITY_YML)
        self._assert_scanner_pins(sec)
        self._assert_read_only(sec)
        self._assert_concurrency(sec, "security-")
        qwf = _yaml_load(QUALITY_YML)
        self._assert_read_only(qwf)
        self._assert_concurrency(qwf, "quality-integration-")
        agg = _job(qwf, AGGREGATE_JOB)
        self.assertEqual(str(agg.get("if")), "always()")
        self._assert_gate_steps_clean(agg)
        needs = set(_needs(agg))
        for dom in OLD_DOMAINS:
            with self.subTest(domain=dom):
                self.assertIn(dom, needs, f"domain {dom} no longer mandatory")
        bound = _bound_results(agg)
        run = _run_block(agg)
        for dom in OLD_DOMAINS:
            var = bound.get(dom)
            with self.subTest(bound=dom):
                self.assertIsNotNone(var, f"no env binding for needs.{dom}.result")
            if var is not None:
                with self.subTest(run_ref=dom):
                    self.assertIn(var, run)

    # -- 6. mutation sensitivity (green on base: mutants must be caught) ---

    def test_mutations_detected(self) -> None:
        sec = _yaml_load(SECURITY_YML)
        qwf = _yaml_load(QUALITY_YML)

        mut = copy.deepcopy(sec)
        for step in mut["jobs"]["secret-scan"]["steps"]:
            if isinstance(step, dict) and GITLEAKS_SHA256 in str(step.get("run", "")):
                step["run"] = step["run"].replace(GITLEAKS_SHA256, "0" * 64)
        with self.subTest(mutant="gitleaks-checksum-tampered"), self.assertRaises(AssertionError):
            self._assert_scanner_pins(mut)

        mut = copy.deepcopy(sec)
        mut["jobs"]["secret-scan"]["continue-on-error"] = True
        with self.subTest(mutant="continue-on-error-added"), self.assertRaises(AssertionError):
            self._assert_scanner_pins(mut)

        mut = copy.deepcopy(sec)
        mut["jobs"]["dependency-audit"]["if"] = "always()"
        with self.subTest(mutant="scanner-condition-added"), self.assertRaises(AssertionError):
            self._assert_scanner_pins(mut)

        mut = copy.deepcopy(sec)
        mut["permissions"]["contents"] = "write"
        with self.subTest(mutant="permission-weakened"), self.assertRaises(AssertionError):
            self._assert_read_only(mut)

        mut = copy.deepcopy(sec)
        mut["concurrency"]["group"] = "other-${{ github.workflow }}-${{ github.ref }}"
        with self.subTest(mutant="concurrency-prefix-changed"), self.assertRaises(AssertionError):
            self._assert_concurrency(mut, "security-")

        mut = copy.deepcopy(qwf)
        step = next(s for s in mut["jobs"][AGGREGATE_JOB]["steps"] if isinstance(s, dict) and s.get("env"))
        victim = None
        for var, expr in step["env"].items():
            if _binding_need(expr) == OLD_DOMAINS[0]:
                victim = var
                break
        self.assertIsNotNone(victim, "aggregate env binding for the first domain not found")
        del step["env"][victim]
        with self.subTest(mutant="aggregate-binding-removed"), self.assertRaises(AssertionError):
            self._assert_accepts_success(mut["jobs"][AGGREGATE_JOB], {d: "success" for d in OLD_DOMAINS + (CALL_JOB,)})

        mut = copy.deepcopy(qwf)
        mut["jobs"][AGGREGATE_JOB]["steps"][0]["run"] = "exit 0"
        failing = {d: "success" for d in OLD_DOMAINS + (CALL_JOB,)}
        failing[OLD_DOMAINS[0]] = "failure"
        with self.subTest(mutant="aggregate-assert-removed"), self.assertRaises(AssertionError):
            self._assert_rejects_non_success(mut["jobs"][AGGREGATE_JOB], failing)

        mut = copy.deepcopy(qwf)
        mut["jobs"][AGGREGATE_JOB]["steps"][0]["env"][victim] = (
            "${{ needs.static-contract-security.result == 'success' && 'success' || 'success' }}"
        )
        with self.subTest(mutant="masked-binding-expression"), self.assertRaises(AssertionError):
            self._assert_accepts_success(mut["jobs"][AGGREGATE_JOB], {d: "success" for d in OLD_DOMAINS + (CALL_JOB,)})

        mut = copy.deepcopy(qwf)
        mut["jobs"][CALL_JOB] = {"uses": SECURITY_TARGET, "secrets": "inherit"}
        with self.subTest(mutant="call-secrets-inherit"), self.assertRaises(AssertionError):
            self._assert_call_job_clean(mut["jobs"][CALL_JOB])

        mut = copy.deepcopy(sec)
        for step in mut["jobs"]["secret-scan"]["steps"]:
            if isinstance(step, dict) and "gitleaks detect" in str(step.get("run", "")):
                step["continue-on-error"] = True
        with self.subTest(mutant="scan-step-continue-on-error"), self.assertRaises(AssertionError):
            self._assert_scanner_pins(mut)

        mut = copy.deepcopy(sec)
        for step in mut["jobs"]["dependency-audit"]["steps"]:
            if isinstance(step, dict) and "pip-audit -r api" in str(step.get("run", "")):
                step["if"] = "false"
        with self.subTest(mutant="audit-run-step-if-false"), self.assertRaises(AssertionError):
            self._assert_scanner_pins(mut)

        mut = copy.deepcopy(sec)
        mut["permissions"]["actions"] = "write"
        with self.subTest(mutant="permission-scope-added"), self.assertRaises(AssertionError):
            self._assert_read_only(mut)

        mut = copy.deepcopy(qwf)
        mut["jobs"][AGGREGATE_JOB]["steps"][0]["if"] = "false"
        with self.subTest(mutant="outer-run-step-if-false"), self.assertRaises(AssertionError):
            self._assert_gate_steps_clean(mut["jobs"][AGGREGATE_JOB])

        mut = copy.deepcopy(qwf)
        mut["jobs"][AGGREGATE_JOB]["steps"][0]["continue-on-error"] = True
        with self.subTest(mutant="outer-run-step-continue-on-error"), self.assertRaises(AssertionError):
            self._assert_gate_steps_clean(mut["jobs"][AGGREGATE_JOB])
