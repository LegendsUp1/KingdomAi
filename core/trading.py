"""Trading system for Kingdom AI."""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from core.base_component import BaseComponent

class TradingSystem(BaseComponent):
    """Cryptocurrency trading system."""
    
    def __init__(self, wallet, market_api, event_bus=None, config: Dict[str, Any] = None):
        """Initialize trading system.
        
        Args:
            wallet: WalletManager instance
            market_api: MarketAPI instance
            event_bus: EventBus instance
            config: Trading configuration
        """
        super().__init__(name="TradingSystem", event_bus=event_bus)
        self.wallet = wallet
        self.market_api = market_api
        self.config = config or {}
        self.logger = logging.getLogger("KingdomAI.TradingSystem")
        
        # Trading state
        self.is_trading = False
        self.positions: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.api_keys: Dict[str, Dict[str, str]] = {}
        self.active_markets: List[str] = []
        
        # Strategy instances
        self.strategies: Dict[str, Dict[str, Any]] = {}
        self.active_strategies = []
        self.strategy_tasks = []
        self.market_data: Dict[str, Dict[str, Any]] = {}
        self.wallet_balances: Dict[str, Any] = {}
        
        # Load configuration
        self.load_config()
        
    async def initialize(self) -> bool:
        """Initialize trading system asynchronously.
        
        Returns:
            bool: True if initialized successfully
        """
        try:
            self.logger.info("Initializing trading system...")
            
            # Verify market API is available
            if not self.market_api:
                self.logger.error("Market API not provided")
                return False
                
            # Verify wallet is available
            if not self.wallet:
                self.logger.error("Wallet not provided")
                return False
                
            # Load active markets from config
            self.active_markets = self.config.get("active_markets", [])
            
            # Subscribe to market events
            if self.event_bus:
                await self.event_bus.subscribe_sync("market.update", self._handle_market_update)
                await self.event_bus.subscribe_sync("market.error", self._handle_market_error)
                await self.event_bus.subscribe_sync("wallet.update", self._handle_wallet_update)
                
            # Load trading history
            self._load_trading_history()
            
            # Initialize strategies
            await self._initialize_strategies()
            
            self.logger.info("Trading system initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing trading system: {e}")
            return False
    
    async def start(self) -> bool:
        """Start trading system.
        
        Returns:
            bool: True if started successfully
        """
        try:
            if self.is_trading:
                self.logger.warning("Trading system already started")
                return True
                
            self.logger.info("Starting trading system...")
            
            # Start strategies
            for strategy in self.active_strategies:
                task = asyncio.create_task(strategy.run())
                self.strategy_tasks.append(task)
                
            self.is_trading = True
            
            # Notify GUI that trading has started
            if self.event_bus:
                await self.event_bus.publish("trading.status", {
                    "status": "started",
                    "active_strategies": len(self.active_strategies),
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info("Trading system started")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting trading system: {e}")
            return False
            
    async def stop(self) -> bool:
        """Stop trading system.
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.is_trading:
                self.logger.warning("Trading system not running")
                return True
                
            self.logger.info("Stopping trading system...")
            
            # Cancel strategy tasks
            for task in self.strategy_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to be cancelled
            if self.strategy_tasks:
                await asyncio.gather(*self.strategy_tasks, return_exceptions=True)
                self.strategy_tasks.clear()
                
            self.is_trading = False
            
            # Save state before stopping
            self.save_state()
            
            # Notify GUI that trading has stopped
            if self.event_bus:
                await self.event_bus.publish("trading.status", {
                    "status": "stopped",
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info("Trading system stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping trading system: {e}")
            return False
            
    def initialize_sync(self):
        """Synchronous version of initialize"""
        return True

    def load_config(self) -> None:
        """Load trading configuration.

        API keys are loaded from per-user storage when the wallet's active
        user is a consumer, falling back to the global config only for the
        owner ('creator').
        """
        try:
            config_path = Path("config/trading.json")
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    self.config = json.load(f)

            user_id = getattr(self.wallet, "_active_user_id", "creator") if self.wallet else "creator"
            keys_path = None
            if user_id and user_id != "creator":
                user_keys = Path("data") / "wallets" / "users" / user_id / "api_keys.json"
                if user_keys.exists():
                    keys_path = user_keys
            if keys_path is None:
                candidate = Path("config/api_keys.json")
                if candidate.exists() and (user_id == "creator" or not user_id):
                    keys_path = candidate

            if keys_path and keys_path.exists():
                with open(keys_path, encoding="utf-8") as f:
                    self.api_keys = json.load(f)
                    
            self.logger.info("Loaded trading configuration (user=%s)", user_id)
            
        except Exception as e:
            self.logger.error(f"Error loading trading configuration: {e}")
            
    def _save_trading_history(self) -> None:
        """Save trading history to disk."""
        try:
            history_path = Path("data/trading_history.json")
            history_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump({
                    "positions": self.positions,
                    "trade_history": self.trade_history,
                    "last_update": datetime.now().isoformat()
                }, f, indent=2)
                
            self.logger.debug("Saved trading history")
            
        except Exception as e:
            self.logger.error(f"Error saving trading history: {e}")
            
    def _load_trading_history(self) -> None:
        """Load trading history from disk."""
        try:
            history_path = Path("data/trading_history.json")
            if history_path.exists():
                with open(history_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.positions = data.get("positions", [])
                    self.trade_history = data.get("trade_history", [])
                    
                self.logger.debug(f"Loaded trading history with {len(self.trade_history)} trades")
                
        except Exception as e:
            self.logger.error(f"Error loading trading history: {e}")
            
    async def _initialize_strategies(self) -> None:
        """Initialize trading strategies from configuration."""
        try:
            strategy_configs = self.config.get("strategies", {})
            for name, cfg in strategy_configs.items():
                enabled = cfg.get("enabled", True)
                if enabled:
                    self.strategies[name] = {
                        "name": name,
                        "type": cfg.get("type", "default"),
                        "params": cfg.get("params", {}),
                        "active": False,
                    }
            self.logger.info(f"Initialized {len(self.strategies)} trading strategies")
        except Exception as e:
            self.logger.error(f"Error initializing strategies: {e}")

    async def _handle_market_update(self, data) -> None:
        """Handle market update events — route to active strategies and update state."""
        try:
            symbol = data.get("symbol", "")
            price = data.get("price", 0.0)
            if symbol and price:
                self.market_data[symbol] = {
                    "price": price,
                    "volume": data.get("volume", 0.0),
                    "timestamp": data.get("timestamp"),
                }
                if self.event_bus:
                    self.event_bus.publish("trading.market.updated", {
                        "symbol": symbol, "price": price
                    })
        except Exception as e:
            self.logger.error(f"Error handling market update: {e}")

    async def _handle_market_error(self, data) -> None:
        """Handle market error events — log and publish alert."""
        try:
            error_msg = data.get("error", "Unknown market error")
            source = data.get("source", "unknown")
            self.logger.warning(f"Market error from {source}: {error_msg}")
            if self.event_bus:
                self.event_bus.publish("trading.alert", {
                    "type": "market_error", "source": source, "message": error_msg
                })
        except Exception as e:
            self.logger.error(f"Error handling market error event: {e}")

    async def _handle_wallet_update(self, data) -> None:
        """Handle wallet update events — sync balance state."""
        try:
            wallet_id = data.get("wallet_id", "")
            balance = data.get("balance", {})
            if wallet_id:
                self.wallet_balances[wallet_id] = balance
                self.logger.debug(f"Wallet {wallet_id} updated: {balance}")
        except Exception as e:
            self.logger.error(f"Error handling wallet update: {e}")

    async def initialize_markets(self) -> bool:
        """Initialize trading markets.
        
        Returns:
            True if initialized successfully
        """
        try:
            # Connect to each market
            for market, keys in self.api_keys.items():
                if await self.market_api.connect_market(market, keys):
                    self.active_markets.append(market)
                    self.logger.info(f"Connected to market: {market}")
                    
            return len(self.active_markets) > 0
            
        except Exception as e:
            self.logger.error(f"Error initializing markets: {e}")
            return False
            
    async def start_trading(self) -> bool:
        """Start automated trading."""
        if self.is_trading:
            return True
            
        try:
            if not self.wallet or not self.market_api:
                self.logger.error("Wallet or market API not initialized")
                return False
                
            # Initialize markets
            if not await self.initialize_markets():
                self.logger.error("Failed to initialize markets")
                return False
                
            self.is_trading = True
            self.logger.info("Trading started")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting trading: {e}")
            self.is_trading = False
            return False
            
    def stop_trading(self) -> bool:
        """Stop automated trading."""
        if not self.is_trading:
            return True
            
        try:
            self.is_trading = False
            self.logger.info("Trading stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping trading: {e}")
            return False
            
    async def place_trade(
        self,
        market: str,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
        order_type: str = "market"
    ) -> Optional[str]:
        """Place a trade order.
        
        Args:
            market: Market to trade on
            symbol: Trading pair symbol
            side: 'buy' or 'sell'
            amount: Trade amount
            price: Optional limit price
            order_type: Order type (market/limit)
            
        Returns:
            Order ID or None if error
        """
        try:
            if market not in self.active_markets:
                raise ValueError(f"Market not connected: {market}")
                
            # Get current market data
            market_data = await self.market_api.get_market_data(market, symbol)
            if not market_data:
                return None
                
            # Build order
            order = {
                "market": market,
                "symbol": symbol,
                "side": side,
                "amount": str(amount),
                "type": order_type,
                "timestamp": datetime.now().isoformat()
            }
            
            if price:
                order["price"] = str(price)
            elif order_type == "market":
                order["price"] = market_data["price"]
                
            # Place order
            order_id = await self.market_api.place_order(market, order)
            if not order_id:
                return None
                
            # Update order with ID
            order["id"] = order_id
            
            # Add to history
            self.trade_history.append(order)
            
            # Update positions
            if side == "buy":
                self.positions.append(order)
            else:
                # Remove matching buy position
                for i, pos in enumerate(self.positions):
                    if (pos["market"] == market and
                        pos["symbol"] == symbol and
                        Decimal(pos["amount"]) == amount):
                        self.positions.pop(i)
                        break
                        
            self.logger.info(f"Placed {side} order: {order_id}")
            return order_id
            
        except Exception as e:
            self.logger.error(f"Error placing trade: {e}")
            return None
            
    async def get_position(self, market: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current position.
        
        Args:
            market: Market name
            symbol: Trading pair symbol
            
        Returns:
            Position info or None if not found
        """
        try:
            for pos in self.positions:
                if pos["market"] == market and pos["symbol"] == symbol:
                    # Get current market price
                    market_data = await self.market_api.get_market_data(market, symbol)
                    if market_data:
                        # Calculate PnL
                        entry_price = Decimal(pos["price"])
                        current_price = Decimal(market_data["price"])
                        amount = Decimal(pos["amount"])
                        
                        pnl = (current_price - entry_price) * amount
                        pnl_percent = (current_price / entry_price - 1) * 100
                        
                        return {
                            **pos,
                            "current_price": str(current_price),
                            "pnl": str(pnl),
                            "pnl_percent": str(pnl_percent)
                        }
                        
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting position: {e}")
            return None
            
    async def get_balance(self, market: str, asset: str) -> Optional[Decimal]:
        """Get asset balance.
        
        Args:
            market: Market name
            asset: Asset symbol
            
        Returns:
            Balance amount or None if error
        """
        try:
            if market not in self.active_markets:
                raise ValueError(f"Market not connected: {market}")
                
            balance = await self.market_api.get_balance(market, asset)
            return Decimal(balance) if balance else None
            
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return None
            
    async def get_order_book(
        self,
        market: str,
        symbol: str,
        depth: int = 10
    ) -> Optional[Dict[str, List[Tuple[Decimal, Decimal]]]]:
        """Get market order book.
        
        Args:
            market: Market name
            symbol: Trading pair symbol
            depth: Order book depth
            
        Returns:
            Order book with bids and asks or None if error
        """
        try:
            if market not in self.active_markets:
                raise ValueError(f"Market not connected: {market}")
                
            book = await self.market_api.get_order_book(market, symbol, depth)
            if not book:
                return None
                
            return {
                "bids": [(Decimal(p), Decimal(v)) for p, v in book["bids"]],
                "asks": [(Decimal(p), Decimal(v)) for p, v in book["asks"]]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting order book: {e}")
            return None
            
    async def cancel_order(self, market: str, order_id: str) -> bool:
        """Cancel order.
        
        Args:
            market: Market name
            order_id: Order ID
            
        Returns:
            True if cancelled successfully
        """
        try:
            if market not in self.active_markets:
                raise ValueError(f"Market not connected: {market}")
                
            return await self.market_api.cancel_order(market, order_id)
            
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return False
            
    async def get_trade_history(
        self,
        market: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get trade history.
        
        Args:
            market: Optional market filter
            symbol: Optional symbol filter
            limit: Maximum number of trades
            
        Returns:
            List of trades
        """
        try:
            trades = self.trade_history
            
            if market:
                trades = [t for t in trades if t["market"] == market]
            if symbol:
                trades = [t for t in trades if t["symbol"] == symbol]
                
            return sorted(
                trades,
                key=lambda x: x["timestamp"],
                reverse=True
            )[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting trade history: {e}")
            return []
            
    def save_state(self) -> bool:
        """Save trading state.
        
        Returns:
            True if saved successfully
        """
        try:
            state = {
                "positions": self.positions,
                "trade_history": self.trade_history,
                "active_markets": self.active_markets
            }
            
            state_path = Path("state/trading.json")
            state_path.parent.mkdir(exist_ok=True)
            
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            self.logger.info("Saved trading state")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
            return False
            
    def load_state(self) -> bool:
        """Load trading state.
        
        Returns:
            True if loaded successfully
        """
        try:
            state_path = Path("state/trading.json")
            if not state_path.exists():
                return False
                
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
                
            self.positions = state.get("positions", [])
            self.trade_history = state.get("trade_history", [])
            self.active_markets = state.get("active_markets", [])
            
            self.logger.info("Loaded trading state")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading state: {e}")
            return False
            
    async def close(self) -> None:
        """Close trading system."""
        try:
            # Save final state
            self.save_state()
            
            # Stop trading
            self.stop_trading()
            
            # Clear state
            self.positions.clear()
            self.trade_history.clear()
            self.active_markets.clear()
            self.api_keys.clear()
            
            self.logger.info("Trading system closed")
            
        except Exception as e:
            self.logger.error(f"Error closing trading system: {e}")
