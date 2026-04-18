#!/usr/bin/env python3
# TradingSystem for Kingdom AI

import logging
import asyncio
import json
import time
import traceback
from typing import Dict, Any, Optional
from decimal import Decimal
from core.base_component import BaseComponent
from core.event_bus import EventBus

class TradingSystem(BaseComponent):
    """
    TradingSystem handles trading operations for the Kingdom AI system.
    Implements real-time order management, portfolio tracking, and risk management.
    """
    
    def __init__(self, event_bus: EventBus):
        """Initialize the TradingSystem with required components."""
        super().__init__("TradingSystem", event_bus)
        self.logger = logging.getLogger("KingdomAI.TradingSystem")
        self._initialized = False  # Fixed: use _initialized (BaseComponent property)
        self.active_orders: Dict[str, Dict] = {}
        self.portfolio: Dict[str, Dict] = {}
        self.market_data: Dict[str, Any] = {}
        self.exchange_connected = False
        self._exchange = None
        
    async def initialize(self) -> bool:
        """Initialize the TradingSystem and its components."""
        try:
            self.logger.info("Initializing TradingSystem...")
            
            # Set up event subscriptions
            subscriptions = [
                ('trading.order.new', self._handle_new_order),
                ('trading.order.cancel', self._handle_cancel_order),
                ('trading.market.update', self._handle_market_update),
                ('trading.portfolio.analyze', self._handle_portfolio_analyze),
                ('trading.positions.get', self._handle_get_positions),
                ('trading.balance.get', self._handle_get_balance)
            ]
            
            for event, handler in subscriptions:
                self.event_bus.subscribe_sync(event, handler)
            
            # Initialize exchange connection
            await self._initialize_exchange()
            
            # Load portfolio and active orders
            await self._load_initial_state()
            
            self._initialized = True  # Fixed: use _initialized (BaseComponent property)
            self.logger.info("TradingSystem initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize TradingSystem: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _initialize_exchange(self) -> None:
        """Initialize connection to the exchange via ccxt."""
        try:
            import ccxt as _ccxt
            import os, json

            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                       'config', 'api_keys.json')
            exchange_id = 'binance'
            api_key = ''
            api_secret = ''

            if os.path.exists(config_path):
                with open(config_path) as f:
                    keys = json.load(f)
                if isinstance(keys, dict):
                    for eid in ('binance', 'bybit', 'kucoin'):
                        if eid in keys:
                            exchange_id = eid
                            api_key = keys[eid].get('api_key', '')
                            api_secret = keys[eid].get('api_secret', '')
                            break

            exchange_class = getattr(_ccxt, exchange_id, _ccxt.binance)
            self._exchange = exchange_class({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
            })

            await asyncio.to_thread(self._exchange.load_markets)
            self.exchange_connected = True
            self.logger.info(f"Exchange connection established ({exchange_id})")

        except Exception as e:
            self.logger.error(f"Failed to connect to exchange: {str(e)}")
            self._exchange = None
            self.exchange_connected = False
            raise
    
    async def _load_initial_state(self) -> None:
        """Load initial portfolio and active orders from the exchange."""
        try:
            if self._exchange and self.exchange_connected:
                balance = await asyncio.to_thread(self._exchange.fetch_balance)
                for asset, amount in balance.get('total', {}).items():
                    amt = float(amount or 0)
                    if amt > 0:
                        self.portfolio[asset] = {'amount': amt, 'free': float(balance['free'].get(asset, 0))}

                try:
                    open_orders = await asyncio.to_thread(self._exchange.fetch_open_orders)
                    for order in open_orders:
                        self.active_orders[order['id']] = {
                            'order_id': order['id'],
                            'symbol': order.get('symbol', ''),
                            'side': order.get('side', ''),
                            'type': order.get('type', ''),
                            'quantity': float(order.get('amount', 0)),
                            'price': float(order.get('price', 0) or 0),
                            'status': order.get('status', 'open'),
                            'timestamp': order.get('timestamp', int(time.time() * 1000)),
                        }
                except Exception:
                    self.active_orders = {}

            self.logger.info(f"Initial state loaded: {len(self.portfolio)} assets, {len(self.active_orders)} open orders")

        except Exception as e:
            self.logger.error(f"Failed to load initial state: {str(e)}")
            self.portfolio = {}
            self.active_orders = {}
    
    async def _handle_new_order(self, event_data: Dict) -> None:
        """Handle new order request."""
        try:
            self.logger.info(f"Processing new order: {json.dumps(event_data)}")
            
            # Validate order data
            required_fields = ['symbol', 'side', 'order_type', 'quantity']
            if not all(field in event_data for field in required_fields):
                raise ValueError("Missing required order fields")
            
            qty = Decimal(str(event_data['quantity']))
            if qty <= 0:
                raise ValueError(f"Invalid quantity: {qty}")
            if event_data.get('order_type') == 'limit' and not event_data.get('price'):
                raise ValueError("Limit orders require a price")

            # Place order on exchange
            order_result = await self._place_order(
                symbol=event_data['symbol'],
                side=event_data['side'],
                order_type=event_data.get('order_type', 'market'),
                quantity=Decimal(str(event_data['quantity'])),
                price=Decimal(str(event_data.get('price', 0))),
                params=event_data.get('params', {})
            )
            
            # Update local state
            self.active_orders[order_result['order_id']] = order_result
            
            # Publish order update
            await self.event_bus.publish_async('trading.order.update', order_result)
            
        except Exception as e:
            error_msg = f"Failed to process new order: {str(e)}"
            self.logger.error(error_msg)
            await self.event_bus.publish_async('trading.error', {
                'error': error_msg,
                'event_data': event_data,
                'traceback': traceback.format_exc()
            })
    
    async def _place_order(self, symbol: str, side: str, order_type: str, 
                         quantity: Decimal, price: Decimal = Decimal('0'), 
                         params: Optional[Dict] = None) -> Dict:
        """Place an order on the exchange via ccxt."""
        try:
            if not self._exchange or not self.exchange_connected:
                raise RuntimeError("Exchange not connected")

            ccxt_params = params or {}
            amount = float(quantity)
            px = float(price) if price else None

            if order_type == 'market':
                raw = await asyncio.to_thread(
                    self._exchange.create_order, symbol, 'market', side, amount, None, ccxt_params)
            else:
                if not px:
                    raise ValueError("Limit orders require a price")
                raw = await asyncio.to_thread(
                    self._exchange.create_order, symbol, order_type, side, amount, px, ccxt_params)

            order_result = {
                'order_id': raw.get('id', f"order_{int(time.time() * 1000)}"),
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': amount,
                'price': float(raw.get('price') or px or 0),
                'status': raw.get('status', 'new'),
                'timestamp': raw.get('timestamp', int(time.time() * 1000)),
                'params': ccxt_params,
                'raw': {k: v for k, v in raw.items() if k in ('id', 'status', 'filled', 'remaining', 'cost')},
            }
            return order_result

        except Exception as e:
            self.logger.error(f"Order placement failed: {str(e)}")
            raise
    
    # Other handler methods with proper implementation...
    async def _handle_cancel_order(self, event_data: Dict) -> None:
        """Handle order cancellation via ccxt."""
        try:
            order_id = event_data.get('order_id')
            if not order_id:
                raise ValueError("Missing order_id in cancel request")

            symbol = event_data.get('symbol')
            if not symbol and order_id in self.active_orders:
                symbol = self.active_orders[order_id].get('symbol')

            if self._exchange and self.exchange_connected:
                await asyncio.to_thread(self._exchange.cancel_order, order_id, symbol)

            if order_id in self.active_orders:
                self.active_orders[order_id]['status'] = 'canceled'

            await self.event_bus.publish_async('trading.order.update', {
                'order_id': order_id,
                'status': 'canceled'
            })

        except Exception as e:
            error_msg = f"Failed to cancel order: {str(e)}"
            self.logger.error(error_msg)
            await self.event_bus.publish_async('trading.error', {
                'error': error_msg,
                'event_data': event_data
            })
    
    async def _handle_market_update(self, event_data: Dict) -> None:
        """Handle market data updates."""
        try:
            symbol = event_data.get('symbol')
            if not symbol:
                return
                
            # Update local market data
            self.market_data[symbol] = {
                'bid': event_data.get('bid'),
                'ask': event_data.get('ask'),
                'last': event_data.get('last'),
                'volume': event_data.get('volume'),
                'timestamp': event_data.get('timestamp', int(time.time() * 1000))
            }
            
            # Update any dependent systems
            await self._check_orders()
            
        except Exception as e:
            self.logger.error(f"Error processing market update: {str(e)}")
    
    async def _check_orders(self) -> None:
        """Check and update order statuses based on market data.
        KAIG Integration: Publishes trading.profit when orders fill with positive P&L."""
        for order_id, order in list(self.active_orders.items()):
            if order.get('status') in ('new', 'open', 'partially_filled'):
                symbol = order.get('symbol', '')
                if symbol in self.market_data:
                    last_price = self.market_data[symbol].get('last', 0)
                    order_price = order.get('price', 0)
                    side = order.get('side', '')
                    qty = order.get('quantity', 0)
                    if last_price and order_price and qty:
                        # Check if limit order would fill
                        should_fill = False
                        if order.get('type') == 'limit':
                            if side == 'buy' and last_price <= order_price:
                                should_fill = True
                            elif side == 'sell' and last_price >= order_price:
                                should_fill = True
                        # Calculate P&L for filled sell orders
                        if should_fill:
                            order['status'] = 'filled'
                            order['fill_price'] = last_price
                            pnl = 0.0
                            if side == 'sell':
                                entry = order.get('entry_price', order_price)
                                pnl = (last_price - entry) * qty
                            order['pnl'] = pnl
                            await self.event_bus.publish_async('trading.order.update', order)
                            # KAIG Integration: Publish profit event for buyback pipeline
                            if pnl > 0:
                                self.event_bus.publish('trading.profit', {
                                    'profit_usd': pnl,
                                    'profit': pnl,
                                    'symbol': symbol,
                                    'order_id': order_id,
                                    'source': 'trading_system',
                                })
    
    async def _handle_portfolio_analyze(self, event_data: Dict) -> None:
        """Handle portfolio analysis request using live exchange data."""
        try:
            positions = []
            total_value = 0.0
            total_cost = 0.0

            if self._exchange and self.exchange_connected:
                balance = await asyncio.to_thread(self._exchange.fetch_balance)
                for asset, amount in balance.get('total', {}).items():
                    amt = float(amount or 0)
                    if amt <= 0 or asset in ('USDT', 'USD', 'BUSD', 'USDC'):
                        if asset in ('USDT', 'USD', 'BUSD', 'USDC'):
                            total_value += amt
                        continue
                    sym = f"{asset}/USDT"
                    price = 0.0
                    try:
                        ticker = await asyncio.to_thread(self._exchange.fetch_ticker, sym)
                        price = float(ticker.get('last', 0) or 0)
                    except Exception:
                        pass
                    value = amt * price
                    total_value += value
                    positions.append({'symbol': sym, 'amount': amt, 'price': price, 'value': value})
            else:
                for asset, pos in self.portfolio.items():
                    amt = pos.get('amount', 0)
                    if amt > 0:
                        positions.append({'symbol': asset, 'amount': amt, 'price': 0, 'value': 0})

            analysis = {
                'timestamp': int(time.time() * 1000),
                'total_value': total_value,
                'positions': positions,
                'pnl': total_value - total_cost if total_cost else 0.0,
                'risk_metrics': {
                    'position_count': len(positions),
                    'largest_position_pct': max((p['value'] / total_value * 100 for p in positions), default=0) if total_value > 0 else 0,
                }
            }

            await self.event_bus.publish_async('trading.portfolio.analysis', analysis)

        except Exception as e:
            self.logger.error(f"Portfolio analysis failed: {str(e)}")
    
    async def _handle_get_positions(self, event_data: Dict) -> None:
        """Handle get positions request from exchange."""
        try:
            positions = []
            if self._exchange and self.exchange_connected:
                balance = await asyncio.to_thread(self._exchange.fetch_balance)
                for asset, amount in balance.get('total', {}).items():
                    amt = float(amount or 0)
                    if amt > 0 and asset not in ('USDT', 'USD', 'BUSD', 'USDC'):
                        positions.append({
                            'symbol': f"{asset}/USDT",
                            'amount': amt,
                            'free': float(balance.get('free', {}).get(asset, 0)),
                        })

            await self.event_bus.publish_async('trading.positions.update', {
                'positions': positions,
                'timestamp': int(time.time() * 1000)
            })

        except Exception as e:
            self.logger.error(f"Failed to get positions: {str(e)}")
    
    async def _handle_get_balance(self, event_data: Dict) -> None:
        """Handle get balance request from exchange."""
        try:
            balance = {}
            if self._exchange and self.exchange_connected:
                raw = await asyncio.to_thread(self._exchange.fetch_balance)
                balance = {
                    'total': raw.get('total', {}),
                    'free': raw.get('free', {}),
                    'used': raw.get('used', {}),
                }

            await self.event_bus.publish_async('trading.balance.update', {
                'balance': balance,
                'timestamp': int(time.time() * 1000)
            })

        except Exception as e:
            self.logger.error(f"Failed to get balance: {str(e)}")
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        try:
            # Cancel all active orders
            for order_id in list(self.active_orders.keys()):
                await self._cancel_order(order_id)
                
            # Close exchange connection
            self.exchange_connected = False
            
            self.logger.info("TradingSystem shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")
    
    async def _cancel_order(self, order_id: str) -> None:
        """Cancel a single order via ccxt."""
        try:
            symbol = None
            if order_id in self.active_orders:
                symbol = self.active_orders[order_id].get('symbol')
            if self._exchange and self.exchange_connected:
                await asyncio.to_thread(self._exchange.cancel_order, order_id, symbol)
            if order_id in self.active_orders:
                self.active_orders[order_id]['status'] = 'canceled'
        except Exception as e:
            self.logger.warning(f"Could not cancel order {order_id}: {e}")
            if order_id in self.active_orders:
                self.active_orders[order_id]['status'] = 'cancel_failed'
            
    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return {
            'initialized': self.initialized,
            'exchange_connected': self.exchange_connected,
            'active_orders': len(self.active_orders),
            'tracked_symbols': len(self.market_data),
            'portfolio_size': len(self.portfolio)
        }
