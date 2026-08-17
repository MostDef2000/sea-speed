#!/usr/bin/env python3
"""Repository validation entrypoint for Sea Speed CI."""
from __future__ import annotations
import re,subprocess,sys,tempfile
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ALLOWED_TOP_LEVEL={".github",".gitignore",".specify","AGENTS.md","README.md","api","contracts","data","deploy","docs","frontend","schemas","scripts","skills","specs","tests","worker"}
REQUIRED_FILES={
"AGENTS.md","README.md","api/app/main.py","frontend/root/index.html","frontend/sea-speed/index.html","frontend/sea-speed/objects/index.html","frontend/sea-speed/cameras/index.html","frontend/sea-speed/road/index.html",
"worker/analytics_profiles.py","worker/hls_motion_yolo_worker_events.py","worker/hls_motion_yolo_runtime.py",
"contracts/SEA_SPEED_GOVERNANCE.md","contracts/SEA_SPEED_DELIVERY_POLICY.md","contracts/runtime/SEA_SPEED_TASK_RUNTIME.md","contracts/runtime/RELEASE_READINESS_GATE.md",
".specify/memory/constitution.md",".specify/templates/overrides/spec-template.md",".specify/templates/overrides/plan-template.md",".specify/templates/overrides/tasks-template.md","specs/README.md","specs/001-camera-live-pipeline/spec.md","specs/002-sdd-adoption/spec.md","specs/018-water-road-analytics-profiles/spec.md",
"data/contracts/sea-speed-contracts-v1.schema.json","data/contracts/fixtures-v1.json","data/contracts/contract-policy-v1.json","data/contracts/change-control-policy-v1.json","data/quality/quality-gates-v1.json","data/quality/reliability-budget-v1.json","data/quality/accepted-risks-v1.json",
"scripts/ci/validate_change_contract.py","scripts/ci/validate_contracts.py","scripts/ci/validate_sdd.py","scripts/ci/validate_telemetry.py","scripts/release/build_release_manifest.py","scripts/release/validate_release_manifest.py","scripts/release/validate_deployment_manifest.py","scripts/quality/common.py","scripts/quality/validate_quality_contracts.py","scripts/quality/validate_workflow_policy.py","scripts/quality/test_properties.py","scripts/quality/test_fuzz_recovery.py","scripts/quality/build_exact_artifacts.py","scripts/quality/validate_exact_artifacts.py","scripts/quality/build_quality_evidence.py","scripts/quality/validate_quality_evidence.py","scripts/quality/verify_quality_status.py",
"schemas/release-manifest.schema.json","schemas/deployment-manifest.schema.json","schemas/telemetry.schema.json","schemas/quality-evidence.schema.json",
"tests/test_api_contract.py","tests/test_change_contract.py","tests/test_validate_sdd.py","tests/test_worker_contract.py","tests/test_frontend_contract.py","tests/test_release_manifest.py","tests/test_telemetry_contract.py","tests/test_analytics_profiles.py","tests/quality/test_quality_architecture.py",
"docs/quality/testing-policy.md","docs/quality/quality-gate-architecture.md","docs/operations/PRODUCTION_BASELINE.md","docs/operations/RELEASE_PROVENANCE.md","docs/evidence/POST_RELEASE_REVIEW.md","docs/decision_records/DR-003-release-provenance-and-evidence-loop.md",".github/workflows/quality-integration.yml",".github/workflows/deploy-vps.yml",".github/ISSUE_TEMPLATE/loop-engineering.yml",".github/pull_request_template.md"}
FORBIDDEN_DIRECTORY_NAMES={".venv","venv","__pycache__","output","snapshots","overlays"}; FORBIDDEN_PATH_PREFIXES={"worker/runtime","worker/events","worker/output","api/data","api/media"}; FORBIDDEN_FILENAMES={".env",".env.local"}; FORBIDDEN_SUFFIXES={".engine",".jpeg",".jpg",".log",".mkv",".mp4",".onnx",".png",".pt",".pyc"}
SECRET_PATTERNS={"private key":re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),"GitHub token":re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),"AWS access key":re.compile(r"\bAKIA[0-9A-Z]{16}\b"),"hard-coded Sea Speed token":re.compile(r"(?im)^\s*(?:set\s+\"?)?SEA_SPEED_API_TOKEN\s*=\s*[^\s\"']+"),"hard-coded HLS auth":re.compile(r"(?im)^\s*(?:set\s+\"?)?HLS_BASIC_AUTH_BASE64\s*=\s*[^\s\"']+")}
TEXT_SUFFIXES={".cmd",".html",".js",".json",".md",".ps1",".py",".sh",".txt",".yaml",".yml"}
class HtmlStructureValidator(HTMLParser):
 def __init__(self): super().__init__(convert_charrefs=True); self.has_html=self.has_head=self.has_body=False; self.inline_scripts=[]; self._script_buffer=None
 def handle_starttag(self,tag,attrs):
  tag=tag.lower()
  if tag=="html": self.has_html=True
  elif tag=="head": self.has_head=True
  elif tag=="body": self.has_body=True
  elif tag=="script" and not dict(attrs).get("src"): self._script_buffer=[]
 def handle_data(self,data):
  if self._script_buffer is not None:self._script_buffer.append(data)
 def handle_endtag(self,tag):
  if tag.lower()=="script" and self._script_buffer is not None:self.inline_scripts.append("".join(self._script_buffer)); self._script_buffer=None
