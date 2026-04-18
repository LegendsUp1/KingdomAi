"""
KINGDOM AI - Universal Device Brain Controller
SOTA 2026 - Natural Language Control for ANY Device via Ollama

Works with ANY microcontroller without custom firmware:
- Auto-learns device capabilities through probing
- Ollama translates natural language to device commands
- Remembers what works for each device type
- Supports: Particle, Arduino, ESP32, STM32, Teensy, any serial device

Examples:
- "Turn on the light" → Ollama figures out the right command
- "What can this device do?" → Probes and reports capabilities
- "Blink the LED" → Tries common patterns until one works
"""

import asyncio
import re
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("KingdomAI.DeviceBrain")

_orch = None
_ORCH_AVAILABLE = False

def _ensure_orch():
    global _orch, _ORCH_AVAILABLE
    if _ORCH_AVAILABLE:
        return True
    try:
        from core.ollama_gateway import orchestrator as _o, get_ollama_url as _gou
        _orch = _o
        globals()["get_ollama_url"] = _gou
        _ORCH_AVAILABLE = True
        return True
    except Exception:
        return False

def get_ollama_url():
    return "http://localhost:11434"

_ensure_orch()

# Common command patterns for different devices
UNIVERSAL_COMMANDS = {
    # Try these patterns in order until one works
    "led_on": ["LED_ON", "led on", "1", "ON", "HIGH", "D7:1", "digitalWrite(13,HIGH)"],
    "led_off": ["LED_OFF", "led off", "0", "OFF", "LOW", "D7:0", "digitalWrite(13,LOW)"],
    "blink": ["BLINK", "blink", "LED_BLINK", "flash"],
    "status": ["STATUS", "status", "?", "INFO", "info", "i"],
    "help": ["HELP", "help", "h", "?", "commands"],
    "version": ["VERSION", "version", "v", "ver"],
    "reset": ["RESET", "reset", "reboot", "restart"],
}

# Device command mappings for natural language
DEVICE_COMMANDS = {
    # LED Control
    "turn on": "LED_ON",
    "light on": "LED_ON",
    "led on": "LED_ON",
    "turn off": "LED_OFF",
    "light off": "LED_OFF",
    "led off": "LED_OFF",
    "blink": "LED_BLINK",
    "flash": "LED_BLINK",
    "toggle": "TOGGLE",
    
    # RGB Colors
    "red": "RED",
    "green": "GREEN",
    "blue": "BLUE",
    "white": "WHITE",
    "purple": "RGB:128,0,255",
    "orange": "RGB:255,165,0",
    "yellow": "RGB:255,255,0",
    "pink": "RGB:255,105,180",
    "cyan": "RGB:0,255,255",
    "off color": "RGB_OFF",
    "color off": "RGB_OFF",
    
    # Info Commands
    "status": "STATUS",
    "info": "INFO",
    "help": "HELP",
    "version": "VERSION",
    "mac": "MAC",
    "id": "ID",
    
    # System
    "reset": "RESET",
    "reboot": "RESET",
    "restart": "RESET",
}


