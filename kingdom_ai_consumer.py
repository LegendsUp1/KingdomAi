#!/usr/bin/env python3
"""
Kingdom AI — Consumer Version
SOTA 2026: Streamlined entry point for consumer deployments.

This is the consumer-facing launcher that:
  1. Validates license key
  2. Loads tier-appropriate protection flags
  3. Initializes only the modules enabled for the consumer's tier
  4. Connects to Creator's KAI army network (if tier allows)
  5. Runs the full GUI with consumer-appropriate features

Tiers:
  - Basic ($9.99/mo): Core protection + basic health
  - Pro ($29.99/mo): Full protection + full health + army + hive
  - Enterprise ($99.99/mo): All features

Usage:
  python kingdom_ai_consumer.py --license <LICENSE_KEY>
  python kingdom_ai_consumer.py --setup  (first-time setup wizard)
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional

os.environ["KINGDOM_APP_MODE"] = "consumer"
# Consumer DESKTOP — full dependency tier, hardware-adaptive.
# Consumer-desktop users get the same TRT-LLM / vLLM / CUDA /
# sentence-transformers stack the creator gets, provided their machine
# supports it. Role "consumer" only redacts keys, secrets, and proprietary
# data. Only KINGDOM_APP_PLATFORM=mobile triggers the light tier.
os.environ["KINGDOM_APP_PLATFORM"] = "desktop"

# Configure logging before anything else
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "kingdom_consumer.log"), mode="a"),
    ],
)
logger = logging.getLogger("KingdomAI.Consumer")

# Ensure logs directory exists
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"), exist_ok=True)

# Consumer config path
CONSUMER_CONFIG_PATH = os.path.join("config", "consumer_config.json")


def load_consumer_config() -> Dict[str, Any]:
    """Load saved consumer configuration."""
    if os.path.exists(CONSUMER_CONFIG_PATH):
        try:
            with open(CONSUMER_CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Init: Failed to load consumer config: %s", e)
    return {}


def save_consumer_config(config: Dict[str, Any]) -> None:
    """Save consumer configuration."""
    os.makedirs(os.path.dirname(CONSUMER_CONFIG_PATH), exist_ok=True)
    with open(CONSUMER_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def run_setup_wizard() -> Dict[str, Any]:
    """Interactive first-time setup wizard."""
    print("\n" + "=" * 60)
    print("  KINGDOM AI — Consumer Setup Wizard")
    print("=" * 60)
    print()
    print("Welcome to Kingdom AI! Let's get you set up.")
    print()

    # Get license key
    license_key = input("Enter your license key: ").strip()
    if not license_key:
        print("ERROR: License key is required.")
        sys.exit(1)

    # Get Creator name
    creator_name = input("Enter your name (Creator name): ").strip()
    if not creator_name:
        creator_name = "Creator"

    # Emergency contact setup
    print("\n--- Emergency Contact Setup ---")
    print("Add at least one emergency contact (press Enter to skip).")
    contacts = []
    for i in range(3):
        name = input(f"  Contact {i+1} name: ").strip()
        if not name:
            break
        phone = input(f"  Contact {i+1} phone: ").strip()
        email = input(f"  Contact {i+1} email: ").strip()
        relationship = input(f"  Contact {i+1} relationship: ").strip()
        contacts.append({
            "name": name,
            "phone": phone,
            "email": email,
            "relationship": relationship,
            "role": "emergency_contact",
        })
        print(f"  ✓ Added {name}")

    # Wearable setup
    print("\n--- Wearable Device Setup ---")
    print("Connect a wearable for health monitoring (press Enter to skip).")
    wearable = {}
    brand = input("  Wearable brand (garmin/oura/fitbit/none): ").strip().lower()
    if brand and brand != "none":
        wearable["brand"] = brand
        if brand == "garmin":
            wearable["email"] = input("  Garmin Connect email: ").strip()
            wearable["password"] = input("  Garmin Connect password: ").strip()
        elif brand == "oura":
            wearable["access_token"] = input("  Oura API access token: ").strip()
        print(f"  ✓ {brand.title()} configured")

    config = {
        "license_key": license_key,
        "creator_name": creator_name,
        "emergency_contacts": contacts,
        "wearable": wearable,
        "setup_completed": True,
        "setup_at": datetime.utcnow().isoformat(),
    }

    save_consumer_config(config)
    print("\n✓ Setup complete! Configuration saved.")
    print(f"  License: {license_key[:8]}...{license_key[-4:]}")
    print(f"  Contacts: {len(contacts)}")
    print(f"  Wearable: {wearable.get('brand', 'none')}")
    print()

    return config


def activate_consumer_flags(event_bus: Any, tier_config: Dict[str, Any]) -> None:
    """Activate protection flags based on consumer tier."""
    flags = tier_config.get("protection_flags", {})
    for module, active in flags.items():
        if active:
            event_bus.publish("protection.flag.set", {
                "module": module,
                "active": True,
                "source": "consumer_installer",
            })
    logger.info("Consumer protection flags activated: %d modules",
                sum(1 for v in flags.values() if v))


def setup_emergency_contacts(event_bus: Any, contacts: list) -> None:
    """Register emergency contacts from consumer config."""
    for contact in contacts:
        event_bus.publish("contacts.add", contact)
    if contacts:
        logger.info("Registered %d emergency contacts", len(contacts))


def setup_wearable(event_bus: Any, wearable: Dict) -> None:
    """Connect wearable device from consumer config."""
    if not wearable or not wearable.get("brand"):
        return

    event_bus.publish("health.device.add", {
        "brand": wearable["brand"],
        "name": f"{wearable['brand'].title()} Watch",
        "connection_type": "api",
        "credentials": {k: v for k, v in wearable.items() if k != "brand"},
    })
    logger.info("Wearable configured: %s", wearable["brand"])


def main():
    parser = argparse.ArgumentParser(description="Kingdom AI Consumer Edition")
    parser.add_argument("--license", type=str, help="License key")
    parser.add_argument("--setup", action="store_true", help="Run first-time setup wizard")
    parser.add_argument("--headless", action="store_true", help="Run without GUI (background protection only)")
    parser.add_argument("--device-id", type=str, default=None, help="Link to existing mobile device ID")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════╗")
    print("║     KINGDOM AI — Consumer Edition        ║")
    print("║     Creator Protection System            ║")
    print("║     SOTA 2026                            ║")
    print("╚══════════════════════════════════════════╝\n")

    # Setup wizard
    if args.setup:
        config = run_setup_wizard()
    else:
        config = load_consumer_config()

    if not config.get("setup_completed"):
        print("First-time setup required. Run: python kingdom_ai_consumer.py --setup")
        sys.exit(1)

    license_key = args.license or config.get("license_key", "")
    if not license_key:
        print("ERROR: No license key found. Run setup or provide --license <KEY>")
        sys.exit(1)

    logger.info("Kingdom AI Consumer starting...")
    logger.info("License: %s...%s", license_key[:8], license_key[-4:])

    # ──────────────────────────────────────────────
    # Initialize core systems (same as kingdom_ai_perfect.py but lighter)
    # ──────────────────────────────────────────────

    # Event bus
    try:
        from core.event_bus import EventBus
        event_bus = EventBus.get_instance()
        logger.info("[OK] EventBus initialized")
    except Exception as e:
        logger.critical("EventBus initialization failed: %s", e)
        sys.exit(1)

    # Redis (optional for consumer)
    redis_client = None
    try:
        from core.redis_connector import RedisConnector
        redis_client = RedisConnector()
        logger.info("[OK] Redis Quantum Nexus connected")
    except Exception:
        logger.info("Redis unavailable — using local storage only")

    # Validate license
    tier_config = None
    try:
        from core.security.consumer_installer import ConsumerInstaller
        installer = ConsumerInstaller(event_bus=event_bus, redis_connector=redis_client)
        validation = installer.validate_license(license_key)

        if not validation.get("valid"):
            # Try activating first
            installer.activate_license(license_key)
            validation = installer.validate_license(license_key)

        if validation.get("valid"):
            tier_config = installer.generate_consumer_config(license_key)
            logger.info("[OK] License validated: tier=%s", validation.get("tier"))
        else:
            logger.warning("License validation: %s — running with basic features",
                          validation.get("reason", "unknown"))
            # Generate basic config as fallback
            tier_config = installer.generate_consumer_config(license_key)
    except Exception as e:
        logger.warning("License validation skipped: %s", e)

    # ──────────────────────────────────────────────
    # Initialize protection modules
    # ──────────────────────────────────────────────
    try:
        from core.component_registry import register_component

        # Core protection (always loaded)
        from core.security.protection_flags import ProtectionFlagController
        pf = ProtectionFlagController(event_bus=event_bus, redis_connector=redis_client)
        register_component('protection_flags', pf)

        from core.security.protection_policy import ProtectionPolicyStore
        pp = ProtectionPolicyStore(event_bus=event_bus, redis_connector=redis_client)
        register_component('protection_policy', pp)

        from core.security.creator_shield import CreatorShield
        cs = CreatorShield(event_bus=event_bus, redis_connector=redis_client)
        register_component('creator_shield', cs)

        from core.security.wellness_checker import WellnessChecker
        wc = WellnessChecker(event_bus=event_bus, redis_connector=redis_client)
        register_component('wellness_checker', wc)

        from core.security.contact_manager import ContactManager
        cm = ContactManager(event_bus=event_bus, redis_connector=redis_client)
        register_component('contact_manager', cm)

        from core.security.silent_alarm import SilentAlarm
        sa = SilentAlarm(event_bus=event_bus, redis_connector=redis_client)
        register_component('silent_alarm', sa)

        from core.security.evidence_collector import EvidenceCollector
        ec = EvidenceCollector(event_bus=event_bus, redis_connector=redis_client)
        register_component('evidence_collector', ec)

        from core.security.presence_monitor import PresenceMonitor
        pm = PresenceMonitor(event_bus=event_bus, redis_connector=redis_client)
        register_component('presence_monitor', pm)

        from core.security.duress_auth import DuressAuth
        da = DuressAuth(event_bus=event_bus, redis_connector=redis_client)
        register_component('duress_auth', da)

        from core.security.scene_context_engine import SceneContextEngine
        sce = SceneContextEngine(event_bus=event_bus, redis_connector=redis_client)
        register_component('scene_context_engine', sce)

        from core.security.hostile_audio_detector import HostileAudioDetector
        had = HostileAudioDetector(event_bus=event_bus, redis_connector=redis_client)
        register_component('hostile_audio_detector', had)

        from core.security.hostile_visual_detector import HostileVisualDetector
        hvd = HostileVisualDetector(event_bus=event_bus, redis_connector=redis_client)
        register_component('hostile_visual_detector', hvd)

        from core.security.threat_nlp_analyzer import ThreatNLPAnalyzer
        tna = ThreatNLPAnalyzer(event_bus=event_bus, redis_connector=redis_client)
        register_component('threat_nlp_analyzer', tna)

        from core.security.ambient_transcriber import AmbientTranscriber
        at = AmbientTranscriber(event_bus=event_bus, redis_connector=redis_client)
        register_component('ambient_transcriber', at)

        from core.security.file_integrity import FileIntegrityMonitor
        fi = FileIntegrityMonitor(event_bus=event_bus, redis_connector=redis_client)
        register_component('file_integrity', fi)

        from core.security.liveness_detector import LivenessDetector
        ld = LivenessDetector(event_bus=event_bus, redis_connector=redis_client)
        register_component('liveness_detector', ld)

        from core.security.digital_trust import DigitalTrust
        dt = DigitalTrust(event_bus=event_bus, redis_connector=redis_client)
        register_component('digital_trust', dt)

        from core.security.safe_haven import SafeHaven
        sh = SafeHaven(event_bus=event_bus, redis_connector=redis_client)
        register_component('safe_haven', sh)

        from core.security.nlp_policy_evolver import NLPPolicyEvolver
        npe = NLPPolicyEvolver(event_bus=event_bus, redis_connector=redis_client)
        register_component('nlp_policy_evolver', npe)

        from core.security.advanced_hardening import AdvancedHardening
        ah = AdvancedHardening(event_bus=event_bus, redis_connector=redis_client)
        register_component('advanced_hardening', ah)

        # Health modules
        from core.health.wearable_hub import WearableHub
        wh = WearableHub(event_bus=event_bus, redis_connector=redis_client)
        register_component('wearable_hub', wh)

        from core.health.health_anomaly_detector import HealthAnomalyDetector
        hd = HealthAnomalyDetector(event_bus=event_bus, redis_connector=redis_client)
        register_component('health_anomaly_detector', hd)

        from core.health.health_advisor import HealthAdvisor
        ha = HealthAdvisor(event_bus=event_bus, redis_connector=redis_client)
        register_component('health_advisor', ha)

        # Army + Hive (tier-dependent)
        from core.security.army_comms import ArmyComms
        ac = ArmyComms(event_bus=event_bus, redis_connector=redis_client)
        register_component('army_comms', ac)

        from core.security.hive_mind import HiveMind
        hm = HiveMind(event_bus=event_bus, redis_connector=redis_client)
        register_component('hive_mind', hm)

        # SOTA 2026: AICommandRouter — typed SHA-LU-AM detection, command routing
        try:
            from core.ai_command_router import get_command_router
            get_command_router(event_bus=event_bus)
            logger.info("[OK] AICommandRouter — typed SHA-LU-AM + commands active")
        except Exception as acr_err:
            logger.debug("AICommandRouter (non-fatal): %s", acr_err)

        # SOTA 2026: ThothAI — AI brain for chat responses (ai.request -> ai.response)
        try:
            from core.thoth import ThothAI
            from core.component_registry import get_component
            thoth_ai = ThothAI(component_id="thoth", event_bus=event_bus)
            if not get_component('thoth_ai'):
                register_component('thoth_ai', thoth_ai)
            if hasattr(event_bus, 'register_component'):
                event_bus.register_component('thoth_ai', thoth_ai)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(thoth_ai.initialize())
                else:
                    loop.run_until_complete(thoth_ai.initialize())
            except RuntimeError:
                asyncio.run(thoth_ai.initialize())
            logger.info("[OK] ThothAI — AI brain active for consumer")
        except Exception as thoth_err:
            logger.debug("ThothAI (non-fatal): %s", thoth_err)

        # SOTA 2026: VoiceManager — TTS for vocal output (voice.speak)
        try:
            from core.voice_manager import VoiceManager
            from core.component_registry import get_component
            voice_manager = VoiceManager(event_bus=event_bus)
            if not get_component('voice_manager'):
                register_component('voice_manager', voice_manager)
            if hasattr(event_bus, 'register_component'):
                event_bus.register_component('voice_manager', voice_manager)
            logger.info("[OK] VoiceManager — vocal output (TTS) active for consumer")
        except Exception as vm_err:
            logger.debug("VoiceManager (non-fatal): %s", vm_err)

        # SOTA 2026: UnifiedAIRouter — ai.response -> voice.speak (vocal output from AI)
        try:
            from core.unified_ai_router import UnifiedAIRouter
            unified_router = UnifiedAIRouter(event_bus)
            unified_router.initialize()
            register_component('unified_ai_router', unified_router)
            if hasattr(event_bus, 'register_component'):
                event_bus.register_component('unified_ai_router', unified_router)
            logger.info("[OK] UnifiedAIRouter — AI vocal output active for consumer")
        except Exception as uar_err:
            logger.debug("UnifiedAIRouter (non-fatal): %s", uar_err)

        # SOTA 2026: AlwaysOnVoice — vocal input (said) for consumer
        try:
            from core.always_on_voice import get_always_on_voice
            aov = get_always_on_voice(event_bus)
            aov.initialize()
            register_component('always_on_voice', aov)
            if hasattr(event_bus, 'register_component'):
                event_bus.register_component('always_on_voice', aov)
            aov.start()
            logger.info("[OK] AlwaysOnVoice — vocal input active for consumer")
        except Exception as aov_err:
            logger.debug("AlwaysOnVoice (non-fatal): %s", aov_err)

        # SOTA 2026: Web MCP + Truth Timeline (owner/consumer desktop + mobile)
        try:
            from core.web_mcp_integration import get_web_mcp_tools_component
            web_mcp = get_web_mcp_tools_component(event_bus=event_bus)
            register_component('web_mcp_tools', web_mcp)
            if hasattr(event_bus, 'register_component'):
                event_bus.register_component('web_mcp_tools', web_mcp)
            logger.info("[OK] Web MCP tools registered for consumer")
        except Exception as wmcp_err:
            logger.debug("Web MCP (non-fatal): %s", wmcp_err)

        logger.info("[OK] All consumer protection modules loaded (dormant)")

        # ──────────────────────────────────────────────────────────────
        #  UNIFIED BRAIN (consumer desktop = full stack, minus keys/data)
        # ──────────────────────────────────────────────────────────────
        # Consumer desktop users get the exact same always-on SOTA 2026
        # inference stack, MemPalace, Ollama memory integration, Dictionary
        # Brain, Language Learning Hub, Harmonic Orchestrator, and
        # Neuroprotection Layer that the creator desktop runs — the only
        # difference is no owner keys, no proprietary data, and the
        # creator-only UI is hidden. The light-tier skip lives on the
        # PLATFORM axis (KINGDOM_APP_PLATFORM=mobile), never on role.
        _inference_stack = None
        try:
            from core.inference_stack import get_inference_stack
            _inference_stack = get_inference_stack(event_bus=event_bus)
            register_component("inference_stack", _inference_stack)
            _info = _inference_stack.get_system_info()
            logger.info(
                "[OK] InferenceStack v%s role=%s platform=%s tier=%s cuda=%s "
                "gpu=%s ollama=%s",
                _info["version"], _info["role"], _info["platform"],
                _info["tier"], _info["torch"]["cuda"],
                _info["torch"]["device_name"] or "-",
                _info["ollama"]["reachable"],
            )
        except Exception as _isx:
            logger.debug("InferenceStack init skipped (non-fatal): %s", _isx)

        _mp = None
        _omi = None
        try:
            from components.mempalace_setup import initialize_mempalace
            _mp = initialize_mempalace(event_bus)
            if isinstance(_mp, dict):
                register_component("mempalace_bridge", _mp.get("bridge"))
                register_component("memory_palace_manager", _mp.get("palace"))
                register_component("memory_persistence", _mp.get("persistence"))

            from components.ollama_memory_integration import OllamaMemoryIntegration
            _omi = OllamaMemoryIntegration(
                event_bus=event_bus,
                persistence_layer=(_mp or {}).get("persistence"),
                inference_stack=_inference_stack,
            )
            register_component("ollama_memory_integration", _omi)
            logger.info("[OK] MemPalace + Ollama memory integration initialised")
        except Exception as _mpx:
            logger.debug("MemPalace init skipped (non-fatal): %s", _mpx)

        _ho = None
        _npl = None
        _llh = None
        try:
            from components.harmonic_orchestrator_v3 import HarmonicOrchestratorV3
            _ho = HarmonicOrchestratorV3(event_bus=event_bus)
            register_component("harmonic_orchestrator", _ho)

            from components.neuroprotection_layer import NeuroprotectionLayer
            _npl = NeuroprotectionLayer(event_bus=event_bus)
            register_component("neuroprotection_layer", _npl)

            from components.language_learning_hub import LanguageLearningHub
            _llh = LanguageLearningHub(event_bus=event_bus)
            register_component("language_learning_hub", _llh)
            logger.info("[OK] AI orchestrator subsystems initialised")
        except Exception as _orx:
            logger.debug("AI orchestrator subsystems skipped (non-fatal): %s", _orx)

        _dbrain = None
        try:
            from components.dictionary_brain import DictionaryBrain
            _mp_persistence = (_mp or {}).get("persistence") if _mp else None
            _mp_palace = (_mp or {}).get("palace") if _mp else None
            _dbrain = DictionaryBrain(
                event_bus=event_bus,
                data_dir="~/.kingdom_ai/dictionaries",
                persistence_layer=_mp_persistence,
                palace_manager=_mp_palace,
                ollama_integration=_omi,
                language_hub=_llh,
                harmonic_orchestrator=_ho,
                neuroprotection=_npl,
                inference_stack=_inference_stack,
            )
            register_component("dictionary_brain", _dbrain)
            _status = _dbrain.get_status()
            logger.info(
                "[OK] DictionaryBrain v%s (webster=%d britannica=%d early=%d "
                "indexed=%d stack=%s)",
                _status["version"],
                _status["webster_1828_entries"],
                _status["britannica_entries"],
                _status["early_english_entries"],
                _status["indexed_entries"],
                _status["linked"]["inference_stack"],
            )
        except Exception as _dbx:
            logger.debug("DictionaryBrain init skipped (non-fatal): %s", _dbx)

        # UnifiedBrainRouter — funnels every inbound query through Dictionary
        # enrichment → MemPalace recall → Language Hub → InferenceStack →
        # writeback, giving the consumer desktop a single coherent brain path
        # instead of parallel subsystems.
        try:
            from core.unified_brain_router import UnifiedBrainRouter
            _ubr = UnifiedBrainRouter(
                event_bus=event_bus,
                inference_stack=_inference_stack,
                dictionary_brain=_dbrain,
                ollama_memory_integration=_omi,
                mempalace_bridge=(_mp or {}).get("bridge") if _mp else None,
                language_hub=_llh,
                harmonic_orchestrator=_ho,
                neuroprotection=_npl,
            )
            register_component("unified_brain_router", _ubr)
            logger.info(
                "[OK] UnifiedBrainRouter wired (dictionary→mempalace→"
                "language→inference) — consumer desktop brain is unified"
            )
        except Exception as _ubrx:
            logger.debug("UnifiedBrainRouter init skipped (non-fatal): %s", _ubrx)

        # Mobile Sync Server — desktop ↔ mobile WebSocket bridge
        try:
            from core.mobile_sync_server import MobileSyncServer
            mobile_sync = MobileSyncServer(event_bus=event_bus, redis_connector=redis_client)
            register_component('mobile_sync_server', mobile_sync)
            if hasattr(event_bus, 'register_component'):
                event_bus.register_component('mobile_sync_server', mobile_sync)
            # Start the WebSocket server in background
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(mobile_sync.start_server())
                else:
                    loop.run_until_complete(mobile_sync.start_server())
            except Exception as e:
                logger.warning("Init: Failed to start mobile sync server: %s", e)
            logger.info("[OK] MobileSyncServer started for consumer (ws://0.0.0.0:8765)")
        except Exception as ms_err:
            logger.debug("MobileSyncServer (non-fatal): %s", ms_err)

        # SOTA 2026: Generate unique consumer ID (persisted across restarts)
        # If --device-id provided, use it to link to existing mobile device
        consumer_id = None
        try:
            import uuid as _uuid
            consumer_id_path = os.path.join("data", "consumer_identity.json")
            os.makedirs(os.path.dirname(consumer_id_path), exist_ok=True)
            if args.device_id:
                consumer_id = args.device_id
                with open(consumer_id_path, "w") as _f:
                    json.dump({
                        "consumer_id": consumer_id,
                        "created_at": datetime.now().isoformat(),
                        "type": "consumer",
                        "linked_from": "device_id",
                    }, _f, indent=2)
                logger.info("[OK] Consumer linked to device ID: %s", consumer_id)
            elif os.path.exists(consumer_id_path):
                with open(consumer_id_path, "r") as _f:
                    _identity = json.load(_f)
                consumer_id = _identity.get("consumer_id")
            if not consumer_id:
                consumer_id = f"consumer_{_uuid.uuid4().hex[:12]}"
                with open(consumer_id_path, "w") as _f:
                    json.dump({
                        "consumer_id": consumer_id,
                        "created_at": datetime.now().isoformat(),
                        "type": "consumer",
                    }, _f, indent=2)
            logger.info("[OK] Consumer identity: %s", consumer_id)
        except Exception as cid_err:
            import uuid as _uuid
            consumer_id = f"consumer_{_uuid.uuid4().hex[:12]}"
            logger.warning("Consumer ID fallback: %s (%s)", consumer_id, cid_err)

        # SOTA 2026: Create per-consumer wallet (NEVER uses owner's addresses)
        try:
            from core.wallet_creator import WalletCreator
            wc = WalletCreator(event_bus=event_bus)
            import asyncio
            async def _create_consumer_wallet():
                return await wc.create_user_wallet(consumer_id, ["ETH", "BTC", "SOL"])
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        _cw_result = pool.submit(
                            lambda: asyncio.run(_create_consumer_wallet())).result(timeout=30)
                else:
                    _cw_result = loop.run_until_complete(_create_consumer_wallet())
            except RuntimeError:
                _cw_result = asyncio.run(_create_consumer_wallet())
            if _cw_result.get("success"):
                _cw_addrs = _cw_result.get("addresses", {})
                logger.info("[OK] Consumer wallet created: %s chains — %s",
                            len(_cw_addrs), list(_cw_addrs.keys()))
            else:
                logger.warning("Consumer wallet creation issue: %s", _cw_result.get("error"))
        except Exception as cw_err:
            logger.warning("Consumer wallet creation (non-fatal): %s", cw_err)

        # SOTA 2026: Initialize WalletManager with CONSUMER'S OWN wallet
        # CRITICAL: skip_owner_data=True prevents loading owner's addresses,
        #           private keys, and multi_coin_wallets.json
        wallet_manager = None
        try:
            from core.wallet_manager import WalletManager
            wallet_manager = WalletManager(
                event_bus=event_bus,
                config={"skip_owner_data": True},
            )
            wallet_manager.load_user_wallet(consumer_id)
            register_component('wallet_manager', wallet_manager)
            register_component('wallet_system', wallet_manager)
            if hasattr(event_bus, 'register_component'):
                event_bus.register_component('wallet_manager', wallet_manager)
                event_bus.register_component('wallet_system', wallet_manager)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(wallet_manager.initialize())
                else:
                    loop.run_until_complete(wallet_manager.initialize())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(wallet_manager.initialize())
            logger.info("[OK] WalletManager loaded with CONSUMER wallet (id=%s)", consumer_id)
        except Exception as wm_err:
            logger.warning("WalletManager init (non-fatal): %s", wm_err)

        # SOTA 2026: Auto-register consumer username (if not already done)
        try:
            from core.username_registry import register_username, update_addresses
            _cw_manifest = wc.get_user_wallet(consumer_id) if consumer_id else None
            _cw_addrs = _cw_manifest.get("addresses", {}) if _cw_manifest else {}
            if _cw_addrs:
                _uname_result = register_username(
                    raw_username=consumer_id,
                    user_id=consumer_id,
                    addresses=_cw_addrs,
                    display_name=consumer_id,
                )
                if _uname_result.get("success"):
                    logger.info("[OK] Consumer username '%s' registered", _uname_result.get("username"))
                elif "already" in str(_uname_result.get("error", "")):
                    update_addresses(consumer_id, _cw_addrs)
                    logger.info("[OK] Consumer username already registered, addresses synced")
        except Exception as un_err:
            logger.debug("Consumer username registration (non-fatal): %s", un_err)

        # SOTA 2026: Auto-issue consumer digital card
        try:
            if wallet_manager and hasattr(event_bus, 'get_component'):
                _sync = event_bus.get_component('mobile_sync_server')
                if _sync and hasattr(_sync, '_fintech_get_cards'):
                    _existing_cards = _sync._fintech_get_cards(user_id=consumer_id)
                    if not _existing_cards.get("cards"):
                        import asyncio
                        asyncio.ensure_future(_sync._fintech_issue_card({
                            "user_id": consumer_id,
                            "card_name": f"Kingdom Card ({consumer_id[:8]})",
                        }))
                        logger.info("[OK] Auto-issued digital card for consumer %s", consumer_id)
        except Exception as dc_err:
            logger.debug("Consumer digital card (non-fatal): %s", dc_err)

        # SOTA 2026: Initialize KAIG (KAI Gold) Engine — AI-managed crypto
        try:
            from core.kaig_engine import KAIGEngine
            kaig_engine = KAIGEngine.get_instance(event_bus=event_bus)
            register_component('kaig_engine', kaig_engine)
            logger.info("[OK] KAIG Engine initialized — $KAIG node + treasury + buyback active")
        except Exception as kaig_err:
            logger.debug("KAIG Engine (non-fatal): %s", kaig_err)

        # SOTA 2026: KAIG AutoPilot — CONSUMER mode (read-only updates, auto wallet)
        try:
            from core.kaig_autopilot import KAIGAutoPilot
            kaig_autopilot = KAIGAutoPilot.get_instance(
                event_bus=event_bus, is_creator=False)
            register_component('kaig_autopilot', kaig_autopilot)
            kaig_autopilot.start()
            logger.info("[OK] KAIG AutoPilot CONSUMER mode — read-only + auto wallet")
        except Exception as ap_err:
            logger.debug("KAIG AutoPilot (non-fatal): %s", ap_err)

        # SOTA 2026: KAIG Intelligence Bridge — routes trading/mining profits to wallet
        try:
            from core.kaig_intelligence_bridge import KAIGIntelligenceBridge
            kaig_bridge = KAIGIntelligenceBridge(event_bus=event_bus)
            register_component('kaig_intelligence_bridge', kaig_bridge)
            logger.info("[OK] KAIG Intelligence Bridge — profit routing active")
        except Exception as kb_err:
            logger.debug("KAIG Intelligence Bridge (non-fatal): %s", kb_err)

        # SOTA 2026: Mining Intelligence — AI-optimized mining for consumer
        try:
            from core.mining_intelligence import MiningIntelligence
            mining_intel = MiningIntelligence(event_bus=event_bus)
            register_component('mining_intelligence', mining_intel)
            logger.info("[OK] Mining Intelligence active for consumer")
        except Exception as mi_err:
            logger.debug("Mining Intelligence (non-fatal): %s", mi_err)

        # SOTA 2026: Coin Accumulation Intelligence — smart DCA/accumulation
        try:
            from core.coin_accumulation_intelligence import CoinAccumulationIntelligence
            coin_intel = CoinAccumulationIntelligence(event_bus=event_bus)
            register_component('coin_accumulation_intelligence', coin_intel)
            logger.info("[OK] Coin Accumulation Intelligence active for consumer")
        except Exception as ci_err:
            logger.debug("Coin Accumulation Intelligence (non-fatal): %s", ci_err)

    except Exception as e:
        logger.error("Protection module initialization error: %s", e)

    # ──────────────────────────────────────────────
    # Activate tier-appropriate flags
    # ──────────────────────────────────────────────
    if tier_config:
        activate_consumer_flags(event_bus, tier_config)

    # Setup contacts and wearable from saved config
    setup_emergency_contacts(event_bus, config.get("emergency_contacts", []))
    setup_wearable(event_bus, config.get("wearable", {}))

    # ──────────────────────────────────────────────
    # Launch GUI or headless mode
    # ──────────────────────────────────────────────
    if args.headless:
        logger.info("Running in headless mode (background protection only)")
        print("Kingdom AI Consumer running in background protection mode.")
        print("Press Ctrl+C to stop.")

        # Still voice the manifesto in headless mode
        try:
            from core.manifesto import get_all_voice_segments
            for seg in get_all_voice_segments():
                event_bus.publish("voice.speak", {
                    "text": seg["text"],
                    "priority": seg.get("priority", "high"),
                    "source": "manifesto",
                })
        except Exception as e:
            logger.warning("Voicing manifesto in headless mode: %s", e)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            event_bus.shutdown()
            print("\nKingdom AI Consumer stopped.")
    else:
        # Launch full GUI with manifesto welcome experience
        logger.info("Launching Kingdom AI Consumer GUI...")
        try:
            from PyQt6.QtWidgets import QApplication, QStackedWidget
            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)

            # Check if first launch — show manifesto welcome
            show_welcome = True
            try:
                from gui.qt_frames.manifesto_welcome import ManifestoWelcome
                show_welcome = ManifestoWelcome.should_show_welcome()
            except ImportError:
                show_welcome = False

            from gui.kingdom_main_window_qt import KingdomMainWindow
            main_window = KingdomMainWindow(event_bus=event_bus)
            main_window.initialize()  # Load all 16 tabs + connect event bus
            main_window.setWindowTitle("Kingdom AI — Consumer Edition")

            if show_welcome:
                # Create a container that shows welcome first, then main app
                container = QStackedWidget()
                container.setWindowTitle("Kingdom AI — Welcome to the Kingdom")
                container.setMinimumSize(1200, 800)
                container.setStyleSheet("background-color: #050510;")

                welcome_screen = ManifestoWelcome(parent=container, event_bus=event_bus)

                def _on_welcome_complete():
                    """Transition from welcome to main application."""
                    container.setCurrentWidget(main_window)
                    container.setWindowTitle("Kingdom AI — Consumer Edition")
                    main_window.show()
                    logger.info("[OK] Welcome complete — entering Kingdom AI")

                welcome_screen.welcome_complete.connect(_on_welcome_complete)
                container.addWidget(welcome_screen)
                container.addWidget(main_window)
                container.setCurrentWidget(welcome_screen)
                container.showMaximized()

                # Start the welcome experience
                welcome_screen.start()
                logger.info("[OK] Manifesto welcome experience launched")
            else:
                main_window.show()
                logger.info("[OK] Kingdom AI Consumer GUI launched (returning user)")

            sys.exit(app.exec())

        except ImportError as e:
            logger.error("GUI unavailable: %s — falling back to headless mode", e)
            print(f"GUI unavailable ({e}). Running in headless mode.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                event_bus.shutdown()


if __name__ == "__main__":
    main()
