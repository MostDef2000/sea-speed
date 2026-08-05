# Ubuntu worker compatibility boundary

Status: repository compatibility prepared; physical host not commissioned  
Issue: #60

## Purpose

Define what can be proven before the planned Ubuntu worker server exists and provide non-secret checks for the first host setup.

This document does not claim that the worker is installed, GPU-enabled or operational on Ubuntu.

## Confirmed from source

The current event worker:

- uses `pathlib.Path` for repository-relative output paths;
- invokes FFmpeg through an argument list rather than a shell command string;
- receives HLS, API, token and model configuration through environment-variable names;
- contains no required hard-coded Windows drive path in the worker source;
- keeps detection, tracking, speed and event behavior independent of the host launcher.

Run the dependency-free source contract from repository root:

```bash
python3 scripts/worker/check_ubuntu_compatibility.py
```

A successful result proves only the checked source contracts. It does not prove native-library or GPU compatibility.

## Host preflight

After Ubuntu is installed, run from the exact checked-out release directory:

```bash
bash deploy/worker/ubuntu/preflight.sh
```

The preflight reports only capability names, versions and presence states. It must not print `.env` contents, tokens, camera credentials or URLs.

Expected result classes:

- `PASS` — capability is available;
- `FAIL` — required repository or host capability is missing;
- `UNKNOWN` — the check requires later installation, local secrets, network access or an active runtime.

Before the physical server exists, the following remain `UNKNOWN`:

- RTX 5070 detection;
- installed NVIDIA driver compatibility;
- PyTorch CUDA availability;
- FFmpeg access to the production HLS stream;
- API connectivity with the local token;
- worker frame progression and `worker_online`;
- GPU load, VRAM and temperature under inference;
- reboot, restart and rollback behavior.

## Required local boundaries

The future host must keep these outside Git-tracked release content:

- `.env` and all credentials;
- YOLO model weights;
- datasets and caches;
- runtime output, event images and video;
- logs and checkpoints.

The exact directory layout, service account, systemd unit, updater, rollback and SSD/HDD retention policy belong to later separately approved stages.

## Release impact

This compatibility stage changes repository contracts, tests and documentation only. It requires no VPS deployment and no update of the existing Windows worker.

## Commissioning verdict

Until the physical host is installed and the runtime checks pass, use:

```text
UBUNTU_SOURCE_COMPATIBLE
UBUNTU_RUNTIME_UNKNOWN
```

Do not report the Ubuntu worker as production-ready based on CI alone.
