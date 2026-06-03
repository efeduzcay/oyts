#!/usr/bin/env python3
"""Tiny static HTTP server for live.html.

Portable — serves the directory the script lives in, not a hardcoded path.
Pass an alternative port as the first argument (default 8765). Maps `/` to
`/live.html` so opening the root in a browser lands on the demo page.

Usage:
    python serve.py              # http://127.0.0.1:8765/
    python serve.py 8080
"""
from __future__ import annotations

import functools
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


WEB_DIR = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        if self.path in ("/", ""):
            self.path = "/live.html"
        return super().do_GET()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    host = "127.0.0.1"
    handler = functools.partial(Handler, directory=str(WEB_DIR))
    print(f"OYTS static @ http://{host}:{port}  (root={WEB_DIR})", flush=True)
    try:
        ThreadingHTTPServer((host, port), handler).serve_forever()
    except KeyboardInterrupt:
        print("\nDurduruldu.")


if __name__ == "__main__":
    main()
