#!/usr/bin/env python3

"""
ThothAI GUI Integration
Handles proper integration of ThothAI, voice greeting, and API key management with the GUI
"""

import os
import logging
import asyncio
import traceback
from typing import Dict, Any, Optional, List, Union, Literal, Callable

# Import base component
from core.base_component import BaseComponent

# Try to import the GUI managers
try:
    from core.gui_manager import GUIManager
except ImportError:
    GUIManager = None

# Set up logger first for consistent logging
logger = logging.getLogger("ThothGUIIntegration")

# Try to import ThothAI from different possible locations with enhanced fallback mechanism
ThothAI = None  # Initialize to None so we can check if any import succeeds

# First try the standard import paths
for import_path in ["core.thothai.ThothAI", "components.thothai.ThothAI", "utils.thoth.Thoth", "core.thoth.Thoth"]:
    try:
        module_parts = import_path.split('.')
        class_name = module_parts[-1]
        module_path = '.'.join(module_parts[:-1])
        
        # Dynamic import
        module = __import__(module_path, fromlist=[class_name])
        imported_class = getattr(module, class_name)
        
        if class_name == "Thoth":
            ThothAI = imported_class  # Alias Thoth as ThothAI for compatibility
            logger.info(f"Successfully imported {class_name} from {module_path} as ThothAI")
        else:
            ThothAI = imported_class
            logger.info(f"Successfully imported {class_name} from {module_path}")
        
        break  # Exit the loop if import succeeds
    except (ImportError, AttributeError) as e:
        logger.warning(f"Failed to import {import_path}: {e}")

# If standard imports fail, try a more aggressive approach with importlib
if ThothAI is None:
    logger.warning("Standard imports failed. Attempting to locate ThothAI module in filesystem...")
    try:
        import importlib.util
        import sys
        
        # Add additional search paths
        additional_paths = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),  # Parent directory
            os.path.abspath(os.path.dirname(__file__)),  # Current directory
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'components')),  # components directory
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils'))  # utils directory
        ]
        
        # Add paths to sys.path if not already there
        for path in additional_paths:
            if path not in sys.path:
                sys.path.append(path)
        
        # Look for any thothai or thoth module in the directory structure
        for module_name in ["thothai", "thoth"]:
            for base_path in [*additional_paths, *sys.path]:
                if not base_path:
                    continue
                
                # Check different possible locations
                for subdir in ["", "core", "components", "utils"]:
                    module_path = os.path.join(base_path, subdir, f"{module_name}.py")
                    if os.path.exists(module_path):
                        logger.info(f"Found {module_name} at {module_path}")
                        spec = importlib.util.spec_from_file_location(f"{subdir}.{module_name}", module_path)
                        if spec is None or spec.loader is None:
                            continue
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Get the ThothAI or Thoth class from the module
                        for class_name in ["ThothAI", "Thoth"]:
                            if hasattr(module, class_name):
                                ThothAI = getattr(module, class_name)
                                logger.info(f"Successfully imported {class_name} from {module_path}")
                                break
                        
                        if ThothAI is not None:
                            break
            
            if ThothAI is not None:
                break
    except Exception as e:
        logger.error(f"Failed all attempts to import ThothAI: {e}")
        logger.error(traceback.format_exc())

# Final fallback - create a minimal ThothAI class if we couldn't import it
if ThothAI is None:
    logger.warning("Creating minimal ThothAI implementation for compatibility")
    from core.base_component import BaseComponent
    
    class MinimalThothAI(BaseComponent):
        """Minimal ThothAI implementation for compatibility when the real implementation is not available"""
        
        def __init__(self, event_bus=None, config=None):
            super().__init__(name="MinimalThothAI")
            self._initialized = False
            self._event_bus = event_bus  # Store but don't use in minimal mode
            self._config = config or {}
            logger.warning("Using minimal ThothAI implementation with reduced functionality")
        
        @property
        def initialized(self) -> bool:
            return self._initialized
        
        async def initialize(self):
            logger.info("Initializing minimal ThothAI")
            self._initialized = True
            return True
            
        async def generate_response(self, prompt, **kwargs):
            return "[AI response not available - ThothAI is running in compatibility mode]"
            
        async def generate_code(self, prompt, **kwargs):
            return "# Code generation not available in compatibility mode"
    
    ThothAI = MinimalThothAI

try:
    from core.voice_manager import VoiceManager
    logger.info("Successfully imported VoiceManager")
except ImportError as e:
    logger.warning(f"Failed to import VoiceManager: {e}")
    VoiceManager = None

try:
    from core.api_key_manager import APIKeyManager
except ImportError:
    APIKeyManager = None


