"""
XRP Transaction Module
Handles XRP transaction creation, signing, and submission
"""

import logging
from typing import Dict, Optional
from xrpl.models import Payment, Transaction
from xrpl.wallet import Wallet
from .xrp_client import XRPClient

logger = logging.getLogger(__name__)

class XRPTransaction:
    def __init__(self, client: XRPClient):
        self.client = client
        
    async def send_xrp(self, wallet: Wallet, destination: str, amount: str) -> Dict:
        """Send XRP to destination address"""
        try:
            # Create payment transaction
            payment = Payment(
                account=wallet.classic_address,
                destination=destination,
                amount=amount
            )
            
            # Sign and submit transaction
            response = await self.client.submit(payment, wallet)
            
            return {
                "status": "success",
                "tx_hash": response.result["tx_json"]["hash"],
                "result": response.result
            }
        except Exception as e:
            logger.error(f"Failed to send XRP: {e}")
            return {"status": "error", "message": str(e)}
            
    async def get_transaction_info(self, tx_hash: str) -> Dict:
        """Get information about a specific transaction"""
        try:
            tx_info = await self.client.request_transaction(tx_hash)
            return {
                "status": "success",
                "transaction": tx_info.result
            }
        except Exception as e:
            logger.error(f"Failed to get transaction info: {e}")
            return {"status": "error", "message": str(e)}
            
    async def get_transaction_history(self, address: str, limit: int = 10) -> Dict:
        """Get transaction history for an address"""
        try:
            history = await self.client.request_account_tx(address, limit=limit)
            return {
                "status": "success",
                "transactions": history.result["transactions"]
            }
        except Exception as e:
            logger.error(f"Failed to get transaction history: {e}")
            return {"status": "error", "message": str(e)}
