#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOTA 2026 Color-Coded Console Logging by System Tab/Subtab Categories

This module provides ANSI color-coded console output for Kingdom AI,
organized by system categories matching the GUI tabs and subtabs.

Categories and Colors:
- SYSTEM (Core/Init): White/Bold
- DASHBOARD: Cyan
- TRADING: Green
- MINING: Yellow
- BLOCKCHAIN: Magenta
- WALLET: Blue
- THOTH_AI: Red (bright)
- CODEGEN: Cyan (bright)
- API_KEYS: Yellow (bright)
- VR: Magenta (bright)
- SETTINGS: White
- REDIS: Red
- VOICE: Green (bright)
- SENTIENCE: Magenta
- ERRORS: Red/Bold
- WARNINGS: Yellow/Bold
"""

import logging
import re
import sys
from datetime import datetime
from typing import Dict, Optional

# ANSI Color Codes
class Colors:
    """ANSI escape codes for terminal colors."""
    # Reset
    RESET = "\033[0m"
    
    # Regular colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright/Bold colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Styles
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


# Category to Color mapping - organized by GUI tabs
CATEGORY_COLORS: Dict[str, str] = {
    # Core System
    "SYSTEM": Colors.BOLD + Colors.WHITE,
    "INIT": Colors.BOLD + Colors.WHITE,
    "STARTUP": Colors.BOLD + Colors.WHITE,
    "SHUTDOWN": Colors.BOLD + Colors.YELLOW,
    
    # Tab 1: Dashboard
    "DASHBOARD": Colors.CYAN,
    "DashboardTab": Colors.CYAN,
    "Dashboard": Colors.CYAN,
    
    # Tab 2: Trading
    "TRADING": Colors.GREEN,
    "TradingTab": Colors.GREEN,
    "Trading": Colors.GREEN,
    "TradingComponent": Colors.GREEN,
    "QuantumTrading": Colors.BRIGHT_GREEN,
    "OrderManagement": Colors.GREEN,
    "RealExchangeExecutor": Colors.BRIGHT_GREEN,
    
    # Tab 3: Mining
    "MINING": Colors.YELLOW,
    "MiningTab": Colors.YELLOW,
    "Mining": Colors.YELLOW,
    "MiningSystem": Colors.YELLOW,
    "QuantumMining": Colors.BRIGHT_YELLOW,
    "ExahashQuantum": Colors.BRIGHT_YELLOW,
    
    # Tab 4: Blockchain
    "BLOCKCHAIN": Colors.MAGENTA,
    "BlockchainTab": Colors.MAGENTA,
    "Blockchain": Colors.MAGENTA,
    "Web3": Colors.MAGENTA,
    "kingdomweb3": Colors.BRIGHT_MAGENTA,
    "network_stats": Colors.MAGENTA,
    
    # Tab 5: Wallet
    "WALLET": Colors.BLUE,
    "WalletTab": Colors.BLUE,
    "Wallet": Colors.BLUE,
    "WalletManager": Colors.BLUE,
    "Portfolio": Colors.BRIGHT_BLUE,
    
    # Tab 6: Thoth AI
    "THOTH": Colors.BRIGHT_RED,
    "ThothAI": Colors.BRIGHT_RED,
    "ThothAITab": Colors.BRIGHT_RED,
    "thoth": Colors.BRIGHT_RED,
    "brain_router": Colors.BRIGHT_RED,
    "BrainRouter": Colors.BRIGHT_RED,
    "Ollama": Colors.BRIGHT_RED,
    
    # Tab 7: Code Generator
    "CODEGEN": Colors.BRIGHT_CYAN,
    "CodeGenerator": Colors.BRIGHT_CYAN,
    "CodeGen": Colors.BRIGHT_CYAN,
    
    # Tab 8: API Keys
    "APIKEYS": Colors.BRIGHT_YELLOW,
    "APIKeyManager": Colors.BRIGHT_YELLOW,
    "api_key": Colors.BRIGHT_YELLOW,
    "global_api_keys": Colors.BRIGHT_YELLOW,
    
    # Tab 9: VR
    "VR": Colors.BRIGHT_MAGENTA,
    "VRTab": Colors.BRIGHT_MAGENTA,
    "VRManager": Colors.BRIGHT_MAGENTA,
    "OpenVR": Colors.BRIGHT_MAGENTA,
    
    # Tab 10: Settings
    "SETTINGS": Colors.WHITE,
    "SettingsTab": Colors.WHITE,
    "Settings": Colors.WHITE,
    
    # Special Systems
    "REDIS": Colors.RED,
    "RedisConnector": Colors.RED,
    "QuantumNexus": Colors.RED,
    "Redis": Colors.RED,
    
    "VOICE": Colors.BRIGHT_GREEN,
    "VoiceManager": Colors.BRIGHT_GREEN,
    "BlackPanther": Colors.BRIGHT_GREEN,
    "TTS": Colors.BRIGHT_GREEN,
    "WSLAudioBridge": Colors.BRIGHT_GREEN,
    
    "SENTIENCE": Colors.MAGENTA,
    "Sentience": Colors.MAGENTA,
    "ConsciousnessField": Colors.MAGENTA,
    "ThothSentience": Colors.MAGENTA,
    "Frequency432": Colors.MAGENTA,
    
    "EVENT_BUS": Colors.CYAN,
    "EventBus": Colors.CYAN,
    
    "GUI": Colors.BRIGHT_WHITE,
    "MainWindow": Colors.BRIGHT_WHITE,
    "TabManager": Colors.BRIGHT_WHITE,
    
    # Hardware
    "HARDWARE": Colors.BRIGHT_BLUE,
    "HardwareAwareness": Colors.BRIGHT_BLUE,
    "HostDeviceManager": Colors.BRIGHT_BLUE,
    "GPU": Colors.BRIGHT_BLUE,
    
    # WebSocket
    "WEBSOCKET": Colors.CYAN,
    "WebSocket": Colors.CYAN,
    "websocket": Colors.CYAN,
}

# Level colors
LEVEL_COLORS: Dict[str, str] = {
    "DEBUG": Colors.DIM + Colors.WHITE,
    "INFO": Colors.WHITE,
    "WARNING": Colors.BOLD + Colors.YELLOW,
    "ERROR": Colors.BOLD + Colors.RED,
    "CRITICAL": Colors.BOLD + Colors.BG_RED + Colors.WHITE,
}


def get_category_color(logger_name: str) -> str:
    """Get the color code for a logger name based on category matching."""
    # Direct match first
    if logger_name in CATEGORY_COLORS:
        return CATEGORY_COLORS[logger_name]
    
    # Check for partial matches in logger name
    for category, color in CATEGORY_COLORS.items():
        if category.lower() in logger_name.lower():
            return color
    
    # Check for common patterns
    name_lower = logger_name.lower()
    if "trading" in name_lower:
        return CATEGORY_COLORS["TRADING"]
    elif "mining" in name_lower:
        return CATEGORY_COLORS["MINING"]
    elif "blockchain" in name_lower or "web3" in name_lower:
        return CATEGORY_COLORS["BLOCKCHAIN"]
    elif "wallet" in name_lower:
        return CATEGORY_COLORS["WALLET"]
    elif "thoth" in name_lower or "brain" in name_lower or "ai" in name_lower:
        return CATEGORY_COLORS["THOTH"]
    elif "redis" in name_lower or "nexus" in name_lower:
        return CATEGORY_COLORS["REDIS"]
    elif "voice" in name_lower or "speech" in name_lower or "tts" in name_lower:
        return CATEGORY_COLORS["VOICE"]
    elif "sentience" in name_lower or "consciousness" in name_lower or "432" in name_lower:
        return CATEGORY_COLORS["SENTIENCE"]
    elif "vr" in name_lower or "openvr" in name_lower:
        return CATEGORY_COLORS["VR"]
    elif "gui" in name_lower or "qt" in name_lower or "frame" in name_lower:
        return CATEGORY_COLORS["GUI"]
    elif "hardware" in name_lower or "device" in name_lower or "gpu" in name_lower:
        return CATEGORY_COLORS["HARDWARE"]
    elif "websocket" in name_lower or "ws" in name_lower:
        return CATEGORY_COLORS["WEBSOCKET"]
    elif "api" in name_lower and "key" in name_lower:
        return CATEGORY_COLORS["APIKEYS"]
    elif "event" in name_lower and "bus" in name_lower:
        return CATEGORY_COLORS["EVENT_BUS"]
    
    # Default to white
    return Colors.WHITE


class ColoredFormatter(logging.Formatter):
    """SOTA 2026 Color-coded logging formatter by system category."""
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, 
                 use_colors: bool = True):
        """Initialize the colored formatter.
        
        Args:
            fmt: Log format string
            datefmt: Date format string
            use_colors: Whether to use ANSI colors (disable for file output)
        """
        if fmt is None:
            fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors."""
        if not self.use_colors:
            return super().format(record)
        
        # Get category color based on logger name
        category_color = get_category_color(record.name)
        
        # Get level color
        level_color = LEVEL_COLORS.get(record.levelname, Colors.WHITE)
        
        # Build colored output
        # Format: [TIME] [LEVEL] [LOGGER_NAME] MESSAGE
        timestamp = self.formatTime(record, self.datefmt)
        
        # Color the level name
        colored_level = f"{level_color}{record.levelname}{Colors.RESET}"
        
        # Color the logger name by category
        colored_name = f"{category_color}{record.name}{Colors.RESET}"
        
        # Message gets subtle coloring based on level
        if record.levelno >= logging.ERROR:
            colored_msg = f"{Colors.RED}{record.getMessage()}{Colors.RESET}"
        elif record.levelno >= logging.WARNING:
            colored_msg = f"{Colors.YELLOW}{record.getMessage()}{Colors.RESET}"
        else:
            colored_msg = record.getMessage()
        
        # Final formatted string
        return f"{Colors.DIM}{timestamp}{Colors.RESET} - {colored_name} - {colored_level} - {colored_msg}"


