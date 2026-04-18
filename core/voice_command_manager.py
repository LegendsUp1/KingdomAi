"""
Voice Command Manager - SOTA 2026 System-Wide Voice Control

This module provides comprehensive voice and text command control for the entire
Kingdom AI system. It enables users to control every tab, trigger every action,
and navigate the UI using natural language commands - spoken or typed.

SOTA 2026 Features:
- Natural language command parsing with fuzzy matching
- LLM-powered intelligent command interpretation (Ollama integration)
- System-wide command registry with hot-reload support
- Tab navigation, button triggers, scroll control
- Domain-specific commands (trading, mining, wallet, AI)
- Event bus integration for decoupled command execution
- Voice activation with wake word support
- Command history and undo support
"""

import re
import logging
from typing import Dict, List, Callable, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger("KingdomAI.VoiceCommandManager")


class CommandCategory(Enum):
    """Categories of voice commands."""
    NAVIGATION = "navigation"      # Tab switching, window control
    UI_CONTROL = "ui_control"      # Scroll, zoom, resize
    TRADING = "trading"            # Trading actions
    MINING = "mining"              # Mining actions
    WALLET = "wallet"              # Wallet operations
    BLOCKCHAIN = "blockchain"      # Blockchain operations
    AI = "ai"                      # AI/Thoth commands
    VISUAL = "visual"              # Visual canvas commands
    SETTINGS = "settings"          # Settings/config
    SYSTEM = "system"              # System-wide commands
    VR = "vr"                      # VR interface
    API = "api"                    # API key management


@dataclass
class VoiceCommand:
    """Represents a registered voice command."""
    name: str
    category: CommandCategory
    keywords: List[str]           # Trigger phrases
    action: str                   # Action identifier or event to publish
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    enabled: bool = True


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    command: Optional[VoiceCommand]
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


