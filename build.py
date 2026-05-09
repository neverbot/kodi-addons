#!/usr/bin/env python3
"""Build the published Kodi repository under docs/.

Reads addons.json for the list of external add-ons to track. For each,
fetches its latest semver-style git tag via the GitHub API, downloads the
source tarball at that tag, and packages it as a Kodi-compatible zip with
the add-on id as the top-level directory.

Also packages the local repository.neverbot/ source. Generates the index
files Kodi expects:

    docs/
      addons.xml
      addons.xml.md5
      <addon-id>/
        <addon-id>-<version>.zip          # latest version
        <addon-id>-<version>-icon.png     # optional, copied from source if present
        <addon-id>-<version>-fanart.jpg   # optional

History of older zips is preserved (older releases stay browseable).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
CONFIG = ROOT / "addons.json"
LOCAL_REPO_ADDON = ROOT / "repository.neverbot"


def log(msg: str) -> None:
    print(f"==> {msg}", flush=True)


def gh_api(path: str) -> dict | list:
    """Call the GitHub API, optionally with a token from the env."""
    url = f"https://api.github.com{path}"
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "neverbot-kodi-addons-builder"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def latest_release_tag(repo: str) -> str:
    """Return the latest tag of `owner/repo`, preferring published releases."""
    try:
        rel = gh_api(f"/repos/{repo}/releases/latest")
        if isinstance(rel, dict) and rel.get("tag_name"):
            return rel["tag_name"]
    except urllib.error.HTTPError:
        pass
    # Fall back to the most recent tag (releases may not exist yet).
    tags = gh_api(f"/repos/{repo}/tags")
    if not isinstance(tags, list) or not tags:
        raise RuntimeError(f"{repo}: no tags found")
    return tags[0]["name"]


def download_tarball(repo: str, ref: str, dest: Path) -> Path:
    """Download a github tarball for owner/repo at ref into dest. Returns the
    extracted source-tree root path."""
    url = f"https://api.github.com/repos/{repo}/tarball/{ref}"
    headers = {"User-Agent": "neverbot-kodi-addons-builder"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(dest)
    inside = list(dest.iterdir())
    if len(inside) != 1 or not inside[0].is_dir():
        raise RuntimeError(f"unexpected tarball layout for {repo}@{ref}")
    return inside[0]


def read_addon_xml(path: Path) -> tuple[str, str, ET.Element]:
    """Return (id, version, parsed root) from an addon.xml on disk."""
    tree = ET.parse(path)
    root = tree.getroot()
    return root.attrib["id"], root.attrib["version"], root


def build_zip(source_dir: Path, addon_id: str, version: str, out_dir: Path) -> Path:
    """Zip `source_dir` so the archive root is `<addon_id>/`.

    Excludes VCS junk and Python caches.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{addon_id}-{version}.zip"
    excludes = {".git", ".github", "__pycache__", ".DS_Store",
                ".gitignore", ".vscode", ".idea"}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            rel = path.relative_to(source_dir)
            if any(part in excludes for part in rel.parts):
                continue
            if path.is_dir():
                continue
            zf.write(path, arcname=f"{addon_id}/{rel}")
    return zip_path


def copy_assets(source_dir: Path, addon_id: str, out_dir: Path) -> None:
    """Copy icon.png / fanart.jpg / changelog into the published addon dir
    so Kodi can preview them in the install dialog."""
    for name in ("icon.png", "fanart.jpg", "changelog.txt"):
        src = source_dir / name
        if src.is_file():
            shutil.copy2(src, out_dir / name)


def addon_xml_for_index(source_dir: Path) -> ET.Element:
    """Return the addon.xml root element to embed in the repo's addons.xml.

    We don't strip anything — Kodi expects the same content as in the
    addon's own addon.xml.
    """
    return ET.parse(source_dir / "addon.xml").getroot()


def build_addons_xml(addon_roots: list[ET.Element]) -> bytes:
    out = ET.Element("addons")
    for el in addon_roots:
        out.append(el)
    body = ET.tostring(out, encoding="utf-8", xml_declaration=False)
    # Match the format Kodi tooling typically emits.
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + body + b"\n"


def summary_en(root: ET.Element) -> str:
    """Pull the en_GB summary out of an addon.xml root element, with a
    sensible fallback if it's missing."""
    for s in root.iter("summary"):
        if s.attrib.get("lang") in ("en_GB", "en", None):
            return (s.text or "").strip()
    return ""


