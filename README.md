# Prompt & Play

A small, playful fantasy library of prompt games. Each game is a self-contained prompt that turns a capable AI into a game master. Visitors can read the prompt, copy it, or open Google Gemini with it ready to paste.

The visual style is a bright storybook built from the 64×64 Hovdingen pixel art: cream paper, dark plum ink, grass green, and roof orange, with chunky borders and hard offset shadows. Headings use the self-hosted Bricolage Grotesque font, while the layout stays simple and readable with a playful tone rather than a grim one.

The site is a static site generated with Python. There is no server, database, login, or JavaScript framework.

## Quick start

Requirements: Python 3.10+ and Pillow (used to normalise icons).

```bash
python3 -m pip install -r requirements.txt
python3 build.py --serve
```

Then open <http://localhost:8000/>.

To build without serving:

```bash
python3 build.py
```

The generated site is written to `dist/`. Open `dist/index.html` through a local server rather than `file://` so clipboard permissions behave correctly.

## Adding a game

Create a folder under `games/` whose name is the URL slug. Use lowercase letters, numbers, and single hyphens.

```
games/my-new-game/
├─ game.json
├─ prompt.md
└─ icon.png
```

`game.json`:

```json
{
  "title": "My New Game",
  "description": "One or two sentences that make someone want to play.",
  "author": "Michael",
  "icon": "icon.png"
}
```

- `title`, `description`, and `author` are required.
- `author` falls back to `defaultAuthor` in `site.json`.
- `icon` defaults to `icon.png`.
- The prompt file defaults to `prompt.md`; set `"prompt": "another-file.md"` to use a different file.
- The prompt is shown exactly as written, so plain text or Markdown both work.

For a non-English game, add its language metadata:

```json
{
  "language": "sv",
  "languageLabel": "Svenska"
}
```

- `language` is an optional language code and defaults to `en`. Non-English games get a language badge and correct `lang` attributes for screen readers.
- `languageLabel` is the badge text. It defaults to the uppercase language code.

Then run:

```bash
python3 build.py
```

### Icons

Each game needs a square image. A 64×64 PNG is ideal. Larger square PNG, JPEG, or WebP images are automatically resized to 64×64 PNG. Non-square images stop the build with an error. If Pillow is not installed, icons must already be 64×64 PNG files.

If an icon is missing and Pillow is available, the build creates a simple monogram fallback and prints a note.

## Site settings

Edit `site.json`:

| Field | Purpose |
| --- | --- |
| `name` | Site name shown in the header and page titles. |
| `tagline` | Short line under the logo. |
| `description` | Meta description and social preview text. |
| `intro` | Introduction paragraph on the home page. |
| `defaultAuthor` | Author used when a game omits one. |
| `playUrl` | URL opened by the Play button. Defaults to Gemini. |
| `baseUrl` | Optional public URL used for canonical and Open Graph tags. |

For GitHub Pages, set `baseUrl` to the public site address after the first deploy, for example:

```json
"baseUrl": "https://yourname.github.io/promptgames"
```

Leave it empty for local development. The site works without it; only the canonical and social-image tags are omitted.

## Deploying to GitHub Pages

1. Create a GitHub repository and push this project to the `main` branch.
2. In the repository, open **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Push a change to `main`, or run the **Deploy to GitHub Pages** workflow manually.
5. The site will be published at `https://yourname.github.io/repository-name/`.

The workflow in `.github/workflows/pages.yml` installs Pillow, runs `build.py`, and deploys `dist/`. All links are relative, so the site works whether it is hosted at a domain root or under a repository subpath.

You can also upload the contents of `dist/` to any static host (Netlify, Cloudflare Pages, a VPS, and so on).

## How the Play button works

Google Gemini does not support pre-filling a prompt through a URL. The Play button therefore:

1. Copies the full prompt to the clipboard while the page still has focus.
2. Opens `https://gemini.google.com/app` in a new tab.
3. Shows a message asking the player to paste the prompt and press send.

Copying happens before the new tab opens. Opening the tab first would consume the browser's user activation and move focus away, which causes clipboard writes to fail.

This works for prompts of any length. Clipboard access requires HTTPS or `localhost`; GitHub Pages provides HTTPS.

## Included games

- `games/hovdingen/` — **Hövdingen**, a Swedish narrative strategy game set in Skogsbryn. It uses `"language": "sv"` and `"languageLabel": "Svenska"`.
- `games/ceo/` — **CEO**, a Swedish satirical business strategy game about running Färgstark Doft & Svamp AB. It also uses `"language": "sv"` and `"languageLabel": "Svenska"`.

The build currently contains these two games. Add more folders under `games/` to expand the library. Keep at least one game in `games/` or the build will stop with an error.

## Project layout

```
build.py                  # Build script and content validation
requirements.txt          # Python dependency (Pillow)
site.json                 # Site name, copy, default author, Gemini URL
games/<slug>/             # One folder per game
templates/                # HTML templates
static/                   # CSS, JS, favicon, self-hosted fonts
dist/                     # Generated output (not committed)
.github/workflows/        # GitHub Pages deployment
```

## Accessibility notes

The site uses semantic landmarks, a skip link, visible focus styles, 48px action targets, `aria-live` status messages, and a reduced-motion fallback. The prompt preview is plain selectable text and expands without JavaScript being required to read it.

## Troubleshooting

- **“icon must be square”** — crop or resize the icon to a square image. The build will resize it to 64×64.
- **“prompt file is missing”** — check the `prompt` value in `game.json`, or add `prompt.md`.
- **Copy does not work** — serve the site over `localhost` or HTTPS. Browsers restrict clipboard access on `file://`.
- **Play opens Gemini but nothing is pasted** — this is expected. The prompt is copied; paste it manually and press send.
- **Play opens Gemini but the clipboard is empty** — allow clipboard access if your browser asks, and reload the page after updating the site so it uses the current `app.js`.
