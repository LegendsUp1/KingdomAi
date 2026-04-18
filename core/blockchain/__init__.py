"""Blockchain integration initialization for Kingdom AI."""

import logging
import asyncio
import json
import os
import traceback
from typing import Dict, Any, Optional, List, Callable

# Setup logger
logger = logging.getLogger("kingdom_ai.blockchain")

# Import base component and event bus related modules
from core.base_component import BaseComponent

# Initialize all flags to False by default
has_wallet_manager = False
has_mining_dashboard = False
has_blockchain_explorer = False
has_transaction_monitor = False
has_network_stats = False

# Import local blockchain module components directly
try:
    # Import connector classes
    from .connector import (
        BlockchainConnectorBase, EthereumConnector, BitcoinConnector,
        create_blockchain_connector
    )
    logger.info("Successfully imported blockchain connector classes")
    
    # Import manager classes
    from .manager import BlockchainManager, BlockchainError
    logger.info("Successfully imported blockchain manager classes")
    
    # Import wallet manager if available
    try:
        from .wallet import WalletManager
        logger.info("Successfully imported wallet manager")
        has_wallet_manager = True
    except ImportError as e:
        logger.warning(f"Wallet manager not available: {e}")
        has_wallet_manager = False
    
    # Import mining dashboard if available
    try:
        from .mining_dashboard import MiningDashboard
        logger.info("Successfully imported mining dashboard")
        has_mining_dashboard = True
    except ImportError as e:
        logger.warning(f"Mining dashboard not available: {e}")
        has_mining_dashboard = False
        
    # Import blockchain explorer if available
    try:
        from .explorer_browser import BlockchainExplorer
        logger.info("Successfully imported blockchain explorer")
        has_blockchain_explorer = True
    except ImportError as e:
        logger.warning(f"Blockchain explorer not available: {e}")
        has_blockchain_explorer = False
    
    # Import transaction monitor if available
    try:
        from .transaction_monitor import TransactionMonitor
        logger.info("Successfully imported transaction monitor")
        has_transaction_monitor = True
    except ImportError as e:
        logger.warning(f"Transaction monitor not available: {e}")
        has_transaction_monitor = False
    
    # Import network stats if available
    try:
        from .network_stats import NetworkStats
        logger.info("Successfully imported network stats")
        has_network_stats = True
    except ImportError as e:
        logger.warning(f"Network stats not available: {e}")
        has_network_stats = False
    
    # Set flag to indicate successful imports
    blockchain_components_available = True

except ImportError as e:
    logger.error(f"Failed to import blockchain components: {e}")
    blockchain_components_available = False

# Create uppercase exports for backward compatibility
HAS_WALLET_MANAGER = has_wallet_manager
HAS_MINING_DASHBOARD = has_mining_dashboard
HAS_BLOCKCHAIN_EXPLORER = has_blockchain_explorer
HAS_TRANSACTION_MONITOR = has_transaction_monitor
HAS_NETWORK_STATS = has_network_stats
BLOCKCHAIN_COMPONENTS_AVAILABLE = blockchain_components_available

# Initialize class import tracking dictionary
class_imports = {
    'BlockchainConnectorBase': True,
    'EthereumConnector': True,
    'BitcoinConnector': True,
    'BlockchainManager': True,
    'WalletManager': HAS_WALLET_MANAGER,
    'MiningDashboard': HAS_MINING_DASHBOARD,
    'BlockchainExplorer': HAS_BLOCKCHAIN_EXPLORER,
    'TransactionMonitor': HAS_TRANSACTION_MONITOR,
    'NetworkStats': HAS_NETWORK_STATS
}

# Set flag for whether fix modules are available
HAS_FIX_MODULES = any(class_imports.values())

# No fallback handlers allowed - system must halt on critical failures