def fail(message): print(f"ERROR: {message}",file=sys.stderr); raise SystemExit(1)
def tracked_files():
 r=subprocess.run(["git","ls-files","-z"],cwd=ROOT,check=True,capture_output=True); return [Path(x.decode()) for x in r.stdout.split(b"\0") if x]
def validate_paths(files):
 missing=sorted(p for p in REQUIRED_FILES if not (ROOT/p).is_file())
 if missing: fail("required files are missing: "+", ".join(missing))
 for path in files:
  if path.parts[0] not in ALLOWED_TOP_LEVEL: fail(f"unexpected top-level path: {path}")
  normalized=path.as_posix().lower(); dirs={part.lower() for part in path.parts[:-1]}
  if path.name.lower() in FORBIDDEN_FILENAMES: fail(f"local environment file is tracked: {path}")
  if dirs & FORBIDDEN_DIRECTORY_NAMES: fail(f"runtime or local directory is tracked: {path}")
  if any(normalized==prefix or normalized.startswith(prefix+"/") for prefix in FORBIDDEN_PATH_PREFIXES): fail(f"runtime data path is tracked: {path}")
  if path.suffix.lower() in FORBIDDEN_SUFFIXES: fail(f"forbidden generated or binary artifact is tracked: {path}")
def validate_python(files):
 for path in [x for x in files if x.suffix.lower()==".py"]:
  try: compile((ROOT/path).read_text(encoding="utf-8-sig"),str(path),"exec")
  except (SyntaxError,UnicodeDecodeError) as exc: fail(f"Python syntax failed for {path}: {exc}")
def validate_frontend():
 html_paths=[ROOT/"frontend/root/index.html",ROOT/"frontend/sea-speed/index.html",ROOT/"frontend/sea-speed/objects/index.html",ROOT/"frontend/sea-speed/cameras/index.html",ROOT/"frontend/sea-speed/road/index.html"]
 with tempfile.TemporaryDirectory(prefix="sea-speed-js-") as td:
  for html in html_paths:
   parser=HtmlStructureValidator()
   try: parser.feed(html.read_text(encoding="utf-8-sig")); parser.close()
   except Exception as exc: fail(f"HTML parsing failed for {html.relative_to(ROOT)}: {exc}")
   if not (parser.has_html and parser.has_head and parser.has_body): fail(f"frontend HTML must contain html, head and body elements: {html.relative_to(ROOT)}")
   for idx,script in enumerate(parser.inline_scripts,1):
    if not script.strip(): continue
    sp=Path(td)/f"{html.parent.name}-inline-{idx}.js"; sp.write_text(script,encoding="utf-8"); r=subprocess.run(["node","--check",str(sp)],cwd=ROOT,text=True,capture_output=True)
    if r.returncode: fail(f"JavaScript syntax failed for {html.relative_to(ROOT)} inline script {idx}: {(r.stderr or r.stdout).strip()}")
def validate_secrets(files):
 for path in files:
  if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"README.md",".gitignore"}: continue
  try: content=(ROOT/path).read_text(encoding="utf-8-sig")
  except UnicodeDecodeError: fail(f"text file is not valid UTF-8: {path}")
  for label,pattern in SECRET_PATTERNS.items():
   if pattern.search(content): fail(f"possible {label} detected in {path}")
def main():
 files=tracked_files(); validate_paths(files); validate_python(files); validate_frontend(); validate_secrets(files); print("Sea Speed repository validation passed"); print(f"Tracked files checked: {len(files)}"); return 0
if __name__=="__main__": raise SystemExit(main())
