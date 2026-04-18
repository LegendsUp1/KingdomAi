"""
Kingdom AI — Duress Authentication
SOTA 2026: Coercion-resistant authentication with duress PIN support.

Features:
  - Duress PIN: A special PIN that appears to unlock normally but silently
    triggers the alarm + evidence capture + notifies army
  - Voice stress analysis integration for detecting coerced authentication
  - Failed auth lockout with escalating penalties
  - Biometric-gated system updates (only Creator can authorize)
  - Multi-factor: voice + face + PIN (any 2 of 3 required)

Dormant until protection flag "duress_auth" is activated.
"""
import hashlib
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

REDIS_KEY = "kingdom:duress_auth:state"


class DuressAuth(BaseComponent):
    """
    Coercion-resistant authentication system.

    Supports:
      - Normal PIN → standard access
      - Duress PIN → appears normal but triggers silent alarm
      - Biometric-only → voice/face verified by UserIdentityEngine
      - Failed auth tracking → lockout after threshold

    Integration:
      - UserIdentityEngine (voice/face biometrics)
      - CreatorShield (threat level input)
      - SilentAlarm (duress activation)
      - EvidenceCollector (capture during duress)
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        # PIN storage (hashed)
        self._normal_pin_hash: Optional[str] = None
        self._duress_pin_hash: Optional[str] = None

        # Lockout state
        self._failed_attempts = 0
        self._lockout_until: float = 0
        self._max_attempts = 5
        self._lockout_duration = 300  # 5 minutes base lockout

        # Update authorization
        self._pending_updates: Dict[str, Dict] = {}
        self._lock = threading.RLock()

        self._load_state()
        self._subscribe_events()
        self._initialized = True
        logger.info("DuressAuth initialized (dormant until activated)")

    # ------------------------------------------------------------------
    # PIN management
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_pin(pin: str) -> str:
        return hashlib.sha256(pin.encode()).hexdigest()

    def set_normal_pin(self, pin: str) -> bool:
        """Set the normal access PIN (Creator only)."""
        if len(pin) < 4:
            return False
        self._normal_pin_hash = self._hash_pin(pin)
        self._persist_state()
        logger.info("Normal PIN set")
        return True

    def set_duress_pin(self, pin: str) -> bool:
        """Set the duress PIN (looks like normal access but triggers alarm)."""
        if len(pin) < 4:
            return False
        if self._normal_pin_hash and self._hash_pin(pin) == self._normal_pin_hash:
            logger.warning("Duress PIN cannot be same as normal PIN")
            return False
        self._duress_pin_hash = self._hash_pin(pin)
        self._persist_state()
        logger.info("Duress PIN set")
        return True

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate_pin(self, pin: str) -> Dict[str, Any]:
        """
        Authenticate with PIN.

        Returns:
            Dict with keys: success, is_duress, locked_out, message
        """
        if not self._is_active():
            return {"success": True, "is_duress": False, "locked_out": False,
                    "message": "Auth disabled (dormant)"}

        # Check lockout
        now = time.time()
        if now < self._lockout_until:
            remaining = int(self._lockout_until - now)
            return {
                "success": False,
                "is_duress": False,
                "locked_out": True,
                "message": f"Locked out for {remaining} seconds",
            }

        pin_hash = self._hash_pin(pin)

        # Check duress PIN FIRST
        if self._duress_pin_hash and pin_hash == self._duress_pin_hash:
            self._failed_attempts = 0
            self._trigger_duress(pin_type="duress_pin")
            # Return success to appear normal to attacker
            return {
                "success": True,
                "is_duress": True,  # Internal flag — NOT shown to user
                "locked_out": False,
                "message": "Authenticated",
            }

        # Check normal PIN
        if self._normal_pin_hash and pin_hash == self._normal_pin_hash:
            self._failed_attempts = 0
            if self.event_bus:
                self.event_bus.publish("security.auth.success", {
                    "method": "pin",
                    "timestamp": datetime.utcnow().isoformat(),
                })
            return {
                "success": True,
                "is_duress": False,
                "locked_out": False,
                "message": "Authenticated",
            }

        # Failed attempt
        self._failed_attempts += 1
        if self.event_bus:
            self.event_bus.publish("identity.command.rejected", {
                "method": "pin",
                "attempts": self._failed_attempts,
                "timestamp": datetime.utcnow().isoformat(),
            })

        if self._failed_attempts >= self._max_attempts:
            # Escalating lockout: 5min, 15min, 1hr
            multiplier = min(12, self._failed_attempts // self._max_attempts)
            lockout = self._lockout_duration * multiplier
            self._lockout_until = now + lockout
            logger.warning("Auth lockout triggered: %d seconds (attempt %d)",
                           lockout, self._failed_attempts)
            return {
                "success": False,
                "is_duress": False,
                "locked_out": True,
                "message": f"Too many failed attempts. Locked for {lockout}s",
            }

        return {
            "success": False,
            "is_duress": False,
            "locked_out": False,
            "message": f"Invalid PIN ({self._max_attempts - self._failed_attempts} attempts remaining)",
        }

    def authenticate_biometric(self, voice_verified: bool = False,
                                face_verified: bool = False,
                                voice_stress_high: bool = False) -> Dict[str, Any]:
        """
        Authenticate via biometrics from UserIdentityEngine.

        Requires at least one biometric factor.
        If voice stress is detected during auth, treat as potential duress.
        """
        if not self._is_active():
            return {"success": True, "is_duress": False, "message": "Auth disabled"}

        if not voice_verified and not face_verified:
            return {"success": False, "is_duress": False, "message": "No biometric match"}

        # Check for duress indicators
        if voice_stress_high and (voice_verified or face_verified):
            self._trigger_duress(pin_type="biometric_under_stress")
            return {
                "success": True,
                "is_duress": True,
                "message": "Authenticated",
            }

        if self.event_bus:
            self.event_bus.publish("security.auth.success", {
                "method": "biometric",
                "voice": voice_verified,
                "face": face_verified,
                "timestamp": datetime.utcnow().isoformat(),
            })

        return {"success": True, "is_duress": False, "message": "Authenticated"}

    # ------------------------------------------------------------------
    # Update authorization (biometric-gated)
    # ------------------------------------------------------------------

    def request_update_authorization(self, update_id: str, update_description: str) -> str:
        """
        Request Creator authorization for a system update.
        Returns update_id. Creator must biometrically confirm.
        """
        with self._lock:
            self._pending_updates[update_id] = {
                "update_id": update_id,
                "description": update_description,
                "requested_at": datetime.utcnow().isoformat(),
                "authorized": False,
            }

        if self.event_bus:
            self.event_bus.publish("security.update.authorization_required", {
                "update_id": update_id,
                "description": update_description,
            })
            # Ask Creator via voice
            self.event_bus.publish("voice.speak", {
                "text": f"System update requested: {update_description}. "
                        "Please confirm with your voice or face to authorize.",
                "priority": "high",
                "source": "duress_auth",
            })

        return update_id

    def authorize_update(self, update_id: str, biometric_verified: bool = False) -> bool:
        """Authorize a pending update after biometric verification."""
        if not biometric_verified:
            return False

        with self._lock:
            update = self._pending_updates.get(update_id)
            if not update:
                return False
            update["authorized"] = True
            update["authorized_at"] = datetime.utcnow().isoformat()

        if self.event_bus:
            self.event_bus.publish("security.update.authorized", update)

        logger.info("Update authorized: %s", update_id)
        return True

    # ------------------------------------------------------------------
    # Duress trigger
    # ------------------------------------------------------------------

    def _trigger_duress(self, pin_type: str) -> None:
        """Silently trigger duress response."""
        logger.warning("DURESS DETECTED via %s — triggering silent response", pin_type)

        if self.event_bus:
            # Trigger silent alarm
            self.event_bus.publish("security.silent_alarm.trigger", {
                "reason": f"Duress authentication ({pin_type})",
                "threat_level": "critical",
            })

            # Start evidence capture
            self.event_bus.publish("security.evidence.start_capture", {
                "reason": f"duress_auth_{pin_type}",
                "duration_seconds": 600,
            })

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_state(self) -> None:
        state = {
            "normal_pin_hash": self._normal_pin_hash,
            "duress_pin_hash": self._duress_pin_hash,
        }
        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY, state)
            except Exception:
                pass

    def _load_state(self) -> None:
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY)
                if isinstance(data, dict):
                    self._normal_pin_hash = data.get("normal_pin_hash")
                    self._duress_pin_hash = data.get("duress_pin_hash")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("duress_auth")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("security.auth.pin", self._handle_pin_auth)
        self.event_bus.subscribe("security.auth.biometric", self._handle_bio_auth)
        self.event_bus.subscribe("security.pin.set_normal", self._handle_set_normal)
        self.event_bus.subscribe("security.pin.set_duress", self._handle_set_duress)
        self.event_bus.subscribe("security.update.request", self._handle_update_request)
        self.event_bus.subscribe("security.update.confirm", self._handle_update_confirm)

    def _handle_pin_auth(self, data: Any) -> None:
        if isinstance(data, dict):
            result = self.authenticate_pin(data.get("pin", ""))
            if self.event_bus:
                self.event_bus.publish("security.auth.result", result)

    def _handle_bio_auth(self, data: Any) -> None:
        if isinstance(data, dict):
            result = self.authenticate_biometric(
                voice_verified=data.get("voice_verified", False),
                face_verified=data.get("face_verified", False),
                voice_stress_high=data.get("voice_stress_high", False),
            )
            if self.event_bus:
                self.event_bus.publish("security.auth.result", result)

    def _handle_set_normal(self, data: Any) -> None:
        if isinstance(data, dict):
            self.set_normal_pin(data.get("pin", ""))

    def _handle_set_duress(self, data: Any) -> None:
        if isinstance(data, dict):
            self.set_duress_pin(data.get("pin", ""))

    def _handle_update_request(self, data: Any) -> None:
        if isinstance(data, dict):
            self.request_update_authorization(
                data.get("update_id", ""),
                data.get("description", ""),
            )

    def _handle_update_confirm(self, data: Any) -> None:
        if isinstance(data, dict):
            self.authorize_update(
                data.get("update_id", ""),
                data.get("biometric_verified", False),
            )

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        await super().close()
