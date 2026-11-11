#!/usr/bin/env python3
"""Import Obsidian-style notes from the second-brain repo into content/posts/.

    python import_notes.py --repo /path/to/second-brain

One post per Gita chapter (the several note files inside a chapter folder
become sections of that post), plus the Mahabharata notes as a second series.
Skips empty files, .DS_Store, PDFs and broken Obsidian image embeds.
Dates come from each file's last commit in the source repo.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "content" / "posts"

CHAPTER_NUM = re.compile(r"chapter\s*(\d+)", re.I)
OBSIDIAN_EMBED = re.compile(r"!\[\[([^\]]+)\]\]")
OBSIDIAN_LINK = re.compile(r"(?<!!)\[\[([^\]]+)\]\]")

# Nicer section headings than the raw filenames
SECTION_TITLES = {
    "ami ganatra notes": "Notes from Ami Ganatra's lectures",
    "ami ganatra note": "Notes from Ami Ganatra's lectures",
    "ami gantra notes": "Notes from Ami Ganatra's lectures",
    "ami ganatra notes ": "Notes from Ami Ganatra's lectures",
    "my notes": "My notes",
    "notes": "My notes",
    "self introspection": "Self-introspection",
}

# Chapter titles, tidied from the folder names in the source repo
GITA_TITLES = {
    1: "Arjuna's despair",
    2: "Sankhya and Karma Yoga",
    3: "Karma Yoga",
    4: "Sankhya Yoga in detail",
    5: "Karma Yoga in detail",
    6: "Dhyana Yoga",
    7: "Bhagavana Tatva",
    8: "Attaining the supreme",
    10: "Raja Vidya",
    11: "Vishwaroopa Darshana",
    12: "Bhakti Yoga",
    13: "Kshetra-Kshetragna Vibhaga",
    14: "The three gunas",
    15: "Purushottama Yoga",
    16: "Daivi and Asuri Sampada",
    17: "Shraddha-Traya Vibhaga",
    18: "Moksha-Sanyasa Yoga",
}

MAHABHARATA_ORDER = {"intro": 1, "part 1": 2, "adiparva": 3, "trivia": 4}
MAHABHARATA_TITLES = {
    "intro": "Reading the Mahabharata: where to start",
    "part 1": "Mahabharata notes: the opening",
    "adiparva": "Adi Parva",
    "trivia": "Mahabharata: things worth remembering",
}


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value.lower()).strip()
    return re.sub(r"[\s_-]+", "-", value) or "untitled"


def git_date(repo: Path, rel: str) -> str:
    """Last commit date for a file, falling back to today."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%aI", "--", rel],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        if out:
            return out[:10]
    except Exception:
        pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def clean(body: str, available_images: set[str]) -> str:
    """Strip Obsidian syntax; keep embeds only when the image actually exists."""
    def embed(m: re.Match) -> str:
        name = m.group(1).strip()
        if name in available_images:
            return f"![{Path(name).stem}](/img/notes/{slugify(Path(name).stem)}{Path(name).suffix})"
        return ""  # referenced but never committed to the repo

    body = OBSIDIAN_EMBED.sub(embed, body)
    body = OBSIDIAN_LINK.sub(lambda m: m.group(1).split("|")[-1], body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def section_title(stem: str) -> str:
    key = stem.strip().lower()
    if key in SECTION_TITLES:
        return SECTION_TITLES[key]
    if CHAPTER_NUM.search(stem):          # e.g. "Chapter 2 - Karma Yoga"
        tail = stem.split("-", 1)
        return tail[1].strip() if len(tail) > 1 else "My notes"
    return stem.strip()


def front_matter(**kw) -> str:
    lines = ["---"]
    for k, v in kw.items():
        if v not in (None, "", []):
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def write_post(path: Path, text: str, dry: bool) -> None:
    if dry:
        print(f"  would write {path.relative_to(ROOT)}  ({len(text)} bytes)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, type=Path, help="path to the cloned second-brain repo")
    ap.add_argument("--images", action="store_true",
                    help="also copy the committed screenshots into static/img/notes/")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo = args.repo.expanduser().resolve()
    gita = repo / "Bhagvata Gita"
    maha = repo / "MahaBharata"
    if not gita.is_dir():
        print(f"no 'Bhagvata Gita' folder under {repo}", file=sys.stderr)
        return 1

    images = {p.name for p in gita.rglob("*.png")} if args.images else set()
    if args.images and not args.dry_run:
        dest = ROOT / "static" / "img" / "notes"
        dest.mkdir(parents=True, exist_ok=True)
        for p in gita.rglob("*.png"):
            (dest / f"{slugify(p.stem)}{p.suffix}").write_bytes(p.read_bytes())

    def usable(p: Path) -> bool:
        return (p.suffix.lower() == ".md" and p.stat().st_size > 0
                and not p.name.startswith(".")
                and p.stem.lower() not in ("untitled", "untitled 2"))

    # ---- group the Gita notes by chapter ----------------------------
    chapters: dict[int, list[Path]] = {}
    extras: list[Path] = []
    for p in sorted(gita.rglob("*.md")):
        if not usable(p):
            continue
        rel = p.relative_to(gita)
        m = CHAPTER_NUM.search(str(rel))
        if m:
            chapters.setdefault(int(m.group(1)), []).append(p)
        else:
            extras.append(p)

    print(f"importing {len(chapters)} Gita chapters, {len(extras)} loose notes, "
          f"{len(list(maha.glob('*.md'))) if maha.is_dir() else 0} Mahabharata files")

    for num in sorted(chapters):
        files = sorted(chapters[num], key=lambda f: (0 if "my" in f.stem.lower() else 1, f.stem))
        name = GITA_TITLES.get(num, "")
        title = f"Gita Chapter {num}: {name}" if name else f"Gita Chapter {num}"
        body_parts = []
        for f in files:
            text = clean(f.read_text(encoding="utf-8", errors="replace"), images)
            if not text:
                continue
            heading = section_title(f.stem)
            # a single-section chapter reads better without a redundant heading
            body_parts.append(text if len(files) == 1 else f"## {heading}\n\n{text}")

        if not body_parts:
            continue
        date = min(git_date(repo, str(f.relative_to(repo))) for f in files)
        fm = front_matter(
            title=f'"{title}"',
            date=date,
            slug=f"gita-chapter-{num}",
            series="Bhagavad Gita",
            order=num,
            tags="Bhagavad Gita, notes",
            description=f'"My notes on Chapter {num} of the Bhagavad Gita'
                        + (f' - {name}."' if name else '."'),
        )
        write_post(OUT / f"gita-chapter-{num:02d}.md", fm + "\n\n" + "\n\n".join(body_parts) + "\n",
                   args.dry_run)

    # ---- loose Gita notes -------------------------------------------
    loose_meta = {
        "my observations": ("Gita: my open questions", 90),
        "untitled 1": ("The six enemies of the mind", 91),
        "text 39": ("Gita 2.39 and the trouble with translations", 92),
        "notes": ("Premanand ji's saar: notes", 93),
    }
    for p in extras:
        key = p.stem.strip().lower()
        title, order = loose_meta.get(key, (p.stem.strip().title(), 94))
        text = clean(p.read_text(encoding="utf-8", errors="replace"), images)
        if not text:
            continue
        fm = front_matter(
            title=f'"{title}"',
            date=git_date(repo, str(p.relative_to(repo))),
            slug=slugify(title),
            series="Bhagavad Gita",
            order=order,
            tags="Bhagavad Gita, notes",
        )
        write_post(OUT / f"gita-note-{slugify(title)}.md", fm + "\n\n" + text + "\n", args.dry_run)

    # ---- Mahabharata -------------------------------------------------
    if maha.is_dir():
        for p in sorted(maha.glob("*.md")):
            if not usable(p):
                continue
            key = p.stem.strip().lower()
            title = MAHABHARATA_TITLES.get(key, p.stem.strip())
            text = clean(p.read_text(encoding="utf-8", errors="replace"), images)
            if not text:
                continue
            fm = front_matter(
                title=f'"{title}"',
                date=git_date(repo, str(p.relative_to(repo))),
                slug=slugify(title),
                series="Mahabharata",
                order=MAHABHARATA_ORDER.get(key, 9),
                tags="Mahabharata, notes",
            )
            write_post(OUT / f"mahabharata-{slugify(key)}.md", fm + "\n\n" + text + "\n",
                       args.dry_run)

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
