"""
MASTER SYSTEM INTEGRATOR
Connects ALL blockchain, trading, mining, and WebSocket systems across the codebase
Ensures everything works together seamlessly
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List

logger = logging.getLogger("KingdomAI.MasterIntegrator")


class MasterSystemIntegrator:
    """
    Master integrator that connects ALL systems:
    - Blockchain (Bitcoin, Ethereum, Polygon, BSC, Arbitrum, Optimism, Base, Avalanche)
    - Trading (Coinbase, Kraken, Bitstamp, Gemini WebSockets + Trading System)
    - Mining (80+ PoW cryptocurrencies)
    - WebSockets (Trading + Blockchain event listeners)
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.systems = {}
        self.initialized = False
        logger.info("🎯 Master System Integrator created")
    
    async def initialize_all_systems(self) -> Dict[str, Any]:
        """Initialize ALL systems in the correct order"""
        results = {
            'blockchain': None,
            'trading': None,
            'mining': None,
            'websockets': None,
            'success': False,
            'errors': []
        }
        
        try:
            logger.info("="*80)
            logger.info("🚀 INITIALIZING ALL KINGDOM AI SYSTEMS")
            logger.info("="*80)
            
            # 1. Initialize Blockchain Manager (connects to all chains)
            logger.info("\n🔗 [1/4] Initializing Blockchain Manager...")
            blockchain_result = await self._initialize_blockchain()
            results['blockchain'] = blockchain_result
            
            # 2. Initialize Trading System (with WebSocket feeds)
            logger.info("\n💹 [2/4] Initializing Trading System...")
            trading_result = await self._initialize_trading()
            results['trading'] = trading_result
            
            # 3. Initialize Mining System (80+ cryptocurrencies)
            logger.info("\n⛏️  [3/4] Initializing Mining System...")
            mining_result = await self._initialize_mining()
            results['mining'] = mining_result
            
            # 4. Initialize WebSocket Systems (Trading + Blockchain)
            logger.info("\n📡 [4/4] Initializing WebSocket Systems...")
            websocket_result = await self._initialize_websockets()
            results['websockets'] = websocket_result
            
            # Check overall success
            all_success = all([
                blockchain_result.get('success', False),
                trading_result.get('success', False),
                mining_result.get('success', False),
                websocket_result.get('success', False)
            ])
            
            results['success'] = all_success
            self.initialized = all_success
            
            logger.info("\n" + "="*80)
            if all_success:
                logger.info("✅ ALL SYSTEMS INITIALIZED SUCCESSFULLY")
            else:
                logger.warning("⚠️  SOME SYSTEMS FAILED TO INITIALIZE")
            logger.info("="*80)
            
            self._print_summary(results)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Master initialization failed: {e}")
            results['errors'].append(str(e))
            return results
    
    async def _initialize_blockchain(self) -> Dict[str, Any]:
        """Initialize blockchain manager with all supported chains"""
        result = {
            'success': False,
            'manager': None,
            'connectors': {},
            'wallet_manager': None,
            'mining_dashboard': None,
            'errors': []
        }
        
        try:
            from core.blockchain.manager import BlockchainManager
            
            # Create blockchain manager
            blockchain_manager = BlockchainManager(event_bus=self.event_bus)
            
            # Initialize it
            success = await blockchain_manager.initialize()
            
            if success:
                result['success'] = True
                result['manager'] = blockchain_manager
                result['connectors'] = blockchain_manager.connectors
                result['wallet_manager'] = blockchain_manager.wallet_manager
                result['mining_dashboard'] = blockchain_manager.mining_dashboard
                
                self.systems['blockchain_manager'] = blockchain_manager
                
                logger.info(f"✅ Blockchain Manager initialized")
                logger.info(f"   - Connectors: {len(blockchain_manager.connectors)}")
                logger.info(f"   - Chains: {list(blockchain_manager.connectors.keys())}")
            else:
                result['errors'].append("Blockchain manager initialization returned False")
                logger.error("❌ Blockchain Manager failed to initialize")
                
        except Exception as e:
            result['errors'].append(str(e))
            logger.error(f"❌ Blockchain initialization error: {e}")
        
        return result
    
    async def _initialize_trading(self) -> Dict[str, Any]:
        """Initialize trading system with all components"""
        result = {
            'success': False,
            'trading_system': None,
            'market_data': None,
            'order_executor': None,
            'strategy_manager': None,
            'errors': []
        }
        
        try:
            from core.trading_system import TradingSystem
            
            # Create trading system
            trading_system = TradingSystem(event_bus=self.event_bus)
            
            # Initialize it
            if hasattr(trading_system, 'initialize'):
                success = await trading_system.initialize()
            else:
                # Some trading systems don't have async initialize
                success = True
            
            if success:
                result['success'] = True
                result['trading_system'] = trading_system
                
                # Get components
                if hasattr(trading_system, 'market_data'):
                    result['market_data'] = trading_system.market_data
                if hasattr(trading_system, 'order_executor'):
                    result['order_executor'] = trading_system.order_executor
                if hasattr(trading_system, 'strategy_manager'):
                    result['strategy_manager'] = trading_system.strategy_manager
                
                self.systems['trading_system'] = trading_system
                
                logger.info(f"✅ Trading System initialized")
                logger.info(f"   - Aggressive Mode: {getattr(trading_system, 'aggressive_mode', True)}")
                logger.info(f"   - Strategies: {getattr(trading_system, 'strategy_count', 'N/A')}")
            else:
                result['errors'].append("Trading system initialization returned False")
                logger.error("❌ Trading System failed to initialize")
                
        except Exception as e:
            result['errors'].append(str(e))
            logger.error(f"❌ Trading initialization error: {e}")
        
        return result
    
    async def _initialize_mining(self) -> Dict[str, Any]:
        """Initialize mining system with all algorithms"""
        result = {
            'success': False,
            'mining_system': None,
            'supported_coins': [],
            'dashboard': None,
            'errors': []
        }
        
        try:
            from core.mining_system import MiningSystem
            
            # Create mining system
            mining_system = MiningSystem(event_bus=self.event_bus)
            
            # Initialize it
            if hasattr(mining_system, 'initialize'):
                success = await mining_system.initialize()
            else:
                success = True
            
            if success:
                result['success'] = True
                result['mining_system'] = mining_system
                
                # Get supported coins
                if hasattr(mining_system, 'supported_coins'):
                    result['supported_coins'] = mining_system.supported_coins
                elif hasattr(mining_system, 'config') and 'currencies' in mining_system.config:
                    result['supported_coins'] = mining_system.config['currencies']
                
                # Get dashboard
                if hasattr(mining_system, 'dashboard'):
                    result['dashboard'] = mining_system.dashboard
                
                self.systems['mining_system'] = mining_system
                
                logger.info(f"✅ Mining System initialized")
                logger.info(f"   - Supported Coins: {len(result['supported_coins'])}")
            else:
                result['errors'].append("Mining system initialization returned False")
                logger.error("❌ Mining System failed to initialize")
                
        except Exception as e:
            result['errors'].append(str(e))
            logger.error(f"❌ Mining initialization error: {e}")
        
        return result
    
    async def _initialize_websockets(self) -> Dict[str, Any]:
        """Initialize all WebSocket connections"""
        result = {
            'success': False,
            'trading_feeds': {},
            'blockchain_listeners': {},
            'errors': []
        }
        
        try:
            # Initialize Trading WebSocket Feeds
            logger.info("   📊 Initializing Trading WebSocket Feeds...")
            try:
                from gui.qt_frames.trading.trading_websocket_price_feed import WebSocketPriceFeed
                
                # Create WebSocket feed
                ws_feed = WebSocketPriceFeed(event_bus=self.event_bus)
                
                # Start all exchanges (Coinbase, Kraken, Bitstamp, Gemini)
                ws_feed.start()
                
                result['trading_feeds']['multi_exchange'] = ws_feed
                logger.info("   ✅ Trading WebSocket Feeds started (Coinbase, Kraken, Bitstamp, Gemini)")
                
            except Exception as e:
                result['errors'].append(f"Trading WebSocket error: {e}")
                logger.warning(f"   ⚠️  Trading WebSocket initialization failed: {e}")
            
            # Initialize Blockchain Event Listeners
            logger.info("   ⛓️  Initializing Blockchain Event Listeners...")
            try:
                from kingdom_ai.blockchain.event_listener import EventListener
                
                # Create event listener
                event_listener = EventListener(event_bus=self.event_bus)
                
                # Initialize it
                await event_listener.initialize()
                
                result['blockchain_listeners']['event_listener'] = event_listener
                logger.info("   ✅ Blockchain Event Listeners initialized")
                
            except Exception as e:
                result['errors'].append(f"Blockchain listener error: {e}")
                logger.warning(f"   ⚠️  Blockchain listener initialization failed: {e}")
            
            # Consider success if at least one WebSocket system works
            result['success'] = len(result['trading_feeds']) > 0 or len(result['blockchain_listeners']) > 0
            
            if result['success']:
                self.systems['websockets'] = result
                logger.info("✅ WebSocket Systems initialized")
            else:
                logger.error("❌ All WebSocket Systems failed")
                
        except Exception as e:
            result['errors'].append(str(e))
            logger.error(f"❌ WebSocket initialization error: {e}")
        
        return result
    
    def _print_summary(self, results: Dict[str, Any]):
        """Print initialization summary"""
        logger.info("\n" + "="*80)
        logger.info("📋 INITIALIZATION SUMMARY")
        logger.info("="*80)
        
        # Blockchain
        blockchain = results.get('blockchain', {})
        if blockchain.get('success'):
            logger.info(f"✅ Blockchain: {len(blockchain.get('connectors', {}))} chains connected")
        else:
            logger.info(f"❌ Blockchain: Failed - {blockchain.get('errors', [])}")
        
        # Trading
        trading = results.get('trading', {})
        if trading.get('success'):
            logger.info(f"✅ Trading: System active")
        else:
            logger.info(f"❌ Trading: Failed - {trading.get('errors', [])}")
        
        # Mining
        mining = results.get('mining', {})
        if mining.get('success'):
            logger.info(f"✅ Mining: {len(mining.get('supported_coins', []))} coins supported")
        else:
            logger.info(f"❌ Mining: Failed - {mining.get('errors', [])}")
        
        # WebSockets
        websockets = results.get('websockets', {})
        if websockets.get('success'):
            trading_count = len(websockets.get('trading_feeds', {}))
            blockchain_count = len(websockets.get('blockchain_listeners', {}))
            logger.info(f"✅ WebSockets: {trading_count} trading feeds, {blockchain_count} blockchain listeners")
        else:
            logger.info(f"❌ WebSockets: Failed - {websockets.get('errors', [])}")
        
        logger.info("="*80)
    
    def get_system(self, system_name: str) -> Optional[Any]:
        """Get a specific system by name"""
        return self.systems.get(system_name)
    
    def get_all_systems(self) -> Dict[str, Any]:
        """Get all initialized systems"""
        return self.systems.copy()
    
    async def shutdown_all_systems(self):
        """Shutdown all systems gracefully"""
        logger.info("🛑 Shutting down all systems...")
        
        for name, system in self.systems.items():
            try:
                if hasattr(system, 'shutdown'):
                    await system.shutdown()
                    logger.info(f"✅ {name} shut down")
            except Exception as e:
                logger.error(f"❌ Error shutting down {name}: {e}")
        
        self.systems.clear()
        self.initialized = False
        logger.info("✅ All systems shut down")


# Convenience function for easy integration
async def initialize_all_kingdom_systems(event_bus=None) -> MasterSystemIntegrator:
    """
    Initialize all Kingdom AI systems in one call
    
    Returns:
        MasterSystemIntegrator instance with all systems initialized
    """
    integrator = MasterSystemIntegrator(event_bus=event_bus)
    await integrator.initialize_all_systems()
    return integrator
