#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Mining Dashboard module for the Kingdom AI system.

This module provides visualization and monitoring for cryptocurrency mining operations,
displaying real-time statistics, profitability metrics, and performance charts.
It re-exports the core MiningDashboard component to maintain proper event bus
connections and system architecture integrity.
"""

import logging
import importlib.util
import sys
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

# Import MiningDashboard from core directory with strict enforcement - NO FALLBACKS
try:
    from core.mining_dashboard import MiningDashboard
    logger.info("Successfully imported MiningDashboard from core.mining_dashboard")
except ImportError as e:
    # Critical failure - Mining Dashboard is a mandatory component
    logger.critical(f"CRITICAL ERROR: Failed to import MiningDashboard: {str(e)}")
    logger.critical("MiningDashboard is a MANDATORY component with NO FALLBACKS ALLOWED")
    logger.critical("System halting - fix the core.mining_dashboard module and restart")
    
    # System must halt on critical component failures per policy
    sys.exit(1)

# No fallback implementations allowed - removed all fallback classes

# Export the MiningDashboard class
__all__ = ["MiningDashboard"]
