#!/usr/bin/env python3
"""Build deterministic VPS, Ubuntu Worker, and edge source artifacts from exact repository bytes."""
from __future__ import annotations
import argparse,gzip,io,json,sys,tarfile
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.quality.common import SHA40_RE, repository_root, sha256_bytes, sha256_file, write_json_atomic

COMPONENT_FILES={
"vps":{"required":["api/app/main.py","frontend/sea-speed/index.html","frontend/sea-speed/objects/index.html","frontend/sea-speed/cameras/index.html","frontend/sea-speed/road/index.html","frontend/root/index.html","deploy/vps/deploy.sh","deploy/vps/sea-speed-auth-cutover.sh","deploy/vps/install-auth-privilege-boundary.sh","deploy/vps/sea-speed-auth-privileged-helper.py","scripts/operations/nginx_cam1_direct_h264.py","scripts/operations/nginx_sea_speed_auth.py"],"optional":["api/requirements.txt","schemas/release-manifest.schema.json","schemas/deployment-manifest.schema.json"]},
"ubuntu-worker":{"required":["scripts/worker/check_ubuntu_compatibility.py","worker/analytics_profiles.py","worker/hls_motion_yolo_worker_events.py","worker/hls_motion_yolo_runtime.py","worker/ubuntu_worker_entrypoint.py","worker/ubuntu_ai_inference_worker.py","deploy/worker/ubuntu/install-manual.sh","deploy/worker/ubuntu/install-systemd.sh","deploy/worker/ubuntu/update-exact.sh","deploy/worker/ubuntu/rollback-exact.sh","deploy/worker/ubuntu/deploy-authorized.sh","deploy/worker/ubuntu/preflight.sh","deploy/worker/ubuntu/prepare-runtime.sh","deploy/worker/ubuntu/requirements-runtime.txt","deploy/worker/ubuntu/runtime-lock.json","deploy/worker/ubuntu/worker.env.example","deploy/worker/ubuntu/road-worker.env.example","deploy/worker/ubuntu/sea-speed-worker.service.template","deploy/worker/ubuntu/sea-speed-road-worker.service.template","deploy/worker/ubuntu/sea-speed-worker-control.service.template","deploy/worker/ubuntu/worker-control-agent.py","deploy/worker/ubuntu/observed-worker-runner.py","deploy/worker/ubuntu/verify-runtime-progression.py","deploy/worker/ubuntu/check-worker-health.py","deploy/worker/ubuntu/configure-analytics-profiles.py","deploy/worker/ubuntu/prepare-yolo-model.py"],"optional":[]},
"edge":{"required":["worker/analytics_profiles.py","worker/hls_motion_yolo_worker_events.py","worker/hls_motion_yolo_runtime.py"],"optional":["worker/run_worker_once.ps1","worker/restart_worker.cmd","worker/start_worker.cmd","worker/update_worker.ps1","worker/update_worker.cmd","worker/requirements.txt"]}}
FORBIDDEN_SUFFIXES={".jpg",".jpeg",".png",".sqlite",".sqlite3",".db",".env",".pt",".onnx",".engine"}

def deterministic_tar_gz(root:Path,names:list[str])->bytes:
    tar_buffer=io.BytesIO()
    with tarfile.open(fileobj=tar_buffer,mode="w",format=tarfile.PAX_FORMAT) as archive:
        for name in sorted(names):
            path=root/name; data=path.read_bytes(); info=tarfile.TarInfo(name=name); info.size=len(data); info.mode=0o755 if path.suffix in {".sh",".cmd",".ps1"} else 0o644; info.mtime=0; info.uid=info.gid=0; info.uname=info.gname=""; archive.addfile(info,io.BytesIO(data))
    compressed=io.BytesIO()
    with gzip.GzipFile(filename="",mode="wb",fileobj=compressed,mtime=0,compresslevel=9) as h: h.write(tar_buffer.getvalue())
    return compressed.getvalue()

def build_component(root,output_dir,component,source_commit):
    cfg=COMPONENT_FILES[component]; missing=[n for n in cfg["required"] if not (root/n).is_file()]
    if missing: raise FileNotFoundError(f"{component} artifact missing required files: {', '.join(missing)}")
    names=[*cfg["required"],*[n for n in cfg["optional"] if (root/n).is_file()]]
    for name in names:
        path=Path(name)
        if any(part in {".git","output","media","data"} for part in path.parts): raise ValueError(f"runtime directory cannot enter exact artifact: {name}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES: raise ValueError(f"runtime/media/model file cannot enter exact artifact: {name}")
    payload=deterministic_tar_gz(root,names); filename=f"sea-speed-{component}-{source_commit}.tar.gz"; artifact_path=output_dir/filename; artifact_path.write_bytes(payload)
    files=[{"path":n,"sha256":sha256_file(root/n),"size":(root/n).stat().st_size} for n in sorted(names)]
    return {"component":component,"filename":filename,"sha256":sha256_bytes(payload),"size":len(payload),"files":files}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--source-commit",required=True); p.add_argument("--output-dir",default="dist/exact"); a=p.parse_args(); source=a.source_commit.lower()
    if not SHA40_RE.fullmatch(source): raise SystemExit("source commit must be a full lowercase 40-character SHA")
    root=repository_root(); out=Path(a.output_dir); out=out if out.is_absolute() else root/out; out.mkdir(parents=True,exist_ok=True)
    manifest={"schema":"sea_speed_exact_artifacts_v1","source_commit":source,"artifacts":[build_component(root,out,c,source) for c in ("vps","edge")],"release_artifacts":[build_component(root,out,"ubuntu-worker",source)]}
    write_json_atomic(out/"exact-artifacts.json",manifest); print(json.dumps(manifest,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