class VoiceCommandManager:
    """
    SOTA 2026 Voice Command Manager for Kingdom AI.
    
    Provides system-wide voice and text command control with:
    - Natural language understanding via Ollama LLM
    - Fuzzy keyword matching for robust recognition
    - Event bus integration for decoupled execution
    - Comprehensive command registry for all system functions
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern for system-wide access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, event_bus=None, ollama_brain=None):
        """Initialize the Voice Command Manager."""
        if self._initialized:
            return
        
        self.event_bus = event_bus
        self.ollama_brain = ollama_brain
        self.commands: Dict[str, VoiceCommand] = {}
        self.command_history: List[Tuple[datetime, str, CommandResult]] = []
        self.max_history = 100
        self._callbacks: Dict[str, List[Callable]] = {}
        self._main_window = None
        self._current_tab = None
        
        # SOTA 2026: Biometric Security Integration
        self._biometric_security = None
        self._require_biometric_auth = True  # Require auth for commands
        self._init_biometric_security()
        
        # Register all built-in commands
        self._register_builtin_commands()
        
        # Subscribe to event bus
        if self.event_bus:
            self.event_bus.subscribe('voice.command', self._handle_voice_event)
            self.event_bus.subscribe('text.command', self._handle_text_event)
        
        self._initialized = True
        logger.info("🎤 Voice Command Manager initialized - SOTA 2026")
    
    def set_main_window(self, main_window):
        """Set reference to main window for UI control."""
        self._main_window = main_window
        logger.info("🎤 Main window reference set")
    
    def set_ollama_brain(self, ollama_brain):
        """Set Ollama brain for intelligent command parsing."""
        self.ollama_brain = ollama_brain
        logger.info("🧠 Ollama brain connected for intelligent command parsing")
    
    def _init_biometric_security(self):
        """Initialize biometric security integration."""
        try:
            from core.biometric_security_manager import get_biometric_security_manager
            self._biometric_security = get_biometric_security_manager(self.event_bus)
            logger.info("🔐 Biometric Security Manager connected")
        except ImportError as e:
            logger.warning(f"⚠️ Biometric Security not available: {e}")
            self._biometric_security = None
            self._require_biometric_auth = False
        except Exception as e:
            logger.error(f"❌ Failed to initialize Biometric Security: {e}")
            self._biometric_security = None
            self._require_biometric_auth = False
    
    def set_biometric_security(self, security_manager):
        """Set biometric security manager reference."""
        self._biometric_security = security_manager
        logger.info("🔐 Biometric Security Manager set")
    
    def check_biometric_auth(self, command_name: str = None) -> Tuple[bool, str]:
        """Check if current user is authorized to execute commands.
        
        Args:
            command_name: Optional command name for fine-grained control
            
        Returns:
            Tuple of (authorized, message)
        """
        if not self._require_biometric_auth:
            return True, "Biometric auth disabled"
        
        if self._biometric_security is None:
            return True, "No biometric security configured"
        
        return self._biometric_security.can_execute_command(command_name)
    
    def _register_builtin_commands(self):
        """Register all built-in voice commands."""
        
        # ==================== NAVIGATION COMMANDS ====================
        navigation_commands = [
            VoiceCommand(
                name="go_to_dashboard",
                category=CommandCategory.NAVIGATION,
                keywords=["go to dashboard", "open dashboard", "show dashboard", 
                         "dashboard tab", "switch to dashboard", "dashboard"],
                action="navigate.tab.dashboard",
                description="Navigate to Dashboard tab"
            ),
            VoiceCommand(
                name="go_to_trading",
                category=CommandCategory.NAVIGATION,
                keywords=["go to trading", "open trading", "show trading", 
                         "trading tab", "switch to trading", "trading", "trade"],
                action="navigate.tab.trading",
                description="Navigate to Trading tab"
            ),
            VoiceCommand(
                name="go_to_mining",
                category=CommandCategory.NAVIGATION,
                keywords=["go to mining", "open mining", "show mining",
                         "mining tab", "switch to mining", "mining", "mine"],
                action="navigate.tab.mining",
                description="Navigate to Mining tab"
            ),
            VoiceCommand(
                name="go_to_wallet",
                category=CommandCategory.NAVIGATION,
                keywords=["go to wallet", "open wallet", "show wallet",
                         "wallet tab", "switch to wallet", "wallet", "wallets"],
                action="navigate.tab.wallet",
                description="Navigate to Wallet tab"
            ),
            VoiceCommand(
                name="go_to_blockchain",
                category=CommandCategory.NAVIGATION,
                keywords=["go to blockchain", "open blockchain", "show blockchain",
                         "blockchain tab", "switch to blockchain", "blockchain"],
                action="navigate.tab.blockchain",
                description="Navigate to Blockchain tab"
            ),
            VoiceCommand(
                name="go_to_thoth",
                category=CommandCategory.NAVIGATION,
                keywords=["go to thoth", "open thoth", "show thoth", "thoth tab",
                         "switch to thoth", "thoth", "ai tab", "go to ai",
                         "open ai", "kingdom ai"],
                action="navigate.tab.thoth",
                description="Navigate to Thoth AI tab"
            ),
            VoiceCommand(
                name="go_to_vr",
                category=CommandCategory.NAVIGATION,
                keywords=["go to vr", "open vr", "show vr", "vr tab",
                         "switch to vr", "virtual reality", "vr interface"],
                action="navigate.tab.vr",
                description="Navigate to VR tab"
            ),
            VoiceCommand(
                name="go_to_settings",
                category=CommandCategory.NAVIGATION,
                keywords=["go to settings", "open settings", "show settings",
                         "settings tab", "switch to settings", "settings", "preferences"],
                action="navigate.tab.settings",
                description="Navigate to Settings tab"
            ),
            VoiceCommand(
                name="go_to_api_keys",
                category=CommandCategory.NAVIGATION,
                keywords=["go to api keys", "open api keys", "show api keys",
                         "api keys tab", "api manager", "manage api keys"],
                action="navigate.tab.api_keys",
                description="Navigate to API Keys tab"
            ),
            VoiceCommand(
                name="go_to_code_generator",
                category=CommandCategory.NAVIGATION,
                keywords=["go to code generator", "open code generator", "code gen",
                         "code generator tab", "generate code"],
                action="navigate.tab.code_generator",
                description="Navigate to Code Generator tab"
            ),
            VoiceCommand(
                name="go_to_devices",
                category=CommandCategory.NAVIGATION,
                keywords=["go to devices", "open devices", "show devices",
                         "devices tab", "device manager", "connected devices"],
                action="navigate.tab.devices",
                description="Navigate to Device Manager tab"
            ),
            VoiceCommand(
                name="go_to_creative_studio",
                category=CommandCategory.NAVIGATION,
                keywords=["go to creative studio", "open creative studio", "creative studio",
                         "creative tab", "map creator", "terrain studio", "create maps"],
                action="navigate.tab.creative_studio",
                description="Navigate to Creative Studio tab"
            ),
        ]
        
        # ==================== CREATIVE STUDIO COMMANDS ====================
        creative_commands = [
            VoiceCommand(
                name="create_world_map",
                category=CommandCategory.SYSTEM,
                keywords=["create world map", "generate world", "make world map",
                         "build world", "new world map"],
                action="creative.voice.create",
                description="Create a new world map in Creative Studio",
                parameters={"prompt": "create world map"}
            ),
            VoiceCommand(
                name="create_dungeon",
                category=CommandCategory.SYSTEM,
                keywords=["create dungeon", "generate dungeon", "make dungeon",
                         "build dungeon", "new dungeon"],
                action="creative.voice.create",
                description="Create a new dungeon map in Creative Studio",
                parameters={"prompt": "create dungeon map"}
            ),
            VoiceCommand(
                name="create_city",
                category=CommandCategory.SYSTEM,
                keywords=["create city", "generate city", "make city map",
                         "build city", "new city"],
                action="creative.voice.create",
                description="Create a new city map in Creative Studio",
                parameters={"prompt": "create city map"}
            ),
            VoiceCommand(
                name="send_to_unity",
                category=CommandCategory.SYSTEM,
                keywords=["send to unity", "export to unity", "unity runtime",
                         "send terrain", "unity terrain", "push to unity"],
                action="creative.voice.unity",
                description="Send current terrain to Unity runtime"
            ),
        ]
        
        # ==================== UI CONTROL COMMANDS ====================
        ui_commands = [
            VoiceCommand(
                name="scroll_up",
                category=CommandCategory.UI_CONTROL,
                keywords=["scroll up", "go up", "page up", "up"],
                action="ui.scroll.up",
                description="Scroll the current view up"
            ),
            VoiceCommand(
                name="scroll_down",
                category=CommandCategory.UI_CONTROL,
                keywords=["scroll down", "go down", "page down", "down"],
                action="ui.scroll.down",
                description="Scroll the current view down"
            ),
            VoiceCommand(
                name="scroll_top",
                category=CommandCategory.UI_CONTROL,
                keywords=["scroll to top", "go to top", "top of page", "beginning"],
                action="ui.scroll.top",
                description="Scroll to the top of the current view"
            ),
            VoiceCommand(
                name="scroll_bottom",
                category=CommandCategory.UI_CONTROL,
                keywords=["scroll to bottom", "go to bottom", "bottom of page", "end"],
                action="ui.scroll.bottom",
                description="Scroll to the bottom of the current view"
            ),
            VoiceCommand(
                name="refresh",
                category=CommandCategory.UI_CONTROL,
                keywords=["refresh", "reload", "update", "sync"],
                action="ui.refresh",
                description="Refresh the current view"
            ),
            VoiceCommand(
                name="fullscreen",
                category=CommandCategory.UI_CONTROL,
                keywords=["fullscreen", "full screen", "maximize", "expand"],
                action="ui.fullscreen",
                description="Toggle fullscreen mode"
            ),
            VoiceCommand(
                name="minimize",
                category=CommandCategory.UI_CONTROL,
                keywords=["minimize", "hide window", "minimize window"],
                action="ui.minimize",
                description="Minimize the window"
            ),
            VoiceCommand(
                name="zoom_in",
                category=CommandCategory.UI_CONTROL,
                keywords=["zoom in", "make bigger", "increase size", "enlarge"],
                action="ui.zoom.in",
                description="Zoom in on the current view"
            ),
            VoiceCommand(
                name="zoom_out",
                category=CommandCategory.UI_CONTROL,
                keywords=["zoom out", "make smaller", "decrease size", "shrink"],
                action="ui.zoom.out",
                description="Zoom out on the current view"
            ),
            VoiceCommand(
                name="toggle_dark_mode",
                category=CommandCategory.UI_CONTROL,
                keywords=["dark mode", "light mode", "toggle theme", "switch theme"],
                action="ui.theme.toggle",
                description="Toggle between dark and light mode"
            ),
        ]
        
        # ==================== TRADING COMMANDS ====================
        trading_commands = [
            VoiceCommand(
                name="place_buy_order",
                category=CommandCategory.TRADING,
                keywords=["buy", "place buy order", "purchase", "long"],
                action="trading.order.buy",
                description="Place a buy order",
                requires_confirmation=True
            ),
            VoiceCommand(
                name="place_sell_order",
                category=CommandCategory.TRADING,
                keywords=["sell", "place sell order", "short"],
                action="trading.order.sell",
                description="Place a sell order",
                requires_confirmation=True
            ),
            VoiceCommand(
                name="cancel_order",
                category=CommandCategory.TRADING,
                keywords=["cancel order", "cancel trade", "abort order"],
                action="trading.order.cancel",
                description="Cancel an open order",
                requires_confirmation=True
            ),
            VoiceCommand(
                name="show_portfolio",
                category=CommandCategory.TRADING,
                keywords=["show portfolio", "my portfolio", "view holdings",
                         "what do i own", "my positions"],
                action="trading.portfolio.show",
                description="Show current portfolio"
            ),
            VoiceCommand(
                name="show_open_orders",
                category=CommandCategory.TRADING,
                keywords=["show orders", "open orders", "pending orders",
                         "my orders", "view orders"],
                action="trading.orders.show",
                description="Show open orders"
            ),
            VoiceCommand(
                name="show_market_data",
                category=CommandCategory.TRADING,
                keywords=["market data", "show market", "price of", "what is the price"],
                action="trading.market.show",
                description="Show market data"
            ),
            VoiceCommand(
                name="start_copy_trading",
                category=CommandCategory.TRADING,
                keywords=["copy trading", "start copy trading", "follow trader"],
                action="trading.copy.start",
                description="Start copy trading"
            ),
            VoiceCommand(
                name="whale_tracking",
                category=CommandCategory.TRADING,
                keywords=["whale tracking", "track whales", "whale alerts",
                         "big transactions"],
                action="trading.whale.track",
                description="Enable whale tracking"
            ),
        ]
        
        # ==================== MINING COMMANDS ====================
        mining_commands = [
            VoiceCommand(
                name="start_mining",
                category=CommandCategory.MINING,
                keywords=["start mining", "begin mining", "mine", "start miner"],
                action="mining.start",
                description="Start mining"
            ),
            VoiceCommand(
                name="stop_mining",
                category=CommandCategory.MINING,
                keywords=["stop mining", "stop miner", "pause mining", "halt mining"],
                action="mining.stop",
                description="Stop mining"
            ),
            VoiceCommand(
                name="mine_bitcoin",
                category=CommandCategory.MINING,
                keywords=["mine bitcoin", "mine btc", "bitcoin mining"],
                action="mining.coin.bitcoin",
                description="Start mining Bitcoin"
            ),
            VoiceCommand(
                name="mine_ethereum",
                category=CommandCategory.MINING,
                keywords=["mine ethereum", "mine eth", "ethereum mining"],
                action="mining.coin.ethereum",
                description="Start mining Ethereum"
            ),
            VoiceCommand(
                name="mine_monero",
                category=CommandCategory.MINING,
                keywords=["mine monero", "mine xmr", "monero mining"],
                action="mining.coin.monero",
                description="Start mining Monero"
            ),
            VoiceCommand(
                name="show_hashrate",
                category=CommandCategory.MINING,
                keywords=["show hashrate", "my hashrate", "mining speed",
                         "hash rate", "mining performance"],
                action="mining.hashrate.show",
                description="Show current hashrate"
            ),
            VoiceCommand(
                name="show_mining_stats",
                category=CommandCategory.MINING,
                keywords=["mining stats", "mining statistics", "mining status",
                         "mining earnings", "mining rewards"],
                action="mining.stats.show",
                description="Show mining statistics"
            ),
            VoiceCommand(
                name="quantum_mining",
                category=CommandCategory.MINING,
                keywords=["quantum mining", "start quantum", "quantum mode"],
                action="mining.quantum.start",
                description="Start quantum mining mode"
            ),
        ]
        
        # ==================== WALLET COMMANDS ====================
        wallet_commands = [
            VoiceCommand(
                name="show_balance",
                category=CommandCategory.WALLET,
                keywords=["show balance", "my balance", "check balance",
                         "how much do i have", "wallet balance"],
                action="wallet.balance.show",
                description="Show wallet balance"
            ),
            VoiceCommand(
                name="send_crypto",
                category=CommandCategory.WALLET,
                keywords=["send crypto", "transfer", "send coins", "send tokens"],
                action="wallet.send",
                description="Send cryptocurrency",
                requires_confirmation=True
            ),
            VoiceCommand(
                name="receive_crypto",
                category=CommandCategory.WALLET,
                keywords=["receive crypto", "my address", "wallet address",
                         "deposit address", "receive"],
                action="wallet.receive",
                description="Show receive address"
            ),
            VoiceCommand(
                name="show_transactions",
                category=CommandCategory.WALLET,
                keywords=["show transactions", "transaction history", "my transactions",
                         "recent transactions"],
                action="wallet.transactions.show",
                description="Show transaction history"
            ),
            VoiceCommand(
                name="create_wallet",
                category=CommandCategory.WALLET,
                keywords=["create wallet", "new wallet", "generate wallet"],
                action="wallet.create",
                description="Create a new wallet"
            ),
            VoiceCommand(
                name="import_wallet",
                category=CommandCategory.WALLET,
                keywords=["import wallet", "restore wallet", "recover wallet"],
                action="wallet.import",
                description="Import existing wallet"
            ),
        ]
        
        # ==================== AI COMMANDS ====================
        ai_commands = [
            VoiceCommand(
                name="ask_thoth",
                category=CommandCategory.AI,
                keywords=["ask thoth", "hey thoth", "thoth", "ask ai",
                         "ask kingdom ai", "question for ai"],
                action="ai.thoth.ask",
                description="Ask Thoth AI a question"
            ),
            VoiceCommand(
                name="switch_model",
                category=CommandCategory.AI,
                keywords=["switch model", "change model", "use model",
                         "different model"],
                action="ai.model.switch",
                description="Switch AI model"
            ),
            VoiceCommand(
                name="voice_mode",
                category=CommandCategory.AI,
                keywords=["voice mode", "enable voice", "start voice",
                         "voice input", "speak to ai"],
                action="ai.voice.enable",
                description="Enable voice input mode"
            ),
            VoiceCommand(
                name="text_mode",
                category=CommandCategory.AI,
                keywords=["text mode", "disable voice", "stop voice",
                         "type mode", "keyboard input"],
                action="ai.voice.disable",
                description="Disable voice input mode"
            ),
            VoiceCommand(
                name="clear_chat",
                category=CommandCategory.AI,
                keywords=["clear chat", "clear conversation", "new conversation",
                         "start fresh", "reset chat"],
                action="ai.chat.clear",
                description="Clear chat history"
            ),
            VoiceCommand(
                name="analyze_market",
                category=CommandCategory.AI,
                keywords=["analyze market", "market analysis", "ai analysis",
                         "predict market", "market prediction"],
                action="ai.analyze.market",
                description="AI market analysis"
            ),
        ]
        
        # ==================== VISUAL CANVAS COMMANDS ====================
        visual_commands = [
            VoiceCommand(
                name="open_visual_canvas",
                category=CommandCategory.VISUAL,
                keywords=["open visual", "show visual", "visual canvas",
                         "open canvas", "art canvas", "image generator"],
                action="visual.canvas.open",
                description="Open Visual Creation Canvas"
            ),
            VoiceCommand(
                name="close_visual_canvas",
                category=CommandCategory.VISUAL,
                keywords=["close visual", "hide visual", "close canvas"],
                action="visual.canvas.close",
                description="Close Visual Creation Canvas"
            ),
            VoiceCommand(
                name="generate_image",
                category=CommandCategory.VISUAL,
                keywords=["generate image", "create image", "draw", "paint"],
                action="visual.generate.image",
                description="Generate an image"
            ),
            VoiceCommand(
                name="plot_function",
                category=CommandCategory.VISUAL,
                keywords=["plot function", "graph function", "math plot",
                         "draw graph", "function graph"],
                action="visual.generate.function",
                description="Plot a mathematical function"
            ),
            VoiceCommand(
                name="draw_fractal",
                category=CommandCategory.VISUAL,
                keywords=["draw fractal", "mandelbrot", "fractal", "julia set"],
                action="visual.generate.fractal",
                description="Generate a fractal visualization"
            ),
            VoiceCommand(
                name="research_active_vision_frame",
                category=CommandCategory.VISUAL,
                keywords=[
                    "research this image", "research this frame", "search web with this image",
                    "analyze this image", "what do you see in this image", "research through vr view",
                    "research meta glasses image"
                ],
                action="vision.action.research.active_frame",
                description="Research using active webcam/VR/Meta vision frame"
            ),
            VoiceCommand(
                name="send_active_vision_to_creative",
                category=CommandCategory.VISUAL,
                keywords=[
                    "send this image to creative studio", "send image to creative studio",
                    "create from this image", "use this frame in creative studio",
                    "send vr image to creative studio", "send meta glasses image to creative studio"
                ],
                action="vision.action.creative.active_frame",
                description="Send active webcam/VR/Meta vision frame to Creative Studio"
            ),
        ]
        
        # ==================== SYSTEM COMMANDS ====================
        system_commands = [
            VoiceCommand(
                name="help",
                category=CommandCategory.SYSTEM,
                keywords=["help", "what can you do", "commands", "list commands",
                         "available commands", "how to use"],
                action="system.help",
                description="Show help and available commands"
            ),
            VoiceCommand(
                name="status",
                category=CommandCategory.SYSTEM,
                keywords=["system status", "status", "health check",
                         "system health", "connection status"],
                action="system.status",
                description="Show system status"
            ),
            VoiceCommand(
                name="comms_scan",
                category=CommandCategory.SYSTEM,
                keywords=["scan comms", "scan communications", "scan interfaces", "detect radios", "detect comms"],
                action="comms.scan",
                description="Scan communication interfaces (audio/video/radio)"
            ),
            VoiceCommand(
                name="comms_status",
                category=CommandCategory.SYSTEM,
                keywords=["comms status", "communications status", "radio status", "sonar status"],
                action="comms.status.request",
                description="Show communication subsystem status"
            ),
            VoiceCommand(
                name="comms_video_start",
                category=CommandCategory.SYSTEM,
                keywords=["start video stream", "start vision stream", "start camera stream", "enable vision"],
                action="comms.video.start",
                description="Start MJPEG vision streaming"
            ),
            VoiceCommand(
                name="comms_video_stop",
                category=CommandCategory.SYSTEM,
                keywords=["stop video stream", "stop vision stream", "stop camera stream", "disable vision"],
                action="comms.video.stop",
                description="Stop MJPEG vision streaming"
            ),
            VoiceCommand(
                name="comms_sonar_start",
                category=CommandCategory.SYSTEM,
                keywords=["start sonar", "start listening", "enable sonar", "start acoustic monitoring"],
                action="comms.sonar.start",
                description="Start passive sonar (microphone monitoring)"
            ),
            VoiceCommand(
                name="comms_sonar_stop",
                category=CommandCategory.SYSTEM,
                keywords=["stop sonar", "stop listening", "disable sonar", "stop acoustic monitoring"],
                action="comms.sonar.stop",
                description="Stop passive sonar (microphone monitoring)"
            ),
            VoiceCommand(
                name="emergency_stop",
                category=CommandCategory.SYSTEM,
                keywords=["emergency stop", "stop everything", "halt all",
                         "emergency", "panic"],
                action="system.emergency.stop",
                description="Emergency stop all operations",
                requires_confirmation=True
            ),
            VoiceCommand(
                name="save",
                category=CommandCategory.SYSTEM,
                keywords=["save", "save settings", "save config", "save all"],
                action="system.save",
                description="Save current state"
            ),
            VoiceCommand(
                name="exit",
                category=CommandCategory.SYSTEM,
                keywords=["exit", "quit", "close application", "shutdown"],
                action="system.exit",
                description="Exit application",
                requires_confirmation=True
            ),
            VoiceCommand(
                name="undo",
                category=CommandCategory.SYSTEM,
                keywords=["undo", "undo last", "revert", "go back"],
                action="system.undo",
                description="Undo last action"
            ),
            VoiceCommand(
                name="repeat",
                category=CommandCategory.SYSTEM,
                keywords=["repeat", "do it again", "repeat last", "again"],
                action="system.repeat",
                description="Repeat last command"
            ),
            # SOTA 2026: Biometric Security Commands
            VoiceCommand(
                name="enroll_face",
                category=CommandCategory.SYSTEM,
                keywords=["enroll my face", "learn my face", "register face",
                         "face enrollment", "add my face"],
                action="security.face.enroll",
                description="Enroll your face for recognition",
                requires_confirmation=True
            ),
            VoiceCommand(
                name="enroll_voice",
                category=CommandCategory.SYSTEM,
                keywords=["enroll my voice", "learn my voice", "register voice",
                         "voice enrollment", "add my voice"],
                action="security.voice.enroll",
                description="Enroll your voice for recognition",
                requires_confirmation=True
            ),
            VoiceCommand(
                name="verify_identity",
                category=CommandCategory.SYSTEM,
                keywords=["verify me", "who am i", "identify me", "check identity",
                         "verify identity", "authenticate me"],
                action="security.verify",
                description="Verify your identity"
            ),
            VoiceCommand(
                name="security_status",
                category=CommandCategory.SYSTEM,
                keywords=["security status", "who is logged in", "current user",
                         "authentication status", "biometric status"],
                action="security.status",
                description="Show security and authentication status"
            ),
            VoiceCommand(
                name="lock_system",
                category=CommandCategory.SYSTEM,
                keywords=["lock system", "lock kingdom", "secure system",
                         "enable security", "lock"],
                action="security.lock",
                description="Lock the system requiring re-authentication"
            ),
            VoiceCommand(
                name="list_users",
                category=CommandCategory.SYSTEM,
                keywords=["list users", "who has access", "authorized users",
                         "show users", "family members"],
                action="security.users.list",
                description="List authorized users"
            ),
        ]
        
        # Register all commands
        all_commands = (
            navigation_commands + creative_commands + ui_commands + trading_commands +
            mining_commands + wallet_commands + ai_commands +
            visual_commands + system_commands
        )
        
        for cmd in all_commands:
            self.register_command(cmd)
        
        logger.info(f"🎤 Registered {len(self.commands)} voice commands")
    
    def register_command(self, command: VoiceCommand):
        """Register a new voice command."""
        self.commands[command.name] = command
        logger.debug(f"Registered command: {command.name}")
    
    def unregister_command(self, name: str):
        """Unregister a voice command."""
        if name in self.commands:
            del self.commands[name]
            logger.debug(f"Unregistered command: {name}")
    
    def register_callback(self, action: str, callback: Callable):
        """Register a callback for a specific action."""
        if action not in self._callbacks:
            self._callbacks[action] = []
        self._callbacks[action].append(callback)
        logger.debug(f"Registered callback for action: {action}")
    
    def process_command(self, text: str) -> CommandResult:
        """
        Process a voice or text command.
        
        Args:
            text: The command text (from speech recognition or text input)
            
        Returns:
            CommandResult with success status and details
        """
        text_lower = text.lower().strip()
        logger.info(f"🎤 Processing command: '{text}'")
        
        # SOTA 2026: Check biometric authentication before executing commands
        auth_allowed, auth_message = self.check_biometric_auth()
        if not auth_allowed:
            logger.warning(f"🔐 Command blocked - authentication required: {auth_message}")
            return CommandResult(
                success=False,
                command=None,
                message=f"🔐 Access denied: {auth_message}. Please authenticate with face or voice."
            )
        
        # Try exact keyword matching first
        matched_command = self._match_keyword(text_lower)
        
        if matched_command:
            return self._execute_command(matched_command, text)
        
        # Try fuzzy matching
        matched_command = self._fuzzy_match(text_lower)
        
        if matched_command:
            return self._execute_command(matched_command, text)
        
        # Try LLM-based parsing if available
        if self.ollama_brain:
            matched_command = self._llm_parse_command(text)
            if matched_command:
                return self._execute_command(matched_command, text)
        
        # No match found
        logger.debug(f"🎤 No command matched for: '{text}'")
        return CommandResult(
            success=False,
            command=None,
            message=f"Command not recognized: '{text}'. Say 'help' for available commands."
        )
    
    def _match_keyword(self, text: str) -> Optional[VoiceCommand]:
        """Match command by exact keyword."""
        for cmd in self.commands.values():
            if not cmd.enabled:
                continue
            for keyword in cmd.keywords:
                if keyword in text:
                    return cmd
        return None
    
    def _fuzzy_match(self, text: str, threshold: float = 0.7) -> Optional[VoiceCommand]:
        """Fuzzy match command using similarity scoring."""
        best_match = None
        best_score = 0.0
        
        for cmd in self.commands.values():
            if not cmd.enabled:
                continue
            for keyword in cmd.keywords:
                score = self._similarity_score(text, keyword)
                if score > threshold and score > best_score:
                    best_score = score
                    best_match = cmd
        
        return best_match
    
    def _similarity_score(self, text1: str, text2: str) -> float:
        """Calculate similarity score between two strings."""
        # Simple word overlap scoring
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _llm_parse_command(self, text: str) -> Optional[VoiceCommand]:
        """Use LLM to parse and understand command intent.

        Path 1: self.ollama_brain.generate()
        Path 2: OllamaOrchestrator direct API call (fallback)
        """
        command_list = "\n".join([
            f"- {cmd.name}: {cmd.description} (keywords: {', '.join(cmd.keywords[:3])})"
            for cmd in list(self.commands.values())[:30]
        ])

        prompt = (
            f"You are a voice command parser. Given the user's input, determine which command they want to execute.\n\n"
            f"Available commands:\n{command_list}\n\n"
            f'User said: "{text}"\n\n'
            f'Respond with ONLY the command name (e.g., "go_to_trading" or "start_mining") or "none" if no command matches.\n'
            f"Command name:"
        )

        # Path 1: via ollama_brain
        try:
            if self.ollama_brain and hasattr(self.ollama_brain, 'generate'):
                response = self.ollama_brain.generate(prompt, max_tokens=50)
                if response:
                    command_name = response.strip().lower().replace('"', '').replace("'", "")
                    if command_name in self.commands:
                        return self.commands[command_name]
        except Exception as e:
            logger.debug("LLM parsing (ollama_brain) failed: %s", e)

        # Path 2: OllamaOrchestrator direct call
        try:
            from core.ollama_gateway import orchestrator as _orch, get_ollama_url
            import requests
            model = _orch.get_model_for_task("voice")
            url = get_ollama_url()
            resp = requests.post(
                f"{url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 30, "temperature": 0.05},
                      "keep_alive": -1},
                timeout=10,
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "").strip().lower().replace('"', '').replace("'", "")
                if raw in self.commands:
                    return self.commands[raw]
        except Exception as e:
            logger.debug("LLM parsing (orchestrator) failed: %s", e)

        return None
    
    def _execute_command(self, command: VoiceCommand, original_text: str) -> CommandResult:
        """Execute a matched command."""
        logger.info(f"🎤 Executing command: {command.name} -> {command.action}")
        
        # Extract parameters from text if needed
        params = self._extract_parameters(command, original_text)
        
        # Check if confirmation is required
        if command.requires_confirmation:
            # For now, proceed without confirmation - could add dialog
            logger.info(f"⚠️ Command {command.name} requires confirmation")
        
        # Execute via callbacks first
        executed = False
        if command.action in self._callbacks:
            for callback in self._callbacks[command.action]:
                try:
                    callback(command, params)
                    executed = True
                except Exception as e:
                    logger.error(f"Callback error for {command.action}: {e}")
        
        # Publish to event bus
        if self.event_bus:
            try:
                self.event_bus.publish(command.action, {
                    'command': command.name,
                    'original_text': original_text,
                    'parameters': params,
                    'timestamp': datetime.now().isoformat()
                })
                executed = True
            except Exception as e:
                logger.error(f"Event bus publish error: {e}")
        
        # Execute built-in actions
        if not executed:
            executed = self._execute_builtin(command, params)
        
        # Record in history
        result = CommandResult(
            success=executed,
            command=command,
            message=f"Executed: {command.description}" if executed else f"Failed to execute: {command.name}",
            data=params
        )
        
        self.command_history.append((datetime.now(), original_text, result))
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
        
        return result
    
    def _extract_parameters(self, command: VoiceCommand, text: str) -> Dict[str, Any]:
        """Extract parameters from command text."""
        params = {}
        text_lower = text.lower()
        
        # Extract coin/token names
        coins = ['bitcoin', 'btc', 'ethereum', 'eth', 'monero', 'xmr', 'solana', 'sol',
                'cardano', 'ada', 'dogecoin', 'doge', 'polygon', 'matic']
        for coin in coins:
            if coin in text_lower:
                params['coin'] = coin
                break
        
        # Extract numbers
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', text)
        if numbers:
            params['amount'] = float(numbers[0])
        
        # Extract addresses (hex)
        addresses = re.findall(r'0x[a-fA-F0-9]{40}', text)
        if addresses:
            params['address'] = addresses[0]
        
        return params
    
    def _execute_builtin(self, command: VoiceCommand, params: Dict) -> bool:
        """Execute built-in command actions."""
        if not self._main_window:
            return False
        
        action = command.action
        
        try:
            # Navigation commands
            if action.startswith("navigate.tab."):
                tab_name = action.replace("navigate.tab.", "")
                return self._navigate_to_tab(tab_name)
            
            # UI commands
            elif action == "ui.scroll.up":
                return self._scroll(direction="up")
            elif action == "ui.scroll.down":
                return self._scroll(direction="down")
            elif action == "ui.scroll.top":
                return self._scroll(direction="top")
            elif action == "ui.scroll.bottom":
                return self._scroll(direction="bottom")
            elif action == "ui.refresh":
                return self._refresh_current()
            elif action == "ui.fullscreen":
                return self._toggle_fullscreen()
            elif action == "ui.minimize":
                return self._minimize_window()
            
            # System commands
            elif action == "system.help":
                return self._show_help()
            elif action == "system.status":
                return self._show_status()
            
            return False
            
        except Exception as e:
            logger.error(f"Error executing builtin {action}: {e}")
            return False
    
    def _navigate_to_tab(self, tab_name: str) -> bool:
        """Navigate to a specific tab."""
        tab_mapping = {
            'dashboard': 0,
            'trading': 1,
            'blockchain': 2,
            'mining': 3,
            'thoth': 4,
            'code_generator': 5,
            'api_keys': 6,
            'vr': 7,
            'wallet': 8,
            'settings': 9,
            'devices': 10,
            'creative_studio': 11
        }
        
        if tab_name in tab_mapping and self._main_window:
            try:
                if hasattr(self._main_window, 'tab_widget'):
                    self._main_window.tab_widget.setCurrentIndex(tab_mapping[tab_name])
                    logger.info(f"🎤 Navigated to tab: {tab_name}")
                    return True
                elif hasattr(self._main_window, 'tabs'):
                    self._main_window.tabs.setCurrentIndex(tab_mapping[tab_name])
                    logger.info(f"🎤 Navigated to tab: {tab_name}")
                    return True
            except Exception as e:
                logger.error(f"Tab navigation error: {e}")
        return False
    
    def _scroll(self, direction: str) -> bool:
        """Scroll the current view."""
        try:
            from PyQt6.QtWidgets import QApplication, QScrollArea
            from PyQt6.QtCore import Qt
            
            # Get the focused widget
            widget = QApplication.focusWidget()
            if not widget:
                widget = self._main_window
            
            # Find scroll area
            scroll_area = None
            current = widget
            while current:
                if isinstance(current, QScrollArea):
                    scroll_area = current
                    break
                current = current.parent() if hasattr(current, 'parent') else None
            
            if scroll_area:
                scrollbar = scroll_area.verticalScrollBar()
                if direction == "up":
                    scrollbar.setValue(scrollbar.value() - 100)
                elif direction == "down":
                    scrollbar.setValue(scrollbar.value() + 100)
                elif direction == "top":
                    scrollbar.setValue(0)
                elif direction == "bottom":
                    scrollbar.setValue(scrollbar.maximum())
                return True
                
        except Exception as e:
            logger.error(f"Scroll error: {e}")
        return False
    
    def _refresh_current(self) -> bool:
        """Refresh the current tab/view."""
        if self._main_window and hasattr(self._main_window, 'tab_widget'):
            current = self._main_window.tab_widget.currentWidget()
            if hasattr(current, 'refresh'):
                current.refresh()
                return True
            elif hasattr(current, '_refresh'):
                current._refresh()
                return True
        return False
    
    def _toggle_fullscreen(self) -> bool:
        """Toggle fullscreen mode."""
        if self._main_window:
            if self._main_window.isFullScreen():
                self._main_window.showNormal()
            else:
                self._main_window.showFullScreen()
            return True
        return False
    
    def _minimize_window(self) -> bool:
        """Minimize the window."""
        if self._main_window:
            self._main_window.showMinimized()
            return True
        return False
    
    def _show_help(self) -> bool:
        """Show help information."""
        help_text = "Available command categories:\n"
        for category in CommandCategory:
            count = sum(1 for c in self.commands.values() if c.category == category)
            help_text += f"  - {category.value}: {count} commands\n"
        
        logger.info(f"🎤 Help:\n{help_text}")
        
        if self.event_bus:
            self.event_bus.publish('system.help.show', {
                'text': help_text,
                'commands': [c.name for c in self.commands.values()]
            })
        return True
    
    def _show_status(self) -> bool:
        """Show system status."""
        status = {
            'commands_registered': len(self.commands),
            'history_length': len(self.command_history),
            'ollama_connected': self.ollama_brain is not None,
            'event_bus_connected': self.event_bus is not None,
            'main_window_connected': self._main_window is not None
        }
        logger.info(f"🎤 Status: {status}")
        
        if self.event_bus:
            self.event_bus.publish('system.status.show', status)
        return True
    
    def get_commands_by_category(self, category: CommandCategory) -> List[VoiceCommand]:
        """Get all commands in a category."""
        return [c for c in self.commands.values() if c.category == category]
    
    def get_all_keywords(self) -> List[str]:
        """Get all registered keywords."""
        keywords = []
        for cmd in self.commands.values():
            keywords.extend(cmd.keywords)
        return keywords
    
    def _handle_voice_event(self, data: dict):
        """Handle voice command event from event bus."""
        text = data.get('text', '')
        if text:
            result = self.process_command(text)
            if self.event_bus:
                self.event_bus.publish('voice.command.result', {
                    'success': result.success,
                    'message': result.message,
                    'command': result.command.name if result.command else None
                })
    
    def _handle_text_event(self, data: dict):
        """Handle text command event from event bus."""
        text = data.get('text', '')
        if text:
            self.process_command(text)


# Singleton accessor
_voice_command_manager: Optional[VoiceCommandManager] = None

def get_voice_command_manager(event_bus=None, ollama_brain=None) -> VoiceCommandManager:
    """Get the singleton Voice Command Manager instance."""
    global _voice_command_manager
    if _voice_command_manager is None:
        _voice_command_manager = VoiceCommandManager(event_bus, ollama_brain)
    return _voice_command_manager
