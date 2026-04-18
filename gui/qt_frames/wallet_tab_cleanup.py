"""
CRITICAL FIX: Wallet Tab Cleanup Methods
Add this to wallet_tab.py to prevent memory leaks and protect financial data
"""

def cleanup(self):
    """
    CRITICAL: Clean up all wallet tab resources to prevent memory leaks.
    This protects mining rewards, crypto holdings, and trading operations.
    """
    try:
        logger.info("🧹 Cleaning up Wallet Tab resources...")
        
        # 1. Stop all QTimers
        timers_to_stop = ['update_timer', 'price_timer', '_accum_update_timer']
        for timer_name in timers_to_stop:
            if hasattr(self, timer_name):
                timer = getattr(self, timer_name)
                if timer and hasattr(timer, 'isActive'):
                    if timer.isActive():
                        timer.stop()
                    timer.deleteLater()
                    logger.debug(f"✅ Stopped {timer_name}")
                setattr(self, timer_name, None)
        
        # 2. Unsubscribe from all event bus subscriptions
        if hasattr(self, 'event_bus') and self.event_bus:
            try:
                # Accumulation events
                if hasattr(self, '_on_accumulation_executed'):
                    self.event_bus.unsubscribe('accumulation.executed', self._on_accumulation_executed)
                if hasattr(self, '_on_accumulation_status'):
                    self.event_bus.unsubscribe('accumulation.status', self._on_accumulation_status)
                if hasattr(self, '_on_mining_received'):
                    self.event_bus.unsubscribe('accumulation.mining.received', self._on_mining_received)
                if hasattr(self, '_on_compound_executed'):
                    self.event_bus.unsubscribe('accumulation.compound.executed', self._on_compound_executed)
                
                logger.debug("✅ Unsubscribed from event bus")
            except Exception as e:
                logger.warning(f"Event bus cleanup warning: {e}")
        
        # 3. Stop accumulation intelligence if running
        if hasattr(self, 'accumulation_intelligence') and self.accumulation_intelligence:
            try:
                if hasattr(self.accumulation_intelligence, 'stop'):
                    import asyncio
                    if asyncio.iscoroutinefunction(self.accumulation_intelligence.stop):
                        # Schedule async stop
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.ensure_future(self.accumulation_intelligence.stop())
                        except:
                            pass
                    else:
                        self.accumulation_intelligence.stop()
                logger.debug("✅ Stopped accumulation intelligence")
            except Exception as e:
                logger.warning(f"Accumulation intelligence cleanup warning: {e}")
        
        # 4. Close wallet manager connections
        if hasattr(self, 'wallet_manager') and self.wallet_manager:
            try:
                if hasattr(self.wallet_manager, 'close'):
                    self.wallet_manager.close()
                elif hasattr(self.wallet_manager, 'disconnect'):
                    self.wallet_manager.disconnect()
                logger.debug("✅ Closed wallet manager")
            except Exception as e:
                logger.warning(f"Wallet manager cleanup warning: {e}")
        
        # 5. Close Redis connection
        if hasattr(self, 'redis_client') and self.redis_client:
            try:
                if hasattr(self.redis_client, 'close'):
                    self.redis_client.close()
                logger.debug("✅ Closed Redis connection")
            except Exception as e:
                logger.warning(f"Redis cleanup warning: {e}")
        
        # 6. Clear data structures
        if hasattr(self, 'wallet_balances'):
            self.wallet_balances.clear()
        if hasattr(self, 'transactions'):
            self.transactions.clear()
        if hasattr(self, 'wallet_addresses'):
            self.wallet_addresses.clear()
        
        logger.info("✅ Wallet Tab cleanup complete - financial data protected")
        
    except Exception as e:
        logger.error(f"Error during wallet tab cleanup: {e}")
        import traceback
        logger.error(traceback.format_exc())

def closeEvent(self, event):
    """Handle close event - ensure cleanup is called."""
    try:
        self.cleanup()
    except Exception as e:
        logger.error(f"Error in wallet tab closeEvent: {e}")
    finally:
        event.accept()
