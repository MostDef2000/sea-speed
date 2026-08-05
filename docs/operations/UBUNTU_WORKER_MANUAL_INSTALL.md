# Ubuntu worker manual installation

Status: repository flow prepared; physical server runtime remains unverified.

## Scope

This procedure prepares one immutable worker release from an exact Git commit.
It does not install or select an NVIDIA driver, CUDA runtime or PyTorch build,
and it does not configure systemd, automatic updates or rollback.

## Host prerequisites

Install Ubuntu packages providing:

- `git`;
- `python3` and `python3-venv`;
- `ffmpeg`;
- `tar`;
- NVIDIA tooling appropriate for the installed RTX 5070.

Do not select CUDA or PyTorch versions from this document. During server
commissioning, verify the installed driver and use the current official
PyTorch installation selector for the compatible build.

## Exact checkout

Use a full lowercase 40-character commit SHA that passed the aggregate quality
gate. Clone the repository, fetch that commit and detach the checkout:

```bash
git clone https://github.com/MostDef2000/sea-speed.git
cd sea-speed
git fetch origin <commit> --depth=1
git checkout --detach <commit>
```

Run the compatibility checks:

```bash
python3 scripts/worker/check_ubuntu_compatibility.py
bash deploy/worker/ubuntu/preflight.sh
```

## Prepare the release

```bash
sudo bash deploy/worker/ubuntu/install-manual.sh <commit> /opt/sea-speed-worker
```

The first run creates the immutable source release, its virtual environment and
protected shared directories. Until a hardware-compatible PyTorch build is
installed, it exits with an explicit next action and does not claim success.

Install PyTorch into the prepared virtual environment using the verified command
from the official selector, then rerun the installer. The second run installs
the remaining runtime dependencies and validates imports.

## Protected local state

These paths are outside immutable release source and must survive later updates:

```text
/opt/sea-speed-worker/shared/config
/opt/sea-speed-worker/shared/models
/opt/sea-speed-worker/shared/datasets
/opt/sea-speed-worker/shared/output
```

Copy `worker.env.example` to a local `worker.env`, populate it directly on the
server and set mode `0600`. Never print or commit its contents.

## Manual validation boundary

After installation, validate only non-secret facts:

```bash
/opt/sea-speed-worker/releases/<commit>/venv/bin/python -c \
  'import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NO_CUDA")'
```

HLS connectivity, API connectivity, model loading, frame progression and
`worker_online` remain runtime commissioning checks. They are not proven by
repository CI.

## Uninstall before production use

Because systemd and production activation are out of scope, a prepared release
can be removed only after confirming it is not running:

```bash
sudo rm -rf /opt/sea-speed-worker/releases/<commit>
```

Do not remove `shared/` during release cleanup.
