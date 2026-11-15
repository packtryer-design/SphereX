"""Host Blink's data server from this computer, for the public site (e.g. on Vercel).

    python scripts/host.py            # Ctrl+C to stop

What it does:
  1. starts the API (uvicorn, port 8000), or reuses one already running there
  2. opens a free Cloudflare quick tunnel to it: a public https address, no account needed
     (downloads `cloudflared` into .tools/ the first time if it isn't installed)
  3. publishes that address to the `api-endpoint` branch on GitHub as endpoint.json. The
     static site reads it live, so it finds this computer without being redeployed
  4. keeps checking the tunnel and reopens it if it drops
  5. on Ctrl+C: marks the server offline (unless another computer has taken over since)

Any computer can host: clone the repo, install the API's dependencies, make sure `git push`
works, and run this. The most recent computer to start hosting wins. Warm the demo objects
first so visitors don't wait on NASA's archive:
    python scripts/warm_cache.py barnards-star orion

Options: --port 8000   --no-publish (tunnel only, print the address)
"""

import argparse
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
BRANCH = "api-endpoint"
TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
RELEASES = "https://github.com/cloudflare/cloudflared/releases/latest/download/"
# Keeps Vercel from trying to deploy the tiny api-endpoint branch (it has no site in it).
NO_DEPLOY = json.dumps({"git": {"deploymentEnabled": False}}) + "\n"


def log(msg: str) -> None:
    print(f"[host {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------- cloudflared ----------


def cloudflared() -> str:
    found = shutil.which("cloudflared")
    if found:
        return found
    system = platform.system()
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "amd64"
    if system == "Windows":
        asset, exe = "cloudflared-windows-amd64.exe", TOOLS / "cloudflared.exe"
    elif system == "Linux":
        asset, exe = f"cloudflared-linux-{arch}", TOOLS / "cloudflared"
    elif system == "Darwin":
        asset, exe = f"cloudflared-darwin-{arch}.tgz", TOOLS / "cloudflared"
    else:
        sys.exit(f"Unsupported system {system}: install cloudflared yourself and re-run.")
    if not exe.exists():
        TOOLS.mkdir(exist_ok=True)
        log(f"downloading cloudflared ({asset}) from Cloudflare's GitHub releases…")
        tmp = TOOLS / (asset + ".part")
        urllib.request.urlretrieve(RELEASES + asset, tmp)
        if asset.endswith(".tgz"):
            with tarfile.open(tmp) as t:
                member = next(m for m in t.getmembers() if m.name.endswith("cloudflared"))
                member.name = exe.name
                t.extract(member, TOOLS)
            tmp.unlink()
        else:
            tmp.replace(exe)
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(exe)


# ---------- API server ----------


def healthy(base: str, timeout: float = 8) -> bool:
    try:
        with urllib.request.urlopen(f"{base}/api/health", timeout=timeout) as r:
            return r.status == 200 and json.loads(r.read()).get("ok") is True
    except Exception:
        return False


def start_api(port: int) -> subprocess.Popen[bytes] | None:
    local = f"http://127.0.0.1:{port}"
    if healthy(local, 3):
        log(f"using the Blink API already running on port {port}")
        return None
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        sys.exit("The API's dependencies aren't installed. See README.md, 'Run it'.")
    log(f"starting the Blink API on port {port}…")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
    )
    for _ in range(120):
        if healthy(local, 2):
            log("API is up")
            return proc
        if proc.poll() is not None:
            sys.exit("The API failed to start: see the error above.")
        time.sleep(1)
    proc.terminate()
    sys.exit("The API didn't come up within 2 minutes.")


# ---------- tunnel ----------