class ThothGUIIntegration(BaseComponent):
    """
    ThothAI integration with the GUI
    
    This component ensures that:
    1. ThothAI code generator/chat interface is properly configured
    2. Voice system provides the welcome greeting
    3. API keys are automatically connected from the API envelope
    """
    
    async def gui_output(self, message: str) -> None:
        """Send a message to the GUI asynchronously
        
        Args:
            message: Message to display
        """
        try:
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                if asyncio.iscoroutinefunction(self.event_bus.publish):
                    await self.event_bus.publish("gui.output", {
                        "message": str(message),  # Ensure message is a string
                        "component": "thoth_gui_integration"
                    })
                else:
                    # Synchronous publish
                    self.event_bus.publish("gui.output", {
                        "message": str(message),  # Ensure message is a string
                        "component": "thoth_gui_integration"
                    })
        except Exception as e:
            self.logger.error(f"Error sending GUI output: {e}")
    
    def gui_output_sync(self, message: str) -> None:
        """Send a message to the GUI synchronously
        
        Args:
            message: Message to display
        """
        try:
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                if asyncio.iscoroutinefunction(self.event_bus.publish):
                    # We're in a sync context, create an event loop
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.event_bus.publish("gui.output", {
                        "message": message,
                        "component": "thoth_gui_integration"
                    }))
                else:
                    # Synchronous publish
                    self.event_bus.publish("gui.output", {
                        "message": message,
                        "component": "thoth_gui_integration"
                    })
        except Exception as e:
            self.logger.error(f"Error sending GUI output: {e}")
            
    async def generate_ai_response(self, event_data: Dict[str, Any]) -> bool:
        """Generate an AI response
        
        Args:
            event_data: Event data containing the prompt
            
        Returns:
            bool: Success status
        """
        try:
            if not event_data or 'prompt' not in event_data:
                self.logger.error("No prompt specified for AI response")
                return False
                
            prompt = event_data['prompt']
            system_prompt = event_data.get('system_prompt', None)
            
            if not self.thoth_initialized or self.thoth_ai is None:
                thoth_result = await self._initialize_thoth_async()
                if not thoth_result:
                    self.logger.error("Could not initialize ThothAI")
                    if self.event_bus:
                        pub = self.event_bus.publish("ai.response", {
                            "success": False,
                            "error": "Could not initialize ThothAI",
                            "request_id": event_data.get('request_id')
                        })
                        if asyncio.iscoroutine(pub):
                            await pub
                    return False
                
            # Generate response using the appropriate method
            self.logger.info(f"Generating AI response for: {prompt[:50]}...")
            
            response = None
            try:
                gen_resp = getattr(self.thoth_ai, 'generate_response', None)
                get_comp = getattr(self.thoth_ai, 'get_completion', None)
                if gen_resp and callable(gen_resp):
                    if asyncio.iscoroutinefunction(gen_resp):
                        response = await gen_resp(prompt, **({'system_prompt': system_prompt} if system_prompt else {}))
                    else:
                        response = gen_resp(prompt, **({'system_prompt': system_prompt} if system_prompt else {}))
                elif get_comp and callable(get_comp):
                    if asyncio.iscoroutinefunction(get_comp):
                        response = await get_comp(prompt, **({'system_prompt': system_prompt} if system_prompt else {}))
                    else:
                        response = get_comp(prompt, **({'system_prompt': system_prompt} if system_prompt else {}))
                else:
                    self.logger.error("ThothAI does not have generate_response or get_completion method")
                    if self.event_bus:
                        pub = self.event_bus.publish("ai.response", {
                            "success": False,
                            "error": "ThothAI cannot generate responses",
                            "request_id": event_data.get('request_id')
                        })
                        if asyncio.iscoroutine(pub):
                            await pub
                    return False
            except Exception as e:
                self.logger.error(f"Error generating response: {e}")
                if self.event_bus:
                    pub = self.event_bus.publish("ai.response", {
                        "success": False,
                        "error": str(e),
                        "request_id": event_data.get('request_id')
                    })
                    if asyncio.iscoroutine(pub):
                        await pub
                return False
                
            # Publish response via event bus
            if self.event_bus and response:
                pub = self.event_bus.publish("ai.response", {
                    "success": True,
                    "response": response,
                    "request_id": event_data.get('request_id')
                })
                if asyncio.iscoroutine(pub):
                    await pub
                return True
            return False
                
        except Exception as e:
            self.logger.error(f"Error generating AI response: {e}")
            if self.event_bus:
                pub = self.event_bus.publish("ai.response", {
                    "success": False,
                    "error": str(e),
                    "request_id": event_data.get('request_id')
                })
                if asyncio.iscoroutine(pub):
                    await pub
            return False
            
    async def initialize_component(self, event_data: Dict[str, Any] = None) -> bool:
        """Initialize a component by its name
        
        Args:
            event_data: Event data containing the component name
            
        Returns:
            bool: Success status
        """
        try:
            if not event_data or 'component' not in event_data:
                self.logger.error("No component specified for initialization")
                return False
                
            component_name = event_data['component'].lower()
            
            if component_name == 'thoth' or component_name == 'ai':
                return await self._initialize_thoth_async()
            elif component_name == 'voice':
                return await self._initialize_voice_manager_async()
            elif component_name == 'api_keys' or component_name == 'keys':
                return await self._initialize_api_key_manager_async()
            else:
                self.logger.warning(f"Unknown component: {component_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error initializing component: {e}")
            self.logger.exception(e)
            return False
            
    def __init__(self, gui_manager=None, **kwargs):
        """
        Initialize the ThothAI GUI integration
        
        Args:
            gui_manager: The GUI manager instance
            **kwargs: Configuration parameters
        """
        # Create logger before calling super().__init__ to ensure we have it available
        self.logger = logging.getLogger(__name__)
        
        # Call parent constructor with component name and event bus
        super().__init__("ThothGUIIntegration", kwargs.get('event_bus', None))
        
        # Track initialization state
        self._is_initializing = False
        
        # Store configuration
        self.config = {
            'auto_initialize': True,  # Initialize components on startup
            'greeting_enabled': True,  # Whether to play greeting on startup
            'auto_connect_api_keys': True,  # Auto-connect API keys from envelope
            'greeting_text': "Welcome to Kingdom A.I. How may I assist you?",
            'voice_enabled': True,  # Whether to use voice for greeting
            'model': "llama2",  # Default model to use
            'ollama_url': "http://localhost:11434"  # Default Ollama URL
        }
        
        # Update with provided configuration
        if 'config' in kwargs and isinstance(kwargs['config'], dict):
            self.config.update(kwargs['config'])
            
        # Setup components
        self.gui_manager = gui_manager
        self.thoth_ai = None
        self.voice_manager = None
        self.api_key_manager = None
        
        # Initialization status
        self.thoth_initialized = False
        self._events_subscribed = False
        self.voice_initialized = False
        self.api_keys_initialized = False
        self.is_initializing = False  # Flag to track initialization state
        
        self.logger.info("ThothGUI integration component initialized")
        self.logger.debug(f"Configuration: {self.config}")
    
    async def initialize(self) -> Literal[True]:
        """
        Initialize the ThothAI GUI integration component.
        
        Returns:
            Literal[True]: Always returns True per BaseComponent contract
        """
        if hasattr(self, 'is_initializing') and self.is_initializing:
            self.logger.warning("ThothAI GUI integration is already initializing")
            # Always return True per BaseComponent contract
            return True
        
        self.is_initializing = True
        
        self.logger.info("Initializing ThothAI GUI integration...")
        
        try:
            # Verify we have all required attributes before proceeding
            if not hasattr(self, 'event_bus') or self.event_bus is None:
                self.logger.warning("No event bus available for ThothAI GUI integration")
                # Continue initialization without event bus
            
            # Register for events - safely handle this in case register_for_events is None or not a coroutine
            try:
                if hasattr(self, 'register_for_events') and callable(self.register_for_events):
                    if asyncio.iscoroutinefunction(self.register_for_events):
                        events_result = await self.register_for_events()
                    else:
                        self.register_for_events()
                else:
                    self.logger.warning("No register_for_events method available")
            except Exception as e:
                self.logger.error(f"Error registering for events: {e}")
            
            # Initialize components in sequence with proper error handling
            # Load API keys first - safely handle in case method is None
            if hasattr(self, '_initialize_api_key_manager_async') and callable(self._initialize_api_key_manager_async):
                try:
                    api_key_result = await self._initialize_api_key_manager_async()
                    self.logger.info(f"API Key Manager initialized: {api_key_result}")
                except Exception as e:
                    self.logger.error(f"Error initializing API Key Manager: {e}")
                    api_key_result = False
            else:
                self.logger.warning("No _initialize_api_key_manager_async method available")
                api_key_result = False
            
            # Then initialize Thoth - safely handle in case method is None
            if hasattr(self, '_initialize_thoth_async') and callable(self._initialize_thoth_async):
                try:
                    thoth_result = await self._initialize_thoth_async()
                    self.logger.info(f"Thoth initialized: {thoth_result}")
                except Exception as e:
                    self.logger.error(f"Error initializing Thoth: {e}")
                    thoth_result = False
            else:
                self.logger.warning("No _initialize_thoth_async method available")
                thoth_result = False
            
            # Then initialize voice manager - safely handle in case method is None
            if hasattr(self, '_initialize_voice_manager_async') and callable(self._initialize_voice_manager_async):
                try:
                    voice_result = await self._initialize_voice_manager_async()
                    self.logger.info(f"Voice Manager initialized: {voice_result}")
                except Exception as e:
                    self.logger.error(f"Error initializing Voice Manager: {e}")
                    voice_result = False
            else:
                self.logger.warning("No _initialize_voice_manager_async method available")
                voice_result = False
            
            # Wait for GUI to be ready before playing greeting
            if self.event_bus and hasattr(self.event_bus, 'subscribe') and callable(self.event_bus.subscribe) and not self._events_subscribed:
                try:
                    subscribe_result = self.event_bus.subscribe_sync("gui.update", self.handle_gui_update)
                    if asyncio.iscoroutine(subscribe_result):
                        await subscribe_result
                except Exception as e:
                    self.logger.error(f"Error subscribing to gui.update: {e}")
            
            self.logger.info("ThothAI GUI integration initialized")
            # Always return True per BaseComponent contract
            
        except Exception as e:
            self.logger.error(f"Error initializing ThothAI GUI integration: {e}")
            
        self.is_initializing = False
        self.is_initializing_result = True
        return True
    
    def initialize_sync(self) -> Literal[True]:
        """Initialize the ThothAI GUI integration synchronously
        
        Returns:
            bool: True if initialization is successful, False otherwise
        """
        self.logger.info("Initializing ThothAI GUI integration (sync)...")
        
        try:
            # Subscribe to events
            self.subscribe_to_events_sync()
            
            # Initialize ThothAI
            # Initialize ThothAI - handle async vs sync properly
            thoth_init_result = self._initialize_thoth_async()
            if asyncio.iscoroutine(thoth_init_result):
                # Create a new event loop if needed
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    thoth_init_success = loop.run_until_complete(thoth_init_result)
                except Exception as e:
                    self.logger.error(f"Error running ThothAI initialization: {e}")
                    thoth_init_success = False
            else:
                thoth_init_success = thoth_init_result
                
            if not thoth_init_success:
                self.logger.warning("Failed to initialize ThothAI - continuing without ThothAI")
            
            # Initialize voice manager - handle coroutines if needed
            voice_init_result = self._initialize_voice_manager_async()
            if asyncio.iscoroutine(voice_init_result):
                try:
                    loop = asyncio.get_event_loop()
                    voice_init_success = loop.run_until_complete(voice_init_result)
                except Exception as e:
                    self.logger.error(f"Error running voice initialization: {e}")
                    voice_init_success = False
            else:
                voice_init_success = voice_init_result
                
            if not voice_init_success:
                self.logger.warning("Failed to initialize Voice Manager - continuing without voice")
            
            # Initialize API key manager - handle coroutines if needed
            api_init_result = self._initialize_api_key_manager_async()
            if asyncio.iscoroutine(api_init_result):
                try:
                    loop = asyncio.get_event_loop()
                    api_init_success = loop.run_until_complete(api_init_result)
                except Exception as e:
                    self.logger.error(f"Error running API key initialization: {e}")
                    api_init_success = False
            else:
                api_init_success = api_init_result
                
            if not api_init_success:
                self.logger.warning("Failed to initialize API Key Manager - continuing without API auto-connection")
            
            # Subscribe to GUI events for greeting (guard against duplicates)
            if self.event_bus and not self._events_subscribed:
                if hasattr(self.event_bus, 'subscribe'):
                    subscribe_result = self.event_bus.subscribe_sync("gui.update", self.handle_gui_update)
                    if asyncio.iscoroutine(subscribe_result):
                        loop = asyncio.get_event_loop()
                        loop.run_until_complete(subscribe_result)
            
            self.logger.info("ThothAI GUI integration initialized (sync)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing ThothGUIIntegration: {e}")
            self.logger.exception(e)
            
        return True
    
    async def _initialize_thoth_async(self) -> bool:
        """Initialize Thoth AI asynchronously
        
        Returns:
            bool: True if initialized successfully, False otherwise
        """
        self.logger.info("Initializing ThothAI asynchronously...")
        
        try:
            # Import ThothAI with fallback mechanisms
            try:
                from thothai import ThothAI
            except ImportError:
                try:
                    from thoth_gui_integration.thothai import ThothAI
                except ImportError:
                    # Use minimal fallback implementation
                    ThothAI = MinimalThothAI
            
            if not ThothAI:
                self.logger.error("ThothAI module not available")
                return False
                
            # Initialize ThothAI with event_bus and config
            self.thoth_ai = ThothAI(self.event_bus, self.config)  # type: ignore[call-arg]
            self.thoth_initialized = True
            self.logger.info("ThothAI initialized successfully")

            # After the conversational ThothAI is online, ensure the trading
            # ThothLiveIntegration backend is also initialized in this same
            # process so that TradingTab and other panels can access a
            # 'thoth_ai' component via EventBus.get_component("thoth_ai").
            try:
                await self._initialize_thoth_live_backend()
            except Exception as live_err:  # noqa: BLE001
                self.logger.error(f"Error initializing Thoth live backend: {live_err}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing ThothAI: {e}")
            return False

    async def _initialize_thoth_live_backend(self) -> None:
        """Initialize ThothLiveIntegration and register it as 'thoth_ai'.

        This connects the Ollama brain to ALL live trading/blockchain systems
        inside the same process as the GUI, then exposes the resulting
        ThothLiveIntegration instance via the EventBus component registry so
        TradingTab._connect_to_central_brain can retrieve it.
        """

        # Guard against double-initialization
        if getattr(self, "_thoth_live_initialized", False):
            return

        try:
            from core.event_bus import EventBus
            from initialize_thoth_live import initialize_thoth_with_all_live_systems
        except Exception:
            self.logger.warning(
                "Thoth live integration modules not available; "
                "skipping ThothLiveIntegration backend initialization"
            )
            return

        # Resolve the event bus used by the GUI/Thoth systems.
        bus = getattr(self, "event_bus", None)
        if bus is None:
            try:
                bus = EventBus.get_instance()
            except Exception:
                bus = None

        if bus is None:
            self.logger.warning("No EventBus instance available for ThothLiveIntegration; skipping")
            return

        # Extract API keys from the APIKeyManager if it is present.
        api_keys = {}
        try:
            manager = getattr(self, "api_key_manager", None)
            if manager is not None:
                api_keys = getattr(manager, "api_keys", {}) or {}
        except Exception:
            api_keys = {}

        # Initialize ThothLiveIntegration with all live systems.
        thoth_live = await initialize_thoth_with_all_live_systems(bus, api_keys)
        if thoth_live is None:
            # SOTA 2026 FIX: ThothLive is optional - use debug not warning
            self.logger.debug("ℹ️ ThothLiveIntegration initialization returned None (optional feature)")
            return

        # Register as 'thoth_ai' so TradingTab and other tabs can access the
        # full live trading brain via EventBus.get_component('thoth_ai').
        if hasattr(bus, "register_component"):
            try:
                bus.register_component("thoth_ai", thoth_live)
                self.logger.info("✅ Registered ThothLiveIntegration as 'thoth_ai' on EventBus")
            except Exception as reg_err:  # noqa: BLE001
                self.logger.error(f"Error registering ThothLiveIntegration on EventBus: {reg_err}")

        self._thoth_live_initialized = True
    
    def _initialize_thoth_sync(self) -> bool:
        """Initialize Thoth AI synchronously
        
        Returns:
            bool: True if initialized successfully
        """
        self.logger.info("Initializing ThothAI synchronously...")
        
        if not ThothAI:
            self.logger.error("ThothAI module not available")
            self.gui_output_sync("Error: ThothAI module not found")
            return False
            
        try:
            # Setup ThothAI configuration
            thoth_config = {
                'model': self.config.get('model', 'llama2'),
                'ollama_url': self.config.get('ollama_url', 'http://localhost:11434')
            }
            
            # Initialize ThothAI with event_bus and config
            self.thoth_ai = ThothAI(self.event_bus, thoth_config)  # type: ignore[call-arg]
            
            # Initialize ThothAI
            if hasattr(self.thoth_ai, 'initialize') and callable(getattr(self.thoth_ai, 'initialize')):
                if asyncio.iscoroutinefunction(self.thoth_ai.initialize):
                    # We're in a sync context, create an event loop
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    init_success = loop.run_until_complete(self.thoth_ai.initialize())
                else:
                    init_success = self.thoth_ai.initialize()
                    
                if not init_success:
                    self.logger.error("Failed to initialize ThothAI")
                    self.gui_output_sync("Error: Failed to initialize ThothAI")
                    return False
            
            self.thoth_initialized = True
            self.logger.info("ThothAI initialized successfully")
            self.gui_output_sync("ThothAI initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing ThothAI: {e}")
            self.logger.error(traceback.format_exc())
            self.gui_output_sync(f"Error initializing ThothAI: {str(e)}")
            return False
    
    async def _initialize_voice_manager_async(self) -> bool:
        """Initialize Voice Manager asynchronously
        
        Returns:
            bool: True if initialized successfully
        """
        try:
            if self.event_bus is not None and hasattr(self.event_bus, "get_component"):
                existing = self.event_bus.get_component("voice_manager", silent=True)
                if existing is not None:
                    self.voice_manager = existing
                    self.voice_initialized = True
                    return True
        except Exception:
            pass

        if VoiceManager is None:
            # SOTA 2026 FIX: Voice is optional - use debug not warning
            self.logger.debug("ℹ️ VoiceManager not available (optional feature)")
            return False

        self.voice_manager = VoiceManager(event_bus=self.event_bus)

        result: bool
        if hasattr(self.voice_manager, 'initialize') and asyncio.iscoroutinefunction(self.voice_manager.initialize):
            result = bool(await self.voice_manager.initialize())
        elif hasattr(self.voice_manager, 'initialize_sync') and callable(getattr(self.voice_manager, 'initialize_sync', None)):
            result = bool(self.voice_manager.initialize_sync())
        elif hasattr(self.voice_manager, 'initialize') and callable(getattr(self.voice_manager, 'initialize', None)):
            init_out = self.voice_manager.initialize()
            result = True if init_out is None else bool(init_out)
        else:
            result = True

        try:
            if self.event_bus is not None and hasattr(self.event_bus, "register_component"):
                self.event_bus.register_component("voice_manager", self.voice_manager)
        except Exception:
            pass

        self.voice_initialized = result
        return result
    
    async def _initialize_api_key_manager_async(self) -> bool:
        """Initialize API Key Manager asynchronously
        
        Returns:
            bool: True if initialized successfully, False otherwise
        """
        # Create API Key Manager instance
        self.api_key_manager = APIKeyManager(event_bus=self.event_bus)
        
        # Initialize API Key Manager
        if hasattr(self.api_key_manager, 'initialize') and asyncio.iscoroutinefunction(self.api_key_manager.initialize):
            return await self.api_key_manager.initialize()
        else:
            return self.api_key_manager.initialize_sync()
    
    async def play_welcome_greeting(self) -> bool:
        """Play the welcome greeting using voice manager
        
        Returns:
            bool: True if the greeting was played successfully, False otherwise
        """
        # ThothQt._show_welcome_greeting() handles type+speak (single source of truth)
        self.logger.info("Greeting delegated to ThothQt (unified type+speak)")
        return True
            
    async def greet_user(self) -> bool:
        """Greet the user using voice or by sending a text message.
        
        This is called by kingdomkeys.py during initialization.
        
        Returns:
            bool: True if greeting was successful, False otherwise
        """
        self.logger.info("Greeting user...")
        
        try:
            # First try with voice greeting
            voice_greeting_success = await self.play_welcome_greeting()
            
            # If voice greeting failed, try text greeting via event bus
            if not voice_greeting_success and self.event_bus:
                self.logger.info("Voice greeting failed, sending text greeting")
                greeting_text = "Kingdom AI system is now fully initialized and operational."
                
                # Send system message to UI
                if asyncio.iscoroutinefunction(self.event_bus.publish):
                    await self.event_bus.publish("system.message", {
                        "message": greeting_text,
                        "type": "greeting",
                        "sender": "system"
                    })
                else:
                    self.event_bus.publish("system.message", {
                        "message": greeting_text,
                        "type": "greeting",
                        "sender": "system"
                    })
                
                # Also send to chat if there's a chat interface
                if asyncio.iscoroutinefunction(self.event_bus.publish):
                    await self.event_bus.publish("gui.chat.message", {
                        "message": greeting_text,
                        "sender": "KingdomAI"
                    })
                else:
                    self.event_bus.publish("gui.chat.message", {
                        "message": greeting_text,
                        "sender": "KingdomAI"
                    })
                
                return True
                
            return voice_greeting_success
        except Exception as e:
            self.logger.error(f"Error greeting user: {e}")
            return False
    
    async def subscribe_to_events(self):
        """Subscribe to events asynchronously"""
        # Register for events
        if self.event_bus:
            if hasattr(self.event_bus, 'subscribe'):
                if self._events_subscribed:
                    self.logger.debug("Events already subscribed -- skipping duplicate")
                    return
                sub_method = getattr(self.event_bus, 'subscribe', None)
                if sub_method and asyncio.iscoroutinefunction(sub_method):
                    await sub_method('system.thoth.request', self.handle_thoth_request)
                    await sub_method('system.status', self.handle_system_status)
                    await sub_method('system.error', self.handle_system_error)
                    await sub_method('gui.update', self.handle_gui_update)
                    await sub_method('system.health.check', self.handle_health_check)
                    self.logger.debug("Subscribed to events asynchronously")
                else:
                    self.event_bus.subscribe_sync('system.thoth.request', self.handle_thoth_request)
                    self.event_bus.subscribe_sync('system.status', self.handle_system_status)
                    self.event_bus.subscribe_sync('system.error', self.handle_system_error)
                    self.event_bus.subscribe_sync('gui.update', self.handle_gui_update)
                    self.event_bus.subscribe_sync('system.health.check', self.handle_health_check)
                    self.logger.debug("Subscribed to events synchronously (from async method)")
                self._events_subscribed = True
            else:
                self.logger.warning("Event bus does not have subscribe method")
            
    def subscribe_to_events_sync(self):
        """Subscribe to events synchronously (single subscription, guarded)"""
        if self._events_subscribed:
            self.logger.debug("Events already subscribed -- skipping duplicate sync path")
            return
        if self.event_bus:
            sub = getattr(self.event_bus, 'subscribe_sync', None) or self.event_bus.subscribe
            sub('system.thoth.request', self.handle_thoth_request)
            sub('system.status', self.handle_system_status)
            sub('system.error', self.handle_system_error)
            sub('gui.update', self.handle_gui_update)
            sub('system.health.check', self.handle_health_check)
            self._events_subscribed = True
            self.logger.debug("Subscribed to events synchronously (single path)")
    
    async def handle_system_status(self, event):
        """Handle system status events
        
        Args:
            event: The event object
        """
        try:
            if not event.data:
                return
                
            status = event.data.get('status')
            component = event.data.get('component')
            
            if status == 'ready' and component == 'system':
                self.logger.info("System ready - initializing ThothAI components")
                
                # Ensure all components are initialized
                tasks = []
                
                if not self.thoth_initialized:
                    tasks.append(self._initialize_thoth_async())
                    
                if not self.voice_initialized:
                    tasks.append(self._initialize_voice_manager_async())
                    
                if not self.api_keys_initialized:
                    tasks.append(self._initialize_api_key_manager_async())
                
                # Execute all initialization tasks in parallel
                if tasks:
                    await asyncio.gather(*tasks)
                
        except Exception as e:
            self.logger.error(f"Error handling system status: {e}")
    
    async def handle_system_error(self, event):
        """Handle system error events
        
        Args:
            event: The event object
        """
        try:
            if not event.data:
                return
                
            error = event.data.get('error')
            component = event.data.get('component')
            
            if component in ['thoth_ai', 'voice_manager', 'api_key_manager']:
                self.logger.error(f"ThothGUI Integration component error: {component} - {error}")
        except Exception as e:
            self.logger.error(f"Error handling system error: {e}")
    
    async def handle_gui_update(self, event):
        """Handle GUI update events
        
        Args:
            event: The event object
        """
        try:
            if not event.data:
                return
                
            status = event.data.get('status')
            
            # Play welcome greeting when main GUI is shown
            if status == 'main_gui_shown':
                self.logger.info("Main GUI shown - playing welcome greeting")
                await self.play_welcome_greeting()
            
        except Exception as e:
            self.logger.error(f"Error handling GUI update: {e}")
    
    async def handle_thoth_request(self, event):
        """Handle ThothAI request events
        
        Args:
            event: The event object
        """
        try:
            if not event.data:
                return
                
            request_type = event.data.get('type')
            content = event.data.get('content')
            
            if not self.thoth_ai:
                self.logger.warning(f"Cannot handle ThothAI request: ThothAI not initialized")
                return
            
            if request_type == 'code_generation':
                self.logger.info(f"Processing code generation request: {content[:50]}...")
                # Forward to ThothAI
                response = None
                
                gen_code = getattr(self.thoth_ai, 'generate_code', None)
                gen_method = getattr(self.thoth_ai, 'generate', None)
                get_comp = getattr(self.thoth_ai, 'get_completion', None)
                
                if gen_code and callable(gen_code):
                    response = await gen_code(content) if asyncio.iscoroutinefunction(gen_code) else gen_code(content)
                # Fallback to generate method if available
                elif gen_method and callable(gen_method):
                    response = await gen_method(content, context={"type": "code_generation"}) if asyncio.iscoroutinefunction(gen_method) else gen_method(content, context={"type": "code_generation"})
                # Fallback to standard interface
                elif get_comp and callable(get_comp):
                    response = await get_comp(content, **{"system_prompt": "Generate code based on the following requirements."}) if asyncio.iscoroutinefunction(get_comp) else get_comp(content, **{"system_prompt": "Generate code based on the following requirements."})
                
                if response:
                    # Publish response
                    if self.event_bus:
                        pub = self.event_bus.publish("thoth.response", {
                            "type": "code_generation",
                            "content": response,
                            "request_id": event.data.get('request_id')
                        })
                        if asyncio.iscoroutine(pub):
                            await pub
                else:
                    self.logger.error("Failed to generate code - no compatible method found in ThothAI implementation")
            
            elif request_type == 'chat':
                self.logger.info(f"Processing chat request: {content[:50]}...")
                # Forward to ThothAI
                gen_resp = getattr(self.thoth_ai, 'generate_response', None)
                if gen_resp and callable(gen_resp):
                    response = await gen_resp(content) if asyncio.iscoroutinefunction(gen_resp) else gen_resp(content)
                    
                    # Publish response
                    if self.event_bus:
                        pub = self.event_bus.publish("thoth.response", {
                            "type": "chat",
                            "content": response,
                            "request_id": event.data.get('request_id')
                        })
                        if asyncio.iscoroutine(pub):
                            await pub
        
        except Exception as e:
            self.logger.error(f"Error handling ThothAI request: {e}")
            
    async def register_for_events(self) -> bool:
        """Register for all events"""
        if not self.event_bus:
            self.logger.warning("No event bus available for registering events")
            return False
            
        # UI events
        self.event_bus.subscribe_sync("gui.thoth.command", self.run_ai_command)
        
        # Register for additional component methods
        self.event_bus.subscribe_sync("thoth.run_command", self.run_ai_command)
        self.event_bus.subscribe_sync("thoth.voice_command", self.run_voice_command)
        self.event_bus.subscribe_sync("thoth.generate_response", self.generate_ai_response)
        self.event_bus.subscribe_sync("thoth.initialize_component", self.initialize_component)
        self.event_bus.subscribe_sync("thoth.voice_say", self.voice_say_text)
        self.event_bus.subscribe_sync("gui.voice.command", self.run_voice_command)
        
        # AI events
        self.event_bus.subscribe_sync("ai.generate", self.generate_ai_response)
        
        # Initialization events
        self.event_bus.subscribe_sync("system.initialize.component", self.initialize_component)
        
        # Voice events
        self.event_bus.subscribe_sync("voice.welcome", self.play_welcome_greeting)
        
        # system.health.check already subscribed via subscribe_to_events path
        
        self.logger.info("ThothAI GUI integration registered for all events")
        return True
    
    async def voice_say_text(self, event_data: Dict[str, Any]) -> bool:
        """Say text using voice manager
        
        Args:
            event_data: Event data containing the text to say
            
        Returns:
            bool: Success status
        """
        try:
            if not self.voice_initialized or self.voice_manager is None:
                self.logger.warning("Voice manager not initialized")
                await self._initialize_voice_manager_async()
                
            if not self.voice_initialized or self.voice_manager is None:
                self.logger.error("Could not initialize voice manager")
                return False
                
            text = event_data.get("text", "")
            if not text:
                self.logger.warning("No text provided for voice")
                return False

            if self.event_bus and hasattr(self.event_bus, 'publish'):
                self.event_bus.publish("voice.speak", {
                    "text": text,
                    "source": "thoth_gui_integration",
                })
                return True

            self.logger.error("No event bus available for voice output")
            return False
            
        except Exception as e:
            self.logger.error(f"Error saying text: {e}")
            return False
    
    async def run_voice_command(self, event_data: Dict[str, Any]) -> bool:
        """Run a voice command
        
        Args:
            event_data: Event data containing the command and parameters
            
        Returns:
            bool: Success status
        """
        try:
            if not event_data or 'command' not in event_data:
                self.logger.error("No command specified for voice")
                await self.gui_output("Error: No command specified for voice")
                return False
                
            command = event_data['command'].lower()
            params = event_data.get('params', {})
            
            if not self.voice_initialized or self.voice_manager is None:
                await self._initialize_voice_manager_async()
                
            if not self.voice_initialized or self.voice_manager is None:
                self.logger.error("Could not initialize Voice Manager")
                await self.gui_output("Error: Could not initialize Voice Manager")
                return False
                
            # Process voice command
            if command == 'say':
                if 'text' not in params:
                    self.logger.error("No text provided for voice 'say' command")
                    return False
                    
                await self.gui_output(f"Saying: {params['text']}")
                
                say_method = getattr(self.voice_manager, 'say', None)
                if say_method and callable(say_method):
                    if asyncio.iscoroutinefunction(say_method):
                        await say_method(params['text'])
                    else:
                        say_method(params['text'])
                    return True
                else:
                    self.logger.error("Voice Manager does not have say method")
                    return False
            elif command == 'speak':
                if 'text' not in params:
                    self.logger.error("No text provided for voice 'speak' command")
                    return False
                    
                await self.gui_output(f"Speaking: {params['text']}")
                
                if hasattr(self.voice_manager, 'speak') and callable(getattr(self.voice_manager, 'speak')):
                    if asyncio.iscoroutinefunction(self.voice_manager.speak):
                        await self.voice_manager.speak(params['text'])
                    else:
                        self.voice_manager.speak(params['text'])
                    return True
                else:
                    self.logger.error("Voice Manager does not have speak method")
                    return False
                    
            self.logger.warning(f"Unknown voice command: {command}")
            return False
                
        except Exception as e:
            self.logger.error(f"Error running voice command: {e}")
            await self.gui_output(f"Error: {str(e)}")
            return False

    async def run_ai_command(self, event_data: Dict[str, Any]) -> bool:
        """Run an AI command
        
        Args:
            event_data: Event data containing the command and parameters
            
        Returns:
            bool: Success status
        """
        try:
            if not event_data or 'command' not in event_data:
                self.logger.error("No command specified for AI")
                await self.gui_output("Error: No command specified for AI")
                return False
                
            command = event_data['command'].lower()
            params = event_data.get('params', {})
            
            if not self.thoth_ai:
                await self._initialize_thoth_async()
                
            if not self.thoth_ai:
                self.logger.error("Could not initialize Thoth AI")
                await self.gui_output("Error: Could not initialize ThothAI")
                return False
                
            # Process command
            if command == 'generate_code':
                if 'prompt' not in params:
                    return False
                    
                await self.gui_output(f"Generating code for: {params['prompt']}...")
                # Use the appropriate method depending on what's available
                gen_code = getattr(self.thoth_ai, 'generate_code', None)
                get_comp = getattr(self.thoth_ai, 'get_completion', None)
                response = None
                
                if gen_code and callable(gen_code):
                    response = await gen_code(params['prompt']) if asyncio.iscoroutinefunction(gen_code) else gen_code(params['prompt'])
                elif get_comp and callable(get_comp):
                    prompt_text = f"Generate code for: {params['prompt']}"
                    kwargs = {"system_prompt": "You are a skilled code generator. Produce concise, well-documented code."}
                    response = await get_comp(prompt_text, **kwargs) if asyncio.iscoroutinefunction(get_comp) else get_comp(prompt_text, **kwargs)
                else:
                    self.logger.error("ThothAI does not have generate_code or get_completion method")
                    await self.gui_output("Error: ThothAI cannot generate code")
                    return False
                await self.gui_output("Code generated:")
                if asyncio.iscoroutine(response):
                    response = await response
                await self.gui_output(str(response) if response else "No response")
                return True
                
            elif command == 'generate':
                if 'prompt' not in params:
                    return False
                    
                await self.gui_output(f"Generating response for: {params['prompt']}...")
                # Use the appropriate method depending on what's available
                gen_method = getattr(self.thoth_ai, 'generate', None)
                get_comp = getattr(self.thoth_ai, 'get_completion', None)
                response = None
                
                if gen_method and callable(gen_method):
                    response = await gen_method(params['prompt']) if asyncio.iscoroutinefunction(gen_method) else gen_method(params['prompt'])
                elif get_comp and callable(get_comp):
                    response = await get_comp(params['prompt']) if asyncio.iscoroutinefunction(get_comp) else get_comp(params['prompt'])
                else:
                    self.logger.error("ThothAI does not have generate or get_completion method")
                    await self.gui_output("Error: ThothAI cannot generate responses")
                    return False
                await self.gui_output("Response:")
                if asyncio.iscoroutine(response):
                    response = await response
                await self.gui_output(str(response) if response else "No response")
                return True
                
            elif command == 'completion':
                if 'prompt' not in params:
                    return False
                    
                await self.gui_output(f"Getting completion for: {params['prompt']}...")
                get_comp = getattr(self.thoth_ai, 'get_completion', None)
                if get_comp and callable(get_comp):
                    response = await get_comp(params['prompt']) if asyncio.iscoroutinefunction(get_comp) else get_comp(params['prompt'])
                    if asyncio.iscoroutine(response):
                        response = await response
                    await self.gui_output("Completion:")
                    await self.gui_output(str(response) if response else "No response")
                    return True
                else:
                    await self.gui_output("Error: ThothAI cannot get completions")
                    return False
            
            self.logger.warning(f"Unknown AI command: {command}")
            return False
                
        except Exception as e:
            self.logger.error(f"Error running AI command: {e}")
            await self.gui_output(f"Error: {str(e)}")
            return False
    
    async def handle_health_check(self, event_data: Optional[Dict[str, Any]] = None) -> None:
        """Handle system health check
        
        Args:
            event_data: Optional event data
        """
        try:
            components_status = {
                "thoth": self.thoth_initialized,
                "voice": self.voice_initialized,
                "api_keys": self.api_keys_initialized
            }
            
            if self.event_bus:
                pub = self.event_bus.publish("system.health.response", {
                    "component": "thoth_gui_integration",
                    "status": "ok",
                    "components": components_status,
                    "request_id": event_data.get('request_id') if event_data else None
                })
                if asyncio.iscoroutine(pub):
                    await pub
                
        except Exception as e:
            self.logger.error(f"Error handling health check: {e}")
            
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the ThothAI GUI integration
        
        Returns:
            Dict[str, Any]: Status information
        """
        return {
            'thoth_initialized': self.thoth_initialized,
            'voice_initialized': self.voice_initialized,
            'api_keys_initialized': self.api_keys_initialized,
            'greeting_enabled': self.config['greeting_enabled'],
            'auto_connect_api_keys': self.config['auto_connect_api_keys']
        }
