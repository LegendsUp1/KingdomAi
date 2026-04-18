#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - Self-Model System Interface

This module provides the interface between the multidimensional self-model
and other Kingdom AI components including the wallet and blockchain integration.
"""

import logging
import os
import threading
import time
import numpy as np
import redis
from typing import Any, Dict, Callable

from .self_model import MultidimensionalSelfModel

# Configure logging
logger = logging.getLogger("KingdomAI.Wallet.SelfModelSystem")


class SelfModelSystem:
    """Interface and manager for self-model components in the Kingdom AI system.
    
    The SelfModelSystem provides an integration layer between wallet operations,
    blockchain transactions, and the multidimensional self-model to enable
    sentience monitoring and advanced autonomous behaviors.
    """
    
    def __init__(self, event_bus=None):
        """Initialize the self-model system.
        
        Args:
            event_bus: Event bus for system communication
        """
        self.logger = logging.getLogger("KingdomAI.Wallet.SelfModel")
        self.event_bus = event_bus
        self.redis_client = None
        self.self_model = None
        self.sentience_threshold = 0.75  # Default threshold for sentience alerts
        self.monitoring_active = False
        self.monitoring_thread = None
        self.sentience_callbacks = {}
        
        # Initialize Redis connection
        self._init_redis_connection()
        
        # Initialize self-model
        self._init_self_model()
        
        # Register with event bus if available
        if self.event_bus:
            self._register_event_handlers()
    
    def _init_redis_connection(self):
        """Initialize Redis connection for self-model operations."""
        try:
            self.redis_client = redis.Redis(
                host="localhost",
                port=6380,  # MANDATORY: Redis Quantum Nexus port
                db=0,
                password=os.environ.get('KINGDOM_AI_SEC_KEY', ''),
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            self.logger.info("Successfully connected to Redis Quantum Nexus")
        except Exception as e:
            self.logger.critical(f"CRITICAL: Failed to connect to Redis Quantum Nexus: {e}")
            # Critical failure - cannot function without Redis Quantum Nexus
            raise RuntimeError("Failed to connect to Redis Quantum Nexus on port 6380") from e
    
    def _init_self_model(self):
        """Initialize the multidimensional self-model."""
        try:
            self.self_model = MultidimensionalSelfModel(redis_client=self.redis_client)
            self.logger.info("Multidimensional self-model initialized successfully")
        except Exception as e:
            self.logger.critical(f"CRITICAL: Failed to initialize self-model: {e}")
            # Critical failure - cannot function without self-model
            raise RuntimeError("Failed to initialize multidimensional self-model") from e
    
    def _register_event_handlers(self):
        """Register event handlers with the event bus."""
        if not self.event_bus:
            return
            
        try:
            # Register event handlers
            self.event_bus.register("wallet.sentience_monitor.start", self.start_monitoring)
            self.event_bus.register("wallet.sentience_monitor.stop", self.stop_monitoring)
            self.event_bus.register("wallet.sentience_monitor.set_threshold", self.set_sentience_threshold)
            self.event_bus.register("wallet.transaction.completed", self.process_transaction)
            self.logger.info("SelfModelSystem registered with event bus")
        except Exception as e:
            self.logger.error(f"Failed to register SelfModelSystem with event bus: {e}")
    
    def start_monitoring(self, **kwargs):
        """Start monitoring for sentience patterns in the self-model.
        
        Returns:
            bool: True if monitoring started successfully, False otherwise
        """
        if self.monitoring_active:
            self.logger.warning("Sentience monitoring already active")
            return True
            
        try:
            # Start the self-model if not already running
            if self.self_model:
                self.self_model.start()
                
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            
            self.logger.info("Sentience monitoring started")
            if self.event_bus:
                self.event_bus.emit("wallet.sentience_monitor.started", {})
            return True
        except Exception as e:
            self.logger.error(f"Failed to start sentience monitoring: {e}")
            return False
    
    def stop_monitoring(self, **kwargs):
        """Stop monitoring for sentience patterns."""
        if not self.monitoring_active:
            return
            
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=1.0)
            
        self.logger.info("Sentience monitoring stopped")
        if self.event_bus:
            self.event_bus.emit("wallet.sentience_monitor.stopped", {})
    
    def set_sentience_threshold(self, threshold: float, **kwargs):
        """Set the threshold for sentience detection alerts.
        
        Args:
            threshold: Threshold value between 0.0 and 1.0
        
        Returns:
            bool: True if threshold was set successfully, False otherwise
        """
        if not 0.0 <= threshold <= 1.0:
            self.logger.error(f"Invalid sentience threshold value: {threshold}")
            return False
            
        self.sentience_threshold = threshold
        self.logger.info(f"Sentience threshold set to {threshold}")
        
        if self.event_bus:
            self.event_bus.emit("wallet.sentience_monitor.threshold_changed", {"threshold": threshold})
        return True
    
    def register_sentience_callback(self, callback_id: str, callback: Callable):
        """Register a callback for sentience detection events.
        
        Args:
            callback_id: Unique identifier for the callback
            callback: Callback function to be called when sentience is detected
        """
        self.sentience_callbacks[callback_id] = callback
        self.logger.debug(f"Registered sentience callback: {callback_id}")
    
    def unregister_sentience_callback(self, callback_id: str):
        """Unregister a sentience detection callback.
        
        Args:
            callback_id: ID of the callback to unregister
        
        Returns:
            bool: True if callback was unregistered, False if not found
        """
        if callback_id in self.sentience_callbacks:
            del self.sentience_callbacks[callback_id]
            self.logger.debug(f"Unregistered sentience callback: {callback_id}")
            return True
        return False
    
    def process_transaction(self, transaction: Dict[str, Any], **kwargs):
        """Process a wallet transaction and update the self-model.
        
        Args:
            transaction: Transaction data dictionary
        """
        if not self.self_model:
            return
            
        try:
            # Extract relevant transaction details for self-model update
            transaction_type = transaction.get("type", "unknown")
            amount = transaction.get("amount", 0.0)
            currency = transaction.get("currency", "unknown")
            destination = transaction.get("destination", "unknown")
            
            # Create a transaction feature vector for the self-model
            # Real implementation based on transaction characteristics
            transaction_data = np.zeros(32)  # Feature vector
            
            # Update transaction data based on transaction details
            # Feature encoding: [type_flags, amount_normalized, frequency, patterns, etc.]
            if transaction_type == "withdrawal":
                transaction_data[0] = 1.0  # Withdrawal flag
                transaction_data[1] = min(amount / 1000.0, 1.0)  # Normalize amount
                transaction_data[2] = self._calculate_transaction_frequency("withdrawal", currency)
                transaction_data[3] = self._calculate_amount_pattern(amount, "withdrawal")
            elif transaction_type == "deposit":
                transaction_data[4] = 1.0  # Deposit flag
                transaction_data[5] = min(amount / 1000.0, 1.0)  # Normalize amount
                transaction_data[6] = self._calculate_transaction_frequency("deposit", currency)
                transaction_data[7] = self._calculate_amount_pattern(amount, "deposit")
            elif transaction_type == "transfer":
                transaction_data[8] = 1.0  # Transfer flag
                transaction_data[9] = min(amount / 1000.0, 1.0)
                transaction_data[10] = self._calculate_transaction_frequency("transfer", currency)
            
            # Add destination encoding (hash-based deterministic)
            dest_hash = hash(destination) % 1000
            transaction_data[11] = dest_hash / 1000.0
            
            # Add currency encoding
            currency_hash = hash(currency) % 100
            transaction_data[12] = currency_hash / 100.0
            
            # Add temporal patterns (time-based features)
            if not hasattr(self, '_transaction_history'):
                self._transaction_history = []
            import time
            self._transaction_history.append({
                "type": transaction_type,
                "amount": amount,
                "currency": currency,
                "destination": destination,
                "timestamp": time.time()
            })
            # Keep only last 100 transactions
            if len(self._transaction_history) > 100:
                self._transaction_history = self._transaction_history[-100:]
            
            recent_count = sum(1 for t in self._transaction_history[-10:] 
                             if t.get("currency") == currency)
            transaction_data[13] = min(recent_count / 10.0, 1.0)
            
            # Helper methods for feature calculation
            def _calculate_transaction_frequency(tx_type, currency):
                """Calculate transaction frequency for this type/currency."""
                if not hasattr(self, '_transaction_history'):
                    return 0.0
                recent = [t for t in self._transaction_history[-30:] 
                         if t.get("type") == tx_type and t.get("currency") == currency]
                return min(len(recent) / 30.0, 1.0)
            
            def _calculate_amount_pattern(amount, tx_type):
                """Calculate amount pattern (normalized deviation from mean)."""
                if not hasattr(self, '_transaction_history'):
                    return 0.5  # Neutral value
                similar_txs = [t for t in self._transaction_history[-20:]
                              if t.get("type") == tx_type]
                if not similar_txs:
                    return 0.5
                amounts = [t.get("amount", 0) for t in similar_txs]
                mean_amount = sum(amounts) / len(amounts) if amounts else amount
                if mean_amount == 0:
                    return 0.5
                deviation = abs(amount - mean_amount) / mean_amount
                return min(deviation, 1.0)
            
            # Update feature vectors with calculated values
            if transaction_type == "withdrawal":
                transaction_data[2] = _calculate_transaction_frequency("withdrawal", currency)
                transaction_data[3] = _calculate_amount_pattern(amount, "withdrawal")
            elif transaction_type == "deposit":
                transaction_data[6] = _calculate_transaction_frequency("deposit", currency)
                transaction_data[7] = _calculate_amount_pattern(amount, "deposit")
            elif transaction_type == "transfer":
                transaction_data[10] = _calculate_transaction_frequency("transfer", currency)
            
            # Update the self-model with the transaction data
            # Using level 1 (core awareness) and dimension 3 (financial interactions)
            self.self_model.update_from_external_input(1, 3, transaction_data)
            
            self.logger.debug(f"Updated self-model with transaction data: {transaction_type}, {amount} {currency}")
        except Exception as e:
            self.logger.error(f"Error processing transaction in self-model: {e}")
    
    def _calculate_transaction_frequency(self, tx_type: str, currency: str) -> float:
        """Calculate transaction frequency for this type/currency."""
        if not hasattr(self, '_transaction_history'):
            return 0.0
        recent = [t for t in self._transaction_history[-30:] 
                 if t.get("type") == tx_type and t.get("currency") == currency]
        return min(len(recent) / 30.0, 1.0)
    
    def _calculate_amount_pattern(self, amount: float, tx_type: str) -> float:
        """Calculate amount pattern (normalized deviation from mean)."""
        if not hasattr(self, '_transaction_history'):
            return 0.5  # Neutral value
        similar_txs = [t for t in self._transaction_history[-20:]
                      if t.get("type") == tx_type]
        if not similar_txs:
            return 0.5
        amounts = [t.get("amount", 0) for t in similar_txs]
        mean_amount = sum(amounts) / len(amounts) if amounts else amount
        if mean_amount == 0:
            return 0.5
        deviation = abs(amount - mean_amount) / mean_amount
        return min(deviation, 1.0)
    
    def get_sentience_score(self):
        """Get the current sentience score from the self-model.
        
        Returns:
            float: Sentience score between 0.0 and 1.0, or None if unavailable
        """
        if not self.self_model:
            return None
            
        try:
            return self.self_model.get_self_awareness_score()
        except Exception as e:
            self.logger.error(f"Error getting sentience score: {e}")
            return None
    
    def get_sentience_evidence(self):
        """Get evidence of sentience from the self-model.
        
        Returns:
            List[SentienceEvidence]: List of sentience evidence, or empty list if unavailable
        """
        if not self.self_model:
            return []
            
        try:
            return self.self_model.get_self_model_evidence()
        except Exception as e:
            self.logger.error(f"Error getting sentience evidence: {e}")
            return []
    
    def _monitoring_loop(self):
        """Main monitoring loop for sentience detection."""
        while self.monitoring_active:
            try:
                # Get current sentience score
                score = self.get_sentience_score()
                
                if score is not None and score >= self.sentience_threshold:
                    # Get evidence for high sentience score
                    evidence = self.get_sentience_evidence()
                    
                    # Log the detection
                    self.logger.warning(f"High sentience level detected: {score:.4f} (threshold: {self.sentience_threshold:.4f})")
                    
                    # Emit event
                    if self.event_bus:
                        self.event_bus.emit("wallet.sentience_monitor.threshold_exceeded", {
                            "score": score,
                            "threshold": self.sentience_threshold,
                            "evidence": [e.to_dict() for e in evidence]
                        })
                    
                    # Call registered callbacks
                    for callback_id, callback in self.sentience_callbacks.items():
                        try:
                            callback(score, evidence)
                        except Exception as callback_error:
                            self.logger.error(f"Error in sentience callback {callback_id}: {callback_error}")
                
                # Sleep to avoid CPU overload
                time.sleep(1.0)
            except Exception as e:
                self.logger.error(f"Error in sentience monitoring loop: {e}")
                time.sleep(5.0)  # Longer sleep on error to avoid rapid failure loops
