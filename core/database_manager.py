#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DatabaseManager component for Kingdom AI.
Manages database connections and operations.
"""

import os
import asyncio
import logging
import time
import aiosqlite
from datetime import datetime
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)
Base = declarative_base()

class DatabaseManager(BaseComponent):
    """
    Component for managing database connections and operations.
    Supports SQLite, PostgreSQL, and MySQL/MariaDB.
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the DatabaseManager component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        # Ensure proper initialization with event_bus
        super().__init__("DatabaseManager", event_bus, config)
        self.logger = logging.getLogger("core.database_manager")
        self.logger.info("Initializing DatabaseManager")
        self.description = "Manages database connections and operations"
        
        # Database configuration
        self.db_type = self.config.get("db_type", "sqlite")  # sqlite, postgres, mysql
        self.db_path = self.config.get("db_path", os.path.join(os.path.dirname(__file__), '..', 'data', 'kingdom.db'))
        self.db_host = self.config.get("db_host", "localhost")
        self.db_port = self.config.get("db_port", 5432 if self.db_type == "postgres" else 3306)
        self.db_name = self.config.get("db_name", "kingdom")
        self.db_user = self.config.get("db_user", "")
        self.db_password = self.config.get("db_password", "")
        self.pool_size = self.config.get("pool_size", 5)
        self.max_overflow = self.config.get("max_overflow", 10)
        self.connection_timeout = self.config.get("connection_timeout", 30)
        
        # Connection objects
        self.engine = None
        self.session_factory = None
        self.sqlite_connection = None
        self.is_connected = False
        self.connection_retry_count = 0
        self.max_connection_retries = 3
        
        # Status tracking
        self.last_operation_time = None
        self.operation_count = 0
        self.failed_operation_count = 0
        
    async def safe_publish(self, event_name, event_data=None):
        """Safely publish an event to the event bus if it exists.
        
        Args:
            event_name: Name of the event to publish
            event_data: Data to include with the event
        """
        if self.event_bus:
            try:
                await self.event_bus.publish(event_name, event_data)
            except Exception as e:
                self.logger.error(f"Error publishing event {event_name}: {e}")
        else:
            self.logger.debug(f"Event {event_name} not published (no event bus)")
            
    async def initialize(self) -> bool:
        """Initialize the DatabaseManager component.
        
        Returns:
            bool: True if initialized successfully, False otherwise
        """
        try:
            self.logger.info("Initializing DatabaseManager")
            
            # Subscribe to events if event_bus is available
            if self.event_bus:
                # Don't await sync subscription methods
                self.event_bus.subscribe_sync("database.query", self.on_database_query)
                self.event_bus.subscribe_sync("database.execute", self.on_database_execute)
                self.event_bus.subscribe_sync("database.status.request", self.on_status_request)
                self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
                self.event_bus.subscribe_sync("config.update.database", self.on_config_update)
                self.logger.info("Database manager event subscriptions initialized")
            else:
                self.logger.warning("No event bus available, database events will not be published")
            
            # Create database directory if needed
            if self.db_type == "sqlite":
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Initialize database connection
            await self.connect()
            
            self.logger.info("DatabaseManager initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database manager: {e}")
            return False
    
    async def connect(self) -> bool:
        """Establish database connection.
        
        Returns:
            bool: True if connection succeeded, False otherwise
        """
        try:
            if self.db_type == "sqlite":
                await self._connect_sqlite()
            else:
                await self._connect_sqlalchemy()
                
            self.is_connected = True
            self.connection_retry_count = 0
            
            # Publish connection status
            await self.safe_publish("database.status", {
                "status": "connected",
                "type": self.db_type,
                "timestamp": datetime.now().isoformat()
            })
            
            self.logger.info(f"Connected to {self.db_type} database")
            return True
        except Exception as e:
            self.is_connected = False
            self.connection_retry_count += 1
            
            self.logger.error(f"Database connection error: {str(e)}")
            
            # Publish error
            await self.safe_publish("database.error", {
                "error": str(e),
                "type": self.db_type,
                "retry_count": self.connection_retry_count,
                "timestamp": datetime.now().isoformat()
            })
            
            # Retry connection if not exceeding max retries
            if self.connection_retry_count <= self.max_connection_retries:
                retry_delay = 2 ** self.connection_retry_count  # Exponential backoff
                self.logger.info(f"Retrying database connection in {retry_delay} seconds...")
                
                await asyncio.sleep(retry_delay)
                return await self.connect()
            
            return False
    
    async def _connect_sqlite(self):
        """Connect to SQLite database."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Create connection
        self.sqlite_connection = await aiosqlite.connect(self.db_path)
        
        # Enable foreign keys
        await self.sqlite_connection.execute("PRAGMA foreign_keys = ON")
        
        # Set connection to return dictionaries
        self.sqlite_connection.row_factory = aiosqlite.Row
    
    async def _connect_sqlalchemy(self):
        """Connect using SQLAlchemy."""
        # Construct connection string
        if self.db_type == "postgres":
            conn_str = f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        elif self.db_type == "mysql":
            conn_str = f"mysql+aiomysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
        
        # Create engine
        self.engine = create_async_engine(
            conn_str,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.connection_timeout,
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False  # Set to True for debug SQL logs
        )
        
        # Create session factory for async sessions
        self.session_factory = sessionmaker(
            expire_on_commit=False, class_=AsyncSession
        )
        # Bind the session to the engine
        self.session_factory.configure(bind=self.engine)
    
    async def get_session(self):
        """Get a database session."""
        if not self.is_connected:
            await self.connect()
            
        if self.db_type == "sqlite":
            return self.sqlite_connection
        else:
            return self.session_factory()
    
    async def execute_query(self, query, params=None, fetch_all=True):
        """
        Execute a database query.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch_all: Whether to fetch all results or just one
            
        Returns:
            Query results
        """
        self.last_operation_time = time.time()
        self.operation_count += 1
        
        try:
            if self.db_type == "sqlite":
                return await self._execute_sqlite_query(query, params, fetch_all)
            else:
                return await self._execute_sqlalchemy_query(query, params, fetch_all)
        except Exception as e:
            self.failed_operation_count += 1
            logger.error(f"Query execution error: {str(e)}")
            
            # Publish error
            await self.safe_publish("database.error", {
                "error": str(e),
                "query": query,
                "timestamp": datetime.now().isoformat()
            })
            
            raise
    
    async def _execute_sqlite_query(self, query, params=None, fetch_all=True):
        """Execute a query on SQLite database."""
        async with self.sqlite_connection.execute(query, params or ()) as cursor:
            if fetch_all:
                return await cursor.fetchall()
            else:
                return await cursor.fetchone()
    
    async def _execute_sqlalchemy_query(self, query, params=None, fetch_all=True):
        """Execute a query using SQLAlchemy."""
        if not self.session_factory or not self.engine:
            raise ValueError("Database connection not properly initialized")
            
        stmt = sqlalchemy.text(query)
        
        # Use AsyncSession properly
        try:
            async with self.session_factory() as session:
                result = await session.execute(stmt, params or {})
                
                if fetch_all:
                    return result.fetchall()
                else:
                    return result.fetchone()
        except Exception as e:
            self.logger.error(f"SQLAlchemy query execution error: {e}")
            raise
    
    async def execute_statement(self, statement, params=None):
        """
        Execute a database statement (INSERT, UPDATE, DELETE).
        
        Args:
            statement: SQL statement
            params: Statement parameters
            
        Returns:
            Result of execution
        """
        self.last_operation_time = time.time()
        self.operation_count += 1
        
        try:
            if self.db_type == "sqlite":
                return await self._execute_sqlite_statement(statement, params)
            else:
                return await self._execute_sqlalchemy_statement(statement, params)
        except Exception as e:
            self.failed_operation_count += 1
            logger.error(f"Statement execution error: {str(e)}")
            
            # Publish error
            await self.safe_publish("database.error", {
                "error": str(e),
                "statement": statement,
                "timestamp": datetime.now().isoformat()
            })
            
            raise
    
    async def _execute_sqlite_statement(self, statement, params=None):
        """Execute a statement on SQLite database."""
        async with self.sqlite_connection.execute(statement, params or ()) as cursor:
            await self.sqlite_connection.commit()
            return cursor.rowcount
    
    async def _execute_sqlalchemy_statement(self, statement, params=None):
        """Execute a statement using SQLAlchemy."""
        if not self.session_factory or not self.engine:
            raise ValueError("Database connection not properly initialized")
            
        stmt = sqlalchemy.text(statement)
        
        # Use AsyncSession properly
        try:
            async with self.session_factory() as session:
                try:
                    result = await session.execute(stmt, params or {})
                    await session.commit()
                    return result.rowcount
                except Exception as e:
                    await session.rollback()
                    raise e
        except Exception as e:
            self.logger.error(f"SQLAlchemy statement execution error: {e}")
            raise
    
    async def on_database_query(self, data):
        """
        Handle database query request.
        
        Args:
            data: Query data with query, params, and request_id
        """
        if not data or not isinstance(data, dict):
            self.logger.error("Invalid data received for database query")
            return
            
        request_id = data.get("request_id", "unknown")
        query = data.get("query", "")
        params = data.get("params", {})
        fetch_all = data.get("fetch_all", True)
        
        try:
            results = await self.execute_query(query, params, fetch_all)
            
            await self.safe_publish("database.query.result", {
                "request_id": request_id,
                "success": True,
                "results": results,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            self.logger.error(f"Error in on_database_query: {e}")
            await self.safe_publish("database.query.result", {
                "request_id": request_id,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    async def on_database_execute(self, data):
        """
        Handle database execute request.
        
        Args:
            data: Execute data with statement, params, and request_id
        """
        if not data or not isinstance(data, dict):
            self.logger.error("Invalid data received for database execute")
            return
            
        request_id = data.get("request_id", "unknown")
        statement = data.get("statement", "")
        params = data.get("params", {})
        
        try:
            result = await self.execute_statement(statement, params)
            
            await self.safe_publish("database.execute.result", {
                "request_id": request_id,
                "success": True,
                "rows_affected": result,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            self.logger.error(f"Error in on_database_execute: {e}")
            await self.safe_publish("database.execute.result", {
                "request_id": request_id,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    async def on_status_request(self, data):
        """
        Handle database status request.
        
        Args:
            data: Request data
        """
        if not data or not isinstance(data, dict):
            self.logger.error("Invalid data received for status request")
            return
            
        request_id = data.get("request_id", "unknown")
        
        # Check connection
        is_connected = self.is_connected
        if is_connected:
            # Verify connection is still valid
            try:
                if self.db_type == "sqlite" and self.sqlite_connection:
                    async with self.sqlite_connection.execute("SELECT 1") as cursor:
                        await cursor.fetchone()
                elif self.engine and self.session_factory:
                    # Use properly created async session
                    async with self.session_factory() as session:
                        await session.execute(sqlalchemy.text("SELECT 1"))
                else:
                    is_connected = False
            except Exception as e:
                self.logger.error(f"Error checking connection status: {e}")
                is_connected = False
        
        await self.safe_publish("database.status.response", {
            "request_id": request_id,
            "is_connected": is_connected,
            "db_type": self.db_type,
            "operation_count": self.operation_count,
            "failed_operation_count": self.failed_operation_count,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_config_update(self, data):
        """
        Handle configuration update.
        
        Args:
            data: Configuration data
        """
        if not data or not isinstance(data, dict):
            return
            
        # Update configuration
        for key, value in data.items():
            if key in ["db_type", "db_path", "db_host", "db_port", "db_name", "db_user", "db_password",
                       "pool_size", "max_overflow", "connection_timeout"]:
                self.config[key] = value
                setattr(self, key, value)
            self.pool_size = pool_size
            
        max_overflow = data.get("max_overflow")
        if max_overflow:
            self.max_overflow = max_overflow
        
        connection_timeout = data.get("connection_timeout")
        if connection_timeout:
            self.connection_timeout = connection_timeout
            
        # Reconnect with new configuration
        await self.shutdown()
        await self.connect()
        
        logger.info("Database configuration updated")
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the DatabaseManager component."""
        logger.info("Shutting down DatabaseManager")
        
        if self.db_type == "sqlite" and self.sqlite_connection:
            await self.sqlite_connection.close()
        elif self.engine:
            await self.engine.dispose()
        
        self.is_connected = False
        
        logger.info("DatabaseManager shut down successfully")
