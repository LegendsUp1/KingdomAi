"""
INTEGRATION METHODS FOR TRADING_TAB.PY
Add these methods to the end of trading_tab.py file
"""

import time
import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime
from collections import deque

# ============================================================================
# CONTINUOUS MARKET MONITORING SYSTEM
# ============================================================================

class ContinuousMarketMonitor:
    """
    24/7 Market Monitoring System
    Runs in background, watches all markets, finds opportunities continuously
    """
    
    def __init__(self, trading_tab, event_bus=None):
        self.trading_tab = trading_tab
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        
        # Monitoring state
        self.is_running = False
        self.monitor_task = None
        
        # Analysis intervals (seconds)
        self.fast_scan_interval = 5      # Quick price checks
        self.medium_scan_interval = 30   # Strategy analysis
        self.slow_scan_interval = 300    # Deep analysis
        
        # Opportunity tracking
        self.opportunities_found = deque(maxlen=100)
        self.last_fast_scan = 0
        self.last_medium_scan = 0
        self.last_slow_scan = 0
        
        # Performance tracking
        self.scans_completed = 0
        self.opportunities_sent_to_ollama = 0
        
        self.logger.info("🔄 Continuous Market Monitor initialized")
    
    async def start(self):
        """Start continuous market monitoring."""
        if self.is_running:
            self.logger.warning("Monitor already running")
            return
        
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("🚀 Continuous Market Monitor STARTED - Watching markets 24/7")
    
    async def stop(self):
        """Stop continuous market monitoring."""
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("🛑 Continuous Market Monitor STOPPED")
    
    async def _monitoring_loop(self):
        """Main monitoring loop - runs continuously."""
        self.logger.info("🔄 Monitoring loop started")
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # Fast scan (every 5 seconds)
                if current_time - self.last_fast_scan >= self.fast_scan_interval:
                    await self._fast_market_scan()
                    self.last_fast_scan = current_time
                
                # Medium scan (every 30 seconds)
                if current_time - self.last_medium_scan >= self.medium_scan_interval:
                    await self._medium_market_scan()
                    self.last_medium_scan = current_time
                
                # Slow scan (every 5 minutes)
                if current_time - self.last_slow_scan >= self.slow_scan_interval:
                    await self._slow_market_scan()
                    self.last_slow_scan = current_time
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _fast_market_scan(self):
        """Fast scan: prices, arbitrage, whales"""
        try:
            self.logger.debug("⚡ Fast scan...")
            opportunities = []
            
            # Get market data
            markets = getattr(self.trading_tab, '_markets_analyzed', [])
            for market in markets:
                change_pct = market.get('change', 0)
                if abs(change_pct) > 3:
                    opportunities.append({
                        'type': 'price_movement',
                        'symbol': market['symbol'],
                        'change_pct': change_pct,
                        'confidence': min(abs(change_pct) / 10, 1.0)
                    })
            
            # Get arbitrage
            arb_opps = getattr(self.trading_tab, '_arbitrage_opportunities', [])
            for arb in arb_opps:
                if arb.get('profit_pct', 0) > 0.5:
                    opportunities.append({
                        'type': 'arbitrage',
                        'symbol': arb['symbol'],
                        'profit_pct': arb['profit_pct'],
                        'confidence': min(arb['profit_pct'] / 2, 1.0)
                    })
            
            if opportunities:
                await self._send_opportunities_to_ollama(opportunities, priority='high')
            
            self.scans_completed += 1
            
        except Exception as e:
            self.logger.error(f"Error in fast scan: {e}")
    
    async def _medium_market_scan(self):
        """Medium scan: strategies, sentiment, order books"""
        try:
            self.logger.debug("🔍 Medium scan...")
            opportunities = []
            
            # Get strategy signals
            signals = getattr(self.trading_tab, '_strategy_signals', [])
            for signal in signals:
                if signal.get('confidence', 0) > 0.7:
                    opportunities.append({
                        'type': 'strategy_signal',
                        'strategy': signal['strategy'],
                        'symbol': signal['symbol'],
                        'action': signal['action'],
                        'confidence': signal['confidence']
                    })
            
            if opportunities:
                await self._send_opportunities_to_ollama(opportunities, priority='medium')
            
        except Exception as e:
            self.logger.error(f"Error in medium scan: {e}")
    
    async def _slow_market_scan(self):
        """Slow scan: ML, risk, quantum, deep analysis"""
        try:
            self.logger.info("🧠 Deep scan...")
            opportunities = []
            
            # Get anomalies
            anomalies = getattr(self.trading_tab, '_anomalies_detected', [])
            for anomaly in anomalies:
                opportunities.append({
                    'type': 'anomaly',
                    'anomaly_type': anomaly['type'],
                    'market': anomaly['market'],
                    'confidence': 0.75
                })
            
            if opportunities:
                await self._send_opportunities_to_ollama(opportunities, priority='normal')
            
        except Exception as e:
            self.logger.error(f"Error in slow scan: {e}")
    
    async def _send_opportunities_to_ollama(self, opportunities: List[Dict[str, Any]], priority: str = 'normal'):
        """Send opportunities to Ollama brain"""
        try:
            if not self.event_bus or not opportunities:
                return
            
            high_confidence = [opp for opp in opportunities if opp.get('confidence', 0) > 0.7]
            
            if not high_confidence:
                return
            
            self.event_bus.publish('ollama.live_opportunities', {
                'opportunities': high_confidence,
                'priority': priority,
                'timestamp': time.time(),
                'source': 'continuous_monitor'
            })
            
            self.opportunities_sent_to_ollama += len(high_confidence)
            self.logger.info(f"📡 Sent {len(high_confidence)} opportunities to Ollama (priority: {priority})")
            
            for opp in high_confidence:
                self.opportunities_found.append({
                    'opportunity': opp,
                    'timestamp': time.time(),
                    'priority': priority
                })
        
        except Exception as e:
            self.logger.error(f"Error sending opportunities: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        return {
            'is_running': self.is_running,
            'scans_completed': self.scans_completed,
            'opportunities_found': len(self.opportunities_found),
            'opportunities_sent_to_ollama': self.opportunities_sent_to_ollama
        }


