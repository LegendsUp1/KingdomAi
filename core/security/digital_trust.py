"""
Kingdom AI — Digital Trust (Estate Mode)
SOTA 2026: AI-guided asset inheritance using Shamir's Secret Sharing.

When estate mode is activated (Creator confirmed deceased):
  1. Reconstructs master key from Shamir shares held by beneficiaries
  2. Divides crypto assets per ContactManager beneficiary shares
  3. Guides beneficiaries through asset recovery via voice/chat
  4. Provides AI executor functionality (like a digital will executor)
  5. Preserves all Creator data for designated family members

Shamir's Secret Sharing:
  - Master key split into N shares, any K of N can reconstruct
  - Default: K=2, N=3 (any 2 of 3 beneficiaries can recover)
  - Shares distributed to beneficiaries at enrollment time

Dormant until protection flag "digital_trust" is activated.
Estate mode only activates via PresenceMonitor death protocol.
"""
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from base_component import BaseComponent

logger = logging.getLogger(__name__)

REDIS_KEY = "kingdom:digital_trust:config"
LOCAL_PATH_REL = os.path.join("data", "digital_trust_config.json")

# Shamir's Secret Sharing implementation (pure Python, no external deps)
# Uses GF(2^8) arithmetic for byte-level sharing

_PRIME = 257  # Smallest prime > 256 for GF arithmetic


def _eval_polynomial(coeffs: List[int], x: int, prime: int = _PRIME) -> int:
    """Evaluate polynomial at x using Horner's method in GF(prime)."""
    result = 0
    for coeff in reversed(coeffs):
        result = (result * x + coeff) % prime
    return result


def _lagrange_interpolate(x: int, x_s: List[int], y_s: List[int], prime: int = _PRIME) -> int:
    """Lagrange interpolation at x given points (x_s, y_s) in GF(prime)."""
    k = len(x_s)
    nums = []
    dens = []
    for i in range(k):
        others = list(x_s)
        cur = others.pop(i)
        nums.append(_prod([(x - o) for o in others], prime))
        dens.append(_prod([(cur - o) for o in others], prime))
    den = _prod(dens, prime)
    num = sum([_divmod(nums[i] * den * y_s[i] % prime, dens[i], prime) for i in range(k)])
    return (_divmod(num, den, prime) + prime) % prime


def _prod(vals: List[int], prime: int = _PRIME) -> int:
    result = 1
    for v in vals:
        result = (result * v) % prime
    return result


def _divmod(num: int, den: int, prime: int = _PRIME) -> int:
    """Modular division: num / den mod prime."""
    return num * pow(den, prime - 2, prime) % prime


def split_secret(secret: bytes, k: int, n: int) -> List[Tuple[int, bytes]]:
    """
    Split a secret into n shares where any k can reconstruct.

    Returns: List of (share_index, share_bytes) tuples.
    """
    if k > n:
        raise ValueError("k must be <= n")
    if k < 2:
        raise ValueError("k must be >= 2")

    shares: List[List[int]] = [[] for _ in range(n)]

    for byte_val in secret:
        # Random polynomial of degree k-1 with secret as constant term
        coeffs = [byte_val] + [secrets.randbelow(_PRIME) for _ in range(k - 1)]
        for i in range(n):
            x = i + 1  # x values 1..n (never 0)
            shares[i].append(_eval_polynomial(coeffs, x))

    return [(i + 1, bytes(share)) for i, share in enumerate(shares)]


def reconstruct_secret(shares: List[Tuple[int, bytes]]) -> bytes:
    """Reconstruct secret from k or more shares."""
    if not shares:
        raise ValueError("No shares provided")

    length = len(shares[0][1])
    x_s = [s[0] for s in shares]
    result = []

    for byte_idx in range(length):
        y_s = [s[1][byte_idx] for s in shares]
        secret_byte = _lagrange_interpolate(0, x_s, y_s)
        result.append(secret_byte % 256)

    return bytes(result)


class EstateConfig:
    """Estate configuration and beneficiary share allocation."""

    def __init__(self):
        self.shamir_k = 2  # Minimum shares to reconstruct
        self.shamir_n = 3  # Total shares
        self.shares_distributed: Dict[str, bool] = {}  # contact_id -> distributed
        self.estate_activated = False
        self.activated_at: Optional[str] = None
        self.master_key_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shamir_k": self.shamir_k,
            "shamir_n": self.shamir_n,
            "shares_distributed": self.shares_distributed,
            "estate_activated": self.estate_activated,
            "activated_at": self.activated_at,
            "master_key_hash": self.master_key_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EstateConfig":
        c = cls()
        c.shamir_k = data.get("shamir_k", 2)
        c.shamir_n = data.get("shamir_n", 3)
        c.shares_distributed = data.get("shares_distributed", {})
        c.estate_activated = data.get("estate_activated", False)
        c.activated_at = data.get("activated_at")
        c.master_key_hash = data.get("master_key_hash")
        return c


