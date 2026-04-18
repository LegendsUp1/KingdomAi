"""
Wallet Tab Event Handlers
Additional handlers for wallet events
"""

def add_wallet_handlers(wallet_tab):
    """Add missing event handlers to wallet tab"""
    
    def _handle_balance_update(data):
        """Handle wallet balance update"""
        try:
            coin = data.get('coin')
            address = data.get('address')
            balance = data.get('balance', 0)
            wallet_tab.logger.info(f"Balance update: {coin} {address} = {balance}")
        except Exception as e:
            wallet_tab.logger.error(f"Balance update error: {e}")
    
    def _handle_wallet_list(data):
        """Handle wallet list response"""
        try:
            wallets = data.get('wallets', [])
            wallet_tab.logger.info(f"Received {len(wallets)} wallets")
        except Exception as e:
            wallet_tab.logger.error(f"Wallet list error: {e}")
    
    # Attach handlers
    wallet_tab._handle_balance_update = _handle_balance_update
    wallet_tab._handle_wallet_list = _handle_wallet_list
