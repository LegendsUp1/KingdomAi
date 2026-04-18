#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Security Manager Module for Kingdom AI.

This module provides security management capabilities for the Kingdom AI system,
including authentication, authorization, encryption services, and security monitoring.
"""

import uuid
import base64
import json
import os
import logging
import threading
import hashlib
import hmac
import secrets
import ipaddress
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

# Additional imports with proper fallback handling
try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False
    logger = logging.getLogger(__name__)
    logger.warning("bcrypt not available, falling back to builtin hashlib")

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger = logging.getLogger(__name__)
    logger.warning("cryptography libraries not available, using fallback encryption")

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False
    logger = logging.getLogger(__name__)
    logger.warning("PyJWT not available, token features will be limited")

# Additional imports with proper fallback handling
try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False
    logger = logging.getLogger(__name__)
    logger.warning("bcrypt not available, falling back to builtin hashlib")

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger = logging.getLogger(__name__)
    logger.warning("cryptography libraries not available, using fallback encryption")

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False
    logger = logging.getLogger(__name__)
    logger.warning("PyJWT not available, token features will be limited")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for library availability
# Initialize with default values
# CRYPTO_AVAILABLE is set by the _setup_security_libraries function  
# JWT_AVAILABLE is set by the _setup_security_libraries function

# Function to import optional libraries and set availability flags
def _setup_security_libraries():
    # Initialize local availability flags
    has_bcrypt = False
    has_crypto = False
    has_jwt = False
    crypto_available = False
    jwt_available = False
    
    # Try to import bcrypt for password hashing
    try:
        import bcrypt
        has_bcrypt = True
    except ImportError:
        logger.warning("bcrypt not available, falling back to builtin hashlib")
    
    # Try to import cryptography libraries
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.backends import default_backend
        has_crypto = True
        logger.info("Cryptography libraries are available")
    except ImportError:
        logger.warning("Cryptography library not available, falling back to basic encryption")
    
    # Try to import JWT library
    try:
        import jwt
        has_jwt = True
        logger.info("JWT libraries are available")
    except ImportError:
        logger.warning("PyJWT not available, falling back to custom token implementation")
    
    # Set final availability flags
    if has_bcrypt and has_crypto:
        crypto_available = True
    
    if has_jwt:
        jwt_available = True
        
    return has_bcrypt, has_crypto, has_jwt, crypto_available, jwt_available

# Import libraries and set global availability flags
has_bcrypt, has_crypto, has_jwt, CRYPTO_AVAILABLE, JWT_AVAILABLE = _setup_security_libraries()



class SecurityManager:
    """
    Security Manager for the Kingdom AI system.
    
    Handles authentication, authorization, encryption, and overall security
    for the Kingdom AI system. Provides comprehensive security services including:
    
    - User authentication and session management
    - Role-based and resource-based authorization
    - Data encryption and secure key management
    - Security monitoring and intrusion detection
    - API security and access control
    - Audit logging for security events
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, event_bus: Optional[Any] = None):
        """
        Initialize the Security Manager component.
        
        Args:
            config: Security manager configuration settings
            event_bus: Event bus for component communication
        """
        # Setup component configuration
        self.config = config or {}
        self.event_bus = event_bus
        self.component_id = "security_manager_01"
        self.component_name = "SecurityManager"
        self.version = "1.0.0"
        
        # Try to get ConfigManager
        try:
            from core.config_manager import ConfigManager
            self.config_manager = ConfigManager(event_bus=event_bus)
            logger.debug("Initialized ConfigManager in SecurityManager")
        except Exception as e:
            logger.warning(f"Could not initialize ConfigManager: {e}")
            self.config_manager = None
        
        # Base directory paths
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.security_dir = os.path.join(self.base_dir, 'data', 'security')
        self.certs_dir = os.path.join(self.security_dir, 'certs')
        self.keys_dir = os.path.join(self.security_dir, 'keys')
        
        # Create security directories if they don't exist
        for directory in [self.security_dir, self.certs_dir, self.keys_dir]:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory)
                    logger.info(f"Created security directory: {directory}")
                except Exception as e:
                    logger.error(f"Failed to create security directory {directory}: {e}")
        
        # Internal state and locks
        self.is_initialized = False
        self.lock = threading.RLock()
        self.session_lock = threading.RLock()
        self.auth_lock = threading.RLock()
        self.key_lock = threading.RLock()
        
        # Security objects
        self.active_sessions = {}
        self.blocked_ips = set()
        self.failed_attempts = {}
        self.users = {}
        
        # Authentication settings
        self.max_failed_attempts = self.config.get('max_failed_attempts', 5)
        self.lockout_duration = self.config.get('lockout_duration', 900)  # 15 minutes in seconds
        self.session_lifetime = self.config.get('session_lifetime', 3600)  # 1 hour in seconds
        self.token_secret = self.config.get('token_secret', secrets.token_hex(32))
        
        # Permission system
        self.permission_levels = {
            'system': 1000,  # System/internal operations
            'admin': 100,   # Administrator
            'manager': 75,  # Manager
            'power': 60,    # Power user
            'user': 50,     # Regular user
            'limited': 25,  # Limited user
            'guest': 10,    # Guest user
            'none': 0       # No permissions
        }
        
        # Resource permissions
        self.resource_permissions = {}
        
        # Encryption keys
        self.encryption_keys = {}
        self.default_key = None
        
        # Security monitoring
        self.audit_log = []
        self.max_audit_log_size = self.config.get('max_audit_log_size', 1000)
        self.suspicious_activities = []
        
        # API security
        self.api_keys = {}
        self.rate_limits = {}
        
        # Action permission thresholds
        self.action_thresholds = {
            'read': 10,     # Guest level
            'list': 10,     # Guest level
            'view': 10,     # Guest level
            'write': 50,    # User level
            'modify': 50,   # User level
            'update': 50,   # User level
            'create': 50,   # User level
            'delete': 75,   # Manager level
            'execute': 75,  # Manager level
            'admin': 100    # Admin level
        }
        
        logger.info(f"SecurityManager instance created (version {self.version})")
        
    async def initialize(self) -> bool:
        """
        Initialize the Security Manager component.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        logger.info("Initializing Security Manager...")
        
        with self.lock:
            # Avoid re-initialization if already initialized
            if self.is_initialized:
                logger.debug("Security Manager already initialized")
                return True
                
            # Ensure config_manager has the required methods if it exists
            if self.config_manager is not None:
                if not hasattr(self.config_manager, 'get_config'):
                    # Use get method if available, otherwise create a default getter
                    get_method = getattr(self.config_manager, 'get', None)
                    if get_method:
                        self.config_manager.get_config = get_method
                    else:
                        self.config_manager.get_config = lambda path, default=None: default
                        logger.warning("Using default config getter")
            
            # Load security configuration
            try:
                if self.config_manager:
                    security_config = self.config_manager.get_config('security', {})
                    if security_config:
                        # Update permission levels
                        self.permission_levels.update(security_config.get('permission_levels', {}))
                        
                        # Update authentication settings
                        auth_config = security_config.get('authentication', {})
                        self.max_failed_attempts = auth_config.get('max_failed_attempts', self.max_failed_attempts)
                        self.lockout_duration = auth_config.get('lockout_duration', self.lockout_duration)
                        self.session_lifetime = auth_config.get('session_lifetime', self.session_lifetime)
                        
                        # Update security monitoring settings
                        monitoring_config = security_config.get('monitoring', {})
                        self.max_audit_log_size = monitoring_config.get('max_audit_log_size', self.max_audit_log_size)
                        
                        logger.info("Updated security configuration from config manager")
            except Exception as e:
                logger.warning(f"Error loading security configuration: {e}")
            
            # Initialize encryption keys
            try:
                await self._initialize_encryption_keys()
            except Exception as e:
                logger.error(f"Failed to initialize encryption keys: {e}")
                return False
            
            # Load user data
            try:
                await self._load_users()
            except Exception as e:
                logger.error(f"Failed to load user data: {e}")
                return False
            
            # Load resource permissions
            try:
                await self._load_resource_permissions()
            except Exception as e:
                logger.error(f"Failed to load resource permissions: {e}")
                return False
            
            # Register with event bus
            if self.event_bus:
                try:
                    # Register event handlers
                    await self.event_bus.subscribe('system.security.authenticate', self.handle_authenticate_event)
                    await self.event_bus.subscribe('system.security.authorize', self.handle_authorize_event)
                    await self.event_bus.subscribe('system.security.encrypt', self.handle_encrypt_event)
                    await self.event_bus.subscribe('system.security.decrypt', self.handle_decrypt_event)
                    await self.event_bus.subscribe('system.security.create_user', self.handle_create_user_event)
                    await self.event_bus.subscribe('system.security.change_password', self.handle_change_password_event)
                    await self.event_bus.subscribe('system.security.logout', self.handle_logout_event)
                    await self.event_bus.subscribe('system.security.validate_token', self.handle_validate_token_event)
                    await self.event_bus.subscribe('system.security.api_key_auth', self.handle_api_key_auth_event)
                    await self.event_bus.subscribe('system.security.check_permissions', self.handle_check_permissions_event)
                    await self.event_bus.subscribe('system.security.generate_api_key', self.handle_generate_api_key_event)
                    await self.event_bus.subscribe('system.security.get_audit_log', self.handle_get_audit_log_event)
                    await self.event_bus.subscribe('system.shutdown', self.handle_shutdown_event)
                    
                    logger.info("Security Manager events registered with event bus")
                except Exception as e:
                    logger.error(f"Failed to register Security Manager events: {e}")
                    # Continue initialization despite subscription errors
                    # Don't set is_initialized to False as basic functionality can still work
            
            # Set initialized flag
            self.is_initialized = True
            
            # Publish system status update
            if self.event_bus:
                try:
                    # Use publish with await since it's an async method
                    await self.event_bus.publish('component.status', {
                        'component': self.component_name,
                        'component_id': self.component_id,
                        'status': 'initialized',
                        'version': self.version,
                        'message': 'Security Manager initialized successfully',
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"Error publishing initialization status: {e}")
            
            logger.info(f"Security Manager initialized successfully (version {self.version})")
            return self.is_initialized
    
    async def _initialize_encryption_keys(self) -> bool:
        """
        Initialize encryption keys for the security manager.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        with self.key_lock:
            # Check if we have existing keys
            key_file = os.path.join(self.keys_dir, 'encryption_keys.json')
            
            if os.path.exists(key_file):
                try:
                    # Load existing keys
                    with open(key_file, 'r') as f:
                        keys_data = json.load(f)
                    
                    for key_id, key_data in keys_data.items():
                        self.encryption_keys[key_id] = {
                            'key': base64.b64decode(key_data['key']),
                            'created_at': key_data['created_at'],
                            'purpose': key_data['purpose'],
                            'algorithm': key_data['algorithm']
                        }
                    
                    # Set default key to the most recent one
                    if self.encryption_keys:
                        self.default_key = max(self.encryption_keys.keys(), 
                                            key=lambda k: self.encryption_keys[k]['created_at'])
                        logger.info(f"Loaded {len(self.encryption_keys)} encryption keys")
                    else:
                        # No keys found, create a new one
                        await self._create_new_encryption_key()
                except Exception as e:
                    logger.error(f"Error loading encryption keys: {e}")
                    # Create a new key if there was an error
                    await self._create_new_encryption_key()
            else:
                # No keys file exists, create a new key
                await self._create_new_encryption_key()
            
            return True
    
    async def _create_new_encryption_key(self) -> str:
        """
        Create a new encryption key.
        
        Returns:
            str: ID of the newly created key
        """
        with self.key_lock:
            # Generate a unique key ID
            key_id = str(uuid.uuid4())
            
            if CRYPTO_AVAILABLE:
                # Generate a new Fernet key (AES-128 in CBC mode with PKCS7 padding)
                key = Fernet.generate_key()
                algorithm = "AES-128-CBC"
            else:
                # Fallback to a simple key generation method if cryptography is not available
                key = base64.b64encode(secrets.token_bytes(32))
                algorithm = "AES-256-Simple"
            
            # Store the key
            self.encryption_keys[key_id] = {
                'key': key,
                'created_at': datetime.now().isoformat(),
                'purpose': 'general',
                'algorithm': algorithm
            }
            
            # Set as default key
            self.default_key = key_id
            
            # Save to disk
            await self._save_encryption_keys()
            
            logger.info(f"Created new encryption key with ID: {key_id}")
            return key_id
    
    async def _save_encryption_keys(self) -> bool:
        """
        Save encryption keys to disk.
        
        Returns:
            bool: True if keys were saved successfully, False otherwise
        """
        with self.key_lock:
            key_file = os.path.join(self.keys_dir, 'encryption_keys.json')
            
            try:
                # Prepare keys for serialization (convert binary keys to base64)
                keys_data = {}
                for key_id, key_data in self.encryption_keys.items():
                    keys_data[key_id] = {
                        'key': base64.b64encode(key_data['key']).decode('utf-8'),
                        'created_at': key_data['created_at'],
                        'purpose': key_data['purpose'],
                        'algorithm': key_data['algorithm']
                    }
                
                # Save to file
                with open(key_file, 'w') as f:
                    json.dump(keys_data, f, indent=2)
                
                logger.debug(f"Saved {len(self.encryption_keys)} encryption keys to {key_file}")
                return True
            except Exception as e:
                logger.error(f"Error saving encryption keys: {e}")
                return False
    
    async def _load_users(self) -> bool:
        """
        Load user data from disk.
        
        Returns:
            bool: True if users were loaded successfully, False otherwise
        """
        with self.auth_lock:
            user_file = os.path.join(self.security_dir, 'users.json')
            
            if os.path.exists(user_file):
                try:
                    with open(user_file, 'r') as f:
                        self.users = json.load(f)
                    
                    logger.info(f"Loaded {len(self.users)} users from {user_file}")
                    return True
                except Exception as e:
                    logger.error(f"Error loading users: {e}")
                    return False
            else:
                # Create a default admin user if no users exist
                await self._create_default_admin()
                return True
    
    async def _hash_password(self, password: str) -> str:
        """
        Hash a password for storage.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            str: Secure hash of the password
        """
        if CRYPTO_AVAILABLE and hasattr(bcrypt, 'hashpw'):
            # Use bcrypt if available (most secure)
            salt = bcrypt.gensalt(12)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        else:
            # Fallback to PBKDF2 with high iteration count
            salt = secrets.token_bytes(16)
            iterations = 100000  # High iteration count for security
            dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
            return f"pbkdf2:sha256:{iterations}:{base64.b64encode(salt).decode('utf-8')}:{base64.b64encode(dk).decode('utf-8')}"
    
    async def _verify_password(self, stored_hash: str, password: str) -> bool:
        """
        Verify a password against a stored hash.
        
        Args:
            stored_hash: Previously hashed password
            password: Plain text password to verify
            
        Returns:
            bool: True if password matches, False otherwise
        """
        if CRYPTO_AVAILABLE and hasattr(bcrypt, 'checkpw') and stored_hash.startswith('$2'):
            # Verify using bcrypt
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        elif stored_hash.startswith('pbkdf2:'):
            # Verify using PBKDF2
            try:
                _, hash_name, iterations, salt_b64, hash_b64 = stored_hash.split(':')
                iterations = int(iterations)
                salt = base64.b64decode(salt_b64)
                stored_dk = base64.b64decode(hash_b64)
                dk = hashlib.pbkdf2_hmac(hash_name, password.encode('utf-8'), salt, iterations)
                return hmac.compare_digest(stored_dk, dk)
            except Exception as e:
                logger.error(f"Error verifying password: {e}")
                return False
        else:
            logger.error(f"Unknown password hash format: {stored_hash[:10]}...")
            return False
    
    async def _create_default_admin(self) -> bool:
        """
        Create a default admin user if no users exist.
        
        Returns:
            bool: True if default admin was created successfully, False otherwise
        """
        with self.auth_lock:
            # Generate a secure random password
            password = secrets.token_urlsafe(12)
            
            # Create admin user
            admin_id = str(uuid.uuid4())
            self.users[admin_id] = {
                'username': 'admin',
                'password_hash': await self._hash_password(password),
                'email': 'admin@kingdom.ai',
                'role': 'admin',
                'permission_level': self.permission_levels['admin'],
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'failed_attempts': 0,
                'locked_until': None,
                'api_keys': {},
                'settings': {},
                'is_active': True
            }
            
            # Save users to disk
            await self._save_users()
            
            logger.warning(f"Created default admin user with password: {password}")
            logger.warning("Please change this password immediately!")
            
            return True
    
    async def _save_users(self) -> bool:
        """
        Save user data to disk.
        
        Returns:
            bool: True if users were saved successfully, False otherwise
        """
        with self.auth_lock:
            user_file = os.path.join(self.security_dir, 'users.json')
            
            try:
                with open(user_file, 'w') as f:
                    json.dump(self.users, f, indent=2)
                
                logger.debug(f"Saved {len(self.users)} users to {user_file}")
                return True
            except Exception as e:
                logger.error(f"Error saving users: {e}")
                return False
    
    async def _load_resource_permissions(self) -> bool:
        """
        Load resource permissions from disk.
        
        Returns:
            bool: True if permissions were loaded successfully, False otherwise
        """
        permissions_file = os.path.join(self.security_dir, 'permissions.json')
        
        if os.path.exists(permissions_file):
            try:
                with open(permissions_file, 'r') as f:
                    self.resource_permissions = json.load(f)
                
                logger.info(f"Loaded resource permissions from {permissions_file}")
                return True
            except Exception as e:
                logger.error(f"Error loading resource permissions: {e}")
                return False
        else:
            # Create default permissions if file doesn't exist
            await self._create_default_permissions()
            return True
    
    async def _create_default_permissions(self) -> bool:
        """
        Create default resource permissions if none exist.
        
        Returns:
            bool: True if default permissions were created successfully, False otherwise
        """
        # Define default permissions for resources
        self.resource_permissions = {
            # Core system resources
            'system.config': {
                'read': ['admin'],
                'write': ['admin'],
                'execute': ['admin']
            },
            'system.logs': {
                'read': ['admin', 'manager'],
                'write': ['admin'],
                'execute': ['admin']
            },
            'system.security': {
                'read': ['admin'],
                'write': ['admin'],
                'execute': ['admin']
            },
            
            # Trading resources
            'trading.orders': {
                'read': ['admin', 'manager', 'user'],
                'write': ['admin', 'manager', 'user'],
                'execute': ['admin', 'manager']
            },
            'trading.strategies': {
                'read': ['admin', 'manager', 'user'],
                'write': ['admin', 'manager'],
                'execute': ['admin', 'manager']
            },
            'trading.portfolio': {
                'read': ['admin', 'manager', 'user'],
                'write': ['admin', 'manager'],
                'execute': ['admin', 'manager']
            },
            
            # Mining resources
            'mining.settings': {
                'read': ['admin', 'manager', 'user'],
                'write': ['admin', 'manager'],
                'execute': ['admin']
            },
            'mining.hashrate': {
                'read': ['admin', 'manager', 'user', 'guest'],
                'write': ['admin'],
                'execute': ['admin']
            },
            
            # AI resources
            'ai.models': {
                'read': ['admin', 'manager', 'user'],
                'write': ['admin'],
                'execute': ['admin', 'manager', 'user']
            },
            'ai.predictions': {
                'read': ['admin', 'manager', 'user'],
                'write': ['admin', 'manager'],
                'execute': ['admin', 'manager', 'user']
            },
            
            # VR resources
            'vr.settings': {
                'read': ['admin', 'manager', 'user'],
                'write': ['admin', 'manager'],
                'execute': ['admin', 'manager', 'user']
            }
        }
        
        # Save to disk
        permissions_file = os.path.join(self.security_dir, 'permissions.json')
        
        try:
            with open(permissions_file, 'w') as f:
                json.dump(self.resource_permissions, f, indent=2)
            
            logger.info(f"Created default resource permissions in {permissions_file}")
            return True
        except Exception as e:
            logger.error(f"Error creating default permissions: {e}")
            return False
    
    async def authenticate(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authenticate a user with the provided credentials.
        
        Args:
            credentials: Dictionary containing user credentials (username/email and password)
            
        Returns:
            Dict containing authentication result and session info if successful
        """
        logger.info(f"Authentication attempt for user: {credentials.get('username', '<unknown>')}")
        
        if not credentials or not isinstance(credentials, dict):
            return self._failed_auth('Invalid credentials format')
        
        # Check for required fields
        username = credentials.get('username', credentials.get('email'))
        password = credentials.get('password')
        
        if not username or not password:
            return self._failed_auth('Missing username or password')
        
        # Check login attempts to prevent brute force
        client_ip = credentials.get('client_ip', '0.0.0.0')
        if client_ip in self.blocked_ips:
            return self._failed_auth('IP address is blocked due to too many failed attempts')
        
        if client_ip in self.failed_attempts and self.failed_attempts[client_ip]['count'] >= self.max_failed_attempts:
            # Check if enough time has passed to unblock
            block_time = self.failed_attempts[client_ip]['timestamp']
            elapsed = (datetime.now() - datetime.fromisoformat(block_time)).total_seconds()
            
            if elapsed < self.lockout_duration:
                return self._failed_auth(f'Too many failed attempts. Try again in {int(self.lockout_duration - elapsed)} seconds')
            else:
                # Reset failed attempts after lockout period
                self.failed_attempts[client_ip] = {'count': 0, 'timestamp': datetime.now().isoformat()}
        
        # Look up user by username or email
        user_id = None
        user_data = None
        
        for uid, data in self.users.items():
            if data.get('username') == username or data.get('email') == username:
                user_id = uid
                user_data = data
                break
        
        if not user_id or not user_data:
            self._record_failed_attempt(client_ip)
            return self._failed_auth('Invalid username or password')
        
        # Check if account is locked
        if user_data.get('locked_until'):
            lock_time = datetime.fromisoformat(user_data['locked_until'])
            if datetime.now() < lock_time:
                return self._failed_auth(f'Account is locked until {lock_time.isoformat()}')
        
        # Check if account is active
        if not user_data.get('is_active', True):
            return self._failed_auth('Account is disabled')
        
        # Verify password
        password_hash = user_data.get('password_hash', '')
        if not password_hash or not (await self._verify_password(password_hash, password)):
            # Update failed login attempts
            with self.auth_lock:
                user_data['failed_attempts'] = user_data.get('failed_attempts', 0) + 1
                
                # Lock account if too many failures
                if user_data['failed_attempts'] >= self.max_failed_attempts:
                    user_data['locked_until'] = (datetime.now() + timedelta(seconds=self.lockout_duration)).isoformat()
                    logger.warning(f"Account locked for user {username} due to too many failed attempts")
                
                await self._save_users()
            
            self._record_failed_attempt(client_ip)
            return self._failed_auth('Invalid username or password')
        
        # Authentication successful - create session
        session_id = str(uuid.uuid4())
        session_data = {
            'user_id': user_id,
            'username': user_data.get('username'),
            'role': user_data.get('role', 'user'),
            'permission_level': user_data.get('permission_level', self.permission_levels.get('user', 50)),
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(seconds=self.session_lifetime)).isoformat(),
            'client_ip': client_ip,
            'user_agent': credentials.get('user_agent', 'unknown')
        }
        
        # Store session
        with self.session_lock:
            self.active_sessions[session_id] = session_data
        
        # Update user data
        with self.auth_lock:
            user_data['last_login'] = datetime.now().isoformat()
            user_data['failed_attempts'] = 0
            user_data['locked_until'] = None
            await self._save_users()
        
        # Create authentication token
        token = await self._generate_token(session_id, user_id, user_data.get('role', 'user'))
        
        # Add security event to audit log
        await self._add_audit_log_entry('authentication', 'success', {
            'username': username,
            'client_ip': client_ip,
            'session_id': session_id
        })
        
        logger.info(f"Authentication successful for user: {username}")
        
        # Return success with session info
        return {
            'success': True,
            'message': 'Authentication successful',
            'session_id': session_id,
            'token': token,
            'expires_at': session_data['expires_at'],
            'user_info': {
                'user_id': user_id,
                'username': user_data.get('username'),
                'email': user_data.get('email'),
                'role': user_data.get('role', 'user'),
                'permission_level': user_data.get('permission_level', self.permission_levels.get('user', 50))
            }
        }
    
    def _failed_auth(self, message: str) -> Dict[str, Any]:
        """
        Helper to create a failed authentication response.
        
        Args:
            message: Reason for authentication failure
            
        Returns:
            Dict containing failure details
        """
        return {
            'success': False,
            'message': message,
            'error_code': 'AUTH_FAILED'
        }
    
    def _record_failed_attempt(self, client_ip: str) -> None:
        """
        Record a failed authentication attempt for an IP address.
        
        Args:
            client_ip: IP address of the client
        """
        now = datetime.now().isoformat()
        
        if client_ip in self.failed_attempts:
            self.failed_attempts[client_ip]['count'] += 1
            self.failed_attempts[client_ip]['timestamp'] = now
            
            # Block IP if too many failures
            if self.failed_attempts[client_ip]['count'] >= self.max_failed_attempts:
                self.blocked_ips.add(client_ip)
                logger.warning(f"IP {client_ip} blocked due to too many failed login attempts")
        else:
            self.failed_attempts[client_ip] = {'count': 1, 'timestamp': now}
    
    async def _generate_token(self, session_id: str, user_id: str, role: str) -> str:
        """
        Generate an authentication token for a session.
        
        Args:
            session_id: ID of the session
            user_id: ID of the user
            role: User role
            
        Returns:
            str: Generated authentication token
        """
        payload = {
            'session_id': session_id,
            'user_id': user_id,
            'role': role,
            'exp': int((datetime.now() + timedelta(seconds=self.session_lifetime)).timestamp()),
            'iat': int(datetime.now().timestamp()),
            'jti': str(uuid.uuid4())
        }
        
        if JWT_AVAILABLE:
            # Use PyJWT if available
            return jwt.encode(payload, self.token_secret, algorithm='HS256')
        else:
            # Simple fallback (less secure, but functional)
            payload_str = json.dumps(payload)
            payload_b64 = base64.b64encode(payload_str.encode('utf-8')).decode('utf-8')
            
            # Create signature
            signature = hmac.new(
                self.token_secret.encode('utf-8'),
                payload_b64.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return f"{payload_b64}.{signature}"
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate an authentication token.
        
        Args:
            token: Authentication token to validate
            
        Returns:
            Dict containing validation result and session info if valid
        """
        if not token:
            return {'valid': False, 'error': 'No token provided'}
        
        try:
            # Decode token
            if JWT_AVAILABLE:
                # Use PyJWT if available
                payload = jwt.decode(token, self.token_secret, algorithms=['HS256'])
            else:
                # Simple fallback verification
                if '.' not in token:
                    return {'valid': False, 'error': 'Invalid token format'}
                
                payload_b64, signature = token.split('.')
                
                # Verify signature
                expected_signature = hmac.new(
                    self.token_secret.encode('utf-8'),
                    payload_b64.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                if not hmac.compare_digest(signature, expected_signature):
                    return {'valid': False, 'error': 'Invalid token signature'}
                
                # Decode payload
                payload_json = base64.b64decode(payload_b64).decode('utf-8')
                payload = json.loads(payload_json)
            
            # Check expiration
            exp_time = datetime.fromtimestamp(payload.get('exp', 0))
            if datetime.now() > exp_time:
                return {'valid': False, 'error': 'Token has expired'}
            
            # Get session
            session_id = payload.get('session_id')
            if not session_id or session_id not in self.active_sessions:
                return {'valid': False, 'error': 'Invalid session'}
            
            session = self.active_sessions[session_id]
            
            # Return success with session info
            return {
                'valid': True,
                'session_id': session_id,
                'user_id': session.get('user_id'),
                'username': session.get('username'),
                'role': session.get('role'),
                'permission_level': session.get('permission_level')
            }
            
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return {'valid': False, 'error': f'Token validation error: {str(e)}'}
        
    async def _add_audit_log_entry(self, event_type: str, status: str, details: Dict[str, Any]) -> None:
        """
        Add an entry to the security audit log.
        
        Args:
            event_type: Type of security event
            status: Status of the event (success, failure, etc.)
            details: Additional details about the event
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'status': status,
            'details': details
        }
        
        self.audit_log.append(entry)
        
        # Trim audit log if it gets too large
        if len(self.audit_log) > self.max_audit_log_size:
            self.audit_log = self.audit_log[-self.max_audit_log_size:]
            
        if self.config.get("persist_audit_log", False):
            try:
                log_dir = self.config.get("audit_log_dir", "logs")
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, "security_audit.jsonl")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception as persist_err:
                logger.debug(f"Audit log persistence failed: {persist_err}")
    
    async def authorize(self, session_id: str, resource: str, action: str) -> Dict[str, Any]:
        """
        Authorize a session for a specific resource and action.
        
        Args:
            session_id: Active session ID to authorize
            resource: Resource to access (e.g., 'system.config', 'trading.orders')
            action: Action to perform on the resource (e.g., 'read', 'write', 'execute')
            
        Returns:
            Dict containing authorization result and details
        """
        logger.info(f"Authorization request for session {session_id}, resource: {resource}, action: {action}")
        
        # Check session validity
        with self.session_lock:
            if session_id not in self.active_sessions:
                return {
                    'authorized': False,
                    'error': 'Invalid or expired session',
                    'error_code': 'SESSION_INVALID'
                }
            
            session = self.active_sessions[session_id]
            
            # Check session expiration
            if 'expires_at' in session:
                try:
                    expires_at = datetime.fromisoformat(session['expires_at'])
                    if datetime.now() > expires_at:
                        return {
                            'authorized': False,
                            'error': 'Session has expired',
                            'error_code': 'SESSION_EXPIRED'
                        }
                except Exception as e:
                    logger.error(f"Error checking session expiration: {e}")
                    # Continue with authorization despite error
        
        # Get user role and permission level
        user_role = session.get('role', 'guest')
        permission_level = session.get('permission_level', self.permission_levels.get('guest', 10))
        
        # Check resource permissions
        authorized = False
        reason = "No matching permission rules found"
        
        # First check resource-specific permissions
        if resource in self.resource_permissions:
            resource_perms = self.resource_permissions[resource]
            if action in resource_perms:
                allowed_roles = resource_perms[action]
                if user_role in allowed_roles:
                    authorized = True
                    reason = f"Role '{user_role}' is explicitly allowed to {action} on {resource}"
                else:
                    reason = f"Role '{user_role}' is not in the allowed roles for {action} on {resource}"
            else:
                reason = f"Action '{action}' is not defined for resource {resource}"
        
        # If not authorized by resource-specific rules, check permission level
        # using global permission thresholds if defined
        if not authorized and hasattr(self, 'action_thresholds') and action in self.action_thresholds:
            threshold = self.action_thresholds[action]
            if permission_level >= threshold:
                authorized = True
                reason = f"Permission level {permission_level} meets or exceeds threshold {threshold} for {action}"
            else:
                reason = f"Permission level {permission_level} is below threshold {threshold} for {action}"
        
        # Special case: system administrators always have access
        if not authorized and user_role == 'admin':
            authorized = True
            reason = "Administrator override"
        
        # Add security event to audit log
        await self._add_audit_log_entry('authorization', 'success' if authorized else 'failure', {
            'session_id': session_id,
            'user_role': user_role,
            'resource': resource,
            'action': action,
            'authorized': authorized,
            'reason': reason
        })
        
        logger.info(f"Authorization {'granted' if authorized else 'denied'} for {user_role} on {resource}.{action}: {reason}")
        
        return {
            'authorized': authorized,
            'resource': resource,
            'action': action,
            'reason': reason,
            'user_role': user_role,
            'permission_level': permission_level
        }
    
    async def check_permissions(self, user_id: str, resource: str, action: str) -> Dict[str, Any]:
        """
        Check if a user has permission to perform an action on a resource.
        
        Args:
            user_id: ID of the user to check permissions for
            resource: Resource to access
            action: Action to perform on the resource
            
        Returns:
            Dict containing permission check result and details
        """
        logger.debug(f"Checking permissions for user {user_id}, resource: {resource}, action: {action}")
        
        # Check if user exists
        if user_id not in self.users:
            return {
                'has_permission': False,
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        
        user_data = self.users[user_id]
        user_role = user_data.get('role', 'guest')
        permission_level = user_data.get('permission_level', self.permission_levels.get('guest', 10))
        
        # Check resource permissions (similar logic as authorize method)
        has_permission = False
        reason = "No matching permission rules found"
        
        # First check resource-specific permissions
        if resource in self.resource_permissions:
            resource_perms = self.resource_permissions[resource]
            if action in resource_perms:
                allowed_roles = resource_perms[action]
                if user_role in allowed_roles:
                    has_permission = True
                    reason = f"Role '{user_role}' is explicitly allowed to {action} on {resource}"
                else:
                    reason = f"Role '{user_role}' is not in the allowed roles for {action} on {resource}"
            else:
                reason = f"Action '{action}' is not defined for resource {resource}"
        
        # If not authorized by resource-specific rules, check permission level
        if not has_permission and hasattr(self, 'action_thresholds') and action in self.action_thresholds:
            threshold = self.action_thresholds[action]
            if permission_level >= threshold:
                has_permission = True
                reason = f"Permission level {permission_level} meets or exceeds threshold {threshold} for {action}"
            else:
                reason = f"Permission level {permission_level} is below threshold {threshold} for {action}"
        
        # Special case: system administrators always have access
        if not has_permission and user_role == 'admin':
            has_permission = True
            reason = "Administrator override"
        
        return {
            'has_permission': has_permission,
            'user_id': user_id,
            'user_role': user_role,
            'resource': resource,
            'action': action,
            'reason': reason,
            'permission_level': permission_level
        }
    
    async def encrypt(self, data: Union[str, bytes], key_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Encrypt the provided data using strong encryption.
        
        Args:
            data: Data to encrypt
            key_id: Optional ID of the key to use for encryption. If not provided,
                   the default key will be used.
            
        Returns:
            Dict containing the encrypted data and metadata
        """
        logger.debug("Encryption request received")
        
        # Convert string to bytes if needed
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Get encryption key
        if not key_id:
            key_id = self.default_key
        
        if not key_id or key_id not in self.encryption_keys:
            # No valid key available, generate a new one
            if not self.encryption_keys:
                key_id = await self._create_new_encryption_key()
            else:
                key_id = self.default_key
        
        # Get the key data
        key_data = self.encryption_keys.get(key_id)
        if not key_data:
            return {
                'success': False,
                'error': 'Invalid encryption key',
                'error_code': 'INVALID_KEY'
            }
        
        try:
            # 2026 SOTA: Require cryptography library for encryption
            # XOR fallback has been removed as it is cryptographically insecure
            if not CRYPTO_AVAILABLE:
                logger.error("❌ CRITICAL: cryptography library is REQUIRED for encryption")
                logger.error("   Install with: pip install cryptography>=42.0.0")
                return {
                    'success': False,
                    'error': 'cryptography library is required. Install: pip install cryptography>=42.0.0',
                    'error_code': 'CRYPTO_REQUIRED'
                }
            
            # Use Fernet (AES-128-CBC) - proper cryptographic encryption
            f = Fernet(key_data['key'])
            encrypted_data = f.encrypt(data)
            algorithm = key_data['algorithm']
            
            # Return encrypted data with metadata
            return {
                'success': True,
                'encrypted_data': encrypted_data,
                'key_id': key_id,
                'algorithm': algorithm,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return {
                'success': False,
                'error': f'Encryption failed: {str(e)}',
                'error_code': 'ENCRYPTION_FAILED'
            }
    
    async def decrypt(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt previously encrypted data.
        
        Args:
            encrypted_data: Dictionary containing encrypted data and metadata
                           Should include 'encrypted_data', 'key_id', and 'algorithm'
            
        Returns:
            Dict containing the decrypted data or error information
        """
        logger.debug("Decryption request received")
        
        try:
            if not encrypted_data or not isinstance(encrypted_data, dict):
                return {
                    'success': False,
                    'error': 'Invalid encrypted data format: must be a dictionary',
                    'error_code': 'INVALID_FORMAT'
                }
            
            if 'encrypted_data' not in encrypted_data:
                return {
                    'success': False, 
                    'error': 'Missing encrypted_data field',
                    'error_code': 'MISSING_DATA'
                }
                
            key_id = encrypted_data.get('key_id', 'default')
            algorithm = encrypted_data.get('algorithm', 'Fernet')
            encrypted_content = encrypted_data.get('encrypted_data')
            
            # Check for None values to prevent type errors
            if encrypted_content is None:
                return {
                    'success': False,
                    'error': 'No encrypted data provided',
                    'error_code': 'MISSING_DATA'
                }
            
            # Get the encryption key
            if key_id not in self.encryption_keys:
                return {
                    'success': False,
                    'error': f"Unknown key_id: {key_id}",
                    'error_code': 'UNKNOWN_KEY'
                }
                
            key_data = self.encryption_keys[key_id]
            key = key_data.get('key')
            iv = key_data.get('iv')
            
            # For encrypted content coming over the wire, it might be base64 encoded
            if isinstance(encrypted_content, str):
                try:
                    encrypted_content = base64.b64decode(encrypted_content)
                except Exception as e:
                    return {
                        'success': False,
                        'error': f"Failed to decode base64 data: {e}",
                        'error_code': 'DECODE_ERROR'
                    }
            
            # Determine decryption method based on algorithm
            if algorithm == 'Fernet' and CRYPTO_AVAILABLE:
                try:
                    # Ensure key is not None before hashing
                    if key is None:
                        return {
                            'success': False,
                            'error': 'Encryption key is missing',
                            'error_code': 'MISSING_KEY'
                        }
                        
                    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
                    cipher = Fernet(fernet_key)
                    
                    # Ensure encrypted_content is bytes before decryption
                    if not isinstance(encrypted_content, (bytes, str)):
                        return {
                            'success': False,
                            'error': 'Encrypted content must be bytes or string',
                            'error_code': 'INVALID_TYPE'
                        }
                        
                    decrypted_data = cipher.decrypt(encrypted_content)
                    
                    # Try to determine if it's a serialized object
                    try:
                        decrypted_json = json.loads(decrypted_data.decode('utf-8'))
                        result = decrypted_json
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        # Not a JSON object or not UTF-8 encoded, return raw bytes
                        result = decrypted_data
                        
                    return {
                        'success': True,
                        'data': result
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f"Fernet decryption failed: {e}",
                        'error_code': 'DECRYPTION_ERROR'
                    }
            elif algorithm == 'xor' or algorithm == 'AES-Fallback':
                # XOR fallback has been deprecated and removed (2026 SOTA security)
                logger.error("❌ XOR/fallback encryption is no longer supported")
                logger.error("   Data encrypted with XOR cannot be decrypted")
                logger.error("   Re-encrypt using proper cryptography library")
                return {
                    'success': False,
                    'error': 'XOR/fallback encryption is deprecated and no longer supported. '
                             'Please re-encrypt using cryptography library.',
                    'error_code': 'DEPRECATED_ALGORITHM'
                }
            else:
                return {
                    'success': False,
                    'error': f"Unsupported algorithm: {algorithm}",
                    'error_code': 'UNSUPPORTED_ALGORITHM'
                }
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return {
                'success': False,
                'error': f"Decryption failed: {e}",
                'error_code': 'DECRYPTION_ERROR'
            }

    # NOTE: _fallback_decrypt (XOR) has been removed (2026 SOTA security)
    # XOR encryption is cryptographically insecure and should never be used
    # The cryptography library is now REQUIRED for all encryption operations
        
    #
    # API Key Management Methods
    #
    async def generate_api_key(self, user_id: str, key_name: str, 
                              permissions: List[str] = None, expires_in_days: int = 365, 
                              rate_limit: int = 100, allowed_ips: List[str] = None) -> Dict[str, Any]:
        """
        Generate a new API key for the specified user.
        
        Args:
            user_id: User ID to create key for
            key_name: Human-readable name for the key
            permissions: List of allowed resources/actions
            expires_in_days: Number of days until key expires
            rate_limit: Maximum requests per hour
            allowed_ips: List of allowed IP addresses/ranges
            
        Returns:
            Dictionary with API key information
        """
        with self.key_lock:
            # Check if user exists
            if user_id not in self.users:
                return {
                    'success': False,
                    'error': 'User not found',
                    'error_code': 'USER_NOT_FOUND'
                }
                
            # Generate a secure API key
            api_key_id = str(uuid.uuid4())
            api_key_secret = secrets.token_urlsafe(32)
            
            # Calculate expiration date
            expires_at = (datetime.now() + timedelta(days=expires_in_days)).isoformat()
            
            # Format full API key (ID.SECRET)
            full_api_key = f"{api_key_id}.{api_key_secret}"
            
            # Store hashed version of the secret instead of plain text
            secret_hash = hashlib.sha256(api_key_secret.encode()).hexdigest()
            
            # Validate and process allowed IPs
            processed_ips = []
            if allowed_ips:
                for ip in allowed_ips:
                    try:
                        # Check if it's a CIDR notation or single IP
                        if '/' in ip:
                            ipaddress.ip_network(ip, strict=False)  # Validate CIDR notation
                        else:
                            ipaddress.ip_address(ip)  # Validate single IP address
                        processed_ips.append(ip)
                    except ValueError:
                        logger.warning(f"Invalid IP address/range specified: {ip}")
            
            # Store API key info in user record
            api_key_info = {
                'id': api_key_id,
                'name': key_name,
                'secret_hash': secret_hash,
                'permissions': permissions or [],
                'created_at': datetime.now().isoformat(),
                'expires_at': expires_at,
                'rate_limit': rate_limit,
                'allowed_ips': processed_ips,
                'last_used': None,
                'usage_count': 0,
                'usage_history': {}, # Format: {"YYYY-MM-DD-HH": count}
                'is_active': True
            }
            
            # Add to user's API keys
            if 'api_keys' not in self.users[user_id]:
                self.users[user_id]['api_keys'] = {}
                
            self.users[user_id]['api_keys'][api_key_id] = api_key_info
            
            # Save users to disk
            await self._save_users()
            
            # Log the event
            await self._log_security_event(
                'api_key_created',
                f"API key '{key_name}' created for user {user_id}",
                user_id=user_id,
                api_key_id=api_key_id,
                expires_at=expires_at
            )
            
            # Return the full key to the caller - this is the only time it will be visible
            return {
                'success': True,
                'api_key': full_api_key,
                'api_key_id': api_key_id,
                'name': key_name,
                'expires_at': expires_at,
                'permissions': permissions or [],
                'rate_limit': rate_limit,
                'allowed_ips': processed_ips,
                'message': 'API key generated successfully. Keep it secure - it will not be shown again.'
            }
            
    async def revoke_api_key(self, user_id: str, api_key_id: str) -> Dict[str, Any]:
        """
        Revoke an existing API key.
        
        Args:
            user_id: User ID the key belongs to
            api_key_id: ID of the API key to revoke
            
        Returns:
            Dictionary with success status
        """
        with self.key_lock:
            # Check if user exists
            if user_id not in self.users:
                return {
                    'success': False,
                    'error': 'User not found',
                    'error_code': 'USER_NOT_FOUND'
                }
                
            # Check if API key exists
            if 'api_keys' not in self.users[user_id] or api_key_id not in self.users[user_id]['api_keys']:
                return {
                    'success': False,
                    'error': 'API key not found',
                    'error_code': 'API_KEY_NOT_FOUND'
                }
                
            # Set the key to inactive
            self.users[user_id]['api_keys'][api_key_id]['is_active'] = False
            
            # Save users to disk
            await self._save_users()
            
            # Log the event
            await self._log_security_event(
                'api_key_revoked',
                f"API key {api_key_id} revoked for user {user_id}",
                user_id=user_id,
                api_key_id=api_key_id
            )
            
            return {
                'success': True,
                'message': 'API key revoked successfully'
            }
            
    async def authenticate_with_api_key(self, api_key: str, ip_address: str = None, 
                                    resource: str = None, action: str = None) -> Dict[str, Any]:
        """
        Authenticate using an API key.
        
        Args:
            api_key: The API key in format "id.secret"
            ip_address: Client IP address for validation
            resource: Resource being accessed (optional)
            action: Action being performed (optional)
            
        Returns:
            Authentication result dictionary
        """
        with self.auth_lock:
            # Check if API key is in correct format
            parts = api_key.split('.', 1)
            if len(parts) != 2:
                return {
                    'success': False,
                    'error': 'Invalid API key format',
                    'error_code': 'INVALID_API_KEY_FORMAT'
                }
                
            api_key_id, api_key_secret = parts
            
            # Find the user that owns this API key
            user_id = None
            api_key_info = None
            
            for uid, user_data in self.users.items():
                if 'api_keys' in user_data and api_key_id in user_data['api_keys']:
                    user_id = uid
                    api_key_info = user_data['api_keys'][api_key_id]
                    break
                    
            if not user_id or not api_key_info:
                return {
                    'success': False,
                    'error': 'API key not found',
                    'error_code': 'API_KEY_NOT_FOUND'
                }
                
            # Check if key is active
            if not api_key_info.get('is_active', False):
                return {
                    'success': False,
                    'error': 'API key has been revoked',
                    'error_code': 'API_KEY_REVOKED'
                }
                
            # Check expiration
            if 'expires_at' in api_key_info:
                expires_at = datetime.fromisoformat(api_key_info['expires_at'])
                if datetime.now() > expires_at:
                    return {
                        'success': False,
                        'error': 'API key has expired',
                        'error_code': 'API_KEY_EXPIRED'
                    }
                    
            # Verify API key secret
            secret_hash = hashlib.sha256(api_key_secret.encode()).hexdigest()
            if secret_hash != api_key_info.get('secret_hash'):
                return {
                    'success': False,
                    'error': 'Invalid API key',
                    'error_code': 'INVALID_API_KEY'
                }
                
            # Check IP restriction if applicable
            if ip_address and api_key_info.get('allowed_ips'):
                ip_allowed = False
                client_ip = ipaddress.ip_address(ip_address)
                
                for allowed_ip in api_key_info['allowed_ips']:
                    # Check if it's a CIDR range or single IP
                    if '/' in allowed_ip:
                        network = ipaddress.ip_network(allowed_ip, strict=False)
                        if client_ip in network:
                            ip_allowed = True
                            break
                    else:
                        if ip_address == allowed_ip:
                            ip_allowed = True
                            break
                            
                if not ip_allowed:
                    return {
                        'success': False,
                        'error': 'IP address not allowed',
                        'error_code': 'IP_NOT_ALLOWED'
                    }
                    
            # Check rate limiting
            if 'rate_limit' in api_key_info:
                hour_key = datetime.now().strftime("%Y-%m-%d-%H")
                api_key_info['usage_history'] = api_key_info.get('usage_history', {})
                current_hour_usage = api_key_info['usage_history'].get(hour_key, 0)
                
                if current_hour_usage >= api_key_info['rate_limit']:
                    return {
                        'success': False,
                        'error': 'Rate limit exceeded',
                        'error_code': 'RATE_LIMIT_EXCEEDED'
                    }
                    
                # Update usage metrics
                api_key_info['usage_history'][hour_key] = current_hour_usage + 1
                api_key_info['usage_count'] = api_key_info.get('usage_count', 0) + 1
                api_key_info['last_used'] = datetime.now().isoformat()
                
                # Cleanup old usage history (keep only the last 7 days)
                cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                api_key_info['usage_history'] = {k: v for k, v in api_key_info['usage_history'].items() 
                                           if k.startswith(cutoff) or k > cutoff}
                
            # Check permissions if resource and action specified
            if resource and action:
                # Check if this key has specific permissions
                permission_granted = False
                
                # If no permissions are specified, assume full access
                if not api_key_info.get('permissions'):
                    permission_granted = True
                else:
                    # Check for direct resource:action match
                    resource_action = f"{resource}:{action}"
                    if resource_action in api_key_info['permissions']:
                        permission_granted = True
                    # Check for wildcard resource match
                    elif f"{resource}:*" in api_key_info['permissions']:
                        permission_granted = True
                    # Check for global wildcard match
                    elif "*:*" in api_key_info['permissions']:
                        permission_granted = True
                        
                if not permission_granted:
                    return {
                        'success': False,
                        'error': f"API key doesn't have permission for {resource}:{action}",
                        'error_code': 'PERMISSION_DENIED'
                    }
            
            # Save users to persist usage metrics
            await self._save_users()
            
            # Authentication successful, log the event
            await self._log_security_event(
                'api_key_authenticated',
                f"API key {api_key_id} successfully authenticated",
                user_id=user_id,
                api_key_id=api_key_id,
                ip_address=ip_address,
                resource=resource,
                action=action
            )
            
            # Return success with user info
            return {
                'success': True,
                'user_id': user_id,
                'username': self.users[user_id].get('username'),
                'role': self.users[user_id].get('role'),
                'api_key_id': api_key_id,
                'api_key_name': api_key_info.get('name'),
                'message': 'API key authentication successful'
            }
    
    async def _log_security_event(self, event_type: str, message: str, **kwargs) -> None:
        """
        Log a security event to the audit log.
        
        Args:
            event_type: Type of security event
            message: Human-readable description of the event
            **kwargs: Additional event data to log
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'message': message,
            **kwargs
        }
        
        # Add to audit log
        self.audit_log.append(event)
        
        # Trim audit log if it exceeds max size
        if len(self.audit_log) > self.max_audit_log_size:
            self.audit_log = self.audit_log[-self.max_audit_log_size:]
            
        # Log to system logger as well
        logger.info(f"SECURITY EVENT: {event_type} - {message}")
    
    async def handle_authenticate_event(self, data: Dict[str, Any]) -> None:
        """
        Handle authentication event from the event bus.
        
        Args:
            data: Event data containing authentication credentials
        """
        logger.debug("Received authentication event")

        try:
            # Extract request ID and response topic from event data
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.authenticate.response')
            
            # Perform authentication
            auth_result = await self.authenticate(data)
            
            # Add request ID to response if available
            if request_id:
                auth_result['request_id'] = request_id
            
            # Publish result back to the response topic
            if self.event_bus:
                await self.event_bus.publish(response_topic, auth_result)
        except Exception as e:
            logger.error(f"Error handling authentication event: {e}")

            # Publish error response if request_id and event_bus are available
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.authenticate.response'),
                    {
                        'success': False,
                        'request_id': data.get('request_id'),
                        'error': f"Authentication error: {str(e)}",
                        'error_code': 'AUTH_ERROR'
                    }
                )
    
    async def handle_authorize_event(self, data: Dict[str, Any]) -> None:
        """
        Handle authorization event from the event bus.
        
        Args:
            data: Event data containing authorization request details
        """
        logger.debug("Received authorization event")

        try:
            # Extract request parameters
            session_id = data.get('session_id')
            resource = data.get('resource')
            action = data.get('action')
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.authorize.response')
            
            if not session_id or not resource or not action:
                raise ValueError("Missing required parameters: session_id, resource, or action")

            
            # Perform authorization
            auth_result = await self.authorize(session_id, resource, action)
            
            # Add request ID to response if available
            if request_id:
                auth_result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, auth_result)
        except Exception as e:
            logger.error(f"Error handling authorization event: {e}")

            # Publish error response
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.authorize.response'),
                    {
                        'authorized': False,
                        'request_id': data.get('request_id'),
                        'error': f"Authorization error: {str(e)}",
                        'error_code': 'AUTH_ERROR'
                    }
                )
    
    async def handle_encrypt_event(self, data: Dict[str, Any]) -> None:
        """
        Handle encryption event from the event bus.
        
        Args:
            data: Event data containing data to encrypt
        """
        logger.debug("Received encryption event")

        try:
            # Extract parameters
            to_encrypt = data.get('data')
            key_id = data.get('key_id')
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.encrypt.response')
            
            if to_encrypt is None:
                raise ValueError("Missing required parameter: data")

            
            # Perform encryption
            result = await self.encrypt(to_encrypt, key_id)
            
            # Add request ID
            if request_id:
                result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, result)
        except Exception as e:
            logger.error(f"Error handling encryption event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.encrypt.response'),
                    {
                        'success': False,
                        'request_id': data.get('request_id'),
                        'error': f"Encryption error: {str(e)}",
                        'error_code': 'ENCRYPTION_ERROR'
                    }
                )
    
    async def handle_decrypt_event(self, data: Dict[str, Any]) -> None:
        """
        Handle decryption event from the event bus.
        
        Args:
            data: Event data containing encrypted data to decrypt
        """
        logger.debug("Received decryption event")

        try:
            # Encrypted data should be in the proper format
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.decrypt.response')
            
            # Perform decryption
            result = await self.decrypt(data)
            
            # Add request ID
            if request_id:
                result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, result)
        except Exception as e:
            logger.error(f"Error handling decryption event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.decrypt.response'),
                    {
                        'success': False,
                        'request_id': data.get('request_id'),
                        'error': f"Decryption error: {str(e)}",
                        'error_code': 'DECRYPTION_ERROR'
                    }
                )
    
    async def handle_create_user_event(self, data: Dict[str, Any]) -> None:
        """
        Handle user creation event from the event bus.
        
        Args:
            data: Event data containing user information
        """
        logger.debug("Received create user event")

        try:
            # Extract user data
            username = data.get('username')
            password = data.get('password')
            email = data.get('email')
            role = data.get('role', 'user')
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.create_user.response')
            
            if not username or not password:
                raise ValueError("Missing required parameters: username or password")

            
            # Check if username already exists
            existing_user = None
            for uid, user_data in self.users.items():
                if user_data.get('username') == username or user_data.get('email') == email:
                    existing_user = uid
                    break
            
            if existing_user:
                result = {
                    'success': False,
                    'error': 'Username or email already exists',
                    'error_code': 'USER_EXISTS'
                }
            else:
                # Create new user
                user_id = str(uuid.uuid4())
                permission_level = self.permission_levels.get(role, self.permission_levels['user'])
                
                self.users[user_id] = {
                    'username': username,
                    'password_hash': await self._hash_password(password),
                    'email': email,
                    'role': role,
                    'permission_level': permission_level,
                    'created_at': datetime.now().isoformat(),
                    'last_login': None,
                    'failed_attempts': 0,
                    'locked_until': None,
                    'api_keys': {},
                    'settings': {},
                    'is_active': True
                }
                
                # Save users to disk
                await self._save_users()
                
                result = {
                    'success': True,
                    'user_id': user_id,
                    'username': username,
                    'role': role,
                    'message': 'User created successfully'
                }
            
            # Add request ID
            if request_id:
                result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, result)
        except Exception as e:
            logger.error(f"Error handling create user event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.create_user.response'),
                    {
                        'success': False,
                        'request_id': data.get('request_id'),
                        'error': f"User creation error: {str(e)}",
                        'error_code': 'USER_CREATION_ERROR'
                    }
                )
    
    async def handle_change_password_event(self, data: Dict[str, Any]) -> None:
        """
        Handle password change event from the event bus.
        
        Args:
            data: Event data containing user ID and password information
        """
        logger.debug("Received change password event")

        try:
            # Extract parameters
            user_id = data.get('user_id')
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.change_password.response')
            
            if not user_id or not new_password:
                raise ValueError("Missing required parameters: user_id or new_password")

            
            # Check if user exists
            if user_id not in self.users:
                result = {
                    'success': False,
                    'error': 'User not found',
                    'error_code': 'USER_NOT_FOUND'
                }
            else:
                user_data = self.users[user_id]
                
                # If current password is provided, verify it
                if current_password:
                    password_hash = user_data.get('password_hash', '')
                    if not password_hash or not (await self._verify_password(password_hash, current_password)):
                        result = {
                            'success': False,
                            'error': 'Current password is incorrect',
                            'error_code': 'INCORRECT_PASSWORD'
                        }
                    else:
                        # Change password
                        user_data['password_hash'] = await self._hash_password(new_password)
                        await self._save_users()
                        
                        result = {
                            'success': True,
                            'user_id': user_id,
                            'message': 'Password changed successfully'
                        }
                else:
                    # Admin reset (no current password verification)
                    user_data['password_hash'] = await self._hash_password(new_password)
                    await self._save_users()
                    
                    result = {
                        'success': True,
                        'user_id': user_id,
                        'message': 'Password reset successfully'
                    }
            
            # Add request ID
            if request_id:
                result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, result)
        except Exception as e:
            logger.error(f"Error handling change password event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.change_password.response'),
                    {
                        'success': False,
                        'request_id': data.get('request_id'),
                        'error': f"Password change error: {str(e)}",
                        'error_code': 'PASSWORD_CHANGE_ERROR'
                    }
                )
    
    async def handle_logout_event(self, data: Dict[str, Any]) -> None:
        """
        Handle logout event from the event bus.
        
        Args:
            data: Event data containing session ID
        """
        logger.debug("Received logout event")

        try:
            # Extract parameters
            session_id = data.get('session_id')
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.logout.response')
            
            if not session_id:
                raise ValueError("Missing required parameter: session_id")

            
            # Check if session exists
            with self.session_lock:
                if session_id in self.active_sessions:
                    # Remove session
                    del self.active_sessions[session_id]
                    result = {
                        'success': True,
                        'message': 'Logged out successfully'
                    }
                else:
                    result = {
                        'success': False,
                        'error': 'Session not found',
                        'error_code': 'SESSION_NOT_FOUND'
                    }
            
            # Add request ID
            if request_id:
                result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, result)
        except Exception as e:
            logger.error(f"Error handling logout event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.logout.response'),
                    {
                        'success': False,
                        'request_id': data.get('request_id'),
                        'error': f"Logout error: {str(e)}",
                        'error_code': 'LOGOUT_ERROR'
                    }
                )
    
    async def handle_validate_token_event(self, data: Dict[str, Any]) -> None:
        """
        Handle token validation event from the event bus.
        
        Args:
            data: Event data containing token to validate
        """
        logger.debug("Received validate token event")

        try:
            # Extract parameters
            token = data.get('token')
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.validate_token.response')
            
            if not token:
                raise ValueError("Missing required parameter: token")

            
            # Validate token
            result = await self.validate_token(token)
            
            # Add request ID
            if request_id:
                result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, result)
        except Exception as e:
            logger.error(f"Error handling validate token event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.validate_token.response'),
                    {
                        'valid': False,
                        'request_id': data.get('request_id'),
                        'error': f"Token validation error: {str(e)}",
                        'error_code': 'TOKEN_VALIDATION_ERROR'
                    }
                )
    
    async def handle_api_key_auth_event(self, data: Dict[str, Any]) -> None:
        """
        Handle API key authentication event from the event bus.
        
        Args:
            data: Event data containing API key
        """
        logger.debug("Received API key authentication event")

        try:
            # Extract parameters
            api_key = data.get('api_key')
            ip_address = data.get('ip_address')
            resource = data.get('resource')
            action = data.get('action')
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.api_key_auth.response')
            
            if not api_key:
                raise ValueError("Missing required parameter: api_key")

            # Authenticate with API key
            auth_result = await self.authenticate_with_api_key(api_key, ip_address, resource, action)
            
            # Add request ID to response
            if request_id:
                auth_result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, auth_result)
        except Exception as e:
            logger.error(f"Error handling API key authentication event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.api_key_auth.response'),
                    {
                        'success': False,
                        'request_id': data.get('request_id'),
                        'error': f"API key authentication error: {str(e)}",
                        'error_code': 'API_KEY_AUTH_ERROR'
                    }
                )
    
    async def handle_check_permissions_event(self, data: Dict[str, Any]) -> None:
        """
        Handle permissions check event from the event bus.
        
        Args:
            data: Event data containing user ID, resource, and action
        """
        logger.debug("Received check permissions event")

        try:
            # Extract parameters
            user_id = data.get('user_id')
            resource = data.get('resource')
            action = data.get('action')
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.check_permissions.response')
            
            if not user_id or not resource or not action:
                raise ValueError("Missing required parameters: user_id, resource, or action")

            
            # Check permissions
            result = await self.check_permissions(user_id, resource, action)
            
            # Add request ID
            if request_id:
                result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, result)
        except Exception as e:
            logger.error(f"Error handling check permissions event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.check_permissions.response'),
                    {
                        'has_permission': False,
                        'request_id': data.get('request_id'),
                        'error': f"Permissions check error: {str(e)}",
                        'error_code': 'PERMISSIONS_ERROR'
                    }
                )
    
    async def handle_generate_api_key_event(self, data: Dict[str, Any]) -> None:
        """
        Handle API key generation event from the event bus.
        
        Args:
            data: Event data containing user ID and key details
        """
        logger.debug("Received generate API key event")

        try:
            # Extract parameters
            user_id = data.get('user_id')
            key_name = data.get('key_name', 'Default API Key')
            permissions = data.get('permissions', [])
            expires_in_days = data.get('expires_in_days', 365)
            rate_limit = data.get('rate_limit', 100)  # Default 100 requests per hour
            allowed_ips = data.get('allowed_ips', [])  # Empty list means all IPs allowed
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.generate_api_key.response')
            
            if not user_id:
                raise ValueError("Missing required parameter: user_id")

            # Generate API key
            api_key_result = await self.generate_api_key(user_id, key_name, permissions, expires_in_days, rate_limit, allowed_ips)
            
            # Add request ID
            if request_id:
                api_key_result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, api_key_result)
        except Exception as e:
            logger.error(f"Error handling generate API key event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.generate_api_key.response'),
                    {
                        'success': False,
                        'request_id': data.get('request_id'),
                        'error': f"API key generation error: {str(e)}",
                        'error_code': 'API_KEY_GENERATION_ERROR'
                    }
                )
    
    async def handle_get_audit_log_event(self, data: Dict[str, Any]) -> None:
        """
        Handle audit log retrieval event from the event bus.
        
        Args:
            data: Event data containing filters and options
        """
        logger.debug("Received get audit log event")

        try:
            # Extract parameters
            event_type = data.get('event_type')
            limit = data.get('limit', 100)
            offset = data.get('offset', 0)
            start_time = data.get('start_time')
            end_time = data.get('end_time')
            request_id = data.get('request_id')
            response_topic = data.get('response_topic', 'system.security.get_audit_log.response')
            
            # Filter audit log entries
            filtered_log = self.audit_log
            
            if event_type:
                filtered_log = [entry for entry in filtered_log if entry.get('event_type') == event_type]
            
            if start_time:
                start_dt = datetime.fromisoformat(start_time)
                filtered_log = [entry for entry in filtered_log if datetime.fromisoformat(entry.get('timestamp')) >= start_dt]
            
            if end_time:
                end_dt = datetime.fromisoformat(end_time)
                filtered_log = [entry for entry in filtered_log if datetime.fromisoformat(entry.get('timestamp')) <= end_dt]
            
            # Apply pagination
            total_entries = len(filtered_log)
            paginated_log = filtered_log[offset:offset+limit]
            
            result = {
                'success': True,
                'entries': paginated_log,
                'total': total_entries,
                'limit': limit,
                'offset': offset
            }
            
            # Add request ID
            if request_id:
                result['request_id'] = request_id
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish(response_topic, result)
        except Exception as e:
            logger.error(f"Error handling get audit log event: {e}")

            # Publish error
            if self.event_bus and 'request_id' in data:
                await self.event_bus.publish(
                    data.get('response_topic', 'system.security.get_audit_log.response'),
                    {
                        'success': False,
                        'request_id': data.get('request_id'),
                        'error': f"Audit log retrieval error: {str(e)}",
                        'error_code': 'AUDIT_LOG_ERROR'
                    }
                )
    
    async def handle_shutdown_event(self, data: Dict[str, Any]) -> None:
        """
        Handle system shutdown event from the event bus.
        
        Args:
            data: Event data (not used)
        """
        logger.info("Received system shutdown event")

        # Perform cleanup
        await self.shutdown()
    
    async def shutdown(self) -> bool:
        """
        Shutdown the Security Manager component.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        logger.info("Shutting down Security Manager...")

        # Save any pending data
        try:
            # Save users
            await self._save_users()
            
            # Unsubscribe from events if event bus is available
            if self.event_bus:
                try:
                    await self.event_bus.unsubscribe('system.security.authenticate', self.handle_authenticate_event)
                    await self.event_bus.unsubscribe('system.security.authorize', self.handle_authorize_event)
                    await self.event_bus.unsubscribe('system.security.encrypt', self.handle_encrypt_event)
                    await self.event_bus.unsubscribe('system.security.decrypt', self.handle_decrypt_event)
                    await self.event_bus.unsubscribe('system.security.create_user', self.handle_create_user_event)
                    await self.event_bus.unsubscribe('system.security.change_password', self.handle_change_password_event)
                    await self.event_bus.unsubscribe('system.security.logout', self.handle_logout_event)
                    await self.event_bus.unsubscribe('system.security.validate_token', self.handle_validate_token_event)
                    await self.event_bus.unsubscribe('system.security.api_key_auth', self.handle_api_key_auth_event)
                    await self.event_bus.unsubscribe('system.security.check_permissions', self.handle_check_permissions_event)
                    await self.event_bus.unsubscribe('system.security.generate_api_key', self.handle_generate_api_key_event)
                    await self.event_bus.unsubscribe('system.security.get_audit_log', self.handle_get_audit_log_event)
                    await self.event_bus.unsubscribe('system.shutdown', self.handle_shutdown_event)
                    logger.debug("Security Manager events unregistered")
                except Exception as e:
                    logger.error(f"Error unsubscribing from events: {e}")
            
            logger.info("Security Manager shut down successfully")
            return True
        except Exception as e:
            logger.error(f"Error during Security Manager shutdown: {e}")
            return False

def get_config(self, path: str, default=None) -> Any:
    """
    AI-Generated Configuration Accessor with Safety Checks
    
    Args:
        path: Dot-separated path to the configuration value
        default: Default value to return if path doesn't exist
        
    Returns:
        Configuration value or default
    """
    logger.info(f"get_config({path}) called - using compatibility layer")
    return self.get(path, default)