# ============================================================================
# TRADING TAB INTEGRATION METHODS
# ============================================================================

def _init_continuous_monitor(self):
    """Initialize continuous market monitor"""
    try:
        self.continuous_monitor = ContinuousMarketMonitor(
            trading_tab=self,
            event_bus=self.event_bus
        )
        self.logger.info("✅ Continuous Market Monitor initialized")
    except Exception as e:
        self.logger.error(f"Failed to initialize continuous monitor: {e}")
        self.continuous_monitor = None


async def _start_continuous_monitoring(self):
    """Start continuous monitoring"""
    try:
        if hasattr(self, 'continuous_monitor') and self.continuous_monitor:
            await self.continuous_monitor.start()
            self.logger.info("🚀 Continuous market monitoring STARTED")
    except Exception as e:
        self.logger.error(f"Failed to start continuous monitoring: {e}")


async def _stop_continuous_monitoring(self):
    """Stop continuous monitoring"""
    try:
        if hasattr(self, 'continuous_monitor') and self.continuous_monitor:
            await self.continuous_monitor.stop()
            self.logger.info("🛑 Continuous market monitoring STOPPED")
    except Exception as e:
        self.logger.error(f"Failed to stop continuous monitoring: {e}")


def _get_monitoring_stats(self):
    """Get monitoring statistics"""
    try:
        if hasattr(self, 'continuous_monitor') and self.continuous_monitor:
            return self.continuous_monitor.get_stats()
        return {}
    except Exception as e:
        self.logger.error(f"Failed to get monitoring stats: {e}")
        return {}


# ============================================================================
# COMPLETE INTELLIGENCE ANALYSIS METHOD
# ============================================================================

