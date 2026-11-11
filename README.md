# Seedha Passion

A small static blog generator. Markdown in, plain HTML out — no database, no
admin panel, no runtime dependencies for your readers.

## Setup (once)

```bash
make setup          # creates .venv and installs markdown, jinja2, pygments
```

## Writing

```bash
make serve                        # http://localhost:8000, rebuilds as you save
make post t="Why I changed my mind"   # scaffolds content/posts/2026-11-12-why-i-changed-my-mind.md
make page t="Now"                 # scaffolds content/pages/now.md
make drafts                       # preview including draft: true posts
```

Leave `make serve` running in one terminal and edit Markdown in your editor.
Every save rebuilds in well under a second and the open browser tab refreshes
itself.

You can also just drop any `.md` file into `content/posts/` — the watcher picks
it up. The only requirement is a front-matter block at the top:

```markdown
---
title: Why I changed my mind
date: 2026-11-12
tags: ai, essays
description: One line used for the meta description and the RSS summary.
draft: false       # true keeps it out of the build
featured: true     # shows it in "Start here" on the homepage
toc: true          # renders a table of contents
---

Your post starts here.
```

`slug:` is optional — it defaults to the filename minus the date prefix, so the
file above publishes at `/why-i-changed-my-mind/`.

### What you can write

| You want            | You write                                    |
| ------------------- | -------------------------------------------- |
| Inline math         | `$1 - (1-p)^n$`                              |
| Display math        | `$$ ... $$` on its own lines                 |
| Highlighted code    | ```` ```python ```` fence (600+ languages)   |
| Line numbers        | ```` ```python linenums="1" ````             |
| YouTube / Vimeo     | `@youtube(VIDEO_ID_OR_URL)` on its own line  |
| Any iframe          | `@embed(https://...)`                        |
| Callout             | `!!! note` + indented body                   |
| Footnote            | `text[^tag]` and `[^tag]: the note`          |
| Checkboxes          | `- [ ]` / `- [x]`                            |
| Image               | `![alt](/img/photo.jpg)` — put files in `static/img/` |

Math only loads KaTeX on pages that use it. Highlighting is done at build time,
so it costs your readers nothing.

### Site-wide settings

Everything else lives in `site.json`: title, tagline, author, the nav and
footer links, and the intro blurb on the homepage and sidebar.

## Themes

Six colour schemes in the top-right picker — Auto (follows the OS), Light,
Dark, Sepia, Slate, Forest. The choice is remembered per visitor and applied
before first paint, so there is no flash on load.

Each theme is one block of CSS variables near the top of `static/css/style.css`.
To add your own, copy a block, rename the `data-theme` value, and add a matching
`<li>` to the picker in `templates/base.html`.

## Deploying free on GitHub Pages

`.github/workflows/deploy.yml` is already here. It builds the site and
publishes it on every push to `main`.

**Pick your URL first**, because it changes one setting:

| Repo name                  | Live at                              | `site.json`                        |
| -------------------------- | ------------------------------------ | ---------------------------------- |
| `<username>.github.io`     | `https://<username>.github.io`       | leave `base_path` unset — simplest |
| anything else, e.g. `blog` | `https://<username>.github.io/blog`  | set `"base_path": "/blog"`         |
| custom domain              | `https://yourdomain.com`             | leave `base_path` unset            |

Then:

```bash
# 1. set the real URL in site.json
#    "base_url": "https://<username>.github.io"     (origin only, no trailing path)
#    "base_path": "/blog"                           (only for a project repo)

# 2. make this folder a repo and push it
git init -b main
git add .
git commit -m "First version of my blog"
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main

# 3. on github.com: Settings -> Pages -> Source: "GitHub Actions"
```

The first push triggers the build; watch it in the **Actions** tab. After that,
publishing a post is `git add`, `git commit`, `git push` — the site is live in
about a minute. It is free for public repos, with no server to maintain.

For a custom domain, add it under Settings → Pages and create a `static/CNAME`
file containing just the domain, so it survives every rebuild.

## Layout

```
site.json              title, nav, social links, base_url / base_path
content/posts/*.md     your posts
content/pages/*.md     standalone pages (about, now, ...)
templates/             Jinja2 templates: base, index, post, page, list, feed
static/css/style.css   hand-written stylesheet; theme tokens at the top
static/js/             theme picker, KaTeX init, copy-code button
static/img/            your images, served from /img/
build.py               the generator
serve.py               dev server: watch, rebuild, live-reload
new_post.py            scaffolding
dist/                  generated output (gitignored; never edit by hand)
```

Also generated for you: `/archive/`, a page per tag, `feed.xml`, `sitemap.xml`,
`robots.txt`, and a styled `404.html`.
