#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
NLP component for Kingdom AI.

This module connects the existing NLP processor components to the event bus.
"""

import logging
import os
import sys

# Import the existing NLP processor
try:
    from ..kingdom_nlp_processor import NLPProcessor
    NLP_PROCESSOR_AVAILABLE = True
except ImportError:
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from kingdom_nlp_processor import NLPProcessor
        NLP_PROCESSOR_AVAILABLE = True
    except ImportError:
        NLP_PROCESSOR_AVAILABLE = False

from core.base_component import BaseComponent

# Set up logger
logger = logging.getLogger("kingdom_ai")

# Initialization function that 4keys.py expects
async def initialize_nlp_components(event_bus):
    """
    Initialize NLP components and connect them to the event bus.
    
    Args:
        event_bus: Event bus instance for component communication
        
    Returns:
        Dictionary of initialized components
    """
    logger.info("Initializing NLP components")
    components = {}
    
    try:
        # Create a registry adapter since NLPProcessor expects a ComponentRegistry
        component_registry = type("ComponentRegistry", (), {
            "register": lambda comp: None,
            "get_component": lambda name: None,
            "get_all_components": lambda: []
        })()
        
        # Initialize the main NLP processor if available
        if NLP_PROCESSOR_AVAILABLE:
            nlp_processor = NLPProcessor(event_bus=event_bus, registry=component_registry)
            components["nlp_processor"] = nlp_processor
            
            # Attempt to register event handlers
            if hasattr(event_bus, 'register_handler'):
                event_bus.register_handler("nlp.process_text", nlp_processor.process_text)
                event_bus.register_handler("nlp.extract_entities", nlp_processor.extract_entities)
                event_bus.register_handler("nlp.detect_intent", nlp_processor.detect_intent)
            elif hasattr(event_bus, 'subscribe'):
                event_bus.subscribe("nlp.process_text", nlp_processor.process_text)
                event_bus.subscribe("nlp.extract_entities", nlp_processor.extract_entities)
                event_bus.subscribe("nlp.detect_intent", nlp_processor.detect_intent)
                
            logger.info("NLP processor connected to event bus")
        else:
            # Create fallback NLP components
            logger.warning("NLP processor not available, using fallback components")
            
            # Create simple fallback processor
            class FallbackNLPProcessor(BaseComponent):
                def __init__(self, event_bus):
                    super().__init__(event_bus=event_bus)
                    self.name = "FallbackNLPProcessor"
                
                async def process_text(self, event_type, data):
                    text = data.get("text", "")
                    return {"processed": text, "tokens": text.split()}
                    
                async def extract_entities(self, event_type, data):
                    text = data.get("text", "")
                    # Very basic entity extraction
                    entities = []
                    if "bitcoin" in text.lower():
                        entities.append({"type": "CRYPTO", "text": "bitcoin", "value": "BTC"})
                    if "ethereum" in text.lower():
                        entities.append({"type": "CRYPTO", "text": "ethereum", "value": "ETH"})
                    return {"entities": entities}
                    
                async def detect_intent(self, event_type, data):
                    text = data.get("text", "")
                    intent = "unknown"
                    if "price" in text.lower():
                        intent = "price_query"
                    elif "buy" in text.lower():
                        intent = "buy_intent"
                    elif "sell" in text.lower():
                        intent = "sell_intent"
                    return {"intent": intent, "confidence": 0.7}
            
            # Create the fallback processor
            fallback_processor = FallbackNLPProcessor(event_bus=event_bus)
            components["nlp_processor"] = fallback_processor
            
            # Register event handlers for fallback processor
            if hasattr(event_bus, 'register_handler'):
                event_bus.register_handler("nlp.process_text", fallback_processor.process_text)
                event_bus.register_handler("nlp.extract_entities", fallback_processor.extract_entities)
                event_bus.register_handler("nlp.detect_intent", fallback_processor.detect_intent)
            elif hasattr(event_bus, 'subscribe'):
                event_bus.subscribe("nlp.process_text", fallback_processor.process_text)
                event_bus.subscribe("nlp.extract_entities", fallback_processor.extract_entities)
                event_bus.subscribe("nlp.detect_intent", fallback_processor.detect_intent)
                
            logger.info("Fallback NLP processor connected to event bus")
        
        logger.info(f"NLP components initialized with {len(components)} components")
    except Exception as e:
        logger.error(f"Error initializing NLP components: {e}")
    
    return components
