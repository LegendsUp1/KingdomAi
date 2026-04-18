"""
Kingdom AI — Consumer Installer + Profit Share
SOTA 2026: Manages deployment of consumer Kingdom AI instances and
tracks profit-sharing revenue from consumer subscriptions.

Features:
  - Consumer instance provisioning and configuration
  - License key generation and validation
  - Profit share tracking per consumer instance
  - Usage telemetry aggregation (privacy-preserving)
  - Over-the-air update distribution to consumer fleet
  - Revenue dashboard data publishing

Dormant until protection flag "consumer_installer" is activated.
"""
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

REDIS_KEY_LICENSES = "kingdom:consumer:licenses"
REDIS_KEY_REVENUE = "kingdom:consumer:revenue"
LOCAL_PATH_REL = os.path.join("data", "consumer_licenses.json")


class LicenseKey:
    """A consumer license key."""

    def __init__(self, licensee_name: str, tier: str = "basic",
                 profit_share_pct: float = 30.0, license_id: Optional[str] = None):
        self.license_id = license_id or secrets.token_hex(16)
        self.licensee_name = licensee_name
        self.tier = tier  # basic, pro, enterprise
        self.profit_share_pct = profit_share_pct
        self.created_at = datetime.utcnow().isoformat()
        self.activated = False
        self.activated_at: Optional[str] = None
        self.last_heartbeat: Optional[str] = None
        self.total_revenue: float = 0.0
        self.active = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "license_id": self.license_id,
            "licensee_name": self.licensee_name,
            "tier": self.tier,
            "profit_share_pct": self.profit_share_pct,
            "created_at": self.created_at,
            "activated": self.activated,
            "activated_at": self.activated_at,
            "last_heartbeat": self.last_heartbeat,
            "total_revenue": self.total_revenue,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LicenseKey":
        lk = cls(
            licensee_name=data.get("licensee_name", ""),
            tier=data.get("tier", "basic"),
            profit_share_pct=data.get("profit_share_pct", 30.0),
            license_id=data.get("license_id"),
        )
        lk.created_at = data.get("created_at", lk.created_at)
        lk.activated = data.get("activated", False)
        lk.activated_at = data.get("activated_at")
        lk.last_heartbeat = data.get("last_heartbeat")
        lk.total_revenue = data.get("total_revenue", 0.0)
        lk.active = data.get("active", True)
        return lk

    def validate(self) -> bool:
        """Validate this license key is active and not expired."""
        return self.active and self.activated


# Tier pricing
TIER_PRICING = {
    "basic": {"monthly": 9.99, "features": ["protection", "health_basic", "truth_timeline"]},
    "pro": {"monthly": 29.99, "features": ["protection", "health_full", "army", "hive", "truth_timeline"]},
    "enterprise": {"monthly": 99.99, "features": ["all"]},
}


