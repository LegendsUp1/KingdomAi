#!/usr/bin/env python3
"""
Shared Ollama base URL for Kingdom AI.
All Ollama usage (brain router, Thoth live integration, GUI, etc.) must use
this single WSL-aware URL so the Ollama brain is used consistently.
"""

import os
import logging

logger = logging.getLogger(__name__)

_OLLAMA_BASE_URL_CACHE: str | None = None


def _dbg(level: str, location: str, message: str, data: dict = None) -> None:
    """Debug logging helper for Ollama config.
    
    Args:
        level: Log level indicator ('B' for debug, 'I' for info, etc.)
        location: Code location identifier
        message: Debug message
        data: Optional data dictionary to include
    """
    if data:
        logger.debug("[%s] %s: %s | %s", level, location, message, data)
    else:
        logger.debug("[%s] %s: %s", level, location, message)


def get_ollama_base_url() -> str:
    """
    Return the Ollama API base URL (no trailing slash).
    - Env KINGDOM_OLLAMA_BASE_URL wins if set (e.g. http://172.20.0.1:11434 for WSL).
    - In WSL: use Windows host IP so Ollama on Windows is reachable.
    - Otherwise: http://localhost:11434.
    """
    global _OLLAMA_BASE_URL_CACHE
    if _OLLAMA_BASE_URL_CACHE is not None:
        return _OLLAMA_BASE_URL_CACHE

    url = (os.environ.get("KINGDOM_OLLAMA_BASE_URL") or "").strip()
    if url:
        _OLLAMA_BASE_URL_CACHE = url.rstrip("/")
        logger.debug("Ollama base URL from KINGDOM_OLLAMA_BASE_URL: %s", _OLLAMA_BASE_URL_CACHE)
        return _OLLAMA_BASE_URL_CACHE

    # Default for non-WSL
    url = "http://localhost:11434"
    try:
        with open("/proc/version", "r", encoding="utf-8") as f:
            if "microsoft" not in f.read().lower():
                _OLLAMA_BASE_URL_CACHE = url
                _dbg("B", "ollama_config:get_ollama_base_url", "Non-WSL, using localhost", {"url": url})
                return _OLLAMA_BASE_URL_CACHE
    except Exception:
        _OLLAMA_BASE_URL_CACHE = url
        return _OLLAMA_BASE_URL_CACHE

    # WSL: prefer localhost if Ollama is running inside WSL2 (common case)
    localhost_url = "http://127.0.0.1:11434"
    try:
        from urllib.request import urlopen
        with urlopen(f"{localhost_url}/api/tags", timeout=2) as _:
            logger.info("Ollama base URL (WSL, local): %s", localhost_url)
            _OLLAMA_BASE_URL_CACHE = localhost_url
            return _OLLAMA_BASE_URL_CACHE
    except Exception:
        pass

    # WSL: Ollama on Windows host — use host IP
    try:
        import subprocess
        r = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and "via" in r.stdout:
            parts = r.stdout.split()
            if len(parts) >= 3 and parts[0] == "default":
                host_ip = parts[2]
                url = f"http://{host_ip}:11434"
                _dbg("B", "ollama_config:get_ollama_base_url", "WSL ip route default", {"host_ip": host_ip, "url": url})
                logger.info("Ollama base URL (WSL, host): %s", url)
                _OLLAMA_BASE_URL_CACHE = url
                return _OLLAMA_BASE_URL_CACHE
    except Exception as e:
        _dbg("B", "ollama_config:get_ollama_base_url", "WSL ip route failed", {"error": str(e)})
        pass
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8") as rf:
            for line in rf:
                if line.strip().startswith("nameserver"):
                    host_ip = line.strip().split()[1]
                    if not host_ip.startswith("127."):
                        url = f"http://{host_ip}:11434"
                        logger.info("Ollama base URL (WSL resolv.conf): %s", url)
                        _OLLAMA_BASE_URL_CACHE = url
                        return _OLLAMA_BASE_URL_CACHE
                    break
    except Exception:
        pass

    _OLLAMA_BASE_URL_CACHE = localhost_url
    return _OLLAMA_BASE_URL_CACHE


def clear_ollama_url_cache() -> None:
    """Clear cached URL (e.g. for tests)."""
    global _OLLAMA_BASE_URL_CACHE
    _OLLAMA_BASE_URL_CACHE = None
