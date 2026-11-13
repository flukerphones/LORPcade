# LORPcade

A browser arcade on GitHub Pages. Each game is a folder of finished files (`index.html`, `.js`, `.wasm`, ...)
committed to this repo. On every push to `main`, a workflow generates the LORPcade home screen, finds the
games on its own, and deploys everything. Nothing is compiled in CI.

```
endless_sortie/        ->  https://<user>.github.io/<repo>/endless_sortie/
    index.html
    endless_sortie.js
    endless_sortie_bg.wasm
    game.json          (optional)
your_next_game/        ->  https://<user>.github.io/<repo>/your_next_game/
tools/                 home screen generator + template + fonts
.github/workflows/pages.yml
```

Game folders can sit at the top level of the repo (as above) or inside a `games/` folder. Either works.

## One-time setup

1. Push this repo to GitHub (default branch `main`).
2. **Settings > Pages > Build and deployment > Source: GitHub Actions.**
3. Push a commit.

## Adding a game

Copy the game's finished files into a new folder. Any folder with an `index.html` is a game, and the folder
name is its URL (letters, digits, `_` and `-` only). Use **relative** URLs inside the game (`./game.js`,
not `/game.js`), since it is served from a subfolder. Wasm needs a real http(s) server, which Pages is.

### `game.json` (optional)

Without one, the game still appears, with a title made from the folder name and an automatic neon colour.

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
| `accent` | Neon colour for the cabinet (a bright hex works best). |
| `requires` | `["webgpu"]` shows a warning on the cabinet in browsers without WebGPU. |
| `order` | Lower comes first (default 100). Ties sort by title. |
| `hidden` | `true` still publishes the game at its URL but leaves it off the home screen. |
| `thumbnail` | Image path inside the game folder. Without it, a `thumb.png` / `.jpg` / `.webp` / `.gif` in the folder is used, and without that the cabinet gets a generated screen. |

## Preview locally

```sh
python3 tools/build_site.py                    # writes _site/
python3 -m http.server 8080 --directory _site
```
