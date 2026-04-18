"""Creator install server.

Serves the creator-only mobile artifacts to the creator's phone over the
desktop's Wi-Fi network. Device-aware: Android Chrome gets the signed APK,
iOS Safari gets an install page that prompts "Add to Home Screen" and
then the PWA fetches an encrypted ``creator_bootstrap.enc`` bundle on its
first launch, which flips the PWA into creator mode.

Security properties:

  * Binds only to the desktop's RFC1918 Wi-Fi IP. Never 0.0.0.0.
  * Emits a fresh single-use token on every launch; after the token is
    consumed once the server shuts itself down.
  * Auto-shutdown after a configurable TTL (default 10 minutes) even if the
    token is never used.
  * Serves strict Content-Security-Policy + no caching so the browser
    never persists the encrypted bundle.
  * Refuses connections whose peer address is outside RFC1918.

Usage (from the Kaig tab button):

    from core.creator_install_server import CreatorInstallServer
    srv = CreatorInstallServer(artifact_dir=Path.home() / "KingdomAI-Private")
    url, token, qr_data = srv.start()
    # Show QR (qr_data) to the user. Server auto-stops.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

_LOG = logging.getLogger(__name__)

DEFAULT_PORT_RANGE = (8931, 8999)
DEFAULT_TTL_SECONDS = 600  # 10 minutes


def _pick_wifi_ip() -> str:
    """Return the desktop's private Wi-Fi IP, or raise if unavailable."""
    # 1. try a UDP-socket trick to find the outgoing interface
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        if ipaddress.ip_address(ip).is_private:
            return ip
    except OSError:
        pass
    # 2. fall back to the first non-loopback private interface
    for _name, addrs in _iter_interfaces():
        for addr in addrs:
            try:
                ip_obj = ipaddress.ip_address(addr)
            except ValueError:
                continue
            if ip_obj.is_private and not ip_obj.is_loopback:
                return str(ip_obj)
    raise RuntimeError("No private Wi-Fi IP found. Is the desktop connected to your Wi-Fi?")


def _iter_interfaces():
    try:
        import psutil  # type: ignore
    except Exception:
        return []
    out = []
    for name, snics in psutil.net_if_addrs().items():
        addrs = [s.address for s in snics if s.family == socket.AF_INET]
        out.append((name, addrs))
    return out


