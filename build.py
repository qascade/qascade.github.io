#!/usr/bin/env python3
"""Static site generator for this blog.

    python build.py              # build into dist/
    python build.py --clean      # wipe dist/ first
    python build.py --drafts     # include posts marked draft: true

Content lives in content/posts/*.md and content/pages/*.md, each with a
front-matter block delimited by '---'. Supported keys:

    title, date (YYYY-MM-DD), slug, tags (comma separated or [a, b]),
    description, draft (true/false), featured (true/false), toc (true/false)
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
DIST = ROOT / "dist"
CONFIG = ROOT / "site.json"

# NOTE: "extra" is expanded by hand here, minus fenced_code, because
# pymdownx.superfences replaces it (they cannot both be enabled).
MD_EXTENSIONS = [
    "tables",
    "footnotes",
    "attr_list",
    "def_list",
    "abbr",
    "md_in_html",
    "sane_lists",
    "smarty",          # curly quotes and dashes
    "admonition",      # !!! note / warning callouts
    "toc",
    # Shields $...$ / $$...$$ from the Markdown parser (so x_1 stays x_1 and
    # isn't turned into italics) and emits \(...\) / \[...\] for KaTeX.
    "pymdownx.arithmatex",
    "pymdownx.superfences",   # ```lang fences, nestable
    "pymdownx.highlight",     # Pygments syntax highlighting, at build time
    "pymdownx.inlinehilite",  # `#!python one_liner()` inline highlighting
    "pymdownx.tasklist",      # - [ ] / - [x] checkboxes
    "pymdownx.magiclink",     # bare URLs become links
]
MD_CONFIG = {
    "toc": {"permalink": False, "toc_depth": "2-3"},
    "pymdownx.arithmatex": {"generic": True},
    "pymdownx.highlight": {
        "use_pygments": True,
        "css_class": "highlight",
        "guess_lang": False,      # unlabelled fences stay plain
        "linenums": False,        # per-fence opt-in with ```python linenums="1"
        "anchor_linenums": True,
    },
    "pymdownx.tasklist": {"custom_checkbox": True},
}

# Pygments styles used for the light and dark theme families.
CODE_STYLE_LIGHT = "friendly"
CODE_STYLE_DARK = "github-dark"
LIGHT_THEMES = ('light', 'sepia', 'forest')
DARK_THEMES = ('dark', 'slate')


# --- shortcodes --------------------------------------------------------

YOUTUBE_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/|live/)|youtu\.be/)([\w-]{6,})")
VIMEO_ID = re.compile(r"vimeo\.com/(?:video/)?(\d+)")

SHORTCODE = re.compile(r"^@(youtube|vimeo|embed)\(([^)]+)\)\s*$", re.MULTILINE)
BARE_VIDEO_URL = re.compile(
    r"^(https?://(?:www\.)?(?:youtube\.com/\S+|youtu\.be/\S+|vimeo\.com/\S+))\s*$",
    re.MULTILINE)


def video_embed(kind: str, value: str, title: str = "Embedded video") -> str:
    """Return a responsive, lazy-loaded iframe for a video URL or bare id."""
    value = value.strip().strip("'\"")
    if kind == "youtube":
        m = YOUTUBE_ID.search(value)
        vid = m.group(1) if m else value
        # youtube-nocookie keeps the embed from setting tracking cookies
        src = f"https://www.youtube-nocookie.com/embed/{vid}?rel=0"
    elif kind == "vimeo":
        m = VIMEO_ID.search(value)
        src = f"https://player.vimeo.com/video/{m.group(1) if m else value}"
    else:
        src = value
    return (
        '<div class="embed embed-16x9">'
        f'<iframe src="{html.escape(src, quote=True)}" title="{html.escape(title, quote=True)}" '
        'loading="lazy" frameborder="0" allowfullscreen '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
        'gyroscope; picture-in-picture; web-share"></iframe>'
        "</div>"
    )


def expand_shortcodes(body: str) -> str:
    """Turn @youtube(...) / @vimeo(...) / @embed(...) lines - and bare video
    URLs on a line of their own - into responsive iframes."""
    def shortcode(m: re.Match) -> str:
        return "\n" + video_embed(m.group(1), m.group(2)) + "\n"

    def bare(m: re.Match) -> str:
        url = m.group(1)
        kind = "vimeo" if "vimeo." in url else "youtube"
        return "\n" + video_embed(kind, url) + "\n"

    body = SHORTCODE.sub(shortcode, body)
    return BARE_VIDEO_URL.sub(bare, body)


# --- helpers -----------------------------------------------------------

def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", str(value).lower()).strip()
    return re.sub(r"[\s_-]+", "-", value) or "untitled"


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Split a '---' delimited front-matter block off the top of the file."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n", 1)[1].split("\n---", 1)
    if len(parts) != 2:
        return {}, text
    raw, body = parts
    meta: dict[str, object] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            val = val[1:-1]
            meta[key] = [v.strip().strip("'\"") for v in val.split(",") if v.strip()]
            continue
        val = val.strip("'\"")
        low = val.lower()
        if low in ("true", "yes"):
            meta[key] = True
        elif low in ("false", "no"):
            meta[key] = False
        elif key == "tags":
            meta[key] = [v.strip() for v in val.split(",") if v.strip()]
        else:
            meta[key] = val
    return meta, body.lstrip("\n")


def plain_text(rendered_html: str) -> str:
    text = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", rendered_html)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def excerpt_of(rendered_html: str, limit: int = 240) -> str:
    text = plain_text(rendered_html)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return cut[: cut.rfind(" ")] + "…"


def date_of(meta: dict, path: Path) -> datetime:
    raw = str(meta.get("date", "")).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)  # fall back to filename
    if m:
        return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- loading -----------------------------------------------------------

ROOT_RELATIVE = re.compile(r'(href|src)="/(?!/)')


def with_base_path(rendered: str, base: str) -> str:
    """Prefix root-relative links in post HTML when the site is served from a
    subdirectory (e.g. a GitHub Pages project site at /my-blog/)."""
    if not base:
        return rendered
    return ROOT_RELATIVE.sub(rf'\1="{base}/', rendered)


def load_doc(path: Path, md: markdown.Markdown, base: str = "") -> dict:
    meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
    md.reset()
    rendered = with_base_path(md.convert(expand_shortcodes(body)), base)
    words = len(plain_text(rendered).split())
    has_math = 'class="arithmatex"' in rendered
    title = meta.get("title") or re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem).replace("-", " ").title()
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return {
        "source": path,
        "title": title,
        "slug": meta.get("slug") or slugify(re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)),
        "html": rendered,
        "toc": md.toc if meta.get("toc") else "",
        "tags": tags,
        "draft": bool(meta.get("draft", False)),
        "featured": bool(meta.get("featured", False)),
        "description": meta.get("description", ""),
        "excerpt": meta.get("description") or excerpt_of(rendered),
        "words": words,
        "has_math": has_math,
        "series": str(meta.get("series", "")).strip(),
        "order": int(str(meta.get("order", "0")).strip() or 0)
                 if str(meta.get("order", "0")).strip().isdigit() else 0,
        "reading_time": max(1, round(words / 220)),
        "meta": meta,
    }


def load_posts(md: markdown.Markdown, include_drafts: bool, base: str = "") -> list[dict]:
    posts = []
    for path in sorted((CONTENT / "posts").glob("*.md")):
        doc = load_doc(path, md, base)
        if doc["draft"] and not include_drafts:
            continue
        dt = date_of(doc["meta"], path)
        doc.update(
            date=dt,
            date_short=dt.strftime("%d %b %Y"),
            date_long=dt.strftime("%d %B %Y"),
            rfc822=format_datetime(dt),
            url=f"{base}/{doc['slug']}/",
        )
        posts.append(doc)
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def load_pages(md: markdown.Markdown, base: str = "") -> list[dict]:
    pages = []
    for path in sorted((CONTENT / "pages").glob("*.md")):
        doc = load_doc(path, md, base)
        if doc["draft"]:
            continue
        doc["url"] = f"{base}/{doc['slug']}/"
        pages.append(doc)
    return pages


# --- build -------------------------------------------------------------

def group_by_series(posts: list[dict]) -> dict[str, list[dict]]:
    """Posts that declare a series, in reading order (front-matter `order`)."""
    series: dict[str, list[dict]] = {}
    for p in posts:
        if p.get("series"):
            series.setdefault(p["series"], []).append(p)
    for items in series.values():
        items.sort(key=lambda p: (p["order"], p["title"]))
    return series


def group_by_year(posts: list[dict]) -> list[tuple[int, list[dict]]]:
    years: dict[int, list[dict]] = {}
    for p in posts:
        years.setdefault(p["date"].year, []).append(p)
    return sorted(years.items(), reverse=True)


def build_code_css() -> str:
    """Generate Pygments CSS, scoped so each colour theme gets the right
    palette (light styles for the light themes, dark for the dark ones)."""
    from pygments.formatters import HtmlFormatter

    light = HtmlFormatter(style=CODE_STYLE_LIGHT)
    dark = HtmlFormatter(style=CODE_STYLE_DARK)

    light_sel = [".highlight"] + [f':root[data-theme="{t}"] .highlight' for t in LIGHT_THEMES]
    dark_sel = [f':root[data-theme="{t}"] .highlight' for t in DARK_THEMES]
    auto_sel = [':root:not([data-theme]) .highlight', ':root[data-theme="auto"] .highlight']

    auto_block = dark.get_style_defs(auto_sel)
    auto_block = "\n".join("  " + line for line in auto_block.splitlines())

    return "\n".join([
        f"/* GENERATED by build.py - Pygments '{CODE_STYLE_LIGHT}' (light)"
        f" and '{CODE_STYLE_DARK}' (dark). Do not edit by hand. */",
        "",
        light.get_style_defs(light_sel),
        "",
        dark.get_style_defs(dark_sel),
        "",
        "@media (prefers-color-scheme: dark) {",
        auto_block,
        "}",
        "",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the static blog.")
    ap.add_argument("--clean", action="store_true", help="remove dist/ before building")
    ap.add_argument("--drafts", action="store_true", help="include draft posts")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--livereload", action="store_true",
                    help="inject the dev live-reload script (used by serve.py)")
    args = ap.parse_args()

    site = json.loads(CONFIG.read_text(encoding="utf-8"))
    site["base_url"] = site.get("base_url", "").rstrip("/")
    # base_path is for GitHub Pages *project* sites served from /<repo>/.
    # Leave it "" for a user site (<name>.github.io) or a custom domain.
    base = "/" + site.get("base_path", "").strip("/") if site.get("base_path", "").strip("/") else ""
    site["base_path"] = base
    for group in ("nav", "social"):
        for item in site.get(group, []):
            if item.get("url", "").startswith("/"):
                item["url"] = base + item["url"]

    md = markdown.Markdown(extensions=MD_EXTENSIONS, extension_configs=MD_CONFIG,
                           output_format="html5")

    posts = load_posts(md, args.drafts, base)
    pages = load_pages(md, base)

    if args.clean and DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["slug"] = slugify

    tag_counts: dict[str, int] = {}
    for p in posts:
        for t in p["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    all_tags = sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))

    now = datetime.now(timezone.utc)
    series = group_by_series(posts)
    series_list = [
        {"name": name, "slug": slugify(name), "url": f"{base}/series/{slugify(name)}/",
         "count": len(items), "items": items}
        for name, items in sorted(series.items(), key=lambda kv: -len(kv[1]))
    ]
    recent = posts[: site.get("home_recent_count", 5)]
    shared = {
        "site": site,
        "now": now,
        "recent": recent,
        "all_tags": all_tags,
        "pages": pages,
        "livereload": args.livereload,
        "base": base,
        "series_list": series_list,
    }

    # home
    write(DIST / "index.html", env.get_template("index.html").render(
        sidebar=False,
        featured=[p for p in posts if p["featured"]][:5],
        by_year=group_by_year(posts),
        **shared,
    ))

    # posts
    post_tpl = env.get_template("post.html")
    for i, p in enumerate(posts):
        sib = series.get(p.get("series"), [])
        at = sib.index(p) if p in sib else -1
        write(DIST / p["slug"] / "index.html", post_tpl.render(
            post=p,
            series_name=p.get("series"),
            series_url=f"{base}/series/{slugify(p['series'])}/" if p.get("series") else None,
            series_pos=at + 1,
            series_total=len(sib),
            series_prev=sib[at - 1] if at > 0 else None,
            series_next=sib[at + 1] if -1 < at < len(sib) - 1 else None,
            prev=posts[i + 1] if i + 1 < len(posts) else None,
            next=posts[i - 1] if i > 0 else None,
            sidebar=True,
            has_math=p["has_math"],
            **shared,
        ))

    # standalone pages
    page_tpl = env.get_template("page.html")
    for pg in pages:
        write(DIST / pg["slug"] / "index.html", page_tpl.render(
            page=pg, sidebar=True, has_math=pg["has_math"], **shared))

    # archive + tags
    list_tpl = env.get_template("list.html")
    write(DIST / "archive" / "index.html", list_tpl.render(
        heading="Archive",
        subheading=f"{len(posts)} post{'s' if len(posts) != 1 else ''}, newest first.",
        grouped=group_by_year(posts), posts=posts, sidebar=True, **shared,
    ))
    for s in series_list:
        write(DIST / "series" / s["slug"] / "index.html", list_tpl.render(
            heading=s["name"],
            subheading=f"{s['count']} notes, in reading order.",
            grouped=None, posts=s["items"], ordered=True, sidebar=True, **shared,
        ))
    for tag, _ in all_tags:
        tagged = [p for p in posts if tag in p["tags"]]
        write(DIST / "tags" / slugify(tag) / "index.html", list_tpl.render(
            heading=f"#{tag}",
            subheading=f"{len(tagged)} post{'s' if len(tagged) != 1 else ''} tagged {tag}.",
            grouped=None, posts=tagged, sidebar=True, **shared,
        ))

    # feed + sitemap + robots
    write(DIST / "feed.xml", env.get_template("feed.xml").render(
        site=site, posts=posts[:20], build_date=format_datetime(now),
    ))
    urls = [f"{base}/", f"{base}/archive/"] + [p["url"] for p in posts] + [pg["url"] for pg in pages]
    urls += [f"{base}/tags/{slugify(t)}/" for t, _ in all_tags]
    urls += [s["url"] for s in series_list]
    sitemap = "\n".join(
        f"  <url><loc>{site['base_url']}{u}</loc></url>" for u in urls
    )
    write(DIST / "sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f"{sitemap}\n</urlset>\n")
    write(DIST / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {site['base_url']}/sitemap.xml\n")

    # 404
    write(DIST / "404.html", list_tpl.render(
        heading="Page not found",
        subheading="That link has gone missing. Try the archive below.",
        grouped=group_by_year(posts), posts=posts, sidebar=False, **shared,
    ))

    # static assets, then the generated syntax-highlighting palette
    if STATIC.exists():
        shutil.copytree(STATIC, DIST, dirs_exist_ok=True)
    write(DIST / "css" / "code.css", build_code_css())

    if not args.quiet:
        drafts = len(list((CONTENT / "posts").glob("*.md"))) - len(posts)
        print(f"built {len(posts)} posts, {len(pages)} pages, {len(all_tags)} tags -> {DIST.relative_to(ROOT)}/"
              + (f"  ({drafts} draft(s) skipped)" if drafts > 0 and not args.drafts else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
