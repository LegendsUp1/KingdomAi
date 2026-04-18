#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - Centralized Logging Module

This module provides a centralized logging configuration for the Kingdom AI system.
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional

# Configure root logger
def setup_logging(log_level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    Configure the root logger with console and optional file handlers.
    
    Args:
        log_level: Logging level (e.g., logging.INFO, logging.DEBUG)
        log_file: Optional path to log file. If None, logs only to console.
    """
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if log file is specified
    if log_file:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (usually __name__ of the calling module)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"KingdomAI.{name}")

# Set up default logging when module is imported
setup_logging(logging.INFO)

# For backward compatibility
logger = get_logger(__name__)
