#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Environment Integration Module

This module provides system-wide integration of all conda environments with the 
Kingdom AI core components, ensuring seamless access to packages and functionality 
across all environments simultaneously.

The module follows the event-driven architecture of Kingdom AI and maintains
proper initialization order according to the System Initialization Flow.
"""

import json
import logging
import time
import importlib
import platform
from typing import Dict, Optional, Any, Tuple

# Import base components
from core.base_component import BaseComponent, EVENT_SYSTEM
from core.nexus.redis_quantum_nexus import RedisQuantumNexus, NexusEnvironment
from core.environment_manager import EnvironmentManager

logger = logging.getLogger(__name__)

# Constants for environment integration
ENV_INTEGRATION_EVENT = f"{EVENT_SYSTEM}.environment"
ENV_PACKAGE_EVENT = f"{ENV_INTEGRATION_EVENT}.package"
ENV_EXEC_EVENT = f"{ENV_INTEGRATION_EVENT}.execute"
ENV_DATA_KEY = "kingdom:environment:integration:data"

class EnvironmentIntegration(BaseComponent):
    """
    Environment Integration for Kingdom AI.
    
    Provides a unified interface for working with multiple conda environments
    simultaneously, enabling system-wide access to all packages and functionalities.
    
    This component follows the Kingdom AI event-driven architecture and properly
    integrates with the event bus for system-wide communication.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, 
                 event_bus: Optional[Any] = None):
        """
        Initialize the Environment Integration component.
        
        Args:
            config: Configuration dictionary
            event_bus: Event bus for component communication
        """
        super().__init__(name="EnvironmentIntegration", event_bus=event_bus, config=config)
        
        # Configuration
        self.config = config or {}
        self.auto_connect = self.config.get("auto_connect", True)
        self.default_environment = self.config.get("default_environment", "base")
        self.redis_host = self.config.get("redis_host", "127.0.0.1")
        self.redis_port = self.config.get("redis_port", 6380)
        self.redis_password = self.config.get("redis_password", "QuantumNexus2025")
        
        # Components
        self.redis_nexus = None
        self.env_manager = None
        
        # State
        self.initialized = False
        self.environments = {}
        self.active_environment = None
        self.package_mapping = {}  # package -> [environments]
        self.platform = platform.system().lower()
        
        logger.info("Environment Integration component created")
    
    async def initialize(self) -> bool:
        """
        Initialize the Environment Integration component.
        
        This method follows the Kingdom AI initialization flow:
        1. Initialize core services (Redis)
        2. Load configurations
        3. Initialize dependent components
        4. Register event handlers
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            logger.info("Initializing Environment Integration component...")
            
            # Step 1: Initialize Redis Quantum Nexus
            self.redis_nexus = RedisQuantumNexus(config={
                "redis_host": self.redis_host,
                "redis_port": self.redis_port,
                "redis_password": self.redis_password,
                "auto_reconnect": True
            }, event_bus=self.event_bus)
            
            redis_init = await self.redis_nexus.initialize()
            if not redis_init:
                logger.error("Failed to initialize Redis Quantum Nexus")
                return False
            
            # Step 2: Initialize Environment Manager
            self.env_manager = EnvironmentManager(
                config=self.config,
                event_bus=self.event_bus,
                redis_nexus=self.redis_nexus
            )
            
            env_init = await self.env_manager.initialize()
            if not env_init:
                logger.error("Failed to initialize Environment Manager")
                return False
            
            # Step 3: Discover environments and build package mapping
            self.environments = await self.env_manager.discover_environments()
            await self._build_package_mapping()
            
            # Step 4: Register event handlers
            if self.event_bus:
                # Register environment event handlers
                self.event_bus.subscribe_sync(f"{ENV_INTEGRATION_EVENT}.activate", 
                                             self._handle_activate_environment)
                self.event_bus.subscribe_sync(f"{ENV_INTEGRATION_EVENT}.list", 
                                             self._handle_list_environments)
                self.event_bus.subscribe_sync(f"{ENV_PACKAGE_EVENT}.find", 
                                             self._handle_find_package)
                self.event_bus.subscribe_sync(f"{ENV_EXEC_EVENT}.run", 
                                             self._handle_execute_command)
                
                # Register system event handlers
                self.event_bus.subscribe_sync(f"{EVENT_SYSTEM}.status.request", 
                                            self._handle_status_request)
                
                logger.info("Environment Integration event handlers registered")
            
            # Step 5: Activate default environment if specified
            if self.default_environment and self.default_environment in self.environments:
                await self.activate_environment(self.default_environment)
            
            # Step 6: Publish integration status
            if self.event_bus:
                await self.event_bus.publish(f"{ENV_INTEGRATION_EVENT}.initialized", {
                    "environments": list(self.environments.keys()),
                    "package_count": len(self.package_mapping),
                    "active_environment": self.active_environment,
                    "timestamp": time.time()
                })
            
            self.initialized = True
            logger.info(f"Environment Integration initialized with {len(self.environments)} environments")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Environment Integration: {e}")
            return False
    
    async def _build_package_mapping(self) -> None:
        """
        Build a mapping of packages to environments.
        
        This enables quickly finding which environments contain a specific package.
        """
        logger.info("Building package mapping across all environments...")
        try:
            self.package_mapping = {}
            
            # Process each environment
            for env_name, env_info in self.environments.items():
                # Get packages for this environment
                packages = await self.env_manager.get_environment_packages(env_name)
                
                # Add each package to the mapping
                for pkg_name in packages.keys():
                    if pkg_name not in self.package_mapping:
                        self.package_mapping[pkg_name] = []
                    self.package_mapping[pkg_name].append(env_name)
            
            # Store the mapping in Redis for persistence
            if self.redis_nexus:
                await self.redis_nexus.set_data(
                    str(NexusEnvironment.CONFIG),
                    f"{ENV_DATA_KEY}:package_mapping", 
                    json.dumps(self.package_mapping)
                )
            
            logger.info(f"Built package mapping with {len(self.package_mapping)} packages")
        except Exception as e:
            logger.error(f"Error building package mapping: {e}")
    
    async def activate_environment(self, env_name: str) -> bool:
        """
        Activate a specific environment.
        
        Args:
            env_name: Environment name
            
        Returns:
            bool: True if activation was successful
        """
        if not self.env_manager:
            logger.error("Environment Manager not initialized")
            return False
        
        result = await self.env_manager.activate_environment(env_name)
        if result:
            self.active_environment = env_name
            
            if self.event_bus:
                await self.event_bus.publish(f"{ENV_INTEGRATION_EVENT}.activated", {
                    "environment": env_name,
                    "timestamp": time.time()
                })
            
            logger.info(f"Activated environment: {env_name}")
        
        return result
    
    async def find_package(self, package_name: str) -> Dict[str, Any]:
        """
        Find a package across all environments.
        
        Args:
            package_name: Package name to find
            
        Returns:
            Dict: Package information including environments and versions
        """
        if not self.env_manager:
            logger.error("Environment Manager not initialized")
            return {}
        
        # Normalize package name (lowercase)
        pkg_name = package_name.lower()
        
        # Check if package is in our mapping
        environments = self.package_mapping.get(pkg_name, [])
        if not environments:
            # If not in mapping, do a fresh check across environments
            pkg_info = await self.env_manager.get_package_info(pkg_name)
            environments = list(pkg_info.keys())
            
            # Update mapping if needed
            if environments and pkg_name not in self.package_mapping:
                self.package_mapping[pkg_name] = environments
        
        # Get detailed information
        result = {
            "package": pkg_name,
            "found": len(environments) > 0,
            "environments": {},
            "count": len(environments)
        }
        
        # Add version information for each environment
        for env_name in environments:
            packages = await self.env_manager.get_environment_packages(env_name)
            version = packages.get(pkg_name, "unknown")
            result["environments"][env_name] = {
                "version": version,
                "environment": env_name
            }
        
        logger.info(f"Found package {pkg_name} in {len(environments)} environments")
        return result
    
    async def execute_command(self, command: str, environment: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a command in a specific environment.
        
        Args:
            command: Command to execute
            environment: Environment name (uses active environment if None)
            
        Returns:
            Dict: Command execution results
        """
        if not self.env_manager:
            logger.error("Environment Manager not initialized")
            return {
                "success": False,
                "error": "Environment Manager not initialized"
            }
        
        # Use active environment if none specified
        env_name = environment or self.active_environment
        if not env_name:
            logger.error("No environment specified and no active environment")
            return {
                "success": False,
                "error": "No environment specified and no active environment"
            }
        
        # Execute the command
        return_code, stdout, stderr = await self.env_manager.execute_in_environment(env_name, command)
        
        result = {
            "success": return_code == 0,
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "environment": env_name,
            "command": command,
            "timestamp": time.time()
        }
        
        # Log the execution
        if return_code == 0:
            logger.info(f"Successfully executed command in {env_name}: {command}")
        else:
            logger.warning(f"Command execution failed in {env_name}: {command}")
            logger.debug(f"Error output: {stderr}")
        
        return result
    
    async def import_module_from_environment(self, module_name: str, environment: Optional[str] = None) -> Tuple[bool, Optional[Any]]:
        """
        Import a module from a specific environment.
        
        Args:
            module_name: Module name to import
            environment: Environment name (searches all environments if None)
            
        Returns:
            Tuple[bool, Optional[Any]]: Success flag and module if successful
        """
        if not self.env_manager:
            logger.error("Environment Manager not initialized")
            return False, None
        
        # If environment specified, try to import from that environment
        if environment:
            environments = [environment]
        else:
            # Find which environments have this module
            pkg_parts = module_name.split('.')[0]  # Get top-level package name
            find_result = await self.find_package(pkg_parts)
            environments = list(find_result.get("environments", {}).keys())
            
            if not environments:
                logger.warning(f"Module {module_name} not found in any environment")
                return False, None
        
        # Try each environment
        for env_name in environments:
            try:
                # Create a python command to import and check the module
                cmd = f"python -c \"import {module_name}; print('Module found')\"" 
                result = await self.execute_command(cmd, env_name)
                
                if result["success"]:
                    # Activate the environment that has the module
                    await self.activate_environment(env_name)
                    
                    # Try to import in the current process
                    module = importlib.import_module(module_name)
                    logger.info(f"Successfully imported {module_name} from {env_name}")
                    return True, module
            except Exception as e:
                logger.debug(f"Error importing {module_name} from {env_name}: {e}")
        
        logger.warning(f"Failed to import {module_name} from any environment")
        return False, None
    
    async def get_environment_status(self) -> Dict[str, Any]:
        """
        Get the status of all environments.
        
        Returns:
            Dict: Environment status information
        """
        if not self.env_manager or not self.initialized:
            return {
                "status": "not_initialized",
                "environments": {},
                "active": None,
                "package_count": 0
            }
        
        # Refresh environments if needed
        if not self.environments:
            self.environments = await self.env_manager.discover_environments()
        
        status = {
            "status": "active" if self.initialized else "inactive",
            "environments": {},
            "active": self.active_environment,
            "package_count": len(self.package_mapping),
            "total_environments": len(self.environments)
        }
        
        # Add info for each environment
        for env_name, env_info in self.environments.items():
            status["environments"][env_name] = {
                "name": env_name,
                "type": env_info.get("type", "unknown"),
                "is_active": env_name == self.active_environment,
                "path": env_info.get("path", "unknown"),
                "python_version": env_info.get("python_version", "unknown"),
                "package_count": len(env_info.get("packages", {}))
            }
        
        return status
    
    async def _handle_activate_environment(self, data: Dict[str, Any]) -> None:
        """
        Handle environment activation events.
        
        Args:
            data: Event data containing environment name
        """
        env_name = data.get("environment")
        if env_name:
            await self.activate_environment(env_name)
    
    async def _handle_list_environments(self, data: Dict[str, Any]) -> None:
        """
        Handle environment listing events.
        
        Args:
            data: Event data
        """
        if self.event_bus:
            status = await self.get_environment_status()
            await self.event_bus.publish(f"{ENV_INTEGRATION_EVENT}.list.result", status)
    
    async def _handle_find_package(self, data: Dict[str, Any]) -> None:
        """
        Handle package finding events.
        
        Args:
            data: Event data containing package name
        """
        package_name = data.get("package")
        if package_name and self.event_bus:
            result = await self.find_package(package_name)
            await self.event_bus.publish(f"{ENV_PACKAGE_EVENT}.find.result", result)
    
    async def _handle_execute_command(self, data: Dict[str, Any]) -> None:
        """
        Handle command execution events.
        
        Args:
            data: Event data containing command and optional environment
        """
        command = data.get("command")
        environment = data.get("environment")
        
        if command and self.event_bus:
            result = await self.execute_command(command, environment)
            await self.event_bus.publish(f"{ENV_EXEC_EVENT}.run.result", result)
    
    async def _handle_status_request(self, data: Dict[str, Any]) -> None:
        """
        Handle status request events.
        
        Args:
            data: Event data
        """
        if self.event_bus:
            status = await self.get_environment_status()
            await self.event_bus.publish(f"{ENV_INTEGRATION_EVENT}.status", status)
    
    async def cleanup(self) -> bool:
        """
        Clean up resources.
        
        Returns:
            bool: True if cleanup was successful
        """
        logger.info("Cleaning up Environment Integration component...")
        
        # Clean up environment manager
        if self.env_manager:
            await self.env_manager.cleanup()
        
        # Clean up Redis Quantum Nexus
        if self.redis_nexus:
            await self.redis_nexus.cleanup()
        
        self.initialized = False
        logger.info("Environment Integration component cleanup complete")
        return True
