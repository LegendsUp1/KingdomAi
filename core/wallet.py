"""Wallet management for Kingdom AI system."""

import logging
import json
import os
import secrets
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3.types import Wei
from eth_typing import HexStr
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from datetime import datetime
import time
from web3 import Web3
from eth_account.messages import encode_defunct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.event_bus import EventBus

from core.base_component import BaseComponent
from core.blockchain import BlockchainConnector
from core.sentience.wallet_sentience_integration import WalletSentienceIntegration

class Wallet(BaseComponent):
    """Wallet management system."""
    
    def __init__(self, event_bus: Optional["EventBus"] = None, blockchain: Optional[BlockchainConnector] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize wallet system.
        
        Args:
            event_bus: EventBus instance for event-driven communication
            blockchain: Blockchain connector (can be set later via set_blockchain)
            config: Configuration dictionary
        """
        super().__init__(name="Wallet", event_bus=event_bus, config=config)
        self.blockchain = blockchain
        self.logger = logging.getLogger("Wallet")
        self.account: Optional[LocalAccount] = None
        self.keystore_path = Path("wallets")
        self.fernet: Optional[Fernet] = None
        self.active_wallets: Dict[str, Dict[str, Any]] = {}
        self.hardware_wallets: Dict[str, Dict[str, Any]] = {}
        
        # AI Sentience Detection Framework integration
        self.sentience_integration = WalletSentienceIntegration(event_bus=event_bus, wallet=self)
        
    def set_blockchain(self, blockchain: BlockchainConnector) -> None:
        """Set the blockchain connector.
        
        Args:
            blockchain: Blockchain connector instance
        """
        self.blockchain = blockchain
        self.logger.info("Blockchain connector set")
        
    def initialize(self) -> bool:
        """Initialize wallet system.
        
        Returns:
            True if initialized successfully
        """
        try:
            # Create wallets directory if it doesn't exist
            self.keystore_path.mkdir(exist_ok=True)
            
            # Initialize encryption
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(b"KINGDOM_AI_SECURE_KEY"))
            self.fernet = Fernet(key)
            
            # Load existing wallets
            self._load_existing_wallets_sync()
            
            # Initialize sentience integration
            if self.sentience_integration:
                sentience_init_result = self.sentience_integration.initialize(event_bus=self.event_bus, wallet=self)
                if sentience_init_result:
                    self.sentience_integration.start_monitoring()
                    self.logger.info("Wallet sentience monitoring activated")
                else:
                    self.logger.warning("Failed to initialize wallet sentience integration")
            
            self.logger.info("Wallet system initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing wallet: {e}")
            return False
            
    async def initialize_async(self):
        """Async version of initialize"""
        try:
            # Create wallets directory if it doesn't exist
            self.keystore_path.mkdir(exist_ok=True)
            
            # Initialize encryption
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(b"KINGDOM_AI_SECURE_KEY"))
            self.fernet = Fernet(key)
            
            # Load existing wallets
            await self._load_existing_wallets()
            
            self.logger.info("Wallet system initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing wallet: {e}")
            return False

    def _load_existing_wallets_sync(self) -> None:
        """Synchronous version of _load_existing_wallets"""
        try:
            for wallet_file in self.keystore_path.glob("*.json"):
                try:
                    with open(wallet_file, encoding="utf-8") as f:
                        keystore = json.load(f)
                    address = wallet_file.stem
                    self.active_wallets[address] = keystore
                    self.logger.info(f"Loaded wallet: {address}")
                except Exception as e:
                    self.logger.error(f"Error loading wallet {wallet_file}: {e}")
        except Exception as e:
            self.logger.error(f"Error loading wallets: {e}")

    async def _load_existing_wallets(self) -> None:
        """Load existing wallets from keystore."""
        try:
            for wallet_file in self.keystore_path.glob("*.json"):
                try:
                    with open(wallet_file, encoding="utf-8") as f:
                        keystore = json.load(f)
                    address = wallet_file.stem
                    
                    # Check if blockchain is available before calling methods
                    balance = None
                    if self.blockchain:
                        balance = await self.blockchain.get_balance(address)
                    
                    self.active_wallets[address] = {
                        "keystore": keystore,
                        "balance": balance,
                        "transactions": []
                    }
                except Exception as e:
                    self.logger.error(f"Error loading wallet {wallet_file}: {e}")
        except Exception as e:
            self.logger.error(f"Error loading existing wallets: {e}")
            
    async def create_wallet(self, password: str, name: str = "") -> Optional[str]:
        """Create new wallet.
        
        Args:
            password: Wallet encryption password
            name: Optional wallet name
            
        Returns:
            Wallet address or None if error
        """
        try:
            # Generate new account with extra entropy
            extra_entropy = secrets.token_bytes(32)
            account = Account.create(extra_entropy=extra_entropy)
            
            # Create keystore with strong encryption
            keystore = Account.encrypt(
                private_key=account._private_key,
                password=password
            )
            
            # Encrypt keystore before saving
            if self.fernet:
                encrypted_keystore = self.fernet.encrypt(json.dumps(keystore).encode())
                
                # Save encrypted keystore
                wallet_path = self.keystore_path / f"{account.address}.json"
                with open(wallet_path, "wb") as f:
                    f.write(encrypted_keystore)
                    
            # Add to active wallets
            self.active_wallets[account.address] = {
                "keystore": keystore,
                "name": name,
                "balance": Wei(0),
                "transactions": []
            }
            
            # Set as current account
            self.account = account
                
            self.logger.info(f"Created wallet: {account.address}")
            return account.address
            
        except Exception as e:
            self.logger.error(f"Error creating wallet: {e}")
            return None
            
    async def load_wallet(self, address: str, password: str) -> bool:
        """Load existing wallet.
        
        Args:
            address: Wallet address
            password: Wallet encryption password
            
        Returns:
            True if loaded successfully
        """
        try:
            # Load encrypted keystore
            wallet_path = self.keystore_path / f"{address}.json"
            with open(wallet_path, "rb") as f:
                encrypted_data = f.read()
                
            # Decrypt keystore
            if not self.fernet:
                return False
                
            decrypted_data = self.fernet.decrypt(encrypted_data)
            keystore = json.loads(decrypted_data)
                
            # Decrypt private key
            private_key = Account.decrypt(keystore, password)
                
            # Create account
            account = Account.from_key(private_key)
            self.account = account
                
            # Update active wallet
            if address not in self.active_wallets:
                self.active_wallets[address] = {
                    "keystore": keystore,
                    "balance": await self.get_balance(address),
                    "transactions": []
                }
                    
            self.logger.info(f"Loaded wallet: {address}")
            return True
                
        except Exception as e:
            self.logger.error(f"Error loading wallet: {e}")
            return False
            
    async def import_hardware_wallet(self, address: str, name: str = "") -> bool:
        """Import hardware wallet.
        
        Args:
            address: Hardware wallet address
            name: Optional wallet name
            
        Returns:
            True if imported successfully
        """
        try:
            # Verify address format
            if not Web3.is_address(address):
                raise ValueError("Invalid address format")
                
            # Add to hardware wallets
            self.hardware_wallets[address] = {
                "name": name,
                "balance": await self.get_balance(address),
                "transactions": []
            }
            
            self.logger.info(f"Imported hardware wallet: {address}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing hardware wallet: {e}")
            return False
            
    async def get_balance(self, address: Optional[str] = None) -> Optional[Wei]:
        """Get wallet balance.
        
        Args:
            address: Optional wallet address, uses current if None
            
        Returns:
            Balance in Wei or None if error
        """
        try:
            if not address and self.account:
                address = self.account.address
                
            if not address:
                raise ValueError("No wallet address specified")
                
            if not self.blockchain:
                self.logger.error("Blockchain connector not initialized")
                return None
                
            balance = await self.blockchain.get_balance(address)
            
            # Update stored balance
            if address in self.active_wallets:
                self.active_wallets[address]["balance"] = balance
            elif address in self.hardware_wallets:
                self.hardware_wallets[address]["balance"] = balance
                
            return balance
            
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return None
            
    async def create_transaction(self, to_address: str, amount: float, gas_price: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Create a new transaction.
        
        Args:
            to_address: Destination address
            amount: Amount in ETH to send
            gas_price: Optional gas price in wei
            
        Returns:
            Transaction dictionary or None if error
        """
        try:
            if not self.account:
                self.logger.error("No wallet unlocked")
                return None
                
            if not self.blockchain:
                self.logger.error("Blockchain connector not initialized")
                return None
            
            # Get nonce for this account 
            # Use the ethereum module's method instead of directly accessing web3
            if not self.blockchain.eth:
                self.logger.error("Ethereum module not initialized")
                return None
                
            nonce = await self.blockchain.eth.get_transaction_count(self.account.address)
            
            # Get gas price if not provided
            if not gas_price and self.blockchain.eth:
                gas_price = await self.blockchain.eth.gas_price
            
            transaction = {
                'nonce': nonce,
                'to': Web3.to_checksum_address(to_address),
                'value': Web3.to_wei(amount, 'ether'),
                'gas': 21000,  # Standard gas limit for simple ETH transfer
                'gasPrice': gas_price or 20000000000,  # Default if we couldn't get it
                'chainId': self.blockchain.config.chain_id
            }
            
            return transaction
        except Exception as e:
            self.logger.error(f"Error creating transaction: {e}")
            return None
            
    async def send_transaction(self, from_address: str, to_address: str, amount: float) -> Optional[str]:
        """Send a transaction from one address to another.
        
        Args:
            from_address: Source address
            to_address: Destination address
            amount: Amount in ETH to send
            
        Returns:
            Transaction hash as hex string or None if error
        """
        try:
            if not self.account:
                self.logger.error("No wallet unlocked")
                return None
                
            if not self.blockchain:
                self.logger.error("Blockchain connector not initialized")
                return None
                
            # Convert to Wei
            amount_wei = Web3.to_wei(amount, 'ether')
            
            # Use the blockchain connector's send_transaction method
            tx_hash = await self.blockchain.send_transaction(
                from_address=from_address,
                to_address=to_address,
                value=amount_wei
            )
            
            # Update transaction history
            if self.account.address in self.active_wallets:
                self.active_wallets[self.account.address]["transactions"].append({
                    "hash": tx_hash,
                    "from": from_address,
                    "to": to_address,
                    "value": amount,
                    "timestamp": datetime.now().timestamp()
                })
            
            self.logger.info(f"Transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            self.logger.error(f"Error sending transaction: {e}")
            return None
            
    async def sign_message(self, message: str) -> Optional[HexStr]:
        """Sign message with current wallet.
        
        Args:
            message: Message to sign
            
        Returns:
            Signature or None if error
        """
        try:
            if not self.account:
                raise ValueError("No wallet loaded")
                
            # Sign message
            signature = self.account.sign_message(
                encode_defunct(text=message)
            )
            
            return HexStr(signature.signature.hex())
            
        except Exception as e:
            self.logger.error(f"Error signing message: {e}")
            return None
            
    async def verify_signature(
        self,
        message: str,
        signature: HexStr,
        address: Optional[str] = None
    ) -> bool:
        """Verify message signature.
        
        Args:
            message: Original message
            signature: Message signature
            address: Optional signer address
            
        Returns:
            True if signature is valid
        """
        try:
            # Recover signer address
            recovered_address = Account.recover_message(
                encode_defunct(text=message),
                signature=signature
            )
            
            # Verify against provided address
            if address:
                return recovered_address.lower() == address.lower()
                
            # Verify against current wallet
            if self.account:
                return recovered_address.lower() == self.account.address.lower()
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error verifying signature: {e}")
            return False
            
    async def backup_wallet(self, backup_path: Optional[Path] = None) -> bool:
        """Backup current wallet.
        
        Args:
            backup_path: Optional backup directory path
            
        Returns:
            True if backed up successfully
        """
        try:
            if not self.account:
                raise ValueError("No wallet loaded")
                
            # Use default backup path if none provided
            if not backup_path:
                backup_path = Path("backups/wallets")
                
            # Create backup directory
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Get wallet data
            address = self.account.address
            wallet_data = self.active_wallets.get(address, {})
            
            # Create backup file
            backup_file = backup_path / f"{address}_{int(time.time())}.json"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump({
                    "address": address,
                    "keystore": wallet_data.get("keystore"),
                    "name": wallet_data.get("name"),
                    "balance": str(wallet_data.get("balance", 0)),
                    "transactions": wallet_data.get("transactions", [])
                }, f, indent=2)
                
            self.logger.info(f"Backed up wallet to: {backup_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error backing up wallet: {e}")
            return False
            
    async def list_wallets(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """List all wallets.
        
        Returns:
            Tuple of (active wallets, hardware wallets)
        """
        try:
            # Update balances
            for address in self.active_wallets:
                if self.blockchain:
                    self.active_wallets[address]["balance"] = await self.get_balance(address)
                
            for address in self.hardware_wallets:
                if self.blockchain:
                    self.hardware_wallets[address]["balance"] = await self.get_balance(address)
                
            # Convert to list format
            active = [
                {
                    "address": addr,
                    "name": data.get("name", ""),
                    "balance": str(data["balance"]),
                    "transactions": len(data.get("transactions", []))
                }
                for addr, data in self.active_wallets.items()
            ]
            
            hardware = [
                {
                    "address": addr,
                    "name": data.get("name", ""),
                    "balance": str(data["balance"]),
                    "transactions": len(data.get("transactions", []))
                }
                for addr, data in self.hardware_wallets.items()
            ]
            
            return active, hardware
            
        except Exception as e:
            self.logger.error(f"Error listing wallets: {e}")
            return [], []
            
    async def close(self) -> None:
        """Close wallet system."""
        try:
            # Backup all wallets
            for address in self.active_wallets:
                if self.account and self.account.address == address:
                    await self.backup_wallet()
                    
            # Clear sensitive data
            self.account = None
            self.active_wallets.clear()
            self.hardware_wallets.clear()
            self.fernet = None
            
            self.logger.info("Wallet system closed")
            
        except Exception as e:
            self.logger.error(f"Error closing wallet system: {e}")
            
    def subscribe_to_events(self):
        """Subscribe to events from the event bus"""
        if self.event_bus:
            # Use the synchronous subscription to avoid coroutine warnings
            if hasattr(self.event_bus, 'subscribe_sync'):
                self.event_bus.subscribe_sync('wallet.request.balance', self.get_balance)
                self.event_bus.subscribe_sync('wallet.request.create', self.create_wallet)
                self.event_bus.subscribe_sync('system.shutdown', self.cleanup)
            else:
                # Fallback to async, but log a warning
                self.logger.warning("EventBus missing subscribe_sync method, using async version without await")
                self.event_bus.subscribe_sync('wallet.request.balance', self.get_balance)
                self.event_bus.subscribe_sync('wallet.request.create', self.create_wallet)
                self.event_bus.subscribe_sync('system.shutdown', self.cleanup)
                
    def transfer_funds(self, event_data=None):
        """Transfer funds between wallets or to external address
        
        Args:
            event_data: Event data containing transfer details
        """
        if not event_data:
            self.logger.error("No transfer data provided")
            return False
            
        try:
            from_address = event_data.get('from_address')
            to_address = event_data.get('to_address')
            amount = event_data.get('amount')
            
            if not all([from_address, to_address, amount]):
                self.logger.error("Missing required transfer parameters")
                return False
                
            self.logger.info(f"Transferring {amount} from {from_address} to {to_address}")
            # Implement actual transfer logic here
            
            # Publish success event
            if self.event_bus:
                self.event_bus.publish('wallet.transfer.success', {
                    'from_address': from_address,
                    'to_address': to_address,
                    'amount': amount,
                    'timestamp': datetime.now().isoformat()
                })
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error transferring funds: {e}")
            
            # Publish error event
            if self.event_bus:
                self.event_bus.publish('wallet.transfer.error', {
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
                
            return False


# Add alias for compatibility
WalletSystem = Wallet
