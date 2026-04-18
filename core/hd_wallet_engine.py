import logging
from typing import Dict, Any, List
import hashlib

# ---------------------------------------------------------------------------
# RIPEMD160 Fix for HD Wallet Derivation (Python 3.10+)
# ---------------------------------------------------------------------------
# Python 3.10+ removed ripemd160 from hashlib for security reasons.
# HD wallet libraries need it for address derivation. We patch hashlib.new
# to enable ripemd160 via OpenSSL with usedforsecurity=False, with pure Python fallback.

# Pure Python RIPEMD-160 implementation (fallback when OpenSSL doesn't support it)
class _PureRIPEMD160:
    """Pure Python RIPEMD-160 implementation for systems without OpenSSL support."""
    block_size = 64
    digest_size = 20
    name = 'ripemd160'
    
    def __init__(self, data=b''):
        self._h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
        self._buffer = b''
        self._count = 0
        if data:
            self.update(data)
    
    def _rotl(self, x, n):
        return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF
    
    def _f(self, j, x, y, z):
        if j < 16: return x ^ y ^ z
        elif j < 32: return (x & y) | (~x & z)
        elif j < 48: return (x | ~y) ^ z
        elif j < 64: return (x & z) | (y & ~z)
        else: return x ^ (y | ~z)
    
    def _process_block(self, block):
        K = [0x00000000, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E]
        KK = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0x00000000]
        r = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,
             3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,
             4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13]
        rr = [5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,
              15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,
              12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11]
        s = [11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,
             11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,
             9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6]
        ss = [8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,
              9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,
              8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11]
        
        X = [int.from_bytes(block[i*4:(i+1)*4], 'little') for i in range(16)]
        
        al, bl, cl, dl, el = self._h
        ar, br, cr, dr, er = self._h
        
        for j in range(80):
            jj = j // 16
            T = (al + self._f(j, bl, cl, dl) + X[r[j]] + K[jj]) & 0xFFFFFFFF
            T = (self._rotl(T, s[j]) + el) & 0xFFFFFFFF
            al = el; el = dl; dl = self._rotl(cl, 10); cl = bl; bl = T
            
            T = (ar + self._f(79-j, br, cr, dr) + X[rr[j]] + KK[jj]) & 0xFFFFFFFF
            T = (self._rotl(T, ss[j]) + er) & 0xFFFFFFFF
            ar = er; er = dr; dr = self._rotl(cr, 10); cr = br; br = T
        
        T = (self._h[1] + cl + dr) & 0xFFFFFFFF
        self._h[1] = (self._h[2] + dl + er) & 0xFFFFFFFF
        self._h[2] = (self._h[3] + el + ar) & 0xFFFFFFFF
        self._h[3] = (self._h[4] + al + br) & 0xFFFFFFFF
        self._h[4] = (self._h[0] + bl + cr) & 0xFFFFFFFF
        self._h[0] = T
    
    def update(self, data):
        if isinstance(data, str):
            data = data.encode()
        self._buffer += data
        self._count += len(data)
        while len(self._buffer) >= 64:
            self._process_block(self._buffer[:64])
            self._buffer = self._buffer[64:]
        return self
    
    def digest(self):
        h = self._h[:]
        buffer = self._buffer
        count = self._count
        
        buffer += b'\x80'
        if len(buffer) > 56:
            buffer += b'\x00' * (64 - len(buffer))
            temp = _PureRIPEMD160()
            temp._h = h[:]
            temp._process_block(buffer)
            h = temp._h
            buffer = b''
        
        buffer += b'\x00' * (56 - len(buffer))
        buffer += (count * 8).to_bytes(8, 'little')
        
        temp = _PureRIPEMD160()
        temp._h = h[:]
        temp._process_block(buffer)
        
        return b''.join(x.to_bytes(4, 'little') for x in temp._h)
    
    def hexdigest(self):
        return self.digest().hex()
    
    def copy(self):
        new = _PureRIPEMD160()
        new._h = self._h[:]
        new._buffer = self._buffer
        new._count = self._count
        return new

