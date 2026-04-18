#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Key Manager Module for Kingdom AI - Security Manager Wrapper

DEPRECATED: This module is a thin wrapper around the main APIKeyManager.
Use core.api_key_manager.APIKeyManager directly for all new code.

This wrapper maintains backward compatibility for components that import
from core.security_manager.api_key_manager.
"""

import os
import logging
import warnings
from typing import Dict, List, Any, Optional

# Set up logging
logger = logging.getLogger(__name__)

# Import the authoritative implementation
try:
    from core.api_key_manager import APIKeyManager as MainAPIKeyManager
    HAS_MAIN_MANAGER = True
except ImportError:
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from core.api_key_manager import APIKeyManager as MainAPIKeyManager
        HAS_MAIN_MANAGER = True
    except ImportError:
        HAS_MAIN_MANAGER = False
        MainAPIKeyManager = None


class APIKeyManager:
    """
    API Key Manager Wrapper for backward compatibility.
    
    DEPRECATED: Use core.api_key_manager.APIKeyManager directly.
    
    This wrapper delegates all operations to the main APIKeyManager
    in core/api_key_manager.py (2026 SOTA implementation).
    """
    
    _deprecation_warned = False
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, event_bus: Optional[Any] = None):
        """
        Initialize the API Key Manager wrapper.
        
        Args:
            config: API Key Manager configuration settings
            event_bus: Event bus for component communication
        """
        # Emit deprecation warning once
        if not APIKeyManager._deprecation_warned:
            warnings.warn(
                "core.security_manager.api_key_manager.APIKeyManager is deprecated. "
                "Use core.api_key_manager.APIKeyManager instead.",
                DeprecationWarning,
                stacklevel=2
            )
            logger.warning("⚠️ DEPRECATED: Using wrapper APIKeyManager from security_manager")
            logger.warning("   Migrate to: from core.api_key_manager import APIKeyManager")
            APIKeyManager._deprecation_warned = True
        
        # Delegate to main implementation
        if HAS_MAIN_MANAGER:
            self._main_manager = MainAPIKeyManager.get_instance(
                event_bus=event_bus,
                config=config
            )
            self.component_id = self._main_manager.component_id if hasattr(self._main_manager, 'component_id') else "api_key_manager_wrapper"
            self.component_name = "APIKeyManager (Wrapper)"
            self.version = "2.0.0-wrapper"
            self.api_keys = self._main_manager.api_keys
            self.config = config or {}
            self.event_bus = event_bus
            self.is_initialized = True
            logger.info(f"APIKeyManager wrapper initialized (delegating to main manager)")
        else:
            # Fallback: standalone initialization
            logger.error("Main APIKeyManager not available - operating in standalone mode")
            self.config = config or {}
            self.event_bus = event_bus
            self.component_id = "api_key_manager_fallback"
            self.component_name = "APIKeyManager"
            self.version = "1.0.0-fallback"
            self.api_keys = {}
            self.is_initialized = False
            self._main_manager = None
    
    async def initialize(self):
        """
        Initialize the API Key Manager component.
        
        Returns:
            bool: True if initialization was successful
        """
        if self.is_initialized:
            logger.info("APIKeyManager already initialized")
            return self
        
        logger.info("Initializing APIKeyManager...")
        
        try:
            # Load API keys
            self._load_api_keys()
            
            # Register event handlers (synchronous EventBus API)
            if self.event_bus:
                if hasattr(self.event_bus, 'subscribe'):
                    self.event_bus.subscribe("api.key.generate", self.handle_generate_key_event)
                    self.event_bus.subscribe("api.key.validate", self.handle_validate_key_event)
                    self.event_bus.subscribe("api.key.revoke", self.handle_revoke_key_event)
                    self.event_bus.subscribe("api.key.list", self.handle_list_keys_event)
                    self.event_bus.subscribe("system.shutdown", self.handle_shutdown_event)
                    logger.info("Registered API Key Manager event handlers")
            
            self.is_initialized = True
            logger.info("APIKeyManager initialized successfully")
            return self
            
        except Exception as e:
            logger.error(f"Failed to initialize APIKeyManager: {e}")
            return self
    
    def _load_api_keys(self) -> bool:
        """
        Load API keys from disk.
        
        Returns:
            bool: True if API keys were loaded successfully
        """
        with self.key_lock:
            try:
                if os.path.exists(self.api_key_file):
                    with open(self.api_key_file, 'r') as f:
                        self.api_keys = json.load(f)
                    logger.info(f"Loaded {len(self.api_keys)} API keys")
                else:
                    self.api_keys = {}
                    logger.info("No API keys file found, starting with empty keys")
                return True
            except Exception as e:
                logger.error(f"Error loading API keys: {e}")
                self.api_keys = {}
                return False
    
    def _save_api_keys(self) -> bool:
        """
        Save API keys to disk.
        
        Returns:
            bool: True if API keys were saved successfully
        """
        with self.key_lock:
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(self.api_key_file), exist_ok=True)
                
                with open(self.api_key_file, 'w') as f:
                    json.dump(self.api_keys, f, indent=2)
                logger.info(f"Saved {len(self.api_keys)} API keys")
                return True
            except Exception as e:
                logger.error(f"Error saving API keys: {e}")
                return False
    
    def generate_key(self, service_name: str, permissions: List[str] = None,
                     expires_in_days: int = None, rate_limit: int = None) -> Dict[str, Any]:
        """
        Generate a new API key for the specified service.
        
        Args:
            service_name: Name of the service/application this key is for
            permissions: List of allowed resources/actions
            expires_in_days: Number of days until key expires
            rate_limit: Maximum requests per hour
            
        Returns:
            Dictionary with API key information
        """
        with self.key_lock:
            try:
                key_id = str(uuid.uuid4())
                key_secret = secrets.token_hex(32)
                
                # Compute key hash for storage
                key_hash = hashlib.sha256(key_secret.encode()).hexdigest()
                
                # Set expiry date
                expiry_days = expires_in_days or self.default_expiry_days
                expires_at = int(time.time()) + (expiry_days * 86400)
                
                # Create key entry
                key_entry = {
                    'id': key_id,
                    'service': service_name,
                    'hash': key_hash,
                    'created_at': int(time.time()),
                    'expires_at': expires_at,
                    'permissions': permissions or ['read'],
                    'rate_limit': rate_limit or self.default_rate_limit,
                    'last_used': None,
                    'use_count': 0,
                    'active': True
                }
                
                # Store in keys dict
                self.api_keys[key_id] = key_entry
                
                # Save to disk
                self._save_api_keys()
                
                # Return full key (only time this is available)
                return {
                    'key': f"{key_id}.{key_secret}",
                    'id': key_id,
                    'service': service_name,
                    'expires_at': expires_at,
                    'permissions': key_entry['permissions'],
                    'rate_limit': key_entry['rate_limit']
                }
                
            except Exception as e:
                logger.error(f"Error generating API key: {e}")
                return {'error': str(e)}
    
    def validate_key(self, api_key: str, resource: str = None, action: str = None) -> Dict[str, Any]:
        """
        Validate an API key and check permissions if requested.
        
        Args:
            api_key: The API key in format "id.secret"
            resource: Resource being accessed (optional)
            action: Action being performed (optional)
            
        Returns:
            Validation result dictionary with is_valid flag
        """
        try:
            # Split key into ID and secret
            key_parts = api_key.split('.')
            if len(key_parts) != 2:
                return {'is_valid': False, 'reason': 'invalid_format'}
            
            key_id, key_secret = key_parts
            
            with self.key_lock:
                # Check if key ID exists
                if key_id not in self.api_keys:
                    return {'is_valid': False, 'reason': 'unknown_key'}
                
                key_entry = self.api_keys[key_id]
                
                # Check if key is active
                if not key_entry.get('active', True):
                    return {'is_valid': False, 'reason': 'revoked'}
                
                # Check expiration
                if int(time.time()) > key_entry.get('expires_at', 0):
                    return {'is_valid': False, 'reason': 'expired'}
                
                # Verify secret
                expected_hash = key_entry.get('hash')
                actual_hash = hashlib.sha256(key_secret.encode()).hexdigest()
                
                if not hmac.compare_digest(expected_hash, actual_hash):
                    return {'is_valid': False, 'reason': 'invalid_secret'}
                
                # Update usage statistics
                key_entry['last_used'] = int(time.time())
                key_entry['use_count'] = key_entry.get('use_count', 0) + 1
                
                # Check permissions if resource and action are provided
                if resource and action:
                    permissions = key_entry.get('permissions', [])
                    has_permission = False
                    
                    # Check for direct permission
                    direct_perm = f"{resource}:{action}"
                    if direct_perm in permissions or '*' in permissions:
                        has_permission = True
                    
                    # Check for wildcard permissions
                    resource_wildcard = f"{resource}:*"
                    action_wildcard = f"*:{action}"
                    
                    if resource_wildcard in permissions or action_wildcard in permissions:
                        has_permission = True
                    
                    if not has_permission:
                        return {
                            'is_valid': True,
                            'key_id': key_id,
                            'service': key_entry.get('service'),
                            'has_permission': False,
                            'reason': 'permission_denied'
                        }
                
                # Key is valid!
                return {
                    'is_valid': True,
                    'key_id': key_id,
                    'service': key_entry.get('service'),
                    'has_permission': True if not (resource and action) else has_permission
                }
                
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return {'is_valid': False, 'reason': 'validation_error', 'error': str(e)}
    
    def revoke_key(self, key_id: str) -> bool:
        """
        Revoke an existing API key.
        
        Args:
            key_id: ID of the API key to revoke
            
        Returns:
            bool: True if key was revoked successfully
        """
        with self.key_lock:
            try:
                if key_id in self.api_keys:
                    self.api_keys[key_id]['active'] = False
                    self._save_api_keys()
                    logger.info(f"Revoked API key: {key_id}")
                    return True
                else:
                    logger.warning(f"Attempted to revoke unknown API key: {key_id}")
                    return False
            except Exception as e:
                logger.error(f"Error revoking API key: {e}")
                return False
    
    def list_keys(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        List all API keys (without secrets).
        
        Args:
            include_inactive: Whether to include inactive/revoked keys
            
        Returns:
            List of API key information dictionaries
        """
        with self.key_lock:
            try:
                result = []
                for key_id, key_data in self.api_keys.items():
                    # Skip inactive keys if not requested
                    if not include_inactive and not key_data.get('active', True):
                        continue
                    
                    # Create a clean copy without sensitive data
                    key_info = {
                        'id': key_id,
                        'service': key_data.get('service'),
                        'created_at': key_data.get('created_at'),
                        'expires_at': key_data.get('expires_at'),
                        'last_used': key_data.get('last_used'),
                        'use_count': key_data.get('use_count', 0),
                        'active': key_data.get('active', True),
                        'permissions': key_data.get('permissions', []),
                        'rate_limit': key_data.get('rate_limit')
                    }
                    result.append(key_info)
                
                return result
            except Exception as e:
                logger.error(f"Error listing API keys: {e}")
                return []
    
    async def handle_generate_key_event(self, data: Dict[str, Any]):
        """
        Handle API key generation event from the event bus.
        
        Args:
            data: Event data containing key generation parameters
        """
        try:
            # Extract parameters
            service_name = data.get('service', 'default')
            permissions = data.get('permissions')
            expires_in_days = data.get('expires_in_days')
            rate_limit = data.get('rate_limit')
            
            # Generate the key
            result = self.generate_key(
                service_name=service_name,
                permissions=permissions,
                expires_in_days=expires_in_days,
                rate_limit=rate_limit
            )
            
            # Publish result
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                self.event_bus.publish(
                    "api.key.generated",
                    {
                        'request_id': data.get('request_id'),
                        'result': result
                    }
                )
                
        except Exception as e:
            logger.error(f"Error handling API key generation event: {e}")
            # Publish error
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                self.event_bus.publish(
                    "api.key.error",
                    {
                        'request_id': data.get('request_id'),
                        'error': str(e)
                    }
                )
    
    async def handle_validate_key_event(self, data: Dict[str, Any]):
        """
        Handle API key validation event from the event bus.
        
        Args:
            data: Event data containing key to validate
        """
        try:
            # Extract parameters
            api_key = data.get('api_key')
            resource = data.get('resource')
            action = data.get('action')
            
            # Validate the key
            result = self.validate_key(
                api_key=str(api_key or ""),
                resource=resource,
                action=action
            )
            
            # Publish result
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                self.event_bus.publish(
                    "api.key.validated",
                    {
                        'request_id': data.get('request_id'),
                        'result': result
                    }
                )
                
        except Exception as e:
            logger.error(f"Error handling API key validation event: {e}")
            # Publish error
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                await self.event_bus.publish(
                    "api.key.error",
                    {
                        'request_id': data.get('request_id'),
                        'error': str(e)
                    }
                )
    
    async def handle_revoke_key_event(self, data: Dict[str, Any]):
        """
        Handle API key revocation event from the event bus.
        
        Args:
            data: Event data containing key ID to revoke
        """
        try:
            # Extract parameters
            key_id = data.get('key_id')
            
            # Revoke the key
            result = self.revoke_key(key_id=str(key_id or ""))
            
            # Publish result
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                self.event_bus.publish(
                    "api.key.revoked",
                    {
                        'request_id': data.get('request_id'),
                        'success': result,
                        'key_id': key_id
                    }
                )
                
        except Exception as e:
            logger.error(f"Error handling API key revocation event: {e}")
            # Publish error
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                await self.event_bus.publish(
                    "api.key.error",
                    {
                        'request_id': data.get('request_id'),
                        'error': str(e)
                    }
                )
    
    async def handle_list_keys_event(self, data: Dict[str, Any]):
        """
        Handle API key listing event from the event bus.
        
        Args:
            data: Event data containing listing parameters
        """
        try:
            # Extract parameters
            include_inactive = data.get('include_inactive', False)
            
            # List keys
            result = self.list_keys(include_inactive=include_inactive)
            
            # Publish result
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                self.event_bus.publish(
                    "api.key.listed",
                    {
                        'request_id': data.get('request_id'),
                        'keys': result
                    }
                )
                
        except Exception as e:
            logger.error(f"Error handling API key listing event: {e}")
            # Publish error
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                await self.event_bus.publish(
                    "api.key.error",
                    {
                        'request_id': data.get('request_id'),
                        'error': str(e)
                    }
                )
    
    async def handle_shutdown_event(self, data: Dict[str, Any]):
        """
        Handle system shutdown event from the event bus.
        
        Args:
            data: Event data (not used)
        """
        try:
            await self.shutdown()
        except Exception as e:
            logger.error(f"Error handling shutdown event: {e}")
    
    async def shutdown(self):
        """
        Shutdown the API Key Manager component.
        
        Returns:
            bool: True if shutdown was successful
        """
        try:
            logger.info("Shutting down APIKeyManager...")
            
            # Save any pending API key changes
            self._save_api_keys()
            
            self.is_initialized = False
            logger.info("APIKeyManager shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error shutting down APIKeyManager: {e}")
            return False
