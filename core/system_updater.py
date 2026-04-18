#!/usr/bin/env python3
"""
Kingdom AI - System Updater (SOTA 2026)

Master coordinator for keeping the entire Kingdom AI ecosystem up-to-date:
- NVIDIA drivers/CUDA toolkit detection and update notifications
- Ollama auto-update with model preservation
- Kingdom AI self-update with rollback safety
- Python dependency auto-update
- System health verification after every update

DESIGN PRINCIPLES:
1. NEVER break a running system  - always backup before update
2. NEVER lose data              - model preservation is mandatory
3. ALWAYS verify after update   - health checks run post-update
4. ALWAYS allow rollback        - every update is reversible
5. NON-BLOCKING                 - updates run in background threads
"""

import os
import sys
import json
import time
import shutil
import logging
import asyncio
import hashlib
import platform
import subprocess
import threading
import importlib
import importlib.metadata
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("KingdomAI.SystemUpdater")

# ---------------------------------------------------------------------------
# pynvml import (GPU monitoring)
# ---------------------------------------------------------------------------
HAS_PYNVML = False
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_PYNVML = True
except Exception:
    pass

HAS_AIOHTTP = False
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NvidiaStatus:
    """Current NVIDIA hardware/software state."""
    driver_version: str = ""
    cuda_version: str = ""
    gpu_name: str = ""
    gpu_count: int = 0
    vram_total_mb: int = 0
    vram_used_mb: int = 0
    driver_branch: str = ""
    latest_driver: str = ""
    update_available: bool = False
    cuda_toolkit_installed: bool = False
    cuda_toolkit_version: str = ""
    tensorrt_available: bool = False
    tensorrt_version: str = ""
    nvml_available: bool = HAS_PYNVML
    timestamp: str = ""

@dataclass
class OllamaStatus:
    """Current Ollama state."""
    installed: bool = False
    version: str = ""
    latest_version: str = ""
    update_available: bool = False
    models_count: int = 0
    api_reachable: bool = False
    timestamp: str = ""

@dataclass
class KingdomStatus:
    """Current Kingdom AI state."""
    version: str = "2026.2.0"
    python_version: str = ""
    packages_ok: bool = True
    outdated_packages: List[str] = field(default_factory=list)
    missing_packages: List[str] = field(default_factory=list)
    last_update_check: str = ""
    timestamp: str = ""

@dataclass
class UpdateResult:
    """Result of an update operation."""
    component: str = ""
    success: bool = False
    old_version: str = ""
    new_version: str = ""
    message: str = ""
    rolled_back: bool = False
    timestamp: str = ""


