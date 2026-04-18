#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SmartContracts component for interacting with blockchain smart contracts.
"""

import os
import logging
import json
from web3 import Web3, AsyncWeb3

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class SmartContracts(BaseComponent):
    """
    Component for creating, deploying, and interacting with blockchain smart contracts.
    Provides an interface for contract operations across multiple chains.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the SmartContracts component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "SmartContracts"
        self.description = "Manages and interacts with blockchain smart contracts"
        
        # Network configurations
        self.networks = self.config.get("networks", {
            "ethereum": {
                "rpc_url": "https://mainnet.infura.io/v3/your-infura-key",
                "chain_id": 1,
                "explorer": "https://etherscan.io"
            },
            "binance": {
                "rpc_url": "https://bsc-dataseed.binance.org/",
                "chain_id": 56,
                "explorer": "https://bscscan.com"
            },
            "polygon": {
                "rpc_url": "https://polygon-rpc.com",
                "chain_id": 137,
                "explorer": "https://polygonscan.com"
            }
        })
        
        # Web3 instances for each network
        self.web3_instances = {}
        
        # Contract instances
        self.contracts = {}
        
        # ABI cache
        self.abi_cache = {}
        
        # Account management
        self.accounts = {}
        self.default_account = None
        
    async def initialize(self):
        """Initialize the SmartContracts component."""
        logger.info("Initializing SmartContracts component")
        
        # Subscribe to relevant events
        self.event_bus and self.event_bus.subscribe_sync("contract.deploy", self.on_contract_deploy)
        self.event_bus and self.event_bus.subscribe_sync("contract.interact", self.on_contract_interact)
        self.event_bus and self.event_bus.subscribe_sync("account.create", self.on_account_create)
        self.event_bus and self.event_bus.subscribe_sync("account.import", self.on_account_import)
        self.event_bus and self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        
        # Initialize Web3 connections
        await self.init_web3_connections()
        
        # Load saved contracts
        await self.load_saved_contracts()
        
        # Load accounts
        await self.load_accounts()
        
        logger.info("SmartContracts component initialized")
        
    async def init_web3_connections(self):
        """Initialize Web3 connections for each configured network."""
        for network_name, network_config in self.networks.items():
            try:
                rpc_url = network_config.get("rpc_url")
                if not rpc_url:
                    logger.warning(f"RPC URL not configured for network {network_name}")
                    continue
                
                # Create AsyncWeb3 instance for non-blocking operations
                web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
                
                # Test connection
                connected = await web3.is_connected()
                if connected:
                    self.web3_instances[network_name] = web3
                    logger.info(f"Connected to {network_name} blockchain")
                else:
                    logger.error(f"Failed to connect to {network_name} blockchain")
            except Exception as e:
                logger.error(f"Error initializing Web3 for {network_name}: {str(e)}")
                
        # Publish connection status
        self.event_bus.publish("contract.network.status", {
            "connected_networks": list(self.web3_instances.keys()),
            "total_networks": len(self.networks),
            "connected_count": len(self.web3_instances)
        })
    
    async def load_saved_contracts(self):
        """Load saved contract information from storage."""
        contracts_file = os.path.join(self.config.get("data_dir", "data"), "contracts.json")
        
        try:
            if os.path.exists(contracts_file):
                with open(contracts_file, 'r') as f:
                    saved_contracts = json.load(f)
                    
                for contract_name, contract_data in saved_contracts.items():
                    network = contract_data.get("network")
                    address = contract_data.get("address")
                    abi = contract_data.get("abi")
                    
                    if network and address and abi and network in self.web3_instances:
                        # Initialize contract instance
                        web3 = self.web3_instances[network]
                        contract = web3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
                        
                        # Store contract instance and ABI
                        self.contracts[contract_name] = {
                            "network": network,
                            "address": address,
                            "contract": contract,
                            "metadata": contract_data.get("metadata", {})
                        }
                        self.abi_cache[address] = abi
                        
                logger.info(f"Loaded {len(self.contracts)} saved contracts")
        except Exception as e:
            logger.error(f"Error loading saved contracts: {str(e)}")
    
    async def load_accounts(self):
        """Load accounts from secure storage."""
        accounts_file = os.path.join(self.config.get("secure_dir", "secure"), "accounts.json")
        
        try:
            if os.path.exists(accounts_file):
                with open(accounts_file, 'r') as f:
                    encrypted_accounts = json.load(f)
                
                # In a real implementation, this would decrypt the accounts using a secure key
                # For this example, we'll assume accounts are already loaded in the correct format
                
                for account_name, account_data in encrypted_accounts.items():
                    if "address" in account_data:
                        self.accounts[account_name] = {
                            "address": account_data["address"],
                            "network": account_data.get("network", "ethereum")
                        }
                
                # Set default account if exists
                if "default" in self.accounts:
                    self.default_account = self.accounts["default"]
                    
                logger.info(f"Loaded {len(self.accounts)} accounts")
        except Exception as e:
            logger.error(f"Error loading accounts: {str(e)}")
    
    async def deploy_contract(self, contract_name, abi, bytecode, constructor_args=None, network="ethereum", account=None):
        """
        Deploy a new smart contract.
        
        Args:
            contract_name: Name to identify the contract
            abi: Contract ABI
            bytecode: Contract bytecode
            constructor_args: Constructor arguments
            network: Target blockchain network
            account: Account to use for deployment
            
        Returns:
            dict: Deployment result with contract address
        """
        if network not in self.web3_instances:
            msg = f"Network {network} not connected"
            logger.error(msg)
            return {"success": False, "error": msg}
        
        web3 = self.web3_instances[network]
        
        try:
            # Create contract object
            contract = web3.eth.contract(abi=abi, bytecode=bytecode)
            
            # Prepare constructor arguments
            args = constructor_args or []
            
            # Get account to use
            if not account and self.default_account:
                account = self.default_account
                
            if not account:
                msg = "No account specified and no default account set"
                logger.error(msg)
                return {"success": False, "error": msg}
            
            # Build constructor transaction
            construct_txn = await contract.constructor(*args).build_transaction({
                'from': account["address"],
                'nonce': await web3.eth.get_transaction_count(account["address"]),
                'gas': 2000000,
                'gasPrice': await web3.eth.gas_price
            })
            
            private_key = account.get("private_key")
            if not private_key:
                msg = "Account has no private key — cannot sign deployment transaction"
                logger.error(msg)
                return {"success": False, "error": msg}

            signed_txn = web3.eth.account.sign_transaction(construct_txn, private_key)
            tx_hash = await web3.eth.send_raw_transaction(signed_txn.raw_transaction)
            tx_receipt = await web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            contract_address = tx_receipt["contractAddress"]
            if not contract_address:
                return {"success": False, "error": "Deployment receipt contains no contract address"}

            contract_address = Web3.to_checksum_address(contract_address)

            self.contracts[contract_name] = {
                "network": network,
                "address": contract_address,
                "contract": web3.eth.contract(address=contract_address, abi=abi),
                "metadata": {
                    "deployer": account["address"],
                    "deployment_time": tx_receipt.get("blockNumber", 0),
                    "constructor_args": args,
                    "tx_hash": tx_hash.hex() if hasattr(tx_hash, 'hex') else str(tx_hash)
                }
            }
            self.abi_cache[contract_address] = abi
            
            # Save contract data
            await self.save_contracts()
            
            # Publish deployment event
            self.event_bus.publish("contract.deployed", {
                "name": contract_name,
                "address": contract_address,
                "network": network
            })
            
            return {
                "success": True,
                "contract_name": contract_name,
                "address": contract_address,
                "network": network,
                "explorer_url": f"{self.networks[network]['explorer']}/address/{contract_address}"
            }
            
        except Exception as e:
            logger.error(f"Error deploying contract: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def interact_with_contract(self, contract_identifier, method_name, args=None, value=0, account=None, network=None):
        """
        Interact with a deployed smart contract.
        
        Args:
            contract_identifier: Contract name or address
            method_name: Name of the contract method to call
            args: Method arguments
            value: ETH value to send (for payable functions)
            account: Account to use for the transaction
            network: Target blockchain network (only needed if contract_identifier is an address)
            
        Returns:
            dict: Interaction result
        """
        # Determine if identifier is a name or address
        contract_data = None
        if contract_identifier in self.contracts:
            contract_data = self.contracts[contract_identifier]
            network = contract_data["network"]
        elif network and Web3.is_address(contract_identifier):
            # Try to get contract by address
            address = Web3.to_checksum_address(contract_identifier)
            if address in self.abi_cache:
                web3 = self.web3_instances.get(network)
                if web3:
                    contract = web3.eth.contract(address=address, abi=self.abi_cache[address])
                    contract_data = {
                        "network": network,
                        "address": address,
                        "contract": contract
                    }
            
        if not contract_data:
            msg = f"Contract {contract_identifier} not found"
            logger.error(msg)
            return {"success": False, "error": msg}
            
        if network not in self.web3_instances:
            msg = f"Network {network} not connected"
            logger.error(msg)
            return {"success": False, "error": msg}
            
        web3 = self.web3_instances[network]
        contract = contract_data["contract"]
        
        try:
            # Check if method exists
            if not hasattr(contract.functions, method_name):
                msg = f"Method {method_name} not found in contract"
                logger.error(msg)
                return {"success": False, "error": msg}
                
            contract_function = getattr(contract.functions, method_name)
            method_args = args or []
            
            # Check if method is view/pure (read-only) or requires transaction
            method_obj = contract_function(*method_args)
            
            # Try to call the method as view first
            try:
                result = await method_obj.call()
                return {
                    "success": True,
                    "read_only": True,
                    "result": result
                }
            except Exception:
                # Method requires transaction
                # Get account to use
                if not account and self.default_account:
                    account = self.default_account
                    
                if not account:
                    msg = "No account specified and no default account set"
                    logger.error(msg)
                    return {"success": False, "error": msg}
                
                # Build transaction
                txn = await method_obj.build_transaction({
                    'from': account["address"],
                    'nonce': await web3.eth.get_transaction_count(account["address"]),
                    'gas': 2000000,
                    'gasPrice': await web3.eth.gas_price,
                    'value': value
                })
                
                private_key = account.get("private_key")
                if not private_key:
                    msg = "Account has no private key — cannot sign transaction"
                    logger.error(msg)
                    return {"success": False, "error": msg}

                signed_txn = web3.eth.account.sign_transaction(txn, private_key)
                tx_hash_bytes = await web3.eth.send_raw_transaction(signed_txn.raw_transaction)
                tx_hash = tx_hash_bytes.hex() if hasattr(tx_hash_bytes, 'hex') else str(tx_hash_bytes)

                self.event_bus.publish("contract.transaction.sent", {
                    "contract": contract_identifier,
                    "method": method_name,
                    "tx_hash": tx_hash,
                    "network": network
                })

                return {
                    "success": True,
                    "read_only": False,
                    "tx_hash": tx_hash,
                    "explorer_url": f"{self.networks[network]['explorer']}/tx/{tx_hash}"
                }
                
        except Exception as e:
            logger.error(f"Error interacting with contract: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def on_contract_deploy(self, data):
        """
        Handle contract deployment event.
        
        Args:
            data: Deployment data
        """
        result = await self.deploy_contract(
            contract_name=data.get("name", f"Contract_{data.get('network', 'ethereum')}_{len(self.contracts)}"),
            abi=data.get("abi"),
            bytecode=data.get("bytecode"),
            constructor_args=data.get("constructor_args"),
            network=data.get("network", "ethereum"),
            account=data.get("account", self.default_account)
        )
        
        # Publish result
        self.event_bus.publish("contract.deploy.result", {
            "request_id": data.get("request_id"),
            "result": result
        })
    
    async def on_contract_interact(self, data):
        """
        Handle contract interaction event.
        
        Args:
            data: Interaction data
        """
        result = await self.interact_with_contract(
            contract_identifier=data.get("contract"),
            method_name=data.get("method"),
            args=data.get("args"),
            value=data.get("value", 0),
            account=data.get("account"),
            network=data.get("network")
        )
        
        # Publish result
        self.event_bus.publish("contract.interact.result", {
            "request_id": data.get("request_id"),
            "result": result
        })
    
    async def on_account_create(self, data):
        """
        Handle account creation event.
        
        Args:
            data: Account creation data
        """
        import os
        from eth_account import Account as EthAccount

        account_name = data.get("name", f"Account_{len(self.accounts)}")
        network = data.get("network", "ethereum")

        new_acct = EthAccount.create(extra_entropy=os.urandom(32))
        account_address = new_acct.address
        private_key_hex = new_acct.key.hex() if hasattr(new_acct.key, 'hex') else str(new_acct.key)
        
        self.accounts[account_name] = {
            "address": account_address,
            "private_key": private_key_hex,
            "network": network
        }

        if data.get("set_default", not self.default_account):
            self.default_account = self.accounts[account_name]

        await self.save_accounts()

        self.event_bus.publish("account.create.result", {
            "request_id": data.get("request_id"),
            "success": True,
            "account_name": account_name,
            "address": account_address,
            "network": network
        })
    
    async def on_account_import(self, data):
        """
        Handle account import event.
        
        Args:
            data: Account import data
        """
        # In a real implementation, this would securely encrypt and store
        # the imported private key
        
        # For this example, we'll simulate account import
        account_name = data.get("name", f"Imported_{len(self.accounts)}")
        account_address = data.get("address", "0x" + "0" * 40)  # Use provided address or placeholder
        network = data.get("network", "ethereum")
        
        self.accounts[account_name] = {
            "address": account_address,
            "network": network
        }
        
        # Set as default if requested
        if data.get("set_default", False):
            self.default_account = self.accounts[account_name]
            
        # Save accounts
        await self.save_accounts()
        
        # Publish result
        self.event_bus.publish("account.import.result", {
            "request_id": data.get("request_id"),
            "success": True,
            "account_name": account_name,
            "address": account_address,
            "network": network
        })
    
    async def save_contracts(self):
        """Save contract data to persistent storage."""
        contracts_file = os.path.join(self.config.get("data_dir", "data"), "contracts.json")
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(contracts_file), exist_ok=True)
            
            # Prepare contract data for saving
            contracts_data = {}
            for name, data in self.contracts.items():
                contracts_data[name] = {
                    "network": data["network"],
                    "address": data["address"],
                    "abi": self.abi_cache.get(data["address"]),
                    "metadata": data.get("metadata", {})
                }
                
            # Write to file
            with open(contracts_file, 'w') as f:
                json.dump(contracts_data, f, indent=2)
                
            logger.info(f"Saved {len(contracts_data)} contracts to {contracts_file}")
        except Exception as e:
            logger.error(f"Error saving contracts: {str(e)}")
    
    async def save_accounts(self):
        """Save account data to secure storage."""
        accounts_file = os.path.join(self.config.get("secure_dir", "secure"), "accounts.json")
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(accounts_file), exist_ok=True)
            
            # Prepare account data for saving
            # In a real implementation, this would encrypt private keys
            encrypted_accounts = {}
            for name, data in self.accounts.items():
                encrypted_accounts[name] = {
                    "address": data["address"],
                    "network": data.get("network", "ethereum")
                }
                
            # Write to file
            with open(accounts_file, 'w') as f:
                json.dump(encrypted_accounts, f, indent=2)
                
            logger.info(f"Saved {len(encrypted_accounts)} accounts to {accounts_file}")
        except Exception as e:
            logger.error(f"Error saving accounts: {str(e)}")
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the SmartContracts component."""
        logger.info("Shutting down SmartContracts component")
        
        # Save data
        await self.save_contracts()
        await self.save_accounts()
        
        # Close web3 connections if needed
        
        logger.info("SmartContracts component shut down successfully")