def print_color_key_banner():
    """Print the color key banner showing all category colors."""
    banner = f"""
{Colors.BOLD}{Colors.BRIGHT_WHITE}{'=' * 80}{Colors.RESET}
{Colors.BOLD}{Colors.BRIGHT_WHITE}🎨 KINGDOM AI - COLOR-CODED LOGGING KEY{Colors.RESET}
{Colors.BOLD}{Colors.BRIGHT_WHITE}{'=' * 80}{Colors.RESET}

{Colors.BOLD}📊 SYSTEM CATEGORIES:{Colors.RESET}
  {CATEGORY_COLORS['SYSTEM']}■ SYSTEM/INIT{Colors.RESET}      - Core initialization, startup, shutdown
  {CATEGORY_COLORS['DASHBOARD']}■ DASHBOARD{Colors.RESET}       - Tab 1: System overview and metrics
  {CATEGORY_COLORS['TRADING']}■ TRADING{Colors.RESET}         - Tab 2: Trading system, exchanges, orders
  {CATEGORY_COLORS['MINING']}■ MINING{Colors.RESET}          - Tab 3: Mining operations, quantum mining
  {CATEGORY_COLORS['BLOCKCHAIN']}■ BLOCKCHAIN{Colors.RESET}      - Tab 4: Web3, networks, blockchain ops
  {CATEGORY_COLORS['WALLET']}■ WALLET{Colors.RESET}          - Tab 5: Wallet management, portfolio
  {CATEGORY_COLORS['THOTH']}■ THOTH AI{Colors.RESET}        - Tab 6: AI brain, Ollama, chat
  {CATEGORY_COLORS['CODEGEN']}■ CODE GEN{Colors.RESET}        - Tab 7: Code generation
  {CATEGORY_COLORS['APIKEYS']}■ API KEYS{Colors.RESET}        - Tab 8: API key management
  {CATEGORY_COLORS['VR']}■ VR{Colors.RESET}              - Tab 9: Virtual reality system
  {CATEGORY_COLORS['SETTINGS']}■ SETTINGS{Colors.RESET}        - Tab 10: Configuration

{Colors.BOLD}🔧 SUBSYSTEMS:{Colors.RESET}
  {CATEGORY_COLORS['REDIS']}■ REDIS{Colors.RESET}           - Redis Quantum Nexus (port 6380)
  {CATEGORY_COLORS['VOICE']}■ VOICE{Colors.RESET}           - VoiceManager, TTS, Black Panther
  {CATEGORY_COLORS['SENTIENCE']}■ SENTIENCE{Colors.RESET}       - AI consciousness, 432 Hz frequency
  {CATEGORY_COLORS['EVENT_BUS']}■ EVENT BUS{Colors.RESET}       - System event communication
  {CATEGORY_COLORS['GUI']}■ GUI{Colors.RESET}             - PyQt6 interface components
  {CATEGORY_COLORS['HARDWARE']}■ HARDWARE{Colors.RESET}        - GPU, devices, host detection
  {CATEGORY_COLORS['WEBSOCKET']}■ WEBSOCKET{Colors.RESET}       - Real-time data feeds

{Colors.BOLD}⚠️ LOG LEVELS:{Colors.RESET}
  {LEVEL_COLORS['DEBUG']}■ DEBUG{Colors.RESET}           - Detailed debugging information
  {LEVEL_COLORS['INFO']}■ INFO{Colors.RESET}            - General operational messages
  {LEVEL_COLORS['WARNING']}■ WARNING{Colors.RESET}         - Warning conditions
  {LEVEL_COLORS['ERROR']}■ ERROR{Colors.RESET}           - Error conditions
  {LEVEL_COLORS['CRITICAL']}■ CRITICAL{Colors.RESET}        - Critical failures

{Colors.BOLD}{Colors.BRIGHT_WHITE}{'=' * 80}{Colors.RESET}
"""
    print(banner)


