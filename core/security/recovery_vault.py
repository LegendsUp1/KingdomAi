"""BIP-39 seed + portable encrypted backup for Kingdom AI.

This module is additive -- it does not replace ``core.security.secrets_vault``;
it sits alongside it and provides the pieces the consumer recovery flow needs:

    * generate / validate BIP-39 mnemonics (12 or 24 words).
    * derive an AES-256 key from (passphrase, seed, iterations).
    * export a portable encrypted backup blob (AES-GCM + HMAC) that can be
      chunked into several QR codes.
    * import the blob back on the same or a different device.

The iteration count is read from ``config/version.json`` via
``core.version_info.pbkdf2_iters`` (default 600k, tunable up to 1M+).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets as _pysecrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    HAS_CRYPTO = True
except Exception:  # pragma: no cover
    HAS_CRYPTO = False

try:
    from core.version_info import pbkdf2_iters as _pbkdf2_iters
except Exception:
    def _pbkdf2_iters() -> int:  # pragma: no cover
        return 600_000

_LOG = logging.getLogger(__name__)

PROTOCOL_VERSION = 1

_WORDLIST_CACHE: Optional[List[str]] = None


def _load_wordlist() -> List[str]:
    global _WORDLIST_CACHE
    if _WORDLIST_CACHE is not None:
        return _WORDLIST_CACHE
    here = Path(__file__).resolve().parent
    for candidate in (
        here / "bip39_english.txt",
        here.parents[1] / "data" / "bip39_english.txt",
    ):
        if candidate.exists():
            words = [w.strip() for w in candidate.read_text(encoding="utf-8").splitlines() if w.strip()]
            if len(words) == 2048:
                _WORDLIST_CACHE = words
                return words
    try:
        from mnemonic import Mnemonic  # type: ignore
        _WORDLIST_CACHE = Mnemonic("english").wordlist
        return _WORDLIST_CACHE
    except Exception:
        raise RuntimeError(
            "BIP-39 wordlist unavailable. Install `mnemonic` (pip install mnemonic) "
            "or drop a 2048-word english wordlist at core/security/bip39_english.txt."
        )


def generate_recovery_seed(strength_bits: int = 256) -> str:
    """Return a new BIP-39 mnemonic. 256 bits -> 24 words; 128 bits -> 12 words."""
    if strength_bits not in (128, 160, 192, 224, 256):
        raise ValueError("strength_bits must be one of 128,160,192,224,256")
    try:
        from mnemonic import Mnemonic  # type: ignore
        return Mnemonic("english").generate(strength=strength_bits)
    except Exception:
        entropy = _pysecrets.token_bytes(strength_bits // 8)
        return _entropy_to_mnemonic(entropy)


def _entropy_to_mnemonic(entropy: bytes) -> str:
    wordlist = _load_wordlist()
    checksum_len = len(entropy) * 8 // 32
    h = hashlib.sha256(entropy).digest()
    bits = "".join(f"{b:08b}" for b in entropy) + "".join(f"{b:08b}" for b in h)[:checksum_len]
    words = [wordlist[int(bits[i:i + 11], 2)] for i in range(0, len(bits), 11)]
    return " ".join(words)


def validate_mnemonic(mnemonic: str) -> bool:
    words = mnemonic.strip().lower().split()
    if len(words) not in (12, 15, 18, 21, 24):
        return False
    try:
        wordlist = _load_wordlist()
    except RuntimeError:
        return False
    try:
        indices = [wordlist.index(w) for w in words]
    except ValueError:
        return False
    bits = "".join(f"{i:011b}" for i in indices)
    entropy_len = len(bits) * 32 // 33
    entropy_bits, checksum_bits = bits[:entropy_len], bits[entropy_len:]
    entropy = bytes(int(entropy_bits[i:i + 8], 2) for i in range(0, entropy_len, 8))
    digest = hashlib.sha256(entropy).digest()
    expected = "".join(f"{b:08b}" for b in digest)[: len(checksum_bits)]
    return checksum_bits == expected


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    salt = ("mnemonic" + (passphrase or "")).encode("utf-8")
    return hashlib.pbkdf2_hmac(
        "sha512", mnemonic.strip().encode("utf-8"), salt, 2048, 64
    )


def derive_master_key(
    passphrase: str,
    mnemonic: str,
    *,
    salt: Optional[bytes] = None,
    iterations: Optional[int] = None,
) -> Tuple[bytes, bytes, int]:
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography package is required")
    if salt is None:
        salt = _pysecrets.token_bytes(16)
    if iterations is None:
        iterations = _pbkdf2_iters()
    seed = mnemonic_to_seed(mnemonic, passphrase)
    material = passphrase.encode("utf-8") + b"\x00" + seed
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    key = kdf.derive(material)
    return key, salt, iterations


@dataclass
class BackupBundle:
    blob_json: str
    chunks: List[str] = field(default_factory=list)

    def write(self, path: str | os.PathLike) -> None:
        Path(path).write_text(self.blob_json, encoding="utf-8")


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def export_encrypted_backup(
    payload: Dict,
    *,
    passphrase: str,
    mnemonic: str,
    hints: Optional[Dict[str, str]] = None,
    chunk_size: int = 800,
) -> BackupBundle:
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography package is required")
    plain = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    key, salt, iters = derive_master_key(passphrase, mnemonic)
    nonce = _pysecrets.token_bytes(12)
    aes = AESGCM(key)
    ct = aes.encrypt(nonce, plain, associated_data=b"kingdom-ai-backup-v1")
    mac = hmac.new(key, salt + nonce + ct, hashlib.sha256).digest()
    blob = {
        "protocol": PROTOCOL_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pbkdf2_iters": iters,
        "salt_b64": _b64e(salt),
        "nonce_b64": _b64e(nonce),
        "ct_b64": _b64e(ct),
        "hmac_b64": _b64e(mac),
        "hints": dict(hints or {}),
    }
    blob_json = json.dumps(blob, separators=(",", ":"))
    chunks: List[str] = []
    if chunk_size > 0:
        b64 = base64.urlsafe_b64encode(blob_json.encode("utf-8")).decode("ascii")
        total = (len(b64) + chunk_size - 1) // chunk_size
        for i in range(total):
            part = b64[i * chunk_size : (i + 1) * chunk_size]
            chunks.append(f"KAI1:{i + 1}/{total}:{part}")
    try:
        del key
    except Exception:
        pass
    return BackupBundle(blob_json=blob_json, chunks=chunks)


def import_encrypted_backup(
    blob_json: str,
    *,
    passphrase: str,
    mnemonic: str,
) -> Dict:
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography package is required")
    blob = json.loads(blob_json)
    if int(blob.get("protocol", 0)) != PROTOCOL_VERSION:
        raise ValueError(
            f"Unsupported backup protocol {blob.get('protocol')!r}; expected {PROTOCOL_VERSION}"
        )
    salt = _b64d(blob["salt_b64"])
    nonce = _b64d(blob["nonce_b64"])
    ct = _b64d(blob["ct_b64"])
    mac = _b64d(blob["hmac_b64"])
    iters = int(blob.get("pbkdf2_iters", _pbkdf2_iters()))
    key, _, _ = derive_master_key(passphrase, mnemonic, salt=salt, iterations=iters)
    expected = hmac.new(key, salt + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("backup HMAC mismatch -- wrong passphrase or tampered file")
    aes = AESGCM(key)
    plain = aes.decrypt(nonce, ct, associated_data=b"kingdom-ai-backup-v1")
    return json.loads(plain.decode("utf-8"))


def reassemble_chunks(chunks: Iterable[str]) -> str:
    parts: Dict[int, str] = {}
    total = None
    for chunk in chunks:
        if not chunk.startswith("KAI1:"):
            raise ValueError("not a Kingdom AI backup chunk")
        _, idxtotal, data = chunk.split(":", 2)
        idx_s, total_s = idxtotal.split("/", 1)
        idx = int(idx_s)
        new_total = int(total_s)
        if total is None:
            total = new_total
        elif total != new_total:
            raise ValueError("chunks disagree on total count")
        parts[idx] = data
    if total is None or len(parts) != total:
        raise ValueError(f"missing chunks: have {len(parts)} / {total}")
    combined = "".join(parts[i + 1] for i in range(total))
    return base64.urlsafe_b64decode(combined.encode("ascii")).decode("utf-8")


__all__ = [
    "PROTOCOL_VERSION",
    "generate_recovery_seed",
    "validate_mnemonic",
    "mnemonic_to_seed",
    "derive_master_key",
    "export_encrypted_backup",
    "import_encrypted_backup",
    "reassemble_chunks",
    "BackupBundle",
]
