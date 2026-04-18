#!/usr/bin/env python3
"""
NemoClaw Bridge - Connects Kingdom AI to NemoClaw secure agent runtime

This module provides a bridge between Kingdom AI's event bus and NVIDIA NemoClaw,
allowing secure sandboxed execution of AI tasks using OpenClaw agents.
"""

import asyncio
import subprocess
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger('kingdom_ai.nemoclaw_bridge')

@dataclass
class NemoClawConfig:
    """Configuration for NemoClaw bridge"""
    sandbox_name: str = "kingdom-ai-assistant"
    use_cli: bool = True  # True = CLI calls, False = HTTP API
    timeout_seconds: int = 300
    max_retries: int = 3
    enable_logging: bool = True

class NemoClawBridge:
    """
    Bridge between Kingdom AI event bus and NemoClaw CLI/API
    
    This class handles communication with NemoClaw, providing methods to:
    - Check NemoClaw availability and status
    - Send prompts to NemoClaw sandbox
    - Execute commands in secure environment
    - Monitor sandbox health and logs
    """
    
    def __init__(self, event_bus, config: Optional[NemoClawConfig] = None):
        """
        Initialize NemoClaw bridge
        
        Args:
            event_bus: Kingdom AI event bus for communication
            config: NemoClaw configuration (uses defaults if None)
        """
        self.event_bus = event_bus
        self.config = config or NemoClawConfig()
        self.nemoclaw_available = False
        self.sandbox_status = "unknown"
        self.last_check = None
        
        # Register event handlers
        self._register_event_handlers()
        
        logger.info(f"NemoClaw bridge initialized (sandbox: {self.config.sandbox_name})")
    
    def _register_event_handlers(self):
        """Register sync-safe event handlers for NemoClaw operations.

        The KingdomAIBrain handles these events via its own sync wrappers that
        call asyncio.create_task.  The bridge only subscribes lightweight sync
        status trackers here to avoid duplicate async coroutine warnings.
        """
        if self.event_bus:
            self.event_bus.subscribe("nemoclaw.status", self._sync_status_handler)

    def _sync_status_handler(self, data):
        """Lightweight sync handler — just log status requests."""
        logger.debug("NemoClaw status request received via event bus")
    
    async def initialize(self):
        """
        Initialize NemoClaw bridge by checking availability
        
        Returns:
            bool: True if NemoClaw is available, False otherwise
        """
        try:
            # Check if nemoclaw command is available
            result = await self._run_command(["nemoclaw", "--version"])
            
            if result["success"]:
                self.nemoclaw_available = True
                version = result["stdout"].strip()
                logger.info(f"NemoClaw available: {version}")
                
                # Check sandbox status
                await self.check_sandbox_status()
                
                # Publish status
                if self.event_bus:
                    self.event_bus.publish("nemoclaw.initialized", {
                        "available": True,
                        "version": version,
                        "sandbox": self.config.sandbox_name,
                        "status": self.sandbox_status
                    })
                
                return True
            else:
                logger.warning("NemoClaw command not found")
                self.nemoclaw_available = False
                
                if self.event_bus:
                    self.event_bus.publish("nemoclaw.initialized", {
                        "available": False,
                        "error": "NemoClaw command not found"
                    })
                
                return False
                
        except Exception as e:
            logger.error(f"NemoClaw initialization failed: {e}")
            self.nemoclaw_available = False
            return False
    
    async def check_sandbox_status(self) -> Dict[str, Any]:
        """
        Check the status of the NemoClaw sandbox
        
        Returns:
            Dict with sandbox status information
        """
        if not self.nemoclaw_available:
            return {"available": False, "status": "nemoclaw_unavailable"}
        
        try:
            result = await self._run_command(
                ["nemoclaw", self.config.sandbox_name, "status"],
                timeout=30
            )
            
            if result["success"]:
                self.sandbox_status = "running"
                self.last_check = datetime.now().isoformat()
                
                status_info = {
                    "available": True,
                    "status": self.sandbox_status,
                    "last_check": self.last_check,
                    "details": result["stdout"]
                }
                
                return status_info
            else:
                self.sandbox_status = "error"
                return {
                    "available": False,
                    "status": "error",
                    "error": result["stderr"]
                }
                
        except Exception as e:
            logger.error(f"Sandbox status check failed: {e}")
            self.sandbox_status = "error"
            return {
                "available": False,
                "status": "error",
                "error": str(e)
            }
    
    async def send_to_nemoclaw(self, prompt: str, 
                              security_level: str = "standard",
                              session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a prompt to NemoClaw sandbox for processing
        
        Args:
            prompt: The prompt/text to send to the agent
            security_level: Security level (standard, high, critical)
            session_id: Optional session ID for conversation tracking
            
        Returns:
            Dict with response from NemoClaw
        """
        if not self.nemoclaw_available:
            return {
                "success": False,
                "error": "NemoClaw not available",
                "backend": "nemoclaw"
            }
        
        try:
            # Build command
            cmd = [
                "nemoclaw", self.config.sandbox_name, "exec",
                "openclaw", "agent",
                "--agent", "main",
                "--local",
                "-m", prompt
            ]
            
            # Add session ID if provided
            if session_id:
                cmd.extend(["--session-id", session_id])
            
            # Execute command
            result = await self._run_command(
                cmd,
                timeout=self.config.timeout_seconds
            )
            
            if result["success"]:
                response = {
                    "success": True,
                    "response": result["stdout"],
                    "security_level": security_level,
                    "sandbox": self.config.sandbox_name,
                    "backend": "nemoclaw",
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session_id
                }
                
                logger.info(f"NemoClaw response received (session: {session_id})")
                return response
            else:
                return {
                    "success": False,
                    "error": result["stderr"],
                    "backend": "nemoclaw",
                    "security_level": security_level
                }
                
        except asyncio.TimeoutError:
            logger.error(f"NemoClaw request timed out (session: {session_id})")
            return {
                "success": False,
                "error": "Request timed out",
                "backend": "nemoclaw",
                "security_level": security_level
            }
        except Exception as e:
            logger.error(f"NemoClaw request failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": "nemoclaw",
                "security_level": security_level
            }
    
    async def execute_in_sandbox(self, command: str, 
                                security_level: str = "high") -> Dict[str, Any]:
        """
        Execute a command securely in the NemoClaw sandbox
        
        Args:
            command: Command to execute
            security_level: Security level for execution
            
        Returns:
            Dict with execution results
        """
        if not self.nemoclaw_available:
            return {
                "success": False,
                "error": "NemoClaw not available"
            }
        
        try:
            # Execute command in sandbox
            cmd = [
                "nemoclaw", self.config.sandbox_name, "exec",
                command
            ]
            
            result = await self._run_command(
                cmd,
                timeout=self.config.timeout_seconds
            )
            
            return {
                "success": result["success"],
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "security_level": security_level,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Sandbox execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_sandbox_logs(self, follow: bool = False, 
                               lines: int = 100) -> Dict[str, Any]:
        """
        Get logs from the NemoClaw sandbox
        
        Args:
            follow: Whether to follow logs (streaming)
            lines: Number of lines to retrieve
            
        Returns:
            Dict with log contents
        """
        if not self.nemoclaw_available:
            return {"success": False, "error": "NemoClaw not available"}
        
        try:
            cmd = ["nemoclaw", self.config.sandbox_name, "logs"]
            
            if follow:
                cmd.append("--follow")
            else:
                cmd.extend(["--tail", str(lines)])
            
            result = await self._run_command(cmd, timeout=30)
            
            return {
                "success": result["success"],
                "logs": result.get("stdout", ""),
                "follow": follow,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get sandbox logs: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _run_command(self, command: List[str], 
                          timeout: int = 30) -> Dict[str, Any]:
        """
        Run a command asynchronously
        
        Args:
            command: Command to run as list of strings
            timeout: Timeout in seconds
            
        Returns:
            Dict with success status, stdout, stderr
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode().strip(),
                "stderr": stderr.decode().strip(),
                "returncode": process.returncode
            }
            
        except asyncio.TimeoutError:
            try:
                process.kill()
            except:
                pass
            raise
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": ""
            }
    
    # Event Handlers — called by KingdomAIBrain via asyncio.create_task()
    async def handle_request(self, data: Dict[str, Any]):
        """Process a nemoclaw.request and publish the response."""
        prompt = data.get("prompt", "")
        security_level = data.get("security_level", "standard")
        session_id = data.get("session_id")

        response = await self.send_to_nemoclaw(prompt, security_level, session_id)

        if self.event_bus:
            publish = getattr(self.event_bus, "publish", None)
            if publish:
                publish("nemoclaw.response", response)

    async def handle_status_request(self, data: Dict[str, Any]):
        """Check sandbox status and publish the update."""
        status = await self.check_sandbox_status()

        if self.event_bus:
            publish = getattr(self.event_bus, "publish", None)
            if publish:
                publish("nemoclaw.status_update", status)

    async def handle_execute(self, data: Dict[str, Any]):
        """Execute a command in the sandbox and publish the result."""
        command = data.get("command", "")
        security_level = data.get("security_level", "high")

        result = await self.execute_in_sandbox(command, security_level)

        if self.event_bus:
            publish = getattr(self.event_bus, "publish", None)
            if publish:
                publish("nemoclaw.execution_result", result)