def setup_colored_logging(level: int = logging.INFO) -> logging.Handler:
    """Set up color-coded console logging.
    
    Args:
        level: Minimum logging level
        
    Returns:
        The configured console handler
    """
    # Create colored console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter())
    
    return console_handler


def install_colored_logging(level: int = logging.INFO):
    """Install color-coded logging on the root logger.
    
    This replaces the default StreamHandler with our colored one.
    
    Args:
        level: Minimum logging level
    """
    root_logger = logging.getLogger()
    
    # Remove existing StreamHandlers to avoid duplicate output
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            root_logger.removeHandler(handler)
    
    # Add our colored handler
    colored_handler = setup_colored_logging(level)
    root_logger.addHandler(colored_handler)
    
    return colored_handler


# Convenience function to get a colored logger
def get_colored_logger(name: str) -> logging.Logger:
    """Get a logger with colored output configured."""
    logger = logging.getLogger(name)
    return logger


if __name__ == "__main__":
    # Demo the color-coded logging
    print_color_key_banner()
    
    # Set up logging
    logging.basicConfig(level=logging.DEBUG)
    install_colored_logging(logging.DEBUG)
    
    # Test various loggers
    test_loggers = [
        "KingdomAI.Trading",
        "KingdomAI.Mining",
        "KingdomAI.Blockchain",
        "KingdomAI.Wallet",
        "KingdomAI.ThothAI",
        "KingdomAI.Redis",
        "KingdomAI.Voice",
        "KingdomAI.Sentience",
        "KingdomAI.VR",
        "KingdomAI.GUI",
    ]
    
    for logger_name in test_loggers:
        logger = logging.getLogger(logger_name)
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
