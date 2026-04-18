"""
CORRECTED REAL TRADING ANALYSIS IMPLEMENTATION
Uses correct RealExchangeExecutor API methods
NO MOCK DATA - 100% REAL APIs
"""

import time
import asyncio
from typing import Dict, Any, List

async def _analyze_and_auto_trade_REAL(self):
    """
    Run REAL trading analysis using REAL executors with CORRECT API methods.
    """
    try:
        self.logger.info("🔍 Starting REAL trading analysis with live APIs...")
        
        # Start countdown timer for UI
        self._analysis_start_time = time.time()
        self._analysis_duration = 180  # 3 minutes
        
        if not hasattr(self, '_analysis_countdown_timer'):
            from PyQt6.QtCore import QTimer
            self._analysis_countdown_timer = QTimer(self)
            self._analysis_countdown_timer.timeout.connect(self._update_analysis_timer)
        self._analysis_countdown_timer.start(1000)
        
        # 1. Get REAL API keys
        from core.api_key_manager import APIKeyManager
        api_manager = APIKeyManager.get_instance(event_bus=self.event_bus)
        if not hasattr(api_manager, 'api_keys') or not api_manager.api_keys:
            api_manager.initialize_sync()
        all_keys = api_manager.api_keys
        self.logger.info(f"✅ Loaded {len(all_keys)} API keys from APIKeyManager")
        
        # 2. Initialize REAL executors
        from core.real_exchange_executor import RealExchangeExecutor
        from core.real_stock_executor import RealStockExecutor
        from core.multichain_trade_executor import MultiChainTradeExecutor
        from core.exchange_universe import build_real_exchange_api_keys
        
        # Build API keys in correct format for executors
        exchange_keys = build_real_exchange_api_keys(all_keys)
        
        # Create executors with REAL connections
        crypto_executor = RealExchangeExecutor(exchange_keys, event_bus=self.event_bus)
        stock_executor = RealStockExecutor(all_keys, event_bus=self.event_bus)
        blockchain_executor = MultiChainTradeExecutor(event_bus=self.event_bus)
        
        self.logger.info("✅ Initialized REAL executors (crypto, stocks, blockchain)")
        
        # 3. Get REAL exchange health (which exchanges are working)
        exchange_health = await crypto_executor.get_exchange_health()
        broker_health = await stock_executor.get_broker_health()
        
        working_exchanges = [ex for ex, h in exchange_health.items() if h.get('status') == 'ok']
        working_brokers = [br for br, h in broker_health.items() if h.get('status') == 'ok']
        
        self.logger.info(f"✅ Exchange health: {len(working_exchanges)} working exchanges")
        self.logger.info(f"✅ Broker health: {len(working_brokers)} working brokers")
        
        # 4. Fetch REAL market data from working exchanges using CCXT directly
        markets_analyzed = []
        exchanges_analyzed = []
        
        for exchange_name in working_exchanges[:5]:  # Top 5 working exchanges
            exchanges_analyzed.append(exchange_name)
            try:
                # Access underlying CCXT exchange
                ccxt_exchange = crypto_executor.exchanges.get(exchange_name)
                if ccxt_exchange:
                    # Get REAL ticker for BTC, ETH, SOL
                    for symbol in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']:
                        try:
                            # Use CCXT fetch_ticker directly
                            ticker = await asyncio.to_thread(ccxt_exchange.fetch_ticker, symbol)
                            if ticker:
                                markets_analyzed.append({
                                    'exchange': exchange_name,
                                    'symbol': symbol,
                                    'price': ticker.get('last', 0),
                                    'volume': ticker.get('baseVolume', 0),
                                    'change': ticker.get('percentage', 0),
                                    'bid': ticker.get('bid', 0),
                                    'ask': ticker.get('ask', 0),
                                    'high': ticker.get('high', 0),
                                    'low': ticker.get('low', 0),
                                    'timestamp': ticker.get('timestamp', time.time() * 1000)
                                })
                                self.logger.info(f"✅ {exchange_name} {symbol}: ${ticker.get('last', 0):,.2f}")
                        except Exception as e:
                            self.logger.debug(f"Could not fetch {symbol} from {exchange_name}: {e}")
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {exchange_name}: {e}")
        
        # 5. Get REAL blockchain data
        blockchains_analyzed = []
        supported_chains = blockchain_executor.get_supported_networks()
        
        for chain in ['ethereum', 'bsc', 'polygon', 'arbitrum', 'optimism'][:5]:
            if chain in supported_chains:
                try:
                    status = await blockchain_executor.get_chain_status(chain)
                    if status.reachable:
                        blockchains_analyzed.append({
                            'chain': chain,
                            'rpc_url': status.rpc_url,
                            'latest_block': status.latest_block,
                            'is_evm': status.is_evm,
                            'reachable': True
                        })
                        self.logger.info(f"✅ {chain}: block {status.latest_block}")
                except Exception as e:
                    self.logger.debug(f"Could not check {chain}: {e}")
        
        # 6. Get REAL stock data
        stock_symbols_analyzed = []
        if 'alpaca' in working_brokers:
            try:
                # Get real stock positions
                positions = await stock_executor.get_alpaca_positions()
                if positions.get('status') == 'ok':
                    stock_symbols_analyzed = positions.get('positions', [])
                    self.logger.info(f"✅ Alpaca: {len(stock_symbols_analyzed)} positions")
            except Exception as e:
                self.logger.debug(f"Could not fetch Alpaca positions: {e}")
        
        # 7. Build REAL analysis results
        results = {
            'timestamp': time.time(),
            'markets': markets_analyzed,
            'exchanges': exchanges_analyzed,
            'blockchains': blockchains_analyzed,
            'stock_positions': stock_symbols_analyzed,
            'exchange_health': exchange_health,
            'broker_health': broker_health,
            'api_calls_made': len(markets_analyzed) + len(blockchains_analyzed),
            'data_sources': 'REAL APIs - NO MOCK DATA',
            'working_exchanges': working_exchanges,
            'working_brokers': working_brokers
        }
        
        # 8. Save to state manager
        self._save_analysis_results(results)
        
        # 9. Send to Ollama brain for decision making
        if self.event_bus:
            self.event_bus.publish('ollama.analyze_markets', {
                'analysis_results': results,
                'request_trading_decision': True,
                'timestamp': time.time()
            })
            self.logger.info("📡 Sent analysis to Ollama brain for decision")
        
        # 10. Update UI with results
        self._markets_analyzed = markets_analyzed
        self._exchanges_analyzed = exchanges_analyzed
        self._blockchains_analyzed = blockchains_analyzed
        
        self.logger.info(f"✅ REAL analysis complete: {len(markets_analyzed)} markets, "
                        f"{len(exchanges_analyzed)} exchanges, {len(blockchains_analyzed)} blockchains")
        
        return results
        
    except Exception as e:
        self.logger.error(f"Error in REAL analysis: {e}")
        import traceback
        self.logger.error(traceback.format_exc())
        return {}


