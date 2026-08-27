#!/usr/bin/env python3
"""Validate exact-artifact inventory, digest, extraction safety and syntax."""
from __future__ import annotations
import argparse,json,py_compile,subprocess,sys,tarfile,tempfile
from pathlib import Path,PurePosixPath
if __package__ in (None,""): sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.quality.common import load_json,repository_root,sha256_file
REQUIRED_BY_COMPONENT={
"vps":{"api/app/main.py","frontend/sea-speed/index.html","frontend/sea-speed/objects/index.html","frontend/sea-speed/cameras/index.html","frontend/sea-speed/road/index.html","frontend/root/index.html","deploy/vps/deploy.sh","deploy/vps/sea-speed-auth-cutover.sh","deploy/vps/install-auth-privilege-boundary.sh","deploy/vps/sea-speed-auth-privileged-helper.py","deploy/vps/sea-speed-nginx-zerotier-wait.sh","deploy/vps/sea-speed-nginx-zerotier.conf","scripts/operations/nginx_cam1_direct_h264.py","scripts/operations/nginx_sea_speed_auth.py"},
"ubuntu-worker":{"scripts/worker/check_ubuntu_compatibility.py","worker/analytics_profiles.py","worker/hls_motion_yolo_worker_events.py","worker/hls_motion_yolo_runtime.py","worker/ubuntu_worker_entrypoint.py","worker/ubuntu_ai_inference_worker.py","deploy/worker/ubuntu/install-manual.sh","deploy/worker/ubuntu/install-systemd.sh","deploy/worker/ubuntu/update-exact.sh","deploy/worker/ubuntu/rollback-exact.sh","deploy/worker/ubuntu/deploy-authorized.sh","deploy/worker/ubuntu/preflight.sh","deploy/worker/ubuntu/prepare-runtime.sh","deploy/worker/ubuntu/requirements-runtime.txt","deploy/worker/ubuntu/runtime-lock.json","deploy/worker/ubuntu/worker.env.example","deploy/worker/ubuntu/road-worker.env.example","deploy/worker/ubuntu/sea-speed-worker.service.template","deploy/worker/ubuntu/sea-speed-road-worker.service.template","deploy/worker/ubuntu/sea-speed-worker-control.service.template","deploy/worker/ubuntu/worker-control-agent.py","deploy/worker/ubuntu/observed-worker-runner.py","deploy/worker/ubuntu/verify-runtime-progression.py","deploy/worker/ubuntu/check-worker-health.py","deploy/worker/ubuntu/configure-analytics-profiles.py","deploy/worker/ubuntu/prepare-yolo-model.py"},
"edge":{"worker/analytics_profiles.py","worker/hls_motion_yolo_worker_events.py","worker/hls_motion_yolo_runtime.py"}}
QUALITY_EVIDENCE_COMPONENTS={"vps","edge"}; RELEASE_ONLY_COMPONENTS={"ubuntu-worker"}
WINDOWS_ARCHIVAL_SUFFIXES={".cmd",".ps1"}
def safe_members(archive):
    members=archive.getmembers()
    for m in members:
        p=PurePosixPath(m.name)
        if p.is_absolute() or ".." in p.parts or m.issym() or m.islnk(): raise ValueError(f"unsafe archive member: {m.name}")
    return members
def validate_artifact(root,manifest_path,artifact,seen):
    if not isinstance(artifact,dict): raise SystemExit("exact-artifact entry must be an object")
    component=artifact.get("component")
    if component not in REQUIRED_BY_COMPONENT or component in seen: raise SystemExit(f"unexpected or duplicate exact-artifact component: {component}")
    seen.add(component); archive_path=manifest_path.parent/artifact["filename"]
    if sha256_file(archive_path)!=artifact["sha256"] or archive_path.stat().st_size!=artifact["size"]: raise SystemExit(f"artifact digest/size mismatch: {component}")
    expected={e["path"] for e in artifact["files"]}
    if not REQUIRED_BY_COMPONENT[component].issubset(expected): raise SystemExit(f"required inventory missing from {component}")
    if any(Path(n).suffix.lower() in {".pt",".onnx",".engine"} for n in expected): raise SystemExit("model binaries must not enter exact artifacts")
    if component=="edge" and any(Path(n).suffix.lower() in WINDOWS_ARCHIVAL_SUFFIXES or n.startswith("worker/windows/") for n in expected):
        raise SystemExit("deprecated Windows tooling must not enter exact edge artifacts")
    for e in artifact["files"]:
        source=root/e["path"]
        if sha256_file(source)!=e["sha256"] or source.stat().st_size!=e["size"]: raise SystemExit(f"source inventory mismatch: {e['path']}")
    with tempfile.TemporaryDirectory() as td:
        target=Path(td)
        with tarfile.open(archive_path,"r:gz") as a:
            members=safe_members(a); names={m.name for m in members if m.isfile()}
            if names!=expected: raise SystemExit(f"archive inventory mismatch: {component}")
            a.extractall(target,members=members)
        for py in target.rglob("*.py"): py_compile.compile(str(py),doraise=True)
        if component=="vps":
            for script in (target/"deploy/vps/deploy.sh",target/"deploy/vps/sea-speed-auth-cutover.sh",target/"deploy/vps/install-auth-privilege-boundary.sh",target/"deploy/vps/sea-speed-nginx-zerotier-wait.sh"):
                subprocess.run(["bash","-n",str(script)],check=True)
            for html in [target/"frontend/sea-speed/index.html",target/"frontend/sea-speed/objects/index.html",target/"frontend/sea-speed/cameras/index.html",target/"frontend/sea-speed/road/index.html",target/"frontend/root/index.html"]:
                text=html.read_text(encoding="utf-8-sig").lower()
                if "<html" not in text or "</html>" not in text: raise SystemExit(f"invalid exact HTML artifact: {html}")
        elif component=="ubuntu-worker":
            for script in sorted((target/"deploy/worker/ubuntu").glob("*.sh")): subprocess.run(["bash","-n",str(script)],check=True)
            lock=json.loads((target/"deploy/worker/ubuntu/runtime-lock.json").read_text())
            if lock.get("schema_version")!=1: raise SystemExit("Ubuntu Worker runtime lock schema is invalid")
def main():
    p=argparse.ArgumentParser(); p.add_argument("--manifest",required=True); a=p.parse_args(); root=repository_root(); mp=Path(a.manifest); mp=mp if mp.is_absolute() else root/mp; m=load_json(mp)
    if m.get("schema")!="sea_speed_exact_artifacts_v1": raise SystemExit("unexpected exact-artifact manifest schema")
    qa=m.get("artifacts",[]); ra=m.get("release_artifacts",[])
    if {i.get("component") for i in qa if isinstance(i,dict)}!=QUALITY_EVIDENCE_COMPONENTS or {i.get("component") for i in ra if isinstance(i,dict)}!=RELEASE_ONLY_COMPONENTS: raise SystemExit("exact artifact component set mismatch")
    if len(qa)!=2 or len(ra)!=1: raise SystemExit("exact-artifact manifest must contain two quality artifacts and one Ubuntu release artifact")
    seen=set()
    for artifact in [*qa,*ra]: validate_artifact(root,mp,artifact,seen)
    if seen!=set(REQUIRED_BY_COMPONENT): raise SystemExit("VPS, Ubuntu Worker, and edge exact artifacts are all required")
    print("Exact artifacts valid: VPS/edge quality evidence plus Ubuntu Worker release inventory, digests, extraction and syntax"); return 0
if __name__=="__main__": raise SystemExit(main())
