"""
Kingdom AI — File Integrity Monitor
SOTA 2026: Detects unauthorized modifications to Kingdom AI source files.

Uses HMAC-SHA256 checksums to verify file integrity at startup and periodically.
If tampering is detected, publishes security events for CreatorShield to handle.
Dormant until protection flag "file_integrity" is activated.
"""
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from base_component import BaseComponent

logger = logging.getLogger(__name__)

REDIS_KEY = "kingdom:file_integrity_baseline"
LOCAL_BASELINE_REL = os.path.join("config", "file_integrity_baseline.json")

# File extensions to monitor
MONITORED_EXTENSIONS = {".py", ".json", ".yaml", ".yml", ".toml", ".cfg", ".env"}

# Directories to skip
SKIP_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "node_modules", ".pytest_cache",
    "creation_env", "ml_packages_venv", "kingdom-venv", ".pip_cache",
    ".pip_tmp", "build_talib", "external_miners", "Unity Hub", "HunyuanVideo",
    "GPT-SoVITS", "android-stubs", "gradle", "downloads", "firmware",
    "kingdom_fix_backups", "kingdom_backups", "corrupted_files_backup",
    "legacy_backup_functions", "backups", "logs", "cache", "data",
    "display_proof", "manual_parts",
}


def _file_hash(filepath: str, secret: bytes) -> str:
    """Compute HMAC-SHA256 of a file's contents."""
    h = hmac.new(secret, digestmod=hashlib.sha256)
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except (OSError, PermissionError):
        return ""
    return h.hexdigest()