def _on_ollama_trading_decision(self, data: Dict[str, Any]):
    """Handle trading decision from Ollama brain - EXECUTE REAL TRADE."""
    try:
        decision = data.get('decision')  # 'buy', 'sell', 'hold'
        symbol = data.get('symbol')
        exchange = data.get('exchange')
        confidence = data.get('confidence', 0)
        reasoning = data.get('reasoning', '')
        
        self.logger.info(f"🧠 Ollama decision: {decision} {symbol} on {exchange} "
                        f"(confidence: {confidence:.2f})")
        self.logger.info(f"🧠 Reasoning: {reasoning}")
        
        # Update UI with decision
        if hasattr(self, 'auto_trade_info') and self.auto_trade_info:
            self.auto_trade_info.setText(
                f"🧠 OLLAMA DECISION:\n"
                f"Action: {decision.upper()}\n"
                f"Symbol: {symbol}\n"
                f"Exchange: {exchange}\n"
                f"Confidence: {confidence:.1%}\n"
                f"Reasoning: {reasoning}"
            )
        
        # Execute the trade if confidence is high enough
        if confidence > 0.7 and decision in ['buy', 'sell']:
            # Schedule async execution
            import asyncio
            asyncio.create_task(self._execute_ollama_trade(symbol, exchange, decision, confidence))
        
    except Exception as e:
        self.logger.error(f"Error handling Ollama decision: {e}")