def render_index_html(rows: list[dict]) -> str:
    """Render docs/index.html — a tiny static landing page.

    `rows` is a list of dicts with keys: id, name, version, summary, github
    (None for the repository add-on, which is built locally).
    """
    repo_url = "https://github.com/neverbot/kodi-addons"
    cards = []
    for r in rows:
        zip_url = f"{r['id']}/{r['id']}-{r['version']}.zip"
        github_link = (
            f'<a href="{r["github"]}">source</a>'
            if r.get("github")
            else f'<a href="{repo_url}">source</a>'
        )
        summary = r["summary"] or ""
        cards.append(
            "<article>"
            f'<h3>{r["name"]} '
            f'<span class="ver">v{r["version"]}</span></h3>'
            f"<p>{summary}</p>"
            "<p>"
            f'<a class="btn" href="{zip_url}">Download zip</a> '
            f"{github_link}"
            "</p>"
            f'<p class="id"><code>{r["id"]}</code></p>'
            "</article>"
        )
    cards_html = "\n".join(cards)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>neverbot's Kodi add-ons</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 760px; margin: 2rem auto; padding: 0 1rem;
  }}
  h1 {{ margin-bottom: .25rem; }}
  .lede {{ color: #666; margin-top: 0; }}
  article {{
    border: 1px solid #ccc4; border-radius: 8px;
    padding: 1rem 1.25rem; margin: 1rem 0;
  }}
  article h3 {{ margin: 0 0 .25rem; }}
  .ver {{ font-weight: 400; color: #888; font-size: .85em; }}
  .id code {{ color: #888; font-size: .85em; }}
  .btn {{
    display: inline-block; padding: .35rem .8rem;
    background: #0366d6; color: #fff; border-radius: 6px;
    text-decoration: none; margin-right: .5rem;
  }}
  .btn:hover {{ background: #024ea0; }}
  a {{ color: #0366d6; }}
  pre {{
    background: #f4f4f4; padding: .75rem 1rem; border-radius: 6px;
    overflow-x: auto;
  }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #111; color: #ddd; }}
    .lede, .ver, .id code {{ color: #999; }}
    pre {{ background: #1a1a1a; }}
  }}
</style>
</head>
<body>
<h1>neverbot's Kodi add-ons</h1>
<p class="lede">A small Kodi add-on repository.
Install the repository add-on once, then get every add-on listed below
(and updates to them) automatically.</p>

<h2>Install</h2>
<ol>
  <li>Download the
    <a href="repository.neverbot/repository.neverbot-1.0.0.zip"><strong>repository
    add-on zip</strong></a>.</li>
  <li>In Kodi: <em>Settings → Add-ons → Install from zip file</em> →
    pick the file. Enable “Unknown sources” first if Kodi asks.</li>
  <li>Then: <em>Settings → Add-ons → Install from repository →
    neverbot's Kodi add-ons</em> → install whichever add-ons you want.</li>
</ol>

<h2>Add-ons</h2>
{cards_html}

<h2>Manual repository setup</h2>
<p>If you'd rather configure Kodi to fetch from this URL directly:</p>
<pre>https://neverbot.github.io/kodi-addons/</pre>
<p>That's the <code>datadir</code> the repository add-on points at;
<code>addons.xml</code> and <code>addons.xml.md5</code> live next to it.</p>

<hr>
<p><small>Source: <a href="{repo_url}">{repo_url}</a></small></p>
</body>
</html>
"""


def main() -> int:
    config = json.loads(CONFIG.read_text())
    DOCS.mkdir(exist_ok=True)

    addon_roots: list[ET.Element] = []
    rows: list[dict] = []

    # 1) The repository add-on itself, from local source.
    log("packaging repository.neverbot from local source")
    repo_id, repo_ver, repo_root = read_addon_xml(LOCAL_REPO_ADDON / "addon.xml")
    repo_out = DOCS / repo_id
    repo_out.mkdir(parents=True, exist_ok=True)
    build_zip(LOCAL_REPO_ADDON, repo_id, repo_ver, repo_out)
    copy_assets(LOCAL_REPO_ADDON, repo_id, repo_out)
    addon_roots.append(repo_root)
    rows.append({
        "id": repo_id, "name": repo_root.attrib.get("name", repo_id),
        "version": repo_ver, "summary": summary_en(repo_root),
        "github": None,
    })

    # 2) Each tracked external add-on at its latest tag.
    with tempfile.TemporaryDirectory() as tmp_root:
        tmp = Path(tmp_root)
        for entry in config["addons"]:
            github = entry["github"]
            log(f"resolving latest tag for {github}")
            try:
                tag = latest_release_tag(github)
            except Exception as e:
                log(f"  WARN: no usable tag yet ({e}); skipping this addon")
                continue
            log(f"  tag = {tag}")
            workdir = tmp / entry["id"]
            workdir.mkdir()
            source_dir = download_tarball(github, tag, workdir)
            addon_id, addon_ver, root = read_addon_xml(source_dir / "addon.xml")
            if addon_id != entry["id"]:
                raise RuntimeError(
                    f"{github}: addon.xml id ({addon_id}) does not match "
                    f"config id ({entry['id']})"
                )
            log(f"  building {addon_id}-{addon_ver}.zip")
            out = DOCS / addon_id
            build_zip(source_dir, addon_id, addon_ver, out)
            copy_assets(source_dir, addon_id, out)
            addon_roots.append(root)
            rows.append({
                "id": addon_id, "name": root.attrib.get("name", addon_id),
                "version": addon_ver, "summary": summary_en(root),
                "github": f"https://github.com/{github}",
            })

    # 3) addons.xml + .md5 + index.html
    log("writing addons.xml")
    body = build_addons_xml(addon_roots)
    (DOCS / "addons.xml").write_bytes(body)
    (DOCS / "addons.xml.md5").write_text(hashlib.md5(body).hexdigest() + "\n")

    log("writing index.html")
    (DOCS / "index.html").write_text(render_index_html(rows), encoding="utf-8")

    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
