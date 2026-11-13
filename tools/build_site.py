#!/usr/bin/env python3
"""LORPcade site generator. Standard library only.

    python3 tools/build_site.py [--out _site]

Games are prebuilt: any folder that has an index.html is a game, and it is published as is
at /<folder-name>/. Looked for in two places, so use whichever you prefer:
    <repo>/<game>/index.html          (a folder at the top level of the repo)
    <repo>/games/<game>/index.html    (a folder inside games/)

An optional game.json next to the index.html sets the title, blurb, colour etc. (see README).
Nothing is compiled here; this only writes the home screen and copies the game folders.
"""
import argparse
import colorsys
import hashlib
import html
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_SRC = Path(__file__).resolve().parent / "site"
ASSETS = "arcade-assets"  # the home screen's own files; can't be used as a game name
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
THUMBS = ("thumb.png", "thumb.jpg", "thumb.jpeg", "thumb.webp", "thumb.gif")
HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
NOT_GAMES = {"tools", "games", ASSETS, "node_modules"}  # top-level folders never treated as games


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


# ---------------------------------------------------------------- detection

def discover():
    """-> {slug: folder}. A game is a folder containing index.html."""
    found = {}
    for base in (ROOT, ROOT / "games"):
        if not base.is_dir():
            continue
        for p in sorted(base.iterdir()):
            if not p.is_dir() or p.name.startswith((".", "_")) or not (p / "index.html").is_file():
                continue
            if base == ROOT and p.name in NOT_GAMES:
                continue
            if not SLUG_RE.match(p.name) or p.name == ASSETS:
                warn(f"skipping {p.relative_to(ROOT)}: folder names may only use letters, digits, '_' and '-' "
                     f"(and can't be '{ASSETS}')")
                continue
            if p.name in found:
                die(f"two game folders are both called '{p.name}': {found[p.name].relative_to(ROOT)} and "
                    f"{p.relative_to(ROOT)}")
            found[p.name] = p
    return found


# ---------------------------------------------------------------- manifest

def auto_accent(slug):
    hue = int(hashlib.sha1(slug.encode()).hexdigest()[:4], 16) % 360
    r, g, b = colorsys.hls_to_rgb(hue / 360, 0.6, 1.0)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def norm_hex(value):
    if not isinstance(value, str) or not HEX_RE.match(value):
        return None
    v = value.lower()
    return "#" + "".join(c * 2 for c in v[1:]) if len(v) == 4 else v


def load_game(slug, folder):
    raw = {}
    mf = folder / "game.json"
    if mf.is_file():
        try:
            raw = json.loads(mf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            die(f"{mf.relative_to(ROOT)} is not valid JSON: {e}")
        if not isinstance(raw, dict):
            die(f"{mf.relative_to(ROOT)} must be a JSON object")

    def text(key):
        v = raw.get(key)
        return v.strip() if isinstance(v, str) else ""

    if raw.get("accent") and not norm_hex(raw["accent"]):
        warn(f"{slug}/game.json: 'accent' should look like #ff2e97; using an automatic colour")

    thumb = None  # path relative to the game folder (it is published along with the game)
    wanted = ([raw["thumbnail"]] if isinstance(raw.get("thumbnail"), str) else []) + list(THUMBS)
    for name in wanted:
        if (folder / name).is_file():
            thumb = name.replace("\\", "/").lstrip("/")
            break

    requires = raw.get("requires", [])
    order = raw.get("order", 100)
    return {
        "slug": slug,
        "title": text("title") or slug.replace("_", " ").replace("-", " ").title(),
        "tagline": text("tagline"),
        "description": text("description"),
        "genre": text("genre"),
        "players": text("players"),
        "controls": text("controls"),
        "accent": norm_hex(raw.get("accent")) or auto_accent(slug),
        "requires": [str(r).lower() for r in requires] if isinstance(requires, list) else [],
        "order": order if isinstance(order, (int, float)) else 100,
        "hidden": raw.get("hidden") is True,
        "thumb": thumb,
    }


# ---------------------------------------------------------------- rendering

def render_card(game):
    e = html.escape
    if game["thumb"]:
        art = f'<img class="art-img" src="{game["slug"]}/{e(game["thumb"])}" alt="" loading="lazy">'
    else:
        art = '<div class="art-gen" aria-hidden="true"><i class="sun"></i><i class="floor"></i></div>'
    tags = "".join(f"<li>{e(t)}</li>" for t in (game["genre"], game["players"], game["controls"]) if t)
    tagline = f'<p class="tagline">{e(game["tagline"])}</p>' if game["tagline"] else ""
    desc = f'<p class="desc">{e(game["description"])}</p>' if game["description"] else ""
    return f"""
      <li class="slot">
        <a class="cab" href="{game["slug"]}/" style="--accent:{game["accent"]}" data-requires="{e(" ".join(game["requires"]))}">
          <div class="frame"><div class="cab-in">
            <div class="marquee"><span class="marquee-title">{e(game["title"])}</span></div>
            <div class="bezel"><div class="screen">{art}<span class="glass" aria-hidden="true"></span></div></div>
            <div class="deck">
              {tagline}{desc}
              <ul class="tags">{tags}</ul>
              <p class="warn">This game needs WebGPU, which this browser doesn’t report. Try a recent Chrome or Edge.</p>
              <div class="start"><i class="btn" aria-hidden="true"></i><span class="start-label">1P start</span></div>
            </div>
          </div></div>
        </a>
      </li>"""


EMPTY = ('<li class="empty"><p>No games on the floor yet.</p>'
         '<p>Add a game folder with an <code>index.html</code> and push to the main branch.</p></li>')


def build(out: Path):
    found = discover()
    games = [load_game(slug, folder) for slug, folder in found.items()]
    listed = sorted((g for g in games if not g["hidden"]), key=lambda g: (g["order"], g["title"].lower()))

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for slug, folder in found.items():
        shutil.copytree(folder, out / slug, ignore=shutil.ignore_patterns(".git", ".git*", ".DS_Store"))
        print(f"  game  {slug:<24} <- {folder.relative_to(ROOT)}/")

    shutil.copytree(SITE_SRC / "fonts", out / ASSETS / "fonts")

    repo = os.environ.get("GITHUB_REPOSITORY")
    sha = os.environ.get("GITHUB_SHA", "")[:7] or "local"
    page = (SITE_SRC / "index.template.html").read_text(encoding="utf-8")
    for token, value in {
        "{{CARDS}}": "".join(render_card(g) for g in listed) or EMPTY,
        "{{GAME_COUNT}}": f"{len(listed):02d}",
        "{{BUILD_SHA}}": sha,
        "{{BUILD_DATE}}": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "{{SOURCE}}": (f' <a href="https://github.com/{html.escape(repo)}">Source on GitHub</a>.' if repo else ""),
    }.items():
        page = page.replace(token, value)
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"  home  {len(listed)} game(s) listed, {len(games) - len(listed)} hidden -> {out}/index.html")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "_site")
    build(ap.parse_args().out)


if __name__ == "__main__":
    main()
