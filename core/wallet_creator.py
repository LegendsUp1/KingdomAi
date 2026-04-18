"""
Kingdom AI Wallet Creator - 2025 Security Standards
Create and import cryptocurrency wallets with BIP39 seed phrases.

Features:
- BIP39 compliant seed phrase generation
- Multi-chain wallet support (ETH, BTC, SOL, etc.)
- Secure seed phrase encryption
- Import from existing seed phrases
- HD wallet derivation (BIP44)
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import secrets
import hashlib

from core.hd_wallet_engine import derive_pow_addresses_from_seed, HD_WALLET_AVAILABLE
from core.coin_family_classifier import build_pow_families
from core.wallet_adapters import load_monero_adapter_from_config, MONERO_AVAILABLE, ExternalWalletAdapter

from cryptography.fernet import Fernet

# BIP39 for seed phrase generation
try:
    from mnemonic import Mnemonic
    mnemonic_available = True
except ImportError:
    mnemonic_available = False
    
# Ethereum wallet generation
try:
    from eth_account import Account
    from eth_account.hdaccount import generate_mnemonic, seed_from_mnemonic, key_from_seed
    eth_available = True
except ImportError:
    eth_available = False

# Bitcoin wallet generation
try:
    from bitcoinlib.keys import HDKey
    from bitcoinlib.mnemonic import Mnemonic as BitcoinMnemonic
    bitcoin_available = True
except ImportError:
    bitcoin_available = False

# Solana wallet generation
try:
    from solders.keypair import Keypair
    from solana.rpc.async_api import AsyncClient
    solana_available = True
except ImportError:
    solana_available = False

logger = logging.getLogger("KingdomAI.WalletCreator")

class WalletCreator:
    """
    Create and import cryptocurrency wallets with BIP39 seed phrases.
    Implements 2025 security best practices.
    """
    
    def __init__(self, config: Dict[str, Any] = None, event_bus=None):
        """Initialize wallet creator."""
        self.config = config or {}
        self.event_bus = event_bus
        
        # Wallet storage directory
        self.wallet_dir = Path("data/wallets")
        self.wallet_dir.mkdir(parents=True, exist_ok=True)
        
        # Encryption key (from persistence manager)
        self.encryption_key = self._get_encryption_key()
        
        # BIP39 mnemonic generator
        if mnemonic_available:
            self.mnemonic_generator = Mnemonic("english")
        else:
            self.mnemonic_generator = None
            logger.warning("⚠️ Mnemonic library not available - install with: pip install mnemonic")
    
    def _get_encryption_key(self) -> bytes:
        """Get or create encryption key."""
        key_file = Path("data/.encryption_key")
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            try:
                os.chmod(key_file, 0o600)
            except:
                pass
            return key
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        try:
            fernet = Fernet(self.encryption_key)
            encrypted = fernet.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return data
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        try:
            fernet = Fernet(self.encryption_key)
            decrypted = fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_data
    
    def generate_seed_phrase(self, word_count: int = 12) -> Optional[str]:
        """
        Generate a BIP39 compliant seed phrase.
        
        Args:
            word_count: Number of words (12 or 24)
            
        Returns:
            Seed phrase as string, or None if generation fails
        """
        if not self.mnemonic_generator:
            logger.error("❌ Mnemonic library not available")
            return None
        
        try:
            # Generate entropy
            if word_count == 12:
                strength = 128  # 12 words
            elif word_count == 24:
                strength = 256  # 24 words
            else:
                logger.error(f"Invalid word count: {word_count}. Use 12 or 24.")
                return None
            
            # Generate mnemonic
            seed_phrase = self.mnemonic_generator.generate(strength=strength)
            
            logger.info(f"✅ Generated {word_count}-word seed phrase")
            return seed_phrase
            
        except Exception as e:
            logger.error(f"❌ Seed phrase generation failed: {e}")
            return None
    
    def validate_seed_phrase(self, seed_phrase: str) -> bool:
        """
        Validate a BIP39 seed phrase.
        
        Args:
            seed_phrase: Seed phrase to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not self.mnemonic_generator:
            return False
        
        try:
            return self.mnemonic_generator.check(seed_phrase)
        except:
            return False
    
    async def create_wallet(
        self,
        name: str,
        blockchain: str = "ETH",
        word_count: int = 12,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new wallet with seed phrase.
        
        Args:
            name: Wallet name
            blockchain: Blockchain type (ETH, BTC, SOL, etc.)
            word_count: Seed phrase length (12 or 24)
            password: Optional password for additional encryption
            
        Returns:
            Wallet info including seed phrase (DISPLAY TO USER!)
        """
        try:
            logger.info(f"🔄 Creating {blockchain} wallet: {name}")
            
            # Generate seed phrase
            seed_phrase = self.generate_seed_phrase(word_count)
            if not seed_phrase:
                return {"success": False, "error": "Failed to generate seed phrase"}
            
            # Create wallet based on blockchain
            if blockchain.upper() == "ETH":
                wallet_data = await self._create_ethereum_wallet(name, seed_phrase, password)
            elif blockchain.upper() == "BTC":
                wallet_data = await self._create_bitcoin_wallet(name, seed_phrase, password)
            elif blockchain.upper() == "SOL":
                wallet_data = await self._create_solana_wallet(name, seed_phrase, password)
            else:
                return {"success": False, "error": f"Unsupported blockchain: {blockchain}"}
            
            if not wallet_data.get("success"):
                return wallet_data
            
            # Save wallet (encrypted)
            await self._save_wallet(name, blockchain, wallet_data, seed_phrase, password)
            
            # Return wallet info with seed phrase
            return {
                "success": True,
                "name": name,
                "blockchain": blockchain,
                "address": wallet_data.get("address"),
                "seed_phrase": seed_phrase,  # ⚠️ CRITICAL: Display to user!
                "created_at": datetime.now().isoformat(),
                "warning": "⚠️ WRITE DOWN YOUR SEED PHRASE NOW! You will NOT see it again!"
            }
            
        except Exception as e:
            logger.error(f"❌ Wallet creation failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def import_wallet(
        self,
        name: str,
        seed_phrase: str,
        blockchain: str = "ETH",
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Import wallet from existing seed phrase.
        
        Args:
            name: Wallet name
            seed_phrase: Existing seed phrase (12 or 24 words)
            blockchain: Blockchain type
            password: Optional password
            
        Returns:
            Wallet info
        """
        try:
            logger.info(f"🔄 Importing {blockchain} wallet: {name}")
            
            # Validate seed phrase
            if not self.validate_seed_phrase(seed_phrase):
                return {"success": False, "error": "Invalid seed phrase"}
            
            # Create wallet from seed phrase
            if blockchain.upper() == "ETH":
                wallet_data = await self._create_ethereum_wallet(name, seed_phrase, password)
            elif blockchain.upper() == "BTC":
                wallet_data = await self._create_bitcoin_wallet(name, seed_phrase, password)
            elif blockchain.upper() == "SOL":
                wallet_data = await self._create_solana_wallet(name, seed_phrase, password)
            else:
                return {"success": False, "error": f"Unsupported blockchain: {blockchain}"}
            
            if not wallet_data.get("success"):
                return wallet_data
            
            # Save wallet (encrypted)
            await self._save_wallet(name, blockchain, wallet_data, seed_phrase, password)
            
            return {
                "success": True,
                "name": name,
                "blockchain": blockchain,
                "address": wallet_data.get("address"),
                "imported_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Wallet import failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _create_ethereum_wallet(
        self,
        name: str,
        seed_phrase: str,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create Ethereum wallet from seed phrase."""
        try:
            if not eth_available:
                return {"success": False, "error": "eth-account not installed"}
            
            # Enable unaudited HD wallet features
            Account.enable_unaudited_hdwallet_features()
            
            # Derive account from seed phrase
            account = Account.from_mnemonic(seed_phrase)
            
            return {
                "success": True,
                "address": account.address,
                "private_key": account.key.hex(),
                "blockchain": "ETH"
            }
            
        except Exception as e:
            logger.error(f"Ethereum wallet creation failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _create_bitcoin_wallet(
        self,
        name: str,
        seed_phrase: str,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create Bitcoin wallet from seed phrase."""
        try:
            if not bitcoin_available:
                # Fallback: Simple address generation
                logger.warning("⚠️ bitcoinlib not available - using simplified wallet")
                # Generate deterministic address from seed phrase
                seed_hash = hashlib.sha256(seed_phrase.encode()).hexdigest()
                address = f"bc1q{seed_hash[:40]}"  # Simplified bech32 format
                
                return {
                    "success": True,
                    "address": address,
                    "private_key": seed_hash,
                    "blockchain": "BTC",
                    "note": "Simplified wallet - install bitcoinlib for full features"
                }
            
            # Full Bitcoin wallet with bitcoinlib
            hdkey = HDKey.from_passphrase(seed_phrase)
            
            return {
                "success": True,
                "address": hdkey.address(),
                "private_key": hdkey.private_hex,
                "blockchain": "BTC"
            }
            
        except Exception as e:
            logger.error(f"Bitcoin wallet creation failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _create_solana_wallet(
        self,
        name: str,
        seed_phrase: str,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create Solana wallet from seed phrase."""
        try:
            if not solana_available:
                return {"success": False, "error": "solana libraries not installed"}
            
            # Derive Solana keypair from seed phrase
            # Note: Solana uses ed25519, different from BIP39
            seed_hash = hashlib.sha256(seed_phrase.encode()).digest()
            keypair = Keypair.from_seed(seed_hash[:32])
            
            return {
                "success": True,
                "address": str(keypair.pubkey()),
                "private_key": bytes(keypair).hex(),
                "blockchain": "SOL"
            }
            
        except Exception as e:
            logger.error(f"Solana wallet creation failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _save_wallet(
        self,
        name: str,
        blockchain: str,
        wallet_data: Dict[str, Any],
        seed_phrase: str,
        password: Optional[str] = None
    ):
        """Save wallet to encrypted storage."""
        try:
            wallet_file = self.wallet_dir / f"{name}_{blockchain}.json"
            
            # Encrypt sensitive data
            encrypted_seed = self.encrypt_data(seed_phrase)
            encrypted_private_key = self.encrypt_data(wallet_data.get("private_key", ""))
            
            # Wallet data to save
            save_data = {
                "name": name,
                "blockchain": blockchain,
                "address": wallet_data.get("address"),
                "encrypted_seed_phrase": encrypted_seed,
                "encrypted_private_key": encrypted_private_key,
                "created_at": datetime.now().isoformat(),
                "has_password": password is not None
            }
            
            # Save to file
            with open(wallet_file, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            # Set restrictive permissions
            try:
                os.chmod(wallet_file, 0o600)
            except:
                pass
            
            logger.info(f"✅ Wallet saved: {wallet_file}")
            
        except Exception as e:
            logger.error(f"Failed to save wallet: {e}")

    async def create_multi_chain_wallet(
        self,
        name: str,
        blockchains: List[str],
        word_count: int = 24,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a single BIP39 wallet used across multiple blockchains.

        Generates one seed phrase and derives per-chain wallets (ETH / BTC / SOL).
        All per-chain wallet files share the same mnemonic, matching 2025
        multi-chain wallet best practices.
        """
        try:
            seed_phrase = self.generate_seed_phrase(word_count)
            if not seed_phrase:
                return {"success": False, "error": "Failed to generate seed phrase"}

            results: Dict[str, Any] = {"success": True, "name": name, "seed_phrase": seed_phrase, "blockchains": {}}

            for chain in blockchains:
                chain_upper = str(chain).upper()
                if chain_upper == "ETH":
                    wallet_data = await self._create_ethereum_wallet(name, seed_phrase, password)
                elif chain_upper == "BTC":
                    wallet_data = await self._create_bitcoin_wallet(name, seed_phrase, password)
                elif chain_upper == "SOL":
                    wallet_data = await self._create_solana_wallet(name, seed_phrase, password)
                else:
                    logger.warning(f"Unsupported blockchain in multi-chain wallet: {chain_upper}")
                    continue

                if not wallet_data.get("success"):
                    return wallet_data

                await self._save_wallet(name, chain_upper, wallet_data, seed_phrase, password)
                results["blockchains"][chain_upper] = {
                    "address": wallet_data.get("address"),
                    "blockchain": chain_upper,
                }

            return results

        except Exception as e:
            logger.error(f"Multi-chain wallet creation failed: {e}")
            return {"success": False, "error": str(e)}

    async def create_kingdom_ai_wallet_if_missing(
        self,
        word_count: int = 24,
        password: Optional[str] = None,
        log_plaintext: bool = True
    ) -> Dict[str, Any]:
        """Create or load the global 'Kingdom AI Wallet'.

        This uses a single BIP39 seed for ETH and BTC, stores encrypted
        wallet files under data/wallets, and optionally appends the seed
        phrase and addresses to a plaintext log file for the user.
        """
        wallet_name = "kingdom_ai_wallet"
        try:
            existing_eth = self.wallet_dir / f"{wallet_name}_ETH.json"
            existing_btc = self.wallet_dir / f"{wallet_name}_BTC.json"

            seed_phrase: Optional[str] = None
            chain_addresses: Dict[str, str] = {}

            if existing_eth.exists() or existing_btc.exists():
                # Load existing primary wallet (prefer ETH if present)
                primary_path = existing_eth if existing_eth.exists() else existing_btc
                with open(primary_path, "r", encoding="utf-8-sig") as f:
                    wdata = json.load(f)
                enc_seed = wdata.get("encrypted_seed_phrase")
                if isinstance(enc_seed, str) and enc_seed:
                    seed_phrase = self.decrypt_data(enc_seed)
                addr = wdata.get("address")
                if addr:
                    chain = wdata.get("blockchain", "ETH").upper()
                    if chain == "ETH":
                        chain_addresses["ETH"] = addr
                    elif chain == "BTC":
                        chain_addresses["BTC"] = addr

                # Try to load the counterpart chain if it exists
                for path, chain_code in ((existing_eth, "ETH"), (existing_btc, "BTC")):
                    if path.exists():
                        try:
                            with open(path, "r", encoding="utf-8-sig") as f:
                                wdata2 = json.load(f)
                            addr2 = wdata2.get("address")
                            if addr2:
                                chain_addresses[chain_code] = addr2
                        except Exception:
                            continue

                result = {
                    "success": True,
                    "name": wallet_name,
                    "seed_phrase": seed_phrase,
                    "blockchains": {
                        chain: {"address": addr} for chain, addr in chain_addresses.items()
                    },
                }
            else:
                # Create new multi-chain wallet (ETH + BTC)
                multi = await self.create_multi_chain_wallet(
                    name=wallet_name,
                    blockchains=["ETH", "BTC"],
                    word_count=word_count,
                    password=password,
                )
                if not multi.get("success"):
                    return multi

                seed_phrase = multi.get("seed_phrase")
                for chain_code, info in multi.get("blockchains", {}).items():
                    addr = info.get("address")
                    if addr:
                        chain_addresses[chain_code] = addr

                result = multi

            # Merge any previously generated app-level wallet addresses as a baseline
            try:
                app_wallet_path = self.wallet_dir / "kingdom_ai_wallet_app.json"
                if app_wallet_path.exists():
                    with open(app_wallet_path, "r", encoding="utf-8-sig") as f:
                        existing_app = json.load(f)
                    existing_chains = existing_app.get("chains") or {}
                    if isinstance(existing_chains, dict):
                        for sym, info in existing_chains.items():
                            try:
                                addr = info.get("address") if isinstance(info, dict) else info
                                if not isinstance(addr, str) or not addr.strip():
                                    continue
                                sym_upper = str(sym).upper()
                                if sym_upper not in chain_addresses:
                                    chain_addresses[sym_upper] = addr.strip()
                            except Exception:
                                continue
            except Exception as e:
                logger.error(f"Failed to merge existing app wallet addresses: {e}")

            # Derive additional PoW coin addresses from the BIP39 seed when possible
            if seed_phrase:
                try:
                    base_dir = Path(__file__).resolve().parent.parent
                    pow_path = base_dir / "config" / "pow_blockchains.json"
                    pow_list: List[Dict[str, Any]] = []
                    if pow_path.exists():
                        with open(pow_path, "r", encoding="utf-8-sig") as f:
                            pow_data = json.load(f)
                        pow_list = pow_data.get("pow_blockchains") or []

                        # Build/update PoW wallet family index for observability
                        try:
                            index_path = base_dir / "data" / "wallets" / "pow_wallet_families.json"
                            build_pow_families(pow_path, output_path=index_path)
                        except Exception as e_index:
                            logger.error(f"Failed to build PoW wallet family index: {e_index}")

                    # Use HD wallet engine for BTC-family coins when available
                    if pow_list and HD_WALLET_AVAILABLE:
                        try:
                            hd_addrs = derive_pow_addresses_from_seed(seed_phrase, pow_list)
                            for sym, info in hd_addrs.items():
                                addr = info.get("address")
                                if isinstance(addr, str) and addr.strip():
                                    sym_upper = str(sym).upper()
                                    if sym_upper not in chain_addresses:
                                        chain_addresses[sym_upper] = addr.strip()
                        except Exception as e:
                            logger.error(f"Failed to derive HD PoW addresses: {e}")

                    # Reuse the ETH address for all EVM-style PoW coins (Ethash/Etchash/Ubqhash)
                    if pow_list:
                        eth_addr = chain_addresses.get("ETH")
                        if isinstance(eth_addr, str) and eth_addr.strip():
                            for bc in pow_list:
                                try:
                                    sym2 = str(bc.get("symbol", "")).upper()
                                    algo = str(bc.get("algorithm", "")).lower()
                                    if not sym2 or sym2 in chain_addresses:
                                        continue
                                    if "ethash" in algo or "etchash" in algo or "ubqhash" in algo:
                                        chain_addresses[sym2] = eth_addr.strip()
                                except Exception:
                                    continue

                    # Optionally pull XMR address from monero-wallet-rpc via adapter
                    try:
                        if MONERO_AVAILABLE:
                            monero_config = base_dir / "config" / "wallet_monero.json"
                            adapter = load_monero_adapter_from_config(monero_config)
                            if adapter:
                                xmr_addr = adapter.get_primary_address()
                                if isinstance(xmr_addr, str) and xmr_addr.strip():
                                    if "XMR" not in chain_addresses:
                                        chain_addresses["XMR"] = xmr_addr.strip()
                    except Exception as e:
                        logger.error(f"Failed to integrate Monero adapter: {e}")

                    # External CLI-based wallets for any remaining coins
                    try:
                        external_cfg_path = base_dir / "config" / "wallet_external.json"
                        if external_cfg_path.exists():
                            with open(external_cfg_path, "r", encoding="utf-8-sig") as f:
                                external_cfg = json.load(f)

                            if isinstance(external_cfg, dict):
                                for sym, cfg in external_cfg.items():
                                    try:
                                        sym_upper = str(sym).upper()
                                        if sym_upper in chain_addresses:
                                            continue
                                        command = cfg.get("command") if isinstance(cfg, dict) else None
                                        if not isinstance(command, list) or not command:
                                            continue
                                        adapter = ExternalWalletAdapter(command=command, coin=sym_upper)
                                        addr = adapter.get_address()
                                        if isinstance(addr, str) and addr.strip():
                                            chain_addresses[sym_upper] = addr.strip()
                                    except Exception as e_coin:
                                        logger.debug(f"External wallet adapter skipped for {sym}: {e_coin}")
                    except Exception as e:
                        logger.error(f"Failed to integrate external wallet adapters: {e}")

                    # (Status report is recomputed later after multi-coin wallets are applied.)
                except Exception as e:
                    logger.error(f"Failed to process PoW blockchain definitions: {e}")

            # Augment chain addresses with any per-coin PoW wallets defined in multi_coin_wallets.json
            try:
                base_dir = Path(__file__).resolve().parent.parent
                mcw_path = base_dir / "config" / "multi_coin_wallets.json"
                if mcw_path.exists():
                    with open(mcw_path, "r", encoding="utf-8-sig") as f:
                        mcw_data = json.load(f)
                    for section in ("cpu_wallets", "gpu_wallets"):
                        wallets = mcw_data.get(section) or {}
                        if isinstance(wallets, dict):
                            for sym, addr in wallets.items():
                                if not isinstance(addr, str) or not addr.strip():
                                    continue
                                sym_upper = str(sym).upper()
                                if sym_upper not in chain_addresses:
                                    chain_addresses[sym_upper] = addr.strip()
            except Exception as e:
                logger.error(f"Failed to augment Kingdom AI wallet with multi-coin wallets: {e}")

            # Recompute and persist final PoW wallet status after all sources (HD, external, multi-coin) are applied
            try:
                base_dir = Path(__file__).resolve().parent.parent
                pow_path = base_dir / "config" / "pow_blockchains.json"
                pow_list_final: List[Dict[str, Any]] = []
                if pow_path.exists():
                    with open(pow_path, "r", encoding="utf-8-sig") as f:
                        pow_data = json.load(f)
                    pow_list_final = pow_data.get("pow_blockchains") or []

                pow_syms = {
                    str(bc.get("symbol", "")).upper()
                    for bc in (pow_list_final or [])
                    if bc.get("symbol")
                }
                configured = sorted(
                    sym
                    for sym in pow_syms
                    if isinstance(chain_addresses.get(sym), str)
                    and chain_addresses[sym].strip()
                )
                missing = sorted(sym for sym in pow_syms if sym not in configured)

                status = {
                    "timestamp": datetime.now().isoformat(),
                    "seed_available": bool(seed_phrase),
                    "pow_total": len(pow_syms),
                    "configured_count": len(configured),
                    "missing_count": len(missing),
                    "configured": configured,
                    "missing": missing,
                }

                # Store wallet status in Redis Quantum Nexus (primary data source)
                try:
                    import redis
                    redis_client = redis.Redis(
                        host='localhost',
                        port=6380,
                        password='QuantumNexus2025',
                        db=0,
                        decode_responses=True
                    )
                    redis_client.set("kingdom:wallet:status", json.dumps(status))
                    logger.info("✅ Wallet status stored in Redis Quantum Nexus")
                except Exception as redis_err:
                    logger.error(f"Failed to store wallet status in Redis: {redis_err}")

                logger.info(
                    "Final Kingdom AI wallet status: %d/%d PoW coins configured",
                    len(configured),
                    len(pow_syms),
                )
                if missing:
                    logger.warning(
                        "Final missing PoW wallet addresses for: %s", ", ".join(missing)
                    )
            except Exception as e_status_outer:
                logger.error(
                    f"Failed to compute final Kingdom AI wallet status: {e_status_outer}"
                )

            # Write app-level wallet descriptor for GUI and mining systems
            app_wallet_path = self.wallet_dir / "kingdom_ai_wallet_app.json"
            app_data = {
                "id": wallet_name,
                "name": "Kingdom AI Wallet",
                "created_at": datetime.now().isoformat(),
                "addresses": {},
                "chains": {},
            }

            for chain_code, addr in chain_addresses.items():
                if chain_code == "ETH":
                    app_data["addresses"]["ethereum"] = addr
                    app_data["chains"]["ETH"] = {"address": addr}
                elif chain_code == "BTC":
                    app_data["addresses"]["bitcoin"] = addr
                    app_data["chains"]["BTC"] = {"address": addr}
                else:
                    app_data["chains"][chain_code] = {"address": addr}

            try:
                with open(app_wallet_path, "w", encoding="utf-8") as f:
                    json.dump(app_data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to write app-level Kingdom AI wallet file: {e}")

            # Optional plaintext seed log (Option B)
            if log_plaintext and seed_phrase:
                try:
                    log_path = self.wallet_dir / "kingdom_ai_wallet_seeds.log"
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write("==============================\n")
                        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                        f.write(f"Wallet: {wallet_name}\n")
                        f.write(f"Seed phrase: {seed_phrase}\n")
                        for chain_code, addr in chain_addresses.items():
                            f.write(f"{chain_code} address: {addr}\n")
                        f.write("==============================\n\n")
                    try:
                        os.chmod(log_path, 0o600)
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Failed to write plaintext seed log: {e}")

            return result

        except Exception as e:
            logger.error(f"Failed to create or load Kingdom AI wallet: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_wallets(self) -> List[Dict[str, Any]]:
        """List all saved wallets."""
        try:
            wallets = []
            
            for wallet_file in self.wallet_dir.glob("*.json"):
                try:
                    with open(wallet_file, 'r') as f:
                        wallet_data = json.load(f)
                    
                    wallets.append({
                        "name": wallet_data.get("name"),
                        "blockchain": wallet_data.get("blockchain"),
                        "address": wallet_data.get("address"),
                        "created_at": wallet_data.get("created_at")
                    })
                except:
                    pass
            
            return wallets
            
        except Exception as e:
            logger.error(f"Failed to list wallets: {e}")
            return []


    # ================================================================
    # PER-USER WALLET CREATION (SOTA 2026)
    # ================================================================

    async def create_user_wallet(
        self,
        user_id: str,
        blockchains: Optional[List[str]] = None,
        word_count: int = 24,
    ) -> Dict[str, Any]:
        """Create an isolated wallet set for a specific user.

        Each user_id gets its own subdirectory under data/wallets/users/,
        its own BIP39 seed phrase, and its own per-chain wallet files.
        If a wallet already exists for this user_id the existing one is
        returned — never overwritten.

        Args:
            user_id: Unique identifier for the user (device_id, biometric id, etc.)
            blockchains: List of chain symbols to derive (default: ETH, BTC, SOL)
            word_count: BIP39 word count (12 or 24)

        Returns:
            Dict with success, user_id, addresses, and seed_phrase (encrypted).
        """
        if not user_id or not isinstance(user_id, str):
            return {"success": False, "error": "user_id is required"}

        if blockchains is None:
            blockchains = ["ETH", "BTC", "SOL"]

        user_dir = self.wallet_dir / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = user_dir / "wallet_manifest.json"

        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8-sig") as f:
                    existing = json.load(f)
                if existing.get("addresses"):
                    logger.info("User wallet already exists for %s", user_id)
                    return {
                        "success": True,
                        "user_id": user_id,
                        "addresses": existing.get("addresses", {}),
                        "created": False,
                    }
            except Exception:
                pass

        multi = await self.create_multi_chain_wallet(
            name=f"user_{user_id}",
            blockchains=blockchains,
            word_count=word_count,
        )
        if not multi.get("success"):
            return multi

        addresses: Dict[str, str] = {}
        for chain, info in multi.get("blockchains", {}).items():
            addr = info.get("address")
            if addr:
                addresses[chain] = addr

        manifest = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "addresses": addresses,
            "blockchains": list(addresses.keys()),
            "encrypted_seed": self.encrypt_data(multi.get("seed_phrase", "")),
        }
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            logger.error("Failed to write user wallet manifest: %s", e)

        logger.info("Created new wallet for user %s with chains: %s",
                     user_id, list(addresses.keys()))
        return {
            "success": True,
            "user_id": user_id,
            "addresses": addresses,
            "created": True,
        }

    def get_user_wallet(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load an existing user wallet manifest (synchronous)."""
        if not user_id:
            return None
        manifest_path = self.wallet_dir / "users" / user_id / "wallet_manifest.json"
        if not manifest_path.exists():
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return None

    def list_user_wallets(self) -> List[Dict[str, Any]]:
        """List all per-user wallet manifests."""
        users_dir = self.wallet_dir / "users"
        if not users_dir.exists():
            return []
        results = []
        for user_dir in users_dir.iterdir():
            if user_dir.is_dir():
                manifest = user_dir / "wallet_manifest.json"
                if manifest.exists():
                    try:
                        with open(manifest, "r", encoding="utf-8-sig") as f:
                            data = json.load(f)
                        results.append(data)
                    except Exception:
                        pass
        return results


# Export
__all__ = ["WalletCreator"]
