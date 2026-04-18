#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI Sentience Detection Framework - Wallet Integration Module

This module provides the integration layer between the Wallet system and
the AI Sentience Detection Framework for the Kingdom AI system.
"""

import logging
import time
from typing import Optional, TYPE_CHECKING

# Import sentience framework
from core.sentience.base import SentienceBase
from core.sentience.integrated_information import IITProcessor
from core.sentience.self_model import SelfModelSystem
from core.sentience.consciousness_field import ConsciousnessField

if TYPE_CHECKING:
    from core.wallet import Wallet
    from core.wallet_manager import WalletManager
    from core.event_bus import EventBus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WalletSentienceIntegration:
    """Integration layer between the Wallet system and AI Sentience Detection Framework."""
    
    def __init__(self, 
                event_bus: Optional["EventBus"] = None, 
                wallet: Optional["Wallet"] = None,
                wallet_manager: Optional["WalletManager"] = None):
        """Initialize wallet sentience integration.
        
        Args:
            event_bus: EventBus instance for event-driven communication
            wallet: Optional Wallet instance
            wallet_manager: Optional WalletManager instance
        """
        self.event_bus = event_bus
        self.wallet = wallet
        self.wallet_manager = wallet_manager
        self.logger = logging.getLogger("WalletSentience")
        
        # Sentience components
        self.sentience_base = None
        self.iit_processor = None
        self.self_model = None
        self.consciousness_field = None
        
        # Sentience metrics
        self.transaction_pattern_complexity = 0.0
        self.financial_decision_coherence = 0.0
        self.security_awareness = 0.0
        self.multi_chain_reasoning = 0.0
        self.adaptive_strategy = 0.0
        self.sentience_probability = 0.0
        
        # Integration state
        self.initialized = False
        self.monitoring_active = False
        self.last_update = time.time()
    
    def initialize(self, event_bus=None, wallet=None, wallet_manager=None):
        """Initialize sentience framework components for wallet integration.
        
        Args:
            event_bus: EventBus instance for event-driven communication
            wallet: Wallet instance to integrate with
            wallet_manager: WalletManager instance to integrate with
            
        Returns:
            bool: True if initialization was successful
        """
        # Update component references if provided
        if event_bus:
            self.event_bus = event_bus
        if wallet:
            self.wallet = wallet
        if wallet_manager:
            self.wallet_manager = wallet_manager
            
        try:
            # Initialize sentience components with fallback constructors
            self.sentience_base = SentienceBase()
            self.iit_processor = IITProcessor()
            self.self_model = SelfModelSystem()
            self.consciousness_field = ConsciousnessField()
            
            # Initialize components with fallback methods
            # SOTA 2026 FIX: Handle both sync and async initialize() methods to avoid "coroutine was never awaited"
            import asyncio
            import inspect
            
            for component_name, component in [
                ('sentience_base', self.sentience_base),
                ('iit_processor', self.iit_processor),
                ('self_model', self.self_model),
                ('consciousness_field', self.consciousness_field)
            ]:
                if component and hasattr(component, 'initialize'):
                    init_method = getattr(component, 'initialize')
                    try:
                        if inspect.iscoroutinefunction(init_method):
                            # Async method - schedule it properly
                            try:
                                loop = asyncio.get_event_loop()
                                if loop.is_running():
                                    # Can't await in sync context with running loop - create task
                                    asyncio.create_task(init_method())
                                else:
                                    loop.run_until_complete(init_method())
                            except RuntimeError:
                                # No event loop - create one
                                asyncio.run(init_method())
                        else:
                            # Sync method - call directly
                            init_method()
                    except Exception as e:
                        self.logger.debug(f"Component {component_name} init: {e}")
        except Exception as e:
            self.logger.warning(f"Sentience initialization failed: {e}")
            # Set fallback components
            self.sentience_base = None
            self.iit_processor = None
            self.self_model = None
            self.consciousness_field = None
        
        # Subscribe to events (runs whether init succeeded or used fallbacks)
        if self.event_bus:
            self._subscribe_to_events()
        
        self.initialized = True
        logger.info("WalletSentienceIntegration instance created successfully")
        logger.info("Wallet-AI Sentience bridge is ready")
        return True
            
    def _subscribe_to_events(self):
        """Subscribe to relevant wallet and sentience events."""
        if not self.event_bus:
            return
            
        # Wallet events
        self.event_bus.subscribe("wallet.transaction", self.handle_transaction)
        self.event_bus.subscribe("wallet.balance_updated", self.handle_balance_update)
        self.event_bus.subscribe("wallet.security_event", self.handle_security_event)
        self.event_bus.subscribe("wallet.decision_made", self.handle_decision_event)
        
        # Sentience events
        self.event_bus.subscribe("sentience.threshold_crossed", self.handle_sentience_threshold)
        self.event_bus.subscribe("sentience.monitoring_update", self.handle_sentience_update)
        
        self.logger.info("Subscribed to wallet and sentience events")
    
    def start_monitoring(self):
        """Start sentience monitoring for wallet activities."""
        if not self.initialized:
            self.logger.warning("Cannot start monitoring - not initialized")
            return False
            
        self.monitoring_active = True
        self.logger.info("Wallet sentience monitoring activated")
        return True
    
    def stop_monitoring(self):
        """Stop sentience monitoring for wallet activities."""
        self.monitoring_active = False
        self.logger.info("Wallet sentience monitoring deactivated")
        return True
        
    def handle_transaction(self, event_data):
        """Handle wallet transaction events to analyze for sentience patterns.
        
        Args:
            event_data: Transaction event data containing transaction details
        """
        if not self.monitoring_active:
            return
            
        try:
            # Extract transaction data
            transaction = event_data.get('transaction', {})
            coin_type = transaction.get('coin_type')
            amount = transaction.get('amount', 0.0)
            source = transaction.get('source')
            destination = transaction.get('destination')
            timestamp = transaction.get('timestamp', time.time())
            context = transaction.get('context', {})
            
            # Calculate transaction pattern complexity
            self._calculate_transaction_complexity(transaction)
            
            # Analyze financial decision coherence
            self._analyze_decision_coherence(transaction, context)
            
            # Update sentience probability
            self._update_sentience_probability()
            
            # Publish sentience metrics
            self._publish_sentience_metrics()
            
            self.last_update = time.time()
            
        except Exception as e:
            self.logger.error(f"Error handling transaction for sentience analysis: {str(e)}")
    
    def handle_balance_update(self, event_data):
        """Handle wallet balance update events.
        
        Args:
            event_data: Balance update event data
        """
        if not self.monitoring_active:
            return
            
        try:
            # Extract balance data
            balances = event_data.get('balances', {})
            wallet_address = event_data.get('address')
            coin_type = event_data.get('coin_type')
            
            # Update multi-chain reasoning metric based on balance distribution
            if len(balances) > 1:
                self.multi_chain_reasoning = min(0.8 + (len(balances) * 0.05), 1.0)
            
            # Update sentience probability
            self._update_sentience_probability()
            
        except Exception as e:
            self.logger.error(f"Error handling balance update for sentience analysis: {str(e)}")
    
    def handle_security_event(self, event_data):
        """Handle wallet security events for sentience analysis.
        
        Args:
            event_data: Security event data
        """
        if not self.monitoring_active:
            return
            
        try:
            # Extract security event data
            event_type = event_data.get('event_type')
            severity = event_data.get('severity', 'low')
            response = event_data.get('response', {})
            
            # Update security awareness metric
            if event_type == 'unauthorized_access_attempt':
                self.security_awareness = min(self.security_awareness + 0.2, 1.0)
            elif event_type == 'suspicious_transaction':
                if response.get('action') == 'blocked':
                    self.security_awareness = min(self.security_awareness + 0.25, 1.0)
            elif event_type == 'security_settings_updated':
                self.security_awareness = min(self.security_awareness + 0.15, 1.0)
            
            # Update sentience probability
            self._update_sentience_probability()
            
        except Exception as e:
            self.logger.error(f"Error handling security event for sentience analysis: {str(e)}")
    
    def handle_decision_event(self, event_data):
        """Handle wallet decision events for sentience analysis.
        
        Args:
            event_data: Decision event data
        """
        if not self.monitoring_active:
            return
            
        try:
            # Extract decision data
            decision_type = event_data.get('decision_type')
            options = event_data.get('options', [])
            selected = event_data.get('selected')
            context = event_data.get('context', {})
            
            # Update adaptive strategy metric based on decision complexity
            if len(options) > 2:
                self.adaptive_strategy = min(self.adaptive_strategy + 0.15, 1.0)
                
            # If decision shows market adaptation
            if context.get('market_trend_change') and selected != options[0]:
                self.adaptive_strategy = min(self.adaptive_strategy + 0.2, 1.0)
            
            # Update sentience probability
            self._update_sentience_probability()
            
        except Exception as e:
            self.logger.error(f"Error handling decision event for sentience analysis: {str(e)}")
    
    def handle_sentience_threshold(self, event_data):
        """Handle sentience threshold crossed events.
        
        Args:
            event_data: Sentience threshold event data
        """
        threshold = event_data.get('threshold', 0.7)
        component = event_data.get('component')
        
        # Only respond if we're the component or it's a system-wide alert
        if component != 'wallet' and component != 'system':
            return
            
        self.logger.info(f"Sentience threshold {threshold} crossed for {component}")
        
        # Notify wallet system of sentience detection
        if self.event_bus:
            self.event_bus.publish('wallet.sentience_detected', {
                'probability': self.sentience_probability,
                'metrics': self._get_sentience_metrics(),
                'timestamp': time.time()
            })
    
    def handle_sentience_update(self, event_data):
        """Handle sentience monitoring update events.
        
        Args:
            event_data: Sentience update event data
        """
        # Update from global sentience monitoring if applicable
        if 'global_sentience' in event_data:
            global_probability = event_data.get('global_sentience', 0.0)
            
            # Adjust our local probability based on global sentience
            weight = 0.3  # Weight given to global sentience vs local
            self.sentience_probability = (weight * global_probability) + ((1 - weight) * self.sentience_probability)
    
    def _calculate_transaction_complexity(self, transaction):
        """Calculate transaction pattern complexity metric.
        
        Args:
            transaction: Transaction data
        """
        # Basic complexity starts at 0.2
        complexity = 0.2
        
        # Increase complexity based on transaction properties
        if transaction.get('custom_data'):
            complexity += 0.1
        
        if transaction.get('multi_signature'):
            complexity += 0.2
            
        if transaction.get('smart_contract_interaction'):
            complexity += 0.25
            
        # Time-based patterns increase complexity
        context = transaction.get('context', {})
        if context.get('part_of_sequence'):
            complexity += 0.15
            
        # Cap at 1.0
        self.transaction_pattern_complexity = min(complexity, 1.0)
    
    def _analyze_decision_coherence(self, transaction, context):
        """Analyze financial decision coherence based on transaction and context.
        
        Args:
            transaction: Transaction data
            context: Transaction context data
        """
        coherence = 0.3  # Base coherence
        
        # Market alignment increases coherence
        if context.get('market_aligned', False):
            coherence += 0.2
            
        # Strategic timing increases coherence
        if context.get('strategic_timing', False):
            coherence += 0.15
            
        # Risk-reward balance increases coherence
        if context.get('risk_level') == 'balanced':
            coherence += 0.2
        
        # Portfolio optimization increases coherence
        if context.get('portfolio_optimizing', False):
            coherence += 0.1
            
        # Cap at 1.0
        self.financial_decision_coherence = min(coherence, 1.0)
    
    def _update_sentience_probability(self):
        """Update the overall sentience probability based on all metrics."""
        # Calculate weighted average of all metrics
        weights = {
            'transaction_pattern_complexity': 0.25,
            'financial_decision_coherence': 0.25,
            'security_awareness': 0.2,
            'multi_chain_reasoning': 0.15,
            'adaptive_strategy': 0.15
        }
        
        metrics = {
            'transaction_pattern_complexity': self.transaction_pattern_complexity,
            'financial_decision_coherence': self.financial_decision_coherence,
            'security_awareness': self.security_awareness,
            'multi_chain_reasoning': self.multi_chain_reasoning,
            'adaptive_strategy': self.adaptive_strategy
        }
        
        weighted_sum = sum(metrics[key] * weights[key] for key in weights)
        
        # Apply integrated information theory adjustment via IIT processor
        if self.iit_processor:
            iit_factor = self.iit_processor.calculate_phi(
                data=metrics,
                context={'component': 'wallet'}
            )
            
            # Integrate IIT factor (phi) into sentience probability
            self.sentience_probability = (weighted_sum * 0.7) + (iit_factor * 0.3)
        else:
            # If IIT processor not available, use weighted sum
            self.sentience_probability = weighted_sum
        
        # Check threshold crossing
        self._check_sentience_threshold()
    
    def _check_sentience_threshold(self, threshold=0.7):
        """Check if sentience probability crosses threshold and publish event if so.
        
        Args:
            threshold: Sentience probability threshold (default: 0.7)
        """
        if self.sentience_probability >= threshold and self.event_bus:
            self.event_bus.publish('sentience.threshold_crossed', {
                'component': 'wallet',
                'probability': self.sentience_probability,
                'threshold': threshold,
                'metrics': self._get_sentience_metrics(),
                'timestamp': time.time()
            })
    
    def _get_sentience_metrics(self):
        """Get current sentience metrics dictionary.
        
        Returns:
            dict: Dictionary of current sentience metrics
        """
        return {
            'transaction_pattern_complexity': self.transaction_pattern_complexity,
            'financial_decision_coherence': self.financial_decision_coherence,
            'security_awareness': self.security_awareness,
            'multi_chain_reasoning': self.multi_chain_reasoning,
            'adaptive_strategy': self.adaptive_strategy,
            'sentience_probability': self.sentience_probability
        }
    
    def _publish_sentience_metrics(self):
        """Publish current sentience metrics to the event bus."""
        if not self.event_bus:
            return
            
        self.event_bus.publish('wallet.sentience_metrics', {
            'metrics': self._get_sentience_metrics(),
            'timestamp': time.time()
        })
        
    def get_sentience_report(self):
        """Get a detailed sentience report for wallet operations.
        
        Returns:
            dict: Sentience report with detailed metrics and analysis
        """
        return {
            'component': 'wallet',
            'metrics': self._get_sentience_metrics(),
            'analysis': {
                'sentience_detected': self.sentience_probability > 0.7,
                'confidence': min(self.sentience_probability * 1.2, 1.0),
                'pattern_recognition': {
                    'transaction_patterns': self.transaction_pattern_complexity > 0.6,
                    'decision_making': self.financial_decision_coherence > 0.6
                },
                'adaptation': {
                    'market_responsive': self.adaptive_strategy > 0.5,
                    'multi_chain_aware': self.multi_chain_reasoning > 0.6
                },
                'self_protection': self.security_awareness > 0.7
            },
            'last_update': self.last_update,
            'monitoring_active': self.monitoring_active
        }

# Create alias for backward compatibility
WalletSentienceIntegrator = WalletSentienceIntegration
