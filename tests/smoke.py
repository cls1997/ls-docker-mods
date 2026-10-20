"""Offline Docker/s6 smoke tests using actual LSIO base images (amd64 by default).

Run: python3 tests/smoke.py [--image ghcr.io/linuxserver/baseimage-ubuntu:noble]
No package metadata is downloaded. Images must be locally available or pullable.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


REPO = Path(__file__).resolve().parents[1]
DEFAULTS = [
    "ghcr.io/linuxserver/baseimage-alpine:3.23",
    "ghcr.io/linuxserver/baseimage-alpine:3.24",
    "ghcr.io/linuxserver/baseimage-ubuntu:noble",
    "ghcr.io/linuxserver/baseimage-ubuntu:resolute",
    "ghcr.io/linuxserver/baseimage-debian:trixie",
    "ghcr.io/linuxserver/baseimage-debian:kali",
    "ghcr.io/linuxserver/baseimage-arch:latest",
    "ghcr.io/linuxserver/baseimage-fedora:42",
    "ghcr.io/linuxserver/baseimage-fedora:44",
    "ghcr.io/linuxserver/baseimage-el:9",
]
PROBE = r"""
set -euo pipefail
if [ -r /etc/os-release ]; then . /etc/os-release; else . /usr/lib/os-release; fi
case "$ID" in
  alpine) grep -q 'https://mirrors.cernet.edu.cn/alpine/' /etc/apk/repositories ;;
  ubuntu|debian)
    apt-get --print-uris update > /tmp/certnet-apt-uris
    grep -q 'mirrors.cernet.edu.cn/api/apt/mirrorlist/' /tmp/certnet-apt-uris
    ;;
  kali)
    apt-get --print-uris update > /tmp/certnet-apt-uris
    grep -q 'mirrors.cernet.edu.cn/kali' /tmp/certnet-apt-uris
    ;;
  arch|archarm)
    pacman-conf --repo core Server > /tmp/certnet-pacman-servers
    grep -q 'https://mirrors.cernet.edu.cn/archlinux' /tmp/certnet-pacman-servers
    ;;
  fedora)
    dnf --cacheonly repolist > /tmp/certnet-dnf-repos
    grep -q '^fedora' /tmp/certnet-dnf-repos
    if [[ "${VERSION_ID:-}" =~ ^[0-9]+$ ]] && (( VERSION_ID >= 44 )); then
      dnf --dump-repo-config=fedora,updates > /tmp/certnet-dnf-config
      grep -q '^mirrorlist = https://mirrors.cernet.edu.cn/api/rpm/mirrorlist/fedora/releases/' /tmp/certnet-dnf-config
      grep -q '^mirrorlist = https://mirrors.cernet.edu.cn/api/rpm/mirrorlist/fedora/updates/' /tmp/certnet-dnf-config
      grep -q '^gpgcheck = 1' /tmp/certnet-dnf-config
    fi
    ;;
  rhel) ! grep -r -q 'mirrors.cernet.edu.cn' /etc/yum.repos.d ;;
  *) exit 1 ;;
esac
# Repeated runs must not change repository content or backups.
snapshot() {
  find /etc/apt /etc/apk /etc/pacman.d /etc/yum.repos.d /etc/dnf/repos.override.d \
      -type f -exec sha256sum {} \; 2>/dev/null | sort || true
}
snapshot > /tmp/certnet-before
/usr/local/lib/certnet-mirror/configure
snapshot > /tmp/certnet-after
test "$(sha256sum < /tmp/certnet-before)" = "$(sha256sum < /tmp/certnet-after)"
s6-rc -a list | grep -x 'init-mod-universal-package-manager-certnet-mirror'
"""


def command(*args, check=True):
    result = subprocess.run(args, cwd=REPO, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    if check and result.returncode:
        raise RuntimeError(f"{' '.join(args)}\n{result.stdout}")
    return result.stdout


def initialized(name, count):
    for _ in range(120):
        logs = command("docker", "logs", name)
        if "fatal:" in logs:
            raise RuntimeError(logs)
        if logs.count("[ls.io-init] done.") >= count:
            return logs
        time.sleep(0.25)
    raise RuntimeError(f"Initialization timed out: {logs}")


def test_image(image):
    suffix = uuid.uuid4().hex[:10]
    tag = f"local/certnet-smoke:{suffix}"
    name = f"certnet-smoke-{suffix}"
    try:
        # BuildKit can fetch FROM layers without creating a tagged local image.
        # Ensure the reference exists for the provenance inspection below.
        available = subprocess.run(["docker", "image", "inspect", image],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if available.returncode:
            command("docker", "pull", image)
        command("docker", "build", "-f", "tests/Dockerfile.smoke",
                "--build-arg", f"BASE_IMAGE={image}", "-t", tag, ".")
        command("docker", "run", "-d", "--name", name, tag)
        initialized(name, 1)
        command("docker", "exec", name, "bash", "-c", PROBE)
        command("docker", "restart", name)
        initialized(name, 2)
        command("docker", "exec", name, "bash", "-c", PROBE)
        release = command("docker", "exec", name, "bash", "-c",
                          "cat /etc/os-release 2>/dev/null || cat /usr/lib/os-release")
        digest = json.loads(command("docker", "image", "inspect", image))[0]
        return {"image": image, "id": digest["Id"], "arch": digest["Architecture"],
                "os_release": release, "result": "PASS"}
    except Exception as error:
        return {"image": image, "result": "FAIL", "error": str(error),
                "logs": command("docker", "logs", name, check=False)}
    finally:
        command("docker", "rm", "-f", name, check=False)
        command("docker", "image", "rm", tag, check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", help="LSIO base image to test")
    args = parser.parse_args()
    os.environ.setdefault("BUILDX_CONFIG", "/tmp/certnet-mirror-buildx")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(test_image, args.image or DEFAULTS))
    print(json.dumps(results, indent=2, ensure_ascii=False))
    raise SystemExit(any(result["result"] != "PASS" for result in results))
