import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("KingdomAI.CoinFamilyClassifier")

# Wallet family identifiers
FAMILY_EVM_SHARED_KEY = "evm_shared_key"
FAMILY_BIP44_HD_BTCLIKE = "bip44_hd_btclike"
FAMILY_CRYPTONOTE = "cryptonote"
FAMILY_BTC_LIKE_CUSTOM = "btc_like_custom"
FAMILY_CUSTOM_CHAIN = "custom_chain_wallet"

# Symbols we can safely map to BIP44-style BTC-like HD wallets
BIP44_HD_BTCLIKE_SYMBOLS = {
    "BTC",
    "BCH",
    "BSV",
    "LTC",
    "DOGE",
    "DASH",
    "ZEC",
}

# CryptoNote / RandomX family symbols (Monero and forks)
CRYPTONOTE_SYMBOLS = {
    "XMR",
    "XHV",
    "WOW",
    "SUMO",
    "TUBE",
    "MSR",
    "ARQ",
    "DERO",
    "XEQ",
    "LOKI",
    "TRTL",
    "XTA",
    "XLA",
    "CCX",
    "XMV",
    "RYO",
    "AEON",
    "KRB",
    "XDN",
    "BCN",
    "QRL",
    "ETN",
    "XUN",
    "BBR",
    "IRL",
    "GRFT",
}

CRYPTONOTE_ALGO_KEYWORDS = (
    "cryptonight",
    "randomx",
    "randomwow",
    "randomarq",
    "astrobwt",
    "argon2id chukwa",
    "panthera",
    "wild keccak",
)

BTC_LIKE_ALGO_KEYWORDS = (
    "sha-256",
    "scrypt",
    "equihash",
    "groestl",
    "mtp",
    "verthash",
    "cuckoo",
    "cuckatoo",
    "cuckaroo",
    "zhash",
)


def classify_coin(symbol: str, algorithm: str) -> str:
    """Classify a PoW coin into a wallet family based on symbol and algorithm.

    This does not guarantee full wallet support; it is an advisory mapping
    used by higher-level components to decide how to derive addresses or
    which external wallet integrations are required.
    """
    sym = (symbol or "").upper()
    alg = (algorithm or "").lower()

    # EVM-style PoW: share ETH-style key/address (Ethash/Etchash/Ubqhash)
    if "ethash" in alg or "etchash" in alg or "ubqhash" in alg:
        return FAMILY_EVM_SHARED_KEY

    # Coins we know are supported by the HD BIP44 engine
    if sym in BIP44_HD_BTCLIKE_SYMBOLS:
        return FAMILY_BIP44_HD_BTCLIKE

    # CryptoNote / RandomX-style coins
    if sym in CRYPTONOTE_SYMBOLS or any(k in alg for k in CRYPTONOTE_ALGO_KEYWORDS):
        return FAMILY_CRYPTONOTE

    # UTXO BTC-like coins with custom algorithms
    if any(k in alg for k in BTC_LIKE_ALGO_KEYWORDS):
        return FAMILY_BTC_LIKE_CUSTOM

    # Fallback: treated as custom chain with its own wallet requirements
    return FAMILY_CUSTOM_CHAIN


def build_pow_families(
    pow_config_path: Path,
    output_path: Optional[Path] = None,
) -> Dict[str, str]:
    """Build mapping of PoW symbols -> wallet family.

    Args:
        pow_config_path: Path to pow_blockchains.json
        output_path: Optional path where the mapping should be written
                     as JSON (symbol -> family).
    """
    families: Dict[str, str] = {}

    try:
        with open(pow_config_path, "r", encoding="utf-8-sig") as f:
            data: Dict[str, Any] = json.load(f)
    except Exception as e:
        logger.error("Failed to read pow_blockchains config: %s", e)
        return families

    for bc in data.get("pow_blockchains", []):
        try:
            sym = str(bc.get("symbol", "")).upper()
            alg = str(bc.get("algorithm", ""))
            if not sym:
                continue
            families[sym] = classify_coin(sym, alg)
        except Exception as e:
            logger.error("Error classifying coin entry %s: %s", bc, e)

    if output_path is not None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"families": families}, f, indent=2, sort_keys=True)
        except Exception as e:
            logger.error("Failed to write pow wallet family index: %s", e)

    return families
