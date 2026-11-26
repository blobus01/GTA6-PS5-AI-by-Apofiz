"""Auto-update for ApofizPlay GTA6: find a newer build on GitHub Releases and install it.

Public interface (used by the launcher):

    info = check_for_update(current_version, channel="stable")
    # -> None when up to date, offline, rate-limited, private repo without token, or
    #    no asset for this OS/arch. Otherwise a dict:
    #    {"version": "0.2.0", "notes": "...markdown...", "url": "https://...",
    #     "size": 123456, "sha256": "ab12..." or None, "name": "ApofizPlay-...dmg",
    #     "tag": "v0.2.0", "prerelease": False, "html_url": "https://github.com/..."}

    result = apply_update(info, progress_cb=lambda done, total: ...)
    # Downloads to a temp dir, verifies SHA-256, then:
    #   macOS   -> opens the .dmg in Finder (user drags the app to /Applications),
    #              result["action"] == "opened_dmg"
    #   Windows -> schedules "Setup.exe /SILENT" to start once this process exits,
    #              result["action"] == "installer_scheduled", result["quit_required"] True:
    #              the launcher must quit promptly after this returns.
    #   other   -> result["action"] == "downloaded" (file left at result["path"]).
    # Raises UpdateError on download/verification failure.

Release assets the updater looks for (produced by .github/workflows/release.yml):
    ApofizPlay-GTA6-<VERSION>-mac-arm64.dmg            (+ .sha256)
    ApofizPlay-GTA6-<VERSION>-win-x64-Setup.exe        (+ .sha256)

Channels: "stable" ignores pre-releases; "beta" also considers pre-releases.
Environment overrides: APOFIZ_UPDATE_REPO (owner/name), APOFIZ_UPDATE_TOKEN or
GITHUB_TOKEN (needed only while the repo is private), PS5_REMOTE_HOME (cache dir).
Only stdlib + requests.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

import requests

REPO = os.environ.get("APOFIZ_UPDATE_REPO", "blobus01/GTA6-PS5-AI-by-Apofiz")
API = "https://api.github.com"
TIMEOUT = 5  # seconds, for API calls
DOWNLOAD_TIMEOUT = 30  # seconds per read while downloading
CACHE_TTL = 6 * 3600
ASSET_PREFIX = "ApofizPlay-GTA6-"
USER_AGENT = "ApofizPlay-GTA6-updater"


class UpdateError(RuntimeError):
    """Raised by apply_update when the download or verification fails."""


# ---------------------------------------------------------------- versions

_SEMVER = re.compile(
    r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?\s*$"
)


def parse_version(text: str) -> tuple:
    """Parse "v1.2.3-beta.1+build" into a sortable key. Raises ValueError if malformed."""
    m = _SEMVER.match(str(text or ""))
    if not m:
        raise ValueError(f"not a version: {text!r}")
    core = tuple(int(x or 0) for x in m.group(1, 2, 3))
    pre = m.group(4)
    if not pre:
        # A release sorts after any of its pre-releases.
        return core + ((1,),)
    ids = []
    for part in pre.split("."):
        # Semver: numeric identifiers sort before alphanumeric ones, numerically.
        ids.append((0, int(part), "") if part.isdigit() else (1, 0, part))
    return core + ((0, tuple(ids)),)


def compare_versions(a: str, b: str) -> int:
    """Return -1, 0 or 1 like cmp(a, b) using semver precedence (build metadata ignored)."""
    ka, kb = parse_version(a), parse_version(b)
    return (ka > kb) - (ka < kb)


def is_newer(candidate: str, current: str) -> bool:
    try:
        return compare_versions(candidate, current) > 0
    except ValueError:
        return False


def is_prerelease_version(text: str) -> bool:
    m = _SEMVER.match(str(text or ""))
    return bool(m and m.group(4))


# ---------------------------------------------------------------- platform

def platform_key(system: Optional[str] = None, machine: Optional[str] = None) -> Optional[str]:
    """Asset key for this OS/arch: "mac-arm64", "win-x64", or None if unsupported."""
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    if system == "darwin":
        # Only Apple Silicon builds are published; Intel Macs cannot run them.
        return "mac-arm64" if machine in ("arm64", "aarch64") else None
    if system in ("windows", "win32") or system.startswith(("cygwin", "msys")):
        # Windows on ARM runs the x64 build under emulation.
        return "win-x64" if machine in ("amd64", "x86_64", "x64", "arm64", "aarch64") else None
    return None


_ASSET_SUFFIX = {"mac-arm64": "-mac-arm64.dmg", "win-x64": "-win-x64-Setup.exe"}


def select_asset(assets: list, key: Optional[str]) -> tuple[Optional[dict], Optional[dict]]:
    """Pick (installer_asset, sha256_asset) for the platform key from a release's assets."""
    if not key or key not in _ASSET_SUFFIX:
        return None, None
    suffix = _ASSET_SUFFIX[key].lower()
    by_name = {a.get("name", ""): a for a in assets or []}
    # versioned names first (website aliases without a version are published too)
    for name, asset in sorted(by_name.items(), key=lambda kv: -len(kv[0])):
        low = name.lower()
        if low.startswith(ASSET_PREFIX.lower()) and low.endswith(suffix):
            return asset, by_name.get(name + ".sha256")
    return None, None


