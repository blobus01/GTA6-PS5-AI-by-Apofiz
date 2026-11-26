#!/usr/bin/env python3
"""Build the GTA6 PS5 AI landing page.

    python3 site/build.py            # single self-contained file -> site/dist/index.html
    python3 site/build.py --multi    # GitHub Pages build -> site/dist/index.html + site/dist/assets/

Placeholders in site/src.html:
    {{IMG:name}}      image from site/assets/name.* (inlined as data: URI, or assets/<file> with --multi)
    {{REL:version}}   release tag, {{REL:date}} publish date,
    {{REL:mac_size}}  / {{REL:win_size}} human file sizes   (from site/release.json, empty if absent)
    {{DL:mac}} / {{DL:win}} / {{DL:latest}} / {{REPO}}       download + repo URLs

site/release.json is optional. Either the raw GitHub API answer of
`GET /repos/<owner>/<repo>/releases/latest`, or the short form
    {"version": "v0.4.0", "date": "2026-11-26",
     "assets": {"ApofizPlay-GTA6-mac-arm64.dmg": {"size": 91234567}, ...}}
The page also refreshes version/size live from the GitHub API in the browser.
"""
import base64
import json
import mimetypes
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src.html"
ASSETS = HERE / "assets"
DIST = HERE / "dist"
RELEASE = HERE / "release.json"

REPO = "https://github.com/blobus01/GTA6-PS5-AI-by-Apofiz"
# Version-less alias names: every release must publish these exact asset names,
# otherwise /releases/latest/download/<name> returns 404.
ASSET_MAC = "ApofizPlay-GTA6-mac-arm64.dmg"
ASSET_WIN = "ApofizPlay-GTA6-win-x64-Setup.exe"

mimetypes.add_type("image/webp", ".webp")


def human(n):
    if not n:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return (f"{n:.0f} {unit}" if unit in ("B", "KB") or n >= 100 else f"{n:.1f} {unit}")
        n /= 1024.0
    return ""


def release_info():
    info = {"version": "", "date": "", "mac_size": "", "win_size": ""}
    if not RELEASE.exists():
        return info
    try:
        data = json.loads(RELEASE.read_text("utf-8"))
    except ValueError as e:
        print(f"warning: {RELEASE.name} is not valid JSON ({e}); ignoring", file=sys.stderr)
        return info
    sizes = {}
    assets = data.get("assets") or {}
    if isinstance(assets, list):  # raw GitHub API shape
        sizes = {a.get("name"): a.get("size") for a in assets if isinstance(a, dict)}
    elif isinstance(assets, dict):
        sizes = {k: (v.get("size") if isinstance(v, dict) else v) for k, v in assets.items()}
    info["version"] = str(data.get("version") or data.get("tag_name") or "")
    info["date"] = str(data.get("date") or data.get("published_at") or "")[:10]
    info["mac_size"] = human(sizes.get(ASSET_MAC))
    info["win_size"] = human(sizes.get(ASSET_WIN))
    return info


def find_asset(name):
    hits = sorted(p for p in ASSETS.glob(name + ".*") if p.is_file())
    if not hits:
        sys.exit(f"error: no asset for {{{{IMG:{name}}}}} in {ASSETS}")
    return hits[0]


def build(multi):
    html = SRC.read_text("utf-8")
    rel = release_info()
    used = {}

    def img(m):
        p = find_asset(m.group(1))
        used[p.name] = p
        if multi:
            return "assets/" + p.name
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")

    html = re.sub(r"\{\{IMG:([A-Za-z0-9_\-]+)\}\}", img, html)
    html = re.sub(r"\{\{REL:([a-z_]+)\}\}", lambda m: rel.get(m.group(1), ""), html)
    links = {
        "mac": f"{REPO}/releases/latest/download/{ASSET_MAC}",
        "win": f"{REPO}/releases/latest/download/{ASSET_WIN}",
        "latest": f"{REPO}/releases/latest",
    }
    html = re.sub(r"\{\{DL:([a-z]+)\}\}", lambda m: links[m.group(1)], html)
    html = html.replace("{{REPO}}", REPO)

    left = re.findall(r"\{\{[A-Z]+:?[^}]*\}\}", html)
    if left:
        sys.exit(f"error: unresolved placeholders: {sorted(set(left))}")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    (DIST / "index.html").write_text(html, "utf-8")
    if multi:
        (DIST / "assets").mkdir()
        for name, p in used.items():
            shutil.copy2(p, DIST / "assets" / name)
        (DIST / ".nojekyll").write_text("")
    size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    mode = "multi-file" if multi else "single-file"
    print(f"built {mode}: {DIST / 'index.html'}  ({len(used)} images, {size / 1024:.0f} KB total)"
          + (f"  release {rel['version']}" if rel["version"] else "  (no release.json)"))


if __name__ == "__main__":
    build(multi="--multi" in sys.argv[1:])