class _CreatorInstallHandler(BaseHTTPRequestHandler):
    server_version = "KingdomAICreatorInstall/1.0"

    # populated by the parent server instance
    install_token: str = ""
    artifact_dir: Path = Path("/tmp")
    shutdown_event: Optional[threading.Event] = None

    def log_message(self, fmt, *args):  # pragma: no cover
        _LOG.info("[install-server] " + fmt, *args)

    def _client_is_private(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0]).is_private
        except ValueError:
            return False

    def _deny(self, code: int, reason: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(reason.encode("utf-8"))

    def _send_headers(self, code: int, content_type: str, length: int):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def do_GET(self):
        if not self._client_is_private():
            return self._deny(403, "external clients not allowed")
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        token = (qs.get("t", [""])[0] or "")
        if not hmac.compare_digest(token, self.install_token):
            return self._deny(403, "invalid or expired token")

        ua = self.headers.get("User-Agent", "")
        is_ios = any(p in ua for p in ("iPhone", "iPad", "iPod"))
        is_android = "Android" in ua

        # Android phones go straight for the APK.
        if url.path == "/install" and is_android:
            apk = self.artifact_dir / "KingdomAI-Creator.apk"
            if not apk.exists():
                return self._deny(404, "creator APK not built yet; run scripts/build_creator_apk.sh")
            data = apk.read_bytes()
            self._send_headers(200, "application/vnd.android.package-archive", len(data))
            self.wfile.write(data)
            self._consume_token()
            return

        # iOS devices land on a tiny install page -> Add to Home Screen.
        if url.path == "/install" and is_ios:
            html = self._ios_install_page()
            self._send_headers(200, "text/html; charset=utf-8", len(html))
            self.wfile.write(html)
            return

        # Generic install page shown to any other browser (including the
        # creator double-checking on the desktop).
        if url.path == "/install":
            html = self._generic_install_page()
            self._send_headers(200, "text/html; charset=utf-8", len(html))
            return self.wfile.write(html)

        # PWA bootstrap endpoint (called by the PWA on first launch to pull
        # the encrypted creator config). One-shot consumption.
        if url.path == "/creator_bootstrap.enc":
            bundle = self.artifact_dir / "creator_bootstrap.enc"
            if not bundle.exists():
                return self._deny(404, "creator bootstrap not built yet")
            data = bundle.read_bytes()
            self._send_headers(200, "application/octet-stream", len(data))
            self.wfile.write(data)
            self._consume_token()
            return

        # Serve PWA assets
        for asset in ("manifest.json", "sw.js", "icon.png", "pwa.html"):
            if url.path == f"/{asset}":
                path = self.artifact_dir / "pwa" / asset
                if not path.exists():
                    return self._deny(404, f"{asset} not found")
                data = path.read_bytes()
                mime = {
                    "manifest.json": "application/manifest+json",
                    "sw.js": "application/javascript",
                    "icon.png": "image/png",
                    "pwa.html": "text/html; charset=utf-8",
                }[asset]
                self._send_headers(200, mime, len(data))
                self.wfile.write(data)
                return

        return self._deny(404, "not found")

    def _ios_install_page(self) -> bytes:
        # Minimal page that tells Safari to Add to Home Screen.
        html = (
            "<!doctype html><html><head>"
            "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Install Kingdom AI (creator)</title>"
            "<link rel='apple-touch-icon' href='/icon.png'>"
            "<link rel='manifest' href='/manifest.json'>"
            "<meta name='apple-mobile-web-app-capable' content='yes'>"
            "<meta name='apple-mobile-web-app-status-bar-style' content='black-translucent'>"
            "<meta name='apple-mobile-web-app-title' content='Kingdom AI'>"
            "<style>body{font-family:-apple-system,sans-serif;background:#0A0E17;color:#FFD700;padding:32px;line-height:1.5}"
            "h1{font-size:22px} p{color:#ccc}</style>"
            "</head><body>"
            "<h1>&#128081; Install Kingdom AI (Creator)</h1>"
            "<p>1. Tap the <b>Share</b> button at the bottom of Safari.</p>"
            "<p>2. Scroll down and tap <b>Add to Home Screen</b>.</p>"
            "<p>3. Tap <b>Add</b>.</p>"
            "<p>Kingdom AI will install as an app. Open it from your home screen and it will "
            "finish bootstrapping itself into creator mode automatically.</p>"
            "</body></html>"
        )
        return html.encode("utf-8")

    def _generic_install_page(self) -> bytes:
        return (
            "<!doctype html><html><body style='font-family:sans-serif'>"
            "<h2>Kingdom AI -- Creator install</h2>"
            "<p>Open this URL on your <b>phone</b> (same Wi-Fi).</p>"
            "<p>Android: the APK will download automatically.</p>"
            "<p>iPhone / iPad: Safari will walk you through Add to Home Screen.</p>"
            "</body></html>"
        ).encode("utf-8")

    def _consume_token(self):
        if self.shutdown_event is not None:
            self.shutdown_event.set()


class CreatorInstallServer:
    """Start a short-lived install server and return the URL + QR payload."""

    def __init__(
        self,
        artifact_dir: Path,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        port_range: Tuple[int, int] = DEFAULT_PORT_RANGE,
    ) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.ttl = ttl_seconds
        self.port_range = port_range
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

    def start(self) -> Tuple[str, str, str]:
        if not self.artifact_dir.exists():
            raise RuntimeError(
                f"artifact_dir not found: {self.artifact_dir}. Run scripts/build_creator_pwa.sh "
                "and (optionally) scripts/build_creator_apk.sh first."
            )
        ip = _pick_wifi_ip()
        port = self._find_free_port(ip)
        token = secrets.token_urlsafe(32)
        handler = _CreatorInstallHandler
        handler.install_token = token
        handler.artifact_dir = self.artifact_dir
        handler.shutdown_event = self._shutdown_event
        self._httpd = HTTPServer((ip, port), handler)
        self._thread = threading.Thread(target=self._serve_forever, daemon=True)
        self._thread.start()
        # watchdog thread: auto-shutdown after TTL or on token consumption
        threading.Thread(target=self._watchdog, daemon=True).start()
        url = f"http://{ip}:{port}/install?t={token}"
        return url, token, url  # qr_data == url; caller renders it

    def _serve_forever(self):
        try:
            self._httpd.serve_forever(poll_interval=0.5)
        except Exception as exc:  # pragma: no cover
            _LOG.warning("creator install server stopped: %s", exc)

    def _watchdog(self):
        deadline = time.time() + self.ttl
        while time.time() < deadline:
            if self._shutdown_event.wait(timeout=1.0):
                break
        _LOG.info("creator install server shutting down (ttl or token consumed)")
        self.stop()

    def stop(self):
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:  # pragma: no cover
                pass
            self._httpd = None

    def _find_free_port(self, ip: str) -> int:
        lo, hi = self.port_range
        for port in range(lo, hi + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((ip, port))
                    return port
                except OSError:
                    continue
        raise RuntimeError(f"no free port in range {lo}-{hi} on {ip}")


__all__ = ["CreatorInstallServer"]