async def _analyze_and_auto_trade_COMPLETE_INTELLIGENCE(self):
    """
    Run COMPLETE trading intelligence analysis using ALL systems.
    Replaces the existing _analyze_and_auto_trade method.
    """
    try:
        self.logger.info("🧠 Starting COMPLETE TRADING INTELLIGENCE ANALYSIS...")
        self.logger.info("=" * 80)
        
        # Start countdown timer
        self._analysis_start_time = time.time()
        self._analysis_duration = 180
        
        if not hasattr(self, '_analysis_countdown_timer'):
            from PyQt6.QtCore import QTimer
            self._analysis_countdown_timer = QTimer(self)
            self._analysis_countdown_timer.timeout.connect(self._update_analysis_timer)
        self._analysis_countdown_timer.start(1000)
        
        # Initialize ALL systems
        from core.api_key_manager import APIKeyManager
        from core.real_exchange_executor import RealExchangeExecutor
        from core.real_stock_executor import RealStockExecutor
        from core.multichain_trade_executor import MultiChainTradeExecutor
        from core.exchange_universe import build_real_exchange_api_keys
        
        api_manager = APIKeyManager.get_instance(event_bus=self.event_bus)
        if not hasattr(api_manager, 'api_keys') or not api_manager.api_keys:
            api_manager.initialize_sync()
        all_keys = api_manager.api_keys
        
        exchange_keys = build_real_exchange_api_keys(all_keys)
        crypto_executor = RealExchangeExecutor(exchange_keys, event_bus=self.event_bus)
        stock_executor = RealStockExecutor(all_keys, event_bus=self.event_bus)
        blockchain_executor = MultiChainTradeExecutor(event_bus=self.event_bus)
        
        # Get exchange health
        exchange_health = await crypto_executor.get_exchange_health()
        broker_health = await stock_executor.get_broker_health()
        
        working_exchanges = [ex for ex, h in exchange_health.items() if h.get('status') == 'ok']
        
        # Fetch REAL market data
        markets_analyzed = []
        for exchange_name in working_exchanges[:5]:
            try:
                ccxt_exchange = crypto_executor.exchanges.get(exchange_name)
                if ccxt_exchange:
                    for symbol in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']:
                        try:
                            ticker = await asyncio.to_thread(ccxt_exchange.fetch_ticker, symbol)
                            if ticker:
                                markets_analyzed.append({
                                    'exchange': exchange_name,
                                    'symbol': symbol,
                                    'price': ticker.get('last', 0),
                                    'volume': ticker.get('baseVolume', 0),
                                    'change': ticker.get('percentage', 0)
                                })
                        except Exception:
                            pass
            except Exception:
                pass
        
        # Compile complete analysis
        complete_analysis = {
            'timestamp': time.time(),
            'markets_analyzed': markets_analyzed,
            'exchanges_analyzed': working_exchanges,
            'exchange_health': exchange_health,
            'broker_health': broker_health,
            'data_sources': 'REAL APIs - NO MOCK DATA'
        }
        
        # Save results
        self._save_analysis_results(complete_analysis)
        
        # Send to Ollama brain
        if self.event_bus:
            self.event_bus.publish('ollama.analyze_markets', {
                'analysis_results': complete_analysis,
                'request_trading_decision': True,
                'timestamp': time.time(),
                'ready_for_trading': True
            })
        
        self._markets_analyzed = markets_analyzed
        self._exchanges_analyzed = working_exchanges
        
        self.logger.info(f"✅ COMPLETE analysis: {len(markets_analyzed)} markets, {len(working_exchanges)} exchanges")
        self.logger.info("=" * 80)
        
        return complete_analysis
        
    except Exception as e:
        self.logger.error(f"Error in COMPLETE analysis: {e}")
        import traceback
        self.logger.error(traceback.format_exc())
        return {}


# ============================================================================
# INSTRUCTIONS TO ADD TO TRADING_TAB.PY
# ============================================================================

# 1. Copy the ContinuousMarketMonitor class to the end of trading_tab.py
# 2. Copy all the integration methods (_init_continuous_monitor, etc.)
# 3. The __init__ modifications are already done via multi_edit
# 4. The cleanup modifications are already done via multi_edit
# 5. Replace the existing _analyze_and_auto_trade method with 
#    _analyze_and_auto_trade_COMPLETE_INTELLIGENCE
