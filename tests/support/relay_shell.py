"""Executed-twin harness for the camera relay deploy shells (issue #398 wave 3).

Wave-2 F5 flagship pattern, extended: the REAL deploy script bytes run under
``unshare --user --map-root-user``, which maps this process's uid to root inside
a disposable user namespace — so the root-gated flows (state dirs,
install/chown/mv, digest files) execute for real while ``systemctl`` is a stub
on PATH and every mutable path (config, env file, state root) lives in a temp
directory owned by this process (it already looks root-owned inside the
namespace, so the scripts' root-ownership gates pass without any mutation of
real system paths).

Two run modes:

- in-place: the script at its repo location resolves the REAL canonical
  renderer (``scripts/operations/mediamtx_path_config.py``) through its own
  ``script_dir/../../..`` walk — the full production path is exercised.
- copy-tree: a copy of the real script at ``<tmp>/a/b/<name>.sh`` resolves
  ``<tmp>`` as repo root; tests plant a recording renderer stub there. Used by
  the wave-3 demo to mutate script copies without touching ``deploy/**``.

Offline and deterministic: the only network activity is the scripts' own
private-address TCP listener probe, which connects to an RFC1918 address with
no listener inside the sandbox (connection refused / bounded timeout). All
temp state is cleaned up by the caller's ``TemporaryDirectory``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAMERA_RELAY = ROOT / "deploy/worker/ubuntu/camera-relay.sh"
PREVIEW_RELAY = ROOT / "deploy/worker/ubuntu/camera-preview-relay.sh"

_UNSHARE = shutil.which("unshare")
_USER_NS_OK: bool | None = None

# Parameterized systemctl stub. Behavior knobs arrive through the environment
# (SYSTEMCTL_* values below); every invocation is appended to $SYSTEMCTL_LOG
# when that variable points at a writable file, so tests can assert which
# control-plane calls the real script made.
SYSTEMCTL_STUB = r"""
systemctl() {
  if [[ -n "${SYSTEMCTL_LOG:-}" ]]; then
    printf '%s\n' "$*" >> "$SYSTEMCTL_LOG"
  fi
  if [[ "${1:-}" == "show" ]]; then
    local prop=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        -p) prop="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    case "$prop" in
      User) printf '%s\n' "${SYSTEMCTL_USER:-}" ;;
      Group) printf '%s\n' "${SYSTEMCTL_GROUP:-}" ;;
      Environment) printf '%s\n' "${SYSTEMCTL_ENVIRONMENT:-}" ;;
      ExecStart) printf '%s\n' "${SYSTEMCTL_EXECSTART:-}" ;;
      *) printf '%s\n' "${SYSTEMCTL_SHOW_DEFAULT:-}" ;;
    esac
    return 0
  fi
  case "${1:-}" in
    is-active)
      if [[ "$2" == "--quiet" ]]; then
        for active_service in ${SYSTEMCTL_QUIET_ACTIVE_SERVICES:-}; do
          [[ "$3" == "$active_service" ]] && return 0
        done
        return 1
      fi
      printf '%s\n' "${SYSTEMCTL_ACTIVE_TEXT:-inactive}"
      return 0
      ;;
    is-enabled)
      printf '%s\n' "${SYSTEMCTL_ENABLED_TEXT:-enabled}"
      return 0
      ;;
    restart)
      if [[ "${SYSTEMCTL_RESTART_FAIL:-}" == "yes" ]]; then
        printf 'ERROR restart of %s failed\n' "$2" >&2
        return 1
      fi
      return 0
      ;;
    stop|start|enable|daemon-reload|reset-failed) return 0 ;;
    *) return 0 ;;
  esac
}
"""


def user_namespace_available() -> bool:
    """Probe (once) that unprivileged user namespaces work in this sandbox."""
    global _USER_NS_OK
    if _USER_NS_OK is None:
        if not _UNSHARE:
            _USER_NS_OK = False
        else:
            probe = subprocess.run(
                [_UNSHARE, "--user", "--map-root-user", "true"],
                capture_output=True,
            )
            _USER_NS_OK = probe.returncode == 0
    return _USER_NS_OK


def skip_without_user_namespace(testcase) -> None:
    """Skip root-gated executed twins where user namespaces are unavailable
    (same discipline as the historical os.geteuid() root-gated skips)."""
    if not user_namespace_available():
        testcase.skipTest("unprivileged user namespace (unshare --user --map-root-user) unavailable")


def bindable_private_listener() -> "tuple[str, object] | None":
    """Bind a deterministic RFC1918 listener for the shells' TCP probes.

    Returns (address, socket) for the first bindable RFC1918 host address, or
    None when the environment has none (the caller skips — the probe must be
    a real listening socket, never an environment-dependent dead address;
    the sandbox egress proxy accepts connects to dead RFC1918 addresses).
    """
    import socket

    try:
        lines = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=5
        ).stdout.split()
    except Exception:
        lines = []
    for candidate in lines:
        if not candidate.split(":")[0].startswith(("10.", "172.", "192.168.")):
            continue
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((candidate, 0))
            sock.listen(4)
            return "%s:%d" % sock.getsockname()[0:2], sock
        except OSError:
            sock.close()
    return None


def stub_dir(tmp: Path, renderer_stub: str | None = None) -> Path:
    """Build a PATH-stub directory holding the systemctl stub (and optionally
    a fake ffmpeg for the transcode run-on-ready script)."""
    directory = tmp / "stubs"
    directory.mkdir(parents=True, exist_ok=True)
    systemctl = directory / "systemctl"
    systemctl.write_text("#!/usr/bin/env bash\n" + SYSTEMCTL_STUB + '\nsystemctl "$@"\n', encoding="utf-8")
    systemctl.chmod(0o755)
    if renderer_stub is not None:
        python3 = directory / "python3"
        python3.write_text("#!/usr/bin/env bash\n" + renderer_stub, encoding="utf-8")
        python3.chmod(0o755)
    return directory


def run_shell(
    script: Path,
    args: list[str],
    tmp: Path,
    *,
    env_extra: dict[str, str] | None = None,
    use_unshare: bool = True,
    with_stubs: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute the real script bytes with stubbed systemctl on PATH.

    use_unshare=True runs under `unshare --user --map-root-user` so the
    root-gated flow executes; use_unshare=False runs bare (used for the
    standalone-status property, which must work without root).
    """
    environment = dict(env_extra or {})
    if with_stubs:
        stubs = stub_dir(tmp, environment.pop("_renderer_stub", None))
        environment["PATH"] = f"{stubs}:{'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'}"
    argv = []
    if use_unshare:
        if not user_namespace_available():
            raise RuntimeError("user namespace unavailable; call skip_without_user_namespace first")
        argv += [_UNSHARE, "--user", "--map-root-user"]
    argv += ["/bin/bash", str(script), *args]
    return subprocess.run(argv, env=environment, text=True, capture_output=True, timeout=120)


# A recording renderer for copy-tree runs: answers check-address affirmatively,
# writes a placeholder candidate for --output, and appends its full argv to
# $RENDERER_ARGS_LOG so tests can assert exactly what the shell forwarded.
# The shells invoke `python3 "$renderer" MODE ...`, so $1 is the renderer path;
# the recorder keys on that and scans the remaining argv for output flags.
RENDERING_RECORDER = r'''
if [[ "$1" == *mediamtx_path_config.py ]]; then
  out=""; prev=""
  for a in "$@"; do
    if [[ "$prev" == "--output" || "$prev" == "--config-output" || "$prev" == "--catalog-output" ]]; then
      printf 'mode-0600-placeholder\n' > "$a"
      chmod 0600 "$a"
    fi
    prev="$a"
  done
  [[ -n "${RENDERER_ARGS_LOG:-}" ]] && printf '%s\n' "$*" >> "$RENDERER_ARGS_LOG"
  exit 0
fi
exit 0
'''


def recording_renderer_env(log_path: Path) -> dict[str, str]:
    return {"_renderer_stub": RENDERING_RECORDER, "RENDERER_ARGS_LOG": str(log_path)}
