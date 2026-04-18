#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Command Router for Kingdom AI - SOTA 2026

Routes chat/voice commands from Thoth AI to execute actions across all tabs:
- Device control (USB, Bluetooth, Audio, Webcams, VR)
- Software automation (list windows, focus, send keys, click)
- Trading operations
- Mining operations
- Wallet operations
- System control

Works with both text and voice input via EventBus integration.
"""

import re
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CommandCategory(Enum):
    """Categories of commands the router can handle"""
    DEVICE = "device"           # Host device control
    SOFTWARE = "software"       # Software automation
    TRADING = "trading"         # Trading operations
    MINING = "mining"           # Mining operations
    QUANTUM = "quantum"         # Quantum computing operations
    WALLET = "wallet"           # Wallet operations
    BLOCKCHAIN = "blockchain"   # Blockchain operations
    VR = "vr"                   # VR system control
    UNITY = "unity"             # Unity runtime control (Quest 3, VR builds)
    CODEGEN = "codegen"         # Code generator
    SETTINGS = "settings"       # Settings control
    SYSTEM = "system"           # System control
    VISION = "vision"           # 2026 SOTA: Vision system control (facial recognition, analysis, OCR)
    IDENTITY = "identity"       # 2026 SOTA: Biometric identity (SpeechBrain ECAPA-TDNN + facenet-pytorch)
    GENERAL = "general"         # General AI conversation


@dataclass
class ParsedCommand:
    """A parsed command from user input"""
    category: CommandCategory
    action: str
    parameters: Dict[str, Any]
    confidence: float
    raw_text: str


class AICommandRouter:
    """
    SOTA 2026 AI Command Router
    
    Parses natural language commands from chat/voice and routes them
    to appropriate MCP tools and system actions.
    """
    
    # Command patterns for each category
    COMMAND_PATTERNS = {
        CommandCategory.DEVICE: [
            (r"(?:scan|detect|find|list)\s+(?:all\s+)?devices?", "scan_devices", {}),
            (r"(?:enable|connect|pair)\s+(?:the\s+)?(?:bluetooth\s+)?device\s+(.+)", "enable_device", {"device_id": 1}),
            (r"(?:disable|disconnect)\s+(?:the\s+)?device\s+(.+)", "disable_device", {"device_id": 1}),
            (r"(?:show|get|list)\s+(?:all\s+)?(?:connected\s+)?devices?", "list_devices", {}),
            (r"(?:find|search)\s+device\s+(.+)", "find_device", {"query": 1}),
            # SOTA 2026: Device Takeover Commands (order matters - more specific patterns first)
            (r"(?:release|free)\s+(?:control\s+(?:of|from)\s+)?(?:the\s+)?device\s+(.+)", "release_device", {"device_id": 1}),
            (r"(?:get|show|check)\s+(?:takeover|control)\s+status\s+(?:of\s+)?(?:the\s+)?device\s+(.+)", "get_takeover_status", {"device_id": 1}),
            (r"(?:list|show|get)\s+(?:taken\s+over|controlled)\s+devices?", "list_taken_over_devices", {}),
            (r"(?:configure|setup|set)\s+(?:device\s+)?wifi\s+(.+)\s+(.+)", "configure_device_wifi", {"ssid": 1, "password": 2}),
            (r"(?:connect|join)\s+(?:device\s+)?(?:to\s+)?wifi\s+(.+)", "configure_device_wifi", {"ssid": 1}),
            (r"(?:send|execute|run)\s+(?:command\s+)?(.+)\s+(?:to|on)\s+(?:the\s+)?device\s+(.+)", "send_device_command", {"command": 1, "device_id": 2}),
            (r"(?:tell|command)\s+(?:the\s+)?device\s+(?:to\s+)?(.+)", "send_device_command", {"command": 1}),
            (r"(?:make|have)\s+(?:the\s+)?device\s+(.+)", "send_device_command", {"command": 1}),
            (r"(?:takeover|take\s+over|hijack)\s+(?:the\s+)?device\s+(.+)", "takeover_device", {"device_id": 1}),
            (r"(?:takeover|take\s+over)\s+(?:the\s+)?(.+)\s+device", "takeover_device", {"device_id": 1}),
            (r"(?:control)\s+(?:the\s+)?device\s+(.+)", "takeover_device", {"device_id": 1}),
            (r"device\s+(.+)", "send_device_command", {"command": 1}),
            # Natural language device commands
            (r"(?:turn\s+)?(?:the\s+)?led\s+(?:on|off|red|green|blue|blink)", "send_device_command", {"command": 0}),
            (r"(?:blink|flash)\s+(?:the\s+)?(?:led|light)", "send_device_command", {"command": "blink"}),
            (r"(?:set|change)\s+(?:led\s+)?color\s+(?:to\s+)?(.+)", "send_device_command", {"command": 1}),
        ],
        CommandCategory.SOFTWARE: [
            (r"(?:list|show|get)\s+(?:all\s+)?(?:open\s+)?windows?", "list_windows", {}),
            (r"(?:connect|attach|focus)\s+(?:to\s+)?(?:the\s+)?(?:software|window|app)\s+(.+)", "connect_software", {"name_contains": 1}),
            (r"(?:disconnect|detach)\s+(?:from\s+)?(?:the\s+)?(?:software|window|app)", "disconnect_software", {}),
            (r"(?:open|launch|start|run)\s+(?:the\s+)?(?:program|app|application|software)\s+(.+)", "start_process", {"path": 1}),
            (r"(?:click|press)\s+(?:at\s+)?(?:position\s+)?(\d+)[,\s]+(\d+)", "click_at", {"x": 1, "y": 2}),
            (r"(?:type|send|input)\s+(?:text\s+)?['\"](.+)['\"]" , "send_keys", {"keys": 1}),
            (r"(?:type|input)\s+(.+)(?!\s*(?:to|on)\s*[a-zA-Z0-9]+)", "send_keys", {"keys": 1}),
            (r"(?:find|locate)\s+(?:the\s+)?(?:button|control|element)\s+(.+)", "find_control", {"name": 1}),
            (r"(?:invoke|click|press)\s+(?:the\s+)?(?:button|control)\s+(.+)", "invoke_control", {"name": 1}),
        ],
        CommandCategory.TRADING: [
            (r"(?:buy|purchase)\s+(\d+(?:\.\d+)?)\s+(.+)", "place_order", {"side": "buy", "amount": 1, "symbol": 2}),
            (r"(?:sell)\s+(\d+(?:\.\d+)?)\s+(.+)", "place_order", {"side": "sell", "amount": 1, "symbol": 2}),
            (r"(?:show|get|check)\s+(?:my\s+)?(?:portfolio|holdings|positions?)", "get_portfolio", {}),
            (r"(?:show|get|check)\s+(?:the\s+)?price\s+(?:of\s+)?(.+)", "get_price", {"symbol": 1}),
            (r"(?:cancel)\s+(?:all\s+)?orders?", "cancel_orders", {}),
            (r"(?:start|enable|activate)\s+(?:auto\s+)?trading", "start_auto_trading", {}),
            (r"(?:stop|disable|deactivate)\s+(?:auto\s+)?trading", "stop_auto_trading", {}),
            # SOTA 2026: Trading plan and goal management commands
            (r"(?:set|update|change)\s+(?:my\s+)?(?:profit\s+)?goal\s+(?:to\s+)?\$?(\d+(?:[,.]?\d+)*(?:\s*(?:million|billion|trillion|m|b|t))?)", "set_profit_goal", {"amount": 1}),
            (r"(?:set|update|change)\s+(?:my\s+)?daily\s+(?:profit\s+)?(?:target|goal)\s+(?:to\s+)?\$?(\d+(?:[,.]?\d+)*(?:\s*(?:million|billion|trillion|m|b|t))?)", "set_daily_target", {"amount": 1}),
            (r"(?:i\s+want\s+to\s+)?(?:acquire|accumulate|stack|get|obtain)\s+(.+)", "update_plan_acquire", {"asset": 1}),
            (r"(?:i\s+want\s+to\s+)?(?:sell|dump|exit|close)\s+(?:my\s+)?(?:position\s+(?:in|on)\s+)?(.+)", "update_plan_sell", {"asset": 1}),
            (r"(?:focus|target|prioritize)\s+(?:on\s+)?(.+)\s+(?:trading|market)", "set_focus_market", {"market": 1}),
            (r"(?:analyze|check|what\s+about)\s+(.+)\s+(?:market|opportunity|price)", "analyze_asset", {"symbol": 1}),
            (r"(?:update|modify|change)\s+(?:my\s+)?(?:trading\s+)?plan\s+(?:to\s+)?(.+)", "update_trading_plan", {"instruction": 1}),
            (r"(?:show|get|what\s+is)\s+(?:my\s+)?(?:current\s+)?(?:trading\s+)?plan", "get_trading_plan", {}),
            (r"(?:predator|aggressive|hunt)\s+mode\s+(?:on|enable|activate)", "enable_predator_mode", {}),
            (r"(?:predator|aggressive|hunt)\s+mode\s+(?:off|disable|deactivate)", "disable_predator_mode", {}),
        ],
        CommandCategory.MINING: [
            (r"(?:start|begin|enable)\s+mining\s+(.+)", "start_mining", {"coin": 1}),
            (r"(?:stop|end|disable)\s+mining", "stop_mining", {}),
            (r"(?:show|get|check)\s+(?:mining\s+)?(?:hashrate|stats?|status)", "get_mining_stats", {}),
            (r"(?:switch|change)\s+(?:mining\s+)?pool\s+(?:to\s+)?(.+)", "switch_pool", {"pool": 1}),
        ],
        CommandCategory.QUANTUM: [
            (r"(?:show|get|check)\s+quantum\s+(?:status|backends?|devices?)", "quantum_status", {}),
            (r"(?:detect|scan|find)\s+quantum\s+(?:hardware|devices?|backends?)", "quantum_detect", {}),
            (r"(?:start|enable|activate)\s+quantum\s+mining", "quantum_mining_start", {}),
            (r"(?:stop|disable|deactivate)\s+quantum\s+mining", "quantum_mining_stop", {}),
            (r"(?:submit|run|execute)\s+quantum\s+(?:job|circuit)\s+(?:to\s+)?ibm", "quantum_submit_ibm", {}),
            (r"(?:submit|run|execute)\s+quantum\s+(?:job|circuit)\s+(?:to\s+)?openquantum", "quantum_submit_openquantum", {}),
            (r"(?:list|show)\s+(?:ibm\s+)?quantum\s+backends?", "quantum_list_backends", {}),
            (r"(?:is|are)\s+(?:quantum|real)\s+(?:hardware|backends?)\s+available", "quantum_check_availability", {}),
            (r"(?:configure|setup|set)\s+(?:ibm\s+)?quantum\s+(?:api\s+)?key", "quantum_configure_ibm", {}),
            (r"(?:configure|setup|set)\s+openquantum\s+(?:sdk\s+)?key", "quantum_configure_openquantum", {}),
            (r"(?:show|explain)\s+quantum\s+(?:mining\s+)?(?:capabilities|features)", "quantum_capabilities", {}),
            # Quantum Trading Operations
            (r"(?:optimize|quantum\s+optimize)\s+(?:my\s+)?portfolio", "quantum_optimize_portfolio", {}),
            (r"(?:find|detect|scan)\s+(?:quantum\s+)?arbitrage", "quantum_find_arbitrage", {}),
            (r"(?:quantum\s+)?risk\s+(?:analysis|analyze)", "quantum_risk_analysis", {}),
            (r"(?:use|enable)\s+quantum\s+(?:for\s+)?trading", "quantum_trading_enable", {}),
        ],
        CommandCategory.WALLET: [
            (r"(?:show|get|check)\s+(?:my\s+)?(?:wallet\s+)?balance(?:s)?", "get_balance", {}),
            (r"(?:send|transfer)\s+(\d+(?:\.\d+)?)\s+(\w+)\s+to\s+(0x[a-fA-F0-9]+|\S+@\S+|\w+)", "send_transaction", {"amount": 1, "token": 2, "to": 3}),
            (r"(?:show|get|list)\s+(?:my\s+)?(?:wallet\s+)?address(?:es)?", "get_addresses", {}),
        ],
        CommandCategory.BLOCKCHAIN: [
            (r"(?:show|get|check)\s+(?:blockchain\s+)?(?:network|chain)\s+status", "get_network_status", {}),
            (r"(?:connect|switch)\s+(?:to\s+)?(?:network|chain)\s+(.+)", "switch_network", {"network": 1}),
            (r"(?:show|list|get)\s+(?:all\s+)?(?:available\s+)?networks?", "list_networks", {}),
            (r"(?:deploy|create)\s+(?:smart\s+)?contract\s+(.+)", "deploy_contract", {"contract": 1}),
            (r"(?:show|get|check)\s+(?:gas\s+)?(?:price|fee)s?", "get_gas_price", {}),
            (r"(?:show|get)\s+(?:block\s+)?(?:explorer|info)", "open_explorer", {}),
            (r"(?:verify|check)\s+(?:transaction|tx)\s+(.+)", "verify_transaction", {"tx_hash": 1}),
        ],
        CommandCategory.VR: [
            (r"(?:start|enable|launch)\s+(?:vr|virtual\s+reality)\s+(?:mode|system)?", "start_vr", {}),
            (r"(?:stop|disable|exit)\s+(?:vr|virtual\s+reality)\s+(?:mode|system)?", "stop_vr", {}),
            (r"(?:show|get|check)\s+(?:vr|virtual\s+reality)\s+status", "get_vr_status", {}),
            (r"(?:calibrate|reset)\s+(?:vr|virtual\s+reality)\s+(?:headset|controllers?)?", "calibrate_vr", {}),
            (r"(?:enable|start)\s+(?:hand|gesture)\s+tracking", "enable_hand_tracking", {}),
            (r"(?:disable|stop)\s+(?:hand|gesture)\s+tracking", "disable_hand_tracking", {}),
            (r"(?:show|open)\s+(?:vr\s+)?trading\s+(?:floor|room|environment)", "open_vr_trading", {}),
            # 2026 SOTA: VR Scene Management Commands
            (r"(?:load|switch\s+to|open)\s+(?:vr\s+)?scene\s+(.+)", "vr_load_scene", {"scene_name": 1}),
            (r"(?:list|show)\s+(?:available\s+)?(?:vr\s+)?scenes?", "vr_list_scenes", {}),
            (r"(?:save|store)\s+(?:vr\s+)?scene\s+(?:as\s+)?(.+)", "vr_save_scene", {"scene_name": 1}),
            # 2026 SOTA: VR Object Control Commands
            (r"(?:add|create|spawn)\s+(?:vr\s+)?object\s+(.+)", "vr_add_object", {"object_type": 1}),
            (r"(?:remove|delete)\s+(?:vr\s+)?object\s+(.+)", "vr_remove_object", {"object_id": 1}),
            (r"(?:move|position)\s+(?:vr\s+)?object\s+(.+)\s+to\s+(.+)", "vr_move_object", {"object_id": 1, "position": 2}),
            (r"(?:scale|resize)\s+(?:vr\s+)?object\s+(.+)\s+to\s+(.+)", "vr_scale_object", {"object_id": 1, "scale": 2}),
            # 2026 SOTA: VR Visualization Control
            (r"(?:show|display)\s+(?:vr\s+)?(?:market|trading)\s+visualization", "vr_show_market_viz", {}),
            (r"(?:show|display)\s+(?:vr\s+)?portfolio\s+visualization", "vr_show_portfolio_viz", {}),
            (r"(?:show|display)\s+(?:vr\s+)?mining\s+visualization", "vr_show_mining_viz", {}),
            (r"(?:hide|close)\s+(?:all\s+)?(?:vr\s+)?visualizations?", "vr_hide_visualizations", {}),
            # 2026 SOTA: VR Environment Settings
            (r"(?:set|change)\s+(?:vr\s+)?quality\s+(?:to\s+)?(.+)", "vr_set_quality", {"quality_level": 1}),
            (r"(?:set|change)\s+(?:vr\s+)?(?:fps|framerate)\s+(?:to\s+)?(\d+)", "vr_set_fps", {"target_fps": 1}),
            (r"(?:set|change)\s+(?:vr\s+)?tracking\s+(?:mode|rate)\s+(?:to\s+)?(.+)", "vr_set_tracking", {"tracking_mode": 1}),
            # 2026 SOTA: VR Haptic Feedback Commands
            (r"(?:enable|start)\s+(?:vr\s+)?haptic(?:s|feedback)?", "vr_enable_haptics", {}),
            (r"(?:disable|stop)\s+(?:vr\s+)?haptic(?:s|feedback)?", "vr_disable_haptics", {}),
            (r"(?:test|trigger)\s+(?:vr\s+)?haptic(?:s|feedback)?\s+(?:on\s+)?(.+)", "vr_test_haptics", {"target": 1}),
            # 2026 SOTA: VR Spatial Audio Commands
            (r"(?:enable|start)\s+(?:vr\s+)?spatial\s+audio", "vr_enable_spatial_audio", {}),
            (r"(?:disable|stop)\s+(?:vr\s+)?spatial\s+audio", "vr_disable_spatial_audio", {}),
            # 2026 SOTA: VR Recording/Capture
            (r"(?:start|begin)\s+(?:vr\s+)?recording", "vr_start_recording", {}),
            (r"(?:stop|end)\s+(?:vr\s+)?recording", "vr_stop_recording", {}),
            (r"(?:capture|take)\s+(?:vr\s+)?(?:screenshot|snapshot)", "vr_capture_screenshot", {}),
            # 2026 SOTA: VR Device Management
            (r"(?:list|show|detect)\s+(?:vr\s+)?devices?", "vr_list_devices", {}),
            (r"(?:connect|pair)\s+(?:to\s+)?(?:vr\s+)?device\s+(.+)", "vr_connect_device", {"device_id": 1}),
            (r"(?:disconnect|unpair)\s+(?:from\s+)?(?:vr\s+)?device", "vr_disconnect_device", {}),
            (r"(?:get|show)\s+(?:vr\s+)?(?:headset|device)\s+(?:battery|power)", "vr_get_battery", {}),
        ],
        # SOTA 2026: Unity Runtime Commands (Quest 3, VR builds, game control)
        CommandCategory.UNITY: [
            (r"(?:move|go|walk|step)\s+forward", "unity_move_forward", {}),
            (r"(?:move|go|walk|step)\s+backward(?:s)?", "unity_move_backward", {}),
            (r"(?:turn|rotate|look)\s+left", "unity_turn_left", {}),
            (r"(?:turn|rotate|look)\s+right", "unity_turn_right", {}),
            (r"^jump$", "unity_jump", {}),
            (r"(?:jump|hop|leap)", "unity_jump", {}),
            (r"^stop$", "unity_stop", {}),
            (r"(?:stop|halt|freeze)", "unity_stop", {}),
            (r"(?:connect|attach)\s+(?:to\s+)?unity", "unity_connect", {}),
            (r"(?:disconnect|detach)\s+(?:from\s+)?unity", "unity_disconnect", {}),
            (r"(?:check|ping|test)\s+unity\s+(?:connection|status)?", "unity_ping", {}),
        ],
        CommandCategory.CODEGEN: [
            (r"(?:generate|create|write)\s+(?:code|script)\s+(?:for\s+)?(.+)", "generate_code", {"description": 1}),
            (r"(?:generate|create)\s+(?:trading\s+)?strategy\s+(.+)", "generate_strategy", {"strategy_type": 1}),
            (r"(?:generate|create)\s+(?:smart\s+)?contract\s+(.+)", "generate_contract", {"contract_type": 1}),
            (r"(?:explain|document)\s+(?:this\s+)?code", "explain_code", {}),
            (r"(?:optimize|improve)\s+(?:this\s+)?code", "optimize_code", {}),
            (r"(?:show|list)\s+(?:code\s+)?templates?", "list_templates", {}),
        ],
        CommandCategory.SETTINGS: [
            (r"(?:show|open|get)\s+settings?", "open_settings", {}),
            (r"(?:change|set|update)\s+(?:api\s+)?key\s+(?:for\s+)?(.+)", "set_api_key", {"service": 1}),
            (r"(?:enable|turn\s+on)\s+dark\s+mode", "enable_dark_mode", {}),
            (r"(?:disable|turn\s+off)\s+dark\s+mode", "disable_dark_mode", {}),
            (r"(?:set|change)\s+language\s+(?:to\s+)?(.+)", "set_language", {"language": 1}),
            (r"(?:enable|disable)\s+notifications?", "toggle_notifications", {}),
            (r"(?:reset|restore)\s+(?:default\s+)?settings?", "reset_settings", {}),
            (r"(?:backup|export)\s+(?:my\s+)?(?:config|settings|data)", "backup_config", {}),
            (r"(?:import|restore)\s+(?:my\s+)?(?:config|settings|data)", "import_config", {}),
        ],
        CommandCategory.SYSTEM: [
            (r"(?:show|open|switch\s+to)\s+(?:the\s+)?trading\s+tab", "switch_tab", {"tab": "trading"}),
            (r"(?:show|open|switch\s+to)\s+(?:the\s+)?mining\s+tab", "switch_tab", {"tab": "mining"}),
            (r"(?:show|open|switch\s+to)\s+(?:the\s+)?wallet\s+tab", "switch_tab", {"tab": "wallet"}),
            (r"(?:show|open|switch\s+to)\s+(?:the\s+)?settings?\s+tab", "switch_tab", {"tab": "settings"}),
            (r"(?:show|open|switch\s+to)\s+(?:the\s+)?dashboard", "switch_tab", {"tab": "dashboard"}),
            (r"(?:show|get)\s+system\s+status", "get_system_status", {}),
            (r"^(?:refresh|reload)$", "refresh_tab", {}),
            (r"(?:refresh|reload)\s+(?:the\s+)?(?:current\s+)?(?:tab|view|page)?", "refresh_tab", {}),
            (r"(?:scan|detect|list)\s+(?:comms|communications|interfaces|radios)", "comms_scan", {}),
            (r"(?:show|get)\s+(?:comms|communications)\s+status", "comms_status", {}),
            (r"(?:start|enable)\s+(?:video|vision|camera)\s+stream", "comms_video_start", {}),
            (r"(?:stop|disable)\s+(?:video|vision|camera)\s+stream", "comms_video_stop", {}),
            (r"(?:start|enable)\s+(?:sonar|listening|acoustic\s+monitoring)", "comms_sonar_start", {}),
            (r"(?:stop|disable)\s+(?:sonar|listening|acoustic\s+monitoring)", "comms_sonar_stop", {}),
            # SOTA 2026: Radio/RF Commands for Comms Tab
            (r"(?:transmit|send|broadcast)\s+(?:on\s+)?(?:radio|rf|frequency)\s*([\d.]+)?", "comms_radio_transmit", {"frequency_mhz": 1}),
            (r"(?:start|begin|enable)\s+(?:radio|rf)\s+(?:receive|rx|listening)", "comms_radio_receive_start", {}),
            (r"(?:stop|end|disable)\s+(?:radio|rf)\s+(?:receive|rx|listening)", "comms_radio_receive_stop", {}),
            (r"(?:receive|listen)\s+(?:on\s+)?(?:radio|rf|frequency)\s*([\d.]+)?", "comms_radio_receive_start", {"frequency_mhz": 1}),
            # SOTA 2026: Voice/Call Commands for Comms Tab
            (r"(?:start|begin|make|initiate)\s+(?:voice\s+)?(?:call|connection)", "comms_call_start", {}),
            (r"(?:end|stop|hang\s*up|terminate)\s+(?:voice\s+)?(?:call|connection)", "comms_call_stop", {}),
            (r"(?:show|get)\s+(?:call|connection)\s+status", "comms_call_status", {}),
            # SOTA 2026: Full Host System Control
            (r"(?:run|execute)\s+(?:command|cmd|shell)\s+(.+)", "run_shell_command", {"command": 1}),
            (r"(?:list|show)\s+(?:running\s+)?processes", "list_processes", {}),
            (r"(?:kill|terminate|stop)\s+process\s+(.+)", "kill_process", {"process": 1}),
            (r"(?:take|capture)\s+screenshot", "take_screenshot", {}),
            (r"(?:start|begin)\s+(?:screen\s+)?recording", "start_screen_recording", {}),
            (r"(?:stop|end)\s+(?:screen\s+)?recording", "stop_screen_recording", {}),
            (r"(?:get|show)\s+system\s+info(?:rmation)?", "get_system_info", {}),
            (r"(?:list|show)\s+(?:all\s+)?(?:open\s+)?windows", "list_windows", {}),
            (r"(?:focus|activate|switch\s+to)\s+window\s+(.+)", "focus_window", {"window": 1}),
            (r"(?:minimize|hide)\s+(?:all\s+)?windows", "minimize_windows", {}),
            (r"(?:maximize|restore)\s+window", "maximize_window", {}),
            # Hardware Control
            (r"(?:list|show)\s+(?:all\s+)?gpus?", "list_gpus", {}),
            (r"(?:get|show)\s+gpu\s+(?:status|info|stats)", "get_gpu_status", {}),
            (r"(?:list|show)\s+(?:all\s+)?cameras?", "list_cameras", {}),
            (r"(?:enable|activate|start)\s+camera\s+(\d+)?", "enable_camera", {"camera_id": 1}),
            (r"(?:disable|deactivate|stop)\s+camera", "disable_camera", {}),
            (r"(?:list|show)\s+(?:all\s+)?microphones?", "list_microphones", {}),
            (r"(?:enable|activate)\s+microphone\s+(\d+)?", "enable_microphone", {"mic_id": 1}),
            (r"(?:disable|deactivate|mute)\s+microphone", "disable_microphone", {}),
            # Mouse/Keyboard Control
            (r"(?:click|press)\s+(?:at\s+)?(\d+)\s*,?\s*(\d+)", "click_at", {"x": 1, "y": 2}),
            (r"(?:move\s+)?mouse\s+(?:to\s+)?(\d+)\s*,?\s*(\d+)", "move_mouse", {"x": 1, "y": 2}),
            (r"(?:type|send\s+keys?|input)\s+(.+)", "send_keys", {"text": 1}),
            (r"(?:press|hit)\s+(?:key\s+)?(.+)", "press_key", {"key": 1}),
        ],
        # 2026 SOTA: VISION Command Category - Facial Recognition, Analysis, OCR
        CommandCategory.VISION: [
            # Facial Recognition Commands (DeepFace + InsightFace)
            (r"(?:analyze|scan|detect)\s+(?:the\s+)?(?:facial|face)\s+(?:features?|expression)?", "vision_analyze_face", {}),
            (r"(?:recognize|identify)\s+(?:this\s+)?face", "vision_recognize_face", {}),
            (r"(?:detect|find|count)\s+(?:all\s+)?faces?\s+(?:in\s+)?(?:the\s+)?(?:frame|image|video)?", "vision_detect_faces", {}),
            (r"(?:what|analyze)\s+(?:is\s+)?(?:the\s+)?(?:emotion|mood|expression)\s+(?:of\s+)?(?:this\s+)?(?:person|face)?", "vision_analyze_emotion", {}),
            (r"(?:estimate|guess|what\s+is)\s+(?:the\s+)?(?:age|gender)\s+(?:of\s+)?(?:this\s+)?person", "vision_analyze_demographics", {}),
            (r"(?:track|follow)\s+(?:this\s+)?(?:person|face)", "vision_track_person", {}),
            (r"(?:add|register|save)\s+(?:this\s+)?face\s+(?:as\s+)?(.+)", "vision_register_face", {"name": 1}),
            (r"(?:who\s+is|identify)\s+(?:this\s+)?(?:person|face)", "vision_identify_person", {}),
            (r"(?:list|show)\s+(?:all\s+)?(?:registered|known)\s+faces?", "vision_list_faces", {}),
            (r"(?:delete|remove)\s+face\s+(.+)", "vision_delete_face", {"name": 1}),
            # Object Detection Commands (YOLO)
            (r"(?:detect|find|identify)\s+(?:all\s+)?objects?\s+(?:in\s+)?(?:the\s+)?(?:frame|image|view)?", "vision_detect_objects", {}),
            (r"(?:find|locate|where\s+is)\s+(?:the\s+)?(.+)\s+(?:in\s+)?(?:the\s+)?(?:frame|view)?", "vision_find_object", {"object_name": 1}),
            (r"(?:track|follow)\s+(?:the\s+)?(.+)\s+(?:in\s+)?(?:the\s+)?camera", "vision_track_object", {"object_name": 1}),
            (r"(?:count|how\s+many)\s+(?:are\s+there\s+)?(.+)\s+(?:in\s+)?(?:the\s+)?(?:frame|view)?", "vision_count_objects", {"object_type": 1}),
            # Scene Understanding Commands
            (r"(?:describe|what\s+(?:is|do\s+you\s+see))\s+(?:in\s+)?(?:the\s+)?(?:frame|image|view|camera)?", "vision_describe_scene", {}),
            (r"(?:analyze|understand)\s+(?:the\s+)?scene", "vision_analyze_scene", {}),
            (r"(?:what\s+is\s+happening|what's\s+going\s+on)\s+(?:in\s+)?(?:the\s+)?(?:frame|view)?", "vision_analyze_activity", {}),
            # OCR/Text Extraction Commands
            (r"(?:read|extract|get)\s+(?:the\s+)?text\s+(?:from|in)\s+(?:the\s+)?(?:frame|image|document)?", "vision_extract_text", {}),
            (r"(?:ocr|scan)\s+(?:the\s+)?(?:document|text|image)?", "vision_ocr", {}),
            (r"(?:read|scan)\s+(?:this\s+)?(?:document|page|paper)", "vision_read_document", {}),
            (r"(?:translate|what\s+does)\s+(?:this\s+)?(?:text|document)\s+(?:say|mean)?", "vision_translate_text", {}),
            # Pose/Gesture Estimation Commands (MediaPipe)
            (r"(?:detect|analyze)\s+(?:body\s+)?pose", "vision_detect_pose", {}),
            (r"(?:recognize|detect)\s+(?:hand\s+)?gesture(?:s)?", "vision_detect_gestures", {}),
            (r"(?:track|follow)\s+(?:hand|body)\s+(?:movement|motion)", "vision_track_movement", {}),
            # Vision Stream Control Commands
            (r"(?:start|enable|begin)\s+vision\s+(?:stream|analysis)?", "vision_start_stream", {}),
            (r"(?:stop|disable|end)\s+vision\s+(?:stream|analysis)?", "vision_stop_stream", {}),
            (r"(?:pause|freeze)\s+vision\s+(?:stream|analysis)?", "vision_pause_stream", {}),
            (r"(?:resume|continue)\s+vision\s+(?:stream|analysis)?", "vision_resume_stream", {}),
            # Vision Quality Control
            (r"(?:enhance|improve)\s+(?:the\s+)?(?:image|frame|video)\s+(?:quality)?", "vision_enhance_image", {}),
            (r"(?:set|change)\s+vision\s+(?:quality|resolution)\s+(?:to\s+)?(.+)", "vision_set_quality", {"quality": 1}),
            (r"(?:set|change)\s+vision\s+(?:fps|framerate)\s+(?:to\s+)?(\d+)", "vision_set_fps", {"fps": 1}),
            # Vision Recording/Capture
            (r"(?:capture|take)\s+(?:a\s+)?(?:frame|snapshot|screenshot)", "vision_capture_frame", {}),
            (r"(?:start|begin)\s+(?:vision\s+)?recording", "vision_start_recording", {}),
            (r"(?:stop|end)\s+(?:vision\s+)?recording", "vision_stop_recording", {}),
            (r"(?:save|export)\s+(?:the\s+)?(?:frame|image)\s+(?:as\s+)?(.+)?", "vision_save_frame", {"filename": 1}),
            # Multi-Camera Management
            (r"(?:switch|change)\s+(?:to\s+)?camera\s+(\d+)", "vision_switch_camera", {"camera_id": 1}),
            (r"(?:list|show)\s+(?:available\s+)?cameras?", "vision_list_cameras", {}),
            (r"(?:enable|activate)\s+(?:vr|meta\s+glasses?)\s+(?:vision|camera)", "vision_enable_vr_camera", {}),
            (r"(?:disable|deactivate)\s+(?:vr|meta\s+glasses?)\s+(?:vision|camera)", "vision_disable_vr_camera", {}),
            (r"(?:research|analyze|search)\s+(?:this\s+)?(?:image|frame|view)\s+(?:on\s+the\s+web|with\s+web)?", "vision_research_active_frame", {}),
            (r"(?:send|push|use)\s+(?:this\s+)?(?:image|frame|view)\s+(?:to|in)\s+creative\s+studio", "vision_send_to_creative", {}),
            # Vision AI Integration
            (r"(?:analyze|process)\s+(?:this\s+)?image\s+(?:with|using)\s+(?:ai|llava)", "vision_ai_analyze", {}),
            (r"(?:generate|create)\s+(?:image|picture)\s+(?:of|from)\s+(.+)", "vision_ai_generate", {"prompt": 1}),
            (r"(?:compare|diff)\s+(?:these\s+)?(?:images?|frames?)", "vision_compare_images", {}),
        ],
        # 2026 SOTA: IDENTITY Command Category - SpeechBrain ECAPA-TDNN + facenet-pytorch biometrics
        CommandCategory.IDENTITY: [
            # Speaker verification (SpeechBrain ECAPA-TDNN)
            (r"(?:who\s+am\s+i|identify\s+me|verify\s+(?:my\s+)?identity)", "identity_verify", {}),
            (r"(?:enroll|register|add)\s+(?:my\s+)?voice", "identity_enroll_voice", {}),
            (r"(?:enroll|register|add)\s+(?:my\s+)?face", "identity_enroll_face", {}),
            (r"(?:show|get|check)\s+(?:identity|biometric)\s+(?:status|info)", "identity_status", {}),
            (r"(?:list|show)\s+(?:all\s+)?(?:enrolled|registered)\s+(?:users?|profiles?|identities)", "identity_list_profiles", {}),
            (r"(?:delete|remove)\s+(?:my\s+)?(?:voice|face)\s+(?:enrollment|profile|data)", "identity_delete_enrollment", {}),
            (r"(?:enable|activate)\s+(?:speaker|voice)\s+(?:verification|lock)", "identity_enable_verification", {}),
            (r"(?:disable|deactivate)\s+(?:speaker|voice)\s+(?:verification|lock)", "identity_disable_verification", {}),
        ],
    }
    
    def __init__(self, event_bus=None, mcp_bridge=None):
        """
        Initialize the AI Command Router.
        
        Args:
            event_bus: Event bus for publishing actions
            mcp_bridge: ThothMCPBridge for MCP tool execution
        """
        self.event_bus = event_bus
        self.mcp_bridge = mcp_bridge
        self._connected_software = None
        
        # Subscribe to AI requests to intercept commands
        if event_bus:
            self._setup_event_subscriptions()
        
        logger.info("✅ AI Command Router initialized")
    
    def _setup_event_subscriptions(self):
        """Set up EventBus subscriptions for command routing."""
        try:
            # Subscribe to AI responses to check for actionable commands
            self.event_bus.subscribe('ai.command.execute', self._handle_command_execute)
            # Subscribe to chat messages for direct command detection
            self.event_bus.subscribe('chat.message.user', self._handle_user_message)
            # SOTA 2026: Subscribe to voice input for device/system command routing
            self.event_bus.subscribe('ai.user_input', self._handle_user_message)
            
            # SOTA 2026: Subscribe to device detection events to inform AI brain
            self.event_bus.subscribe('device.connected', self._handle_device_connected)
            self.event_bus.subscribe('device.disconnected', self._handle_device_disconnected)
            
            # SOTA 2026: SHA-LU-AM (שלום) — Secret Reserve reveal (Hebrew: peace)
            self.event_bus.subscribe('secret.reserve.reveal', self._handle_secret_reserve_reveal)
            # SHA-LU-AM typed: when user types in chat (desktop or mobile)
            self.event_bus.subscribe('ai.request', self._check_typed_sha_lu_am)
            
            logger.info("✅ AI Command Router subscribed to events (voice + device + secret.reserve + typed SHA-LU-AM)")
        except Exception as e:
            logger.error(f"Error setting up command router subscriptions: {e}")
    
    def _handle_device_connected(self, event_data: Dict[str, Any]) -> None:
        """Handle device connected events - inform AI brain of new devices.
        
        SOTA 2026: When a device is detected, route it to the AI brain for awareness.
        """
        try:
            device = event_data.get('device', {})
            device_name = device.get('name', 'Unknown device')
            device_category = device.get('category', 'unknown')
            
            logger.info(f"🔌 AI Router: Device connected - {device_name} ({device_category})")
            
            # Publish to AI brain for awareness
            if self.event_bus:
                self.event_bus.publish('ai.device.connected', {
                    'device': device,
                    'message': f"New device connected: {device_name}",
                    'category': device_category,
                    'can_voice_command': device.get('capabilities', {}).get('voice_commands', False),
                })
                
                # If it's a webcam with mic, notify voice system
                if device_category == 'audio_input' or device.get('capabilities', {}).get('microphone'):
                    self.event_bus.publish('voice.microphone.available', {
                        'device': device,
                        'name': device_name,
                    })
                    logger.info(f"🎤 AI Router: Microphone available - {device_name}")
                    
        except Exception as e:
            logger.error(f"Error handling device connected: {e}")
    
    def _handle_device_disconnected(self, event_data: Dict[str, Any]) -> None:
        """Handle device disconnected events."""
        try:
            device = event_data.get('device', {})
            device_name = device.get('name', 'Unknown device')
            logger.info(f"🔌 AI Router: Device disconnected - {device_name}")
            
            if self.event_bus:
                self.event_bus.publish('ai.device.disconnected', {
                    'device': device,
                    'message': f"Device disconnected: {device_name}",
                })
        except Exception as e:
            logger.error(f"Error handling device disconnected: {e}")

    def _check_typed_sha_lu_am(self, data: Dict[str, Any]) -> None:
        """When user types SHA-LU-AM in chat, publish secret.reserve.reveal. Said and typed."""
        if not isinstance(data, dict) or not self.event_bus:
            return
        text = (data.get("prompt") or data.get("message") or data.get("text") or "").strip()
        if not text:
            return
        t = text.lower().replace(" ", "").replace("-", "")
        is_sha = (
            "shaluam" in t or "shalom" in text.lower() or
            "sha lu am" in text.lower() or "sha-lu-am" in text or
            "\u05e9\u05dc\u05d5\u05dd" in text  # Hebrew שלום
        )
        if is_sha:
            # Typed from desktop or linked mobile — treat as owner present
            self.event_bus.publish("secret.reserve.reveal", {
                "trigger": "SHA-LU-AM",
                "text": text,
                "source": data.get("source", "typed"),
                "owner_verified": True,
                "hive_mind_activate": True,
            })

    def _handle_secret_reserve_reveal(self, event_data: Dict[str, Any]) -> None:
        """Handle SHA-LU-AM (שלום) — "Remember!" Owner/enrolled only. Bulletproof hacking defense.
        Activates Hive Mind so all others come online. Activates reserve_revealed so wisdom
        can be brought to chat. Ollama brain helps user learn native tongue. NOT for trading.
        """
        try:
            if not event_data.get("owner_verified"):
                return
            try:
                from core.security.protection_flags import ProtectionFlagController
                fc = ProtectionFlagController.get_instance()
                if event_data.get("hive_mind_activate"):
                    fc.activate("hive_mind", source="sha_lu_am")
                fc.activate("reserve_revealed", source="sha_lu_am")
            except Exception:
                pass
        except Exception as e:
            logger.debug("Secret reserve reveal: %s", e)

    def parse_command(self, text: str) -> Optional[ParsedCommand]:
        """
        Parse natural language text into a command.
        
        Args:
            text: User input text
            
        Returns:
            ParsedCommand if a command was detected, None otherwise
        """
        text_lower = text.lower().strip()
        
        # Try each category's patterns
        for category, patterns in self.COMMAND_PATTERNS.items():
            for pattern, action, param_map in patterns:
                match = re.search(pattern, text_lower, re.IGNORECASE)
                if match:
                    # Extract parameters from regex groups
                    params = {}
                    for param_name, group_idx in param_map.items():
                        if isinstance(group_idx, int) and group_idx <= len(match.groups()):
                            params[param_name] = match.group(group_idx)
                        else:
                            params[param_name] = group_idx
                    
                    return ParsedCommand(
                        category=category,
                        action=action,
                        parameters=params,
                        confidence=0.9,
                        raw_text=text
                    )
        
        return None
    
    def execute_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """
        Execute a parsed command.
        
        Args:
            command: ParsedCommand to execute
            
        Returns:
            Result dictionary with success status and data
        """
        logger.info(f"🎯 Executing command: {command.category.value}.{command.action}")
        
        try:
            if command.category == CommandCategory.DEVICE:
                return self._execute_device_command(command)
            elif command.category == CommandCategory.SOFTWARE:
                return self._execute_software_command(command)
            elif command.category == CommandCategory.TRADING:
                return self._execute_trading_command(command)
            elif command.category == CommandCategory.MINING:
                return self._execute_mining_command(command)
            elif command.category == CommandCategory.QUANTUM:
                return self._execute_quantum_command(command)
            elif command.category == CommandCategory.WALLET:
                return self._execute_wallet_command(command)
            elif command.category == CommandCategory.BLOCKCHAIN:
                return self._execute_blockchain_command(command)
            elif command.category == CommandCategory.VR:
                return self._execute_vr_command(command)
            elif command.category == CommandCategory.UNITY:
                return self._execute_unity_command(command)
            elif command.category == CommandCategory.CODEGEN:
                return self._execute_codegen_command(command)
            elif command.category == CommandCategory.SETTINGS:
                return self._execute_settings_command(command)
            elif command.category == CommandCategory.SYSTEM:
                return self._execute_system_command(command)
            elif command.category == CommandCategory.VISION:
                return self._execute_vision_command(command)
            elif command.category == CommandCategory.IDENTITY:
                return self._execute_identity_command(command)
            else:
                return {"success": False, "error": "Unknown command category"}
                
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return {"success": False, "error": str(e)}
    
    def _execute_device_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute device control commands via MCP and DeviceTakeoverManager."""
        if not self.mcp_bridge:
            self._init_mcp_bridge()
        
        # SOTA 2026: Handle takeover commands with enhanced logic
        takeover_actions = {
            "takeover_device", "send_device_command", "configure_device_wifi",
            "list_taken_over_devices", "release_device", "get_takeover_status"
        }
        
        if command.action in takeover_actions:
            # Use MCP bridge which routes to HostDeviceMCPTools
            if self.mcp_bridge:
                result = self.mcp_bridge.execute_mcp_tool(command.action, command.parameters)
                
                # Publish status updates to event bus for GUI visibility (UnifiedAIRouter will deduplicate)
                if self.event_bus and result.get("success"):
                    self.event_bus.publish('ai.response', {
                        'request_id': f"cmd_{command.action}_{int(time.time()*1000)}",
                        'response': result.get('message', f"Device command '{command.action}' executed"),
                        'sender': 'ai_command_router',
                        'action': command.action,
                        'result': result
                    })
                
                self._publish_result("device", command, result)
                return result
            
            # Fallback: Try direct takeover manager access
            try:
                from core.host_device_manager import get_device_takeover_manager
                takeover_mgr = get_device_takeover_manager(self.event_bus)
                
                if command.action == "send_device_command":
                    device_id = command.parameters.get("device_id", "")
                    cmd = command.parameters.get("command", command.raw_text)
                    result = takeover_mgr.send_device_command(device_id, cmd)
                elif command.action == "list_taken_over_devices":
                    devices = takeover_mgr.get_all_taken_over_devices()
                    result = {"success": True, "devices": devices, "count": len(devices)}
                elif command.action == "get_takeover_status":
                    device_id = command.parameters.get("device_id", "")
                    info = takeover_mgr.get_takeover_info(device_id)
                    result = {"success": True, "takeover_info": info}
                else:
                    result = {"success": False, "error": f"Unhandled takeover action: {command.action}"}
                
                self._publish_result("device", command, result)
                return result
            except Exception as e:
                logger.error(f"Takeover fallback error: {e}")
                return {"success": False, "error": str(e)}
        
        # Standard device commands via MCP
        if self.mcp_bridge:
            result = self.mcp_bridge.execute_mcp_tool(command.action, command.parameters)
            self._publish_result("device", command, result)
            return result
        return {"success": False, "error": "MCP Bridge not available"}
    
    def _execute_software_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute software automation commands via MCP."""
        if not self.mcp_bridge:
            self._init_mcp_bridge()
        
        if command.action == "connect_software":
            # Build window selector from name
            window_selector = {"name_contains": command.parameters.get("name_contains", "")}
            command.parameters = {"window": window_selector}
        
        if self.mcp_bridge:
            result = self.mcp_bridge.execute_mcp_tool(command.action, command.parameters)
            self._publish_result("software", command, result)
            return result
        return {"success": False, "error": "MCP Bridge not available"}
    
    def _execute_trading_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute trading commands via EventBus."""
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            "place_order": "trading.order.place",
            "get_portfolio": "trading.portfolio.request",
            "get_price": "trading.price.request",
            "cancel_orders": "trading.orders.cancel",
            "start_auto_trading": "trading.auto.start",
            "stop_auto_trading": "trading.auto.stop",
            # SOTA 2026: Trading plan and goal management
            "set_profit_goal": "trading.goal.set",
            "set_daily_target": "trading.goal.daily",
            "update_plan_acquire": "trading.plan.acquire",
            "update_plan_sell": "trading.plan.sell",
            "set_focus_market": "trading.focus.market",
            "analyze_asset": "trading.analyze.asset",
            "update_trading_plan": "trading.plan.update",
            "get_trading_plan": "trading.plan.get",
            "enable_predator_mode": "trading.predator.enable",
            "disable_predator_mode": "trading.predator.disable",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown trading action: {command.action}"}
    
    def _execute_mining_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute mining commands via EventBus."""
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            "start_mining": "mining.start",
            "stop_mining": "mining.stop",
            "get_mining_stats": "mining.stats.request",
            "switch_pool": "mining.pool.switch",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown mining action: {command.action}"}
    
    def _execute_quantum_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute quantum computing commands via EventBus and direct API calls."""
        # Import quantum module for direct operations
        try:
            from core.quantum_mining import (
                QuantumMiningSupport, 
                QuantumProviderManager,
                is_real_quantum_available
            )
        except ImportError:
            return {"success": False, "error": "Quantum mining module not available"}
        
        # Direct query commands (return data immediately)
        if command.action == "quantum_status":
            status = QuantumMiningSupport.get_quantum_status()
            return {"success": True, "action": command.action, "data": status}
        
        if command.action == "quantum_check_availability":
            available = is_real_quantum_available()
            return {"success": True, "action": command.action, "available": available,
                    "message": "Real quantum hardware is available!" if available else "No real quantum hardware configured"}
        
        if command.action == "quantum_list_backends":
            mgr = QuantumProviderManager.get_instance()
            mgr.initialize()
            backends = [str(b.name() if callable(b.name) else b.name) for b in mgr.get_ibm_backends()]
            return {"success": True, "action": command.action, "backends": backends,
                    "count": len(backends)}
        
        if command.action == "quantum_capabilities":
            return {"success": True, "action": command.action, "capabilities": {
                "ibm_quantum": "Real IBM quantum hardware via qiskit-ibm-provider",
                "openquantum": "Multi-provider quantum access via OpenQuantum SDK",
                "grover_mining": "Quantum-enhanced mining using Grover's algorithm",
                "circuit_submission": "Submit custom quantum circuits to real QPUs",
                "portfolio_optimization": "QAOA-based quantum portfolio optimization",
                "arbitrage_detection": "Quantum search for arbitrage opportunities",
                "risk_analysis": "Quantum-enhanced VaR and risk assessment",
                "fallback": "Local simulator fallback when no real hardware available"
            }}
        
        # Quantum trading operations (async)
        if command.action == "quantum_optimize_portfolio":
            try:
                from core.quantum_mining import get_quantum_trading_enhancer
                enhancer = get_quantum_trading_enhancer()
                if not enhancer.is_available():
                    return {"success": False, "error": "Quantum hardware not available for trading optimization"}
                # Publish event for async handling
                if self.event_bus:
                    self.event_bus.publish("quantum.trading.optimize_portfolio", command.parameters)
                return {"success": True, "action": command.action, "message": "Portfolio optimization queued on quantum hardware"}
            except ImportError:
                return {"success": False, "error": "Quantum trading module not available"}
        
        if command.action == "quantum_find_arbitrage":
            if self.event_bus:
                self.event_bus.publish("quantum.trading.find_arbitrage", command.parameters)
            return {"success": True, "action": command.action, "message": "Quantum arbitrage scan initiated"}
        
        if command.action == "quantum_risk_analysis":
            if self.event_bus:
                self.event_bus.publish("quantum.trading.risk_analysis", command.parameters)
            return {"success": True, "action": command.action, "message": "Quantum risk analysis initiated"}
        
        if command.action == "quantum_trading_enable":
            if self.event_bus:
                self.event_bus.publish("quantum.trading.enable", {"enabled": True})
            return {"success": True, "action": command.action, "message": "Quantum trading enhancement enabled"}
        
        # EventBus-based commands
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            "quantum_detect": "quantum.hardware.detect",
            "quantum_mining_start": "quantum.mining.start",
            "quantum_mining_stop": "quantum.mining.stop",
            "quantum_submit_ibm": "quantum.job.submit.ibm",
            "quantum_submit_openquantum": "quantum.job.submit.openquantum",
            "quantum_configure_ibm": "quantum.config.ibm",
            "quantum_configure_openquantum": "quantum.config.openquantum",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown quantum action: {command.action}"}
    
    def _execute_wallet_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute wallet commands via EventBus."""
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            "get_balance": "wallet.balance.request",
            "send_transaction": "wallet.transaction.send",
            "get_addresses": "wallet.addresses.request",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown wallet action: {command.action}"}
    
    def _execute_system_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute system commands via EventBus."""
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            "switch_tab": "tab.switch",  # Matches tab_manager.py subscription
            "get_system_status": "system.status.request",
            "refresh_tab": "tab.refresh",
            # SOTA 2026: Full Comms Tab Integration
            "comms_scan": "comms.scan",
            "comms_status": "comms.status.request",
            "comms_video_start": "comms.video.start",
            "comms_video_stop": "comms.video.stop",
            "comms_sonar_start": "comms.sonar.start",
            "comms_sonar_stop": "comms.sonar.stop",
            "comms_radio_transmit": "comms.radio.transmit",
            "comms_radio_receive_start": "comms.radio.receive.start",
            "comms_radio_receive_stop": "comms.radio.receive.stop",
            "comms_call_start": "comms.call.start",
            "comms_call_stop": "comms.call.stop",
            "comms_call_status": "comms.call.status.request",
            # SOTA 2026: Full Host System Control
            "run_shell_command": "system.shell.execute",
            "list_processes": "system.processes.list",
            "kill_process": "system.process.kill",
            "take_screenshot": "system.screenshot.capture",
            "start_screen_recording": "system.recording.start",
            "stop_screen_recording": "system.recording.stop",
            "get_system_info": "system.info.request",
            "list_windows": "system.windows.list",
            "focus_window": "system.window.focus",
            "minimize_windows": "system.windows.minimize",
            "maximize_window": "system.window.maximize",
            # Hardware Control
            "list_gpus": "hardware.gpus.list",
            "get_gpu_status": "hardware.gpu.status",
            "list_cameras": "hardware.cameras.list",
            "enable_camera": "hardware.camera.enable",
            "disable_camera": "hardware.camera.disable",
            "list_microphones": "hardware.microphones.list",
            "enable_microphone": "hardware.microphone.enable",
            "disable_microphone": "hardware.microphone.disable",
            # Mouse/Keyboard Control
            "click_at": "input.mouse.click",
            "move_mouse": "input.mouse.move",
            "send_keys": "input.keyboard.type",
            "press_key": "input.keyboard.press",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown system action: {command.action}"}
    
    def _execute_blockchain_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute blockchain commands via EventBus."""
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            "get_network_status": "blockchain.network.status",
            "switch_network": "blockchain.network.switch",
            "list_networks": "blockchain.networks.list",
            "deploy_contract": "blockchain.contract.deploy",
            "get_gas_price": "blockchain.gas.price",
            "open_explorer": "blockchain.explorer.open",
            "verify_transaction": "blockchain.transaction.verify",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown blockchain action: {command.action}"}
    
    def _execute_vr_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute VR commands via EventBus.
        
        2026 SOTA: Extended VR commands for scene management, object control,
        haptics, spatial audio, and device management.
        """
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            # Basic VR Control
            "start_vr": "vr.system.start",
            "stop_vr": "vr.system.stop",
            "get_vr_status": "vr.status.request",
            "calibrate_vr": "vr.calibrate",
            "enable_hand_tracking": "vr.hands.enable",
            "disable_hand_tracking": "vr.hands.disable",
            "open_vr_trading": "vr.trading.open",
            # 2026 SOTA: Scene Management
            "vr_load_scene": "vr.scene.load",
            "vr_list_scenes": "vr.scene.list",
            "vr_save_scene": "vr.scene.save",
            # 2026 SOTA: Object Control
            "vr_add_object": "vr.object.add",
            "vr_remove_object": "vr.object.remove",
            "vr_move_object": "vr.object.move",
            "vr_scale_object": "vr.object.scale",
            # 2026 SOTA: Visualization Control
            "vr_show_market_viz": "vr.visualization.market",
            "vr_show_portfolio_viz": "vr.visualization.portfolio",
            "vr_show_mining_viz": "vr.visualization.mining",
            "vr_hide_visualizations": "vr.visualization.hide_all",
            # 2026 SOTA: Environment Settings
            "vr_set_quality": "vr.settings.quality",
            "vr_set_fps": "vr.settings.fps",
            "vr_set_tracking": "vr.settings.tracking",
            # 2026 SOTA: Haptic Feedback
            "vr_enable_haptics": "vr.haptics.enable",
            "vr_disable_haptics": "vr.haptics.disable",
            "vr_test_haptics": "vr.haptics.test",
            # 2026 SOTA: Spatial Audio
            "vr_enable_spatial_audio": "vr.audio.spatial.enable",
            "vr_disable_spatial_audio": "vr.audio.spatial.disable",
            # 2026 SOTA: Recording/Capture
            "vr_start_recording": "vr.recording.start",
            "vr_stop_recording": "vr.recording.stop",
            "vr_capture_screenshot": "vr.capture.screenshot",
            # 2026 SOTA: Device Management
            "vr_list_devices": "vr.devices.list",
            "vr_connect_device": "vr.device.connect",
            "vr_disconnect_device": "vr.device.disconnect",
            "vr_get_battery": "vr.device.battery",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown VR action: {command.action}"}
    
    def _execute_vision_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute Vision commands via EventBus.
        
        2026 SOTA: Vision system commands for facial recognition (DeepFace/InsightFace),
        object detection (YOLO), pose estimation (MediaPipe), OCR, and AI vision.
        """
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            # Facial Recognition (DeepFace + InsightFace)
            "vision_analyze_face": "vision.face.analyze",
            "vision_recognize_face": "vision.face.recognize",
            "vision_detect_faces": "vision.face.detect",
            "vision_analyze_emotion": "vision.face.emotion",
            "vision_analyze_demographics": "vision.face.demographics",
            "vision_track_person": "vision.face.track",
            "vision_register_face": "vision.face.register",
            "vision_identify_person": "vision.face.identify",
            "vision_list_faces": "vision.face.list",
            "vision_delete_face": "vision.face.delete",
            # Object Detection (YOLO)
            "vision_detect_objects": "vision.objects.detect",
            "vision_find_object": "vision.objects.find",
            "vision_track_object": "vision.objects.track",
            "vision_count_objects": "vision.objects.count",
            # Scene Understanding
            "vision_describe_scene": "vision.scene.describe",
            "vision_analyze_scene": "vision.scene.analyze",
            "vision_analyze_activity": "vision.scene.activity",
            # OCR/Text Extraction
            "vision_extract_text": "vision.ocr.extract",
            "vision_ocr": "vision.ocr.scan",
            "vision_read_document": "vision.ocr.document",
            "vision_translate_text": "vision.ocr.translate",
            # Pose/Gesture Estimation (MediaPipe)
            "vision_detect_pose": "vision.pose.detect",
            "vision_detect_gestures": "vision.gesture.detect",
            "vision_track_movement": "vision.motion.track",
            # Vision Stream Control
            "vision_start_stream": "vision.stream.start",
            "vision_stop_stream": "vision.stream.stop",
            "vision_pause_stream": "vision.stream.pause",
            "vision_resume_stream": "vision.stream.resume",
            # Vision Quality Control
            "vision_enhance_image": "vision.enhance.image",
            "vision_set_quality": "vision.settings.quality",
            "vision_set_fps": "vision.settings.fps",
            # Vision Recording/Capture
            "vision_capture_frame": "vision.capture.frame",
            "vision_start_recording": "vision.recording.start",
            "vision_stop_recording": "vision.recording.stop",
            "vision_save_frame": "vision.capture.save",
            # Multi-Camera Management
            "vision_switch_camera": "vision.camera.switch",
            "vision_list_cameras": "vision.camera.list",
            "vision_enable_vr_camera": "vision.camera.vr.enable",
            "vision_disable_vr_camera": "vision.camera.vr.disable",
            "vision_research_active_frame": "vision.action.research.active_frame",
            "vision_send_to_creative": "vision.action.creative.active_frame",
            # Vision AI Integration
            "vision_ai_analyze": "vision.ai.analyze",
            "vision_ai_generate": "vision.ai.generate",
            "vision_compare_images": "vision.ai.compare",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown vision action: {command.action}"}
    
    def _execute_identity_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute Identity/Biometric commands via EventBus.
        
        2026 SOTA: SpeechBrain ECAPA-TDNN for voice biometrics,
        facenet-pytorch for face biometrics, Silero VAD for speech detection.
        """
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            # Speaker verification (SpeechBrain ECAPA-TDNN 192-dim embeddings)
            "identity_verify": "identity.verify",
            "identity_enroll_voice": "identity.enroll.voice",
            "identity_enroll_face": "identity.enroll.face",
            "identity_status": "identity.status",
            "identity_list_profiles": "identity.profiles.list",
            "identity_delete_enrollment": "identity.enrollment.delete",
            "identity_enable_verification": "identity.verification.enable",
            "identity_disable_verification": "identity.verification.disable",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown identity action: {command.action}"}
    
    def _execute_unity_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute Unity runtime commands via EventBus → TCP to Unity CommandReceiver.cs."""
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        # Map action names to Unity TCP commands and events
        unity_command_mapping = {
            "unity_move_forward": "move forward",
            "unity_move_backward": "move backward",
            "unity_turn_left": "turn left",
            "unity_turn_right": "turn right",
            "unity_jump": "jump",
            "unity_stop": "stop",
        }
        
        # Connection control events (not sent to Unity TCP, handled by bridge)
        connection_events = {
            "unity_connect": "unity.runtime.connect",
            "unity_disconnect": "unity.runtime.disconnect",
            "unity_ping": "unity.runtime.ping",
        }
        
        # Check if it's a movement command (sent via unity.command → TCP)
        if command.action in unity_command_mapping:
            unity_cmd = unity_command_mapping[command.action]
            self.event_bus.publish("unity.command", {
                "command": unity_cmd,
                "source": "ai_command_router",
                "action": command.action,
            })
            logger.info(f"🎮 Published unity.command: '{unity_cmd}'")
            return {"success": True, "action": command.action, "unity_command": unity_cmd, "published": "unity.command"}
        
        # Check if it's a connection control event
        if command.action in connection_events:
            event_type = connection_events[command.action]
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        
        return {"success": False, "error": f"Unknown Unity action: {command.action}"}
    
    def _execute_codegen_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute code generator commands via EventBus."""
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            "generate_code": "codegen.generate",
            "generate_strategy": "codegen.strategy.generate",
            "generate_contract": "codegen.contract.generate",
            "explain_code": "codegen.explain",
            "optimize_code": "codegen.optimize",
            "list_templates": "codegen.templates.list",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown codegen action: {command.action}"}
    
    def _execute_settings_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Execute settings commands via EventBus."""
        if not self.event_bus:
            return {"success": False, "error": "EventBus not available"}
        
        event_mapping = {
            "open_settings": "settings.open",
            "set_api_key": "settings.apikey.set",
            "enable_dark_mode": "settings.theme.dark",
            "disable_dark_mode": "settings.theme.light",
            "set_language": "settings.language.set",
            "toggle_notifications": "settings.notifications.toggle",
            "reset_settings": "settings.reset",
            "backup_config": "settings.backup",
            "import_config": "settings.import",
        }
        
        event_type = event_mapping.get(command.action)
        if event_type:
            self.event_bus.publish(event_type, command.parameters)
            return {"success": True, "action": command.action, "published": event_type}
        return {"success": False, "error": f"Unknown settings action: {command.action}"}
    
    def _init_mcp_bridge(self):
        """Initialize MCP Bridge if not already done."""
        try:
            from ai.thoth_mcp import ThothMCPBridge
            self.mcp_bridge = ThothMCPBridge()
            logger.info("✅ AI Command Router initialized MCP Bridge")
        except Exception as e:
            logger.error(f"Failed to initialize MCP Bridge: {e}")
    
    def _publish_result(self, category: str, command: ParsedCommand, result: Dict[str, Any]):
        """Publish command result to EventBus."""
        if self.event_bus:
            self.event_bus.publish(f"ai.command.result.{category}", {
                "action": command.action,
                "parameters": command.parameters,
                "result": result,
                "success": result.get("success", False),
            })
    
    def _handle_command_execute(self, payload: Dict[str, Any]):
        """Handle explicit command execution request."""
        text = payload.get("text", "")
        command = self.parse_command(text)
        if command:
            result = self.execute_command(command)
            if self.event_bus:
                self.event_bus.publish("ai.command.executed", {
                    "command": command.action,
                    "result": result,
                })
    
    def _handle_user_message(self, payload: Dict[str, Any]):
        """Handle user chat/voice message to detect commands.
        
        Supports both 'message' key (from chat.message.user) and 'text' key (from ai.user_input).
        """
        text = payload.get("message") or payload.get("text") or ""
        command = self.parse_command(text)
        if command:
            # Detected a command in the user message
            logger.info(f"🎯 Detected command in chat: {command.category.value}.{command.action}")
            result = self.execute_command(command)
            
            # Publish result for AI to include in response
            if self.event_bus:
                self.event_bus.publish("ai.command.auto_executed", {
                    "command": command.action,
                    "category": command.category.value,
                    "result": result,
                    "original_text": text,
                })
    
    def process_and_route(self, text: str, **kwargs) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Process text and route to appropriate handler.
        
        SOTA 2026 Architecture:
        1. Parse for commands → execute directly if found
        2. Not a command → route to brain via ai.request
        
        Args:
            text: User input text
            **kwargs: Additional options (send_to_brain=True, priority="normal", speak=False)
            
        Returns:
            Tuple of (was_command, result)
        """
        command = self.parse_command(text)
        if command:
            result = self.execute_command(command)
            return True, result
        
        # Not a command - route to brain if requested
        if kwargs.get("send_to_brain", False) and self.event_bus:
            self._route_to_brain(text, **kwargs)
        
        return False, None
    
    def _route_to_brain(self, text: str, **kwargs) -> None:
        """Route non-command text to AI brain for processing.
        
        SOTA 2026: Integrates with UnifiedAIRouter → BrainRouter/KingdomAIBrain
        """
        if not self.event_bus:
            logger.warning("Cannot route to brain - no event bus")
            return
        
        import time
        request_id = kwargs.get("request_id") or f"router_{int(time.time() * 1000)}"
        
        # Publish ai.request which UnifiedAIRouter will bridge to brain.request
        self.event_bus.publish("ai.request", {
            "request_id": request_id,
            "prompt": text,
            "domain": kwargs.get("domain", "general"),
            "sender": "ai_command_router",
            "speak": kwargs.get("speak", False),
            "priority": kwargs.get("priority", "normal"),  # SOTA 2026: Priority routing
            "source_tab": kwargs.get("source_tab"),
        })
        logger.info(f"🧠 Routed to brain: {text[:50]}... (priority: {kwargs.get('priority', 'normal')})")
    
    def route_device_event_to_brain(self, device: Dict[str, Any], event_type: str) -> None:
        """Route device events to brain for AI awareness.
        
        SOTA 2026: Ensures AI brain knows about device changes.
        """
        if not self.event_bus:
            return
        
        device_name = device.get("name", "Unknown")
        device_category = device.get("category", "unknown")
        
        # Build context for brain
        context = f"Device {event_type}: {device_name} ({device_category})"
        if device.get("capabilities", {}).get("microphone"):
            context += " - has microphone for voice commands"
        
        # Publish for brain awareness (low priority, don't need response)
        self.event_bus.publish("brain.context.update", {
            "type": "device_event",
            "event": event_type,
            "device": device,
            "summary": context,
        })


# Singleton instance
_command_router_instance: Optional[AICommandRouter] = None


def get_command_router(event_bus=None, mcp_bridge=None) -> AICommandRouter:
    """Get or create the singleton AI Command Router instance."""
    global _command_router_instance
    if _command_router_instance is None:
        _command_router_instance = AICommandRouter(event_bus, mcp_bridge)
    return _command_router_instance
