#!/usr/bin/env python3
"""
Kingdom AI Core Settings
"""
from pathlib import Path as _Path

def _find_redis_password_file() -> str:
    """Locate the redis password file using repo-relative paths with fallbacks."""
    repo_cfg = _Path(__file__).resolve().parent.parent / "config" / "redis_password.txt"
    if repo_cfg.is_file():
        return str(repo_cfg)
    home_cfg = _Path.home() / ".kingdom_ai" / "redis_password.txt"
    if home_cfg.is_file():
        return str(home_cfg)
    return str(repo_cfg)

# Redis Quantum Nexus Configuration
REDIS_CONFIG = {
    "redis_host": "localhost",
    "redis_port": 6380,
    "redis_db": 0,
    "redis_password_file": _find_redis_password_file(),
    "redis_password_env": "KINGDOM_REDIS_PASSWORD"
}