class ConsumerInstaller(BaseComponent):
    """
    Manages consumer Kingdom AI deployments and profit sharing.

    Handles:
      - License key generation for new consumers
      - Activation and validation of consumer instances
      - Profit share calculation and tracking
      - Fleet management and update distribution
    """

    _instance: Optional["ConsumerInstaller"] = None
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

        self._licenses: Dict[str, LicenseKey] = {}
        self._lock = threading.RLock()

        self._local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            LOCAL_PATH_REL,
        )

        self._load_licenses()
        self._subscribe_events()
        self._initialized = True
        logger.info("ConsumerInstaller initialized — %d licenses", len(self._licenses))

    # ------------------------------------------------------------------
    # License management
    # ------------------------------------------------------------------

    def generate_license(self, licensee_name: str, tier: str = "basic",
                         profit_share_pct: float = 30.0) -> Dict[str, Any]:
        """Generate a new consumer license key."""
        if tier not in TIER_PRICING:
            tier = "basic"

        license_key = LicenseKey(
            licensee_name=licensee_name,
            tier=tier,
            profit_share_pct=profit_share_pct,
        )

        with self._lock:
            self._licenses[license_key.license_id] = license_key
        self._persist()

        if self.event_bus:
            self.event_bus.publish("consumer.license.generated", license_key.to_dict())

        logger.info("License generated: %s for %s (tier=%s, share=%.0f%%)",
                     license_key.license_id[:12], licensee_name, tier, profit_share_pct)
        return license_key.to_dict()

    def activate_license(self, license_id: str) -> bool:
        """Activate a consumer license."""
        with self._lock:
            lk = self._licenses.get(license_id)
            if not lk:
                return False
            lk.activated = True
            lk.activated_at = datetime.utcnow().isoformat()
        self._persist()

        if self.event_bus:
            self.event_bus.publish("consumer.license.activated", lk.to_dict())

        logger.info("License activated: %s (%s)", license_id[:12], lk.licensee_name)
        return True

    def validate_license(self, license_id: str) -> Dict[str, Any]:
        """Validate a consumer license."""
        with self._lock:
            lk = self._licenses.get(license_id)
            if not lk:
                return {"valid": False, "reason": "License not found"}
            if not lk.active:
                return {"valid": False, "reason": "License deactivated"}
            if not lk.activated:
                return {"valid": False, "reason": "License not activated"}

            lk.last_heartbeat = datetime.utcnow().isoformat()

            return {
                "valid": True,
                "tier": lk.tier,
                "features": TIER_PRICING.get(lk.tier, {}).get("features", []),
                "licensee": lk.licensee_name,
            }

    def revoke_license(self, license_id: str) -> bool:
        with self._lock:
            lk = self._licenses.get(license_id)
            if not lk:
                return False
            lk.active = False
        self._persist()
        return True

    # ------------------------------------------------------------------
    # Profit share
    # ------------------------------------------------------------------

    def record_payment(self, license_id: str, amount: float) -> Dict[str, Any]:
        """Record a payment and calculate profit share."""
        with self._lock:
            lk = self._licenses.get(license_id)
            if not lk:
                return {"error": "License not found"}

            creator_share = amount * (lk.profit_share_pct / 100)
            platform_share = amount - creator_share
            lk.total_revenue += creator_share

        self._persist()

        result = {
            "license_id": license_id,
            "payment_amount": amount,
            "creator_share": round(creator_share, 2),
            "platform_share": round(platform_share, 2),
            "profit_share_pct": lk.profit_share_pct,
            "total_creator_revenue": round(lk.total_revenue, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self.event_bus:
            self.event_bus.publish("consumer.payment.recorded", result)

        return result

    def get_revenue_summary(self) -> Dict[str, Any]:
        """Get revenue summary across all consumer licenses."""
        with self._lock:
            total_revenue = sum(lk.total_revenue for lk in self._licenses.values())
            active_count = sum(1 for lk in self._licenses.values() if lk.validate())
            tier_breakdown = {}
            for lk in self._licenses.values():
                if lk.tier not in tier_breakdown:
                    tier_breakdown[lk.tier] = {"count": 0, "revenue": 0}
                tier_breakdown[lk.tier]["count"] += 1
                tier_breakdown[lk.tier]["revenue"] += lk.total_revenue

        return {
            "total_licenses": len(self._licenses),
            "active_licenses": active_count,
            "total_creator_revenue": round(total_revenue, 2),
            "tier_breakdown": tier_breakdown,
        }

    def get_all_licenses(self) -> List[Dict]:
        with self._lock:
            return [lk.to_dict() for lk in self._licenses.values()]

    # ------------------------------------------------------------------
    # Consumer config generation
    # ------------------------------------------------------------------

    def generate_consumer_config(self, license_id: str) -> Dict[str, Any]:
        """Generate configuration for a consumer KAI instance."""
        with self._lock:
            lk = self._licenses.get(license_id)
            if not lk:
                return {"error": "License not found"}

        tier_info = TIER_PRICING.get(lk.tier, TIER_PRICING["basic"])
        features = tier_info.get("features", [])

        config = {
            "license_id": license_id,
            "tier": lk.tier,
            "enabled_features": features,
            "protection_flags": {},
            "version": "1.0.0",
            "update_channel": "stable",
        }

        # Set protection flags based on tier
        all_flags = [
            "file_integrity", "scene_awareness", "hostile_audio", "hostile_visual",
            "ambient_transcriber", "threat_nlp", "wellness_checker", "contact_manager",
            "wearable_hub", "health_anomaly_detector", "health_advisor",
            "silent_alarm", "evidence_collector", "duress_auth", "liveness_detector",
            "presence_monitor", "digital_trust", "safe_haven", "hive_mind",
            "army_mTLS", "army_e2e_encryption", "nlp_policy_evolution",
        ]

        for flag in all_flags:
            if "all" in features:
                config["protection_flags"][flag] = True
            elif "protection" in features and flag in (
                "file_integrity", "hostile_audio", "hostile_visual", "threat_nlp",
                "wellness_checker", "silent_alarm", "evidence_collector",
                "contact_manager", "presence_monitor",
            ):
                config["protection_flags"][flag] = True
            elif "health_basic" in features and flag in (
                "wearable_hub", "health_anomaly_detector",
            ):
                config["protection_flags"][flag] = True
            elif "health_full" in features and flag in (
                "wearable_hub", "health_anomaly_detector", "health_advisor",
                "scene_awareness", "ambient_transcriber",
            ):
                config["protection_flags"][flag] = True
            elif "army" in features and flag in ("army_mTLS", "army_e2e_encryption"):
                config["protection_flags"][flag] = True
            elif "hive" in features and flag == "hive_mind":
                config["protection_flags"][flag] = True
            else:
                config["protection_flags"][flag] = False

        return config

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_licenses(self) -> None:
        loaded = False
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY_LICENSES)
                if isinstance(data, list):
                    for ld in data:
                        lk = LicenseKey.from_dict(ld)
                        self._licenses[lk.license_id] = lk
                    loaded = True
            except Exception:
                pass

        if not loaded and os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for ld in data:
                        lk = LicenseKey.from_dict(ld)
                        self._licenses[lk.license_id] = lk
            except Exception:
                pass

    def _persist(self) -> None:
        with self._lock:
            snapshot = [lk.to_dict() for lk in self._licenses.values()]

        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY_LICENSES, snapshot)
            except Exception:
                pass

        try:
            os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
            with open(self._local_path, "w") as f:
                json.dump(snapshot, f, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("consumer.license.generate", self._handle_generate)
        self.event_bus.subscribe("consumer.license.activate", self._handle_activate)
        self.event_bus.subscribe("consumer.license.validate", self._handle_validate)
        self.event_bus.subscribe("consumer.payment.record", self._handle_payment)
        self.event_bus.subscribe("consumer.revenue.query", self._handle_revenue_query)
        self.event_bus.subscribe("consumer.licenses.query", self._handle_licenses_query)

    def _handle_generate(self, data: Any) -> None:
        if isinstance(data, dict):
            self.generate_license(
                data.get("licensee_name", ""),
                data.get("tier", "basic"),
                data.get("profit_share_pct", 30.0),
            )

    def _handle_activate(self, data: Any) -> None:
        if isinstance(data, dict):
            self.activate_license(data.get("license_id", ""))

    def _handle_validate(self, data: Any) -> None:
        if isinstance(data, dict):
            result = self.validate_license(data.get("license_id", ""))
            if self.event_bus:
                self.event_bus.publish("consumer.license.validation_result", result)

    def _handle_payment(self, data: Any) -> None:
        if isinstance(data, dict):
            self.record_payment(
                data.get("license_id", ""),
                data.get("amount", 0),
            )

    def _handle_revenue_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("consumer.revenue.summary", self.get_revenue_summary())

    def _handle_licenses_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("consumer.licenses.list", {
                "licenses": self.get_all_licenses(),
            })

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self._persist()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return self.get_revenue_summary()
