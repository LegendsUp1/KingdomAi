#!/usr/bin/env python3
"""
2026 SOTA Serial Port Management for Kingdom AI
Provides robust serial port access with proper error handling and conflict resolution
"""

import logging
import time
import threading
from typing import Optional, Dict, Any
from contextlib import contextmanager
import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)

class SerialPortManager:
    """
    2026 SOTA Serial Port Manager
    
    Features:
    - Port conflict detection and resolution
    - Automatic retry with exponential backoff
    - Port locking mechanism to prevent conflicts
    - Graceful cleanup and resource management
    """
    
    def __init__(self):
        self._locked_ports: Dict[str, threading.Lock] = {}
        self._active_connections: Dict[str, serial.Serial] = {}
        self._lock = threading.Lock()
        
    @contextmanager
    def get_serial_connection(self, port: str, baudrate: int = 9600, timeout: float = 1.0, **kwargs):
        """
        2026 SOTA: Context manager for safe serial port access
        
        Args:
            port: COM port name (e.g., 'COM6')
            baudrate: Serial baud rate
            timeout: Connection timeout
            **kwargs: Additional serial parameters
            
        Yields:
            serial.Serial: Active serial connection
            
        Raises:
            SerialPortError: If port cannot be accessed
        """
        connection = None
        try:
            # Acquire port lock to prevent conflicts
            port_lock = self._get_port_lock(port)
            port_lock.acquire()
            
            # 2026 SOTA: Check if port is already in use
            if self._is_port_in_use(port):
                logger.warning(f"Port {port} appears to be in use, attempting to free it")
                self._free_port(port)
                time.sleep(0.5)  # Brief pause for port to become available
            
            # 2026 SOTA: Create connection with retry logic
            connection = self._create_connection_with_retry(port, baudrate, timeout, **kwargs)
            yield connection
            
        finally:
            # 2026 SOTA: Ensure proper cleanup
            if connection:
                try:
                    connection.close()
                except Exception as e:
                    logger.warning(f"Error closing serial connection: {e}")
            
            # Release port lock
            if port in self._locked_ports:
                self._locked_ports[port].release()
    
    def _get_port_lock(self, port: str) -> threading.Lock:
        """Get or create a lock for the specific port"""
        with self._lock:
            if port not in self._locked_ports:
                self._locked_ports[port] = threading.Lock()
            return self._locked_ports[port]
    
    def _is_port_in_use(self, port: str) -> bool:
        """Check if a port is currently in use by another process"""
        try:
            # Try to open port briefly to check if it's available
            test_conn = serial.Serial(port, timeout=0.1)
            test_conn.close()
            return False
        except (serial.SerialException, OSError) as e:
            if "Access is denied" in str(e) or "Permission denied" in str(e):
                return True
            return False
    
    def _free_port(self, port: str):
        """Attempt to free a port that's in use"""
        try:
            # 2026 SOTA: Try multiple approaches to free the port
            approaches = [
                lambda: self._close_existing_connection(port),
                lambda: self._reset_port(port),
                lambda: self._wait_for_port_release(port)
            ]
            
            for approach in approaches:
                try:
                    approach()
                    if not self._is_port_in_use(port):
                        logger.info(f"Successfully freed port {port}")
                        return
                except Exception as e:
                    logger.debug(f"Port freeing approach failed: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to free port {port}: {e}")
    
    def _close_existing_connection(self, port: str):
        """Close any existing connection to the port"""
        if port in self._active_connections:
            try:
                self._active_connections[port].close()
                del self._active_connections[port]
                logger.debug(f"Closed existing connection to {port}")
            except Exception as e:
                logger.debug(f"Error closing existing connection: {e}")
    
    def _reset_port(self, port: str):
        """Reset the port (Windows specific)"""
        try:
            import subprocess
            # On Windows, try to reset the port using PowerShell
            result = subprocess.run([
                'powershell', '-Command',
                f'Get-WmiObject Win32_SerialPort | Where-Object {{$_.DeviceID -like "*{port.replace("COM", "")}*"}} | ForEach-Object {{$_.Disable(); $_.Enable()}}'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                logger.debug(f"Port {port} reset successfully")
        except Exception as e:
            logger.debug(f"Port reset failed: {e}")
    
    def _wait_for_port_release(self, port: str):
        """Wait for the port to be released"""
        max_wait = 5.0
        wait_interval = 0.5
        elapsed = 0.0
        
        while elapsed < max_wait:
            if not self._is_port_in_use(port):
                logger.debug(f"Port {port} released after {elapsed:.1f}s")
                return
            time.sleep(wait_interval)
            elapsed += wait_interval
    
    def _create_connection_with_retry(self, port: str, baudrate: int, timeout: float, **kwargs) -> serial.Serial:
        """Create serial connection with 2026 SOTA retry logic"""
        max_retries = 3
        base_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                # 2026 SOTA: Use optimal serial settings
                connection = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=timeout,
                    write_timeout=timeout,
                    inter_byte_timeout=0.1,
                    **kwargs
                )
                
                # Test the connection
                if connection.is_open:
                    self._active_connections[port] = connection
                    logger.info(f"Successfully connected to {port} on attempt {attempt + 1}")
                    return connection
                else:
                    raise serial.SerialException("Connection failed to open")
                    
            except (serial.SerialException, OSError) as e:
                if attempt == max_retries - 1:
                    raise SerialPortError(f"Failed to connect to {port} after {max_retries} attempts: {e}")
                
                # Exponential backoff
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Connection attempt {attempt + 1} failed for {port}, retrying in {delay:.1f}s: {e}")
                time.sleep(delay)

        raise SerialPortError(f"Failed to connect to {port} after {max_retries} attempts")
    
    def list_available_ports(self) -> list:
        """List all available serial ports with detailed information"""
        ports = []
        try:
            for port_info in serial.tools.list_ports.comports():
                ports.append({
                    'device': port_info.device,
                    'name': port_info.name or 'Unknown',
                    'description': port_info.description or 'No description',
                    'hwid': port_info.hwid or 'No HWID',
                    'vid': port_info.vid,
                    'pid': port_info.pid,
                    'serial_number': port_info.serial_number,
                    'location': port_info.location,
                    'manufacturer': port_info.manufacturer or 'Unknown',
                    'product': port_info.product or 'Unknown'
                })
        except Exception as e:
            logger.error(f"Error listing serial ports: {e}")
        
        return ports
    
    def cleanup(self):
        """Clean up all active connections and locks"""
        with self._lock:
            # Close all active connections
            for port, connection in self._active_connections.items():
                try:
                    connection.close()
                    logger.debug(f"Closed connection to {port}")
                except Exception as e:
                    logger.warning(f"Error closing connection to {port}: {e}")
            
            self._active_connections.clear()
            self._locked_ports.clear()
            logger.info("Serial port manager cleaned up")


class SerialPortError(Exception):
    """Custom exception for serial port errors"""
    pass


# Global instance for application-wide use
serial_manager = SerialPortManager()
