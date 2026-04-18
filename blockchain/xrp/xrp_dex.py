"""
XRP DEX Module
Handles decentralized exchange operations on the XRP Ledger
"""

import logging
from typing import Dict, List, Optional
from xrpl.models import Offer, OfferCreate, OfferCancel
from xrpl.wallet import Wallet
from .xrp_client import XRPClient

logger = logging.getLogger(__name__)

class XRPDex:
    def __init__(self, client: XRPClient):
        self.client = client
        
    async def create_offer(self, wallet: Wallet, taker_gets: Dict, taker_pays: Dict) -> Dict:
        """Create a new offer on the DEX"""
        try:
            offer = OfferCreate(
                account=wallet.classic_address,
                taker_gets=taker_gets,
                taker_pays=taker_pays
            )
            
            response = await self.client.submit(offer, wallet)
            return {
                "status": "success",
                "offer_id": response.result["tx_json"]["hash"],
                "result": response.result
            }
        except Exception as e:
            logger.error(f"Failed to create offer: {e}")
            return {"status": "error", "message": str(e)}
            
    async def cancel_offer(self, wallet: Wallet, offer_sequence: int) -> Dict:
        """Cancel an existing offer"""
        try:
            cancel = OfferCancel(
                account=wallet.classic_address,
                offer_sequence=offer_sequence
            )
            
            response = await self.client.submit(cancel, wallet)
            return {
                "status": "success",
                "result": response.result
            }
        except Exception as e:
            logger.error(f"Failed to cancel offer: {e}")
            return {"status": "error", "message": str(e)}
            
    async def get_offers(self, address: str) -> Dict:
        """Get all offers for an address"""
        try:
            offers = await self.client.request_account_offers(address)
            return {
                "status": "success",
                "offers": offers.result["offers"]
            }
        except Exception as e:
            logger.error(f"Failed to get offers: {e}")
            return {"status": "error", "message": str(e)}
            
    async def get_order_book(self, taker_gets: Dict, taker_pays: Dict) -> Dict:
        """Get the order book for a trading pair"""
        try:
            book_offers = await self.client.request_book_offers(
                taker_gets=taker_gets,
                taker_pays=taker_pays
            )
            return {
                "status": "success",
                "offers": book_offers.result["offers"]
            }
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            return {"status": "error", "message": str(e)}
