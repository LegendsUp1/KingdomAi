"""
Wallet Integration Module for Kingdom AI

Handles integration between wallet, trading, and mining systems
using the event bus for real-time communication.
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
import time

from core.base_component import BaseComponent
from core.event_bus import EventBus
from core.wallet_manager import WalletManager

logger = logging.getLogger('KingdomAI.WalletIntegration')

class WalletIntegration(BaseComponent):
    """
    Handles integration between wallet, trading, and mining systems.
    Manages fund transfers, profit distribution, and real-time updates.
    """
    
    def __init__(self, wallet_manager: WalletManager, event_bus: Optional[EventBus] = None, 
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Wallet Integration component.
        
        Args:
            wallet_manager: Instance of WalletManager
            event_bus: Event bus instance for communication
            config: Configuration dictionary
        """
        super().__init__(event_bus=event_bus, config=config or {})
        self.wallet_manager = wallet_manager
        self.running = False
        
        # Track pending transactions
        self.pending_transactions: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Wallet Integration initialized")
    
    async def initialize(self) -> bool:
        """Initialize the wallet integration component."""
        if not await super().initialize():
            return False
            
        # Subscribe to relevant events
        if self.event_bus:
            # Trading system events
            self.event_bus.subscribe_sync("trading.profit_earned", self._handle_trading_profit)
            self.event_bus.subscribe_sync("trading.funds_request", self._handle_funds_request)
            
            # Mining system events
            self.event_bus.subscribe_sync("mining.reward_earned", self._handle_mining_reward)
            self.event_bus.subscribe_sync("mining.payout_completed", self._handle_mining_payout)
            
            # Wallet events
            self.event_bus.subscribe_sync("wallet.balance_updated", self._handle_balance_update)
            self.event_bus.subscribe_sync("wallet.transaction_completed", self._handle_transaction_completed)
            
            logger.info("Wallet Integration event subscriptions set up")
        
        self.running = True
        return True
    
    async def start(self) -> bool:
        """Start the wallet integration service."""
        if not self.running:
            await self.initialize()
        return True
    
    async def stop(self) -> bool:
        """Stop the wallet integration service."""
        self.running = False
        return True
    
    # Event Handlers
    
    async def _handle_trading_profit(self, event_id: str, event_data: Dict[str, Any]) -> None:
        """
        Handle trading profit events.
        
        Args:
            event_id: Unique event ID
            event_data: {
                'amount': Decimal,  # Profit amount
                'currency': str,    # Currency code (e.g., 'BTC', 'ETH')
                'trade_id': str,    # Reference to the trade
                'timestamp': float  # When the profit was earned
            }
        """
        try:
            amount = Decimal(str(event_data.get('amount', 0)))
            currency = event_data.get('currency', 'BTC').upper()
            trade_id = event_data.get('trade_id', 'unknown')
            
            if amount <= 0:
                logger.warning(f"Received non-positive profit amount: {amount}")
                return
                
            logger.info(f"Processing trading profit: {amount} {currency} from trade {trade_id}")
            
            # Get the trading wallet address from config or use a default
            wallet_address = self.config.get('trading_wallet', {}).get(currency)
            if not wallet_address:
                logger.error(f"No trading wallet configured for {currency}")
                return
            
            # Create a transaction to credit the trading profit
            tx_data = {
                'from_address': 'trading_system',
                'to_address': wallet_address,
                'amount': float(amount),
                'currency': currency,
                'tx_type': 'trading_profit',
                'reference_id': trade_id,
                'metadata': {
                    'source': 'trading_system',
                    'description': f'Trading profit from trade {trade_id}'
                }
            }
            
            # Publish transaction request
            if self.event_bus:
                self.event_bus.publish('wallet.create_transaction', tx_data)
                
        except Exception as e:
            logger.error(f"Error handling trading profit: {e}", exc_info=True)
    
    async def _handle_funds_request(self, event_id: str, event_data: Dict[str, Any]) -> None:
        """
        Handle requests for funds from the trading system.
        
        Args:
            event_id: Unique event ID
            event_data: {
                'amount': Decimal,      # Amount requested
                'currency': str,        # Currency code
                'purpose': str,         # Purpose of the request
                'request_id': str,      # Unique request ID
                'target_address': str,  # Optional target address
                'metadata': dict        # Additional metadata
            }
        """
        try:
            amount = Decimal(str(event_data.get('amount', 0)))
            currency = event_data.get('currency', 'BTC').upper()
            purpose = event_data.get('purpose', 'trading')
            request_id = event_data.get('request_id')
            target_address = event_data.get('target_address')
            
            if amount <= 0:
                logger.warning(f"Invalid amount requested: {amount}")
                await self._send_funds_response(False, request_id, "Invalid amount")
                return
                
            logger.info(f"Processing funds request: {amount} {currency} for {purpose}")
            
            # Get the source wallet address from config or use a default
            source_wallet = self.config.get('trading_wallet', {}).get(currency)
            if not source_wallet:
                error_msg = f"No trading wallet configured for {currency}"
                logger.error(error_msg)
                await self._send_funds_response(False, request_id, error_msg)
                return
            
            # If no target address, use the trading system's hot wallet
            if not target_address:
                target_address = self.config.get('trading_hot_wallet', {}).get(currency)
                if not target_address:
                    error_msg = f"No target address provided and no default hot wallet for {currency}"
                    logger.error(error_msg)
                    await self._send_funds_response(False, request_id, error_msg)
                    return
            
            # Create a transaction to send funds to the trading system
            tx_data = {
                'from_address': source_wallet,
                'to_address': target_address,
                'amount': float(amount),
                'currency': currency,
                'tx_type': 'trading_allocation',
                'reference_id': request_id,
                'metadata': {
                    'purpose': purpose,
                    'description': f'Funds allocated for {purpose}'
                }
            }
            
            # Store the pending transaction
            tx_id = f"tx_{int(time.time())}_{request_id}"
            self.pending_transactions[tx_id] = {
                'type': 'trading_allocation',
                'request_id': request_id,
                'amount': amount,
                'currency': currency,
                'status': 'pending',
                'metadata': tx_data.get('metadata', {})
            }
            
            # Publish transaction request
            if self.event_bus:
                self.event_bus.publish('wallet.create_transaction', {
                    **tx_data,
                    'callback_event': 'wallet.trading_allocation_processed',
                    'callback_data': {'tx_id': tx_id}
                })
                
        except Exception as e:
            error_msg = f"Error processing funds request: {e}"
            logger.error(error_msg, exc_info=True)
            await self._send_funds_response(False, request_id, str(e))
    
    async def _handle_mining_reward(self, event_id: str, event_data: Dict[str, Any]) -> None:
        """
        Handle mining reward events.
        
        Args:
            event_id: Unique event ID
            event_data: {
                'amount': Decimal,      # Reward amount
                'currency': str,        # Currency code (e.g., 'BTC', 'ETH')
                'block_height': int,    # Block height
                'miner_address': str,   # Address of the miner
                'timestamp': float       # When the reward was earned
            }
        """
        try:
            amount = Decimal(str(event_data.get('amount', 0)))
            currency = event_data.get('currency', 'BTC').upper()
            block_height = event_data.get('block_height')
            miner_address = event_data.get('miner_address')
            
            if amount <= 0:
                logger.warning(f"Received non-positive mining reward: {amount}")
                return
                
            logger.info(f"Processing mining reward: {amount} {currency} for block {block_height}")
            
            # Get the mining wallet address from config or use the provided miner address
            wallet_address = self.config.get('mining_wallet', {}).get(currency, miner_address)
            if not wallet_address:
                logger.error(f"No mining wallet configured for {currency}")
                return
            
            # Create a transaction to record the mining reward
            tx_data = {
                'from_address': 'mining_reward',
                'to_address': wallet_address,
                'amount': float(amount),
                'currency': currency,
                'tx_type': 'mining_reward',
                'reference_id': f"block_{block_height}",
                'metadata': {
                    'source': 'mining_system',
                    'block_height': block_height,
                    'description': f'Mining reward for block {block_height}'
                }
            }
            
            # Publish transaction request
            if self.event_bus:
                self.event_bus.publish('wallet.create_transaction', tx_data)
                
        except Exception as e:
            logger.error(f"Error handling mining reward: {e}", exc_info=True)
    
    async def _handle_mining_payout(self, event_id: str, event_data: Dict[str, Any]) -> None:
        """
        Handle mining payout events.
        
        Args:
            event_id: Unique event ID
            event_data: {
                'amount': Decimal,      # Payout amount
                'currency': str,        # Currency code
                'payout_id': str,       # Payout reference ID
                'timestamp': float,     # When the payout was processed
                'recipients': list[dict] # List of recipient addresses and amounts
            }
        """
        try:
            amount = Decimal(str(event_data.get('amount', 0)))
            currency = event_data.get('currency', 'BTC').upper()
            payout_id = event_data.get('payout_id')
            recipients = event_data.get('recipients', [])
            
            if amount <= 0:
                logger.warning(f"Received non-positive mining payout: {amount}")
                return
                
            logger.info(f"Processing mining payout: {amount} {currency} (payout {payout_id})")
            
            # Process each recipient
            for recipient in recipients:
                recipient_address = recipient.get('address')
                recipient_amount = Decimal(str(recipient.get('amount', 0)))
                
                if not recipient_address or recipient_amount <= 0:
                    continue
                
                # Create a transaction for each recipient
                tx_data = {
                    'from_address': 'mining_pool',
                    'to_address': recipient_address,
                    'amount': float(recipient_amount),
                    'currency': currency,
                    'tx_type': 'mining_payout',
                    'reference_id': f"payout_{payout_id}",
                    'metadata': {
                        'source': 'mining_pool',
                        'payout_id': payout_id,
                        'description': f'Mining pool payout {payout_id}'
                    }
                }
                
                # Publish transaction request
                if self.event_bus:
                    self.event_bus.publish('wallet.create_transaction', tx_data)
            
            # Publish payout completion event
            if self.event_bus:
                self.event_bus.publish('wallet.mining_payout_completed', {
                    'payout_id': payout_id,
                    'total_amount': float(amount),
                    'currency': currency,
                    'recipient_count': len(recipients),
                    'timestamp': time.time()
                })
                
        except Exception as e:
            logger.error(f"Error handling mining payout: {e}", exc_info=True)
    
    async def _handle_balance_update(self, event_id: str, event_data: Dict[str, Any]) -> None:
        """
        Handle wallet balance update events.
        
        Args:
            event_id: Unique event ID
            event_data: {
                'wallet_address': str,  # Wallet address
                'currency': str,        # Currency code
                'new_balance': Decimal, # Updated balance
                'change': Decimal,      # Amount changed
                'timestamp': float      # When the update occurred
            }
        """
        try:
            wallet_address = event_data.get('wallet_address')
            currency = event_data.get('currency', 'BTC').upper()
            new_balance = Decimal(str(event_data.get('new_balance', 0)))
            
            logger.debug(f"Balance updated - {wallet_address} ({currency}): {new_balance}")
            
            # Forward the update to relevant components
            if self.event_bus:
                # Forward to UI for display
                self.event_bus.publish('ui.update_balance', {
                    'wallet_address': wallet_address,
                    'currency': currency,
                    'balance': float(new_balance),
                    'timestamp': time.time()
                })
                
                # Notify trading system if this is a trading wallet
                if self.config.get('trading_wallet', {}).get(currency) == wallet_address:
                    self.event_bus.publish('trading.balance_updated', {
                        'wallet_address': wallet_address,
                        'currency': currency,
                        'balance': float(new_balance),
                        'timestamp': time.time()
                    })
                
                # Notify mining system if this is a mining wallet
                if self.config.get('mining_wallet', {}).get(currency) == wallet_address:
                    self.event_bus.publish('mining.balance_updated', {
                        'wallet_address': wallet_address,
                        'currency': currency,
                        'balance': float(new_balance),
                        'timestamp': time.time()
                    })
                    
        except Exception as e:
            logger.error(f"Error handling balance update: {e}", exc_info=True)
    
    async def _handle_transaction_completed(self, event_id: str, event_data: Dict[str, Any]) -> None:
        """
        Handle transaction completion events.
        
        Args:
            event_id: Unique event ID
            event_data: {
                'tx_id': str,           # Transaction ID
                'status': str,          # 'completed', 'failed', etc.
                'tx_data': dict,        # Transaction details
                'timestamp': float      # When the transaction was completed
            }
        """
        try:
            tx_id = event_data.get('tx_id')
            status = event_data.get('status')
            tx_data = event_data.get('tx_data', {})
            
            logger.info(f"Transaction {tx_id} {status}")
            
            # Check if this is a pending trading allocation
            if tx_id in self.pending_transactions and status == 'completed':
                pending_tx = self.pending_transactions[tx_id]
                if pending_tx['type'] == 'trading_allocation':
                    # Notify trading system that funds are available
                    if self.event_bus:
                        self.event_bus.publish('trading.funds_allocated', {
                            'request_id': pending_tx['request_id'],
                            'amount': pending_tx['amount'],
                            'currency': pending_tx['currency'],
                            'wallet_address': tx_data.get('to_address'),
                            'tx_id': tx_id,
                            'timestamp': time.time()
                        })
                
                # Clean up
                del self.pending_transactions[tx_id]
            
            # Forward the transaction to relevant components
            if self.event_bus:
                # Forward to UI for display
                self.event_bus.publish('ui.update_transaction', {
                    'tx_id': tx_id,
                    'status': status,
                    'tx_data': tx_data,
                    'timestamp': time.time()
                })
                
        except Exception as e:
            logger.error(f"Error handling transaction completion: {e}", exc_info=True)
    
    # Helper Methods
    
    async def _send_funds_response(self, success: bool, request_id: Optional[str], message: str = "") -> None:
        """
        Send a response to a funds request.
        
        Args:
            success: Whether the request was successful
            request_id: Original request ID
            message: Response message
        """
        if self.event_bus and request_id:
            self.event_bus.publish('trading.funds_response', {
                'success': success,
                'request_id': request_id,
                'message': message,
                'timestamp': time.time()
            })
