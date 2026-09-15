#!/usr/bin/env python3
"""Serve the isolated live-mapping viewer. Does not touch web/ or fake-backend."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mapping import capture

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 18089


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[map-viewer] {self.address_string()} {fmt % args}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send(200, (ROOT / "viewer.html").read_bytes(), "text/html; charset=utf-8")
            return
        if self.path == "/api/snapshot":
            cached = ROOT / "runtime" / "snapshot.json"
            try:
                snap = capture()
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n")
            except Exception as err:
                if cached.exists():
                    snap = json.loads(cached.read_text())
                    snap["captureError"] = str(err)
                else:
                    self._send(503, json.dumps({"error": str(err)}).encode(), "application/json")
                    return
            self._send(200, json.dumps(snap, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if self.path == "/runtime/snapshot.json":
            cached = ROOT / "runtime" / "snapshot.json"
            if not cached.exists():
                self._send(404, b'{"error":"no snapshot"}', "application/json")
                return
            self._send(200, cached.read_bytes(), "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"mapping viewer http://{HOST}:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
