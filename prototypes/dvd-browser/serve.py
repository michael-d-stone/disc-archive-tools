#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Serve the browser probe and one user-selected ISO."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import stat


def byte_range(header, size):
    """Resolve one HTTP byte range to inclusive offsets."""
    match = re.fullmatch(r"bytes=([0-9]*)-([0-9]*)", header, re.ASCII)
    if not match or not size:
        raise ValueError("Invalid byte range")
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix == 0:
            raise ValueError("Empty suffix")
        return max(0, size - suffix), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start > end:
        raise ValueError("Unsatisfiable byte range")
    return start, end


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.respond(send_body=False)

    def do_GET(self):
        self.respond(send_body=True)

    def respond(self, send_body):
        if self.path == "/":
            page = Path(__file__).with_name("index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            if send_body:
                self.wfile.write(page)
        elif self.path == "/disc.iso":
            self.serve_iso(send_body)
        else:
            self.send_error(404)

    def serve_iso(self, send_body):
        descriptor = self.server.iso.fileno()
        size = os.fstat(descriptor).st_size
        start, end = 0, size - 1
        header = self.headers.get("Range") if send_body else None
        if header is not None:
            try:
                start, end = byte_range(header, size)
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        remaining = end - start + 1
        self.send_response(206 if header is not None else 200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(remaining))
        if header is not None:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if send_body:
            try:
                while remaining:
                    block = os.pread(descriptor, min(remaining, 256 * 1024), start)
                    if not block:
                        break
                    self.wfile.write(block)
                    start += len(block)
                    remaining -= len(block)
            except (BrokenPipeError, ConnectionResetError):
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        iso = args.iso.open("rb")
    except OSError as error:
        parser.error(str(error))
    with iso:
        info = os.fstat(iso.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size < 17 * 2048:
            parser.error("Select a regular ISO file with at least 17 sectors.")
        with ThreadingHTTPServer((args.bind, args.port), Handler) as server:
            server.iso = iso
            print(f"Open http://{args.bind}:{server.server_port}/", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
