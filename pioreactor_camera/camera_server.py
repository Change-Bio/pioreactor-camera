#!/usr/bin/env python3
"""Simple HTTP server for the camera gallery frontend."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pioreactor.config import config

IMAGE_DIR = Path(config.get("camera_capture.config", "image_directory", fallback="/home/pioreactor/camera_images"))
STATIC_DIR = Path(__file__).parent / "static"
PORT = int(config.get("camera_capture.config", "server_port", fallback="8190"))

FILENAME_PATTERN = re.compile(r"webcam_snap_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}(?:-\d{2})?)\.(jpg|jpeg|png)")


def parse_image_timestamp(filename: str) -> str | None:
    m = FILENAME_PATTERN.match(filename)
    if not m:
        return None
    ts = m.group(1)
    # Normalize to include seconds
    if len(ts) == 16:  # YYYY-MM-DD_HH-MM
        ts += "-00"
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d_%H-%M-%S")
        return dt.isoformat()
    except ValueError:
        return None


def list_images(page: int = 1, per_page: int = 50) -> dict:
    if not IMAGE_DIR.exists():
        return {"images": [], "total": 0, "page": page, "per_page": per_page}

    all_files = sorted(
        (f for f in IMAGE_DIR.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")),
        key=lambda f: f.name,
        reverse=True,
    )
    total = len(all_files)
    start = (page - 1) * per_page
    end = start + per_page
    page_files = all_files[start:end]

    images = []
    for f in page_files:
        ts = parse_image_timestamp(f.name)
        images.append({
            "filename": f.name,
            "timestamp": ts,
            "size": f.stat().st_size,
        })

    return {"images": images, "total": total, "page": page, "per_page": per_page}


class CameraHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/images":
            qs = parse_qs(parsed.query)
            page = int(qs.get("page", ["1"])[0])
            per_page = int(qs.get("per_page", ["50"])[0])
            per_page = min(per_page, 200)
            data = list_images(page, per_page)
            self._json_response(data)
            return

        if path.startswith("/images/"):
            filename = path[len("/images/"):]
            # Prevent path traversal
            if "/" in filename or "\\" in filename or ".." in filename:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            filepath = IMAGE_DIR / filename
            if filepath.exists() and filepath.is_file():
                self.send_response(HTTPStatus.OK)
                if filepath.suffix.lower() in (".jpg", ".jpeg"):
                    self.send_header("Content-Type", "image/jpeg")
                else:
                    self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(filepath.stat().st_size))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                with open(filepath, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        # Serve static frontend files
        if path == "/":
            path = "/index.html"

        static_path = STATIC_DIR / path.lstrip("/")
        if static_path.exists() and static_path.is_file():
            self.send_response(HTTPStatus.OK)
            content_type = self._guess_type(static_path)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(static_path.stat().st_size))
            self.end_headers()
            with open(static_path, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)
            return

        # SPA fallback - serve index.html for unmatched routes
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(index_path.stat().st_size))
            self.end_headers()
            with open(index_path, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/capture":
            from pioreactor_camera.camera_capture import capture_image, upload_to_gcs, IMAGE_DIR as CAP_DIR
            filename = capture_image(CAP_DIR)
            if filename:
                # Optionally upload to GCS
                try:
                    upload_gcs = config.getboolean("camera_capture.config", "upload_to_gcs", fallback=True)
                    if upload_gcs:
                        gcs_bucket = config.get(
                            "camera_capture.config", "gcs_bucket",
                            fallback="gs://pioreactor-webcam-snaps-1768947561/webcam_snaps"
                        )
                        gcs_project = config.get(
                            "camera_capture.config", "gcs_project", fallback="changebio-tech"
                        )
                        upload_to_gcs(CAP_DIR / filename, gcs_bucket, gcs_project)
                except Exception:
                    pass
                ts = parse_image_timestamp(filename)
                self._json_response({
                    "success": True,
                    "filename": filename,
                    "timestamp": ts,
                })
            else:
                self._json_response({"success": False, "error": "Capture failed"}, status=500)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _guess_type(self, path: Path) -> str:
        ext = path.suffix.lower()
        return {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
        }.get(ext, "application/octet-stream")

    def log_message(self, format, *args):
        pass  # Suppress default logging


def main():
    server = HTTPServer(("0.0.0.0", PORT), CameraHandler)
    print(f"Camera server running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