class Tunnel:
    def __init__(self, exe: str, port: int) -> None:
        self.exe, self.port = exe, port
        self.proc: subprocess.Popen[str] | None = None
        self.url: str | None = None

    def open(self) -> str:
        self.close()
        self.url = None
        found = threading.Event()
        self.proc = subprocess.Popen(
            [self.exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        def read(stream) -> None:  # type: ignore[no-untyped-def]
            for line in stream:
                m = TUNNEL_RE.search(line)
                if m and not self.url:
                    self.url = m.group(0)
                    found.set()

        threading.Thread(target=read, args=(self.proc.stdout,), daemon=True).start()
        if not found.wait(60):
            self.close()
            raise RuntimeError("cloudflared gave no tunnel address within 60 s")
        log(f"tunnel open: {self.url}")
        for _ in range(45):  # a fresh trycloudflare name can take a few seconds to resolve
            if healthy(self.url, 6):
                return self.url
            time.sleep(2)
        raise RuntimeError("the tunnel opened but the API isn't reachable through it")

    def alive(self) -> bool:
        return bool(self.proc and self.proc.poll() is None and self.url and healthy(self.url))

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


# ---------- publishing the address (git plumbing: never touches your working tree) ----------


def git(*args: str, data: str | None = None, env: dict[str, str] | None = None) -> str:
    # Bytes, not text mode: on Windows, text mode turns "\n" into "\r\n", and git mktree
    # would then name the file "endpoint.json\r".
    out = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        input=None if data is None else data.encode("utf-8"),
        capture_output=True,
        env=env,
        check=True,
    )
    return out.stdout.decode("utf-8", errors="replace").strip()


def published_url() -> str | None:
    """Address currently on GitHub, or None."""
    try:
        git("fetch", "--quiet", "origin", BRANCH)
        return json.loads(git("show", "FETCH_HEAD:endpoint.json")).get("url")
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def publish(url: str | None) -> None:
    doc = {
        "url": url,
        "status": "online" if url else "offline",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Written by scripts/host.py. The site reads this to find the API.",
    }
    endpoint = git("hash-object", "-w", "--stdin", data=json.dumps(doc, indent=2) + "\n")
    no_deploy = git("hash-object", "-w", "--stdin", data=NO_DEPLOY)
    web = git("mktree", data=f"100644 blob {no_deploy}\tvercel.json\n")
    tree = git(
        "mktree",
        data=f"100644 blob {endpoint}\tendpoint.json\n100644 blob {no_deploy}\tvercel.json\n"
        f"040000 tree {web}\tweb\n",
    )
    env = dict(os.environ)
    if not subprocess.run(["git", "config", "user.email"], cwd=ROOT, capture_output=True).stdout:
        env.update(
            GIT_AUTHOR_NAME="Blink host",
            GIT_AUTHOR_EMAIL="blink-host@users.noreply.github.com",
            GIT_COMMITTER_NAME="Blink host",
            GIT_COMMITTER_EMAIL="blink-host@users.noreply.github.com",
        )
    commit = git("commit-tree", tree, "-m", f"API endpoint: {doc['status']}", env=env)
    git("push", "--quiet", "--force", "origin", f"{commit}:refs/heads/{BRANCH}")
    log(f"published to the {BRANCH} branch: {doc['status']}{f' at {url}' if url else ''}")


# ---------- main ----------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-publish", action="store_true", help="don't update GitHub")
    args = ap.parse_args()

    api = start_api(args.port)
    tunnel = Tunnel(cloudflared(), args.port)
    url = None
    try:
        url = tunnel.open()
        if not args.no_publish:
            publish(url)
        log("hosting. The public site now uses this computer. Ctrl+C to stop.")
        log(f"direct link (works even without the public site): {url}/?o=barnards-star")
        failures = 0
        while True:
            time.sleep(30)
            if api is not None and api.poll() is not None:
                log("the API process stopped; restarting it")
                api = start_api(args.port)
            if tunnel.alive():
                failures = 0
                continue
            failures += 1
            log(f"tunnel check failed ({failures}/3)")
            if failures >= 3:
                log("reopening the tunnel…")
                url = tunnel.open()
                if not args.no_publish:
                    publish(url)
                failures = 0
    except KeyboardInterrupt:
        log("stopping…")
    finally:
        tunnel.close()
        if not args.no_publish and url:
            try:
                if published_url() in (url, None):
                    publish(None)
                else:
                    log("another computer has taken over hosting: leaving its address in place")
            except subprocess.CalledProcessError as e:
                log(f"couldn't mark the server offline on GitHub: {e.stderr or e}")
        if api is not None:
            api.terminate()
        log("stopped")


if __name__ == "__main__":
    main()
