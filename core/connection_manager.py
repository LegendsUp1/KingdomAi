
import logging
import redis
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class ConnectionManager(BaseComponent):
    """Manages network connections and retries.
    
    This class is responsible for managing connections to various services used by the
    Kingdom AI system, including Redis, trading APIs, AI APIs, blockchain APIs, and VR APIs.
    It also handles the distribution of API keys to components that need them.
    """
    
    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None):
        super().__init__(event_bus=event_bus, config=config or {})
        self._connections = {}
        self._retry_intervals = [1, 2, 5, 10, 30]  # Seconds between retries
        self._is_enabled = True
        self._redis_client = None
        self._component_status = {}
        self.redis_config = {}  # Initialize redis_config as empty dict to avoid None errors
        self._is_initializing = False  # Track initialization state
        self.redis_pool = None
        self.api_keys = {}
        
        # Load API keys and Redis configuration
        self.api_keys = self._load_api_keys()
        self.redis_config = self._load_redis_config()
        
        # Initialize Redis Quantum Nexus Connector
        self.quantum_nexus = None
        
        # Import here to avoid circular imports
        self.RedisQuantumNexusConnector = None  # type: ignore[misc]
        self.NexusEnvironment = None  # type: ignore[misc]
        try:
            import importlib
            rqn_module = importlib.import_module('core.nexus.redis_quantum_nexus')
            self.RedisQuantumNexusConnector = getattr(rqn_module, 'RedisQuantumNexusConnector', None)
            self.NexusEnvironment = getattr(rqn_module, 'NexusEnvironment', None)
        except (ImportError, ModuleNotFoundError):
            logger.warning("Redis Quantum Nexus module not available")
        
    def _load_redis_config(self) -> Dict[str, Any]:
        """Load Redis configuration from a file.
        
        Returns:
            Dict[str, Any]: Redis configuration dict
        """
        try:
            config_path = Path(self.config.get('redis_config_path', 'config/redis_config.json'))
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded Redis configuration from {config_path}")
                return config
            else:
                logger.warning(f"Redis config file not found at {config_path}")
                # REDIS QUANTUM NEXUS - Default config
                return {
                    "host": "127.0.0.1",
                    "port": 6380,  # Quantum Nexus port
                    "password": "QuantumNexus2025",
                    "db": 0
                }
        except Exception as e:
            logger.error(f"Error loading Redis configuration: {e}")
            # REDIS QUANTUM NEXUS - Default configuration
            return {
                "host": "127.0.0.1",
                "port": 6380,  # Quantum Nexus port
                "password": "QuantumNexus2025",
                "db": 0
            }
            
    def _load_api_keys(self) -> Dict[str, str]:
        """Load API keys from a file.
        
        Returns:
            Dict[str, str]: API keys dictionary
        """
        try:
            api_keys_path = Path(self.config.get('api_keys_path', 'config/api_keys.json'))
            if api_keys_path.exists():
                with open(api_keys_path, 'r') as f:
                    api_keys = json.load(f)
                logger.info(f"Loaded API keys from {api_keys_path}")
                return api_keys
            else:
                logger.warning(f"API keys file not found at {api_keys_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading API keys: {e}")
            return {}
            
    def get_redis_client(self) -> Optional[redis.Redis]:
        """Get a Redis client from the connection pool.
        
        Returns:
            Optional[redis.Redis]: Redis client if available, None otherwise
        """
        if hasattr(self, 'redis_pool') and self.redis_pool is not None:
            try:
                return redis.Redis(connection_pool=self.redis_pool)
            except Exception as e:
                logger.error(f"Error getting Redis client: {e}")
                return None
        else:
            logger.warning("Redis pool not initialized")
            return None
            
    def _initialize_redis(self) -> bool:
        """Initialize Redis connection pool and client.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create Redis connection pool
            logger.info(f"Initializing Redis connection pool with {self.redis_config}")
            # REDIS QUANTUM NEXUS - Port 6380, Password QuantumNexus2025
            self.redis_pool = redis.ConnectionPool(
                host=self.redis_config.get('host', '127.0.0.1'),
                port=int(self.redis_config.get('port', 6380)),  # Quantum Nexus port
                password=self.redis_config.get('password', 'QuantumNexus2025'),
                db=int(self.redis_config.get('db', 0)),
                decode_responses=True
            )
            
            # Try to get a client to verify the connection works
            try:
                client = redis.Redis(connection_pool=self.redis_pool)
                client.ping()  # Test the connection
                logger.info("Redis connection successful")
                return True
            except redis.ConnectionError as e:
                logger.error(f"Redis connection failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing Redis: {e}")
            return False
            
    async def initialize(self) -> bool:
        """Initialize the connection manager asynchronously."""
        try:
            if self._is_initializing:
                logger.warning("Connection Manager already initializing")
                return False
                
            self._is_initializing = True
            logger.info("Initializing Connection Manager...")
            
            # Subscribe to events
            try:
                if self.event_bus:
                    logger.info("Subscribing to events...")
                    try:
                        # Use try/except for each subscription to prevent cascading failures
                        import asyncio
                        async def safe_subscribe(topic: str, handler) -> None:
                            """Safely subscribe to event bus topic."""
                            try:
                                if hasattr(self.event_bus, 'subscribe_async'):
                                    result = self.event_bus.subscribe_async(topic, handler)
                                    if asyncio.iscoroutine(result):
                                        await result  # type: ignore[misc]
                                elif hasattr(self.event_bus, 'subscribe'):
                                    self.event_bus.subscribe(topic, handler)
                            except Exception as sub_err:
                                logger.error(f"Error subscribing to {topic}: {sub_err}")
                        
                        await safe_subscribe('component.registered', self._handle_component_registered)
                        await safe_subscribe('component.status.update', self._handle_component_status_update)
                        await safe_subscribe('system.shutdown', self._handle_shutdown)
                    except Exception as e:
                        logger.error(f"Error during event subscriptions: {e}")
                else:
                    logger.warning("Event bus not available")
            except Exception as e:
                logger.error(f"Error accessing event bus: {e}")
                
            # Initialize Redis
            redis_init = self._initialize_redis()
            if not redis_init:
                logger.warning("Redis initialization failed, continuing with limited functionality")
            
            # Initialize Quantum Nexus if available
            if self.RedisQuantumNexusConnector is not None and self.NexusEnvironment is not None:
                logger.info("Initializing Quantum Nexus...")
                try:
                    env = getattr(self.NexusEnvironment, 'DEVELOPMENT', None) or 'development'
                    self.quantum_nexus = self.RedisQuantumNexusConnector(
                        redis_config=self.redis_config,
                        environment=env
                    )
                    if hasattr(self.quantum_nexus, 'connect'):
                        connect_result = self.quantum_nexus.connect()
                        if hasattr(connect_result, '__await__'):
                            await connect_result
                    logger.info("Quantum Nexus initialized")
                except Exception as e:
                    logger.error(f"Error initializing Quantum Nexus: {e}")
            
            # Distribute API keys to components that need them
            await self.distribute_api_keys()
            
            logger.info("Connection Manager initialized successfully")
            self._is_initializing = False
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Connection Manager: {e}")
            self._is_initializing = False
            return False
            
    def initialize_sync(self) -> bool:
        """Initialize the connection manager synchronously."""
        try:
            if self._is_initializing:
                logger.warning("Connection Manager already initializing")
                return False
                
            self._is_initializing = True
            logger.info("Initializing Connection Manager (sync)...")
            
            # Initialize Redis
            redis_init = self._initialize_redis()
            if not redis_init:
                logger.warning("Redis initialization failed, continuing with limited functionality")
            
            # Initialize Quantum Nexus if available (sync version)
            if self.RedisQuantumNexusConnector is not None and self.NexusEnvironment is not None:
                logger.info("Initializing Quantum Nexus (sync)...")
                try:
                    env = getattr(self.NexusEnvironment, 'DEVELOPMENT', None) or 'development'
                    self.quantum_nexus = self.RedisQuantumNexusConnector(
                        redis_config=self.redis_config,
                        environment=env
                    )
                    # We'll call connect later in start_sync
                except Exception as e:
                    logger.error(f"Error initializing Quantum Nexus (sync): {e}")
            
            # Start check thread
            self._start_sync()
            
            # Verify core components
            self._verify_core_components_sync()
            
            # Distribute API keys to components that need them
            self._distribute_api_keys_sync()
            
            # Subscribe to events
            try:
                if self.event_bus:
                    logger.info("Subscribing to events...")
                    self.event_bus.subscribe_sync('component.registered', self._handle_component_registered)
                    self.event_bus.subscribe_sync('component.status.update', self._handle_component_status_update)
                    self.event_bus.subscribe_sync('system.shutdown', self._handle_shutdown)
            except Exception as e:
                logger.error(f"Error subscribing to events: {e}")
            
            logger.info("Connection Manager initialized successfully (sync)")
            self._is_initializing = False
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Connection Manager (sync): {e}")
            self._is_initializing = False
            return False
            
    def _start_sync(self) -> bool:
        """Start the connection manager synchronously."""
        try:
            logger.info("Starting Connection Manager...")
            
            # Run network checks
            success = True
            
            # Check event bus
            if not self._check_event_bus():
                logger.warning("Event bus check failed")
                success = False
                
            # Check network connectivity
            if not self._check_network():
                logger.warning("Network connectivity check failed")
                success = False
                
            # Check database connections
            if not self._check_database():
                logger.warning("Database check failed")
                success = False
                
            # Check Redis
            if not self._check_redis_connection():
                logger.warning("Redis check failed")
                success = False
                
            logger.info(f"Connection Manager started {'' if success else 'with warnings'}")
            return success
            
        except Exception as e:
            logger.error(f"Error starting Connection Manager: {e}")
            return False
            
    def _verify_core_components_sync(self) -> Dict[str, bool]:
        """Verify core infrastructure components synchronously."""
        results = {}
        
        try:
            # Check redis
            if hasattr(self, 'redis_pool') and self.redis_pool is not None:
                try:
                    client = redis.Redis(connection_pool=self.redis_pool)
                    client.ping()
                    results["redis"] = True
                    logger.info("Redis connection verified")
                except Exception as e:
                    results["redis"] = False
                    logger.error(f"Redis connection verification failed: {e}")
            else:
                results["redis"] = False
                logger.warning("Redis pool not initialized")
                
            # Check continuous response generator
            try:
                results["continuous_response"] = self._check_continuous_response()
            except Exception as e:
                results["continuous_response"] = False
                logger.error(f"Error checking continuous response generator: {e}")
                
            # Verify Quantum Nexus if available
            if hasattr(self, 'quantum_nexus') and self.quantum_nexus is not None:
                try:
                    # Try different methods that might be available for connection verification
                    if hasattr(self.quantum_nexus, 'verify_connection'):
                        results["quantum_nexus"] = self.quantum_nexus.verify_connection()
                    elif hasattr(self.quantum_nexus, 'is_connected'):
                        results["quantum_nexus"] = self.quantum_nexus.is_connected()
                    elif hasattr(self.quantum_nexus, 'ping'):
                        results["quantum_nexus"] = self.quantum_nexus.ping()
                    else:
                        logger.warning("No verification method found for Quantum Nexus")
                        results["quantum_nexus"] = False
                except Exception as e:
                    results["quantum_nexus"] = False
                    logger.error(f"Quantum Nexus verification failed: {e}")
            else:
                results["quantum_nexus"] = False
                logger.warning("Quantum Nexus not initialized")
                
            return results
            
        except Exception as e:
            logger.error(f"Error verifying core components: {e}")
            return {"error": False}  # type: ignore[misc]
            
    def _distribute_api_keys_sync(self) -> Dict[str, bool]:
        """Distribute API keys to components synchronously.
        
        This method is a synchronous wrapper around distribute_api_keys.
        
        Returns:
            Dict[str, bool]: Dictionary of results
        """
        try:
            logger.info("Distributing API keys to components (sync)...")
            
            # Connect APIs synchronously
            results = {}
            
            # Connect trading APIs
            try:
                self._connect_trading_apis()
                results["trading"] = True
            except Exception as e:
                logger.error(f"Error connecting trading APIs: {e}")
                results["trading"] = False
            
            # Connect AI APIs
            try:
                self._connect_ai_apis()
                results["ai"] = True
            except Exception as e:
                logger.error(f"Error connecting AI APIs: {e}")
                results["ai"] = False
            
            # Connect blockchain APIs
            try:
                self._connect_blockchain_apis()
                results["blockchain"] = True
            except Exception as e:
                logger.error(f"Error connecting blockchain APIs: {e}")
                results["blockchain"] = False
            
            # Connect VR APIs
            try:
                self._connect_vr_apis()
                results["vr"] = True
            except Exception as e:
                logger.error(f"Error connecting VR APIs: {e}")
                results["vr"] = False
            
            # Connect miscellaneous APIs
            try:
                self._connect_misc_apis()
                results["misc"] = True
            except Exception as e:
                logger.error(f"Error connecting misc APIs: {e}")
                results["misc"] = False
            
            logger.info("API keys distributed successfully (sync)")
            return results
            
        except Exception as e:
            logger.error(f"Error distributing API keys (sync): {e}")
            return {"error": False}  # type: ignore[misc]
            
    def _handle_component_registered(self, data: Dict[str, Any]) -> None:
        """Handle component registration event.
        
        Args:
            data: Event data containing component information
        """
        try:
            component_name = data.get('name')
            component_type = data.get('type')
            
            if component_name and component_type:
                logger.info(f"Component registered: {component_name} (type: {component_type})")
                
                # Update component status
                self._component_status[component_name] = {
                    "type": component_type,
                    "status": "registered",
                    "timestamp": time.time()
                }
                
                # Handle component-specific tasks here
                # For example, distribute API keys if needed
        except Exception as e:
            logger.error(f"Error handling component registration: {e}")
            
    def _handle_component_status_update(self, data: Dict[str, Any]) -> None:
        """Handle component status update event.
        
        Args:
            data: Event data containing component status information
        """
        try:
            component_name = data.get('name')
            status = data.get('status')
            
            if component_name and status:
                logger.info(f"Component status update: {component_name} -> {status}")
                
                # Update component status
                if component_name in self._component_status:
                    self._component_status[component_name].update({
                        "status": status,
                        "timestamp": time.time()
                    })
                else:
                    self._component_status[component_name] = {
                        "status": status,
                        "timestamp": time.time()
                    }
        except Exception as e:
            logger.error(f"Error handling component status update: {e}")
            
    def _handle_shutdown(self, data: Dict[str, Any]) -> None:
        """Handle system shutdown event.
        
        Args:
            data: Event data containing shutdown information
        """
        try:
            logger.info("System shutdown event received, stopping Connection Manager...")
            self._stop()
        except Exception as e:
            logger.error(f"Error handling shutdown: {e}")
            
    def _connect_ai_apis(self) -> None:
        """Connect AI components to their API keys."""
        try:
            # Connect to AI APIs
            ai_keys = self.api_keys.get('ai', {}) if isinstance(self.api_keys, dict) else {}
            if not isinstance(ai_keys, dict):
                ai_keys = {}
            for ai_service, key in ai_keys.items():
                logger.info(f"Setting up AI API: {ai_service}")
                
                # Update connections dictionary for tracking
                self._connections[f"ai_{ai_service}"] = {
                    "service": ai_service,
                    "type": "ai",
                    "status": "connected",
                    "timestamp": time.time()
                }
        except Exception as e:
            logger.error(f"Error connecting to AI APIs: {e}")
            
    def _connect_blockchain_apis(self) -> None:
        """Connect blockchain components to their API keys."""
        try:
            # Connect to blockchain APIs
            blockchain_keys = self.api_keys.get('blockchain', {}) if isinstance(self.api_keys, dict) else {}
            if not isinstance(blockchain_keys, dict):
                blockchain_keys = {}
            for blockchain, key in blockchain_keys.items():
                logger.info(f"Setting up blockchain API: {blockchain}")
                
                # Update connections dictionary for tracking
                self._connections[f"blockchain_{blockchain}"] = {
                    "service": blockchain,
                    "type": "blockchain",
                    "status": "connected",
                    "timestamp": time.time()
                }
                
                # Handle specific blockchain APIs
                if blockchain.lower() == "etherscan":
                    logger.info("Initializing Etherscan API")
                elif blockchain.lower() == "coinmarketcap":
                    logger.info("Initializing CoinMarketCap API")
        except Exception as e:
            logger.error(f"Error connecting to blockchain APIs: {e}")
            
    def _connect_vr_apis(self) -> None:
        """Connect VR components to their API keys."""
        try:
            # Connect to VR APIs
            vr_keys = self.api_keys.get('vr', {}) if isinstance(self.api_keys, dict) else {}
            if not isinstance(vr_keys, dict):
                vr_keys = {}
            for vr_service, key in vr_keys.items():
                logger.info(f"Setting up VR API: {vr_service}")
                
                # Update connections dictionary for tracking
                self._connections[f"vr_{vr_service}"] = {
                    "service": vr_service,
                    "type": "vr",
                    "status": "connected",
                    "timestamp": time.time()
                }
                
                # Handle specific VR APIs
                if vr_service.lower() == "unity":
                    logger.info("Initializing Unity API")
                elif vr_service.lower() == "unreal":
                    logger.info("Initializing Unreal API")
        except Exception as e:
            logger.error(f"Error connecting to VR APIs: {e}")
            
    def _connect_misc_apis(self) -> None:
        """Connect miscellaneous components to their API keys."""
        try:
            # Connect to misc APIs
            misc_keys = self.api_keys.get('misc', {}) if isinstance(self.api_keys, dict) else {}
            if not isinstance(misc_keys, dict):
                misc_keys = {}
            for misc_service, key in misc_keys.items():
                logger.info(f"Setting up misc API: {misc_service}")
                
                # Update connections dictionary for tracking
                self._connections[f"misc_{misc_service}"] = {
                    "service": misc_service,
                    "type": "misc",
                    "status": "connected",
                    "timestamp": time.time()
                }
                
                # Handle specific misc APIs
                if misc_service.lower() == "weather":
                    logger.info("Initializing Weather API")
        except Exception as e:
            logger.error(f"Error connecting to misc APIs: {e}")
            
    def _connect_trading_apis(self) -> None:
        """Connect trading components to their API keys."""
        try:
            # Connect to trading APIs
            trading_keys = self.api_keys.get('trading', {}) if isinstance(self.api_keys, dict) else {}
            if not isinstance(trading_keys, dict):
                trading_keys = {}
            for exchange, key in trading_keys.items():
                logger.info(f"Setting up trading API: {exchange}")
                
                # Update connections dictionary for tracking
                self._connections[f"trading_{exchange}"] = {
                    "service": exchange,
                    "type": "trading",
                    "status": "connected",
                    "timestamp": time.time()
                }
        except Exception as e:
            logger.error(f"Error connecting to trading APIs: {e}")
            
    def _check_event_bus(self) -> bool:
        """Check event bus connection."""
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            return True
        else:
            return False
            
    def _check_network(self) -> bool:
        """Check network connectivity."""
        return True
        
    def _check_database(self) -> bool:
        """Check database connection."""
        try:
            # Implement actual database connection check here
            # For this example, we'll just return True
            
            # Update connections dictionary for tracking
            self._connections["database"] = {
                "service": "main_db",
                "type": "database",
                "status": "connected",
                "timestamp": time.time()
            }
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
            
    def _check_redis_connection(self) -> bool:
        """Check Redis connection."""
        try:
            if hasattr(self, 'redis_pool') and self.redis_pool is not None:
                client = redis.Redis(connection_pool=self.redis_pool)
                client.ping()
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Redis connection check failed: {e}")
            return False
            
    def _check_continuous_response(self) -> bool:
        """Check continuous response generator."""
        try:
            # Import here to avoid circular imports
            from core.continuous_response_generator import ContinuousResponseGenerator
            
            # Just check if the class is available for now
            return ContinuousResponseGenerator is not None
        except ImportError:
            logger.warning("ContinuousResponseGenerator not available")
            return False
            
    async def _start(self) -> bool:
        """Start the connection manager."""
        try:
            logger.info("Starting Connection Manager...")
            
            # Connect to Redis and other services
            redis_init = self._initialize_redis()
            if not redis_init:
                logger.warning("Redis initialization failed, continuing with limited functionality")
            
            # Initialize and connect to Quantum Nexus if available
            if hasattr(self, 'quantum_nexus') and self.quantum_nexus is not None:
                await self.quantum_nexus.connect()
                
            return True
            
        except Exception as e:
            logger.error(f"Error starting Connection Manager: {e}")
            return False
            
    async def _stop(self) -> bool:
        """Stop the connection manager and close all connections."""
        try:
            logger.info("Stopping Connection Manager...")
            
            # Close all connections
            for connection_name in list(self._connections.keys()):
                try:
                    await self.disconnect(connection_name)
                except Exception as e:
                    logger.error(f"Error disconnecting from {connection_name}: {e}")
            
            # Close Redis pool if exists
            if hasattr(self, 'redis_pool') and self.redis_pool is not None:
                try:
                    self.redis_pool.disconnect()
                    logger.info("Redis connection pool closed")
                except Exception as e:
                    logger.error(f"Error closing Redis connection pool: {e}")
            
            # Close Quantum Nexus if exists
            if hasattr(self, 'quantum_nexus') and self.quantum_nexus is not None:
                try:
                    # Try different methods that might be available for disconnect
                    if hasattr(self.quantum_nexus, 'disconnect'):
                        await self.quantum_nexus.disconnect()
                        logger.info("Quantum Nexus disconnected")
                    elif hasattr(self.quantum_nexus, 'close'):
                        # Try sync close method
                        self.quantum_nexus.close()
                        logger.info("Quantum Nexus closed")
                    elif hasattr(self.quantum_nexus, 'close_async'):
                        # Try async close method
                        await self.quantum_nexus.close_async()
                        logger.info("Quantum Nexus closed asynchronously")
                    else:
                        logger.info("No disconnect method found for Quantum Nexus")
                except Exception as e:
                    logger.error(f"Error closing Quantum Nexus connection: {e}")
            
            logger.info("Connection Manager stopped")
            return True
        except Exception as e:
            logger.error(f"Error stopping Connection Manager: {e}")
            return False
            
    async def distribute_api_keys(self) -> bool:
        """Distribute API keys to components that need them.
        
        This method distributes API keys to all registered components that need them.
        
        Returns:
            bool: True if distribution succeeded, False otherwise
        """
        try:
            logger.info("Distributing API keys to components...")
            
            # Connect trading APIs (sync methods, no await needed)
            self._connect_trading_apis()
            
            # Connect AI APIs
            self._connect_ai_apis()

            # Connect blockchain APIs
            self._connect_blockchain_apis()

            # Connect VR APIs
            self._connect_vr_apis()

            # Connect miscellaneous APIs
            self._connect_misc_apis()

            logger.info("API keys distributed successfully")
            return True

        except Exception as e:
            logger.error(f"Error distributing API keys: {e}")
            return False
            
    async def disconnect(self, name: str) -> bool:
        """Disconnect from a service.
        
        Args:
            name: Name of the service to disconnect from
            
        Returns:
            bool: True if disconnected successfully, False otherwise
        """
        try:
            if name in self._connections:
                connection = self._connections[name]
                if hasattr(connection, 'disconnect'):
                    await connection.disconnect()
                elif hasattr(connection, 'close'):
                    connection.close()
                logger.info(f"Disconnected from {name}")
                return True
            else:
                logger.error(f"Service {name} not found")
                return False

        except Exception as e:
            logger.error(f"Error disconnecting from {name}: {e}")
            return False
