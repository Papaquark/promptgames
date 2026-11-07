#!/usr/bin/env python3
"""Build the Prompt & Play static site.

Content lives in games/<slug>/ as game.json, prompt.md and an icon.
The generated site is written to dist/.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import webbrowser
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # Pillow is optional if every icon is already 64x64 PNG.
    Image = None
    ImageDraw = None
    ImageFont = None

ROOT = Path(__file__).resolve().parent
GAMES_DIR = ROOT / "games"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
DIST_DIR = ROOT / "dist"
SITE_FILE = ROOT / "site.json"

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{1,8})*$")
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)


class BuildError(Exception):
    """A problem with the site content or configuration."""


@dataclass(frozen=True)
class Game:
    slug: str
    title: str
    description: str
    author: str
    icon: Path | None
    prompt: str
    word_count: int
    language: str
    language_label: str


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BuildError(f"{path} does not exist") from exc
    except json.JSONDecodeError as exc:
        raise BuildError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise BuildError(f"{path} must contain a JSON object")
    return data


def required_string(data: dict, key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BuildError(f"{context}: '{key}' must be a non-empty string")
    return value.strip()


def load_site() -> dict:
    data = load_json(SITE_FILE)
    site = {
        "name": required_string(data, "name", "site.json"),
        "tagline": required_string(data, "tagline", "site.json"),
        "description": required_string(data, "description", "site.json"),
        "intro": required_string(data, "intro", "site.json"),
        "defaultAuthor": required_string(data, "defaultAuthor", "site.json"),
        "playUrl": required_string(data, "playUrl", "site.json"),
        "baseUrl": str(data.get("baseUrl", "")).strip().rstrip("/"),
    }

    if not site["playUrl"].startswith(("https://", "http://")):
        raise BuildError("site.json: 'playUrl' must start with https:// or http://")

    if site["baseUrl"] and not site["baseUrl"].startswith(("https://", "http://")):
        raise BuildError("site.json: 'baseUrl' must be empty or start with https:// or http://")

    return site


def load_games(site: dict) -> list[Game]:
    if not GAMES_DIR.is_dir():
        raise BuildError("The games/ directory does not exist")

    games: list[Game] = []
    errors: list[str] = []

    for game_dir in sorted(GAMES_DIR.iterdir()):
        if not game_dir.is_dir() or game_dir.name.startswith("."):
            continue

        slug = game_dir.name
        context = f"games/{slug}"

        try:
            if not SLUG_RE.fullmatch(slug):
                raise BuildError(
                    "folder name must use lowercase letters, numbers and single hyphens"
                )

            data = load_json(game_dir / "game.json")
            title = required_string(data, "title", f"{context}/game.json")
            description = required_string(data, "description", f"{context}/game.json")
            author = data.get("author", site["defaultAuthor"])
            if not isinstance(author, str) or not author.strip():
                raise BuildError(f"{context}/game.json: 'author' must be a non-empty string")
            author = author.strip()

            language = data.get("language", "en")
            if not isinstance(language, str) or not language.strip():
                raise BuildError(f"{context}/game.json: 'language' must be a non-empty string")
            language = language.strip()
            if not LANGUAGE_RE.fullmatch(language):
                raise BuildError(
                    f"{context}/game.json: 'language' must be a language code such as 'en' or 'sv'"
                )

            language_label = data.get("languageLabel", language.upper())
            if not isinstance(language_label, str) or not language_label.strip():
                raise BuildError(
                    f"{context}/game.json: 'languageLabel' must be a non-empty string"
                )
            language_label = language_label.strip()

            prompt_name = data.get("prompt", "prompt.md")
            if not isinstance(prompt_name, str) or not prompt_name.strip():
                raise BuildError(f"{context}/game.json: 'prompt' must be a file name")
            prompt_path = game_dir / prompt_name
            try:
                prompt = prompt_path.read_text(encoding="utf-8")
            except FileNotFoundError as exc:
                raise BuildError(f"{context}: prompt file '{prompt_name}' is missing") from exc
            if not prompt.strip():
                raise BuildError(f"{context}: prompt file '{prompt_name}' is empty")

            icon_name = data.get("icon", "icon.png")
            if not isinstance(icon_name, str) or not icon_name.strip():
                raise BuildError(f"{context}/game.json: 'icon' must be a file name")
            icon_path = game_dir / icon_name
            icon = icon_path if icon_path.exists() else None

            words = len(WORD_RE.findall(prompt))
            games.append(
                Game(
                    slug=slug,
                    title=title,
                    description=description,
                    author=author,
                    icon=icon,
                    prompt=prompt,
                    word_count=words,
                    language=language,
                    language_label=language_label,
                )
            )
        except BuildError as exc:
            errors.append(str(exc))

    if errors:
        raise BuildError("\n".join(errors))
    if not games:
        raise BuildError("No games found. Add a folder under games/ with a game.json and prompt.md")

    return sorted(games, key=lambda game: game.title.casefold())


def fallback_icon(title: str) -> "Image.Image":
    """A simple gold monogram for a game without an icon."""
    image = Image.new("RGBA", (64, 64), (13, 11, 10, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, 61, 61), outline=(107, 76, 42, 255), width=1)
    draw.rectangle((6, 6, 57, 57), outline=(58, 43, 31, 255), width=1)

    letter = (title.strip()[:1] or "?").upper()
    try:
        font = ImageFont.load_default(size=32)
    except TypeError:  # Older Pillow
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), letter, font=font)
    width = box[2] - box[0]
    height = box[3] - box[1]
    draw.text(
        (32 - width / 2 - box[0], 32 - height / 2 - box[1]),
        letter,
        fill=(217, 169, 78, 255),
        font=font,
    )
    return image


def write_icon(game: Game, destination: Path) -> None:
    if Image is None:
        if game.icon is None:
            raise BuildError(
                f"games/{game.slug}: icon is missing and Pillow is not installed to generate one"
            )
        if game.icon.suffix.lower() != ".png":
            raise BuildError(
                f"games/{game.slug}: without Pillow, icons must be PNG files"
            )
        header = game.icon.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            raise BuildError(f"games/{game.slug}: '{game.icon.name}' is not a valid PNG")
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        if (width, height) != (64, 64):
            raise BuildError(
                f"games/{game.slug}: without Pillow, icons must already be 64x64 PNGs "
                f"('{game.icon.name}' is {width}x{height})"
            )
        shutil.copyfile(game.icon, destination)
        return

    if game.icon is None:
        print(f"  note: games/{game.slug} has no icon; generated a fallback")
        fallback_icon(game.title).save(destination, "PNG", optimize=True)
        return

    try:
        with Image.open(game.icon) as source:
            image = source.convert("RGBA")
    except OSError as exc:
        raise BuildError(f"games/{game.slug}: could not read icon '{game.icon.name}': {exc}") from exc

    width, height = image.size
    if width != height:
        raise BuildError(
            f"games/{game.slug}: icon '{game.icon.name}' is {width}x{height}; it must be square"
        )
    if width < 16:
        raise BuildError(f"games/{game.slug}: icon '{game.icon.name}' is too small")

    if (width, height) == (64, 64):
        result = image
    else:
        resample = Image.Resampling.NEAREST if width < 64 else Image.Resampling.LANCZOS
        result = image.resize((64, 64), resample)

    result.save(destination, "PNG", optimize=True)


def render_template(name: str, context: dict[str, str]) -> str:
    template = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    required = set(PLACEHOLDER_RE.findall(template))
    missing = required - context.keys()
    if missing:
        raise BuildError(
            f"templates/{name}: missing values for {', '.join(sorted(missing))}"
        )

    for key, value in context.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def page_url(site: dict, path: str) -> str:
    if not site["baseUrl"]:
        return ""
    if path in ("index.html", "./", ""):
        return f"{site['baseUrl']}/"
    return f"{site['baseUrl']}/{path.lstrip('/')}"


def meta_tags(
    site: dict,
    title: str,
    description: str,
    page: str,
    image: str = "",
    og_type: str = "website",
) -> str:
    tags = [
        f'<meta property="og:type" content="{escape(og_type)}">',
        f'<meta property="og:site_name" content="{escape(site["name"])}">',
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        f'<meta name="twitter:card" content="summary">',
        f'<meta name="twitter:title" content="{escape(title)}">',
        f'<meta name="twitter:description" content="{escape(description)}">',
    ]

    url = page_url(site, page)
    if url:
        tags.append(f'<meta property="og:url" content="{escape(url)}">')
        tags.append(f'<link rel="canonical" href="{escape(url)}">')

    if image:
        image_url = page_url(site, image)
        if image_url:
            tags.append(f'<meta property="og:image" content="{escape(image_url)}">')
            tags.append(f'<meta name="twitter:image" content="{escape(image_url)}">')

    return "\n  ".join(tags)


def language_badge(game: Game) -> str:
    if game.language.lower() == "en":
        return ""
    return (
        f'<span class="language-badge" lang="{escape(game.language)}">'
        f"{escape(game.language_label)}</span>"
    )


def card_html(game: Game) -> str:
    badge = language_badge(game)
    return f"""<a class="game-card" href="games/{game.slug}.html">
          <span class="card-icon-frame">
            <img class="card-icon" src="static/icons/{game.slug}.png" alt="" width="64" height="64">
          </span>
          <span class="card-body">
            <span class="card-kicker-row">
              <span class="card-kicker">Solo prompt game</span>
              {badge}
            </span>
            <span class="card-title" lang="{escape(game.language)}">{escape(game.title)}</span>
            <span class="card-author">by {escape(game.author)}</span>
            <span class="card-description" lang="{escape(game.language)}">{escape(game.description)}</span>
            <span class="card-cta">Open the game <span aria-hidden="true">&rarr;</span></span>
          </span>
        </a>"""


def build_index(site: dict, games: list[Game]) -> str:
    cards = "\n        ".join(card_html(game) for game in games)
    title = f"{site['name']} — {site['tagline']}"
    meta = meta_tags(site, title, site["description"], "index.html")

    return render_template(
        "index.html",
        {
            "SITE_NAME": escape(site["name"]),
            "TAGLINE": escape(site["tagline"]),
            "DESCRIPTION": escape(site["description"]),
            "INTRO": escape(site["intro"]),
            "GAME_COUNT": str(len(games)),
            "GAME_PLURAL": "" if len(games) == 1 else "s",
            "GAME_CARDS": cards,
            "META": meta,
            "PLAY_URL": escape(site["playUrl"]),
        },
    )


def build_game(site: dict, game: Game) -> str:
    title = f"{game.title} — {site['name']}"
    meta = meta_tags(
        site,
        title,
        game.description,
        f"games/{game.slug}.html",
        f"static/icons/{game.slug}.png",
        og_type="article",
    )

    return render_template(
        "game.html",
        {
            "SITE_NAME": escape(site["name"]),
            "TAGLINE": escape(site["tagline"]),
            "TITLE": escape(game.title),
            "AUTHOR": escape(game.author),
            "DESCRIPTION": escape(game.description),
            "PROMPT": escape(game.prompt),
            "WORD_COUNT": f"{game.word_count:,}",
            "ICON": f"../static/icons/{game.slug}.png",
            "PLAY_URL": escape(site["playUrl"]),
            "LANG": escape(game.language),
            "LANGUAGE_BADGE": language_badge(game),
            "META": meta,
        },
    )


def build() -> list[Game]:
    site = load_site()
    games = load_games(site)

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    (DIST_DIR / "games").mkdir(parents=True)
    (DIST_DIR / "static" / "icons").mkdir(parents=True)

    if not STATIC_DIR.is_dir():
        raise BuildError("The static/ directory does not exist")
    shutil.copytree(STATIC_DIR, DIST_DIR / "static", dirs_exist_ok=True)

    for game in games:
        write_icon(game, DIST_DIR / "static" / "icons" / f"{game.slug}.png")

    (DIST_DIR / "index.html").write_text(build_index(site, games), encoding="utf-8")

    for game in games:
        (DIST_DIR / "games" / f"{game.slug}.html").write_text(
            build_game(site, game), encoding="utf-8"
        )

    # Stop GitHub Pages from running Jekyll over the generated output.
    (DIST_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Built {len(games)} game{'s' if len(games) != 1 else ''} into {DIST_DIR}/")
    for game in games:
        print(f"  games/{game.slug}.html  ({game.word_count:,} words)")
    if not site["baseUrl"]:
        print("  note: set 'baseUrl' in site.json to enable canonical/Open Graph URLs")
    return games


def serve(port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(DIST_DIR))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        url = f"http://localhost:{port}/"
        print(f"Serving {DIST_DIR}/ at {url}")
        print("Press Ctrl+C to stop.")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Prompt & Play site.")
    parser.add_argument("--serve", action="store_true", help="serve dist/ after building")
    parser.add_argument("--port", type=int, default=8000, help="port for --serve (default 8000)")
    args = parser.parse_args()

    try:
        build()
    except BuildError as exc:
        print(f"\nBuild failed:\n{exc}\n", file=sys.stderr)
        return 1

    if args.serve:
        serve(args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
