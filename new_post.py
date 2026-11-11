#!/usr/bin/env python3
"""Scaffold a new post or page.

    python new_post.py "Why I started writing again"
    python new_post.py "About" --page
    python new_post.py "Half-baked idea" --draft --tags "ai, essays"
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from build import slugify  # single source of truth for slugs

ROOT = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a new post or page file.")
    ap.add_argument("title")
    ap.add_argument("--page", action="store_true", help="create a standalone page instead of a post")
    ap.add_argument("--draft", action="store_true", help="mark as draft (excluded from builds)")
    ap.add_argument("--tags", default="", help="comma separated tags")
    ap.add_argument("--toc", action="store_true", help="render a table of contents")
    args = ap.parse_args()

    slug = slugify(args.title)
    today = date.today().isoformat()

    if args.page:
        path = ROOT / "content" / "pages" / f"{slug}.md"
        front = [f"title: {args.title}", f"slug: {slug}"]
    else:
        path = ROOT / "content" / "posts" / f"{today}-{slug}.md"
        front = [f"title: {args.title}", f"date: {today}", f"slug: {slug}",
                 f"tags: {args.tags}", "description:"]
    if args.draft:
        front.append("draft: true")
    if args.toc:
        front.append("toc: true")

    if path.exists():
        print(f"refusing to overwrite existing {path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(front) + "\n---\n\nStart writing here.\n", encoding="utf-8")
    print(f"created {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
