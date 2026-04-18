#!/usr/bin/env python3
"""
NemoClaw Integration Setup Script

This script initializes the NemoClaw integration with Kingdom AI,
setting up the bridge, unified router, and security policy manager.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.event_bus import EventBus
from core.nemoclaw_bridge import NemoClawBridge, NemoClawConfig
from core.unified_brain_router import UnifiedBrainRouter
from core.security_policy_manager import SecurityPolicyManager, SecurityLevel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('kingdom_ai.nemoclaw_setup')

async def initialize_nemoclaw_integration():
    """
    Initialize NemoClaw integration with Kingdom AI
    
    This function:
    1. Creates event bus
    2. Initializes NemoClaw bridge
    3. Sets up unified brain router
    4. Configures security policies
    5. Tests the integration
    """
    
    logger.info("=== Starting NemoClaw Integration Setup ===")
    
    # Step 1: Create event bus
    logger.info("Step 1: Creating event bus...")
    event_bus = EventBus()
    event_bus.start()
    logger.info("✅ Event bus created and started")
    
    # Step 2: Initialize NemoClaw bridge
    logger.info("Step 2: Initializing NemoClaw bridge...")
    
    # Configure NemoClaw (customize these values based on your setup)
    nemoclaw_config = NemoClawConfig(
        sandbox_name="kingdom-ai-assistant",  # Change this to your sandbox name
        use_cli=True,
        timeout_seconds=300,
        max_retries=3,
        enable_logging=True
    )
    
    nemoclaw_bridge = NemoClawBridge(event_bus, nemoclaw_config)
    nemoclaw_available = await nemoclaw_bridge.initialize()
    
    if nemoclaw_available:
        logger.info("✅ NemoClaw bridge initialized successfully")
        logger.info(f"   Sandbox: {nemoclaw_config.sandbox_name}")
        logger.info(f"   Status: {nemoclaw_bridge.sandbox_status}")
    else:
        logger.warning("⚠️  NemoClaw not available - will use Ollama only")
        logger.warning("   Run 'nemoclaw onboard' to set up NemoClaw")
    
    # Step 3: Initialize security policy manager
    logger.info("Step 3: Initializing security policy manager...")
    security_manager = SecurityPolicyManager()
    
    # Customize security policies if needed
    # security_manager.set_policy(TaskCategory.CODE_EXECUTION, SecurityLevel.CRITICAL)
    # security_manager.set_policy(TaskCategory.FINANCIAL, SecurityLevel.HIGH)
    
    logger.info("✅ Security policy manager initialized")
    logger.info(f"   Policies: {len(security_manager.policies)}")
    
    # Step 4: Initialize unified brain router
    logger.info("Step 4: Initializing unified brain router...")
    
    # Import Ollama connector if available
    ollama_connector = None
    try:
        from core.thoth_ollama_connector import ThothOllamaConnector
        ollama_connector = ThothOllamaConnector(event_bus)
        await ollama_connector.initialize()
        logger.info("✅ Ollama connector initialized")
    except ImportError:
        logger.warning("⚠️  Ollama connector not available")
    except Exception as e:
        logger.warning(f"⚠️  Ollama initialization failed: {e}")
    
    # Create unified router
    unified_router = UnifiedBrainRouter(
        event_bus,
        ollama_connector=ollama_connector,
        nemoclaw_bridge=nemoclaw_bridge if nemoclaw_available else None
    )
    
    await unified_router.initialize()
    logger.info("✅ Unified brain router initialized")
    
    # Step 5: Test integration
    logger.info("Step 5: Testing integration...")
    
    # Test routing decision
    test_decision = await unified_router._make_routing_decision(
        prompt="Hello, how are you?",
        task_type="chat",
        security_level="standard",
        preferred_backend="auto"
    )
    
    logger.info(f"✅ Test routing decision: {test_decision.backend.value}")
    logger.info(f"   Reason: {test_decision.reason}")
    logger.info(f"   Security level: {test_decision.security_level.value}")
    
    # Step 6: Display status
    logger.info("\n=== Integration Status ===")
    logger.info(f"Event Bus: ✅ Running")
    logger.info(f"NemoClaw: {'✅ Available' if nemoclaw_available else '❌ Not Available'}")
    logger.info(f"Ollama: {'✅ Available' if ollama_connector else '❌ Not Available'}")
    logger.info(f"Unified Router: ✅ Running")
    logger.info(f"Security Policies: ✅ {len(security_manager.policies)} policies")
    
    # Step 7: Save configuration
    logger.info("\n=== Saving Configuration ===")
    
    config_dir = Path.home() / ".kingdom_ai" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Save security policies
    policy_file = config_dir / "security_policies.json"
    security_manager.save_policies_to_file(str(policy_file))
    logger.info(f"✅ Security policies saved to {policy_file}")
    
    # Save integration config
    integration_config = {
        "nemoclaw": {
            "available": nemoclaw_available,
            "sandbox_name": nemoclaw_config.sandbox_name,
            "use_cli": nemoclaw_config.use_cli
        },
        "ollama": {
            "available": ollama_connector is not None
        },
        "security_policies": security_manager.get_policy_summary(),
        "timestamp": str(asyncio.get_event_loop().time())
    }
    
    import json
    config_file = config_dir / "nemoclaw_integration.json"
    with open(config_file, 'w') as f:
        json.dump(integration_config, f, indent=2)
    logger.info(f"✅ Integration config saved to {config_file}")
    
    logger.info("\n=== NemoClaw Integration Setup Complete ===")
    logger.info("\nNext Steps:")
    logger.info("1. Use the unified router in your main application")
    logger.info("2. Customize security policies as needed")
    logger.info("3. Add UI controls for backend selection")
    logger.info("4. Test with real requests")
    
    # Keep event bus running for a moment to process events
    await asyncio.sleep(2)
    
    # Stop event bus
    event_bus.stop()
    logger.info("Event bus stopped")
    
    return {
        "success": True,
        "nemoclaw_available": nemoclaw_available,
        "ollama_available": ollama_connector is not None,
        "config_saved": True
    }

def main():
    """Main entry point"""
    try:
        result = asyncio.run(initialize_nemoclaw_integration())
        
        if result["success"]:
            print("\n✅ NemoClaw integration setup completed successfully!")
            print(f"   NemoClaw: {'Available' if result['nemoclaw_available'] else 'Not Available'}")
            print(f"   Ollama: {'Available' if result['ollama_available'] else 'Not Available'}")
            return 0
        else:
            print("\n❌ NemoClaw integration setup failed")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Setup interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Setup failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
