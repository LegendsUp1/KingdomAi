#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI GUI Qt Frames Package

This package contains all the PyQt6 QWidget implementations 
for the Kingdom AI GUI tabs and components.
"""

import logging
import importlib.util
import sys
import os
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Initialize tab class references (will be filled by imports)
BlockchainTab = None
ThothAITab = None
WalletTab = None
ApiKeyManagerTab = None
MiningTab = None
VRTab = None
SettingsTab = None

# Helper function to import a module and handle failures gracefully
def import_module_safe(module_name, class_name, fallback_path=None):
    try:
        # Try normal relative import first
        module = importlib.import_module(f'.{module_name}', package='gui.qt_frames')
        if hasattr(module, class_name):
            return getattr(module, class_name)
    except ImportError as e:
        logger.warning(f"Could not import {class_name} via relative import: {e}")
        
    # If fallback path is provided, try absolute import
    if fallback_path:
        try:
            # Construct absolute path
            abs_path = Path(fallback_path) / f"{module_name}.py"
            if not abs_path.exists():
                logger.warning(f"Fallback file {abs_path} does not exist")
                return None
                
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            if not spec or not spec.loader:
                logger.warning(f"Could not create spec for {abs_path}")
                return None
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, class_name):
                return getattr(module, class_name)
            else:
                logger.warning(f"Module {module_name} does not contain class {class_name}")
                return None
        except Exception as e:
            logger.warning(f"Failed to import {class_name} from {fallback_path}: {e}")
            return None
    return None

# Get the absolute path of the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Import all tab classes
BlockchainTab = import_module_safe('blockchain_tab', 'BlockchainTab', current_dir)
ThothAITab = import_module_safe('thoth_ai_tab', 'ThothAITab', current_dir)
WalletTab = import_module_safe('wallet_tab', 'WalletTab', current_dir)
ApiKeyManagerTab = import_module_safe('api_key_manager_tab', 'ApiKeyManagerTab', current_dir)
MiningTab = import_module_safe('mining_tab', 'MiningTab', current_dir)
VRTab = import_module_safe('vr_tab', 'VRTab', current_dir)
SettingsTab = import_module_safe('settings_tab', 'SettingsTab', current_dir)

# Log import results
for name, cls in [
    ("BlockchainTab", BlockchainTab),
    ("ThothAITab", ThothAITab),
    ("WalletTab", WalletTab),
    ("ApiKeyManagerTab", ApiKeyManagerTab),
    ("MiningTab", MiningTab),
    ("VRTab", VRTab),
    ("SettingsTab", SettingsTab),
]:
    logger.info(f"Tab class {name} {'successfully imported' if cls else 'FAILED to import'}")

# Static __all__ definition with all available tab classes
# This approach is more IDE-friendly than dynamic construction
_available_exports = []
for name, cls in [
    ("BlockchainTab", BlockchainTab),
    ("ThothAITab", ThothAITab),
    ("WalletTab", WalletTab),
    ("ApiKeyManagerTab", ApiKeyManagerTab),
    ("MiningTab", MiningTab),
    ("VRTab", VRTab),
    ("SettingsTab", SettingsTab),
]:
    if cls is not None:
        _available_exports.append(name)

# Define __all__ statically based on available exports
__all__ = [
    "BlockchainTab",
    "ThothAITab", 
    "WalletTab",
    "ApiKeyManagerTab",
    "MiningTab",
    "VRTab",
    "SettingsTab",
]