class DeviceBrainController:
    """
    Universal Device Controller using Ollama.
    Works with ANY microcontroller - learns commands automatically.
    """
    
    def __init__(self, ollama_connector=None, windows_bridge=None):
        self.ollama = ollama_connector
        self.bridge = windows_bridge
        self.connected_device = None
        self.device_port = None
        self.device_baudrate = 115200
        self.command_history: List[Dict] = []
        self.learned_commands: Dict[str, str] = {}  # action -> working command
        self.device_capabilities: List[str] = []
        self.knowledge_file = Path(__file__).parent.parent / "data" / "device_knowledge.json"
        self._load_knowledge()
        
    def _load_knowledge(self):
        """Load learned device commands from disk"""
        try:
            if self.knowledge_file.exists():
                data = json.loads(self.knowledge_file.read_text())
                self.learned_commands = data.get("commands", {})
                self.device_capabilities = data.get("capabilities", [])
        except Exception as e:
            logger.warning(f"Could not load device knowledge: {e}")
    
    def _save_knowledge(self):
        """Save learned commands to disk"""
        try:
            self.knowledge_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "commands": self.learned_commands,
                "capabilities": self.device_capabilities,
                "updated": datetime.now().isoformat()
            }
            self.knowledge_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Could not save device knowledge: {e}")
    
    def learn_command(self, action: str, command: str, worked: bool):
        """Learn that a command worked (or didn't) for an action"""
        if worked:
            self.learned_commands[action] = command
            if action not in self.device_capabilities:
                self.device_capabilities.append(action)
            self._save_knowledge()
            logger.info(f"Learned: '{action}' → '{command}'")
    
    def probe_device(self) -> Dict[str, Any]:
        """Probe device to discover capabilities"""
        if not self.device_port:
            return {"error": "No device connected"}
        
        print("\n🔍 Probing device capabilities...")
        results = {"working_commands": [], "responses": {}}
        
        # Try common commands
        probe_commands = ["help", "?", "status", "info", "version", "i", "v"]
        
        for cmd in probe_commands:
            result = self.send_command(cmd)
            if result.get("success") and result.get("response"):
                resp = result["response"].strip()
                if resp and "error" not in resp.lower() and "unknown" not in resp.lower():
                    results["working_commands"].append(cmd)
                    results["responses"][cmd] = resp
                    print(f"   ✅ '{cmd}' → {resp[:50]}...")
        
        # Parse help response to find available commands
        for cmd, resp in results["responses"].items():
            if "command" in resp.lower() or "help" in cmd.lower():
                # Try to extract command names
                words = re.findall(r'\b[A-Z_]{3,}\b', resp)
                for word in words:
                    if word not in self.device_capabilities:
                        self.device_capabilities.append(word)
        
        self._save_knowledge()
        return results
    
    def connect_device(self, port: str, baudrate: int = 115200, device_info: Dict = None):
        """Connect to a device for control"""
        self.device_port = port
        self.device_baudrate = baudrate
        self.connected_device = device_info or {"port": port}
        logger.info(f"Device connected: {port} @ {baudrate}")
        
    def quick_parse(self, user_input: str) -> Optional[str]:
        """Quick pattern matching for common commands (no AI needed)"""
        text = user_input.lower().strip()

        # Color blink shortcuts (RGB LED)
        if "blink" in text or "flash" in text:
            if "red" in text:
                return "RGB_BLINK:255,0,0"
            if "green" in text:
                return "RGB_BLINK:0,255,0"
            if "blue" in text:
                return "RGB_BLINK:0,0,255"
            if "white" in text:
                return "RGB_BLINK:255,255,255"
        
        # Direct command check
        for pattern, command in DEVICE_COMMANDS.items():
            if pattern in text:
                return command
        
        # RGB color extraction: "set color to 255,0,128" or "rgb 255 0 128"
        rgb_match = re.search(r'(?:rgb|color)\s*[:\s]*(\d+)[,\s]+(\d+)[,\s]+(\d+)', text)
        if rgb_match:
            r, g, b = rgb_match.groups()
            return f"RGB:{r},{g},{b}"
        
        # Pin control: "set pin 5 high" or "pin d0 low"
        pin_match = re.search(r'pin\s*[d]?(\d+)\s*(high|low|on|off)', text)
        if pin_match:
            pin, state = pin_match.groups()
            if state in ('high', 'on'):
                return f"PIN_HIGH:{pin}"
            else:
                return f"PIN_LOW:{pin}"
        
        # PWM: "set pwm 3 to 128"
        pwm_match = re.search(r'pwm\s*(\d+)\s*(?:to\s*)?(\d+)', text)
        if pwm_match:
            pin, value = pwm_match.groups()
            return f"PWM:{pin},{value}"
        
        return None
    
    async def ai_parse(self, user_input: str) -> str:
        """Use Ollama to understand complex natural language commands.

        SOTA 2026: Falls through three paths:
        1. ThothOllamaConnector (if available)
        2. OllamaOrchestrator direct call (VRAM-aware)
        3. Quick-parse heuristic
        """
        prompt = (
            "You are Kingdom AI controlling a microcontroller device.\n"
            "Convert the user's natural language request into the exact device command.\n\n"
            "Available commands:\n"
            "- LED_ON, LED_OFF, LED_BLINK, TOGGLE (D7 LED)\n"
            "- RED, GREEN, BLUE, WHITE, RGB_OFF (RGB LED)\n"
            "- RGB:R,G,B (custom color, 0-255 each)\n"
            "- RGB_BLINK (blink RGB white), RGB_BLINK:R,G,B (blink RGB custom)\n"
            "- PIN_HIGH:X, PIN_LOW:X (GPIO control)\n"
            "- PWM:X,V (PWM output)\n"
            "- STATUS, INFO, HELP, VERSION\n\n"
            f'User request: "{user_input}"\n\n'
            "Respond with ONLY the device command(s), one per line. No explanation.\n"
            "If multiple actions needed, list each command on separate lines.\n"
            "If unclear, respond with: HELP"
        )

        # Path 1: ThothOllamaConnector
        if self.ollama:
            try:
                if hasattr(self.ollama, 'generate_text'):
                    response = await self.ollama.generate_text(prompt)
                elif hasattr(self.ollama, 'generate'):
                    response = await self.ollama.generate(prompt)
                else:
                    response = None
                if response:
                    commands = response.strip().split('\n')
                    commands = [c.strip().upper() for c in commands if c.strip()]
                    return '\n'.join(commands) if commands else user_input
            except Exception as e:
                logger.warning(f"ThothOllama parse failed: {e}")

        # Path 2: OllamaOrchestrator direct call (VRAM-aware)
        if _ensure_orch():
            try:
                import requests as _req
                model = _orch.get_model_for_task("devices")
                url = get_ollama_url()
                resp = _req.post(
                    f"{url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False,
                          "options": {"num_predict": 80, "temperature": 0.2},
                          "keep_alive": -1},
                    timeout=20,
                )
                if resp.status_code == 200:
                    raw = resp.json().get("response", "").strip()
                    if raw:
                        commands = [c.strip().upper() for c in raw.split('\n') if c.strip()]
                        return '\n'.join(commands) if commands else user_input
            except Exception as e:
                logger.warning(f"Orchestrator device parse failed: {e}")

        # Path 3: Heuristic fallback
        return self.quick_parse(user_input) or user_input
    
    def send_command(self, command: str) -> Dict[str, Any]:
        """Send command to connected device"""
        if not self.device_port:
            return {"success": False, "error": "No device connected"}
        
        if not self.bridge:
            try:
                from core.windows_host_bridge import get_windows_host_bridge
                self.bridge = get_windows_host_bridge()
            except ImportError:
                return {"success": False, "error": "Windows bridge not available"}
        
        # Send via bridge
        result = self.bridge.send_serial_command(
            self.device_port, 
            command, 
            self.device_baudrate
        )
        
        # Log command
        self.command_history.append({
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "success": result.get("success", False),
            "response": result.get("response", "")
        })
        
        return result
    
    async def process_natural_language(self, user_input: str) -> Dict[str, Any]:
        """
        Main entry point: Process natural language and control device.
        
        Args:
            user_input: Natural language command from user
            
        Returns:
            Dict with command sent, response, and success status
        """
        # First try quick parse (no AI latency)
        command = self.quick_parse(user_input)
        
        # If no quick match, use AI
        if not command:
            command = await self.ai_parse(user_input)
        
        # Handle multiple commands
        commands = command.split('\n') if '\n' in command else [command]
        
        results = []
        for cmd in commands:
            cmd = cmd.strip()
            if cmd:
                result = self.send_command(cmd)
                results.append({
                    "command": cmd,
                    "success": result.get("success", False),
                    "response": result.get("response", ""),
                    "error": result.get("error", "")
                })
        
        # Combine results
        all_success = all(r["success"] for r in results)
        responses = [r["response"] for r in results if r["response"]]
        
        return {
            "success": all_success,
            "user_input": user_input,
            "commands": [r["command"] for r in results],
            "responses": responses,
            "combined_response": "\n".join(responses) if responses else "(no response)"
        }
    
    def process_sync(self, user_input: str) -> Dict[str, Any]:
        """Synchronous wrapper for process_natural_language"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.process_natural_language(user_input))


# Global instance
_device_brain: Optional[DeviceBrainController] = None


def get_device_brain() -> DeviceBrainController:
    """Get or create global device brain controller"""
    global _device_brain
    if _device_brain is None:
        _device_brain = DeviceBrainController()
    return _device_brain


def setup_device_brain(ollama_connector=None, windows_bridge=None) -> DeviceBrainController:
    """Setup device brain with connectors"""
    global _device_brain
    _device_brain = DeviceBrainController(ollama_connector, windows_bridge)
    return _device_brain
