#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Autonomous Trading Orchestrator for Kingdom AI
Integrates Ollama Brain + Thoth AI for fully autonomous trading
with optional user command acceptance

This module ensures:
1. Ollama Brain and Thoth AI control ALL auto-trading autonomously
2. No human intervention necessary for trade execution
3. System can still accept and execute user trade requests
4. Complete API key integration for all trading platforms
5. Real-time broadcasting of all market data and decisions
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from core.telemetry_collector import TelemetryCollector

logger = logging.getLogger(__name__)

class AutonomousTradingOrchestrator:
    """
    Orchestrates fully autonomous trading with Ollama Brain + Thoth AI
    
    Key Features:
    - 100% autonomous trading decisions
    - Ollama Brain consultation for every trade
    - Thoth AI market analysis integration
    - User command acceptance (manual override)
    - Real-time decision broadcasting
    - Complete API key management integration
    """
    
    def __init__(self, event_bus=None, ollama_brain=None, thoth_ai=None, 
                 trading_system=None, api_key_manager=None, telemetry_collector=None,
                 wallet_manager=None):
        """
        Initialize Autonomous Trading Orchestrator
        
        Args:
            event_bus: Event bus for system-wide broadcasting
            ollama_brain: Ollama brain instance for AI decisions
            thoth_ai: Thoth AI instance for market analysis
            trading_system: Trading system instance
            api_key_manager: API key manager instance
        """
        self.event_bus = event_bus
        self.ollama_brain = ollama_brain
        self.thoth_ai = thoth_ai
        self.trading_system = trading_system
        self.api_key_manager = api_key_manager
        self.telemetry = telemetry_collector
        self.wallet_manager = wallet_manager
        if self.telemetry is None and self.event_bus is not None:
            try:
                self.telemetry = TelemetryCollector(event_bus=self.event_bus)
            except Exception as e:
                logger.error(f"Error initializing TelemetryCollector: {e}")
                self.telemetry = None
        
        # Autonomous trading state
        self.autonomous_mode = False
        self.autonomous_task = None
        
        import threading as _th
        self._ato_lock = _th.Lock()

        self.autonomous_decisions = []
        self.user_commands = []

        self.autonomous_trades_count = 0
        self.user_trades_count = 0
        self.total_autonomous_profit = 0.0
        self.total_user_profit = 0.0
        
        # API key status
        self.connected_exchanges = {}
        self.connected_stock_brokers = {}
        self.connected_forex_platforms = {}
        
        # Decision confidence thresholds
        self.autonomous_threshold = 0.70  # 70% confidence for autonomous execution
        self.user_command_priority = True  # User commands always execute
        
        # KAIG THREE TARGETS — every decision must know these
        self._kaig_directive = {}
        self._kaig_brief = ""
        if self.event_bus:
            try:
                self.event_bus.subscribe('kaig.intel.trading.directive', self._on_kaig_directive)
            except Exception as e:
                logger.warning("Init: Failed to subscribe to KAIG directive: %s", e)
        
        logger.info("✅ Autonomous Trading Orchestrator initialized")
    
    async def start_autonomous_trading(self, symbols: List[str] = None):
        """
        Start fully autonomous trading mode
        
        Ollama Brain + Thoth AI will:
        - Analyze all markets continuously
        - Make trading decisions automatically
        - Execute trades without human intervention
        - Broadcast all decisions for transparency
        
        Args:
            symbols: Optional list of symbols to trade (if None, trades ALL)
        """
        try:
            logger.info("🤖 Starting AUTONOMOUS TRADING MODE")
            
            # 1. Verify Ollama Brain is available
            if not self.ollama_brain:
                raise RuntimeError("Ollama Brain not available for autonomous trading")
            
            # 2. Verify Thoth AI is available
            if not self.thoth_ai:
                logger.warning("Thoth AI not available - using Ollama Brain only")
            
            # 3. Verify trading system is available
            if not self.trading_system:
                raise RuntimeError("Trading System not available")
            
            # 4. Load and verify ALL API keys
            await self._verify_all_api_keys()
            
            # 5. Inform Ollama Brain of autonomous mode
            await self._inform_ollama_autonomous_mode(symbols)
            
            # 6. Enable autonomous mode
            self.autonomous_mode = True
            
            # 7. Start autonomous decision loop
            self.autonomous_task = asyncio.create_task(
                self._autonomous_decision_loop(symbols)
            )
            
            # 8. Broadcast autonomous mode started
            if self.event_bus:
                await self.event_bus.publish('trading.autonomous.started', {
                    'timestamp': datetime.now().isoformat(),
                    'symbols': symbols or 'ALL',
                    'exchanges': len(self.connected_exchanges),
                    'brokers': len(self.connected_stock_brokers),
                    'forex': len(self.connected_forex_platforms),
                    'ollama_ready': True,
                    'thoth_ready': self.thoth_ai is not None
                })
            
            logger.info(f"✅ AUTONOMOUS TRADING ACTIVE - {len(self.connected_exchanges)} exchanges, "
                       f"{len(self.connected_stock_brokers)} brokers, "
                       f"{len(self.connected_forex_platforms)} forex platforms")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start autonomous trading: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def stop_autonomous_trading(self):
        """Stop autonomous trading mode"""
        try:
            logger.info("🛑 Stopping AUTONOMOUS TRADING MODE")
            
            # Stop autonomous loop
            self.autonomous_mode = False
            if self.autonomous_task:
                self.autonomous_task.cancel()
                try:
                    await self.autonomous_task
                except asyncio.CancelledError:
                    pass
            
            # Broadcast stopped
            if self.event_bus:
                await self.event_bus.publish('trading.autonomous.stopped', {
                    'timestamp': datetime.now().isoformat(),
                    'total_trades': self.autonomous_trades_count,
                    'total_profit': self.total_autonomous_profit
                })
            
            logger.info("✅ Autonomous trading stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping autonomous trading: {e}")
            return False
    
    async def _autonomous_decision_loop(self, symbols: Optional[List[str]]):
        """
        Main autonomous decision loop
        
        This runs continuously and:
        1. Gets market data from all sources
        2. Consults Ollama Brain for analysis
        3. Gets Thoth AI predictions
        4. Makes autonomous trading decisions
        5. Executes trades automatically
        6. Broadcasts all decisions
        """
        logger.info("🔄 Autonomous decision loop started")
        
        while self.autonomous_mode:
            try:
                # 1. Get market data for all symbols
                market_data = await self._get_comprehensive_market_data(symbols)
                
                # 2. Analyze with Thoth AI (if available)
                thoth_analysis = None
                if self.thoth_ai:
                    thoth_analysis = await self._get_thoth_analysis(market_data)
                
                # 3. Consult Ollama Brain for every symbol
                for symbol, data in market_data.items():
                    try:
                        # Get Ollama decision
                        decision = await self._get_ollama_decision(
                            symbol, data, thoth_analysis
                        )
                        
                        # Execute if confidence meets threshold
                        if decision['confidence'] >= self.autonomous_threshold:
                            await self._execute_autonomous_trade(decision)
                        
                        # Broadcast decision (executed or not)
                        await self._broadcast_decision(decision)
                        
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                # 3b. Global telemetry-driven actions (orders, cancels, mining, transfers)
                try:
                    actions = await self.propose_actions_from_telemetry(list(market_data.keys()))
                    await self._execute_ai_actions(actions)
                except Exception as actions_err:
                    logger.error(f"Error executing telemetry-based AI actions: {actions_err}")
                
                # 4. Wait before next cycle (configurable)
                await asyncio.sleep(1.0)  # 1 second cycle
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in autonomous loop: {e}")
                await asyncio.sleep(5.0)  # Wait longer on error
        
        logger.info("🛑 Autonomous decision loop stopped")
    
    async def accept_user_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accept and execute user trading command
        
        User commands can override autonomous decisions and execute immediately
        
        Args:
            command: Trading command dict with:
                {
                    'action': 'buy'|'sell',
                    'symbol': 'BTC/USDT',
                    'amount': 0.1,
                    'price': optional,
                    'reason': optional user reason
                }
        
        Returns:
            Execution result dict
        """
        try:
            logger.info(f"👤 USER COMMAND: {command}")
            
            # 1. Validate command
            if not self._validate_command(command):
                return {
                    'success': False,
                    'error': 'Invalid command format'
                }
            
            # 2. Get Ollama opinion (non-blocking)
            ollama_opinion = await self._get_ollama_opinion_on_command(command)
            
            # 3. Execute user command (priority execution)
            result = await self._execute_user_command(command, ollama_opinion)
            
            # 4. Track user command
            self.user_commands.append({
                'command': command,
                'timestamp': datetime.now().isoformat(),
                'result': result,
                'ollama_opinion': ollama_opinion
            })
            
            self.user_trades_count += 1
            if result.get('profit'):
                self.total_user_profit += result['profit']
            
            # 5. Broadcast user command execution
            if self.event_bus:
                await self.event_bus.publish('trading.user_command.executed', {
                    'command': command,
                    'result': result,
                    'ollama_opinion': ollama_opinion,
                    'timestamp': datetime.now().isoformat()
                })
            
            logger.info(f"✅ User command executed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error executing user command: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _verify_all_api_keys(self):
        """Verify and connect to ALL available trading APIs"""
        try:
            logger.info("🔑 Verifying ALL API keys...")
            
            if not self.api_key_manager:
                logger.warning("API Key Manager not available")
                return
            
            # Get all API keys
            all_keys = self.api_key_manager.get_all_api_keys()
            
            # Separate by category
            crypto_keys = {}
            stock_keys = {}
            forex_keys = {}
            
            for service, key_data in all_keys.items():
                if not key_data:
                    continue
                    
                # Check if keys are configured
                if isinstance(key_data, dict):
                    has_key = any(
                        key_data.get(k) for k in ['api_key', 'api_secret', 'username', 'client_id']
                    )
                    
                    if has_key:
                        # Categorize
                        if service in self.api_key_manager.CATEGORIES.get('crypto_exchanges', []):
                            crypto_keys[service] = key_data
                            self.connected_exchanges[service] = True
                        elif service in self.api_key_manager.CATEGORIES.get('stock_exchanges', []):
                            stock_keys[service] = key_data
                            self.connected_stock_brokers[service] = True
                        elif service in self.api_key_manager.CATEGORIES.get('forex_trading', []):
                            forex_keys[service] = key_data
                            self.connected_forex_platforms[service] = True
            
            logger.info(f"✅ Connected APIs:")
            logger.info(f"   📈 Crypto Exchanges: {len(crypto_keys)}")
            logger.info(f"   📊 Stock Brokers: {len(stock_keys)}")
            logger.info(f"   💱 Forex Platforms: {len(forex_keys)}")
            
            # Broadcast API status
            if self.event_bus:
                await self.event_bus.publish('trading.api_keys.verified', {
                    'crypto_exchanges': list(crypto_keys.keys()),
                    'stock_brokers': list(stock_keys.keys()),
                    'forex_platforms': list(forex_keys.keys()),
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Error verifying API keys: {e}")
    
    def _on_kaig_directive(self, event_data):
        """Receive KAIG trading directive with all 3 targets."""
        if isinstance(event_data, dict):
            self._kaig_directive = event_data
            # Build a concise brief for injection into every prompt
            floor = event_data.get('kaig_survival_floor', {})
            price_floor = event_data.get('kaig_price_floor', {})
            survival_met = floor.get('survival_met', False)
            self._kaig_brief = (
                f"KAIG TARGETS (you MUST know these):\n"
                f"1. SURVIVAL FLOOR: ${floor.get('required_realized_gains_usd', 26000):,.0f} realized gains needed "
                f"→ ${floor.get('kaig_treasury_target_usd', 13000):,.0f} to KAIG treasury. "
                f"Status: {'MET' if survival_met else 'NOT MET — EXISTENTIAL PRIORITY'}\n"
                f"2. KAIG PRICE FLOOR: 1 KAIG > ${price_floor.get('current_ath_price_usd', 125835.92):,.2f} "
                f"({price_floor.get('current_ath_coin', 'BTC')} ATH). Live-monitored, always surpass.\n"
                f"3. ULTIMATE TARGET: $2,000,000,000,000\n"
                f"Profit routing: 50% of ALL profits → KAIG treasury buyback.\n"
                f"Current profit: ${event_data.get('profit_total_usd', 0):,.2f}"
            )

    def _get_kaig_context(self) -> str:
        """Get KAIG targets context string for injection into all AI prompts."""
        if self._kaig_brief:
            return self._kaig_brief
        # Fallback if bridge hasn't pushed yet
        return (
            "KAIG TARGETS:\n"
            "1. SURVIVAL FLOOR: $26,000 realized gains → $13,000 to KAIG treasury (existential, FIRST)\n"
            "2. KAIG PRICE FLOOR: 1 KAIG > $125,835.93 (highest crypto ATH ever, live-monitored)\n"
            "3. ULTIMATE TARGET: $2,000,000,000,000\n"
            "Profit routing: 50% of ALL profits → KAIG treasury buyback."
        )

    async def _inform_ollama_autonomous_mode(self, symbols: Optional[List[str]]):
        """Inform Ollama Brain that it's in control — with full KAIG target awareness"""
        try:
            if not self.ollama_brain:
                return
            
            kaig_ctx = self._get_kaig_context()
            context = f"""
            You are now in AUTONOMOUS TRADING MODE for Kingdom AI.
            
            === CRITICAL: KAIG FINANCIAL TARGETS ===
            {kaig_ctx}
            
            Your responsibilities:
            - Generate realized trading gains to meet the KAIG survival floor FIRST
            - Every dollar of profit funds KAIG buybacks (50% auto-routes)
            - Analyze all markets continuously for maximum profit
            - Execute trades automatically when confidence is high (>70%)
            - The survival floor is existential — KAIG cannot launch without it
            - 1 KAIG must always be priced higher than the highest crypto ATH ever
            - The $2T ultimate target is always pursued
            
            Available symbols: {symbols or 'ALL markets'}
            Connected exchanges: {len(self.connected_exchanges)}
            Connected brokers: {len(self.connected_stock_brokers)}
            Connected forex: {len(self.connected_forex_platforms)}
            
            You have full authority to trade. Make decisions that maximize REALIZED GAINS.
            All your decisions will be broadcast for transparency.
            User commands can still override your decisions if needed.
            """
            
            # Check if query is async
            import inspect
            if inspect.iscoroutinefunction(self.ollama_brain.query):
                response = await self.ollama_brain.query(context)
            else:
                response = self.ollama_brain.query(context)
            
            logger.info(f"🤖 Ollama Brain acknowledged: {response}")
            
        except Exception as e:
            logger.error(f"Error informing Ollama: {e}")
    
    async def _get_comprehensive_market_data(self, symbols: Optional[List[str]]) -> Dict:
        """Get market data from all sources"""
        try:
            market_data = {}
            
            if self.trading_system:
                # Use trading system to fetch data
                if symbols:
                    for symbol in symbols:
                        try:
                            data = await self._fetch_symbol_data(symbol)
                            if data:
                                market_data[symbol] = data
                        except Exception as e:
                            logger.warning("Fetching symbol data for %s: %s", symbol, e)
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return {}
    
    async def _fetch_symbol_data(self, symbol: str) -> Optional[Dict]:
        """Fetch real-time data for a single symbol via event bus or ccxt."""
        try:
            if self.event_bus:
                response = {'_result': None}
                def _on_data(data):
                    response['_result'] = data
                self.event_bus.subscribe(f'market.data.response.{symbol}', _on_data)
                self.event_bus.publish('market.data.request', {
                    'symbol': symbol, 'timestamp': datetime.now().isoformat()
                })
                await asyncio.sleep(0.5)
                self.event_bus.unsubscribe(f'market.data.response.{symbol}', _on_data)
                if response['_result']:
                    return response['_result']
            try:
                import ccxt
                exchange = ccxt.binance({'enableRateLimit': True})
                ticker = exchange.fetch_ticker(symbol)
                return {
                    'symbol': symbol,
                    'price': ticker.get('last', 0.0),
                    'volume': ticker.get('quoteVolume', 0.0),
                    'bid': ticker.get('bid', 0.0),
                    'ask': ticker.get('ask', 0.0),
                    'high_24h': ticker.get('high', 0.0),
                    'low_24h': ticker.get('low', 0.0),
                    'change_pct': ticker.get('percentage', 0.0),
                    'timestamp': datetime.now().isoformat()
                }
            except ImportError:
                logger.debug("ccxt not available for symbol fetch")
            return {
                'symbol': symbol, 'price': 0.0, 'volume': 0.0,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error("Error fetching symbol data for %s: %s", symbol, e)
            return None
    
    async def _get_thoth_analysis(self, market_data: Dict) -> Optional[Dict]:
        """Get Thoth AI analysis via the orchestrator."""
        try:
            if not self.thoth_ai:
                return None
            import inspect
            symbols = list(market_data.keys())[:10]
            summary = ", ".join(
                f"{s}=${d.get('price', '?')}" for s, d in list(market_data.items())[:10]
            )
            prompt = (
                f"Analyze these markets and provide trading sentiment:\n{summary}\n\n"
                f"Respond JSON: {{\"sentiment\": \"bullish/bearish/neutral\", "
                f"\"confidence\": 0-1, \"top_picks\": [\"SYM\"], \"risk_level\": \"low/medium/high\", "
                f"\"recommendations\": {{\"SYM\": \"buy/sell/hold\"}}}}"
            )
            if inspect.iscoroutinefunction(getattr(self.thoth_ai, 'query', None)):
                response = await self.thoth_ai.query(prompt)
            elif hasattr(self.thoth_ai, 'query'):
                response = self.thoth_ai.query(prompt)
            else:
                return None
            try:
                return json.loads(response)
            except (json.JSONDecodeError, TypeError):
                return {'sentiment': 'neutral', 'confidence': 0.5, 'raw': str(response)[:200]}
        except Exception as e:
            logger.error("Error getting Thoth analysis: %s", e)
            return None
    
    async def _get_ollama_decision(self, symbol: str, data: Dict, 
                                   thoth_analysis: Optional[Dict]) -> Dict:
        """Get Ollama Brain trading decision"""
        try:
            if not self.ollama_brain:
                return {'action': 'hold', 'confidence': 0.0}
            
            # Try to get full unified analysis from TradingSignalGenerator
            unified_analysis: Optional[Dict[str, Any]] = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                sg = self.event_bus.get_component('trading_signal_generator') or self.event_bus.get_component('signal_generator')
                if sg and hasattr(sg, '_run_unified_analysis'):
                    try:
                        unified_analysis = await sg._run_unified_analysis(symbol)
                    except Exception as ua_err:
                        logger.debug("Unified analysis unavailable for %s: %s", symbol, ua_err)
            
            telemetry_snapshot: Dict[str, Any] = {}
            if self.telemetry:
                try:
                    telemetry_snapshot = self._build_telemetry_snapshot([symbol])
                except Exception as snapshot_err:
                    logger.error(f"Error getting telemetry snapshot: {snapshot_err}")

            snapshot_text = ""
            if telemetry_snapshot:
                try:
                    snapshot_text = json.dumps(telemetry_snapshot, default=str)[:4000]
                except Exception:
                    snapshot_text = ""

            kaig_ctx = self._get_kaig_context()
            # Build market data section: full unified analysis if available, else basic
            if unified_analysis:
                unified_text = json.dumps(unified_analysis, default=str)[:8000]
                market_data_section = f"""
            FULL UNIFIED ANALYSIS (price, RSI, MACD, Bollinger, S/R, order book, sentiment, arbitrage, etc.):
            {unified_text}
            """
            else:
                market_data_section = f"""
            Symbol: {symbol}
            Current Price: {data.get('price', 'N/A')}
            Volume: {data.get('volume', 'N/A')}
            """
            prompt = f"""
            {kaig_ctx}
            
            Analyze this trading opportunity and make a decision:
            
            {market_data_section}
            
            {f"Thoth AI Analysis: {json.dumps(thoth_analysis)}" if thoth_analysis else ""}
            
            Telemetry Snapshot (recent trading/mining events, JSON truncated):
            {snapshot_text}
            
            REMEMBER: Every profitable trade funds KAIG buybacks. Maximize realized gains.
            
            Respond with JSON:
            {{
                "action": "buy" | "sell" | "hold",
                "confidence": 0.0-1.0,
                "amount": recommended trade amount,
                "reason": "brief explanation",
                "mining_actions": {{
                    "start": ["COIN1", "COIN2"],
                    "stop": ["COIN3"],
                    "mode": "focused" | "all"
                }},
                "funds_actions": [
                    {{"from_wallet": "...", "to_wallet": "...", "asset": "...", "amount": 0.0, "reason": "..."}}
                ]
            }}
            """
            
            # Query Ollama
            import inspect
            if inspect.iscoroutinefunction(self.ollama_brain.query):
                response = await self.ollama_brain.query(prompt)
            else:
                response = self.ollama_brain.query(prompt)
            
            # Parse response
            try:
                decision = json.loads(response)
                decision['symbol'] = symbol
                decision['timestamp'] = datetime.now().isoformat()
                decision['source'] = 'ollama_autonomous'
                return decision
            except:
                # Fallback if JSON parsing fails
                return {
                    'symbol': symbol,
                    'action': 'hold',
                    'confidence': 0.0,
                    'reason': 'Failed to parse decision',
                    'timestamp': datetime.now().isoformat(),
                    'source': 'ollama_autonomous'
                }
                
        except Exception as e:
            logger.error(f"Error getting Ollama decision: {e}")
            return {'action': 'hold', 'confidence': 0.0}

    def _build_telemetry_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {}
        if not self.telemetry:
            return snapshot
        try:
            trading_events = self.telemetry.get_recent_domain_events("trading", limit=200)
            mining_events = self.telemetry.get_recent_domain_events("mining", limit=200)
            snapshot["trading_events"] = trading_events
            snapshot["mining_events"] = mining_events
            if symbols:
                per_symbol: Dict[str, Any] = {}
                for s in symbols:
                    if not s:
                        continue
                    per_symbol[s] = self.telemetry.get_recent_symbol_events("trading", s, limit=50)
                snapshot["per_symbol"] = per_symbol
        except Exception as e:
            logger.error(f"Error building telemetry snapshot: {e}")
        return snapshot

    async def propose_actions_from_telemetry(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.ollama_brain or not self.telemetry:
            return {"orders": [], "cancels": [], "mining": {}, "transfers": []}
        try:
            snapshot = self._build_telemetry_snapshot(symbols)
            payload = {
                "telemetry": snapshot,
                "symbols": symbols or [],
                "autonomous_threshold": self.autonomous_threshold,
            }
            kaig_ctx = self._get_kaig_context()
            prompt = (
                "You are the autonomous trading and mining brain for Kingdom AI. "
                f"{kaig_ctx}\n\n"
                "You receive recent trading.telemetry and mining.telemetry events as JSON. "
                "Every profitable trade/mining reward funds KAIG buybacks (50% auto-routes to treasury). "
                "Decide what actions to take now and respond strictly as JSON with the shape:\n"
                "{\n"
                '  "orders": [\n'
                '    {"symbol": "...", "action": "buy|sell", "amount": 0.0, "price": null, "reason": "..."}\n'
                "  ],\n"
                '  "cancels": [\n'
                '    {"order_id": "...", "reason": "..."}\n'
                "  ],\n"
                '  "mining": {\n'
                '    "start": ["COIN1", "COIN2"],\n'
                '    "stop": ["COIN3"],\n'
                '    "mode": "focused|all"\n'
                "  },\n"
                '  "transfers": [\n'
                '    {"from_wallet": "...", "to_wallet": "...", "asset": "...", "amount": 0.0, "reason": "..."}\n'
                "  ],\n"
                '  "ui_actions": [\n'
                '    {"event": "trading.status | trading.automated.status | trading.order.submit | '
                'mining.rewards.funnel | mining.prediction.update | mining.recommendation.applied | '
                'blockchain.refresh.request | airdrop.farming.changed | airdrop.scan.request | '
                'quantum_mining.started | quantum_mining.stopped", "payload": {"...": "..."}}\n'
                "  ]\n"
                "}\n"
                "Only use ui_actions for these whitelisted events. Base your decisions only on the telemetry "
                "snapshot and be conservative if data is sparse."
            )
            prompt_json = json.dumps(payload, default=str)
            full_prompt = prompt + "\n\nTELEMETRY_SNAPSHOT_JSON:\n" + prompt_json
            import inspect
            if inspect.iscoroutinefunction(self.ollama_brain.query):
                response = await self.ollama_brain.query(full_prompt)
            else:
                response = self.ollama_brain.query(full_prompt)
            try:
                parsed = json.loads(response)
                if not isinstance(parsed, dict):
                    return {"orders": [], "cancels": [], "mining": {}, "transfers": [], "ui_actions": []}
                parsed.setdefault("orders", [])
                parsed.setdefault("cancels", [])
                parsed.setdefault("mining", {})
                parsed.setdefault("transfers", [])
                parsed.setdefault("ui_actions", [])
                return parsed
            except Exception:
                return {"orders": [], "cancels": [], "mining": {}, "transfers": [], "ui_actions": []}
        except Exception as e:
            logger.error(f"Error proposing actions from telemetry: {e}")
            return {"orders": [], "cancels": [], "mining": {}, "transfers": [], "ui_actions": []}
    
    async def _execute_ai_actions(self, actions: Dict[str, Any]) -> None:
        """Execute AI-proposed actions using existing trading, mining, and wallet flows.

        This method only *adds* EventBus publications and manager calls; it does not
        change any existing handlers or business logic.
        """
        try:
            if not isinstance(actions, dict):
                return

            bus = self.event_bus

            # Orders -> trading.execute_order
            orders = actions.get("orders") or []
            if bus and isinstance(orders, list):
                for order in orders:
                    if not isinstance(order, dict):
                        continue
                    symbol = order.get("symbol")
                    side_raw = order.get("action") or order.get("side")
                    amount_raw = order.get("amount")
                    price_raw = order.get("price")
                    if not symbol or not side_raw or amount_raw is None:
                        continue
                    try:
                        qty = float(amount_raw)
                    except (TypeError, ValueError):
                        continue
                    side = str(side_raw).lower()
                    if side not in ("buy", "sell"):
                        continue
                    order_payload = {
                        "symbol": symbol,
                        "side": side,
                        "type": "market" if not price_raw else "limit",
                        "amount": qty,
                    }
                    if price_raw is not None:
                        try:
                            order_payload["price"] = float(price_raw)
                        except (TypeError, ValueError) as e:
                            logger.warning("Converting order price: %s", e)
                    try:
                        bus.publish("trading.execute_order", {"order": order_payload})
                    except Exception as pub_err:
                        logger.error(f"Error publishing trading.execute_order: {pub_err}")

            # Cancels -> trading.cancel_order
            cancels = actions.get("cancels") or []
            if bus and isinstance(cancels, list):
                for cancel in cancels:
                    if not isinstance(cancel, dict):
                        continue
                    order_id = cancel.get("order_id")
                    if not order_id:
                        continue
                    try:
                        bus.publish("trading.cancel_order", {"order_id": order_id})
                    except Exception as pub_err:
                        logger.error(f"Error publishing trading.cancel_order: {pub_err}")

            # Mining control -> mining.start / mining.stop / mining.focus.update
            mining = actions.get("mining") or {}
            if bus and isinstance(mining, dict):
                mode_raw = mining.get("mode") or ""
                start_list = mining.get("start") or []
                stop_list = mining.get("stop") or []

                focus_payload: Dict[str, Any] = {}
                mode_str = str(mode_raw).lower()
                if mode_str in ("focused", "all"):
                    focus_payload["mode"] = mode_str
                enabled_coins = [str(c).upper() for c in start_list if c]
                if enabled_coins:
                    focus_payload["enabled_coins"] = enabled_coins
                if focus_payload:
                    try:
                        bus.publish("mining.focus.update", focus_payload)
                    except Exception as pub_err:
                        logger.error(f"Error publishing mining.focus.update: {pub_err}")

                # Multi-coin mining start/stop: use existing MiningSystem event API
                try:
                    if start_list:
                        bus.publish("mining.start", {"mode": "multi_coin"})
                    if stop_list:
                        bus.publish("mining.stop", {})
                except Exception as pub_err:
                    logger.error(f"Error publishing mining start/stop events: {pub_err}")

            # Wallet transfers -> wallet.autonomous.transfer + optional WalletManager
            transfers = actions.get("transfers") or []
            if isinstance(transfers, list):
                for tr in transfers:
                    if not isinstance(tr, dict):
                        continue
                    # Always publish an event so other components can observe
                    if bus:
                        try:
                            bus.publish("wallet.autonomous.transfer", tr)
                        except Exception as pub_err:
                            logger.error(f"Error publishing wallet.autonomous.transfer: {pub_err}")

                    # Optional direct call into a WalletManager if provided
                    if self.wallet_manager and hasattr(self.wallet_manager, "send_transaction"):
                        try:
                            asset = tr.get("asset") or tr.get("network")
                            to_address = tr.get("to_wallet") or tr.get("to_address")
                            amount_raw = tr.get("amount")
                            if not asset or not to_address or amount_raw is None:
                                continue
                            try:
                                amount_val = float(amount_raw)
                            except (TypeError, ValueError):
                                continue
                            send_fn = getattr(self.wallet_manager, "send_transaction")
                            if asyncio.iscoroutinefunction(send_fn):
                                await send_fn(asset, to_address, amount_val)
                            else:
                                send_fn(asset, to_address, amount_val)
                        except Exception as wallet_err:
                            logger.error(f"Error executing wallet transfer: {wallet_err}")

            # UI-level actions mapped to specific EventBus events
            ui_actions = actions.get("ui_actions") or []
            allowed_ui_events = {
                "trading.status",
                "trading.automated.status",
                "trading.order.submit",
                "mining.rewards.funnel",
                "mining.prediction.update",
                "mining.recommendation.applied",
                "blockchain.refresh.request",
                "airdrop.farming.changed",
                "airdrop.scan.request",
                "quantum_mining.started",
                "quantum_mining.stopped",
                # GPU / Quantum commands (request topics)
                "gpu.quantum.optimize.request",
                "gpu.devices.detect.request",
                "mining.gpu.benchmark.request",
            }
            if bus and isinstance(ui_actions, list):
                for act in ui_actions:
                    if not isinstance(act, dict):
                        continue
                    event = act.get("event")
                    payload = act.get("payload") or {}
                    if not event or event not in allowed_ui_events or not isinstance(payload, dict):
                        continue
                    try:
                        bus.publish(event, payload)
                    except Exception as pub_err:
                        logger.error(f"Error publishing UI action {event}: {pub_err}")

        except Exception as e:
            logger.error(f"Error executing AI actions: {e}")
    
    async def _execute_autonomous_trade(self, decision: Dict):
        """Execute autonomous trade through the trading system and event bus."""
        try:
            action = decision.get('action', 'hold')
            symbol = decision.get('symbol', '')
            confidence = decision.get('confidence', 0)
            amount = decision.get('amount', 0)
            logger.info("🤖 AUTONOMOUS TRADE: %s %s (conf=%.2f%%, amt=%s)",
                        action, symbol, confidence * 100, amount)

            if action == 'hold':
                logger.info("HOLD decision — no trade executed")
                with self._ato_lock:
                    self.autonomous_decisions.append(decision)
                return

            trade_order = {
                'action': action,
                'symbol': symbol,
                'amount': amount,
                'confidence': confidence,
                'reason': decision.get('reason', ''),
                'source': 'autonomous_orchestrator',
                'timestamp': datetime.now().isoformat()
            }

            if self.trading_system and hasattr(self.trading_system, 'execute_trade'):
                import inspect
                if inspect.iscoroutinefunction(self.trading_system.execute_trade):
                    result = await self.trading_system.execute_trade(trade_order)
                else:
                    result = self.trading_system.execute_trade(trade_order)
                decision['execution_result'] = result

            if self.event_bus:
                self.event_bus.publish('trading.autonomous.executed', trade_order)

            mining_actions = decision.get('mining_actions')
            if mining_actions and self.event_bus:
                self.event_bus.publish('mining.directive.from_trading', mining_actions)

            funds_actions = decision.get('funds_actions')
            if funds_actions and self.event_bus:
                for fa in funds_actions:
                    self.event_bus.publish('wallet.transfer.request', fa)

            with self._ato_lock:
                self.autonomous_trades_count += 1
                self.autonomous_decisions.append(decision)

        except Exception as e:
            logger.error("Error executing autonomous trade: %s", e)
    
    async def _broadcast_decision(self, decision: Dict):
        """Broadcast trading decision to all systems"""
        try:
            if self.event_bus:
                await self.event_bus.publish('trading.autonomous.decision', decision)
        except Exception as e:
            logger.error(f"Error broadcasting decision: {e}")
    
    def _validate_command(self, command: Dict) -> bool:
        """Validate user command format"""
        required_fields = ['action', 'symbol']
        return all(field in command for field in required_fields)
    
    async def _get_ollama_opinion_on_command(self, command: Dict) -> Dict:
        """Get Ollama's opinion on user command"""
        try:
            if not self.ollama_brain:
                return {'opinion': 'unavailable'}
            
            prompt = f"""
            User wants to execute this trade command:
            {json.dumps(command)}
            
            Provide your opinion on this trade. Is it a good idea?
            Respond with JSON:
            {{
                "opinion": "agree" | "neutral" | "disagree",
                "confidence": 0.0-1.0,
                "reason": "brief explanation",
                "alternative": "optional alternative suggestion"
            }}
            """
            
            # Query Ollama
            import inspect
            if inspect.iscoroutinefunction(self.ollama_brain.query):
                response = await self.ollama_brain.query(prompt)
            else:
                response = self.ollama_brain.query(prompt)
            
            try:
                return json.loads(response)
            except:
                return {'opinion': 'unavailable', 'reason': 'Parse error'}
                
        except Exception as e:
            logger.error(f"Error getting Ollama opinion: {e}")
            return {'opinion': 'error', 'reason': str(e)}
    
    async def _execute_user_command(self, command: Dict, ollama_opinion: Dict) -> Dict:
        """Execute user command (priority execution)."""
        try:
            logger.info("👤 Executing user command: %s", command)
            logger.info("🤖 Ollama opinion: %s", ollama_opinion.get('opinion'))

            trade_order = {
                'action': command.get('action', 'buy'),
                'symbol': command.get('symbol', ''),
                'amount': command.get('amount', 0),
                'source': 'user_command',
                'ollama_opinion': ollama_opinion.get('opinion', 'unavailable'),
                'timestamp': datetime.now().isoformat()
            }

            exec_result = None
            if self.trading_system and hasattr(self.trading_system, 'execute_trade'):
                import inspect
                if inspect.iscoroutinefunction(self.trading_system.execute_trade):
                    exec_result = await self.trading_system.execute_trade(trade_order)
                else:
                    exec_result = self.trading_system.execute_trade(trade_order)

            if self.event_bus:
                self.event_bus.publish('trading.user.command.executed', trade_order)

            return {
                'success': True,
                'command': command,
                'ollama_opinion': ollama_opinion,
                'execution_result': exec_result,
                'executed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("Error executing user command: %s", e)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of autonomous trading"""
        return {
            'autonomous_mode': self.autonomous_mode,
            'connected_exchanges': len(self.connected_exchanges),
            'connected_brokers': len(self.connected_stock_brokers),
            'connected_forex': len(self.connected_forex_platforms),
            'autonomous_trades': self.autonomous_trades_count,
            'user_trades': self.user_trades_count,
            'autonomous_profit': self.total_autonomous_profit,
            'user_profit': self.total_user_profit,
            'total_profit': self.total_autonomous_profit + self.total_user_profit,
            'ollama_available': self.ollama_brain is not None,
            'thoth_available': self.thoth_ai is not None
        }