class FileIntegrityMonitor(BaseComponent):
    """
    Monitors Kingdom AI files for unauthorized modification.

    On first run, builds a baseline of HMAC-SHA256 checksums.
    On subsequent runs, compares against baseline and reports changes.
    Periodic checks run in a background thread when active.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self._local_baseline_path = os.path.join(self._project_root, LOCAL_BASELINE_REL)

        # HMAC secret derived from machine-specific data
        self._secret = self._derive_secret()

        # Baseline: filepath -> hash
        self._baseline: Dict[str, str] = {}
        self._baseline_lock = threading.Lock()

        # Background monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._check_interval = int(self.config.get("check_interval_seconds", 300))  # 5 min default

        self._subscribe_events()
        self._initialized = True
        logger.info("FileIntegrityMonitor initialized (dormant until activated)")

    # ------------------------------------------------------------------
    # Secret derivation
    # ------------------------------------------------------------------

    def _derive_secret(self) -> bytes:
        """Derive a machine-specific HMAC secret."""
        import platform
        try:
            user = os.getlogin()
        except OSError:
            # WSL2 / containers / cron have no controlling terminal for getlogin()
            user = os.getenv('USER') or os.getenv('USERNAME') or 'user'
        seed = f"{platform.node()}:{platform.machine()}:{user}"
        return hashlib.sha256(seed.encode()).digest()

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def _scan_files(self) -> Dict[str, str]:
        """Scan all monitored files and return {relative_path: hmac_hash}."""
        results: Dict[str, str] = {}
        for dirpath, dirnames, filenames in os.walk(self._project_root):
            # Skip excluded directories
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            rel_dir = os.path.relpath(dirpath, self._project_root)
            for fname in filenames:
                _, ext = os.path.splitext(fname)
                if ext.lower() not in MONITORED_EXTENSIONS:
                    continue
                full = os.path.join(dirpath, fname)
                rel = os.path.join(rel_dir, fname) if rel_dir != "." else fname
                h = _file_hash(full, self._secret)
                if h:
                    results[rel] = h
        return results

    def build_baseline(self) -> int:
        """Build initial baseline. Returns number of files baselined."""
        scan = self._scan_files()
        with self._baseline_lock:
            self._baseline = scan
        self._persist_baseline()
        logger.info("File integrity baseline built: %d files", len(scan))
        return len(scan)

    def verify(self) -> Dict[str, List[str]]:
        """
        Verify current files against baseline.
        Returns dict with keys: 'modified', 'added', 'removed'.
        """
        current = self._scan_files()
        with self._baseline_lock:
            baseline = dict(self._baseline)

        modified: List[str] = []
        added: List[str] = []
        removed: List[str] = []

        baseline_keys = set(baseline.keys())
        current_keys = set(current.keys())

        for f in baseline_keys & current_keys:
            if baseline[f] != current[f]:
                modified.append(f)

        added = list(current_keys - baseline_keys)
        removed = list(baseline_keys - current_keys)

        return {"modified": modified, "added": added, "removed": removed}

    def check_and_report(self) -> None:
        """Run verification and publish results if changes detected."""
        # Check protection flag
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            if not fc.is_active("file_integrity"):
                return
        except Exception:
            return

        if not self._baseline:
            self._load_baseline()
            if not self._baseline:
                self.build_baseline()
                return  # First run — baseline just built, nothing to compare

        result = self.verify()
        total_changes = len(result["modified"]) + len(result["added"]) + len(result["removed"])

        if total_changes > 0:
            logger.warning(
                "FILE INTEGRITY ALERT: %d modified, %d added, %d removed",
                len(result["modified"]), len(result["added"]), len(result["removed"]),
            )
            if self.event_bus:
                self.event_bus.publish("security.file_integrity.violation", {
                    "modified": result["modified"][:50],
                    "added": result["added"][:50],
                    "removed": result["removed"][:50],
                    "total_changes": total_changes,
                    "timestamp": datetime.utcnow().isoformat(),
                })
        else:
            logger.debug("File integrity check passed — no changes detected")

    # ------------------------------------------------------------------
    # Background monitoring
    # ------------------------------------------------------------------

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True, name="FileIntegrityMonitor")
        self._monitor_thread.start()
        logger.info("File integrity monitoring started (interval=%ds)", self._check_interval)

    def stop_monitoring(self) -> None:
        self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        logger.info("File integrity monitoring stopped")

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                self.check_and_report()
            except Exception as e:
                logger.error("File integrity check error: %s", e)
            # Sleep in small increments so we can stop quickly
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_baseline(self) -> None:
        with self._baseline_lock:
            snapshot = dict(self._baseline)

        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY, snapshot)
            except Exception:
                pass

        try:
            os.makedirs(os.path.dirname(self._local_baseline_path), exist_ok=True)
            with open(self._local_baseline_path, "w") as f:
                json.dump(snapshot, f)
        except Exception as e:
            logger.debug("Baseline persist failed: %s", e)

    def _load_baseline(self) -> None:
        loaded = False
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY)
                if isinstance(data, dict) and data:
                    with self._baseline_lock:
                        self._baseline = data
                    loaded = True
            except Exception:
                pass

        if not loaded and os.path.exists(self._local_baseline_path):
            try:
                with open(self._local_baseline_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    with self._baseline_lock:
                        self._baseline = data
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("security.file_integrity.scan", self._handle_scan)
        self.event_bus.subscribe("security.file_integrity.rebuild_baseline", self._handle_rebuild)
        self.event_bus.subscribe("protection.flag.changed", self._handle_flag_change)

    def _handle_scan(self, data: Any) -> None:
        self.check_and_report()

    def _handle_rebuild(self, data: Any) -> None:
        count = self.build_baseline()
        if self.event_bus:
            self.event_bus.publish("security.file_integrity.baseline_rebuilt", {"file_count": count})

    def _handle_flag_change(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        if data.get("module") in ("file_integrity", "__all__"):
            if data.get("active"):
                self._load_baseline()
                if not self._baseline:
                    self.build_baseline()
                self.start_monitoring()
            else:
                self.stop_monitoring()

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._load_baseline()
        self._initialized = True
        return True

    async def close(self) -> None:
        self.stop_monitoring()
        await super().close()
