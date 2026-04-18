#!/usr/bin/env python3
"""Unity Runtime Connector for Kingdom AI

Checks if Unity is running and provides connection status.
"""
import os
import logging
import subprocess

logger = logging.getLogger("KingdomAI.UnityConnector")


class UnityConnector:
    """Connector for Unity runtime integration."""
    
    def __init__(self):
        """Initialize Unity connector."""
        self._connected = False
        self._unity_process = None
        self.check_unity_running()
    
    def check_unity_running(self) -> bool:
        """Check if Unity Hub or Unity Editor is running.
        
        Returns:
            bool: True if Unity is detected
        """
        try:
            if os.name == 'nt' or self._in_wsl():
                ps_command = "Get-Process | Where-Object {$_.ProcessName -like '*Unity*'} | Select-Object -First 1"
                result = subprocess.run(
                    ['powershell.exe', '-Command', ps_command],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                self._connected = bool(result.stdout.strip())
            elif os.name == 'posix':
                result = subprocess.run(
                    ['pgrep', '-f', '[Uu]nity'],
                    capture_output=True, text=True, timeout=5
                )
                self._connected = result.returncode == 0
            else:
                self._connected = False

            if self._connected:
                logger.info("✅ Unity detected (Hub or Editor running)")
            else:
                logger.info("ℹ️ Unity not detected (start Unity Hub or Editor for terrain export)")
            return self._connected
        except Exception as e:
            logger.debug(f"Unity check: {e}")
            self._connected = False
        return False
    
    def _in_wsl(self) -> bool:
        """Check if running in WSL."""
        try:
            with open("/proc/version", "r", encoding="utf-8") as f:
                return "microsoft" in f.read().lower()
        except Exception:
            return False
    
    def is_connected(self) -> bool:
        """Get connection status.
        
        Returns:
            bool: True if Unity is running
        """
        return self._connected
    
    def get_status(self) -> dict:
        """Get Unity connection status.
        
        Returns:
            dict: Status information
        """
        return {
            "connected": self._connected,
            "message": "Unity: Connected" if self._connected else "Unity: Not running (start Unity Hub for terrain export)"
        }
