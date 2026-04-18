"""Adapter module for blockchain management components.

This module serves as a compatibility layer to maintain existing imports
while delegating to the properly structured blockchain module components.
"""

import logging
from typing import Dict, Any

# Setup logger
logger = logging.getLogger("kingdom_ai.blockchain_manager")

# Import blockchain components from the proper module
try:
    from core.blockchain.manager import BlockchainManager
    from core.blockchain.connector import BlockchainConnectorBase, create_blockchain_connector
    from core.blockchain.wallet import WalletManager
    from core.blockchain.mining_dashboard import MiningDashboard
    
    # Flag to indicate successful imports
    _blockchain_components_available = True
    logger.info("Successfully imported blockchain components")
except ImportError as e:
    logger.error(f"Error importing blockchain components: {e}")
    _blockchain_components_available = False

# Export the availability flag as a constant
BLOCKCHAIN_COMPONENTS_AVAILABLE = _blockchain_components_available


def initialize_blockchain_components(event_bus=None, config=None) -> Dict[str, Any]:
    """Initialize all blockchain components.
    
    This function creates and initializes all blockchain-related components
    and returns them as a dictionary for registration with the component manager.
    
    Args:
        event_bus: The event bus for component communication
        config: Optional configuration dictionary
        
    Returns:
        Dictionary of blockchain components
    """
    components = {}
    
    if not BLOCKCHAIN_COMPONENTS_AVAILABLE:
        logger.warning("Blockchain components not available, returning empty components dictionary")
        return components
    
    try:
        # Create blockchain manager
        manager = BlockchainManager(event_bus=event_bus, config=config)
        components["blockchain_manager"] = manager
        
        # Create wallet manager (via the blockchain manager to avoid duplication)
        wallet_manager = WalletManager(event_bus=event_bus, config=config)
        components["wallet_manager"] = wallet_manager
        
        # Create mining dashboard
        mining_dashboard = MiningDashboard(event_bus=event_bus, config=config)
        components["mining_dashboard"] = mining_dashboard
        
        logger.info(f"Successfully initialized {len(components)} blockchain components")
        
    except Exception as e:
        logger.error(f"Error initializing blockchain components: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return components
