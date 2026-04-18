"""
XRP Wallet Module
Handles XRP wallet creation, management, and transactions
"""

import json
import logging
from typing import Dict, Optional
from xrpl.wallet import Wallet as XRPLWallet
from xrpl.core.keypairs import generate_seed
from .xrp_client import XRPClient

logger = logging.getLogger(__name__)

class XRPWallet:
    def __init__(self, client: XRPClient):
        self.client = client
        self._wallet: Optional[XRPLWallet] = None
        
    def create_wallet(self) -> Dict:
        """Create a new XRP wallet"""
        try:
            seed = generate_seed()
            self._wallet = XRPLWallet.from_seed(seed)
            return {
                "status": "success",
                "address": self._wallet.classic_address,
                "seed": seed
            }
        except Exception as e:
            logger.error(f"Failed to create wallet: {e}")
            return {"status": "error", "message": str(e)}
            
    def load_wallet(self, seed: str) -> Dict:
        """Load an existing wallet from seed"""
        try:
            self._wallet = XRPLWallet.from_seed(seed)
            return {
                "status": "success",
                "address": self._wallet.classic_address
            }
        except Exception as e:
            logger.error(f"Failed to load wallet: {e}")
            return {"status": "error", "message": str(e)}
            
    async def get_balance(self) -> Dict:
        """Get wallet balance"""
        if not self._wallet:
            return {"status": "error", "message": "No wallet loaded"}
            
        try:
            account_info = await self.client.get_account_info(self._wallet.classic_address)
            if account_info:
                return {
                    "status": "success",
                    "balance": account_info.result["account_data"]["Balance"]
                }
            return {"status": "error", "message": "Failed to get account info"}
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {"status": "error", "message": str(e)}
