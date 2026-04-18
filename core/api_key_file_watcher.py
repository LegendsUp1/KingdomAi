"""Runtime API-key file watcher.

Monitors ``config/api_keys.json``, ``config/api_keys.env``, and the root
``.env`` file for any mtime/size change. When a change is detected, calls
``APIKeyManager.reload_from_disk()`` and publishes ``api.keys.reloaded`` on
the shared EventBus so that RealExchangeExecutor, TradingComponent, and
every subscriber auto-rewires live exchange connectors without a process
restart.

This uses pure stdlib polling (no ``watchdog`` dependency) so it runs in
every venv without additional installs.

Usage (already wired into ``APIKeyManager.__init__`` when an ``event_bus``
is supplied)::

    from core.api_key_file_watcher import APIKeyFileWatcher
    watcher = APIKeyFileWatcher(api_key_manager, poll_interval_s=3.0)
    watcher.start()  # starts a daemon thread; safe to call multiple times
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, Optional

logger = logging.getLogger(__name__)


# Canonical files the watcher will keep an eye on. Additional paths may be
# passed via ``extra_paths`` at construction time.
DEFAULT_WATCH_PATHS: tuple[str, ...] = (
    "config/api_keys.json",
    "config/api_keys.env",
    ".env",
)


class APIKeyFileWatcher:
    """Background mtime/size poller that triggers hot-reload on key file edits."""

    def __init__(
        self,
        api_key_manager,
        *,
        event_bus=None,
        poll_interval_s: float = 3.0,
        watch_paths: Optional[Iterable[str]] = None,
        project_root: Optional[str] = None,
    ) -> None:
        self.api_key_manager = api_key_manager
        self.event_bus = event_bus or getattr(api_key_manager, "event_bus", None)
        self.poll_interval_s = max(0.5, float(poll_interval_s))

        root = Path(project_root) if project_root else Path(
            os.environ.get("KINGDOM_AI_ROOT")
            or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ).resolve()
        self.project_root = root

        paths = list(watch_paths) if watch_paths else list(DEFAULT_WATCH_PATHS)
        self._abs_paths: list[Path] = []
        for p in paths:
            pp = Path(p)
            if not pp.is_absolute():
                pp = (root / pp).resolve()
            self._abs_paths.append(pp)

        self._fingerprints: Dict[str, tuple[float, int]] = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._prime_fingerprints()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Launch the background polling thread (idempotent)."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="APIKeyFileWatcher",
                daemon=True,
            )
            self._thread.start()
        logger.info(
            "APIKeyFileWatcher started (interval=%.1fs, paths=%s)",
            self.poll_interval_s,
            [str(p) for p in self._abs_paths],
        )

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=timeout)
        self._thread = None

    def force_check_now(self) -> bool:
        """Run a single poll iteration synchronously. Returns True if reload fired."""
        return self._check_once()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _prime_fingerprints(self) -> None:
        for p in self._abs_paths:
            self._fingerprints[str(p)] = self._fingerprint(p)

    @staticmethod
    def _fingerprint(path: Path) -> tuple[float, int]:
        try:
            st = path.stat()
            return (st.st_mtime, st.st_size)
        except (FileNotFoundError, PermissionError, OSError):
            return (0.0, -1)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_once()
            except Exception as exc:  # noqa: BLE001
                logger.warning("APIKeyFileWatcher iteration failed: %s", exc)
            self._stop_event.wait(self.poll_interval_s)

    def _check_once(self) -> bool:
        changed: list[str] = []
        for p in self._abs_paths:
            key = str(p)
            current = self._fingerprint(p)
            previous = self._fingerprints.get(key)
            if previous is None:
                self._fingerprints[key] = current
                continue
            if current != previous:
                changed.append(key)
                self._fingerprints[key] = current

        if not changed:
            return False

        logger.info("Detected change in API-key file(s): %s - reloading", changed)
        try:
            self.api_key_manager.reload_from_disk()
        except Exception as exc:  # noqa: BLE001
            logger.error("reload_from_disk() failed after file change: %s", exc)
            return False

        # Broadcast so TradingComponent / RealExchangeExecutor / Stock exec
        # rebuild their flat key maps and connectors.
        if self.event_bus is not None:
            try:
                self.event_bus.publish(
                    "api.keys.reloaded",
                    {
                        "source": "APIKeyFileWatcher",
                        "files": changed,
                        "timestamp": time.time(),
                    },
                )
                self.event_bus.publish(
                    "api.keys.all.loaded",
                    {"source": "APIKeyFileWatcher", "files": changed},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to publish api.keys.reloaded event: %s", exc)
        return True


__all__ = ["APIKeyFileWatcher", "DEFAULT_WATCH_PATHS"]