# Test if system supports ripemd160 natively
_RIPEMD160_NATIVE_SUPPORT = False
try:
    test_hash = hashlib.new('ripemd160', b'test', usedforsecurity=False)
    test_hash.hexdigest()
    _RIPEMD160_NATIVE_SUPPORT = True
except (ValueError, TypeError):
    pass

# Only patch if not already patched (test if ripemd160 already works)
_original_hashlib_new = hashlib.new
# Test if ripemd160 already works (indicating patch is already applied)
_already_patched = False
try:
    test = hashlib.new('ripemd160', b'test')
    test.hexdigest()
    _already_patched = True  # ripemd160 works, patch likely already applied
except (ValueError, TypeError, AttributeError):
    pass  # ripemd160 doesn't work, need to patch

if not _already_patched:
    def _patched_hashlib_new(name, data=b'', **kwargs):
        """Robust patched hashlib.new that enables ripemd160 with pure Python fallback."""
        if name.lower() in ('ripemd160', 'ripemd-160', 'rmd160'):
            if _RIPEMD160_NATIVE_SUPPORT:
                try:
                    return _original_hashlib_new(name, data, usedforsecurity=False, **kwargs)
                except (ValueError, TypeError):
                    return _PureRIPEMD160(data)
            else:
                return _PureRIPEMD160(data)
        try:
            return _original_hashlib_new(name, data, **kwargs)
        except ValueError:
            return _original_hashlib_new(name, data, usedforsecurity=False)
    
    hashlib.new = _patched_hashlib_new

logger = logging.getLogger("KingdomAI.HDWalletEngine")

HD_WALLET_AVAILABLE = False

try:
    from py_crypto_hd_wallet import (
        HdWalletFactory,
        HdWalletCoins,
        HdWalletSpecs,
        HdWalletDataTypes,
        HdWalletKeyTypes,
        HdWalletChanges,
    )
    HD_WALLET_AVAILABLE = True
except Exception as e:
    logger.warning("py-crypto-hd-wallet not available; HD wallet engine disabled: %s", e)
    HD_WALLET_AVAILABLE = False


def _map_symbol_to_hd_coin(symbol: str):
    """Map PoW coin symbol to HdWalletCoins enum where supported.

    Only coins with well-defined BIP44-style networks are mapped here.
    """
    if not HD_WALLET_AVAILABLE:
        return None

    s = symbol.upper()
    if s == "BTC":
        return HdWalletCoins.BITCOIN
    if s == "BCH":
        return HdWalletCoins.BITCOIN_CASH
    if s == "BSV":
        return HdWalletCoins.BITCOIN_SV
    if s == "LTC":
        return HdWalletCoins.LITECOIN
    if s == "DOGE":
        return HdWalletCoins.DOGECOIN
    if s == "DASH":
        return HdWalletCoins.DASH
    if s == "ZEC":
        return HdWalletCoins.ZCASH
    return None


def derive_pow_addresses_from_seed(
    seed_phrase: str,
    pow_blockchains: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Derive per-coin PoW deposit addresses from a BIP39 seed.

    Returns a mapping symbol -> {"address": str} for coins supported by
    py-crypto-hd-wallet / bip_utils.
    """
    results: Dict[str, Dict[str, Any]] = {}

    if not HD_WALLET_AVAILABLE:
        return results
    if not seed_phrase:
        return results

    for bc in pow_blockchains or []:
        symbol = str(bc.get("symbol", "")).upper()
        if not symbol or symbol in results:
            continue

        coin_enum = _map_symbol_to_hd_coin(symbol)
        if not coin_enum:
            continue

        try:
            factory = HdWalletFactory(coin_enum, HdWalletSpecs.BIP44)
            wallet = factory.CreateFromMnemonic("kingdom_ai_wallet", seed_phrase)
            wallet.Generate(change_idx=HdWalletChanges.CHAIN_EXT, addr_num=1)

            addresses = wallet.GetData(HdWalletDataTypes.ADDRESSES)
            if not addresses or addresses.Count() == 0:
                continue

            addr0 = addresses[0].GetKey(HdWalletKeyTypes.ADDRESS)
            if isinstance(addr0, str) and addr0:
                results[symbol] = {"address": addr0}
        except Exception as e:
            logger.error("Failed to derive HD address for %s: %s", symbol, e)

    return results
