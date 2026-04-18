"""
Structured Logging Configuration for Kingdom AI
JSON logs with full context - NO MORE GUESSING!

Now delegates to centralized SOTA 2025 logging system in core.kingdom_logging.
"""

import logging
import sys
from pathlib import Path

# Import centralized logging (auto-configures on import)
try:
    from core.kingdom_logging import (
        configure_kingdom_logging,
        get_logger,
        enable_debug_console,
        disable_debug_console,
    )
    _USE_CENTRALIZED = True
except ImportError:
    _USE_CENTRALIZED = False

# Try structlog if available (legacy support)
try:
    import structlog
    _HAS_STRUCTLOG = True
except ImportError:
    _HAS_STRUCTLOG = False


def setup_structured_logging():
    """
    Configure structured logging for Kingdom AI.
    
    Now delegates to centralized SOTA 2025 logging system which provides:
    - Reduced terminal clutter (WARNING+ on console)
    - Full DEBUG logs to files with JSON format
    - Rate limiting for repetitive errors
    - Automatic log rotation
    
    Returns:
        Logger instance
    """
    # Use centralized logging if available
    if _USE_CENTRALIZED:
        return get_logger("KingdomAI")
    
    # Fallback to structlog if available
    if _HAS_STRUCTLOG:
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Configure standard logging - WARNING+ on console only
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=logging.WARNING,  # Reduced clutter
        )
        
        return structlog.get_logger()
    
    # Basic fallback
    return logging.getLogger("KingdomAI")