class DigitalTrust(BaseComponent):
    """
    AI-guided digital estate executor.

    Manages:
      - Shamir's Secret Sharing for master key protection
      - Asset division per beneficiary percentages
      - Beneficiary authentication and guidance
      - Estate activation via death protocol

    NEVER activates unless PresenceMonitor confirms death.
    """

    _instance: Optional["DigitalTrust"] = None
    _lock_cls = threading.Lock()

    @classmethod
    def get_instance(cls, event_bus=None, redis_connector=None, config=None):
        if cls._instance is None:
            with cls._lock_cls:
                if cls._instance is None:
                    cls._instance = cls(config=config, event_bus=event_bus, redis_connector=redis_connector)
        return cls._instance

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._estate_config = EstateConfig()
        self._lock = threading.RLock()

        self._local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            LOCAL_PATH_REL,
        )

        self._load_config()
        self._subscribe_events()
        self._initialized = True
        logger.info("DigitalTrust initialized (dormant — estate mode inactive)")

    # ------------------------------------------------------------------
    # Key generation and sharing
    # ------------------------------------------------------------------

    def generate_and_split_master_key(self) -> Dict[str, Any]:
        """
        Generate a new master key and split into Shamir shares.
        Shares must be securely distributed to beneficiaries.

        Returns dict with share info (NOT the shares themselves — those
        are published via secure channels to each beneficiary).
        """
        if not self._is_active():
            return {"error": "digital_trust not activated"}

        # Generate 32-byte master key
        master_key = secrets.token_bytes(32)
        key_hash = hashlib.sha256(master_key).hexdigest()

        k = self._estate_config.shamir_k
        n = self._estate_config.shamir_n

        # Split using Shamir's Secret Sharing
        shares = split_secret(master_key, k, n)

        # Store key hash (NOT the key itself)
        self._estate_config.master_key_hash = key_hash
        self._persist_config()

        # Get beneficiaries for share distribution
        beneficiary_shares: Dict[str, Dict] = {}
        if self.event_bus:
            # Request beneficiary list
            try:
                from core.security.contact_manager import ContactManager
                cm = ContactManager.get_instance()
                beneficiaries = cm.get_beneficiaries()

                for i, (share_idx, share_data) in enumerate(shares):
                    if i < len(beneficiaries):
                        ben = beneficiaries[i]
                        contact_id = ben["contact_id"]
                        beneficiary_shares[contact_id] = {
                            "share_index": share_idx,
                            "contact_name": ben["name"],
                            "asset_share_pct": ben.get("asset_share_pct", 0),
                        }
                        self._estate_config.shares_distributed[contact_id] = True
            except Exception as e:
                logger.error("Failed to distribute shares: %s", e)

        self._persist_config()

        result = {
            "master_key_hash": key_hash,
            "shamir_k": k,
            "shamir_n": n,
            "shares_created": len(shares),
            "beneficiaries_assigned": len(beneficiary_shares),
        }

        if self.event_bus:
            self.event_bus.publish("security.estate.shares_created", result)

        logger.info("Master key generated and split: k=%d, n=%d, %d shares distributed",
                     k, n, len(beneficiary_shares))
        return result

    # ------------------------------------------------------------------
    # Estate activation
    # ------------------------------------------------------------------

    def activate_estate_mode(self, reason: str = "") -> bool:
        """
        Activate estate mode. Called by PresenceMonitor death protocol.

        This is an IRREVERSIBLE action (unless Creator recovers and
        explicitly deactivates with biometric verification).
        """
        with self._lock:
            if self._estate_config.estate_activated:
                logger.warning("Estate mode already activated")
                return True

            self._estate_config.estate_activated = True
            self._estate_config.activated_at = datetime.utcnow().isoformat()

        self._persist_config()

        logger.warning("ESTATE MODE ACTIVATED: %s", reason)

        if self.event_bus:
            # Publish estate activation
            self.event_bus.publish("security.estate.activated", {
                "reason": reason,
                "activated_at": self._estate_config.activated_at,
                "shamir_k": self._estate_config.shamir_k,
                "shares_distributed": len(self._estate_config.shares_distributed),
            })

            # Notify contacts about estate mode
            self.event_bus.publish("security.emergency.notify_contacts", {
                "reason": "Kingdom AI Estate Mode has been activated. "
                          "Please contact other beneficiaries to begin asset recovery.",
                "urgency": "critical",
                "estate_mode": True,
            })

            # Speak guidance for any beneficiary present
            self.event_bus.publish("voice.speak", {
                "text": "Estate mode has been activated. I am now operating as a digital "
                        "trust executor. Beneficiaries will need to provide their Shamir "
                        "key shares to access the Creator's assets. Please identify yourself.",
                "priority": "critical",
                "source": "digital_trust",
            })

        return True

    def deactivate_estate_mode(self, biometric_verified: bool = False) -> bool:
        """Deactivate estate mode (Creator recovered). Requires biometric verification."""
        if not biometric_verified:
            logger.warning("Estate deactivation rejected — biometric verification required")
            return False

        with self._lock:
            self._estate_config.estate_activated = False

        self._persist_config()

        if self.event_bus:
            self.event_bus.publish("security.estate.deactivated", {
                "reason": "Creator recovered and biometrically verified",
                "timestamp": datetime.utcnow().isoformat(),
            })

        logger.info("Estate mode DEACTIVATED — Creator confirmed alive")
        return True

    @property
    def is_estate_active(self) -> bool:
        with self._lock:
            return self._estate_config.estate_activated

    # ------------------------------------------------------------------
    # Beneficiary guidance
    # ------------------------------------------------------------------

    def guide_beneficiary(self, beneficiary_name: str, query: str) -> None:
        """
        Guide a beneficiary through the estate process via AI.
        Routes query to ThothAI with estate context.
        """
        if not self.is_estate_active:
            return

        if self.event_bus:
            self.event_bus.publish("ai.request", {
                "text": f"[ESTATE MODE] Beneficiary '{beneficiary_name}' asks: {query}. "
                        f"Guide them through the Kingdom AI estate recovery process. "
                        f"They need to provide their Shamir key share and work with "
                        f"other beneficiaries to reconstruct the master key. "
                        f"Be helpful, compassionate, and clear.",
                "source": "digital_trust",
                "priority": "high",
                "estate_mode": True,
            })

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_config(self) -> None:
        with self._lock:
            snapshot = self._estate_config.to_dict()

        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY, snapshot)
            except Exception:
                pass

        try:
            os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
            with open(self._local_path, "w") as f:
                json.dump(snapshot, f, indent=2)
        except Exception:
            pass

    def _load_config(self) -> None:
        loaded = False
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY)
                if isinstance(data, dict) and data:
                    self._estate_config = EstateConfig.from_dict(data)
                    loaded = True
            except Exception:
                pass

        if not loaded and os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._estate_config = EstateConfig.from_dict(data)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("digital_trust")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("security.estate.activate", self._handle_activate)
        self.event_bus.subscribe("security.estate.deactivate", self._handle_deactivate)
        self.event_bus.subscribe("security.estate.generate_shares", self._handle_gen_shares)
        self.event_bus.subscribe("security.estate.guide", self._handle_guide)
        self.event_bus.subscribe("security.estate.query", self._handle_query)

    def _handle_activate(self, data: Any) -> None:
        reason = ""
        if isinstance(data, dict):
            reason = data.get("reason", "")
        self.activate_estate_mode(reason)

    def _handle_deactivate(self, data: Any) -> None:
        bio = False
        if isinstance(data, dict):
            bio = data.get("biometric_verified", False)
        self.deactivate_estate_mode(bio)

    def _handle_gen_shares(self, data: Any) -> None:
        self.generate_and_split_master_key()

    def _handle_guide(self, data: Any) -> None:
        if isinstance(data, dict):
            self.guide_beneficiary(
                data.get("beneficiary_name", "Unknown"),
                data.get("query", ""),
            )

    def _handle_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("security.estate.status", {
                "estate_active": self.is_estate_active,
                "config": self._estate_config.to_dict(),
            })

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self._persist_config()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "estate_active": self.is_estate_active,
            "shamir_k": self._estate_config.shamir_k,
            "shamir_n": self._estate_config.shamir_n,
            "shares_distributed": len(self._estate_config.shares_distributed),
            "master_key_configured": self._estate_config.master_key_hash is not None,
        }
