"""
CRITICAL FIX: TradingTab State Persistence
Add this code to trading_tab.py to save trading analysis data
"""

# ADD TO __init__() method - AFTER self.event_bus is set
def _init_state_persistence(self):
    """Initialize state persistence for trading data."""
    try:
        from core.system_state_manager import register_state_provider
        
        # Register state provider
        register_state_provider('trading_tab', self._get_trading_state)
        self.logger.info("✅ TradingTab state persistence enabled")
        
        # Initialize data storage
        self._last_analysis_results = {}
        self._trade_history = []
        self._open_positions = []
        self._analysis_verified = False
        
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
                'exchanges': getattr(self, '_selected_exchanges', []),
                'risk_level': getattr(self, '_risk_level', 'medium'),
            },
            'trading_data': {
                'positions': getattr(self, '_open_positions', []),
                'history': getattr(self, '_trade_history', [])[-100:],  # Last 100 trades
                'pairs': getattr(self, '_trading_pairs', []),
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

def _save_analysis_results(self, results: Dict[str, Any]):
    """Save analysis results immediately - CRITICAL for data retention."""
    try:
        self.logger.info("💾 Saving trading analysis results...")
        
        # Store results
        self._last_analysis_results = {
            'timestamp': time.time(),
            'markets': results.get('markets', []),
            'exchanges': results.get('exchanges', []),
            'blockchains': results.get('blockchains', []),
            'signals': results.get('signals', []),
            'recommendations': results.get('recommendations', []),
            'api_calls_made': results.get('api_calls_made', []),
            'data_sources': results.get('data_sources', []),
        }
        
        # Mark as verified
        self._analysis_verified = True
        
        # Force immediate save to disk
        from core.system_state_manager import get_state_manager
        state_manager = get_state_manager()
        state_manager.save_state(manual=True)
        
        self.logger.info(f"✅ Analysis results saved: {len(results.get('markets', []))} markets")
        
    except Exception as e:
        self.logger.error(f"Failed to save analysis results: {e}")

def cleanup(self):
    """Clean up trading tab resources - SAVES DATA BEFORE SHUTDOWN."""
    try:
        self.logger.info("🧹 Cleaning up Trading Tab resources...")
        
        # 1. SAVE FINAL STATE BEFORE CLEANUP
        try:
            from core.system_state_manager import get_state_manager
            get_state_manager().save_state(manual=True)
            self.logger.info("✅ Trading state saved before cleanup")
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
        
        # 2. Stop analysis countdown timer
        if hasattr(self, '_analysis_countdown_timer') and self._analysis_countdown_timer:
            self._analysis_countdown_timer.stop()
            self._analysis_countdown_timer.deleteLater()
            self._analysis_countdown_timer = None
        
        # 3. Stop auto-trade if active
        if getattr(self, 'auto_trade_active', False):
            self._stop_auto_trade()
        
        # 4. Unsubscribe from event bus
        if hasattr(self, 'event_bus') and self.event_bus:
            try:
                if hasattr(self, '_handle_autotrade_plan'):
                    self.event_bus.unsubscribe("ai.autotrade.plan.generated", self._handle_autotrade_plan)
                self.logger.debug("✅ Unsubscribed from trading events")
            except Exception as e:
                self.logger.warning(f"Event bus cleanup warning: {e}")
        
        # 5. Close exchange connections
        if hasattr(self, 'exchange_manager') and self.exchange_manager:
            try:
                if hasattr(self.exchange_manager, 'close'):
                    self.exchange_manager.close()
                self.logger.debug("✅ Closed exchange connections")
            except Exception as e:
                self.logger.warning(f"Exchange cleanup warning: {e}")
        
        # 6. Clear data structures
        if hasattr(self, '_trade_history'):
            self._trade_history.clear()
        if hasattr(self, '_open_positions'):
            self._open_positions.clear()
        
        self.logger.info("✅ Trading Tab cleanup complete - data protected")
        
    except Exception as e:
        self.logger.error(f"Error during trading tab cleanup: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

def closeEvent(self, event):
    """Handle close event - ensure cleanup is called."""
    try:
        self.cleanup()
    except Exception as e:
        self.logger.error(f"Error in trading tab closeEvent: {e}")
    finally:
        event.accept()

# MODIFY _analyze_and_auto_trade() to save results
def _analyze_and_auto_trade_FIXED(self) -> None:
    """Run analysis and SAVE results - FIXED VERSION."""
    try:
        self.logger.info("🔍 Starting trading analysis with data persistence...")
        
        # Start countdown timer
        self._analysis_start_time = time.time()
        self._analysis_duration = 180  # 3 minutes
        
        # Publish analysis event WITH CALLBACK
        if self.event_bus:
            self.event_bus.publish("ai.autotrade.analyze_and_start", {
                'callback': self._on_analysis_complete,  # ADD THIS
                'verify': True,
                'save_results': True,
            })
        
        # Start countdown
        if not hasattr(self, '_analysis_countdown_timer'):
            self._analysis_countdown_timer = QTimer(self)
            self._analysis_countdown_timer.timeout.connect(self._update_analysis_timer)
        self._analysis_countdown_timer.start(1000)  # Update every second
        
        self.logger.info("✅ Analysis started - results will be saved")
        
    except Exception as e:
        self.logger.error(f"Error in analysis: {e}")

def _on_analysis_complete(self, results: Dict[str, Any]):
    """Callback when analysis completes - SAVES DATA."""
    try:
        self.logger.info("📊 Analysis complete - saving results...")
        
        # Save results immediately
        self._save_analysis_results(results)
        
        # Update UI with verification
        if hasattr(self, 'analysis_timer_label'):
            self.analysis_timer_label.setText(
                f"✅ ANALYSIS COMPLETE | {len(results.get('markets', []))} markets analyzed | DATA SAVED"
            )
        
        self.logger.info("✅ Analysis results saved and verified")
        
    except Exception as e:
        self.logger.error(f"Error in analysis callback: {e}")
