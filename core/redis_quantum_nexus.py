#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Redis Quantum Nexus import shim for Kingdom AI.

This module provides compatibility by forwarding imports to the correct module.
"""

import logging
from core.nexus.redis_quantum_nexus import RedisQuantumNexus, NexusEnvironment
from core.redis_connector import RedisQuantumNexusConnector

# Set up logging
logger = logging.getLogger("KingdomAI.QuantumNexus")
logger.info("Using Redis Quantum Nexus from core.nexus.redis_quantum_nexus")
logger.info("Re-exporting RedisQuantumNexusConnector from core.redis_connector")

# Re-export all needed members
__all__ = ['RedisQuantumNexus', 'NexusEnvironment', 'RedisQuantumNexusConnector']