async def _execute_ollama_trade(self, symbol: str, exchange: str, 
                                side: str, confidence: float):
    """Execute REAL trade based on Ollama brain decision using place_real_order()."""
    try:
        self.logger.info(f"🚀 Executing REAL trade: {side} {symbol} on {exchange}")
        
        # Get executor
        from core.real_exchange_executor import RealExchangeExecutor, OrderType, OrderSide
        from core.api_key_manager import APIKeyManager
        from core.exchange_universe import build_real_exchange_api_keys
        
        api_manager = APIKeyManager.get_instance()
        keys = build_real_exchange_api_keys(api_manager.api_keys)
        executor = RealExchangeExecutor(keys, event_bus=self.event_bus)
        
        # Calculate position size based on confidence
        # Higher confidence = larger position
        base_amount = 0.001  # Base: 0.001 BTC or equivalent
        amount = base_amount * confidence
        
        self.logger.info(f"💰 Position size: {amount} (confidence-adjusted)")
        
        # Convert side to OrderSide enum
        order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
        
        # Execute REAL market order using correct API
        order = await executor.place_real_order(
            exchange_name=exchange,
            symbol=symbol,
            side=order_side,
            order_type=OrderType.MARKET,
            amount=amount
        )
        
        self.logger.info(f"✅ REAL trade executed: {order}")
        
        # Update UI
        if hasattr(self, 'auto_trade_info') and self.auto_trade_info:
            self.auto_trade_info.setText(
                f"✅ TRADE EXECUTED:\n"
                f"Order ID: {order.get('id', 'N/A')}\n"
                f"Symbol: {symbol}\n"
                f"Side: {side.upper()}\n"
                f"Amount: {amount}\n"
                f"Exchange: {exchange}\n"
                f"Status: {order.get('status', 'unknown')}"
            )
        
        # Broadcast to wallet system
        if self.event_bus:
            self.event_bus.publish('trading.order.executed', {
                'order': order,
                'ollama_decision': True,
                'confidence': confidence,
                'timestamp': time.time()
            })
        
    except Exception as e:
        self.logger.error(f"Failed to execute Ollama trade: {e}")
        import traceback
        self.logger.error(traceback.format_exc())
        
        # Update UI with error
        if hasattr(self, 'auto_trade_info') and self.auto_trade_info:
            self.auto_trade_info.setText(f"❌ TRADE FAILED:\n{str(e)}")


def _register_ollama_event_handlers(self):
    """Register event handlers for Ollama brain communication."""
    if self.event_bus:
        try:
            # Subscribe to Ollama trading decisions
            self.event_bus.subscribe('ollama.trading_decision', self._on_ollama_trading_decision)
            self.logger.info("✅ Subscribed to Ollama trading decisions")
            
            # Subscribe to Ollama analysis complete
            self.event_bus.subscribe('ollama.market_analysis_complete', 
                                    self._on_ollama_analysis_complete)
            self.logger.info("✅ Subscribed to Ollama analysis complete")
            
        except Exception as e:
            self.logger.warning(f"Failed to subscribe to Ollama events: {e}")


def _on_ollama_analysis_complete(self, data: Dict[str, Any]):
    """Handle Ollama analysis complete event."""
    try:
        summary = data.get('summary', '')
        insights = data.get('insights', [])
        
        self.logger.info(f"🧠 Ollama analysis complete: {summary}")
        
        # Update UI
        if hasattr(self, 'auto_trade_plan_display') and self.auto_trade_plan_display:
            text = f"🧠 OLLAMA ANALYSIS:\n\n{summary}\n\n"
            if insights:
                text += "KEY INSIGHTS:\n"
                for insight in insights:
                    text += f"• {insight}\n"
            self.auto_trade_plan_display.setPlainText(text)
        
    except Exception as e:
        self.logger.debug(f"Error handling Ollama analysis complete: {e}")


# INTEGRATION INSTRUCTIONS:
# 
# 1. Copy these methods into trading_tab.py
# 
# 2. In __init__() method, add after event_bus is set:
#    self._register_ollama_event_handlers()
#
# 3. Replace the button handler for "Analyze & Auto Trade" to call:
#    asyncio.create_task(self._analyze_and_auto_trade_REAL())
#
# 4. Ensure _save_analysis_results() exists (from APPEND_TO_TRADING_TAB.py)
#
# 5. Test: Click button and verify real API calls in logs
