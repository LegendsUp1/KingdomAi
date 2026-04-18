#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Main Window Event Handlers Module.

This module provides all event handlers for the Kingdom AI main window.
These handlers ensure that all tabs respond to system events and
that the UI reflects the current system state.
"""

import time
import logging
import asyncio
import traceback
from typing import Dict, Any, Optional, Union

class MainWindowEventHandlers:
    """Event handlers for the Kingdom AI main window."""
    
    # -------------------------------------------------------------------------
    # Core Infrastructure Event Handlers
    # -------------------------------------------------------------------------
    
    async def _handle_system_status(self, event_data: Dict[str, Any]) -> None:
        """Handle system status events.
        
        Args:
            event_data: The event data containing system status information
        """
        if not event_data:
            self.logger.warning("Received empty system status event")
            return
            
        try:
            # Update status indicators in the UI
            status = event_data.get('status', 'unknown')
            message = event_data.get('message', '')
            timestamp = event_data.get('timestamp', time.time())
            
            # Log the status update
            self.logger.info(f"System status update: {status} - {message}")
            
            # Update the status bar if available
            if hasattr(self, 'status_bar') and self.status_bar:
                self.status_bar.update_status(message, status)
                
            # Update system status indicator in the dashboard if available
            if hasattr(self, 'tabs') and 'Dashboard' in self.tabs:
                # Get the dashboard tab
                dashboard = self.tabs['Dashboard']
                if hasattr(dashboard, 'update_system_status'):
                    dashboard.update_system_status(status, message, timestamp)
        except Exception as e:
            self.logger.error(f"Error handling system status event: {e}")
            self.logger.debug(traceback.format_exc())
    
    async def _handle_redis_status(self, event_data: Dict[str, Any]) -> None:
        """Handle Redis status events.
        
        Args:
            event_data: The event data containing Redis status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'disconnected')
        integrated_components = event_data.get('integrated_components', [])
        timestamp = event_data.get('timestamp', None)
        
        self.logger.info(f"Redis status: {status} with {len(integrated_components)} integrated components")
        
        # Update status tracking
        self.redis_status = {
            "connected": status == "connected",
            "integrated_components": integrated_components,
            "last_update": timestamp or time.time()
        }
        
        # Update UI indicator
        if status == "connected":
            self.redis_indicator.config(text=f"Redis: Connected ({len(integrated_components)} components)", fg="green")
        elif status == "fallback":
            self.redis_indicator.config(text="Redis: Fallback Mode", fg="orange")
        else:
            self.redis_indicator.config(text="Redis: Disconnected", fg="red")
            
        # Refresh tabs if they need Redis data
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'refresh_all_tabs'):
            self.tab_manager.refresh_all_tabs()
    
    def _handle_database_status(self, event_data: Dict[str, Any]) -> None:
        """Handle database status events.
        
        Args:
            event_data: The event data containing database status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'disconnected')
        db_type = event_data.get('type', 'Unknown')
        timestamp = event_data.get('timestamp', time.time())
        
        self.logger.info(f"Database {db_type} status: {status}")
        
        # Update status in all relevant tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            # Update settings tab with database status
            self.tab_manager.update_tab_data("Settings", {
                "database_status": status,
                "database_type": db_type,
                "database_timestamp": timestamp
            })
            
            # Update any other tabs that might need database info
            for tab_name in ["Trading", "Mining", "Portfolio"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "database_status": status
                })
    
    def _handle_network_status(self, event_data: Dict[str, Any]) -> None:
        """Handle network status events.
        
        Args:
            event_data: The event data containing network status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'disconnected')
        latency = event_data.get('latency', -1)
        timestamp = event_data.get('timestamp', time.time())
        
        self.logger.info(f"Network status: {status}, latency: {latency}ms")
        
        # Update status in all tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in self.tab_manager.tabs:
                self.tab_manager.update_tab_data(tab_name, {
                    "network_status": status,
                    "network_latency": latency,
                    "network_timestamp": timestamp
                })
    
    def _handle_system_status(self, event_data: Dict[str, Any]) -> None:
        """Handle system status events.
        
        Args:
            event_data: The event data containing system status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'unknown')
        components = event_data.get('components', {})
        errors = event_data.get('errors', [])
        
        self.logger.info(f"System status: {status} with {len(errors)} errors")
        
        # Update all tabs with system status
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in self.tab_manager.tabs:
                self.tab_manager.update_tab_data(tab_name, {
                    "system_status": status,
                    "system_errors": errors
                })
                
            # Update the dashboard with more detailed information
            self.tab_manager.update_tab_data("Dashboard", {
                "system_status": status,
                "system_components": components,
                "system_errors": errors
            })
    
    def _handle_event_bus_status(self, event_data: Dict[str, Any]) -> None:
        """Handle event bus status events.
        
        Args:
            event_data: The event data containing event bus status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'unknown')
        subscribers = event_data.get('subscribers', 0)
        events = event_data.get('events', 0)
        
        self.logger.info(f"Event bus status: {status} with {subscribers} subscribers and {events} registered events")
        
        # Update all tabs that need event bus status
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            self.tab_manager.update_tab_data("Settings", {
                "event_bus_status": status,
                "event_bus_subscribers": subscribers,
                "event_bus_events": events
            })
    
    # -------------------------------------------------------------------------
    # AI/ML Component Handlers
    # -------------------------------------------------------------------------
    
    def _handle_ai_status(self, event_data: Dict[str, Any]) -> None:
        """Handle AI status events.
        
        Args:
            event_data: The event data containing AI status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'unknown')
        component = event_data.get('component', 'Unknown')
        models = event_data.get('models', [])
        
        self.logger.info(f"AI component {component} status: {status}")
        
        # Update AI status tracking
        self.ai_status = {
            "connected": status == "connected",
            "component": component,
            "models": models,
            "last_update": time.time()
        }
        
        # Update all tabs that need AI status
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Dashboard", "Settings"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "ai_status": status,
                    "ai_component": component,
                    "ai_models": models
                })
    
    def _handle_ai_response(self, event_data: Dict[str, Any]) -> None:
        """Handle AI response events.
        
        Args:
            event_data: The event data containing AI response information
        """
        if not event_data:
            return
            
        response = event_data.get('response', '')
        source = event_data.get('source', 'Unknown')
        
        self.logger.info(f"Received AI response from {source}")
        
        # Update tabs with response
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Dashboard", "AI"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "ai_response": response,
                    "ai_source": source,
                    "ai_timestamp": time.time()
                })
    
    def _handle_voice_status(self, event_data: Dict[str, Any]) -> None:
        """Handle voice status events.
        
        Args:
            event_data: The event data containing voice status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'inactive')
        engine = event_data.get('engine', 'Unknown')
        
        self.logger.info(f"Voice status: {status} with engine {engine}")
        
        # Update voice-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Dashboard", "Voice", "Settings"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "voice_status": status,
                    "voice_engine": engine,
                    "voice_timestamp": time.time()
                })
    
    def _handle_thoth_status(self, event_data: Dict[str, Any]) -> None:
        """Handle ThothAI status events.
        
        Args:
            event_data: The event data containing ThothAI status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'disconnected')
        model = event_data.get('model', 'Unknown')
        
        self.logger.info(f"ThothAI status: {status} with model {model}")
        
        # Update ThothAI-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Dashboard", "AI", "Settings"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "thoth_status": status,
                    "thoth_model": model,
                    "thoth_timestamp": time.time()
                })
    
    # -------------------------------------------------------------------------
    # Trading Component Handlers
    # -------------------------------------------------------------------------
    
    def _handle_trading_integration(self, event_data: Dict[str, Any]) -> None:
        """Handle trading integration status events.
        
        Args:
            event_data: The event data containing trading integration status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'disconnected')
        components = event_data.get('components', {})
        timestamp = event_data.get('timestamp', None)
        
        integrated_count = sum(1 for c in components.values() if c.get('integrated', False))
        total_count = len(components)
        
        self.logger.info(f"Trading integration status: {status} with {integrated_count}/{total_count} components integrated")
        
        # Update status tracking
        self.trading_integration_status = {
            "connected": status == "connected",
            "components": components,
            "last_update": timestamp or time.time()
        }
        
        # Update UI indicator
        if status == "connected":
            self.trading_indicator.config(
                text=f"Trading Integration: Connected ({integrated_count}/{total_count})", 
                fg="green"
            )
        elif status == "partial":
            self.trading_indicator.config(
                text=f"Trading Integration: Partial ({integrated_count}/{total_count})", 
                fg="orange"
            )
        else:
            self.trading_indicator.config(text="Trading Integration: Not Connected", fg="red")
            
        # Update trading tab if exists
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            self.tab_manager.update_tab_data("Trading", {
                "status": status,
                "components": components,
                "integrated_count": integrated_count,
                "total_count": total_count
            })
    
    def _handle_market_update(self, event_data: Dict[str, Any]) -> None:
        """Handle market update events.
        
        Args:
            event_data: The event data containing market update information
        """
        if not event_data:
            return
            
        symbol = event_data.get('symbol', 'Unknown')
        price = event_data.get('price', 0.0)
        change = event_data.get('change', 0.0)
        
        self.logger.info(f"Market update for {symbol}: {price} ({change:+.2f}%)")
        
        # Update trading tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            self.tab_manager.update_tab_data("Trading", {
                "market_updates": {
                    symbol: {
                        "price": price,
                        "change": change,
                        "timestamp": time.time()
                    }
                }
            })
            
            # Also update the dashboard
            self.tab_manager.update_tab_data("Dashboard", {
                "latest_market_update": {
                    "symbol": symbol,
                    "price": price,
                    "change": change
                }
            })
    
    def _handle_trade_confirmed(self, event_data: Dict[str, Any]) -> None:
        """Handle trade confirmation events.
        
        Args:
            event_data: The event data containing trade confirmation information
        """
        if not event_data:
            return
            
        trade_id = event_data.get('id', 'Unknown')
        symbol = event_data.get('symbol', 'Unknown')
        side = event_data.get('side', 'Unknown')
        amount = event_data.get('amount', 0.0)
        price = event_data.get('price', 0.0)
        
        self.logger.info(f"Trade confirmed: {side} {amount} {symbol} at {price}")
        
        # Update trading tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            self.tab_manager.update_tab_data("Trading", {
                "recent_trades": [{
                    "id": trade_id,
                    "symbol": symbol,
                    "side": side,
                    "amount": amount,
                    "price": price,
                    "timestamp": time.time()
                }]
            })
    
    def _handle_portfolio_update(self, event_data: Dict[str, Any]) -> None:
        """Handle portfolio update events.
        
        Args:
            event_data: The event data containing portfolio update information
        """
        if not event_data:
            return
            
        balance = event_data.get('balance', 0.0)
        assets = event_data.get('assets', {})
        
        self.logger.info(f"Portfolio update: Balance {balance}, {len(assets)} assets")
        
        # Update portfolio-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Trading", "Portfolio", "Dashboard"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "portfolio": {
                        "balance": balance,
                        "assets": assets,
                        "timestamp": time.time()
                    }
                })
    
    # -------------------------------------------------------------------------
    # Blockchain/Mining Handlers
    # -------------------------------------------------------------------------
    
    def _handle_blockchain_status(self, event_data: Dict[str, Any]) -> None:
        """Handle blockchain status events.
        
        Args:
            event_data: The event data containing blockchain status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'disconnected')
        network = event_data.get('network', 'Unknown')
        block_height = event_data.get('block_height', 0)
        
        self.logger.info(f"Blockchain {network} status: {status}, block height: {block_height}")
        
        # Update blockchain status tracking
        self.blockchain_status = {
            "connected": status == "connected",
            "network": network,
            "block_height": block_height,
            "last_update": time.time()
        }
        
        # Update blockchain-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Mining", "Blockchain", "Dashboard"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "blockchain_status": status,
                    "blockchain_network": network,
                    "blockchain_height": block_height
                })
    
    def _handle_mining_status(self, event_data: Dict[str, Any]) -> None:
        """Handle mining status events.
        
        Args:
            event_data: The event data containing mining status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'inactive')
        hashrate = event_data.get('hashrate', 0)
        shares = event_data.get('shares', 0)
        
        self.logger.info(f"Mining status: {status}, hashrate: {hashrate} H/s, shares: {shares}")
        
        # Update mining status tracking
        self.mining_status = {
            "active": status == "active",
            "hashrate": hashrate,
            "shares": shares,
            "last_update": time.time()
        }
        
        # Update mining-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Mining", "Dashboard"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "mining_status": status,
                    "mining_hashrate": hashrate,
                    "mining_shares": shares
                })
    
    def _handle_wallet_balance(self, event_data: Dict[str, Any]) -> None:
        """Handle wallet balance events.
        
        Args:
            event_data: The event data containing wallet balance information
        """
        if not event_data:
            return
            
        balance = event_data.get('balance', 0.0)
        currency = event_data.get('currency', 'Unknown')
        
        self.logger.info(f"Wallet balance update: {balance} {currency}")
        
        # Update wallet status tracking
        self.wallet_status = {
            "connected": True,
            "balance": balance,
            "currency": currency,
            "last_update": time.time()
        }
        
        # Update wallet-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Mining", "Wallet", "Dashboard"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "wallet_balance": balance,
                    "wallet_currency": currency
                })
    
    def _handle_wallet_transaction(self, event_data: Dict[str, Any]) -> None:
        """Handle wallet transaction events.
        
        Args:
            event_data: The event data containing wallet transaction information
        """
        if not event_data:
            return
            
        tx_id = event_data.get('tx_id', 'Unknown')
        amount = event_data.get('amount', 0.0)
        currency = event_data.get('currency', 'Unknown')
        status = event_data.get('status', 'pending')
        
        self.logger.info(f"Wallet transaction: {amount} {currency}, status: {status}")
        
        # Update wallet-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Mining", "Wallet", "Dashboard"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "recent_transactions": [{
                        "tx_id": tx_id,
                        "amount": amount,
                        "currency": currency,
                        "status": status,
                        "timestamp": time.time()
                    }]
                })
    
    # -------------------------------------------------------------------------
    # VR System Handlers
    # -------------------------------------------------------------------------
    
    def _handle_vr_status(self, event_data: Dict[str, Any]) -> None:
        """Handle VR system status events.
        
        Args:
            event_data: The event data containing VR system status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'disconnected')
        timestamp = event_data.get('timestamp', None)
        
        self.logger.info(f"VR system status: {status}")
        
        # Update status tracking
        self.vr_status.update({
            "connected": status == "connected",
            "status": status,
            "last_update": timestamp or time.time()
        })
        
        # Update UI indicator
        if status == "connected":
            self.vr_indicator.config(text="VR System: Active", fg="green")
        elif status == "connecting":
            self.vr_indicator.config(text="VR System: Connecting...", fg="orange")
        else:
            self.vr_indicator.config(text="VR System: Inactive", fg="gray")
            
        # Update VR System tab if exists
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            self.tab_manager.update_tab_data("VR System", event_data)
    
    def _handle_headset_status(self, event_data: Dict[str, Any]) -> None:
        """Handle VR headset status events.
        
        Args:
            event_data: The event data containing VR headset status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'not_detected')
        model = event_data.get('model', 'Unknown')
        
        # Update status tracking
        self.vr_status.update({
            "headset": status,
            "model": model,
            "last_update": time.time()
        })
        
        # Update VR System tab if exists
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            self.tab_manager.update_tab_data("VR System", event_data)
    
    def _handle_vr_tracking_status(self, event_data: Dict[str, Any]) -> None:
        """Handle VR tracking status events.
        
        Args:
            event_data: The event data containing VR tracking status information
        """
        if not event_data:
            return
            
        status = event_data.get('status', 'not_tracked')
        controllers = event_data.get('controllers', 0)
        
        # Update status tracking
        self.vr_status.update({
            "tracking": status,
            "controllers": controllers,
            "last_update": time.time()
        })
        
        # Update VR System tab if exists
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            self.tab_manager.update_tab_data("VR System", event_data)
    
    # -------------------------------------------------------------------------
    # Settings and API Handlers
    # -------------------------------------------------------------------------
    
    def _handle_settings_changed(self, event_data: Dict[str, Any]) -> None:
        """Handle settings changed events.
        
        Args:
            event_data: The event data containing settings information
        """
        if not event_data:
            return
            
        settings = event_data.get('settings', {})
        source = event_data.get('source', 'Unknown')
        
        self.logger.info(f"Settings changed from {source}: {len(settings)} settings")
        
        # Update all tabs with new settings
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in self.tab_manager.tabs:
                self.tab_manager.update_tab_data(tab_name, {
                    "settings": settings
                })
    
    def _handle_api_key_added(self, event_data: Dict[str, Any]) -> None:
        """Handle API key added events.
        
        Args:
            event_data: The event data containing API key information
        """
        if not event_data:
            return
            
        service = event_data.get('service', 'Unknown')
        
        self.logger.info(f"API key added for service: {service}")
        
        # Update API-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Settings", "API Keys"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "api_key_added": {
                        "service": service,
                        "timestamp": time.time()
                    }
                })
    
    def _handle_api_key_deleted(self, event_data: Dict[str, Any]) -> None:
        """Handle API key deleted events.
        
        Args:
            event_data: The event data containing API key information
        """
        if not event_data:
            return
            
        service = event_data.get('service', 'Unknown')
        
        self.logger.info(f"API key deleted for service: {service}")
        
        # Update API-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Settings", "API Keys"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "api_key_deleted": {
                        "service": service,
                        "timestamp": time.time()
                    }
                })
    
    def _handle_api_key_test_result(self, event_data: Dict[str, Any]) -> None:
        """Handle API key test result events.
        
        Args:
            event_data: The event data containing API key test information
        """
        if not event_data:
            return
            
        service = event_data.get('service', 'Unknown')
        success = event_data.get('success', False)
        message = event_data.get('message', '')
        
        self.logger.info(f"API key test for {service}: {'Success' if success else 'Failed'}")
        
        # Update API-related tabs
        if hasattr(self, 'tab_manager') and self.tab_manager and hasattr(self.tab_manager, 'update_tab_data'):
            for tab_name in ["Settings", "API Keys"]:
                self.tab_manager.update_tab_data(tab_name, {
                    "api_key_test": {
                        "service": service,
                        "success": success,
                        "message": message,
                        "timestamp": time.time()
                    }
                })
