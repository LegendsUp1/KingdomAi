"""
State persistence methods for TradingTab - Auto-injected at runtime
"""
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def _init_state_persistence(self):
    """Initialize state persistence for trading data - CRITICAL for data retention."""
    try:
        from core.system_state_manager import register_state_provider
        
        # Register state provider
        register_state_provider('trading_tab', self._get_trading_state)
        self.logger.info("✅ TradingTab state persistence enabled")
        
    except Exception as e:
        self.logger.error(f"Failed to init state persistence: {e}")


def _get_trading_state(self) -> Dict[str, Any]:
    """Get current trading state for persistence - SAVES ANALYSIS DATA."""
    try:
        return {
            'timestamp': time.time(),
            'last_analysis': {
                'time': getattr(self, '_analysis_start_time', None),
                'duration': getattr(self, '_analysis_duration', None),
                'results': getattr(self, '_last_analysis_results', {}),
                'verified': getattr(self, '_analysis_verified', False),
            },
            'auto_trade': {
                'active': getattr(self, 'auto_trade_active', False),
                'risk_level': getattr(self, '_risk_level', 'medium'),
            },
            'trading_data': {
                'positions': getattr(self, '_open_positions', []),
                'history': getattr(self, '_trade_history', [])[-100:],
            },
            'market_analysis': {
                'markets_analyzed': getattr(self, '_markets_analyzed', []),
                'exchanges_analyzed': getattr(self, '_exchanges_analyzed', []),
                'blockchains_analyzed': getattr(self, '_blockchains_analyzed', []),
            }
        }
    except Exception as e:
        self.logger.error(f"Error getting trading state: {e}")
        return {}


# Auto-inject methods into TradingTab class at import time
try:
    from gui.qt_frames.trading.trading_tab import TradingTab
    TradingTab._init_state_persistence = _init_state_persistence
    TradingTab._get_trading_state = _get_trading_state
    logger.info("✅ State persistence methods injected into TradingTab")
except Exception as e:
    logger.debug(f"State persistence injection deferred: {e}")
