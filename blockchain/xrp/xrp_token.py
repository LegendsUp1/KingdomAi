"""
XRP Token Module
Handles XRP token (IOU) creation and management
"""

import logging
from typing import Dict, List, Optional
from xrpl.models import Payment, TrustSet, Transaction
from xrpl.wallet import Wallet
from .xrp_client import XRPClient

logger = logging.getLogger(__name__)

class XRPToken:
    def __init__(self, client: XRPClient):
        self.client = client
        
    async def create_trustline(self, wallet: Wallet, issuer: str, currency: str, limit: str) -> Dict:
        """Create a trustline for a token"""
        try:
            trust_set = TrustSet(
                account=wallet.classic_address,
                limit_amount={
                    "currency": currency,
                    "issuer": issuer,
                    "value": limit
                }
            )
            
            response = await self.client.submit(trust_set, wallet)
            return {
                "status": "success",
                "tx_hash": response.result["tx_json"]["hash"],
                "result": response.result
            }
        except Exception as e:
            logger.error(f"Failed to create trustline: {e}")
            return {"status": "error", "message": str(e)}
            
    async def send_token(self, wallet: Wallet, destination: str, currency: str, 
                        issuer: str, amount: str) -> Dict:
        """Send tokens to a destination address"""
        try:
            payment = Payment(
                account=wallet.classic_address,
                destination=destination,
                amount={
                    "currency": currency,
                    "issuer": issuer,
                    "value": amount
                }
            )
            
            response = await self.client.submit(payment, wallet)
            return {
                "status": "success",
                "tx_hash": response.result["tx_json"]["hash"],
                "result": response.result
            }
        except Exception as e:
            logger.error(f"Failed to send token: {e}")
            return {"status": "error", "message": str(e)}
            
    async def get_token_balance(self, address: str, currency: str, issuer: str) -> Dict:
        """Get token balance for an address"""
        try:
            lines = await self.client.request_account_lines(address)
            for line in lines.result["lines"]:
                if line["currency"] == currency and line["account"] == issuer:
                    return {
                        "status": "success",
                        "balance": line["balance"]
                    }
            return {"status": "error", "message": "Token not found"}
        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            return {"status": "error", "message": str(e)}
            
    async def get_token_info(self, currency: str, issuer: str) -> Dict:
        """Get information about a token"""
        try:
            token_info = await self.client.request_token_information(currency, issuer)
            return {
                "status": "success",
                "token": token_info.result
            }
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return {"status": "error", "message": str(e)}
