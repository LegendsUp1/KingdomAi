#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Session Manager Component

Centralized manager for aiohttp client sessions to prevent resource leaks
and ensure proper cleanup during system shutdown.
"""

import asyncio
import logging
from typing import Set, Optional
import aiohttp
from contextlib import asynccontextmanager

from core.base_component import BaseComponent

logger = logging.getLogger("KingdomAI.SessionManager")

class SessionManager(BaseComponent):
    """Centralized manager for aiohttp sessions.
    
    Tracks and manages all aiohttp ClientSession instances to ensure proper cleanup.
    Provides methods for:
    - Creating sessions
    - Tracking active sessions
    - Closing sessions properly during shutdown
    """
    
    def __init__(self, event_bus=None):
        """Initialize the session manager.
        
        Args:
            event_bus: EventBus instance for event communication
        """
        super().__init__(name="SessionManager", event_bus=event_bus)
        self._sessions: Set[aiohttp.ClientSession] = set()
        self._lock = asyncio.Lock()
        self._default_session = None
        logger.info("SessionManager initialized")
    
    async def initialize(self) -> bool:
        """Initialize the session manager.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            logger.info("Initializing SessionManager...")
            
            # Subscribe to system events if event bus is available
            if self.event_bus:
                await self.event_bus.subscribe_sync("system.shutdown", self._handle_system_shutdown)
                
            self.is_initialized = True
            logger.info("SessionManager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SessionManager: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the session manager.
        
        Returns:
            bool: True if started successfully
        """
        try:
            if not self.is_initialized:
                logger.warning("SessionManager must be initialized before starting")
                await self.initialize()
                
            logger.info("Starting SessionManager...")
            
            # Create default session that can be used by components that don't need a custom session
            self._default_session = await self.create_session(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "KingdomAI/1.0"}
            )
            
            self.is_running = True
            logger.info("SessionManager started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start SessionManager: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the session manager and clean up resources.
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            logger.info("Stopping SessionManager...")
            
            # Close all sessions
            await self.close_all()
            
            self.is_running = False
            logger.info("SessionManager stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop SessionManager: {e}")
            return False
    
    async def create_session(self, **kwargs) -> aiohttp.ClientSession:
        """Create and track a new client session.
        
        Args:
            **kwargs: Keyword arguments to pass to aiohttp.ClientSession
            
        Returns:
            aiohttp.ClientSession: Newly created session
        """
        try:
            session = aiohttp.ClientSession(**kwargs)
            async with self._lock:
                self._sessions.add(session)
            logger.debug(f"Created new session (active: {len(self._sessions)})")
            return session
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def close_session(self, session: aiohttp.ClientSession) -> bool:
        """Close a specific session and remove it from tracking.
        
        Args:
            session: The session to close
            
        Returns:
            bool: True if closed successfully
        """
        if not session:
            return False
            
        try:
            if not session.closed:
                await session.close()
                
            async with self._lock:
                if session in self._sessions:
                    self._sessions.remove(session)
                    
            logger.debug(f"Closed session (remaining: {len(self._sessions)})")
            return True
        except Exception as e:
            logger.error(f"Error closing session: {e}")
            return False
    
    async def close_all(self) -> bool:
        """Close all tracked sessions.
        
        Returns:
            bool: True if all sessions were closed successfully
        """
        logger.info("Closing all sessions...")
        
        try:
            success = True
            sessions_to_close = set()
            
            # Make a copy of the sessions set to avoid modification during iteration
            async with self._lock:
                sessions_to_close = self._sessions.copy()
                
            # Close default session if it exists
            if self._default_session and not self._default_session.closed:
                try:
                    await self._default_session.close()
                    logger.debug("Closed default session")
                except Exception as e:
                    logger.error(f"Error closing default session: {e}")
                    success = False
                    
            # Close all other sessions
            for session in sessions_to_close:
                try:
                    if not session.closed:
                        await session.close()
                except Exception as e:
                    logger.error(f"Error closing session: {e}")
                    success = False
                    
            # Clear the sessions set
            async with self._lock:
                self._sessions.clear()
                
            logger.info(f"Closed all sessions (success: {success})")
            return success
            
        except Exception as e:
            logger.error(f"Error closing all sessions: {e}")
            return False
    
    async def get_session(self):
        """Get a client session.
        
        Returns:
            aiohttp.ClientSession: Client session
        """
        try:
            if not self._default_session or self._default_session.closed:
                self._default_session = await self.create_session(
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={"User-Agent": "KingdomAI/1.0"}
                )
            return self._default_session
        except Exception as e:
            logger.error(f"Error creating client session: {e}")
            return None
    
    def initialize_sync(self):

    
        """Synchronous version of initialize"""

    
        return True

        """Get a client session.
        
        Returns:
            aiohttp.ClientSession: Client session
        """
        try:
            if not self._default_session or self._default_session.closed:
                self._default_session = aiohttp.ClientSession()
            return self._default_session
        except Exception as e:
            logger.error(f"Error creating client session: {e}")
            return None
    
    @asynccontextmanager
    async def session(self, **kwargs):
        """Context manager for creating and auto-closing a session.
        
        Args:
            **kwargs: Keyword arguments for aiohttp.ClientSession
            
        Yields:
            aiohttp.ClientSession: The created client session
        """
        session = await self.create_session(**kwargs)
        try:
            yield session
        finally:
            await self.close_session(session)
    
    def get_default_session(self) -> Optional[aiohttp.ClientSession]:
        """Get the default session, creating it if necessary.
        
        Returns:
            Optional[aiohttp.ClientSession]: Default session or None if unavailable
        """
        if self._default_session and not self._default_session.closed:
            return self._default_session
        return None
    
    async def _handle_system_shutdown(self, data=None):
        """Handle system shutdown event by closing all sessions."""
        logger.info("Received system shutdown event, closing all sessions")
        await self.close_all()
