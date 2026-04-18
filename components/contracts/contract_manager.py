"""Contract Manager Component - SOTA 2026 Full Implementation.

Manages smart contracts, trading contracts, and agreement execution.
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import hashlib
import json
import time


class ContractType(Enum):
    """Types of contracts supported."""
    TRADING = "trading"
    SMART_CONTRACT = "smart_contract"
    OPTIONS = "options"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    ESCROW = "escrow"
    CONDITIONAL = "conditional"


class ContractStatus(Enum):
    """Contract lifecycle status."""
    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class Contract:
    """Represents a trading or smart contract."""
    contract_id: str
    contract_type: ContractType
    status: ContractStatus
    created_at: float
    expires_at: Optional[float]
    
    # Parties involved
    parties: List[str] = field(default_factory=list)
    
    # Contract terms
    terms: Dict[str, Any] = field(default_factory=dict)
    
    # Execution conditions
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Actions to take when conditions met
    actions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Execution history
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Contract value/collateral
    value: float = 0.0
    collateral: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContractManager:
    """
    SOTA 2026: Comprehensive contract management system.
    
    Features:
    - Smart contract creation and management
    - Trading contract execution
    - Options/Futures contract handling
    - Conditional order management
    - Contract lifecycle tracking
    - Event-driven execution
    """
    
    def __init__(self, event_bus=None):
        """Initialize Contract Manager.
        
        Args:
            event_bus: Optional event bus for system integration
        """
        self.event_bus = event_bus
        self._initialized = False
        
        # Contract storage
        self.contracts: Dict[str, Contract] = {}
        self.active_contracts: Dict[str, Contract] = {}
        self.pending_contracts: Dict[str, Contract] = {}
        
        # Condition monitors
        self._condition_monitors: Dict[str, Callable] = {}
        self._price_triggers: Dict[str, List[str]] = {}  # symbol -> contract_ids
        
        # Execution queue
        self._execution_queue: List[str] = []
        
        # Statistics
        self.stats = {
            "total_created": 0,
            "total_executed": 0,
            "total_value_processed": 0.0,
            "active_count": 0
        }
        
        # Subscribe to events
        if self.event_bus:
            self._subscribe_to_events()
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant system events."""
        if not self.event_bus:
            return
        
        self.event_bus.subscribe("market.price_update", self._check_price_conditions)
        self.event_bus.subscribe("trading.order.filled", self._handle_order_filled)
        self.event_bus.subscribe("blockchain.transaction_confirmed", self._handle_tx_confirmed)
        self.event_bus.subscribe("contract.execute", self._handle_execute_request)
    
    def initialize(self) -> bool:
        """Initialize the contract manager."""
        try:
            self._initialized = True
            
            if self.event_bus:
                self.event_bus.publish("contract.manager.initialized", {
                    "status": "ready",
                    "supported_types": [t.value for t in ContractType]
                })
            
            return True
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("contract.manager.error", {
                    "error": str(e),
                    "phase": "initialization"
                })
            return False
    
    def create_contract(
        self,
        contract_type: ContractType,
        terms: Dict[str, Any],
        conditions: List[Dict[str, Any]] = None,
        actions: List[Dict[str, Any]] = None,
        parties: List[str] = None,
        expires_in_seconds: Optional[float] = None,
        value: float = 0.0,
        collateral: float = 0.0,
        metadata: Dict[str, Any] = None
    ) -> Optional[Contract]:
        """
        Create a new contract.
        
        Args:
            contract_type: Type of contract
            terms: Contract terms and specifications
            conditions: Conditions that trigger execution
            actions: Actions to execute when conditions met
            parties: Parties involved in contract
            expires_in_seconds: Optional expiration time
            value: Contract value
            collateral: Required collateral
            metadata: Additional metadata
            
        Returns:
            Created Contract or None on failure
        """
        try:
            # Generate unique contract ID
            contract_id = self._generate_contract_id(terms)
            
            # Calculate expiration
            created_at = time.time()
            expires_at = created_at + expires_in_seconds if expires_in_seconds else None
            
            contract = Contract(
                contract_id=contract_id,
                contract_type=contract_type,
                status=ContractStatus.DRAFT,
                created_at=created_at,
                expires_at=expires_at,
                parties=parties or [],
                terms=terms,
                conditions=conditions or [],
                actions=actions or [],
                value=value,
                collateral=collateral,
                metadata=metadata or {}
            )
            
            self.contracts[contract_id] = contract
            self.stats["total_created"] += 1
            
            # Register price triggers if any conditions are price-based
            self._register_price_triggers(contract)
            
            if self.event_bus:
                self.event_bus.publish("contract.created", {
                    "contract_id": contract_id,
                    "type": contract_type.value,
                    "status": contract.status.value,
                    "value": value
                })
            
            return contract
            
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("contract.creation.error", {
                    "error": str(e),
                    "terms": terms
                })
            return None
    
    def _generate_contract_id(self, terms: Dict[str, Any]) -> str:
        """Generate unique contract ID."""
        data = json.dumps(terms, sort_keys=True) + str(time.time())
        return f"CTR-{hashlib.sha256(data.encode()).hexdigest()[:16].upper()}"
    
    def _register_price_triggers(self, contract: Contract) -> None:
        """Register price-based condition triggers."""
        for condition in contract.conditions:
            if condition.get("type") == "price":
                symbol = condition.get("symbol")
                if symbol:
                    if symbol not in self._price_triggers:
                        self._price_triggers[symbol] = []
                    self._price_triggers[symbol].append(contract.contract_id)
    
    def activate_contract(self, contract_id: str) -> bool:
        """
        Activate a contract for monitoring and execution.
        
        Args:
            contract_id: ID of contract to activate
            
        Returns:
            Success status
        """
        if contract_id not in self.contracts:
            return False
        
        contract = self.contracts[contract_id]
        
        # Validate contract can be activated
        if contract.status not in [ContractStatus.DRAFT, ContractStatus.PENDING]:
            return False
        
        # Check collateral if required
        if contract.collateral > 0:
            if not self._verify_collateral(contract):
                contract.status = ContractStatus.PENDING
                self.pending_contracts[contract_id] = contract
                return False
        
        contract.status = ContractStatus.ACTIVE
        self.active_contracts[contract_id] = contract
        self.stats["active_count"] = len(self.active_contracts)
        
        # Log activation
        contract.execution_log.append({
            "action": "activated",
            "timestamp": time.time()
        })
        
        if self.event_bus:
            self.event_bus.publish("contract.activated", {
                "contract_id": contract_id,
                "type": contract.contract_type.value
            })
        
        return True
    
    def _verify_collateral(self, contract: Contract) -> bool:
        """Verify sufficient collateral is available."""
        # In a real implementation, this would check wallet balances
        # For now, assume collateral is verified
        return True
    
    def execute_contract(self, contract_id: str, trigger_data: Dict[str, Any] = None) -> bool:
        """
        Execute a contract.
        
        Args:
            contract_id: ID of contract to execute
            trigger_data: Data that triggered execution
            
        Returns:
            Success status
        """
        if contract_id not in self.contracts:
            return False
        
        contract = self.contracts[contract_id]
        
        if contract.status != ContractStatus.ACTIVE:
            return False
        
        try:
            contract.status = ContractStatus.EXECUTING
            
            # Log execution start
            contract.execution_log.append({
                "action": "execution_started",
                "timestamp": time.time(),
                "trigger_data": trigger_data
            })
            
            # Execute all actions
            for action in contract.actions:
                self._execute_action(contract, action)
            
            # Mark completed
            contract.status = ContractStatus.COMPLETED
            self.stats["total_executed"] += 1
            self.stats["total_value_processed"] += contract.value
            
            # Remove from active
            if contract_id in self.active_contracts:
                del self.active_contracts[contract_id]
                self.stats["active_count"] = len(self.active_contracts)
            
            # Log completion
            contract.execution_log.append({
                "action": "completed",
                "timestamp": time.time()
            })
            
            if self.event_bus:
                self.event_bus.publish("contract.executed", {
                    "contract_id": contract_id,
                    "type": contract.contract_type.value,
                    "value": contract.value,
                    "actions_executed": len(contract.actions)
                })
            
            return True
            
        except Exception as e:
            contract.status = ContractStatus.FAILED
            contract.execution_log.append({
                "action": "failed",
                "timestamp": time.time(),
                "error": str(e)
            })
            
            if self.event_bus:
                self.event_bus.publish("contract.execution.failed", {
                    "contract_id": contract_id,
                    "error": str(e)
                })
            
            return False
    
    def _execute_action(self, contract: Contract, action: Dict[str, Any]) -> None:
        """Execute a single contract action."""
        action_type = action.get("type")
        
        if action_type == "trade":
            self._execute_trade_action(contract, action)
        elif action_type == "transfer":
            self._execute_transfer_action(contract, action)
        elif action_type == "notify":
            self._execute_notify_action(contract, action)
        elif action_type == "cancel_order":
            self._execute_cancel_action(contract, action)
        elif action_type == "smart_contract_call":
            self._execute_smart_contract_call(contract, action)
    
    def _execute_trade_action(self, contract: Contract, action: Dict[str, Any]) -> None:
        """Execute a trade action."""
        if self.event_bus:
            self.event_bus.publish("trading.order.request", {
                "symbol": action.get("symbol"),
                "side": action.get("side", "buy"),
                "quantity": action.get("quantity", 0),
                "order_type": action.get("order_type", "market"),
                "price": action.get("price"),
                "contract_id": contract.contract_id
            })
    
    def _execute_transfer_action(self, contract: Contract, action: Dict[str, Any]) -> None:
        """Execute a transfer action."""
        if self.event_bus:
            self.event_bus.publish("wallet.transfer.request", {
                "from": action.get("from"),
                "to": action.get("to"),
                "amount": action.get("amount"),
                "asset": action.get("asset"),
                "contract_id": contract.contract_id
            })
    
    def _execute_notify_action(self, contract: Contract, action: Dict[str, Any]) -> None:
        """Execute a notification action."""
        if self.event_bus:
            self.event_bus.publish("notification.send", {
                "type": action.get("notify_type", "info"),
                "message": action.get("message"),
                "recipients": action.get("recipients", []),
                "contract_id": contract.contract_id
            })
    
    def _execute_cancel_action(self, contract: Contract, action: Dict[str, Any]) -> None:
        """Execute an order cancellation."""
        if self.event_bus:
            self.event_bus.publish("trading.order.cancel", {
                "order_id": action.get("order_id"),
                "contract_id": contract.contract_id
            })
    
    def _execute_smart_contract_call(self, contract: Contract, action: Dict[str, Any]) -> None:
        """Execute a blockchain smart contract call."""
        if self.event_bus:
            self.event_bus.publish("blockchain.contract.call", {
                "contract_address": action.get("contract_address"),
                "method": action.get("method"),
                "params": action.get("params", []),
                "value": action.get("value", 0),
                "contract_id": contract.contract_id
            })
    
    def _check_price_conditions(self, data: Dict[str, Any]) -> None:
        """Check if price update triggers any contract conditions."""
        symbol = data.get("symbol")
        price = data.get("price", 0)
        
        if symbol not in self._price_triggers:
            return
        
        for contract_id in self._price_triggers[symbol]:
            if contract_id not in self.active_contracts:
                continue
            
            contract = self.active_contracts[contract_id]
            
            for condition in contract.conditions:
                if condition.get("type") != "price":
                    continue
                if condition.get("symbol") != symbol:
                    continue
                
                operator = condition.get("operator", ">=")
                target_price = condition.get("target_price", 0)
                
                triggered = False
                if operator == ">=" and price >= target_price:
                    triggered = True
                elif operator == "<=" and price <= target_price:
                    triggered = True
                elif operator == ">" and price > target_price:
                    triggered = True
                elif operator == "<" and price < target_price:
                    triggered = True
                elif operator == "==" and abs(price - target_price) < 0.0001:
                    triggered = True
                
                if triggered:
                    self.execute_contract(contract_id, {
                        "trigger": "price",
                        "symbol": symbol,
                        "price": price,
                        "condition": condition
                    })
    
    def _handle_order_filled(self, data: Dict[str, Any]) -> None:
        """Handle order filled events for contract tracking."""
        contract_id = data.get("contract_id")
        if contract_id and contract_id in self.contracts:
            self.contracts[contract_id].execution_log.append({
                "action": "order_filled",
                "timestamp": time.time(),
                "data": data
            })
    
    def _handle_tx_confirmed(self, data: Dict[str, Any]) -> None:
        """Handle blockchain transaction confirmations."""
        contract_id = data.get("contract_id")
        if contract_id and contract_id in self.contracts:
            self.contracts[contract_id].execution_log.append({
                "action": "tx_confirmed",
                "timestamp": time.time(),
                "tx_hash": data.get("tx_hash")
            })
    
    def _handle_execute_request(self, data: Dict[str, Any]) -> None:
        """Handle external execution requests."""
        contract_id = data.get("contract_id")
        if contract_id:
            self.execute_contract(contract_id, data)
    
    def cancel_contract(self, contract_id: str, reason: str = "") -> bool:
        """
        Cancel a contract.
        
        Args:
            contract_id: ID of contract to cancel
            reason: Cancellation reason
            
        Returns:
            Success status
        """
        if contract_id not in self.contracts:
            return False
        
        contract = self.contracts[contract_id]
        
        if contract.status in [ContractStatus.COMPLETED, ContractStatus.CANCELLED]:
            return False
        
        contract.status = ContractStatus.CANCELLED
        contract.execution_log.append({
            "action": "cancelled",
            "timestamp": time.time(),
            "reason": reason
        })
        
        # Remove from active/pending
        if contract_id in self.active_contracts:
            del self.active_contracts[contract_id]
        if contract_id in self.pending_contracts:
            del self.pending_contracts[contract_id]
        
        self.stats["active_count"] = len(self.active_contracts)
        
        if self.event_bus:
            self.event_bus.publish("contract.cancelled", {
                "contract_id": contract_id,
                "reason": reason
            })
        
        return True
    
    def get_contract(self, contract_id: str) -> Optional[Contract]:
        """Get a contract by ID."""
        return self.contracts.get(contract_id)
    
    def get_active_contracts(self) -> List[Contract]:
        """Get all active contracts."""
        return list(self.active_contracts.values())
    
    def get_contracts_by_type(self, contract_type: ContractType) -> List[Contract]:
        """Get all contracts of a specific type."""
        return [c for c in self.contracts.values() if c.contract_type == contract_type]
    
    def check_expirations(self) -> List[str]:
        """Check and expire contracts that have passed their expiration time."""
        expired = []
        current_time = time.time()
        
        for contract_id, contract in list(self.active_contracts.items()):
            if contract.expires_at and current_time > contract.expires_at:
                contract.status = ContractStatus.EXPIRED
                contract.execution_log.append({
                    "action": "expired",
                    "timestamp": current_time
                })
                del self.active_contracts[contract_id]
                expired.append(contract_id)
                
                if self.event_bus:
                    self.event_bus.publish("contract.expired", {
                        "contract_id": contract_id
                    })
        
        self.stats["active_count"] = len(self.active_contracts)
        return expired
    
    def get_stats(self) -> Dict[str, Any]:
        """Get contract manager statistics."""
        return {
            **self.stats,
            "pending_count": len(self.pending_contracts),
            "total_contracts": len(self.contracts)
        }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.contracts.clear()
        self.active_contracts.clear()
        self.pending_contracts.clear()
        self._price_triggers.clear()
        self._initialized = False
        
        if self.event_bus:
            self.event_bus.publish("contract.manager.cleanup", {
                "status": "cleaned"
            })


__all__ = ['ContractManager', 'Contract', 'ContractType', 'ContractStatus']
