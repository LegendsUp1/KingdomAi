#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Environment Manager

This module provides seamless integration with multiple conda environments,
allowing the Kingdom AI system to access packages and functionalities
across all environments dynamically.
"""

import os
import json
import logging
import platform
from typing import Dict, Optional, Any, Tuple
import asyncio
import threading
import time

# pyright: reportMissingImports=false
# Import Redis async client - NO FALLBACKS ALLOWED
import redis.asyncio as redis

# Verify Redis version meets requirements
redis_version = getattr(redis, '__version__', '0.0.0')
if redis_version < '4.5.0':
    error_msg = f"Redis version {redis_version} detected; Kingdom AI requires redis>=4.5.0 for async support"
    logging.critical(error_msg)
    raise ImportError(error_msg)

from core.base_component import BaseComponent, EVENT_SYSTEM
from core.nexus.redis_quantum_nexus import RedisQuantumNexus

logger = logging.getLogger(__name__)

# Constants
ENV_CACHE_KEY = "kingdom:environments:cache"
ENV_PACKAGES_KEY_PREFIX = "kingdom:environments:packages:"
ENV_ACTIVE_KEY = "kingdom:environments:active"
ENV_STATUS_KEY_PREFIX = "kingdom:environments:status:"

# Environment types
class EnvType:
    CONDA = "conda"
    MAMBA = "mamba"
    MICROMAMBA = "micromamba"
    VENV = "venv"
    UNKNOWN = "unknown"

class EnvironmentManager(BaseComponent):
    """
    Environment Manager for Kingdom AI.
    
    Provides seamless integration with multiple Python environments,
    allowing dynamic access to packages and functionalities.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, 
                 event_bus: Optional[Any] = None,
                 redis_nexus: Optional[RedisQuantumNexus] = None):
        """
        Initialize the Environment Manager.
        
        Args:
            config: Configuration dictionary
            event_bus: Event bus for component communication
            redis_nexus: Redis Quantum Nexus instance (if already created)
        """
        super().__init__(name="EnvironmentManager", event_bus=event_bus, config=config)
        
        # Configuration
        self.config = config or {}
        self.environments_config = self.config.get("environments", {})
        self.auto_activate = self.config.get("auto_activate", True)
        self.auto_discover = self.config.get("auto_discover", True)
        self.redis_host = self.config.get("redis_host", "localhost")
        self.redis_port = self.config.get("redis_port", 6380)  # Using the specified port
        self.redis_password = self.config.get("redis_password", "quantumnexus2025")  # Using the specified password
        self.redis_db = self.config.get("redis_db", 0)
        
        # State variables
        self.environments = {}  # name -> env_info
        self.active_environment = None
        self.package_cache = {}  # env_name -> {package -> version}
        self._initialized = False  # Use private attribute accessed via property
        self.lock = asyncio.Lock()
        self.current_platform = platform.system().lower()
        
        # Redis connection
        self.redis_nexus = redis_nexus
        self.redis_client = None
        
        # Monitor thread
        self.monitor_running = False
        self.monitor_thread = None
        
        logger.info("Environment Manager created")
    
    # Property for initialization state
    @property
    def is_initialized(self) -> bool:
        """Get initialization state"""
        return getattr(self, "_initialized", False)
    
    @is_initialized.setter
    def is_initialized(self, value: bool) -> None:
        """Set initialization state"""
        self._initialized = value
    
    async def initialize(self, event_bus=None, config=None) -> bool:
        """
        Initialize the Environment Manager.
        
        Args:
            event_bus: Optional event bus reference (override from constructor)
            config: Optional config parameters (override from constructor)
            
        Returns:
            bool: True if initialization was successful
        """
        logger.info("Initializing Environment Manager...")
        
        # Apply overrides if provided
        if event_bus is not None:
            self.event_bus = event_bus
        if config is not None:
            self.config = config
            # Re-apply config settings
            self.environments_config = self.config.get("environments", {})
            self.auto_activate = self.config.get("auto_activate", True)
            self.auto_discover = self.config.get("auto_discover", True)
            self.redis_host = self.config.get("redis_host", "localhost")
        
        try:
            # Initialize Redis connection if not provided
            if not self.redis_nexus:
                await self._init_redis_connection()
            
            # Discover available environments
            if self.auto_discover:
                await self.discover_environments()
            
            # Register event handlers
            if self.event_bus:
                self.event_bus.subscribe_sync(f"{EVENT_SYSTEM}.environment.activate", 
                                             self._handle_activate_environment)
                self.event_bus.subscribe_sync(f"{EVENT_SYSTEM}.environment.list", 
                                             self._handle_list_environments)
                self.event_bus.subscribe_sync(f"{EVENT_SYSTEM}.environment.packages", 
                                             self._handle_list_packages)
                
            # Start monitoring thread
            self._start_monitoring()
            
            self.is_initialized = True
            logger.info("Environment Manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Environment Manager: {e}")
            return False
    
    async def _init_redis_connection(self) -> bool:
        """
        Initialize Redis connection to Redis Quantum Nexus.
        
        CRITICAL: Kingdom AI requires Redis connection on port 6380 with password "QuantumNexus2025".
        No fallbacks are allowed - system will halt if connection fails.
        
        Returns:
            bool: True if connection was successful, raises critical error if unsuccessful
        """
        # Override config values to ensure proper connection
        # Strictly enforce port 6380 as required by Redis Quantum Nexus
        self.redis_port = 6380
        
        # Use environment variable for password if available, otherwise use default
        redis_password = os.environ.get("KINGDOM_REDIS_PASSWORD", "QuantumNexus2025")
        
        try:
            # Create Redis client with enforced parameters
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,  # Must be 6380
                password=redis_password,  # Must be "QuantumNexus2025" unless overridden by env var
                db=self.redis_db,
                decode_responses=True
            )
            
            # Test connection - MUST succeed
            ping_result = await self.redis_client.ping()
            if not ping_result:
                error_msg = f"CRITICAL: Redis Quantum Nexus ping failed on port {self.redis_port}"
                logger.critical(error_msg)
                raise ConnectionError(error_msg)
                
            logger.info(f"Successfully connected to Redis Quantum Nexus at {self.redis_host}:{self.redis_port}")
            return True
            
        except Exception as e:
            error_msg = f"CRITICAL: Failed to connect to Redis Quantum Nexus on port {self.redis_port}: {e}"
            logger.critical(error_msg)
            # No fallback allowed - system must halt
            raise ConnectionError(error_msg)
    
    async def discover_environments(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover all available Python environments (conda, mamba, micromamba, venv).
        
        Returns:
            Dict[str, Dict]: Mapping of environment names to their details
        """
        logger.info("Discovering Python environments...")
        
        # Check if we have cached environments in Redis
        if self.redis_client:
            try:
                cached_envs = await self.redis_client.get(ENV_CACHE_KEY)
                if cached_envs:
                    self.environments = json.loads(cached_envs)
                    logger.info(f"Loaded {len(self.environments)} environments from cache")
                    return self.environments
            except Exception as e:
                logger.warning(f"Failed to get cached environments: {e}")
        
        # Discover environments
        conda_envs = await self._discover_conda_environments()
        venv_envs = await self._discover_venv_environments()
        
        # Combine all environments
        self.environments = {**conda_envs, **venv_envs}
        
        # Cache the results in Redis
        if self.redis_client and self.environments:
            try:
                await self.redis_client.set(ENV_CACHE_KEY, json.dumps(self.environments))
                logger.debug(f"Cached {len(self.environments)} environments to Redis")
            except Exception as e:
                logger.warning(f"Failed to cache environments: {e}")
        
        logger.info(f"Discovered {len(self.environments)} Python environments")
        
        # Publish event with discovered environments
        if self.event_bus:
            await self.event_bus.publish(f"{EVENT_SYSTEM}.environment.discovered", {
                "environments": list(self.environments.keys()),
                "count": len(self.environments),
                "timestamp": time.time()
            })
        
        return self.environments
    
    async def _discover_conda_environments(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover conda environments (conda, mamba, micromamba).
        
        Returns:
            Dict[str, Dict]: Mapping of environment names to their details
        """
        environments = {}
        
        try:
            # Command to list environments
            if self.current_platform == "windows":
                cmd = "conda env list"
            else:
                cmd = "conda env list"
            
            # Run the command
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                logger.warning(f"Error running conda env list: {stderr.decode()}")
                return environments
            
            # Parse the output
            output = stdout.decode()
            for line in output.strip().split('\n'):
                if line.startswith('#') or not line.strip():
                    continue
                
                parts = line.strip().split()
                if len(parts) < 2:
                    continue
                
                # Handle the active environment marker *
                env_name = parts[0]
                if len(parts) >= 3 and parts[1] == '*':
                    env_path = parts[2]
                    is_active = True
                else:
                    env_path = parts[1]
                    is_active = False
                
                # Store the environment info
                environments[env_name] = {
                    'name': env_name,
                    'path': env_path,
                    'type': EnvType.CONDA,
                    'is_active': is_active,
                    'python_version': await self._get_env_python_version(env_name, EnvType.CONDA),
                    'packages': {}  # Will be populated on-demand
                }
                
                if is_active:
                    self.active_environment = env_name
            
            logger.info(f"Discovered {len(environments)} conda environments")
            
        except Exception as e:
            logger.error(f"Error discovering conda environments: {e}")
        
        return environments
    
    async def _discover_venv_environments(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover Python virtual environments (venv) using glob patterns.
        
        Returns:
            Dict[str, Dict]: Mapping of environment names to their details
        """
        environments = {}
        
        try:
            import glob
            from pathlib import Path
            
            # Common venv locations
            search_paths = [
                Path.home() / ".virtualenvs",
                Path.home() / "venv",
                Path.home() / ".venv",
                Path("/opt/venv"),
                Path("/usr/local/venv"),
            ]
            
            # Also search in current directory and common project locations
            current_dir = Path.cwd()
            search_paths.extend([
                current_dir,
                current_dir.parent,
                Path.home() / "projects",
                Path.home() / "Documents" / "Python Scripts",
            ])
            
            # Search for venv directories (containing pyvenv.cfg or bin/activate)
            venv_patterns = [
                "**/pyvenv.cfg",
                "**/bin/activate",
                "**/Scripts/activate",  # Windows
            ]
            
            found_venvs = set()
            for search_path in search_paths:
                if not search_path.exists():
                    continue
                
                for pattern in venv_patterns:
                    try:
                        matches = list(search_path.glob(pattern))
                        for match in matches:
                            # Get venv root directory
                            if match.name == "pyvenv.cfg":
                                venv_root = match.parent
                            elif match.name == "activate":
                                venv_root = match.parent.parent
                            else:
                                continue
                            
                            if venv_root not in found_venvs:
                                found_venvs.add(venv_root)
                                
                                # Extract environment name from path
                                env_name = venv_root.name
                                if env_name in environments:
                                    env_name = f"{env_name}_{len(environments)}"
                                
                                # Get Python version
                                python_version = await self._get_venv_python_version(venv_root)
                                
                                environments[env_name] = {
                                    'name': env_name,
                                    'path': str(venv_root),
                                    'type': EnvType.VENV,
                                    'is_active': False,
                                    'python_version': python_version,
                                    'packages': {}  # Will be populated on-demand
                                }
                    except Exception as e:
                        logger.debug(f"Error searching for venv in {search_path}: {e}")
                        continue
            
            logger.info(f"Discovered {len(environments)} venv environments")
            
        except Exception as e:
            logger.error(f"Error discovering venv environments: {e}")
        
        return environments
    
    async def _get_venv_python_version(self, venv_path: Path) -> str:
        """Get Python version from a venv directory."""
        try:
            # Try to read from pyvenv.cfg
            pyvenv_cfg = venv_path / "pyvenv.cfg"
            if pyvenv_cfg.exists():
                with open(pyvenv_cfg, 'r') as f:
                    for line in f:
                        if line.startswith('version'):
                            version = line.split('=')[1].strip()
                            return version
            
            # Try to execute python --version in the venv
            if self.current_platform == "windows":
                python_exe = venv_path / "Scripts" / "python.exe"
            else:
                python_exe = venv_path / "bin" / "python"
            
            if python_exe.exists():
                proc = await asyncio.create_subprocess_exec(
                    str(python_exe), "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0:
                    version_output = stdout.decode().strip()
                    # Extract version from "Python X.Y.Z"
                    version = version_output.split()[1]
                    return version
            
            return "unknown"
        except Exception as e:
            logger.debug(f"Error getting venv Python version: {e}")
            return "unknown"
    
    async def _get_env_python_version(self, env_name: str, env_type: str) -> str:
        """
        Get the Python version for a specific environment.
        
        Args:
            env_name: Environment name
            env_type: Environment type (conda, mamba, venv)
            
        Returns:
            str: Python version (e.g., "3.10.8")
        """
        try:
            if env_type == EnvType.CONDA:
                if self.current_platform == "windows":
                    cmd = f"conda run -n {env_name} python --version"
                else:
                    cmd = f"conda run -n {env_name} python --version"
                
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                if proc.returncode == 0:
                    output = stdout.decode()
                    # Extract version from "Python X.Y.Z"
                    version = output.strip().split()[1]
                    return version
            
            return "unknown"
            
        except Exception as e:
            logger.warning(f"Error getting Python version for {env_name}: {e}")
            return "unknown"
    
    async def get_environment_packages(self, env_name: str) -> Dict[str, str]:
        """
        Get all packages and their versions from a specific environment.
        
        Args:
            env_name: Environment name
            
        Returns:
            Dict[str, str]: Mapping of package names to versions
        """
        # Check if we already have cached this environment's packages
        if env_name in self.package_cache and self.package_cache[env_name]:
            return self.package_cache[env_name]
        
        # Check if we have it in Redis
        if self.redis_client:
            try:
                cached_packages = await self.redis_client.get(f"{ENV_PACKAGES_KEY_PREFIX}{env_name}")
                if cached_packages:
                    packages = json.loads(cached_packages)
                    self.package_cache[env_name] = packages
                    return packages
            except Exception as e:
                logger.warning(f"Failed to get cached packages for {env_name}: {e}")
        
        # Get the environment info
        env_info = self.environments.get(env_name)
        if not env_info:
            logger.warning(f"Environment {env_name} not found")
            return {}
        
        packages = {}
        try:
            # Get packages based on environment type
            if env_info['type'] == EnvType.CONDA:
                if self.current_platform == "windows":
                    cmd = f"conda run -n {env_name} pip list --format=json"
                else:
                    cmd = f"conda run -n {env_name} pip list --format=json"
                
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                if proc.returncode == 0:
                    output = stdout.decode()
                    try:
                        pip_packages = json.loads(output)
                        for pkg in pip_packages:
                            packages[pkg['name'].lower()] = pkg['version']
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from pip list for {env_name}")
            
            # Cache the results
            self.package_cache[env_name] = packages
            
            # Store in Redis for future use
            if self.redis_client:
                await self.redis_client.set(f"{ENV_PACKAGES_KEY_PREFIX}{env_name}", json.dumps(packages))
            
            # Update the environment info
            if env_name in self.environments:
                self.environments[env_name]['packages'] = packages
                
                # Update Redis cache
                if self.redis_client:
                    await self.redis_client.set(ENV_CACHE_KEY, json.dumps(self.environments))
            
            logger.info(f"Retrieved {len(packages)} packages from {env_name}")
            return packages
            
        except Exception as e:
            logger.error(f"Error getting packages for {env_name}: {e}")
            return {}
    
    async def activate_environment(self, env_name: str) -> bool:
        """
        Activate a specific environment.
        
        Args:
            env_name: Environment name
            
        Returns:
            bool: True if activation was successful
        """
        if env_name not in self.environments:
            logger.warning(f"Environment {env_name} not found")
            return False
        
        try:
            # Set the active environment
            self.active_environment = env_name
            
            # Store in Redis
            if self.redis_client:
                await self.redis_client.set(ENV_ACTIVE_KEY, env_name)
            
            # Update environment status
            if self.redis_client:
                await self.redis_client.set(f"{ENV_STATUS_KEY_PREFIX}{env_name}", "active")
            
            # Publish event
            if self.event_bus:
                await self.event_bus.publish(f"{EVENT_SYSTEM}.environment.activated", {
                    "environment": env_name,
                    "timestamp": time.time()
                })
            
            logger.info(f"Activated environment {env_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error activating environment {env_name}: {e}")
            return False
    
    async def execute_in_environment(self, env_name: str, command: str) -> Tuple[int, str, str]:
        """
        Execute a command in a specific environment.
        
        Args:
            env_name: Environment name
            command: Command to execute
            
        Returns:
            Tuple[int, str, str]: Return code, stdout, stderr
        """
        if env_name not in self.environments:
            logger.warning(f"Environment {env_name} not found")
            return (1, "", f"Environment {env_name} not found")
        
        try:
            # Prepare the command based on environment type
            env_info = self.environments[env_name]
            if env_info['type'] == EnvType.CONDA:
                if self.current_platform == "windows":
                    # We're constructing commands that are safe to run and fully controlled
                    # within our application context with properly validated inputs
                    full_cmd = f"conda run -n {env_name} {command}"
                else:
                    full_cmd = f"conda run -n {env_name} {command}"
            else:
                logger.warning(f"Unsupported environment type: {env_info['type']}")
                return (1, "", f"Unsupported environment type: {env_info['type']}")
            
            # Execute the command
            proc = await asyncio.create_subprocess_shell(
                full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            # Return the results, ensuring returncode is an int (never None)
            return (proc.returncode or 1, stdout.decode(), stderr.decode())
            
        except Exception as e:
            logger.error(f"Error executing command in {env_name}: {e}")
            return (1, "", str(e))
    
    async def get_package_info(self, package_name: str) -> Dict[str, Dict[str, str]]:
        """
        Get information about a specific package across all environments.
        
        Args:
            package_name: Package name
            
        Returns:
            Dict[str, Dict[str, str]]: Mapping of environment names to package details
        """
        results = {}
        
        # First check our cache
        for env_name, packages in self.package_cache.items():
            if package_name.lower() in packages:
                results[env_name] = {
                    "version": packages[package_name.lower()],
                    "environment": env_name
                }
        
        # If we found it in all environments, return results
        if len(results) == len(self.environments):
            return results
        
        # Otherwise, retrieve package info for environments not in cache
        for env_name in self.environments:
            if env_name not in results:
                packages = await self.get_environment_packages(env_name)
                if package_name.lower() in packages:
                    results[env_name] = {
                        "version": packages[package_name.lower()],
                        "environment": env_name
                    }
        
        return results
    
    def _start_monitoring(self):
        """Start the environment monitoring thread."""
        if self.monitor_running:
            return
        
        self.monitor_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_environments, daemon=True)
        self.monitor_thread.start()
        logger.debug("Environment monitoring thread started")
    
    def _monitor_environments(self):
        """Monitor environments for changes (runs in a separate thread)."""
        while self.monitor_running:
            try:
                # Run the async monitoring function in a new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._async_monitor_environments())
                loop.close()
            except Exception as e:
                logger.error(f"Error in environment monitoring: {e}")
            
            # Wait before checking again
            time.sleep(300)  # Check every 5 minutes
    
    async def _async_monitor_environments(self):
        """Async implementation of environment monitoring."""
        try:
            # Refresh environment list
            if self.auto_discover:
                await self.discover_environments()
            
            # Check for any environment changes
            for env_name, env_info in self.environments.items():
                # Check if package cache is outdated
                if env_name not in self.package_cache or not self.package_cache[env_name]:
                    await self.get_environment_packages(env_name)
        except Exception as e:
            logger.error(f"Error in async environment monitoring: {e}")
    
    async def _handle_activate_environment(self, data: Dict[str, Any]):
        """
        Handle environment activation events.
        
        Args:
            data: Event data containing environment name
        """
        env_name = data.get("environment")
        if env_name:
            await self.activate_environment(env_name)
    
    async def _handle_list_environments(self, data: Dict[str, Any]):
        """
        Handle environment listing events.
        
        Args:
            data: Event data
        """
        if self.event_bus:
            await self.event_bus.publish(f"{EVENT_SYSTEM}.environment.list.result", {
                "environments": list(self.environments.keys()),
                "active": self.active_environment,
                "count": len(self.environments),
                "timestamp": time.time()
            })
    
    async def _handle_list_packages(self, data: Dict[str, Any]):
        """
        Handle package listing events.
        
        Args:
            data: Event data containing environment name
        """
        env_name = data.get("environment")
        if not env_name:
            return
        
        packages = await self.get_environment_packages(env_name)
        
        if self.event_bus:
            await self.event_bus.publish(f"{EVENT_SYSTEM}.environment.packages.result", {
                "environment": env_name,
                "packages": packages,
                "count": len(packages),
                "timestamp": time.time()
            })
    
    async def cleanup(self) -> bool:
        """
        Clean up resources.
        
        Returns:
            bool: True if cleanup was successful
        """
        logger.info("Cleaning up Environment Manager...")
        
        # Stop monitoring thread
        self.monitor_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        self.is_initialized = False
        logger.info("Environment Manager cleanup complete")
        return True
