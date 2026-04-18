"""
Kingdom AI - Stratum Protocol Implementation
Handles mining pool connectivity via Stratum protocol for all 80 PoW cryptocurrencies
"""

import asyncio
import json
import socket
import ssl
import time
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from threading import Thread, Event
import hashlib
import struct

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StratumJob:
    """Represents a mining job from the pool"""
    job_id: str
    previous_hash: str
    coinbase1: str
    coinbase2: str
    merkle_branches: List[str]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool
    target: str = ""
    difficulty: float = 1.0
    algorithm: str = "sha256"

@dataclass
class PoolConfig:
    """Pool connection configuration"""
    host: str
    port: int
    username: str
    password: str
    algorithm: str
    ssl_enabled: bool = False
    backup_pools: List[Tuple[str, int]] = None

class StratumConnection:
    """Handles individual Stratum pool connection"""
    
    def __init__(self, pool_config: PoolConfig, coin: str):
        self.pool_config = pool_config
        self.coin = coin
        self.socket = None
        self.ssl_context = None
        self.connected = False
        self.subscribed = False
        self.authorized = False
        self.session_id = None
        self.extranonce1 = None
        self.extranonce2_size = 0
        self.difficulty = 1.0
        self.target = None
        self.current_job = None
        self.message_id = 1
        self.pending_requests = {}
        self.job_callback = None
        self.difficulty_callback = None
        self.connection_callback = None
        self._running = False
        self._thread = None
        self._stop_event = Event()
        
        if pool_config.ssl_enabled:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
    
    async def connect(self) -> bool:
        """Connect to mining pool"""
        try:
            logger.info(f"Connecting to {self.coin} pool: {self.pool_config.host}:{self.pool_config.port}")
            
            # Create socket connection
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(30)
            
            if self.pool_config.ssl_enabled:
                self.socket = self.ssl_context.wrap_socket(self.socket)
            
            await asyncio.get_event_loop().run_in_executor(
                None, self.socket.connect, (self.pool_config.host, self.pool_config.port)
            )
            
            self.connected = True
            logger.info(f"Connected to {self.coin} pool successfully")
            
            # Start message handling thread
            self._running = True
            self._thread = Thread(target=self._message_handler, daemon=True)
            self._thread.start()
            
            # Subscribe to mining notifications
            await self.subscribe()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.coin} pool: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from mining pool"""
        self._running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=5)
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.connected = False
        self.subscribed = False
        self.authorized = False
        logger.info(f"Disconnected from {self.coin} pool")
    
    async def subscribe(self) -> bool:
        """Subscribe to mining notifications"""
        try:
            # Send mining.subscribe
            subscribe_msg = {
                "id": self._get_next_id(),
                "method": "mining.subscribe",
                "params": [f"KingdomAI/{self.coin}"]
            }
            
            response = await self._send_request(subscribe_msg)
            if response and "result" in response:
                result = response["result"]
                if isinstance(result, list) and len(result) >= 2:
                    self.session_id = result[0][0][1] if result[0] else None
                    self.extranonce1 = result[1]
                    self.extranonce2_size = result[2]
                    self.subscribed = True
                    logger.info(f"Subscribed to {self.coin} pool - Session: {self.session_id}")
                    
                    # Authorize worker
                    await self.authorize()
                    return True
            
            logger.error(f"Failed to subscribe to {self.coin} pool")
            return False
            
        except Exception as e:
            logger.error(f"Subscription error for {self.coin}: {e}")
            return False
    
    async def authorize(self) -> bool:
        """Authorize worker with pool"""
        try:
            auth_msg = {
                "id": self._get_next_id(),
                "method": "mining.authorize",
                "params": [self.pool_config.username, self.pool_config.password]
            }
            
            response = await self._send_request(auth_msg)
            if response and response.get("result") is True:
                self.authorized = True
                logger.info(f"Authorized with {self.coin} pool")
                return True
            else:
                logger.error(f"Authorization failed for {self.coin} pool")
                return False
                
        except Exception as e:
            logger.error(f"Authorization error for {self.coin}: {e}")
            return False
    
    async def submit_share(self, job_id: str, extranonce2: str, ntime: str, nonce: str) -> bool:
        """Submit mining share to pool"""
        try:
            submit_msg = {
                "id": self._get_next_id(),
                "method": "mining.submit",
                "params": [
                    self.pool_config.username,
                    job_id,
                    extranonce2,
                    ntime,
                    nonce
                ]
            }
            
            response = await self._send_request(submit_msg)
            if response:
                if response.get("result") is True:
                    logger.info(f"Share accepted for {self.coin}")
                    return True
                else:
                    error = response.get("error", "Unknown error")
                    logger.warning(f"Share rejected for {self.coin}: {error}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Share submission error for {self.coin}: {e}")
            return False
    
    def _message_handler(self):
        """Handle incoming messages from pool"""
        buffer = ""
        
        while self._running and not self._stop_event.is_set():
            try:
                if not self.socket:
                    break
                
                data = self.socket.recv(4096)
                if not data:
                    break
                
                buffer += data.decode('utf-8')
                
                # Process complete messages
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            message = json.loads(line.strip())
                            self._handle_message(message)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e}")
                
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Message handler error for {self.coin}: {e}")
                break
        
        logger.info(f"Message handler stopped for {self.coin}")
    
    def _handle_message(self, message: Dict[str, Any]):
        """Handle individual message from pool"""
        try:
            # Handle responses to our requests
            if "id" in message and message["id"] in self.pending_requests:
                future = self.pending_requests.pop(message["id"])
                if not future.done():
                    future.set_result(message)
                return
            
            # Handle notifications
            if "method" in message:
                method = message["method"]
                params = message.get("params", [])
                
                if method == "mining.notify":
                    self._handle_job_notification(params)
                elif method == "mining.set_difficulty":
                    self._handle_difficulty_change(params)
                elif method == "mining.set_target":
                    self._handle_target_change(params)
                elif method == "client.reconnect":
                    self._handle_reconnect(params)
        
        except Exception as e:
            logger.error(f"Error handling message for {self.coin}: {e}")
    
    def _handle_job_notification(self, params: List[Any]):
        """Handle new mining job notification"""
        try:
            if len(params) >= 8:
                job = StratumJob(
                    job_id=params[0],
                    previous_hash=params[1],
                    coinbase1=params[2],
                    coinbase2=params[3],
                    merkle_branches=params[4],
                    version=params[5],
                    nbits=params[6],
                    ntime=params[7],
                    clean_jobs=params[8] if len(params) > 8 else False,
                    target=self.target or "",
                    difficulty=self.difficulty,
                    algorithm=self.pool_config.algorithm
                )
                
                self.current_job = job
                
                if self.job_callback:
                    self.job_callback(self.coin, job)
                
                logger.debug(f"New job for {self.coin}: {job.job_id}")
        
        except Exception as e:
            logger.error(f"Error handling job notification for {self.coin}: {e}")
    
    def _handle_difficulty_change(self, params: List[Any]):
        """Handle difficulty change notification"""
        try:
            if params:
                self.difficulty = float(params[0])
                # Calculate target from difficulty
                self.target = self._difficulty_to_target(self.difficulty)
                
                if self.difficulty_callback:
                    self.difficulty_callback(self.coin, self.difficulty)
                
                logger.info(f"Difficulty changed for {self.coin}: {self.difficulty}")
        
        except Exception as e:
            logger.error(f"Error handling difficulty change for {self.coin}: {e}")
    
    def _handle_target_change(self, params: List[Any]):
        """Handle target change notification"""
        try:
            if params:
                self.target = params[0]
                # Calculate difficulty from target
                self.difficulty = self._target_to_difficulty(self.target)
                
                if self.difficulty_callback:
                    self.difficulty_callback(self.coin, self.difficulty)
                
                logger.info(f"Target changed for {self.coin}: {self.target}")
        
        except Exception as e:
            logger.error(f"Error handling target change for {self.coin}: {e}")
    
    def _handle_reconnect(self, params: List[Any]):
        """Handle reconnection request"""
        try:
            if len(params) >= 3:
                host = params[0] or self.pool_config.host
                port = int(params[1]) if params[1] else self.pool_config.port
                wait_time = int(params[2]) if params[2] else 0
                
                logger.info(f"Pool requested reconnection for {self.coin}: {host}:{port} in {wait_time}s")
                
                # Schedule reconnection
                def reconnect():
                    time.sleep(wait_time)
                    self.disconnect()
                    self.pool_config.host = host
                    self.pool_config.port = port
                    # Reconnection will be handled by StratumClient
                
                Thread(target=reconnect, daemon=True).start()
        
        except Exception as e:
            logger.error(f"Error handling reconnect for {self.coin}: {e}")
    
    async def _send_request(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send request and wait for response"""
        try:
            if not self.connected or not self.socket:
                return None
            
            # Create future for response
            future = asyncio.Future()
            self.pending_requests[message["id"]] = future
            
            # Send message
            data = json.dumps(message) + '\n'
            await asyncio.get_event_loop().run_in_executor(
                None, self.socket.send, data.encode('utf-8')
            )
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(future, timeout=30)
                return response
            except asyncio.TimeoutError:
                logger.error(f"Request timeout for {self.coin}")
                return None
        
        except Exception as e:
            logger.error(f"Error sending request for {self.coin}: {e}")
            return None
    
    def _get_next_id(self) -> int:
        """Get next message ID"""
        current_id = self.message_id
        self.message_id += 1
        return current_id
    
    def _difficulty_to_target(self, difficulty: float) -> str:
        """Convert difficulty to target hex string"""
        # Bitcoin difficulty 1 target
        max_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
        target = int(max_target / difficulty)
        return f"{target:064x}"
    
    def _target_to_difficulty(self, target_hex: str) -> float:
        """Convert target hex string to difficulty"""
        max_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
        target = int(target_hex, 16)
        return max_target / target if target > 0 else 1.0

