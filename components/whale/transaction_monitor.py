"""
TransactionMonitor - Kingdom AI component

This module provides real-time monitoring of blockchain transactions,
including whale movements, transaction patterns, and gas pricing analytics.
It integrates with the blockchain bridge and blockchain explorer.
"""
import os
import logging
import asyncio
import time
from typing import Any, Dict, List, Optional, Union
import json

# Import blockchain bridge - no fallbacks allowed
try:
    from blockchain.blockchain_bridge import (
        kingdom_web3, Web3, AsyncWeb3,
        get_web3_provider, create_web3_instance,
        is_web3_available
    )
    # System must halt if blockchain bridge is not available
    if not is_web3_available():
        logging.getLogger(__name__).critical("CRITICAL: Web3 functionality is not available.")
        logging.getLogger(__name__).critical("Web3 functionality is MANDATORY with NO FALLBACKS ALLOWED")
        logging.getLogger(__name__).critical("System halting - fix the Web3 issues and restart")
        import sys
        sys.exit(1)
        
    # Verify Redis connection is established and healthy
    if not hasattr(kingdom_web3, 'redis_client') or not kingdom_web3.redis_client:
        logging.getLogger(__name__).critical("CRITICAL: Redis Quantum Nexus connection failed or not established")
        logging.getLogger(__name__).critical("Redis connection is MANDATORY with NO FALLBACKS ALLOWED")
        logging.getLogger(__name__).critical("System halting - fix the Redis connection issues and restart")
        import sys
        sys.exit(1)
        
    # Verify Redis port is exactly 6380 with password 'QuantumNexus2025'
    if not hasattr(kingdom_web3, 'redis_port') or kingdom_web3.redis_port != 6380:
        logging.getLogger(__name__).critical("CRITICAL: Redis Quantum Nexus not configured on mandatory port 6380")
        logging.getLogger(__name__).critical("Redis connection on port 6380 is MANDATORY with NO FALLBACKS ALLOWED")
        logging.getLogger(__name__).critical("System halting - fix the Redis port configuration and restart")
        import sys
        sys.exit(1)
        
    # Verify Redis password
    if not hasattr(kingdom_web3, 'redis_password') or kingdom_web3.redis_password != 'QuantumNexus2025':
        logging.getLogger(__name__).critical("CRITICAL: Redis Quantum Nexus password incorrect or not configured")
        logging.getLogger(__name__).critical("Redis password 'QuantumNexus2025' is MANDATORY with NO FALLBACKS ALLOWED")
        logging.getLogger(__name__).critical("System halting - fix the Redis password configuration and restart")
        import sys
        sys.exit(1)
        
    logging.getLogger(__name__).info("Redis Quantum Nexus connection verified on port 6380")
    
except ImportError as e:
    logging.getLogger(__name__).critical(f"CRITICAL: Failed to import blockchain bridge: {str(e)}")
    logging.getLogger(__name__).critical("Blockchain bridge is MANDATORY with NO FALLBACKS ALLOWED")
    logging.getLogger(__name__).critical("System halting - fix the blockchain bridge module and restart")
    import sys
    sys.exit(1)

# Import blockchain explorer - no fallbacks allowed
try:
    from blockchain.blockchain_explorer import create_blockchain_explorer
except ImportError as e:
    logging.getLogger(__name__).critical(f"CRITICAL: Failed to import blockchain explorer: {str(e)}")
    logging.getLogger(__name__).critical("Blockchain explorer is MANDATORY with NO FALLBACKS ALLOWED")
    logging.getLogger(__name__).critical("System halting - fix the blockchain explorer module and restart")
    import sys
    sys.exit(1)