async def initialize_blockchain_components(event_bus):
    """Initialize blockchain components and connect to event bus.
    
    Args:
        event_bus: Event bus to connect components to
        
    Returns:
        Dictionary of initialized components
    """
    components = {}
    
    try:
        logger.info("Initializing blockchain components")
        
        # Create directory for blockchain data if it doesn't exist
        os.makedirs(os.path.join("data", "blockchain"), exist_ok=True)
        
        # Initialize blockchain components
        if HAS_FIX_MODULES:
            # Try to use fix implementation
            logger.info("Using fix modules for blockchain integration")
            
            try:
                # Load blockchain configuration
                blockchain_config = BlockchainConfig()
                components["blockchain_config"] = blockchain_config
                
                # Import BlockchainManager from fix module
                from fix_blockchain_integration_part2 import BlockchainManager
                
                # Create blockchain manager using the factory method
                blockchain_manager = await BlockchainManager.create(config=blockchain_config, event_bus=event_bus)
                components["blockchain_manager"] = blockchain_manager
                logger.info("BlockchainManager initialized")
            except Exception as e:
                logger.error(f"BlockchainManager initialization failed: {e}")
                logger.warning("⚠️ Blockchain functionality will be limited")
            
            # Create Bitcoin connection
            try:
                if 'BitcoinConnection' in globals():
                    bitcoin_connection = globals()['BitcoinConnection'](config=blockchain_config, event_bus=event_bus)
                else:
                    # Try to import dynamically
                    from fix_blockchain_integration_part1b import BitcoinConnection
                    bitcoin_connection = BitcoinConnection(config=blockchain_config, event_bus=event_bus)
                
                components["bitcoin_connection"] = bitcoin_connection
                logger.info("BitcoinConnection initialized")
            except Exception as e:
                logger.error(f"Error initializing BitcoinConnection: {e}")
            
            # Create Ethereum connection
            try:
                if 'EthereumConnection' in globals():
                    ethereum_connection = globals()['EthereumConnection'](config=blockchain_config, event_bus=event_bus)
                else:
                    # Try to import dynamically
                    from fix_blockchain_integration_part1b import EthereumConnection
                    ethereum_connection = EthereumConnection(config=blockchain_config, event_bus=event_bus)
                
                components["ethereum_connection"] = ethereum_connection
                logger.info("EthereumConnection initialized")
            except Exception as e:
                logger.error(f"Error initializing EthereumConnection: {e}")
            
            # Initialize Transaction Verifier
            try:
                if 'TransactionVerifier' in globals():
                    transaction_verifier = globals()['TransactionVerifier'](config=blockchain_config, event_bus=event_bus)
                else:
                    # Try to import dynamically
                    from fix_blockchain_integration_part2 import TransactionVerifier
                    transaction_verifier = TransactionVerifier(config=blockchain_config, event_bus=event_bus)
                
                components["transaction_verifier"] = transaction_verifier
                logger.info("TransactionVerifier initialized")
            except Exception as e:
                logger.error(f"Error initializing TransactionVerifier: {e}")
            
            # Initialize Wallets
            try:
                if 'WalletConfig' in globals() and 'BitcoinWallet' in globals():
                    wallet_config = globals()['WalletConfig']()
                    bitcoin_wallet = globals()['BitcoinWallet']("kingdom_bitcoin_wallet", config=wallet_config)
                    components["bitcoin_wallet"] = bitcoin_wallet
                    logger.info("BitcoinWallet initialized")
                else:
                    # Try to import dynamically
                    from fix_blockchain_integration_part3a import WalletConfig
                    from fix_blockchain_integration_part3b_bitcoin import BitcoinWallet
                    wallet_config = WalletConfig()
                    bitcoin_wallet = BitcoinWallet("kingdom_bitcoin_wallet", config=wallet_config)
                    components["bitcoin_wallet"] = bitcoin_wallet
                    logger.info("BitcoinWallet initialized")
            except Exception as e:
                logger.error(f"Error initializing BitcoinWallet: {e}")
        else:
            # 2026 FIX: Allow degraded mode instead of crash
            logger.warning("⚠️ Blockchain modules not fully available - running in degraded mode")
        
        # Apply bitcoin connection wrapper fix if available
        try:
            from core.bitcoin_fix import fix_bitcoin_components
            fix_bitcoin_components(components)
        except Exception as e:
            logger.debug("bitcoin_fix not applied: %s", e)
        
        # Register event handlers with event bus
        if event_bus and hasattr(event_bus, 'register_handler'):
            if "blockchain_manager" in components:
                event_bus.register_handler("blockchain.connect", components["blockchain_manager"].handle_connect_request)
                event_bus.register_handler("blockchain.disconnect", components["blockchain_manager"].handle_disconnect_request)
                event_bus.register_handler("blockchain.status", components["blockchain_manager"].handle_status_request)
                event_bus.register_handler("blockchain.transaction", components["blockchain_manager"].handle_transaction_request)
                logger.info("Registered blockchain event handlers")

        # KAIG rebrand resilience — blockchain subsystem is identity-aware
        if event_bus and hasattr(event_bus, 'subscribe'):
            def _on_blockchain_identity_changed(payload):
                if isinstance(payload, dict):
                    logger.warning(
                        "Blockchain: TOKEN REBRANDED %s → %s. "
                        "All on-chain balances preserved — tracked by address, not name. "
                        "Smart contract uses UUPS proxy — name/symbol updated without redeployment.",
                        payload.get("old_ticker", "?"),
                        payload.get("new_ticker", "?"))
            event_bus.subscribe("kaig.identity.changed", _on_blockchain_identity_changed)
            logger.info("Blockchain subscribed to kaig.identity.changed (rebrand resilience)")
        
        logger.info(f"Blockchain initialization completed with {len(components)} components")
        return components
    
    except Exception as e:
        logger.error(f"Error during blockchain components initialization: {e}")
        logger.error(traceback.format_exc())
        return components
