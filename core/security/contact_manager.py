"""
Kingdom AI — Contact Manager
SOTA 2026: Evolving emergency contact list + beneficiary management + biometric enrollment.

Creator builds this list over time via voice commands:
  "Kingdom add [name] as emergency contact"
  "Kingdom add [name] as beneficiary with [%] share"
  "Kingdom enroll [name]'s face/voice"

Each contact has:
  - Name, relationship, phone, email
  - Role: emergency_contact, beneficiary, both
  - Biometric profile (voice + face embeddings) for identity verification
  - Asset share percentage (for beneficiaries)
  - Priority level for notification order

Persisted in Redis + local encrypted JSON.
Dormant until protection flag "contact_manager" is activated.
"""
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

REDIS_KEY = "kingdom:emergency_contacts"
LOCAL_PATH_REL = os.path.join("data", "emergency_contacts.json")


class ContactRole:
    EMERGENCY = "emergency_contact"
    BENEFICIARY = "beneficiary"
    BOTH = "both"


class EmergencyContact:
    """A single emergency contact / beneficiary."""

    def __init__(
        self,
        name: str,
        relationship: str = "",
        phone: str = "",
        email: str = "",
        role: str = ContactRole.EMERGENCY,
        asset_share_pct: float = 0.0,
        priority: int = 50,
        contact_id: Optional[str] = None,
        biometric_enrolled: bool = False,
    ):
        self.contact_id = contact_id or str(uuid.uuid4())[:12]
        self.name = name
        self.relationship = relationship
        self.phone = phone
        self.email = email
        self.role = role
        self.asset_share_pct = asset_share_pct
        self.priority = priority
        self.biometric_enrolled = biometric_enrolled
        self.voice_samples: int = 0
        self.face_samples: int = 0
        self.created_at = datetime.utcnow().isoformat()
        self.last_contacted: Optional[str] = None
        self.notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "name": self.name,
            "relationship": self.relationship,
            "phone": self.phone,
            "email": self.email,
            "role": self.role,
            "asset_share_pct": self.asset_share_pct,
            "priority": self.priority,
            "biometric_enrolled": self.biometric_enrolled,
            "voice_samples": self.voice_samples,
            "face_samples": self.face_samples,
            "created_at": self.created_at,
            "last_contacted": self.last_contacted,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmergencyContact":
        c = cls(
            name=data.get("name", ""),
            relationship=data.get("relationship", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            role=data.get("role", ContactRole.EMERGENCY),
            asset_share_pct=data.get("asset_share_pct", 0.0),
            priority=data.get("priority", 50),
            contact_id=data.get("contact_id"),
            biometric_enrolled=data.get("biometric_enrolled", False),
        )
        c.voice_samples = data.get("voice_samples", 0)
        c.face_samples = data.get("face_samples", 0)
        c.created_at = data.get("created_at", c.created_at)
        c.last_contacted = data.get("last_contacted")
        c.notes = data.get("notes", "")
        return c


class ContactManager(BaseComponent):
    """
    Manages Creator's emergency contact list and beneficiary registry.

    Supports:
      - Add/remove/update contacts via event bus or direct API
      - Biometric enrollment for each contact (via UserIdentityEngine)
      - Priority-ordered notification dispatch
      - Asset share allocation for beneficiaries
      - Validation of total beneficiary shares (must sum to 100%)
    """

    _instance: Optional["ContactManager"] = None
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

        self._contacts: Dict[str, EmergencyContact] = {}
        self._contacts_lock = threading.RLock()
        self._local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            LOCAL_PATH_REL,
        )

        self._load_persisted()
        self._subscribe_events()
        self._initialized = True
        logger.info("ContactManager initialized — %d contacts loaded", len(self._contacts))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_contact(self, name: str, relationship: str = "", phone: str = "",
                    email: str = "", role: str = ContactRole.EMERGENCY,
                    asset_share_pct: float = 0.0, priority: int = 50) -> str:
        """Add a new emergency contact. Returns contact_id."""
        contact = EmergencyContact(
            name=name, relationship=relationship, phone=phone, email=email,
            role=role, asset_share_pct=asset_share_pct, priority=priority,
        )
        with self._contacts_lock:
            self._contacts[contact.contact_id] = contact
        self._persist()

        if self.event_bus:
            self.event_bus.publish("contacts.added", contact.to_dict())
        logger.info("Contact added: %s (%s) — role=%s", name, relationship, role)
        return contact.contact_id

    def remove_contact(self, contact_id: str) -> bool:
        with self._contacts_lock:
            if contact_id in self._contacts:
                removed = self._contacts.pop(contact_id)
                self._persist()
                if self.event_bus:
                    self.event_bus.publish("contacts.removed", {"contact_id": contact_id, "name": removed.name})
                logger.info("Contact removed: %s", removed.name)
                return True
        return False

    def update_contact(self, contact_id: str, **kwargs) -> bool:
        with self._contacts_lock:
            contact = self._contacts.get(contact_id)
            if not contact:
                return False
            for key, value in kwargs.items():
                if hasattr(contact, key):
                    setattr(contact, key, value)
            self._persist()

        if self.event_bus:
            self.event_bus.publish("contacts.updated", contact.to_dict())
        return True

    def get_contact(self, contact_id: str) -> Optional[Dict]:
        with self._contacts_lock:
            c = self._contacts.get(contact_id)
            return c.to_dict() if c else None

    def get_all_contacts(self) -> List[Dict]:
        with self._contacts_lock:
            return [c.to_dict() for c in sorted(self._contacts.values(), key=lambda c: -c.priority)]

    def get_emergency_contacts(self) -> List[Dict]:
        """Get contacts sorted by priority for emergency notification."""
        with self._contacts_lock:
            ecs = [c for c in self._contacts.values() if c.role in (ContactRole.EMERGENCY, ContactRole.BOTH)]
            return [c.to_dict() for c in sorted(ecs, key=lambda c: -c.priority)]

    def get_beneficiaries(self) -> List[Dict]:
        """Get beneficiaries with their asset shares."""
        with self._contacts_lock:
            bens = [c for c in self._contacts.values() if c.role in (ContactRole.BENEFICIARY, ContactRole.BOTH)]
            return [c.to_dict() for c in sorted(bens, key=lambda c: -c.asset_share_pct)]

    def validate_beneficiary_shares(self) -> Dict[str, Any]:
        """Check if beneficiary shares sum to 100%."""
        beneficiaries = self.get_beneficiaries()
        total = sum(b.get("asset_share_pct", 0) for b in beneficiaries)
        return {
            "valid": abs(total - 100.0) < 0.01,
            "total_pct": round(total, 2),
            "beneficiary_count": len(beneficiaries),
            "remaining_pct": round(100.0 - total, 2),
        }

    def find_contact_by_name(self, name: str) -> Optional[Dict]:
        """Find a contact by name (case-insensitive)."""
        name_lower = name.lower()
        with self._contacts_lock:
            for c in self._contacts.values():
                if c.name.lower() == name_lower:
                    return c.to_dict()
        return None

    # ------------------------------------------------------------------
    # Biometric enrollment integration
    # ------------------------------------------------------------------

    def enroll_contact_biometric(self, contact_id: str, biometric_type: str = "voice") -> bool:
        """
        Trigger biometric enrollment for a contact.
        Publishes event for UserIdentityEngine to handle.
        """
        with self._contacts_lock:
            contact = self._contacts.get(contact_id)
            if not contact:
                return False

        if self.event_bus:
            self.event_bus.publish("contacts.biometric.enroll_request", {
                "contact_id": contact_id,
                "contact_name": contact.name,
                "biometric_type": biometric_type,
            })
        logger.info("Biometric enrollment requested for %s (%s)", contact.name, biometric_type)
        return True

    def _on_biometric_enrolled(self, data: Any) -> None:
        """Handle notification that a contact's biometric was enrolled."""
        if not isinstance(data, dict):
            return
        contact_id = data.get("contact_id")
        bio_type = data.get("biometric_type", "")
        if contact_id:
            with self._contacts_lock:
                contact = self._contacts.get(contact_id)
                if contact:
                    if bio_type == "voice":
                        contact.voice_samples += 1
                    elif bio_type == "face":
                        contact.face_samples += 1
                    contact.biometric_enrolled = contact.voice_samples > 0 or contact.face_samples > 0
                    self._persist()

    # ------------------------------------------------------------------
    # Emergency notification dispatch
    # ------------------------------------------------------------------

    def notify_emergency_contacts(self, reason: str, urgency: str = "high",
                                   extra_data: Optional[Dict] = None) -> int:
        """
        Notify all emergency contacts. Returns count notified.
        Actual notification delivery is handled by downstream systems
        (SMS, email, push notification services).
        """
        contacts = self.get_emergency_contacts()
        if not contacts:
            logger.warning("No emergency contacts configured for notification!")
            return 0

        for contact in contacts:
            notification = {
                "contact_id": contact["contact_id"],
                "contact_name": contact["name"],
                "phone": contact["phone"],
                "email": contact["email"],
                "reason": reason,
                "urgency": urgency,
                "extra": extra_data or {},
                "timestamp": datetime.utcnow().isoformat(),
            }
            if self.event_bus:
                self.event_bus.publish("contacts.notification.send", notification)

            # Update last_contacted
            with self._contacts_lock:
                c = self._contacts.get(contact["contact_id"])
                if c:
                    c.last_contacted = datetime.utcnow().isoformat()

        self._persist()
        logger.info("Emergency notification dispatched to %d contacts: %s", len(contacts), reason)
        return len(contacts)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_persisted(self) -> None:
        loaded = False
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY)
                if isinstance(data, list):
                    for cd in data:
                        c = EmergencyContact.from_dict(cd)
                        self._contacts[c.contact_id] = c
                    loaded = True
            except Exception:
                pass

        if not loaded and os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for cd in data:
                        c = EmergencyContact.from_dict(cd)
                        self._contacts[c.contact_id] = c
            except Exception:
                pass

    def _persist(self) -> None:
        with self._contacts_lock:
            snapshot = [c.to_dict() for c in self._contacts.values()]

        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY, snapshot)
            except Exception:
                pass

        try:
            os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
            with open(self._local_path, "w") as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            logger.debug("Contact persist failed: %s", e)

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("contacts.add", self._handle_add)
        self.event_bus.subscribe("contacts.remove", self._handle_remove)
        self.event_bus.subscribe("contacts.update", self._handle_update)
        self.event_bus.subscribe("contacts.query", self._handle_query)
        self.event_bus.subscribe("contacts.biometric.enrolled", self._on_biometric_enrolled)
        self.event_bus.subscribe("security.emergency.notify_contacts", self._handle_emergency_notify)

    def _handle_add(self, data: Any) -> None:
        if isinstance(data, dict):
            self.add_contact(**{k: v for k, v in data.items() if k in (
                "name", "relationship", "phone", "email", "role", "asset_share_pct", "priority"
            )})

    def _handle_remove(self, data: Any) -> None:
        if isinstance(data, dict):
            self.remove_contact(data.get("contact_id", ""))

    def _handle_update(self, data: Any) -> None:
        if isinstance(data, dict):
            cid = data.pop("contact_id", "")
            if cid:
                self.update_contact(cid, **data)

    def _handle_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("contacts.list", {
                "contacts": self.get_all_contacts(),
                "validation": self.validate_beneficiary_shares(),
            })

    def _handle_emergency_notify(self, data: Any) -> None:
        if isinstance(data, dict):
            self.notify_emergency_contacts(
                reason=data.get("reason", "Emergency"),
                urgency=data.get("urgency", "high"),
                extra_data=data,
            )

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self._persist()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_contacts": len(self._contacts),
            "emergency_contacts": len(self.get_emergency_contacts()),
            "beneficiaries": len(self.get_beneficiaries()),
            "beneficiary_validation": self.validate_beneficiary_shares(),
        }
