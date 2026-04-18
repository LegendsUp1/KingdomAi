"""OrderRouter - Kingdom AI component.

This component now integrates with the profit-focused LearningOrchestrator via
LiveAutotradePolicy in *advisory* mode. Every incoming order.request is
evaluated against the current paper_profit_view, and the result is logged and
emitted as an ``autotrade.policy.diagnostics`` event without blocking order
processing.
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from core.live_autotrade_policy import LiveAutotradePolicy


class OrderRouter:
    """
    OrderRouter for Kingdom AI system.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the OrderRouter."""
        self.name = "order.orderrouter"
        self.logger = logging.getLogger(f"KingdomAI.OrderRouter")
        self._event_bus = event_bus
        self._config = config or {}
        self.initialized = False
        self._policy: Optional[LiveAutotradePolicy] = None
        self.logger.info("OrderRouter initialized")
    
    @property
    def event_bus(self):
        """Get the event bus."""
        return self._event_bus
    
    @event_bus.setter
    def event_bus(self, bus):
        """Set the event bus."""
        self._event_bus = bus
        if bus:
            self._register_event_handlers()
    
    def set_event_bus(self, bus):
        """Set the event bus and return success."""
        self.event_bus = bus
        return True
    
    def _register_event_handlers(self):
        """Register handlers with the event bus."""
        if not self._event_bus:
            return False
            
        try:
            self._event_bus.subscribe("order.request", self._handle_request)
            self._ensure_policy()
            self.logger.debug(f"Registered event handlers for {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
            return False

    def _ensure_policy(self) -> None:
        """Lazy-initialize LiveAutotradePolicy from the global orchestrator.

        We resolve LearningOrchestrator from the event bus component registry
        when available. If it cannot be found, policy evaluation is skipped but
        order routing continues normally.
        """

        if self._policy is not None:
            return
        orch = None
        if self._event_bus and hasattr(self._event_bus, "get_component"):
            try:
                orch = self._event_bus.get_component("learning_orchestrator")
            except Exception:
                orch = None
        if orch is not None:
            self._policy = LiveAutotradePolicy(
                orchestrator=orch,
                config=self._config.get("live_autotrade_policy") or {},
            )
    
    def _handle_request(self, event_type, data):
        """Handle component requests."""
        self.logger.debug(f"Handling request {event_type}: {data}")

        # Advisory-only policy evaluation against LearningOrchestrator.
        if self._policy is not None:
            try:
                order_info: Dict[str, Any] = dict(data) if isinstance(data, dict) else {}
                decision = self._policy.pre_trade_check(order_info)
                diagnostics = {
                    "origin": self.name,
                    "asset_class": order_info.get("asset_class"),
                    "symbol": order_info.get("symbol"),
                    "market_type": order_info.get("market_type", "unknown"),
                    "strategy_style": order_info.get("strategy_style")
                    or order_info.get("strategy"),
                    "size_fraction": order_info.get("size_fraction", 0.0),
                    "micro_edge_score": order_info.get("micro_edge_score"),
                    "logic_arb_score": order_info.get("logic_arb_score"),
                    "tail_risk_score": order_info.get("tail_risk_score"),
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                self.logger.debug("LiveAutotradePolicy decision: %s", diagnostics)
                if self._event_bus:
                    self._event_bus.publish("autotrade.policy.diagnostics", diagnostics)
                    # Additive advisory event for cross-market logic arbitrage opportunities.
                    try:
                        logic_arb = float(order_info.get("logic_arb_score", 0.0) or 0.0)
                        tail_risk = float(order_info.get("tail_risk_score", 1.0) or 1.0)
                        if logic_arb >= float(self._config.get("logic_arb_signal_min", 0.6)) and tail_risk <= float(self._config.get("tail_risk_max", 0.75)):
                            self._event_bus.publish("market.logic_arb.opportunity", diagnostics)
                    except Exception:
                        pass
            except Exception as e:
                self.logger.error(f"Error running LiveAutotradePolicy: {e}")
        
        if self._event_bus:
            self._event_bus.publish(
                "order.response",
                {
                    "status": "success",
                    "origin": self.name,
                    "data": {"message": "Request processed by OrderRouter"},
                },
            )
        
        return {"status": "success"}
    
    async def initialize(self):
        """Initialize the component asynchronously."""
        self.logger.info(f"Initializing OrderRouter...")
        try:
            # Perform component-specific initialization here
            self.initialized = True
            self.logger.info(f"OrderRouter initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing OrderRouter: {e}")
            return False
    
    def initialize_sync(self):
        """Initialize the component synchronously."""
        self.logger.info(f"Synchronously initializing OrderRouter...")
        try:
            # Perform component-specific initialization here
            self.initialized = True
            self.logger.info(f"OrderRouter synchronous initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error during synchronous initialization: {e}")
            return False