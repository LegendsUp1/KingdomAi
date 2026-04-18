#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - Blockchain Explorer Module

This module provides blockchain explorer functionality for the Kingdom AI system.
It integrates with the blockchain bridge to provide detailed information about
blockchain transactions, addresses, and blocks.
"""

import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Union
import json
import asyncio

# Set up logger
logger = logging.getLogger(__name__)

# Import blockchain bridge components - NO FALLBACKS ALLOWED
try:
    # Direct import from kingdomweb3_v2 - no relative imports or fallbacks
    from kingdomweb3_v2 import (
        rpc_manager, get_network_config, 
        BLOCKCHAIN_NETWORKS, create_async_web3_instance,
        add_middleware, to_checksum_address as toChecksumAddress, 
        TxParams, 
        ConnectionError, ContractLogicError, ValidationError, TimeExhausted, TransactionNotFound
    )
    
    # Use kingdomweb3_v2 RPC manager directly
    kingdom_web3 = None  # Will use rpc_manager directly
    
    # Create Web3 and AsyncWeb3 class references
    Web3 = kingdom_web3.get_web3_class()
    AsyncWeb3 = kingdom_web3.get_async_web3_class()
    
    # Create global function references for direct access
    get_web3_provider = kingdom_web3.get_provider
    
    # Initialize Redis connection check - MANDATORY, no fallbacks
    if not kingdom_web3._connect_redis_quantum_nexus():
        logger.critical("Redis Quantum Nexus connection failed - port 6380 with password 'QuantumNexus2025'")
        logger.critical("This connection is MANDATORY with NO FALLBACKS ALLOWED")
        logger.critical("System halting - fix Redis Quantum Nexus and restart")
        sys.exit(1)
    
    # Set bridge availability flag
    BLOCKCHAIN_BRIDGE_AVAILABLE = True
    
    logger.info("Successfully imported KingdomWeb3 components and verified Redis Quantum Nexus")
except Exception as e:
    logger.error(f"KingdomWeb3 compatibility layer not available: {str(e)}")
    # System must halt on critical blockchain errors per policy
    logger.critical("Blockchain functionality is MANDATORY with NO FALLBACKS ALLOWED")
    logger.critical("System halting - fix blockchain components and restart")
    sys.exit(1)  

class BlockchainExplorer:
    """
    Kingdom AI Blockchain Explorer
    
    Provides comprehensive blockchain data exploration capabilities for
    Ethereum and compatible networks. Integrates with the KingdomWeb3 bridge.
    """
    
    def __init__(self, event_bus=None, config=None, web3_instance=None):
        """Initialize the BlockchainExplorer."""
        self.name = "blockchain.explorer"
        self.logger = logging.getLogger(f"KingdomAI.BlockchainExplorer")
        self._event_bus = event_bus
        self._config = config or {}
        self.web3 = web3_instance
        self.async_web3 = None
        self.initialized = False
        self.available = False
        self._initialize_web3()
        
        if self._event_bus:
            self._register_event_handlers()
            
        self.logger.info(f"BlockchainExplorer initialized")
        
    def _initialize_web3(self):
        """Initialize Web3 connection using the blockchain bridge."""
        try:
            if not self.web3:
                # Try to create a Web3 instance through the bridge
                self.web3 = create_web3_instance()
                
            # Create async Web3 instance if needed for specific operations
            if 'async_provider' in self._config:
                from blockchain.blockchain_bridge import create_async_web3_instance
                provider_url = self._config.get('async_provider')
                self.async_web3 = create_async_web3_instance(
                    get_web3_provider('async_http', provider_url)
                )
                
            self.available = self.web3 is not None
            if self.available:
                self.logger.info(f"BlockchainExplorer web3 connection established")
            else:
                self.logger.warning(f"BlockchainExplorer web3 connection not available")
        except Exception as e:
            self.logger.error(f"Failed to initialize Web3: {str(e)}")
            self.available = False
    
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
            self._event_bus.subscribe(f"{self.name}.get_block", self._handle_get_block)
            self._event_bus.subscribe(f"{self.name}.get_transaction", self._handle_get_transaction)
            self._event_bus.subscribe(f"{self.name}.get_address", self._handle_get_address)
            self._event_bus.subscribe(f"{self.name}.search", self._handle_search)
            self.logger.debug(f"Registered event handlers for {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
            return False
    
    def _handle_get_block(self, event_type, data):
        """Handle get_block requests."""
        self.logger.debug(f"Handling {event_type}: {data}")
        
        if not self.available:
            return self._error_response("BlockchainExplorer not available")
        
        try:
            block_id = data.get('block_id')
            if not block_id:
                return self._error_response("Missing block_id parameter")
                
            block_data = self.get_block(block_id)
            return {
                "status": "success",
                "data": block_data
            }
        except Exception as e:
            self.logger.error(f"Error in _handle_get_block: {str(e)}")
            return self._error_response(f"Failed to get block: {str(e)}")
    
    def _handle_get_transaction(self, event_type, data):
        """Handle get_transaction requests."""
        self.logger.debug(f"Handling {event_type}: {data}")
        
        if not self.available:
            return self._error_response("BlockchainExplorer not available")
        
        try:
            tx_hash = data.get('tx_hash')
            if not tx_hash:
                return self._error_response("Missing tx_hash parameter")
                
            tx_data = self.get_transaction(tx_hash)
            return {
                "status": "success",
                "data": tx_data
            }
        except Exception as e:
            self.logger.error(f"Error in _handle_get_transaction: {str(e)}")
            return self._error_response(f"Failed to get transaction: {str(e)}")
    
    def _handle_get_address(self, event_type, data):
        """Handle get_address requests."""
        self.logger.debug(f"Handling {event_type}: {data}")
        
        if not self.available:
            return self._error_response("BlockchainExplorer not available")
        
        try:
            address = data.get('address')
            if not address:
                return self._error_response("Missing address parameter")
                
            address_data = self.get_address(address)
            return {
                "status": "success",
                "data": address_data
            }
        except Exception as e:
            self.logger.error(f"Error in _handle_get_address: {str(e)}")
            return self._error_response(f"Failed to get address: {str(e)}")
    
    def _handle_search(self, event_type, data):
        """Handle search requests."""
        self.logger.debug(f"Handling {event_type}: {data}")
        
        if not self.available:
            return self._error_response("BlockchainExplorer not available")
        
        try:
            query = data.get('query')
            if not query:
                return self._error_response("Missing query parameter")
                
            search_results = self.search(query)
            return {
                "status": "success",
                "data": search_results
            }
        except Exception as e:
            self.logger.error(f"Error in _handle_search: {str(e)}")
            return self._error_response(f"Failed to search: {str(e)}")
    
    def _error_response(self, message):
        """Create an error response."""
        return {
            "status": "error",
            "error": message
        }
        
    async def initialize(self):
        """Initialize the component asynchronously."""
        self.logger.info(f"Initializing BlockchainExplorer...")
        try:
            # Ensure we have a Web3 connection
            if not self.web3:
                self._initialize_web3()
                
            # Additional async initialization if needed
            self.initialized = True
            self.logger.info(f"BlockchainExplorer initialization complete")
            return self.available
        except Exception as e:
            self.logger.error(f"Error initializing BlockchainExplorer: {e}")
            return False
    
    def initialize_sync(self):
        """Initialize the component synchronously."""
        self.logger.info(f"Synchronously initializing BlockchainExplorer...")
        try:
            # Ensure we have a Web3 connection
            if not self.web3:
                self._initialize_web3()
                
            self.initialized = True
            self.logger.info(f"BlockchainExplorer synchronous initialization complete")
            return self.available
        except Exception as e:
            self.logger.error(f"Error during synchronous initialization: {e}")
            return False
            
    def get_block(self, block_id):
        """Get block data by block number or hash."""
        if not self.available:
            raise ValueError("BlockchainExplorer not available")
            
        try:
            block = self.web3.eth.get_block(block_id, full_transactions=True)
            # Convert block to serializable dict
            return self._format_block(block)
        except Exception as e:
            self.logger.error(f"Error getting block {block_id}: {str(e)}")
            raise
    
    def get_transaction(self, tx_hash):
        """Get transaction data by hash."""
        if not self.available:
            raise ValueError("BlockchainExplorer not available")
            
        try:
            # Get transaction data
            tx = self.web3.eth.get_transaction(tx_hash)
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            
            # Combine and format data
            return self._format_transaction(tx, receipt)
        except Exception as e:
            self.logger.error(f"Error getting transaction {tx_hash}: {str(e)}")
            raise
    
    def get_address(self, address):
        """Get address data (balance, code, etc.)."""
        if not self.available:
            raise ValueError("BlockchainExplorer not available")
            
        try:
            # Get basic address data
            balance = self.web3.eth.get_balance(address)
            code = self.web3.eth.get_code(address)
            nonce = self.web3.eth.get_transaction_count(address)
            
            # Format and return data
            return {
                "address": address,
                "balance": balance,
                "balance_eth": self.web3.from_wei(balance, 'ether'),
                "code_exists": code != '0x' and len(code) > 2,
                "nonce": nonce,
                "is_contract": code != '0x' and len(code) > 2
            }
        except Exception as e:
            self.logger.error(f"Error getting address {address}: {str(e)}")
            raise
    
    def search(self, query):
        """Search for blocks, transactions, or addresses."""
        if not self.available:
            raise ValueError("BlockchainExplorer not available")
            
        results = {
            "type": "unknown",
            "data": None
        }
        
        try:
            # Check if query is a block number
            if query.isdigit():
                try:
                    block = self.get_block(int(query))
                    results = {"type": "block", "data": block}
                except Exception as e:
                    self.logger.debug(f"Query {query} is not a valid block number: {str(e)}")
            
            # Check if query is a block hash or transaction hash (0x...)
            elif query.startswith("0x") and len(query) == 66:
                try:
                    tx = self.get_transaction(query)
                    results = {"type": "transaction", "data": tx}
                except Exception as e1:
                    self.logger.debug(f"Query {query} is not a valid transaction hash: {str(e1)}")
                    try:
                        block = self.get_block(query)
                        results = {"type": "block", "data": block}
                    except Exception as e2:
                        self.logger.debug(f"Query {query} is not a valid block hash either: {str(e2)}")
            
            # Check if query is an address (0x... with 42 chars)
            elif query.startswith("0x") and len(query) == 42:
                try:
                    address = self.get_address(query)
                    results = {"type": "address", "data": address}
                except Exception as e:
                    self.logger.debug(f"Query {query} is not a valid address: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"Error searching for {query}: {str(e)}")
            results = {"type": "error", "error": str(e)}
            
        return results
    
    def _format_block(self, block):
        """Format block data to be serializable."""
        block_dict = dict(block)
        
        # Process transactions if they're full objects
        if 'transactions' in block_dict and block_dict['transactions'] and hasattr(block_dict['transactions'][0], 'items'):
            block_dict['transactions'] = [dict(tx) for tx in block_dict['transactions']]
            
        # Convert any non-serializable objects
        for key, value in block_dict.items():
            if isinstance(value, bytes):
                block_dict[key] = value.hex()
                
        return block_dict
    
    def _format_transaction(self, tx, receipt):
        """Format transaction data to be serializable."""
        # Convert tx and receipt to dicts
        tx_dict = dict(tx) if tx else {}
        receipt_dict = dict(receipt) if receipt else {}
        
        # Merge the dicts, with receipt taking precedence
        result = {**tx_dict, **receipt_dict}
        
        # Convert any non-serializable objects
        for key, value in result.items():
            if isinstance(value, bytes):
                result[key] = value.hex()
                
        # Add calculated fields
        if 'gasPrice' in result and 'gasUsed' in result:
            result['txFee'] = result['gasPrice'] * result['gasUsed']
            result['txFeeEth'] = self.web3.from_wei(result['txFee'], 'ether')
                
        return result

def create_blockchain_explorer(event_bus=None, config=None):
    """Factory function to create a BlockchainExplorer instance."""
    try:
        # Create and initialize the explorer
        explorer = BlockchainExplorer(event_bus=event_bus, config=config)
        explorer.initialize_sync()
        return explorer
    except Exception as e:
        logger.error(f"Failed to create BlockchainExplorer: {str(e)}")
        return None

# This ensures the module is always "available" in some form
BLOCKCHAIN_EXPLORER_AVAILABLE = True
