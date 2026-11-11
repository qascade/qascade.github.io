#!/usr/bin/env python3
"""Dev server: rebuilds on change, serves dist/ at http://localhost:8000.

    python serve.py [--port 8000] [--drafts]

Watches content/, templates/, static/ and site.json by polling mtimes, so
there are no extra dependencies. Reload the browser after saving.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
WATCH = [ROOT / "content", ROOT / "templates", ROOT / "static", ROOT / "site.json"]


def snapshot() -> dict[str, float]:
    state = {}
    for target in WATCH:
        if target.is_file():
            state[str(target)] = target.stat().st_mtime
        elif target.is_dir():
            for f in target.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    state[str(f)] = f.stat().st_mtime
    return state


def build(extra: list[str]) -> bool:
    result = subprocess.run([sys.executable, str(ROOT / "build.py"),
                             "--livereload", *extra])
    if result.returncode == 0:
        # stamp the build so /js/livereload.js can detect it and refresh
        (DIST / "__build").write_text(str(time.time()), encoding="utf-8")
    return result.returncode == 0


def watch_loop(extra: list[str]) -> None:
    previous = snapshot()
    while True:
        time.sleep(0.7)
        current = snapshot()
        if current != previous:
            previous = current
            print("\nchange detected, rebuilding...")
            build(extra)


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves dist/, with pretty-URL and 404-page handling."""

    def log_message(self, fmt, *a):  # quieter output
        sys.stderr.write("  %s\n" % (fmt % a))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        page = DIST / "404.html"
        if code == 404 and page.exists():
            body = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)


def main() -> int:
    ap = argparse.ArgumentParser(description="Serve the blog locally with auto-rebuild.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="open the site in your browser")
    ap.add_argument("--drafts", action="store_true", help="include draft posts")
    args = ap.parse_args()

    extra = ["--drafts"] if args.drafts else []
    if not build(extra):
        return 1

    threading.Thread(target=watch_loop, args=(extra,), daemon=True).start()

    handler = functools.partial(Handler, directory=str(DIST))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}"
        print(f"\nserving {url}  (ctrl-c to stop)")
        if args.open:
            import webbrowser
            threading.Timer(0.6, webbrowser.open, args=(url,)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")
    return 0


if __name__ == "__main__":
    sys.exit(main())
