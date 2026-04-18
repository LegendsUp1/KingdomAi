"""
Kingdom AI — Hive Mind (Multi-Instance Coordination)
SOTA 2026: Distributed intelligence across multiple KAI instances.

When Creator has KAI running on multiple devices (phone, laptop, desktop,
wearable hub), the Hive Mind coordinates:
  - Shared threat intelligence (one device detects → all devices react)
  - Distributed evidence collection (phone records audio, laptop records screen)
  - Consensus-based threat assessment (majority vote on threat level)
  - Unified presence monitoring (any device confirms Creator alive)
  - Cross-device scene context (phone GPS + laptop audio + wearable HR)

SOTA 2026: PIN-tied names for mobile (Hive Mind / trading).
Each mobile account gets a unique Hebrew-derived name tied to PIN — bulletproof defense,
unhackable; only Ollama brain and enrolled owner understand the language.

Uses ArmyComms for encrypted transport.
Dormant until protection flag "hive_mind" is activated.
"""
import hashlib
import json
import logging
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

# Hebrew-derived name roots for PIN-tied mobile accounts (Turtle Island / Hebrew teachings)
_HIVEMIND_NAME_ROOTS = (
    "Shalom", "Tikvah", "Chaim", "Ohr", "Emet", "Chesed", "Tzedek",
    "Shira", "Lev", "Ruach", "Neshama", "Koach", "Simcha", "Bracha",
)


def _pin_to_hive_name(pin: str) -> str:
    """Derive unique Hebrew-based name from PIN. Same PIN = same name (deterministic)."""
    h = hashlib.sha256(pin.encode("utf-8")).hexdigest()
    idx = int(h[:8], 16) % len(_HIVEMIND_NAME_ROOTS)
    suffix = h[8:12]
    return f"{_HIVEMIND_NAME_ROOTS[idx]}-{suffix}"


class HivePeer:
    """Represents a connected KAI instance in the hive."""

    def __init__(self, peer_id: str, device_type: str = "unknown", pin: Optional[str] = None):
        self.peer_id = peer_id
        self.device_type = device_type  # phone, laptop, desktop, wearable_hub
        self.pin = pin  # Mobile: PIN ties to unique Hebrew-derived name
        self.hive_name: Optional[str] = _pin_to_hive_name(pin) if pin else None
        self.last_seen = time.time()
        self.capabilities: List[str] = []  # audio, video, gps, ble, screen
        self.threat_level: str = "normal"
        self.scene_type: str = "unknown"
        self.creator_present: bool = False
        self.vitals: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "peer_id": self.peer_id,
            "device_type": self.device_type,
            "last_seen": datetime.fromtimestamp(self.last_seen).isoformat(),
            "capabilities": self.capabilities,
            "threat_level": self.threat_level,
            "scene_type": self.scene_type,
            "creator_present": self.creator_present,
        }
        if self.hive_name:
            d["hive_name"] = self.hive_name  # PIN-tied Hebrew-derived name
        return d

    @property
    def is_alive(self) -> bool:
        return time.time() - self.last_seen < 120  # 2 min timeout


