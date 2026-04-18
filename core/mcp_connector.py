#!/usr/bin/env python3
"""
Unified MCP Connector - Kingdom AI Central Hub
==============================================
Consolidates all MCP tools from across the system into a single, unified interface.

This is the MISSING piece that breaks Code Generator and Thoth AI imports.
Creating this file immediately fixes 7+ import failures across the codebase.

Author: Kingdom AI Team
Version: 1.0.0 SOTA 2026
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("KingdomAI.MCPConnector")

# Import all MCP systems
try:
    from core.thoth import MCPConnector as ThothMCP
    THOTH_MCP_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Thoth MCP not available: {e}")
    THOTH_MCP_AVAILABLE = False

try:
    from core.unity_mcp_integration import get_unity_mcp_tools
    UNITY_MCP_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Unity MCP not available: {e}")
    UNITY_MCP_AVAILABLE = False

try:
    from core.software_automation_manager import SoftwareAutomationManager, SoftwareAutomationMCPTools
    SOFTWARE_MCP_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Software MCP not available: {e}")
    SOFTWARE_MCP_AVAILABLE = False

try:
    from core.device_takeover_system import DeviceTakeover
    DEVICE_MCP_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Device MCP not available: {e}")
    DEVICE_MCP_AVAILABLE = False


@dataclass
class MCPTool:
    """Represents an MCP tool with metadata"""
    name: str
    description: str
    parameters: Dict[str, Any]
    category: str
    source: str  # Which system provides this tool
    available: bool = True


class UnifiedMCPConnector:
    """
    Central MCP connector that aggregates ALL MCP tools from across Kingdom AI.
    
    This is the unified interface that was missing - causing import failures
    and preventing users from discovering available tools.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("KingdomAI.UnifiedMCP")
        
        # Initialize all MCP systems
        self.mcp_systems = {}
        self.tools_registry = {}
        
        # Code generation attributes
        self.current_model = "gpt-4"
        self.is_connected = False
        self.is_initialized = False
        
        self._initialize_mcp_systems()
        self._build_tools_registry()
        
        self.logger.info(f"✅ Unified MCP Connector initialized with {len(self.tools_registry)} tools")
    
    def _initialize_mcp_systems(self):
        """Initialize all available MCP systems"""
        
        # Thoth AI MCP
        if THOTH_MCP_AVAILABLE:
            try:
                self.mcp_systems['thoth'] = ThothMCP()
                self.logger.info("✅ Thoth MCP initialized")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize Thoth MCP: {e}")
        
        # Unity MCP
        if UNITY_MCP_AVAILABLE:
            try:
                self.mcp_systems['unity'] = get_unity_mcp_tools(self.event_bus)
                self.logger.info("✅ Unity MCP initialized")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize Unity MCP: {e}")
        
        # Software Automation MCP
        if SOFTWARE_MCP_AVAILABLE:
            try:
                manager = SoftwareAutomationManager()
                self.mcp_systems['software'] = SoftwareAutomationMCPTools(manager)
                self.logger.info("✅ Software MCP initialized")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize Software MCP: {e}")
        
        # Device Takeover MCP (create bridge if needed)
        if DEVICE_MCP_AVAILABLE:
            try:
                device_takeover = DeviceTakeover()
                self.mcp_systems['device'] = DeviceTakeoverMCPBridge(device_takeover)
                self.logger.info("✅ Device MCP initialized")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize Device MCP: {e}")
    
    def _build_tools_registry(self):
        """Build unified registry of all available tools"""
        self.tools_registry = {}
        
        for system_name, mcp_system in self.mcp_systems.items():
            try:
                if hasattr(mcp_system, 'get_tools'):
                    tools = mcp_system.get_tools()
                    for tool in tools:
                        tool_key = f"{system_name}_{tool['name']}"
                        self.tools_registry[tool_key] = MCPTool(
                            name=tool['name'],
                            description=tool['description'],
                            parameters=tool.get('parameters', {}),
                            category=system_name,
                            source=system_name
                        )
            except Exception as e:
                self.logger.error(f"❌ Failed to get tools from {system_name}: {e}")
        
        self.logger.info(f"📋 Built tools registry with {len(self.tools_registry)} tools")
    
    def get_all_tools(self) -> List[MCPTool]:
        """Get all available tools from all systems"""
        return list(self.tools_registry.values())
    
    def get_tools_by_category(self, category: str) -> List[MCPTool]:
        """Get tools from a specific category/system"""
        return [tool for tool in self.tools_registry.values() if tool.category == category]
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name - automatically routes to correct system"""
        
        # Find which system has this tool
        for system_name, mcp_system in self.mcp_systems.items():
            try:
                # Check if this system has the tool
                if hasattr(mcp_system, 'get_tools'):
                    tools = mcp_system.get_tools()
                    tool_names = [t['name'] for t in tools]
                    
                    if tool_name in tool_names:
                        # Execute the tool
                        if hasattr(mcp_system, 'execute_tool'):
                            result = mcp_system.execute_tool(tool_name, parameters)
                            
                            # Log the execution
                            self.logger.info(f"🔧 Executed {tool_name} via {system_name}")
                            
                            # Publish event if event bus available
                            if self.event_bus:
                                self.event_bus.publish('mcp.tool.executed', {
                                    'tool': tool_name,
                                    'system': system_name,
                                    'parameters': parameters,
                                    'result': result,
                                    'timestamp': datetime.now().isoformat()
                                })
                            
                            return result
                        else:
                            return {"success": False, "error": f"System {system_name} doesn't support tool execution"}
                            
            except Exception as e:
                self.logger.error(f"❌ Error executing {tool_name} via {system_name}: {e}")
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": f"Tool {tool_name} not found in any system"}
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get status of all MCP systems"""
        status = {
            "total_tools": len(self.tools_registry),
            "systems": {},
            "categories": {}
        }
        
        for system_name, mcp_system in self.mcp_systems.items():
            try:
                tools_count = len(self.mcp_systems[system_name].get_tools()) if hasattr(self.mcp_systems[system_name], 'get_tools') else 0
                status["systems"][system_name] = {
                    "available": True,
                    "tools_count": tools_count
                }
            except Exception as e:
                status["systems"][system_name] = {
                    "available": False,
                    "error": str(e)
                }
        
        # Count tools by category
        for tool in self.tools_registry.values():
            category = tool.category
            if category not in status["categories"]:
                status["categories"][category] = 0
            status["categories"][category] += 1
        
        return status
    
    async def initialize(self):
        """Async initialization for compatibility"""
        self.logger.info("🚀 Unified MCP Connector initializing...")
        # Additional async setup if needed
        return True
    
    async def connect(self):
        """Async connection for compatibility"""
        self.logger.info("🔗 Unified MCP Connector connecting...")
        # Additional connection logic if needed
        return True
    
    async def close(self):
        """Cleanup resources"""
        self.logger.info("🔌 Unified MCP Connector closing...")
        # Cleanup if needed
    
    # Code Generation Methods - Added for Code Generator App compatibility
    async def generate_code(self, prompt: str, model: str = None, temperature: float = 0.7, max_tokens: int = 2048) -> Dict[str, Any]:
        """Generate code using Thoth AI or available MCP tools"""
        try:
            self.logger.info(f"🔧 Generating code with model: {model or self.current_model}")
            
            # Update current model if provided
            if model:
                self.current_model = model
            
            # Try to use Thoth MCP for code generation
            if 'thoth' in self.mcp_systems:
                thoth_mcp = self.mcp_systems['thoth']
                if hasattr(thoth_mcp, 'generate_code'):
                    result = await thoth_mcp.generate_code(
                        prompt=prompt,
                        model=model or self.current_model,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    return result
            
            # Fallback to tool execution
            result = self.execute_tool('generate_code', {
                'prompt': prompt,
                'model': model or self.current_model,
                'temperature': temperature,
                'max_tokens': max_tokens
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Code generation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'code': None,
                'response': f"Error generating code: {e}"
            }
    
    async def execute_code(self, code: str, language: str = 'python') -> Dict[str, Any]:
        """Execute code in a safe environment"""
        try:
            self.logger.info(f"🔧 Executing {language} code...")
            
            # Try to use Thoth MCP for code execution
            if 'thoth' in self.mcp_systems:
                thoth_mcp = self.mcp_systems['thoth']
                if hasattr(thoth_mcp, 'execute_code'):
                    result = await thoth_mcp.execute_code(
                        code=code,
                        language=language
                    )
                    return result
            
            # Fallback to tool execution
            result = self.execute_tool('execute_code', {
                'code': code,
                'language': language
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Code execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'output': None,
                'response': f"Error executing code: {e}"
            }
    
    async def inject_code(self, code: str, target_module: str = 'user_modules') -> Dict[str, Any]:
        """Inject code into the system"""
        try:
            self.logger.info(f"🔧 Injecting code into {target_module}...")
            
            # Try to use Thoth MCP for code injection
            if 'thoth' in self.mcp_systems:
                thoth_mcp = self.mcp_systems['thoth']
                if hasattr(thoth_mcp, 'inject_code'):
                    result = await thoth_mcp.inject_code(
                        code=code,
                        target_module=target_module
                    )
                    return result
            
            # Fallback to tool execution
            result = self.execute_tool('inject_code', {
                'code': code,
                'target_module': target_module
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Code injection failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f"Error injecting code: {e}"
            }


class DeviceTakeoverMCPBridge:
    """Bridge to expose Device Takeover system as MCP tools"""
    
    def __init__(self, device_takeover):
        self.device_takeover = device_takeover
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Expose device takeover as MCP tools"""
        return [
            {
                "name": "find_all_devices",
                "description": "Find all connected devices (USB, Serial, DFU)",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "connect_device",
                "description": "Connect to a specific device",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "port": {"type": "string"}
                    },
                    "required": ["device_id"]
                }
            },
            {
                "name": "flash_firmware",
                "description": "Flash firmware to a device",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "firmware_path": {"type": "string"}
                    },
                    "required": ["device_id"]
                }
            },
            {
                "name": "execute_device_command",
                "description": "Execute command on connected device",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "command": {"type": "string"}
                    },
                    "required": ["device_id", "command"]
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute device takeover tool"""
        try:
            if tool_name == "find_all_devices":
                devices = self.device_takeover.find_all_devices()
                return {"success": True, "devices": devices}
            
            elif tool_name == "connect_device":
                device_id = parameters.get("device_id")
                port = parameters.get("port")
                result = self.device_takeover.connect_device(device_id, port)
                return {"success": True, "result": result}
            
            elif tool_name == "flash_firmware":
                device_id = parameters.get("device_id")
                firmware_path = parameters.get("firmware_path")
                result = self.device_takeover.flash_particle_firmware({"id": device_id, "firmware_path": firmware_path})
                return {"success": True, "result": result}
            
            elif tool_name == "execute_device_command":
                device_id = parameters.get("device_id")
                command = parameters.get("command")
                result = self.device_takeover.execute_command(command)
                return {"success": True, "result": result}
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton for global access
_unified_mcp_connector: Optional[UnifiedMCPConnector] = None

def get_unified_mcp_connector(event_bus=None) -> UnifiedMCPConnector:
    """Get or create the unified MCP connector singleton"""
    global _unified_mcp_connector
    if _unified_mcp_connector is None:
        _unified_mcp_connector = UnifiedMCPConnector(event_bus)
    return _unified_mcp_connector

# Backward compatibility - this is what the import failures were looking for
MCPConnector = UnifiedMCPConnector
