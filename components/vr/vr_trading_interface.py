"""VR Trading Interface - MANDATORY MODULE"""

from core.base_component import BaseComponent
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class VRTradingInterface(BaseComponent):
    """VR interface for immersive trading."""
    
    def __init__(self, event_bus=None, config: Dict[str, Any] = None):
        super().__init__(event_bus=event_bus, config=config or {})
        self.name = "VRTradingInterface"
        logger.info("✅ VRTradingInterface initialized")
    
    async def initialize(self):
        """Initialize VR trading interface."""
        await super().initialize()
        logger.info("✅ VRTradingInterface fully initialized")