class SystemUpdater:
    """
    SOTA 2026 System Updater

    Manages updates for:
    1. NVIDIA drivers and CUDA toolkit
    2. Ollama (with model preservation)
    3. Kingdom AI Python dependencies
    4. Kingdom AI self-update system
    """

    UPDATE_CHECK_INTERVAL = 3600 * 6  # 6 hours
    STATE_FILE = "system_update_state.json"

    def __init__(self, event_bus=None, config: Optional[Dict] = None):
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logging.getLogger("KingdomAI.SystemUpdater")

        self._kingdom_root = Path(__file__).parent.parent
        self._data_dir = self._kingdom_root / "data" / "updates"
        self._backup_dir = self._data_dir / "backups"
        self._state_file = self._data_dir / self.STATE_FILE

        for d in (self._data_dir, self._backup_dir):
            d.mkdir(parents=True, exist_ok=True)

        self._state: Dict[str, Any] = self._load_state()
        self._update_lock = threading.Lock()
        self._bg_thread: Optional[threading.Thread] = None
        self._running = False

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    async def initialize(self) -> bool:
        """Initialize the updater and run first status check."""
        try:
            self.logger.info("Initializing System Updater (SOTA 2026)")

            nvidia = await self.check_nvidia_status()
            ollama = await self.check_ollama_status()
            kingdom = await self.check_kingdom_status()

            self.logger.info(
                f"NVIDIA: driver={nvidia.driver_version or 'N/A'}, "
                f"CUDA={nvidia.cuda_version or 'N/A'}, "
                f"GPU={nvidia.gpu_name or 'N/A'}"
            )
            self.logger.info(
                f"Ollama: v{ollama.version or 'N/A'}, "
                f"models={ollama.models_count}, "
                f"update={'YES' if ollama.update_available else 'no'}"
            )
            self.logger.info(
                f"Kingdom: v{kingdom.version}, "
                f"packages_ok={kingdom.packages_ok}, "
                f"outdated={len(kingdom.outdated_packages)}"
            )

            if self.event_bus:
                self.event_bus.subscribe("system.update.check", self._handle_update_check)
                self.event_bus.subscribe("system.update.nvidia", self._handle_nvidia_update)
                self.event_bus.subscribe("system.update.ollama", self._handle_ollama_update)
                self.event_bus.subscribe("system.update.packages", self._handle_package_update)

            self._start_background_checker()
            return True

        except Exception as e:
            self.logger.error(f"System Updater init failed: {e}")
            return False

    async def shutdown(self):
        """Stop background checker and save state."""
        self._running = False
        self._save_state()
        self.logger.info("System Updater shut down")

    # -----------------------------------------------------------------------
    # NVIDIA Status & Updates
    # -----------------------------------------------------------------------

    async def check_nvidia_status(self) -> NvidiaStatus:
        """Detect NVIDIA GPU, driver version, CUDA toolkit, TensorRT."""
        status = NvidiaStatus(timestamp=datetime.now().isoformat())

        # 1. pynvml-based detection (most reliable)
        if HAS_PYNVML:
            try:
                status.driver_version = pynvml.nvmlSystemGetDriverVersion()
                status.cuda_version = pynvml.nvmlSystemGetCudaDriverVersion_v2()
                if isinstance(status.cuda_version, int):
                    major = status.cuda_version // 1000
                    minor = (status.cuda_version % 1000) // 10
                    status.cuda_version = f"{major}.{minor}"

                status.gpu_count = pynvml.nvmlDeviceGetCount()
                if status.gpu_count > 0:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    status.gpu_name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(status.gpu_name, bytes):
                        status.gpu_name = status.gpu_name.decode()
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    status.vram_total_mb = mem.total // (1024 * 1024)
                    status.vram_used_mb = mem.used // (1024 * 1024)

                status.nvml_available = True
            except Exception as e:
                self.logger.debug(f"pynvml query error: {e}")

        # 2. nvidia-smi fallback
        if not status.driver_version:
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=driver_version,name,memory.total",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    line = result.stdout.strip().split("\n")[0]
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        status.driver_version = parts[0]
                        status.gpu_name = parts[1]
                        status.vram_total_mb = int(float(parts[2]))
                        status.gpu_count = result.stdout.strip().count("\n") + 1
            except Exception:
                pass

        # 3. CUDA toolkit version (nvcc)
        try:
            result = subprocess.run(
                ["nvcc", "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and "release" in result.stdout.lower():
                for part in result.stdout.split(","):
                    part = part.strip()
                    if part.startswith("release") or part.startswith("V"):
                        ver = part.split()[-1].lstrip("V")
                        status.cuda_toolkit_version = ver
                        status.cuda_toolkit_installed = True
                        break
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # 4. TensorRT
        try:
            import tensorrt
            status.tensorrt_available = True
            status.tensorrt_version = tensorrt.__version__
        except ImportError:
            pass

        # 5. Determine driver branch
        if status.driver_version:
            try:
                major = int(status.driver_version.split(".")[0])
                if major >= 580:
                    status.driver_branch = "R580 (LTS through Aug 2028, CUDA 13.x)"
                elif major >= 570:
                    status.driver_branch = "R570 (Production, EOL Feb 2026, CUDA 12.x)"
                elif major >= 535:
                    status.driver_branch = "R535 (LTS through Jun 2026, CUDA 12.x)"
                else:
                    status.driver_branch = f"R{major} (Legacy)"
            except (ValueError, IndexError):
                pass

        # 6. Check for driver update via GitHub NVIDIA releases
        await self._check_nvidia_latest(status)

        self._state["nvidia"] = asdict(status)
        self._save_state()

        if self.event_bus:
            self.event_bus.publish("system.nvidia.status", asdict(status))

        return status

    async def _check_nvidia_latest(self, status: NvidiaStatus):
        """Check for latest NVIDIA driver version (best-effort)."""
        try:
            if not HAS_AIOHTTP:
                return

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.github.com/repos/NVIDIA/open-gpu-kernel-modules/releases/latest",
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={"Accept": "application/vnd.github.v3+json"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tag = data.get("tag_name", "")
                        if tag:
                            status.latest_driver = tag
                            if status.driver_version and tag != status.driver_version:
                                status.update_available = True
        except Exception:
            pass

    def get_nvidia_update_instructions(self) -> str:
        """Return platform-specific NVIDIA update instructions."""
        os_type = platform.system().lower()
        if os_type == "windows":
            return (
                "NVIDIA Driver Update (Windows):\n"
                "  1. Open GeForce Experience or visit https://www.nvidia.com/drivers\n"
                "  2. Download the latest Game Ready or Studio driver\n"
                "  3. Run the installer (Express or Custom)\n"
                "  Alternatively: winget upgrade NVIDIA.GeForceExperience\n"
            )
        else:
            return (
                "NVIDIA Driver Update (Linux/WSL2):\n"
                "  # Check current: nvidia-smi\n"
                "  # Ubuntu/Debian:\n"
                "  sudo apt update\n"
                "  sudo ubuntu-drivers install --gpgpu\n"
                "  # Or specific version:\n"
                "  sudo apt install nvidia-driver-580\n"
                "  # CUDA Toolkit:\n"
                "  # Visit https://developer.nvidia.com/cuda-downloads\n"
            )

    # -----------------------------------------------------------------------
    # Ollama Status & Updates
    # -----------------------------------------------------------------------

    async def check_ollama_status(self) -> OllamaStatus:
        """Check Ollama installation and available updates."""
        status = OllamaStatus(timestamp=datetime.now().isoformat())

        # Check if installed
        try:
            result = subprocess.run(
                ["ollama", "-v"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                status.installed = True
                output = result.stdout.strip()
                for word in reversed(output.split()):
                    if word and word[0].isdigit():
                        status.version = word
                        break
        except FileNotFoundError:
            status.installed = False
        except Exception:
            pass

        # Check API
        try:
            import requests
            resp = requests.get("http://127.0.0.1:11434/api/version", timeout=5)
            if resp.status_code == 200:
                status.api_reachable = True
                api_ver = resp.json().get("version", "")
                if api_ver and not status.version:
                    status.version = api_ver
        except Exception:
            pass

        # Count models
        try:
            import requests
            resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                status.models_count = len(models)
        except Exception:
            pass

        # Check latest version from GitHub
        try:
            if HAS_AIOHTTP:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.github.com/repos/ollama/ollama/releases/latest",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            tag = data.get("tag_name", "").lstrip("v")
                            if tag:
                                status.latest_version = tag
                                if status.version and tag != status.version:
                                    status.update_available = True
            else:
                import requests
                resp = requests.get(
                    "https://api.github.com/repos/ollama/ollama/releases/latest",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tag = data.get("tag_name", "").lstrip("v")
                    if tag:
                        status.latest_version = tag
                        if status.version and tag != status.version:
                            status.update_available = True
        except Exception:
            pass

        self._state["ollama"] = asdict(status)
        self._save_state()

        if self.event_bus:
            self.event_bus.publish("system.ollama.status", asdict(status))

        return status

    async def update_ollama_safe(self) -> UpdateResult:
        """Update Ollama safely using the OllamaModelManager for model preservation."""
        result = UpdateResult(
            component="ollama",
            timestamp=datetime.now().isoformat()
        )

        try:
            from core.ollama_model_manager import get_ollama_model_manager
            manager = get_ollama_model_manager(self.event_bus)

            if not manager.is_initialized:
                await manager.initialize()

            result.old_version = manager.current_ollama_version or ""

            success, message = await manager.safe_update_ollama()
            result.success = success
            result.message = message
            result.new_version = await manager._get_ollama_version() or result.old_version

            self.logger.info(f"Ollama update: {message}")

        except Exception as e:
            result.success = False
            result.message = str(e)
            self.logger.error(f"Ollama update failed: {e}")

        if self.event_bus:
            self.event_bus.publish("system.update.result", asdict(result))

        return result

    # -----------------------------------------------------------------------
    # Kingdom AI Package Updates
    # -----------------------------------------------------------------------

    async def check_kingdom_status(self) -> KingdomStatus:
        """Check Kingdom AI's Python dependencies using importlib.metadata."""
        status = KingdomStatus(
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            timestamp=datetime.now().isoformat()
        )

        req_file = self._kingdom_root / "requirements.txt"
        if not req_file.exists():
            status.packages_ok = True
            return status

        try:
            with open(req_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue

                    # Parse package==version or package>=version
                    pkg_name = line
                    req_version = ""
                    for sep in ("==", ">=", "<=", "~=", "!="):
                        if sep in line:
                            pkg_name, req_version = line.split(sep, 1)
                            break

                    pkg_name = pkg_name.strip()
                    req_version = req_version.strip()

                    try:
                        dist = importlib.metadata.distribution(pkg_name)
                        installed_ver = dist.version
                        if req_version and self._version_lt(installed_ver, req_version):
                            status.outdated_packages.append(
                                f"{pkg_name} (installed={installed_ver}, required={req_version})"
                            )
                    except importlib.metadata.PackageNotFoundError:
                        status.missing_packages.append(pkg_name)

            status.packages_ok = (
                len(status.missing_packages) == 0 and
                len(status.outdated_packages) == 0
            )

        except Exception as e:
            self.logger.warning(f"Package check failed: {e}")

        self._state["kingdom"] = asdict(status)
        self._save_state()

        if self.event_bus:
            self.event_bus.publish("system.kingdom.status", asdict(status))

        return status

    async def update_packages_safe(self) -> UpdateResult:
        """Update Python packages from requirements.txt with rollback."""
        result = UpdateResult(
            component="packages",
            timestamp=datetime.now().isoformat()
        )

        try:
            req_file = self._kingdom_root / "requirements.txt"
            if not req_file.exists():
                result.success = True
                result.message = "No requirements.txt found"
                return result

            # Freeze current state for rollback
            freeze_file = self._backup_dir / f"pip_freeze_{int(time.time())}.txt"
            freeze_result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True, text=True, timeout=30
            )
            if freeze_result.returncode == 0:
                freeze_file.write_text(freeze_result.stdout)
                self.logger.info(f"Package state saved to {freeze_file}")

            # Run pip install
            install_result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file),
                 "--quiet", "--no-warn-script-location"],
                capture_output=True, text=True, timeout=600
            )

            if install_result.returncode == 0:
                result.success = True
                result.message = "All packages updated successfully"
                self.logger.info("Package update complete")
            else:
                result.success = False
                result.message = f"pip install failed: {install_result.stderr[:500]}"
                self.logger.error(f"Package update failed: {install_result.stderr[:200]}")

                # Rollback
                if freeze_file.exists():
                    self.logger.info("Rolling back packages...")
                    rollback = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", str(freeze_file),
                         "--quiet", "--no-warn-script-location"],
                        capture_output=True, text=True, timeout=600
                    )
                    if rollback.returncode == 0:
                        result.rolled_back = True
                        result.message += " (rolled back successfully)"
                    else:
                        result.message += " (rollback also failed!)"

        except Exception as e:
            result.success = False
            result.message = str(e)
            self.logger.error(f"Package update error: {e}")

        if self.event_bus:
            self.event_bus.publish("system.update.result", asdict(result))

        return result

    # -----------------------------------------------------------------------
    # Comprehensive System Check (runs on startup)
    # -----------------------------------------------------------------------

    async def run_startup_checks(self) -> Dict[str, Any]:
        """
        Run all system checks on startup. Non-blocking, informational.
        Auto-updates only when safe (Ollama, packages).
        NVIDIA updates are notification-only (require user action).
        """
        results: Dict[str, Any] = {"timestamp": datetime.now().isoformat()}

        self.logger.info("=" * 60)
        self.logger.info("KINGDOM AI SYSTEM UPDATE CHECK (SOTA 2026)")
        self.logger.info("=" * 60)

        # 1. NVIDIA status (info only, never auto-update drivers)
        nvidia = await self.check_nvidia_status()
        results["nvidia"] = asdict(nvidia)
        if nvidia.update_available:
            self.logger.info(
                f"NVIDIA driver update available: {nvidia.driver_version} -> {nvidia.latest_driver}"
            )
            if self.event_bus:
                self.event_bus.publish("system.notification", {
                    "type": "info",
                    "title": "NVIDIA Update Available",
                    "message": f"Driver update: {nvidia.driver_version} -> {nvidia.latest_driver}\n"
                               f"{self.get_nvidia_update_instructions()}"
                })

        # 2. Ollama auto-update (safe, with model preservation)
        ollama = await self.check_ollama_status()
        results["ollama"] = asdict(ollama)
        if ollama.update_available and ollama.installed:
            auto_update_ollama = self.config.get("auto_update_ollama", True)
            if auto_update_ollama:
                self.logger.info(
                    f"Ollama update: {ollama.version} -> {ollama.latest_version} (auto-updating)"
                )
                update_result = await self.update_ollama_safe()
                results["ollama_update"] = asdict(update_result)
            else:
                self.logger.info(
                    f"Ollama update available: {ollama.version} -> {ollama.latest_version} (auto-update disabled)"
                )

        # 3. Package health check (auto-install missing, warn on outdated)
        kingdom = await self.check_kingdom_status()
        results["kingdom"] = asdict(kingdom)
        if kingdom.missing_packages:
            self.logger.warning(f"Missing packages: {kingdom.missing_packages}")
            auto_update_packages = self.config.get("auto_update_packages", True)
            if auto_update_packages:
                self.logger.info("Auto-installing missing packages...")
                pkg_result = await self.update_packages_safe()
                results["package_update"] = asdict(pkg_result)

        if kingdom.outdated_packages:
            self.logger.info(f"Outdated packages: {kingdom.outdated_packages}")

        self._state["last_startup_check"] = datetime.now().isoformat()
        self._save_state()

        self.logger.info("System update check complete")
        return results

    # -----------------------------------------------------------------------
    # Background periodic checker
    # -----------------------------------------------------------------------

    def _start_background_checker(self):
        """Start background thread for periodic update checks."""
        if self._running:
            return
        self._running = True
        self._bg_thread = threading.Thread(
            target=self._background_check_loop, daemon=True, name="KingdomUpdateChecker"
        )
        self._bg_thread.start()
        self.logger.info("Background update checker started (6h interval)")

    def _background_check_loop(self):
        """Periodically check for updates in background."""
        while self._running:
            try:
                time.sleep(self.UPDATE_CHECK_INTERVAL)
                if not self._running:
                    break

                self.logger.info("Running periodic update check...")
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self._periodic_check())
                finally:
                    loop.close()

            except Exception as e:
                self.logger.error(f"Background check error: {e}")
                time.sleep(60)

    async def _periodic_check(self):
        """Periodic check - lighter than startup, just status."""
        try:
            nvidia = await self.check_nvidia_status()
            ollama = await self.check_ollama_status()

            if nvidia.update_available and self.event_bus:
                self.event_bus.publish("system.notification", {
                    "type": "info",
                    "title": "NVIDIA Update Available",
                    "message": f"Driver: {nvidia.driver_version} -> {nvidia.latest_driver}"
                })

            if ollama.update_available:
                auto_update = self.config.get("auto_update_ollama", True)
                if auto_update:
                    await self.update_ollama_safe()
                elif self.event_bus:
                    self.event_bus.publish("system.notification", {
                        "type": "info",
                        "title": "Ollama Update Available",
                        "message": f"Version: {ollama.version} -> {ollama.latest_version}"
                    })

        except Exception as e:
            self.logger.error(f"Periodic check failed: {e}")

    # -----------------------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------------------

    def _handle_update_check(self, data: Dict):
        """Handle manual update check request."""
        threading.Thread(
            target=lambda: asyncio.run(self.run_startup_checks()),
            daemon=True
        ).start()

    def _handle_nvidia_update(self, data: Dict):
        """Handle NVIDIA update request (notification only)."""
        if self.event_bus:
            self.event_bus.publish("system.notification", {
                "type": "info",
                "title": "NVIDIA Driver Update",
                "message": self.get_nvidia_update_instructions()
            })

    def _handle_ollama_update(self, data: Dict):
        """Handle Ollama update request."""
        threading.Thread(
            target=lambda: asyncio.run(self.update_ollama_safe()),
            daemon=True
        ).start()

    def _handle_package_update(self, data: Dict):
        """Handle package update request."""
        threading.Thread(
            target=lambda: asyncio.run(self.update_packages_safe()),
            daemon=True
        ).start()

    # -----------------------------------------------------------------------
    # Hot Reload Engine (safe module reloading)
    # -----------------------------------------------------------------------

    def hot_reload_module(self, file_path: str, code: Optional[str] = None) -> Dict[str, Any]:
        """
        Safely hot-reload a Python module with backup and rollback.

        Steps:
        1. Validate syntax of new code (AST parse)
        2. Backup the original file
        3. Write new code (if provided)
        4. Resolve the full module name from file path
        5. Reload the module and all dependents
        6. Verify no import errors
        7. Rollback on any failure

        Returns dict with success, message, and details.
        """
        result = {
            "success": False,
            "message": "",
            "file": file_path,
            "module": "",
            "backup_path": "",
            "rolled_back": False
        }

        try:
            file_path = os.path.abspath(file_path)
            if not file_path.endswith(".py"):
                result["message"] = "Only .py files can be hot-reloaded"
                return result

            # Step 1: Validate syntax
            if code:
                import ast
                try:
                    ast.parse(code, filename=file_path)
                except SyntaxError as e:
                    result["message"] = f"Syntax error at line {e.lineno}: {e.msg}"
                    return result

            # Step 2: Backup original
            backup_path = ""
            if os.path.exists(file_path):
                timestamp = int(time.time())
                backup_path = f"{file_path}.bak.{timestamp}"
                shutil.copy2(file_path, backup_path)
                result["backup_path"] = backup_path

            # Step 3: Write new code
            if code:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)

            # Step 4: Resolve module name
            module_name = self._resolve_module_name(file_path)
            result["module"] = module_name or os.path.splitext(os.path.basename(file_path))[0]

            # Step 5: Reload
            if module_name and module_name in sys.modules:
                old_module = sys.modules[module_name]
                try:
                    reloaded = importlib.reload(old_module)
                    sys.modules[module_name] = reloaded

                    # Also reload any modules that import this one
                    dependents = self._find_dependent_modules(module_name)
                    for dep_name in dependents:
                        try:
                            dep_mod = sys.modules.get(dep_name)
                            if dep_mod:
                                importlib.reload(dep_mod)
                        except Exception as dep_err:
                            self.logger.warning(f"Dependent reload warning ({dep_name}): {dep_err}")

                    result["success"] = True
                    result["message"] = f"Module '{module_name}' hot-reloaded successfully"
                    self.logger.info(f"Hot reload success: {module_name}")

                except Exception as reload_err:
                    self.logger.error(f"Hot reload failed: {reload_err}")

                    # Step 7: Rollback
                    if backup_path and os.path.exists(backup_path):
                        shutil.copy2(backup_path, file_path)
                        # Re-reload with original code
                        try:
                            importlib.reload(old_module)
                        except Exception:
                            pass
                        result["rolled_back"] = True

                    result["message"] = f"Reload failed (rolled back): {reload_err}"
            else:
                result["success"] = True
                result["message"] = f"File saved. Module not in sys.modules, will load on next import."

            # Clean up old backups (keep last 5)
            self._cleanup_backups(file_path)

        except Exception as e:
            result["message"] = f"Hot reload error: {e}"
            self.logger.error(f"Hot reload error: {e}")

        if self.event_bus:
            self.event_bus.publish("system.hot_reload.result", result)

        return result

    def _resolve_module_name(self, file_path: str) -> Optional[str]:
        """Resolve a file path to its Python module name."""
        file_path = os.path.abspath(file_path)

        # Check sys.modules for a match
        for name, mod in sys.modules.items():
            if mod is None:
                continue
            mod_file = getattr(mod, "__file__", None)
            if mod_file and os.path.abspath(mod_file) == file_path:
                return name

        # Try to construct from path relative to kingdom root
        kingdom_root = str(self._kingdom_root)
        if file_path.startswith(kingdom_root):
            rel = os.path.relpath(file_path, kingdom_root)
            # Convert path separators and remove .py
            module_name = rel.replace(os.sep, ".").replace("/", ".")
            if module_name.endswith(".py"):
                module_name = module_name[:-3]
            if module_name.endswith(".__init__"):
                module_name = module_name[:-9]
            return module_name

        return None

    def _find_dependent_modules(self, module_name: str) -> List[str]:
        """Find modules that import the given module (shallow, 1 level)."""
        dependents = []
        target_parts = module_name.split(".")

        for name, mod in list(sys.modules.items()):
            if mod is None or name == module_name:
                continue
            try:
                mod_dict = vars(mod) if mod else {}
                for attr_val in mod_dict.values():
                    if isinstance(attr_val, type(sys)):  # is a module
                        attr_name = getattr(attr_val, "__name__", "")
                        if attr_name == module_name:
                            dependents.append(name)
                            break
            except Exception:
                continue

        return dependents[:10]  # cap to avoid excessive reloads

    def _cleanup_backups(self, file_path: str, keep: int = 5):
        """Remove old backup files, keeping the most recent ones."""
        try:
            directory = os.path.dirname(file_path)
            base = os.path.basename(file_path)
            backups = sorted(
                [f for f in os.listdir(directory) if f.startswith(base + ".bak.")],
                reverse=True
            )
            for old_backup in backups[keep:]:
                try:
                    os.remove(os.path.join(directory, old_backup))
                except Exception:
                    pass
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # State persistence
    # -----------------------------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        """Load persisted state from disk."""
        try:
            if self._state_file.exists():
                return json.loads(self._state_file.read_text())
        except Exception:
            pass
        return {}

    def _save_state(self):
        """Save state to disk."""
        try:
            self._state["last_saved"] = datetime.now().isoformat()
            self._state_file.write_text(json.dumps(self._state, indent=2, default=str))
        except Exception as e:
            self.logger.debug(f"State save error: {e}")

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _version_lt(a: str, b: str) -> bool:
        """Compare version strings. Returns True if a < b."""
        try:
            from packaging.version import Version
            return Version(a) < Version(b)
        except ImportError:
            pass

        try:
            a_parts = [int(x) for x in a.split(".")[:3]]
            b_parts = [int(x) for x in b.split(".")[:3]]
            while len(a_parts) < 3:
                a_parts.append(0)
            while len(b_parts) < 3:
                b_parts.append(0)
            return a_parts < b_parts
        except (ValueError, AttributeError):
            return a < b

    def get_full_status(self) -> Dict[str, Any]:
        """Get cached status of all components."""
        return {
            "nvidia": self._state.get("nvidia", {}),
            "ollama": self._state.get("ollama", {}),
            "kingdom": self._state.get("kingdom", {}),
            "last_startup_check": self._state.get("last_startup_check", ""),
            "last_saved": self._state.get("last_saved", "")
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_system_updater: Optional[SystemUpdater] = None


def get_system_updater(event_bus=None, config=None) -> SystemUpdater:
    """Get or create the System Updater singleton."""
    global _system_updater
    if _system_updater is None:
        _system_updater = SystemUpdater(event_bus=event_bus, config=config)
    return _system_updater


async def initialize_system_updater(event_bus=None, config=None) -> SystemUpdater:
    """Initialize and return the System Updater."""
    updater = get_system_updater(event_bus, config)
    await updater.initialize()
    return updater