class TransactionMonitor:
    """
    TransactionMonitor for Kingdom AI system.
    
    Provides real-time monitoring of blockchain transactions, whale movements,
    transaction patterns, and gas price analytics. Integrates with the blockchain 
    bridge and blockchain explorer components.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the TransactionMonitor."""
        self.name = "whale.transactionmonitor"
        self.logger = logging.getLogger(f"KingdomAI.TransactionMonitor")
        self._event_bus = event_bus
        self._config = config or {}
        self.initialized = False
        
        # Blockchain integration components
        self.web3 = None
        self.async_web3 = None
        self.explorer = None
        self.available = False
        self.monitored_addresses = set()
        self.whale_thresholds = {
            "ethereum": 100,  # 100 ETH
            "bitcoin": 10,   # 10 BTC
            "polygon": 50000 # 50,000 MATIC
        }
        self.transaction_history = []
        self.alert_callbacks = []
        
        # Initialize blockchain connections
        self._initialize_blockchain_connection()
        
        # Start monitoring if everything is set up
        if self._event_bus:
            self._register_event_handlers()
            
        self.logger.info(f"TransactionMonitor initialized")
        
    def _initialize_blockchain_connection(self):
        """Initialize connections to blockchain through bridge."""
        try:
            # Verify Redis connection is established and healthy - no fallbacks allowed
            if not hasattr(kingdom_web3, 'redis_client') or not kingdom_web3.redis_client:
                self.logger.critical("CRITICAL: Redis Quantum Nexus connection required for whale transaction monitor")
                self.logger.critical("Redis connection is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the Redis connection issues and restart")
                import sys
                sys.exit(1)
                
            # Verify Redis port is exactly 6380 with password 'QuantumNexus2025'
            if not hasattr(kingdom_web3, 'redis_port') or kingdom_web3.redis_port != 6380:
                self.logger.critical("CRITICAL: Redis Quantum Nexus not configured on mandatory port 6380")
                self.logger.critical("Redis connection on port 6380 is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the Redis port configuration and restart")
                import sys
                sys.exit(1)
                
            # Verify Redis password
            if not hasattr(kingdom_web3, 'redis_password') or kingdom_web3.redis_password != 'QuantumNexus2025':
                self.logger.critical("CRITICAL: Redis Quantum Nexus password incorrect or not configured")
                self.logger.critical("Redis password 'QuantumNexus2025' is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the Redis password configuration and restart")
                import sys
                sys.exit(1)
            
            # Get Web3 instances from the blockchain bridge - no fallbacks allowed
            self.web3 = create_web3_instance()
            if not self.web3:
                self.logger.critical("CRITICAL: Failed to create Web3 instance for whale transaction monitoring")
                self.logger.critical("Web3 instance is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the Web3 connectivity issues and restart")
                import sys
                sys.exit(1)
            
            # Get async web3 - no fallbacks allowed
            provider_url = self._config.get('provider_url')
            if not provider_url:
                self.logger.critical("CRITICAL: No provider URL specified in configuration")
                self.logger.critical("Provider URL is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the provider URL configuration and restart")
                import sys
                sys.exit(1)
                
            self.async_web3 = AsyncWeb3(get_web3_provider('async_http', provider_url))
            if not self.async_web3:
                self.logger.critical("CRITICAL: Failed to create AsyncWeb3 instance for whale transaction monitoring")
                self.logger.critical("AsyncWeb3 instance is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the AsyncWeb3 connectivity issues and restart")
                import sys
                sys.exit(1)
            
            # Initialize explorer - no fallbacks allowed
            self.explorer = create_blockchain_explorer(self._event_bus, self._config)
            if not self.explorer:
                self.logger.critical("CRITICAL: Failed to initialize blockchain explorer")
                self.logger.critical("Blockchain explorer is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the blockchain explorer issues and restart")
                import sys
                sys.exit(1)
            
            self.available = True
            self.logger.info("Blockchain monitoring connection established successfully")
            
            # Load configuration
            self._load_monitoring_config()
            
            # Start background monitoring tasks
            if not self._event_bus:
                self.logger.critical("CRITICAL: Event bus is not available for transaction monitoring")
                self.logger.critical("Event bus is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the event bus issues and restart")
                import sys
                sys.exit(1)
                
            asyncio.create_task(self._start_monitoring_loop())
                
        except Exception as e:
            self.logger.critical(f"CRITICAL: Failed to initialize blockchain connection: {str(e)}")
            self.logger.critical("Blockchain connection is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the connection issues and restart")
            import sys
            sys.exit(1)
            
    def _load_monitoring_config(self):
        """Load monitoring configuration."""
        if 'whale_thresholds' in self._config:
            self.whale_thresholds.update(self._config['whale_thresholds'])
            
        if 'monitored_addresses' in self._config:
            self.monitored_addresses.update(self._config['monitored_addresses'])
            
        self.logger.debug(f"Loaded monitoring config with {len(self.monitored_addresses)} addresses")
        self.logger.debug(f"Whale thresholds: {self.whale_thresholds}")
        
    def add_monitored_address(self, address, label=None):
        """Add an address to the monitoring list."""
        self.monitored_addresses.add(address)
        if label and self._event_bus:
            self._event_bus.publish("whale.address_added", {
                "address": address,
                "label": label
            })
        return True
    
    @property
    def event_bus(self):
        """Get the event bus."""
        return self._event_bus
    
    @event_bus.setter
    def event_bus(self, bus):
        """Set the event bus."""
        self._event_bus = bus
        if bus:
            self._register_event_handlers()
    
    def set_event_bus(self, bus):
        """Set the event bus and return success."""
        self.event_bus = bus
        return True
    
    def _register_event_handlers(self):
        """Register handlers with the event bus."""
        if not self._event_bus:
            return False
            
        try:
            # Core functionality handlers
            self._event_bus.subscribe(f"whale.request", self._handle_request)
            self._event_bus.subscribe(f"whale.monitor_address", self._handle_monitor_address)
            self._event_bus.subscribe(f"whale.unmonitor_address", self._handle_unmonitor_address)
            self._event_bus.subscribe(f"whale.get_whale_movements", self._handle_get_whale_movements)
            self._event_bus.subscribe(f"whale.get_transaction_history", self._handle_get_transaction_history)
            self._event_bus.subscribe(f"whale.set_threshold", self._handle_set_threshold)
            self._event_bus.subscribe(f"blockchain.new_transaction", self._handle_new_transaction)
            self._event_bus.subscribe(f"blockchain.new_block", self._handle_new_block)
            
            # Connect to the blockchain connector's events if available
            self._event_bus.subscribe(f"blockchain.connector.ready", self._handle_blockchain_ready)
            self._event_bus.subscribe(f"blockchain.connector.transaction", self._handle_blockchain_transaction)
            
            self.logger.debug(f"Registered event handlers for {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
            return False
    
    def _handle_request(self, event_type, data):
        """Handle general component requests."""
        self.logger.debug(f"Handling request {event_type}: {data}")
        
        action = data.get('action') if isinstance(data, dict) else None
        response = {"status": "success", "origin": self.name}
        
        if action == "status":
            response["data"] = {
                "available": self.available,
                "initialized": self.initialized,
                "monitoring_active": self.available and self.initialized,
                "addresses_monitored": len(self.monitored_addresses),
                "transactions_processed": len(self.transaction_history)
            }
        elif action == "start_monitoring":
            if self.available:
                asyncio.create_task(self._start_monitoring_loop())
                response["data"] = {"message": "Monitoring started or restarted"}
            else:
                response = {"status": "error", "error": "Blockchain connection not available"}
        else:
            response["data"] = {"message": "Request processed by TransactionMonitor"}
        
        if self._event_bus:
            self._event_bus.publish(f"whale.response", response)
        
        return response
        
    def _handle_monitor_address(self, event_type, data):
        """Handle request to monitor a specific address."""
        address = data.get('address')
        label = data.get('label')
        
        if not address:
            response = {"status": "error", "error": "No address provided"}
        else:
            success = self.add_monitored_address(address, label)
            response = {
                "status": "success" if success else "error",
                "data": {"address": address, "monitoring": success}
            }
            
        if self._event_bus:
            self._event_bus.publish(f"whale.response", response)
        
        return response
        
    def _handle_unmonitor_address(self, event_type, data):
        """Handle request to stop monitoring an address."""
        address = data.get('address')
        
        if not address or address not in self.monitored_addresses:
            response = {"status": "error", "error": "Address not found or not monitored"}
        else:
            self.monitored_addresses.remove(address)
            response = {
                "status": "success",
                "data": {"address": address, "monitoring": False}
            }
            
        if self._event_bus:
            self._event_bus.publish(f"whale.response", response)
        
        return response
        
    def _handle_get_whale_movements(self, event_type, data):
        """Handle request to get recent whale movements."""
        threshold = data.get('threshold', self.whale_thresholds.get('ethereum'))
        limit = data.get('limit', 10)
        
        # Filter transaction history for whale movements
        whale_movements = []
        for tx in reversed(self.transaction_history):  # Most recent first
            if len(whale_movements) >= limit:
                break
                
            if tx.get('value_eth', 0) >= threshold:
                whale_movements.append(tx)
                
        response = {
            "status": "success",
            "data": {
                "movements": whale_movements,
                "threshold": threshold,
                "count": len(whale_movements)
            }
        }
            
        if self._event_bus:
            self._event_bus.publish(f"whale.response", response)
        
        return response
        
    def _handle_get_transaction_history(self, event_type, data):
        """Handle request to get transaction history."""
        limit = data.get('limit', 20)
        address = data.get('address', None)
        
        # Filter transaction history if address is provided
        if address:
            filtered_history = [
                tx for tx in reversed(self.transaction_history) 
                if tx.get('from') == address or tx.get('to') == address
            ]
            history = filtered_history[:limit]
        else:
            history = list(reversed(self.transaction_history))[:limit]
                
        response = {
            "status": "success",
            "data": {
                "transactions": history,
                "count": len(history),
                "total_available": len(self.transaction_history)
            }
        }
            
        if self._event_bus:
            self._event_bus.publish(f"whale.response", response)
        
        return response
        
    def _handle_set_threshold(self, event_type, data):
        """Handle request to set whale threshold for a network."""
        network = data.get('network')
        threshold = data.get('threshold')
        
        if not network or threshold is None:
            response = {"status": "error", "error": "Network and threshold must be provided"}
        else:
            self.whale_thresholds[network] = threshold
            response = {
                "status": "success",
                "data": {
                    "network": network,
                    "threshold": threshold,
                    "all_thresholds": self.whale_thresholds
                }
            }
            
        if self._event_bus:
            self._event_bus.publish(f"whale.response", response)
        
        return response
        
    def _handle_new_transaction(self, event_type, data):
        """Handle new transaction events from blockchain."""
        tx_hash = data.get('hash')
        
        if not tx_hash or not self.available or not self.web3:
            return
            
        try:
            # Get transaction details
            tx = self.web3.eth.get_transaction(tx_hash)
            if not tx:
                return
                
            # Process the transaction
            self._process_transaction(dict(tx))
        except Exception as e:
            self.logger.error(f"Error processing transaction {tx_hash}: {str(e)}")
            
    def _handle_new_block(self, event_type, data):
        """Handle new block events from blockchain."""
        block_number = data.get('number')
        
        if not block_number or not self.available or not self.web3:
            return
            
        try:
            # Get block with transactions
            block = self.web3.eth.get_block(block_number, full_transactions=True)
            if not block or not hasattr(block, 'transactions'):
                return
                
            # Process each transaction in the block
            for tx in block.transactions:
                self._process_transaction(dict(tx))
        except Exception as e:
            self.logger.error(f"Error processing block {block_number}: {str(e)}")
            
    def _handle_blockchain_ready(self, event_type, data):
        """Handle blockchain connector ready events."""
        # Reinitialize the connection if needed
        if not self.available:
            self._initialize_blockchain_connection()
            
    def _handle_blockchain_transaction(self, event_type, data):
        """Handle transaction events from blockchain connector."""
        if isinstance(data, dict) and 'transaction' in data:
            self._process_transaction(data['transaction'])
            
    def _process_transaction(self, tx):
        """Process a transaction and check for whale activity."""
        # Verify Redis connection is active - no fallbacks allowed
        if not hasattr(kingdom_web3, 'redis_client') or not kingdom_web3.redis_client:
            self.logger.critical("CRITICAL: Redis Quantum Nexus connection lost during transaction processing")
            self.logger.critical("Redis connection is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the Redis connection issues and restart")
            import sys
            sys.exit(1)
            
        # Verify Redis port is exactly 6380
        if not hasattr(kingdom_web3, 'redis_port') or kingdom_web3.redis_port != 6380:
            self.logger.critical("CRITICAL: Redis Quantum Nexus not configured on mandatory port 6380")
            self.logger.critical("Redis connection on port 6380 is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the Redis port configuration and restart")
            import sys
            sys.exit(1)
            
        try:
            # Verify this is a valid transaction with required fields - no fallbacks allowed
            if not isinstance(tx, dict):
                self.logger.critical("CRITICAL: Invalid transaction format received")
                self.logger.critical("Transaction processing is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the transaction format and restart")
                import sys
                sys.exit(1)
                
            # Verify required fields are present - no fallbacks allowed
            if 'value' not in tx or 'from' not in tx or 'to' not in tx:
                self.logger.critical("CRITICAL: Transaction missing required fields (value, from, to)")
                self.logger.critical("Transaction integrity is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the transaction data format and restart")
                import sys
                sys.exit(1)
                
            # Get transaction amount in Ether - no fallbacks allowed
            try:
                # Convert from Wei to Ether
                value_eth = float(tx['value']) / 10**18
            except (ValueError, TypeError) as e:
                self.logger.critical(f"CRITICAL: Failed to convert transaction value: {str(e)}")
                self.logger.critical("Transaction value conversion is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the transaction value format and restart")
                import sys
                sys.exit(1)
                
            # Skip if below threshold - but still record to Redis for analytics
            if value_eth < self.whale_threshold:
                try:
                    # Store small transaction data in Redis for analytics
                    kingdom_web3.redis_client.lpush('kingdom:transactions:all', json.dumps({
                        "from": tx['from'],
                        "to": tx['to'],
                        "value": value_eth,
                        "timestamp": int(time.time())
                    }))
                    # Trim list to prevent unbounded growth
                    kingdom_web3.redis_client.ltrim('kingdom:transactions:all', 0, 9999)
                    return
                except Exception as redis_err:
                    self.logger.critical(f"CRITICAL: Failed to store transaction data in Redis: {str(redis_err)}")
                    self.logger.critical("Redis operations are MANDATORY with NO FALLBACKS ALLOWED")
                    self.logger.critical("System halting - fix the Redis connection and restart")
                    import sys
                    sys.exit(1)
                
            # Log whale transaction
            self.logger.info(f"🐳 Whale transaction detected: {value_eth:.2f} ETH from {tx['from'][:10]}... to {tx['to'][:10]}...")
            
            # Add to recent whales list with timestamp
            whale_tx = {
                "from": tx['from'],
                "to": tx['to'],
                "value": value_eth,
                "hash": tx.get('hash', '').hex() if hasattr(tx.get('hash', ''), 'hex') else tx.get('hash', ''),
                "timestamp": int(time.time()),
                "is_monitored": tx['from'] in self.monitored_addresses or tx['to'] in self.monitored_addresses
            }
            
            # Store in Redis - no fallbacks allowed
            try:
                kingdom_web3.redis_client.lpush('kingdom:transactions:whales', json.dumps(whale_tx))
                kingdom_web3.redis_client.ltrim('kingdom:transactions:whales', 0, 999)
            except Exception as redis_err:
                self.logger.critical(f"CRITICAL: Failed to store whale transaction in Redis: {str(redis_err)}")
                self.logger.critical("Redis operations are MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the Redis connection and restart")
                import sys
                sys.exit(1)
                
            # Keep only recent transactions in memory
            self.whale_transactions.append(whale_tx)
            if len(self.whale_transactions) > 100:  # Keep last 100
                self.whale_transactions.pop(0)
                
            # Add to transaction history
            self.transaction_history.append(whale_tx)
            if len(self.transaction_history) > 1000:  # Keep last 1000
                self.transaction_history.pop(0)
                
            # Publish whale alert event - no fallbacks allowed
            if not self._event_bus:
                self.logger.critical("CRITICAL: Event bus not available for whale transaction alerts")
                self.logger.critical("Event bus is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the event bus issues and restart")
                import sys
                sys.exit(1)
                
            self._event_bus.publish("blockchain.whale_transaction", whale_tx)
            
            # If this is a monitored address, publish specific event
            if whale_tx["is_monitored"]:
                self._event_bus.publish("whale.monitored_transaction", {
                    "transaction": whale_tx,
                    "monitored_address": tx['from'] if tx['from'] in self.monitored_addresses else tx['to']
                })
                
        except Exception as e:
            self.logger.critical(f"CRITICAL: Failed to process transaction: {str(e)}")
            self.logger.critical("Transaction processing is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the transaction processing issues and restart")
            import sys
            sys.exit(1)
            
    async def _start_monitoring_loop(self):
        """Start the blockchain monitoring loop."""
        self.logger.info("Starting blockchain monitoring loop")
        
        # Verify Redis connection is still established and healthy - no fallbacks allowed
        if not hasattr(kingdom_web3, 'redis_client') or not kingdom_web3.redis_client:
            self.logger.critical("CRITICAL: Redis Quantum Nexus connection lost during monitoring loop startup")
            self.logger.critical("Redis connection is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the Redis connection issues and restart")
            import sys
            sys.exit(1)
            
        # Verify blockchain connectivity - no fallbacks allowed
        if not self.async_web3:
            self.logger.critical("CRITICAL: Cannot start monitoring loop: AsyncWeb3 instance not available")
            self.logger.critical("AsyncWeb3 instance is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the blockchain connectivity and restart")
            import sys
            sys.exit(1)
            
        try:
            # Subscribe to new blocks
            self.logger.info("Subscribing to new blocks")
            
            # Get current block number as a starting point - no fallbacks allowed
            try:
                latest_block = await self.async_web3.eth.get_block_number()
                self.logger.info(f"Starting from block {latest_block}")
            except Exception as e:
                self.logger.critical(f"CRITICAL: Failed to get current block number: {str(e)}")
                self.logger.critical("Blockchain connectivity is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the blockchain connectivity and restart")
                import sys
                sys.exit(1)
            
            # Monitor new blocks - no failures allowed in core loop
            while True:
                try:
                    # Verify Redis connection is still active before each iteration
                    if not hasattr(kingdom_web3, 'redis_client') or not kingdom_web3.redis_client:
                        self.logger.critical("CRITICAL: Redis Quantum Nexus connection lost during monitoring")
                        self.logger.critical("Redis connection is MANDATORY with NO FALLBACKS ALLOWED")
                        self.logger.critical("System halting - fix the Redis connection issues and restart")
                        import sys
                        sys.exit(1)
                    
                    # Check for new blocks every 10 seconds
                    await asyncio.sleep(10)
                    
                    # Get latest block - no fallbacks allowed
                    try:
                        current_block = await self.async_web3.eth.get_block_number()
                    except Exception as e:
                        self.logger.critical(f"CRITICAL: Failed to get current block number: {str(e)}")
                        self.logger.critical("Blockchain connectivity is MANDATORY with NO FALLBACKS ALLOWED")
                        self.logger.critical("System halting - fix the blockchain connectivity and restart")
                        import sys
                        sys.exit(1)
                    
                    # Process any new blocks
                    if current_block > latest_block:
                        self.logger.info(f"Processing blocks {latest_block + 1} to {current_block}")
                        
                        for block_num in range(latest_block + 1, current_block + 1):
                            try:
                                # Get full block with transactions - no fallbacks allowed
                                block = await self.async_web3.eth.get_block(block_num, full_transactions=True)
                                
                                # Publish block event - event bus must be available
                                if not self._event_bus:
                                    self.logger.critical("CRITICAL: Event bus not available during monitoring")
                                    self.logger.critical("Event bus is MANDATORY with NO FALLBACKS ALLOWED")
                                    self.logger.critical("System halting - fix the event bus issues and restart")
                                    import sys
                                    sys.exit(1)
                                    
                                self._event_bus.publish("blockchain.new_block", {
                                    "number": block_num,
                                    "timestamp": block.timestamp,
                                    "transaction_count": len(block.transactions)
                                })
                                
                                # Process transactions
                                for tx in block.transactions:
                                    self._process_transaction(dict(tx))
                                    
                            except Exception as e:
                                self.logger.critical(f"CRITICAL: Failed to process block {block_num}: {str(e)}")
                                self.logger.critical("Blockchain block processing is MANDATORY with NO FALLBACKS ALLOWED")
                                self.logger.critical("System halting - fix the blockchain connectivity and restart")
                                import sys
                                sys.exit(1)
                        
                        latest_block = current_block
                        
                except asyncio.CancelledError:
                    self.logger.critical("CRITICAL: Blockchain monitoring loop cancelled")
                    self.logger.critical("Blockchain monitoring is MANDATORY with NO INTERRUPTIONS ALLOWED")
                    self.logger.critical("System halting - fix the monitoring loop issues and restart")
                    import sys
                    sys.exit(1)
                    
        except Exception as e:
            self.logger.critical(f"CRITICAL: Blockchain monitoring loop failed: {str(e)}")
            self.logger.critical("Blockchain monitoring is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the monitoring loop issues and restart")
            import sys
            sys.exit(1)
    
    async def initialize(self):
        """Initialize the component asynchronously."""
        self.logger.info(f"Initializing TransactionMonitor...")
        
        # Verify Redis connection is established and healthy - no fallbacks allowed
        if not hasattr(kingdom_web3, 'redis_client') or not kingdom_web3.redis_client:
            self.logger.critical("CRITICAL: Redis Quantum Nexus connection required for transaction monitoring")
            self.logger.critical("Redis connection is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the Redis connection issues and restart")
            import sys
            sys.exit(1)
            
        # Verify Redis port is exactly 6380 with password 'QuantumNexus2025'
        if not hasattr(kingdom_web3, 'redis_port') or kingdom_web3.redis_port != 6380:
            self.logger.critical("CRITICAL: Redis Quantum Nexus not configured on mandatory port 6380")
            self.logger.critical("Redis connection on port 6380 is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the Redis port configuration and restart")
            import sys
            sys.exit(1)
            
        # Verify Redis password
        if not hasattr(kingdom_web3, 'redis_password') or kingdom_web3.redis_password != 'QuantumNexus2025':
            self.logger.critical("CRITICAL: Redis Quantum Nexus password incorrect or not configured")
            self.logger.critical("Redis password 'QuantumNexus2025' is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the Redis password configuration and restart")
            import sys
            sys.exit(1)
            
        try:
            # Initialize blockchain connection and monitoring - no fallbacks allowed
            if not self.web3 or not self.async_web3 or not self.explorer:
                self._initialize_blockchain_connection()
                
            if not self._event_bus:
                self.logger.critical("CRITICAL: Event bus is not available for transaction monitoring")
                self.logger.critical("Event bus is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the event bus issues and restart")
                import sys
                sys.exit(1)
                
            self.initialized = True
            self.logger.info(f"TransactionMonitor initialization completed successfully")
            return True
        except Exception as e:
            self.logger.critical(f"CRITICAL: Failed to initialize TransactionMonitor: {str(e)}")
            self.logger.critical("TransactionMonitor initialization is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the initialization issues and restart")
            import sys
            sys.exit(1)
    
    def initialize_sync(self):
        """Initialize the component synchronously."""
        self.logger.info(f"Synchronously initializing TransactionMonitor...")
        
        # Verify Redis connection is established and healthy - no fallbacks allowed
        if not hasattr(kingdom_web3, 'redis_client') or not kingdom_web3.redis_client:
            self.logger.critical("CRITICAL: Redis Quantum Nexus connection required for transaction monitoring")
            self.logger.critical("Redis connection is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the Redis connection issues and restart")
            import sys
            sys.exit(1)
            
        # Verify Redis port is exactly 6380 with password 'QuantumNexus2025'
        if not hasattr(kingdom_web3, 'redis_port') or kingdom_web3.redis_port != 6380:
            self.logger.critical("CRITICAL: Redis Quantum Nexus not configured on mandatory port 6380")
            self.logger.critical("Redis connection on port 6380 is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the Redis port configuration and restart")
            import sys
            sys.exit(1)
            
        try:
            # Initialize blockchain connection and monitoring - no fallbacks allowed
            if not self.web3 or not self.async_web3 or not self.explorer:
                self._initialize_blockchain_connection()
                
            if not self._event_bus:
                self.logger.critical("CRITICAL: Event bus is not available for transaction monitoring")
                self.logger.critical("Event bus is MANDATORY with NO FALLBACKS ALLOWED")
                self.logger.critical("System halting - fix the event bus issues and restart")
                import sys
                sys.exit(1)
                
            self.initialized = True
            self.logger.info(f"TransactionMonitor synchronous initialization completed successfully")
            return True
        except Exception as e:
            self.logger.critical(f"CRITICAL: Failed during synchronous initialization: {str(e)}")
            self.logger.critical("TransactionMonitor initialization is MANDATORY with NO FALLBACKS ALLOWED")
            self.logger.critical("System halting - fix the initialization issues and restart")
            import sys
            sys.exit(1)