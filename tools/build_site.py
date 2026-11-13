#!/usr/bin/env python3
"""LORPcade site generator. Standard library only.

    python3 tools/build_site.py list                  JSON array of detected game folders (used by CI)
    python3 tools/build_site.py publish-dir <slug>    folder that gets published for one game (used by CI)
    python3 tools/build_site.py build [--built DIR] [--out _site]
                                                      assemble the homepage + every game into one site

A game is any folder under games/ that has a game.json, a build_web.sh, or a web/index.html.
The folder name is the URL: games/endless_sortie/ is served at <site>/endless_sortie/.

What gets published for a game:
  * has build_web.sh -> its dist-web/ folder (the script must create it)
  * otherwise        -> its web/ folder, as is

With --built DIR (CI), each game's finished files are read from DIR/game-<slug>/ instead.
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
GAMES = ROOT / "games"
SITE_SRC = Path(__file__).resolve().parent / "site"
ASSETS = "arcade-assets"  # reserved folder name for the homepage's own files
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
THUMBS = ("thumb.png", "thumb.jpg", "thumb.jpeg", "thumb.webp", "thumb.gif")
HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


# ---------------------------------------------------------------- detection

def looks_like_game(p: Path) -> bool:
    return (p / "game.json").is_file() or (p / "build_web.sh").is_file() or (p / "web" / "index.html").is_file()


def discover():
    if not GAMES.is_dir():
        return []
    found = []
    for p in sorted(GAMES.iterdir()):
        if not p.is_dir() or p.name.startswith((".", "_")) or not looks_like_game(p):
            continue
        if not SLUG_RE.match(p.name) or p.name == ASSETS:
            warn(f"skipping games/{p.name}: folder names may only use letters, digits, '_' and '-' "
                 f"(and can't be '{ASSETS}')")
            continue
        found.append(p.name)
    return found


def publish_dir(slug):
    g = GAMES / slug
    return g / "dist-web" if (g / "build_web.sh").is_file() else g / "web"


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


def load_game(slug):
    g = GAMES / slug
    raw = {}
    mf = g / "game.json"
    if mf.is_file():
        try:
            raw = json.loads(mf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            die(f"games/{slug}/game.json is not valid JSON: {e}")
        if not isinstance(raw, dict):
            die(f"games/{slug}/game.json must be a JSON object")

    def text(key):
        v = raw.get(key)
        return v.strip() if isinstance(v, str) else ""

    if raw.get("accent") and not norm_hex(raw["accent"]):
        warn(f"games/{slug}/game.json: 'accent' should look like #ff2e97; using an automatic colour")

    thumb = None
    for name in ([raw["thumbnail"]] if isinstance(raw.get("thumbnail"), str) else []) + list(THUMBS):
        cand = (g / name)
        if cand.is_file():
            thumb = cand
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
        art = (f'<img class="art-img" src="{ASSETS}/thumbs/{game["slug"]}{game["thumb"].suffix.lower()}" '
               f'alt="" loading="lazy">')
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
         '<p>Add a folder to <code>games/</code> and push to the main branch.</p></li>')


def build(out: Path, built: Path | None):
    games = [load_game(s) for s in discover()]
    listed = sorted((g for g in games if not g["hidden"]), key=lambda g: (g["order"], g["title"].lower()))

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for g in games:
        slug = g["slug"]
        src = (built / f"game-{slug}") if built else publish_dir(slug)
        if not (src / "index.html").is_file():
            hint = ("the CI build job for it must have failed or been skipped" if built
                    else f"run games/{slug}/build_web.sh first" if (GAMES / slug / "build_web.sh").is_file()
                    else f"it needs a web/index.html")
            die(f"no index.html for '{slug}' in {src} ({hint})")
        shutil.copytree(src, out / slug)
        print(f"  game  {slug:<24} <- {src.relative_to(ROOT) if src.is_relative_to(ROOT) else src}")

    assets = out / ASSETS
    shutil.copytree(SITE_SRC / "fonts", assets / "fonts")
    for g in listed:
        if g["thumb"]:
            (assets / "thumbs").mkdir(exist_ok=True)
            shutil.copy2(g["thumb"], assets / "thumbs" / f'{g["slug"]}{g["thumb"].suffix.lower()}')

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
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    pd = sub.add_parser("publish-dir")
    pd.add_argument("slug")
    b = sub.add_parser("build")
    b.add_argument("--built", type=Path, help="folder holding game-<slug>/ build outputs (CI)")
    b.add_argument("--out", type=Path, default=ROOT / "_site")
    args = ap.parse_args()

    if args.cmd == "list":
        print(json.dumps(discover()))
    elif args.cmd == "publish-dir":
        if args.slug not in discover():
            die(f"'{args.slug}' is not a game folder")
        print(publish_dir(args.slug).relative_to(ROOT).as_posix())
    else:
        build(args.out, args.built)


if __name__ == "__main__":
    main()