# ---------------------------------------------------------------- http + cache

def _home() -> Path:
    return Path(os.environ.get("PS5_REMOTE_HOME", Path.home() / ".ps5-remote"))


def _cache_path() -> Path:
    return _home() / "update.json"


def _token() -> Optional[str]:
    return os.environ.get("APOFIZ_UPDATE_TOKEN") or os.environ.get("GITHUB_TOKEN") or None


def _headers(accept: str = "application/vnd.github+json") -> dict:
    h = {"Accept": accept, "User-Agent": USER_AGENT, "X-GitHub-Api-Version": "2022-11-28"}
    tok = _token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _load_cache() -> dict:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_cache(data: dict) -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass  # caching is best effort


def _slim_release(rel: dict) -> dict:
    return {
        "tag_name": rel.get("tag_name", ""),
        "body": rel.get("body") or "",
        "prerelease": bool(rel.get("prerelease")),
        "draft": bool(rel.get("draft")),
        "html_url": rel.get("html_url", ""),
        "assets": [
            {
                "name": a.get("name", ""),
                "size": a.get("size", 0),
                "browser_download_url": a.get("browser_download_url", ""),
                "url": a.get("url", ""),
            }
            for a in rel.get("assets") or []
        ],
    }


def _fetch_releases(channel: str) -> Optional[list]:
    """Releases for the channel from GitHub, or None on any failure (offline, 404, 403...)."""
    try:
        if channel == "stable":
            r = requests.get(f"{API}/repos/{REPO}/releases/latest", headers=_headers(), timeout=TIMEOUT)
            if r.status_code == 404:
                return []  # no releases yet (or private repo without token)
            if r.status_code != 200:
                return None
            return [_slim_release(r.json())]
        r = requests.get(
            f"{API}/repos/{REPO}/releases", params={"per_page": 20}, headers=_headers(), timeout=TIMEOUT
        )
        if r.status_code == 404:
            return []
        if r.status_code != 200:
            return None
        data = r.json()
        return [_slim_release(x) for x in data] if isinstance(data, list) else None
    except (requests.RequestException, ValueError):
        return None


