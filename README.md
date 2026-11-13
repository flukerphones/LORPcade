# LORPcade

A browser arcade hosted on GitHub Pages. Every game lives in its own folder under `games/`, and the
home screen is generated automatically from whatever is in there.

```
games/
  endless_sortie/     ->  https://<user>.github.io/<repo>/endless_sortie/
  your_next_game/     ->  https://<user>.github.io/<repo>/your_next_game/
tools/
  build_site.py       finds the games and generates the home screen
  site/               the home screen template + self-hosted fonts
.github/workflows/pages.yml
```

## One-time setup

1. Push this repo to GitHub (default branch `main`).
2. **Settings > Pages > Build and deployment > Source: GitHub Actions.**
3. Push a commit. The **Build and deploy LORPcade** workflow runs and publishes the site.

The first Rust build is slow (several minutes: fat LTO, plus compiling `wasm-bindgen-cli` once).
After that, dependencies are cached, and a game whose files haven't changed isn't rebuilt at all.

## Adding a game

Create `games/<name>/`. The folder name becomes the URL, so use letters, digits, `_` and `-`.
A folder is picked up as a game if it contains **any** of these:

| File | Meaning |
|---|---|
| `build_web.sh` | Build script. Run from inside the game folder; must produce `dist-web/index.html`. |
| `web/index.html` | A static game, published as is (no build step). |
| `game.json` | Home screen details (optional, see below). |

Inside a game, use **relative** URLs (`./game.js`, not `/game.js`): the game is served from a subfolder.

### `game.json` (optional)

Without one, the game still appears, with a title made from the folder name and an automatic colour.

```json
{
  "title": "Endless Sortie",
  "tagline": "Arcade combat flight",
  "description": "One or two sentences about the game.",
  "genre": "Flight combat",
  "players": "1 player",
  "controls": "Mouse + keyboard",
  "accent": "#2de2ff",
  "requires": ["webgpu"],
  "order": 10,
  "hidden": false
}
```

| Field | Effect |
|---|---|
| `title`, `tagline`, `description` | Marquee text and the blurb on the cabinet. |
| `genre`, `players`, `controls` | Small tags under the blurb. |
| `accent` | Neon colour for the cabinet (a bright hex like `#ff2e97` works best). |
| `requires` | `["webgpu"]` shows a warning on the cabinet in browsers without WebGPU. |
| `order` | Lower comes first (default 100). Ties sort by title. |
| `hidden` | `true` still publishes the game at its URL but leaves it off the home screen. |
| `thumbnail` | Optional image path. Without it, `thumb.png` / `.jpg` / `.webp` / `.gif` in the game folder is used, and without that the cabinet gets a generated screen. |

## Preview locally

```sh
sh games/endless_sortie/build_web.sh          # build the games that need it
python3 tools/build_site.py build             # writes _site/
python3 -m http.server 8080 --directory _site
```

Browsers won't load wasm from `file://`, so always serve over http.

## How the workflow runs

1. **discover** lists the game folders.
2. **build** runs one job per game, in parallel. Rust games get the toolchain and a dependency cache.
3. **assemble** generates the home screen and bundles every game into one site.
4. **deploy** publishes it (pushes to `main` only; pull requests stop after step 3).

If one game fails to build, nothing is deployed, so the live site never loses a game by accident.