class StratumClient:
    """Main Stratum client managing multiple pool connections"""
    
    def __init__(self):
        self.connections: Dict[str, StratumConnection] = {}
        self.pool_configs: Dict[str, PoolConfig] = {}
        self.job_callbacks: List[Callable] = []
        self.difficulty_callbacks: List[Callable] = []
        self.connection_callbacks: List[Callable] = []
        self._running = False
        self._monitor_thread = None
        self._stop_event = Event()
    
    def add_pool(self, coin: str, pool_config: PoolConfig):
        """Add pool configuration for coin"""
        self.pool_configs[coin] = pool_config
        logger.info(f"Added pool config for {coin}: {pool_config.host}:{pool_config.port}")
    
    def add_job_callback(self, callback: Callable):
        """Add callback for new mining jobs"""
        self.job_callbacks.append(callback)
    
    def add_difficulty_callback(self, callback: Callable):
        """Add callback for difficulty changes"""
        self.difficulty_callbacks.append(callback)
    
    def add_connection_callback(self, callback: Callable):
        """Add callback for connection status changes"""
        self.connection_callbacks.append(callback)
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connect to all configured pools"""
        results = {}
        
        for coin, pool_config in self.pool_configs.items():
            try:
                connection = StratumConnection(pool_config, coin)
                
                # Set callbacks
                connection.job_callback = self._job_received
                connection.difficulty_callback = self._difficulty_changed
                connection.connection_callback = self._connection_status_changed
                
                # Connect to pool
                success = await connection.connect()
                results[coin] = success
                
                if success:
                    self.connections[coin] = connection
                    logger.info(f"Successfully connected to {coin} pool")
                else:
                    logger.error(f"Failed to connect to {coin} pool")
            
            except Exception as e:
                logger.error(f"Error connecting to {coin} pool: {e}")
                results[coin] = False
        
        # Start connection monitoring
        if any(results.values()):
            self._start_monitoring()
        
        return results
    
    async def disconnect_all(self):
        """Disconnect from all pools"""
        self._running = False
        self._stop_event.set()
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        for coin, connection in self.connections.items():
            try:
                connection.disconnect()
                logger.info(f"Disconnected from {coin} pool")
            except Exception as e:
                logger.error(f"Error disconnecting from {coin} pool: {e}")
        
        self.connections.clear()
    
    async def submit_share(self, coin: str, job_id: str, extranonce2: str, ntime: str, nonce: str) -> bool:
        """Submit share for specific coin"""
        if coin in self.connections:
            connection = self.connections[coin]
            if connection.connected and connection.authorized:
                return await connection.submit_share(job_id, extranonce2, ntime, nonce)
        
        logger.warning(f"Cannot submit share for {coin}: not connected or not authorized")
        return False
    
    def get_current_job(self, coin: str) -> Optional[StratumJob]:
        """Get current mining job for coin"""
        if coin in self.connections:
            return self.connections[coin].current_job
        return None
    
    def get_difficulty(self, coin: str) -> float:
        """Get current difficulty for coin"""
        if coin in self.connections:
            return self.connections[coin].difficulty
        return 1.0
    
    def is_connected(self, coin: str) -> bool:
        """Check if connected to pool for coin"""
        return coin in self.connections and self.connections[coin].connected
    
    def is_authorized(self, coin: str) -> bool:
        """Check if authorized with pool for coin"""
        return coin in self.connections and self.connections[coin].authorized
    
    def _job_received(self, coin: str, job: StratumJob):
        """Handle new job from pool"""
        for callback in self.job_callbacks:
            try:
                callback(coin, job)
            except Exception as e:
                logger.error(f"Error in job callback for {coin}: {e}")
    
    def _difficulty_changed(self, coin: str, difficulty: float):
        """Handle difficulty change from pool"""
        for callback in self.difficulty_callbacks:
            try:
                callback(coin, difficulty)
            except Exception as e:
                logger.error(f"Error in difficulty callback for {coin}: {e}")
    
    def _connection_status_changed(self, coin: str, connected: bool):
        """Handle connection status change"""
        for callback in self.connection_callbacks:
            try:
                callback(coin, connected)
            except Exception as e:
                logger.error(f"Error in connection callback for {coin}: {e}")
    
    def _start_monitoring(self):
        """Start connection monitoring thread"""
        self._running = True
        self._monitor_thread = Thread(target=self._monitor_connections, daemon=True)
        self._monitor_thread.start()
    
    def _monitor_connections(self):
        """Monitor and maintain pool connections"""
        while self._running and not self._stop_event.is_set():
            try:
                # Check all connections
                for coin, connection in list(self.connections.items()):
                    if not connection.connected:
                        logger.warning(f"Connection lost for {coin}, attempting reconnection...")
                        
                        # Try to reconnect
                        try:
                            asyncio.run(connection.connect())
                        except Exception as e:
                            logger.error(f"Reconnection failed for {coin}: {e}")
                
                # Wait before next check
                self._stop_event.wait(30)  # Check every 30 seconds
            
            except Exception as e:
                logger.error(f"Error in connection monitor: {e}")
                time.sleep(30)
        
        logger.info("Connection monitoring stopped")

# Global Stratum client instance
stratum_client = StratumClient()

def get_stratum_client() -> StratumClient:
    """Get global Stratum client instance"""
    return stratum_client