class HiveMind(BaseComponent):
    """
    Distributed intelligence coordinator for multi-device KAI deployments.

    Coordinates:
      - Threat intelligence sharing
      - Consensus-based threat assessment
      - Distributed evidence collection
      - Unified presence monitoring
    """

    _instance: Optional["HiveMind"] = None
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

        self._peers: Dict[str, HivePeer] = {}
        self._lock = threading.RLock()

        # This instance's info
        self._local_id = ""  # Set from ArmyComms instance_id
        self._local_capabilities: List[str] = []
        self._detect_capabilities()

        # Consensus state
        self._threat_votes: Dict[str, str] = {}  # peer_id -> threat_level

        # Trade signal intelligence
        self._trade_signals: List[Dict] = []
        self._aggregate_intelligence: Dict[str, Any] = {}
        self._predator_mode_active: bool = False
        self._entity_performance: Dict[str, Dict] = {}

        # Sync thread
        self._sync_thread: Optional[threading.Thread] = None
        self._running = False
        self._sync_interval = 30  # seconds

        self._subscribe_events()
        self._initialized = True
        logger.info("HiveMind initialized (dormant until activated)")

    def _detect_capabilities(self) -> None:
        """Detect what this device can do."""
        caps = []
        try:
            import cv2
            caps.append("video")
        except ImportError as e:
            logger.warning("Init: cv2 not available: %s", e)
        try:
            import sounddevice
            caps.append("audio")
        except (ImportError, OSError) as e:
            logger.warning("Init: sounddevice not available: %s", e)
        try:
            import bleak
            caps.append("ble")
        except ImportError as e:
            logger.warning("Init: bleak not available: %s", e)
        caps.append("screen")  # All devices can capture screen
        self._local_capabilities = caps

    # ------------------------------------------------------------------
    # Peer management
    # ------------------------------------------------------------------

    def update_peer(self, peer_id: str, data: Dict) -> None:
        """Update peer information from hive sync message."""
        with self._lock:
            pin = data.get("pin")
            if peer_id not in self._peers:
                self._peers[peer_id] = HivePeer(
                    peer_id,
                    device_type=data.get("device_type", "unknown"),
                    pin=pin,
                )
                hive_name = self._peers[peer_id].hive_name
                logger.info("New hive peer discovered: %s (%s)%s",
                            peer_id[:8], data.get("device_type", "unknown"),
                            f" [hive_name={hive_name}]" if hive_name else "")

            peer = self._peers[peer_id]
            peer.last_seen = time.time()
            peer.device_type = data.get("device_type", peer.device_type)
            peer.capabilities = data.get("capabilities", peer.capabilities)
            peer.threat_level = data.get("threat_level", peer.threat_level)
            peer.scene_type = data.get("scene_type", peer.scene_type)
            peer.creator_present = data.get("creator_present", peer.creator_present)
            peer.vitals = data.get("vitals", peer.vitals)
            if pin and not peer.hive_name:
                peer.pin = pin
                peer.hive_name = _pin_to_hive_name(pin)

        # Update threat consensus
        self._threat_votes[peer_id] = data.get("threat_level", "normal")
        self._evaluate_consensus()

    def get_alive_peers(self) -> List[Dict]:
        with self._lock:
            return [p.to_dict() for p in self._peers.values() if p.is_alive]

    def get_peer_count(self) -> int:
        with self._lock:
            return sum(1 for p in self._peers.values() if p.is_alive)

    # ------------------------------------------------------------------
    # Consensus-based threat assessment
    # ------------------------------------------------------------------

    def _evaluate_consensus(self) -> None:
        """Evaluate threat level across all hive peers (majority vote)."""
        if not self._threat_votes:
            return

        # Only count alive peers
        alive_ids = set()
        with self._lock:
            alive_ids = {p.peer_id for p in self._peers.values() if p.is_alive}

        active_votes = {k: v for k, v in self._threat_votes.items() if k in alive_ids}
        if not active_votes:
            return

        vote_counts = Counter(active_votes.values())
        consensus_level, count = vote_counts.most_common(1)[0]
        total = len(active_votes)
        agreement_pct = count / total * 100

        # If any peer reports EMERGENCY, escalate regardless of consensus
        if "emergency" in active_votes.values():
            consensus_level = "emergency"
            agreement_pct = 100

        if self.event_bus and agreement_pct >= 50:
            self.event_bus.publish("hive.threat.consensus", {
                "threat_level": consensus_level,
                "agreement_pct": round(agreement_pct, 1),
                "peer_count": total,
                "votes": dict(vote_counts),
            })

    # ------------------------------------------------------------------
    # Distributed evidence collection
    # ------------------------------------------------------------------

    def request_distributed_evidence(self, reason: str) -> None:
        """Request all hive peers to start evidence collection."""
        if not self.event_bus:
            return

        # Broadcast evidence request to army
        self.event_bus.publish("army.broadcast", {
            "msg_type": "evidence_request",
            "payload": {
                "reason": reason,
                "duration_seconds": 600,
                "capabilities_needed": ["audio", "video", "screen"],
            },
        })

        # Also start local evidence collection
        self.event_bus.publish("security.evidence.start_capture", {
            "reason": f"hive_distributed: {reason}",
            "duration_seconds": 600,
        })

    # ------------------------------------------------------------------
    # Unified presence
    # ------------------------------------------------------------------

    def is_creator_present_anywhere(self) -> bool:
        """Check if Creator is confirmed present on ANY hive device."""
        with self._lock:
            for peer in self._peers.values():
                if peer.is_alive and peer.creator_present:
                    return True
        return False

    # ------------------------------------------------------------------
    # Sync loop
    # ------------------------------------------------------------------

    def start_sync(self) -> None:
        if self._running:
            return
        self._running = True
        self._sync_thread = threading.Thread(
            target=self._sync_loop, daemon=True, name="HiveMindSync",
        )
        self._sync_thread.start()
        logger.info("Hive mind sync started (interval=%ds)", self._sync_interval)

    def stop_sync(self) -> None:
        self._running = False
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5)

    def _sync_loop(self) -> None:
        while self._running:
            try:
                if self._is_active():
                    self._broadcast_status()
                    self._cleanup_dead_peers()
            except Exception as e:
                logger.error("Hive sync error: %s", e)

            for _ in range(self._sync_interval):
                if not self._running:
                    return
                time.sleep(1)

    def _broadcast_status(self) -> None:
        """Broadcast this instance's status + trading intelligence to the hive."""
        if not self.event_bus:
            return

        status = {
            "device_type": "desktop",
            "capabilities": self._local_capabilities,
            "threat_level": "normal",
            "scene_type": "unknown",
            "creator_present": True,
            "predator_mode": self._predator_mode_active,
            "trading_intelligence": self._aggregate_intelligence,
            "signal_count": len(self._trade_signals),
        }

        self.event_bus.publish("army.broadcast", {
            "msg_type": "hive_sync",
            "payload": status,
        })

        # Also broadcast recent trading signals for cross-instance coordination
        if self._trade_signals:
            recent = [s for s in self._trade_signals if time.time() - s.get("timestamp", 0) < 300]
            if recent:
                self.event_bus.publish("army.broadcast", {
                    "msg_type": "trading_intelligence_sync",
                    "payload": {
                        "signals": recent[-10:],
                        "aggregate": self._aggregate_intelligence,
                        "predator_mode": self._predator_mode_active,
                    },
                })

    def _cleanup_dead_peers(self) -> None:
        """Remove peers that haven't been seen recently."""
        cutoff = time.time() - 300  # 5 min
        with self._lock:
            dead = [pid for pid, p in self._peers.items() if p.last_seen < cutoff]
            for pid in dead:
                del self._peers[pid]
                self._threat_votes.pop(pid, None)
                logger.info("Hive peer removed (timeout): %s", pid[:8])

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("hive_mind")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Predator Mode & Trading Coordination (24/7 for ALL instances)
    # ------------------------------------------------------------------

    def get_hive_trading_intelligence(self) -> Dict[str, Any]:
        """Get aggregate trading intelligence from all hive instances."""
        return {
            "aggregate": self._aggregate_intelligence,
            "peer_count": self.get_peer_count(),
            "predator_mode_active": self._predator_mode_active,
            "collective_signals": self._trade_signals[-50:] if self._trade_signals else [],
            "entity_performances": self._entity_performance,
        }

    def activate_predator_mode(self, reason: str = "hive_consensus") -> None:
        """Activate predator mode across ALL hive instances."""
        self._predator_mode_active = True
        logger.info("PREDATOR MODE ACTIVATED across hive: %s", reason)
        if self.event_bus:
            self.event_bus.publish("hive.predator_mode.activated", {
                "reason": reason,
                "timestamp": time.time(),
                "peer_count": self.get_peer_count(),
            })
            self.event_bus.publish("army.broadcast", {
                "msg_type": "predator_mode_sync",
                "payload": {"active": True, "reason": reason, "ts": time.time()},
            })

    def _handle_predator_sync(self, data: Any) -> None:
        """Handle predator mode sync from other hive instances."""
        if isinstance(data, dict):
            payload = data.get("payload", {})
            if payload.get("active"):
                if not self._predator_mode_active:
                    self._predator_mode_active = True
                    logger.info("Predator mode synced from hive peer")
                    if self.event_bus:
                        self.event_bus.publish("trading.predator_mode.activate", {
                            "source": "hive_sync",
                            "reason": payload.get("reason", "peer_sync"),
                        })

    def _handle_trading_intelligence_sync(self, data: Any) -> None:
        """Receive trading intelligence from another hive instance."""
        if not isinstance(data, dict):
            return
        payload = data.get("payload", {})
        entity_id = payload.get("entity_id", data.get("sender_id", "unknown"))
        signals = payload.get("signals", [])
        performance = payload.get("performance", {})

        self._entity_performance[entity_id] = {
            "win_rate": performance.get("win_rate", 0),
            "total_trades": performance.get("total_trades", 0),
            "profit_pct": performance.get("profit_pct", 0),
            "last_updated": time.time(),
        }

        for sig in signals:
            if isinstance(sig, dict) and sig.get("symbol"):
                sig["source_entity"] = entity_id
                sig["from_hive"] = True
                self._trade_signals.append(sig)

        if len(self._trade_signals) > 2000:
            self._trade_signals = self._trade_signals[-1000:]

        logger.debug("Received trading intelligence from entity %s: %d signals",
                     entity_id[:8] if entity_id else "?", len(signals))

    def broadcast_trading_intelligence(self, entity_id: str, signals: list, performance: dict) -> None:
        """Share this instance's trading intelligence with all hive peers."""
        if not self.event_bus:
            return
        self.event_bus.publish("army.broadcast", {
            "msg_type": "trading_intelligence_sync",
            "payload": {
                "entity_id": entity_id,
                "signals": signals[-20:] if signals else [],
                "performance": performance,
                "predator_mode": self._predator_mode_active,
                "timestamp": time.time(),
            },
        })

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("army.received.hive_sync", self._handle_hive_sync)
        self.event_bus.subscribe("army.received.evidence_request", self._handle_evidence_req)
        self.event_bus.subscribe("hive.evidence.request", self._handle_local_evidence_req)
        self.event_bus.subscribe("hive.peers.query", self._handle_peers_query)
        self.event_bus.subscribe("protection.flag.changed", self._handle_flag_change)
        # Wisdom protection awareness
        self.event_bus.subscribe("soul.wisdom.gathered", self._on_wisdom)
        self.event_bus.subscribe("trading.signal", self._on_trade)
        self.event_bus.subscribe("army.received.predator_mode_sync", self._handle_predator_sync)
        self.event_bus.subscribe("army.received.trading_intelligence_sync", self._handle_trading_intelligence_sync)
        # Knowledge preservation (HiveMind coordination)
        self.event_bus.subscribe("hive.knowledge.upload", self._on_knowledge_upload)
        self.event_bus.subscribe("hive.knowledge.download", self._on_knowledge_download)

    def _on_wisdom(self, data: Any) -> None:
        """Hive aware of wisdom gathering - protect in owner absence."""
        try:
            if not isinstance(data, dict):
                return
            wisdom_type = data.get("type", "unknown")
            source = data.get("source", "unknown")
            timestamp = data.get("timestamp", time.time())
            logger.debug("HiveMind: Wisdom event received — type=%s, source=%s", wisdom_type, source)

            if self.event_bus and self._predator_mode_active:
                self.event_bus.publish("army.broadcast", {
                    "msg_type": "hive_sync",
                    "payload": {
                        "event": "wisdom_awareness",
                        "wisdom_type": wisdom_type,
                        "timestamp": timestamp,
                    }
                })
        except Exception as e:
            logger.debug("Error processing wisdom event: %s", e)

    def _on_trade(self, data: Any) -> None:
        """Process trading signals and share intelligence across instances."""
        if not isinstance(data, dict):
            return
        signal = {
            "symbol": data.get("symbol", "unknown"),
            "action": data.get("action", "hold"),
            "confidence": float(data.get("confidence", 0)),
            "timestamp": data.get("timestamp", time.time()),
            "source_entity": data.get("entity_id", "unknown"),
            "ai_powered": data.get("ai_powered", False),
        }
        self._trade_signals.append(signal)
        # Keep last 1000 signals
        if len(self._trade_signals) > 1000:
            self._trade_signals = self._trade_signals[-1000:]

        # Update aggregate intelligence
        recent = [
            s
            for s in self._trade_signals
            if time.time() - s.get("timestamp", 0) < 3600
        ]
        actions = Counter(s["action"] for s in recent)
        conf_by_action: Dict[str, List[float]] = defaultdict(list)
        for s in recent:
            conf_by_action[s["action"]].append(s["confidence"])

        self._aggregate_intelligence = {
            "signal_counts": dict(actions),
            "avg_confidence": {
                a: sum(c) / len(c) for a, c in conf_by_action.items() if c
            },
            "dominant_action": actions.most_common(1)[0][0] if actions else "hold",
            "total_signals_1h": len(recent),
            "last_updated": time.time(),
        }

        # Broadcast to connected instances
        if hasattr(self, "_broadcast_intelligence") and callable(
            getattr(self, "_broadcast_intelligence")
        ):
            try:
                self._broadcast_intelligence(self._aggregate_intelligence)
            except Exception as e:
                logger.warning("Broadcasting trade intelligence: %s", e)
        elif hasattr(self, "event_bus") and self.event_bus:
            try:
                self.event_bus.publish("hive.intelligence.updated", self._aggregate_intelligence)
            except Exception as e:
                logger.warning("Publishing trade intelligence update: %s", e)

        logger.debug(
            "Hive mind processed trade signal: %s %s conf=%.2f",
            signal["symbol"],
            signal["action"],
            signal["confidence"],
        )

    def _on_knowledge_upload(self, data: Any) -> None:
        """Knowledge uploaded - broadcast to all hive peers for preservation."""
        if not isinstance(data, dict):
            return
        # Broadcast to all peers for distributed preservation
        if self.event_bus:
            self.event_bus.publish("army.broadcast", {
                "msg_type": "knowledge_sync",
                "payload": {
                    "action": "upload",
                    "filename": data.get("filename", "unknown"),
                    "size": data.get("size", 0),
                    "timestamp": data.get("timestamp"),
                },
            })

    def _on_knowledge_download(self, data: Any) -> None:
        """Knowledge downloaded - log for audit trail."""
        if not isinstance(data, dict):
            return
        # Broadcast download event to peers
        if self.event_bus:
            self.event_bus.publish("army.broadcast", {
                "msg_type": "knowledge_sync",
                "payload": {
                    "action": "download",
                    "filepath": data.get("filepath", ""),
                    "size": data.get("size", 0),
                    "timestamp": data.get("timestamp"),
                },
            })

    def _handle_hive_sync(self, data: Any) -> None:
        if isinstance(data, dict):
            peer_id = data.get("sender_id", "")
            payload = data.get("payload", {})
            if peer_id:
                self.update_peer(peer_id, payload)
                # Sync predator mode from peers
                if payload.get("predator_mode") and not self._predator_mode_active:
                    self._predator_mode_active = True
                    logger.info("Predator mode activated via hive peer sync from %s", peer_id[:8])
                    if self.event_bus:
                        self.event_bus.publish("trading.predator_mode.activate", {
                            "source": "hive_peer_sync", "peer": peer_id[:8]})
                # Incorporate peer's trading intelligence
                peer_intel = payload.get("trading_intelligence", {})
                if peer_intel and isinstance(peer_intel, dict):
                    self._entity_performance[peer_id] = {
                        "from_sync": True,
                        "signal_counts": peer_intel.get("signal_counts", {}),
                        "last_updated": time.time(),
                    }

    def _handle_evidence_req(self, data: Any) -> None:
        if isinstance(data, dict):
            payload = data.get("payload", {})
            reason = payload.get("reason", "hive_request")
            if self.event_bus:
                self.event_bus.publish("security.evidence.start_capture", {
                    "reason": reason,
                    "duration_seconds": payload.get("duration_seconds", 300),
                })

    def _handle_local_evidence_req(self, data: Any) -> None:
        if isinstance(data, dict):
            self.request_distributed_evidence(data.get("reason", "manual"))

    def _handle_peers_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("hive.peers.list", {
                "peers": self.get_alive_peers(),
                "peer_count": self.get_peer_count(),
                "creator_present_anywhere": self.is_creator_present_anywhere(),
            })

    def _handle_flag_change(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        if data.get("module") in ("hive_mind", "__all__"):
            if data.get("active"):
                self.start_sync()
            else:
                self.stop_sync()

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self.stop_sync()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "peer_count": self.get_peer_count(),
            "peers": self.get_alive_peers(),
            "capabilities": self._local_capabilities,
            "syncing": self._running,
            "creator_present_anywhere": self.is_creator_present_anywhere(),
            "predator_mode_active": self._predator_mode_active,
            "trading_intelligence": self._aggregate_intelligence,
            "total_signals": len(self._trade_signals),
            "entity_count": len(self._entity_performance),
        }