def _fetch_sha256(sha_asset: dict) -> Optional[str]:
    """Download a small "<hex>  <filename>" file and return the hex digest."""
    try:
        if _token() and sha_asset.get("url"):
            r = requests.get(sha_asset["url"], headers=_headers("application/octet-stream"), timeout=TIMEOUT)
        else:
            r = requests.get(sha_asset["browser_download_url"], headers=_headers("*/*"), timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        m = re.search(r"\b[0-9a-fA-F]{64}\b", r.text)
        return m.group(0).lower() if m else None
    except (requests.RequestException, KeyError):
        return None


def _get_releases(channel: str, force: bool) -> Optional[list]:
    cache = _load_cache()
    entry = cache.get(REPO, {}).get(channel) if isinstance(cache.get(REPO), dict) else None
    fresh = entry and time.time() - entry.get("checked_at", 0) < CACHE_TTL
    if entry and fresh and not force:
        return entry.get("releases")
    releases = _fetch_releases(channel)
    if releases is None:
        # Offline / rate limited: fall back to a stale cache rather than nothing.
        return entry.get("releases") if entry else None
    cache.setdefault(REPO, {})
    if not isinstance(cache[REPO], dict):
        cache[REPO] = {}
    cache[REPO][channel] = {"checked_at": time.time(), "releases": releases}
    _save_cache(cache)
    return releases


def _remember_sha(channel: str, tag: str, asset_name: str, sha: str) -> None:
    cache = _load_cache()
    entry = cache.get(REPO, {}).get(channel) if isinstance(cache.get(REPO), dict) else None
    if not entry:
        return
    for rel in entry.get("releases", []):
        if rel.get("tag_name") == tag:
            rel.setdefault("sha256", {})[asset_name] = sha
    _save_cache(cache)


# ---------------------------------------------------------------- public API

def check_for_update(
    current_version: str,
    channel: str = "stable",
    *,
    force: bool = False,
    system: Optional[str] = None,
    machine: Optional[str] = None,
) -> Optional[dict]:
    """Return info about a newer release for this OS/arch, or None.

    Never raises for network problems; results are cached for 6 h in
    ~/.ps5-remote/update.json (force=True skips the cache).
    """
    channel = "beta" if channel == "beta" else "stable"
    key = platform_key(system, machine)
    if not key:
        return None
    releases = _get_releases(channel, force)
    if not releases:
        return None

    best = None
    for rel in releases:
        if rel.get("draft"):
            continue
        tag = rel.get("tag_name", "")
        if channel == "stable" and (rel.get("prerelease") or is_prerelease_version(tag)):
            continue
        if not is_newer(tag, current_version):
            continue
        asset, sha_asset = select_asset(rel.get("assets", []), key)
        if not asset:
            continue
        if best is None or compare_versions(tag, best[0]["tag_name"]) > 0:
            best = (rel, asset, sha_asset)
    if best is None:
        return None

    rel, asset, sha_asset = best
    sha = (rel.get("sha256") or {}).get(asset["name"])
    if not sha and sha_asset:
        sha = _fetch_sha256(sha_asset)
        if sha:
            _remember_sha(channel, rel["tag_name"], asset["name"], sha)
    tag = rel["tag_name"]
    return {
        "version": tag[1:] if tag[:1] in "vV" else tag,
        "notes": rel.get("body", ""),
        "url": asset.get("browser_download_url", ""),
        "api_url": asset.get("url", ""),
        "size": int(asset.get("size") or 0),
        "sha256": sha,
        "name": asset.get("name", ""),
        "tag": tag,
        "prerelease": bool(rel.get("prerelease")),
        "html_url": rel.get("html_url", ""),
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(info: dict, dest_dir: Path, progress_cb: Optional[Callable[[int, int], None]] = None) -> Path:
    """Stream the asset into dest_dir and verify its SHA-256. Returns the file path."""
    name = os.path.basename(info.get("name") or info["url"].rsplit("/", 1)[-1]) or "update.bin"
    dest = Path(dest_dir) / name
    part = dest.with_name(dest.name + ".part")
    if _token() and info.get("api_url"):
        url, headers = info["api_url"], _headers("application/octet-stream")
    else:
        url, headers = info["url"], _headers("*/*")
    total = int(info.get("size") or 0)
    done = 0
    try:
        with requests.get(url, headers=headers, stream=True, timeout=(TIMEOUT, DOWNLOAD_TIMEOUT)) as r:
            if r.status_code != 200:
                raise UpdateError(f"download failed: HTTP {r.status_code}")
            total = int(r.headers.get("Content-Length") or total or 0)
            h = hashlib.sha256()
            with open(part, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if not chunk:
                        continue
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    if progress_cb:
                        try:
                            progress_cb(done, total)
                        except Exception:
                            pass  # a broken UI callback must not break the update
    except requests.RequestException as e:
        part.unlink(missing_ok=True)
        raise UpdateError(f"download failed: {e}") from e
    except OSError as e:
        part.unlink(missing_ok=True)
        raise UpdateError(f"cannot write update: {e}") from e

    if total and done != total:
        part.unlink(missing_ok=True)
        raise UpdateError(f"download incomplete: {done} of {total} bytes")
    expected = (info.get("sha256") or "").lower()
    actual = h.hexdigest()
    if expected and actual != expected:
        part.unlink(missing_ok=True)
        raise UpdateError(f"SHA-256 mismatch: expected {expected}, got {actual}")
    os.replace(part, dest)
    return dest


def _running_app_bundle() -> Optional[Path]:
    """The .app bundle this process runs from, if any (macOS)."""
    for p in Path(sys.executable).resolve().parents:
        if p.suffix == ".app":
            return p
    return None


def _schedule_windows_installer(exe: Path, pid: int) -> None:
    """Start the Inno Setup installer silently after process `pid` exits."""
    script = (
        f"Wait-Process -Id {int(pid)} -ErrorAction SilentlyContinue; "
        f"Start-Process -FilePath '{str(exe).replace(chr(39), chr(39) * 2)}' "
        "-ArgumentList '/SILENT','/SUPPRESSMSGBOXES','/NORESTART'"
    )
    flags = 0
    for name in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"):
        flags |= getattr(subprocess, name, 0)
    subprocess.Popen(
        ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
        creationflags=flags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def apply_update(
    info: dict,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    *,
    allow_unverified: bool = False,
    pid: Optional[int] = None,
    system: Optional[str] = None,
) -> dict:
    """Download, verify and hand the update to the OS installer. See module docstring."""
    if not info or not info.get("url"):
        raise UpdateError("no update to apply")
    if not info.get("sha256") and not allow_unverified:
        raise UpdateError("release has no .sha256 checksum; refusing to install unverified update")
    tmp = Path(tempfile.mkdtemp(prefix="apofiz-update-"))
    path = download(info, tmp, progress_cb)
    system = (system or platform.system()).lower()
    result = {"path": str(path), "version": info.get("version"), "action": "downloaded", "quit_required": False}

    if system == "darwin" and path.suffix.lower() == ".dmg":
        # Safe path: mount the image and show it in Finder; the user drags the new
        # app over the old one. We never delete or overwrite a running bundle.
        subprocess.Popen(["open", str(path)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        bundle = _running_app_bundle()
        result.update(action="opened_dmg", app_bundle=str(bundle) if bundle else None,
                      quit_required=bool(bundle and str(bundle).startswith("/Applications/")))
    elif system == "windows" and path.suffix.lower() == ".exe":
        _schedule_windows_installer(path, pid or os.getpid())
        result.update(action="installer_scheduled", quit_required=True)
    return result


def main(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Check for an ApofizPlay GTA6 update.")
    ap.add_argument("--current", help="current version (default: VERSION file)")
    ap.add_argument("--channel", default="stable", choices=["stable", "beta"])
    ap.add_argument("--force", action="store_true", help="ignore the 6 h cache")
    ap.add_argument("--apply", action="store_true", help="download and install if available")
    args = ap.parse_args(argv)
    current = args.current
    if not current:
        vf = Path(__file__).resolve().parent / "VERSION"
        current = vf.read_text(encoding="utf-8").strip() if vf.exists() else "0.0.0"
    info = check_for_update(current, args.channel, force=args.force)
    if not info:
        print(f"up to date ({current})")
        return 0
    print(json.dumps({k: v for k, v in info.items() if k != "notes"}, indent=1))
    if args.apply:
        print(json.dumps(apply_update(info, lambda d, t: None), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
