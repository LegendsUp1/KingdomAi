"""
CRITICAL: Add these methods to the END of trading_tab.py (before the final line)
This enables state persistence and data retention for trading analysis
"""

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
        }
        
        # Update tracking lists
        self._markets_analyzed = results.get('markets', [])
        self._exchanges_analyzed = results.get('exchanges', [])
        self._blockchains_analyzed = results.get('blockchains', [])
        
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
            try:
                self._stop_auto_trade()
            except Exception as e:
                self.logger.warning(f"Auto-trade stop failed: {e}")
        
        # 4. Unsubscribe from event bus
        if hasattr(self, 'event_bus') and self.event_bus:
            try:
                if hasattr(self, '_handle_autotrade_plan'):
                    self.event_bus.unsubscribe("ai.autotrade.plan.generated", self._handle_autotrade_plan)
                self.logger.debug("✅ Unsubscribed from trading events")
            except Exception as e:
                self.logger.warning(f"Event bus cleanup warning: {e}")
        
        # 5. Clear data structures
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
