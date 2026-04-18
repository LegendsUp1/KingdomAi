"""
XRP Client Module
Handles core XRP Ledger connectivity and interactions
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
import websockets
from xrpl.clients import JsonRpcClient, WebsocketClient
from xrpl.models import ServerInfo, AccountInfo
from xrpl.wallet import Wallet

logger = logging.getLogger(__name__)

class XRPClient:
    def __init__(self, config_path: str = "config/config.json"):
        """Initialize XRP client with configuration"""
        self.config = self._load_config(config_path)
        self.node_url = self.config["blockchain"]["xrp"]["node_url"]
        self.fallback_nodes = self.config["blockchain"]["xrp"]["fallback_nodes"]
        self.client: Optional[WebsocketClient] = None
        self.connected = False
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
            
    async def connect(self) -> bool:
        """Establish connection to XRP Ledger"""
        try:
            self.client = WebsocketClient(self.node_url)
            await self.client.connect()
            self.connected = True
            logger.info("Connected to XRP Ledger")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return await self._try_fallback_nodes()
            
    async def _try_fallback_nodes(self) -> bool:
        """Attempt connection to fallback nodes"""
        for node in self.fallback_nodes:
            try:
                self.client = WebsocketClient(node)
                await self.client.connect()
                self.connected = True
                logger.info(f"Connected to fallback node: {node}")
                return True
            except Exception as e:
                logger.error(f"Failed to connect to fallback node {node}: {e}")
        return False
        
    async def get_server_info(self) -> Optional[ServerInfo]:
        """Get XRP Ledger server information"""
        if not self.connected:
            await self.connect()
        try:
            return await self.client.request(ServerInfo())
        except Exception as e:
            logger.error(f"Failed to get server info: {e}")
            return None
            
    async def get_account_info(self, address: str) -> Optional[AccountInfo]:
        """Get account information for XRP address"""
        if not self.connected:
            await self.connect()
        try:
            return await self.client.request(AccountInfo(account=address))
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return None
            
    async def close(self):
        """Close connection to XRP Ledger"""
        if self.client and self.connected:
            await self.client.disconnect()
            self.connected = False
            logger.info("Disconnected from XRP Ledger")
