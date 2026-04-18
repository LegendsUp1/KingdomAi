#!/usr/bin/env python3
"""
Legacy filename kept for backward compatibility.

The implementation lives in :mod:`core.redis_connector`. This module re-exports
the same API so old imports continue to work without loading broken duplicate code.
"""

from core.redis_connector import (
    HAS_REDIS,
    REDIS_AVAILABLE,
    Redis,
    RedisConnector,
    RedisError,
    RedisQuantumNexusConnector,
    redis_import_successful,
)

__all__ = [
    "HAS_REDIS",
    "REDIS_AVAILABLE",
    "Redis",
    "RedisConnector",
    "RedisError",
    "RedisQuantumNexusConnector",
    "redis_import_successful",
]
