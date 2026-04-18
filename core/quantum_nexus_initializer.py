#!/usr/bin/env python3
"""
Kingdom AI Quantum Nexus Initializer

This module initializes the Redis Quantum Nexus connection and
provides helper functions for working with the Quantum Nexus.
"""

import os
import logging
import redis
import time
import threading
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QuantumNexus")

class QuantumNexusInitializer:
    """
    Initializes and manages the Redis Quantum Nexus connection.
    
    The Quantum Nexus is a special Redis instance used for high-performance
    data exchange between Kingdom AI components.
    """
    
    def __init__(self, host="localhost", port=6380, password_file=None):
        """Initialize the Quantum Nexus Initializer"""
        self.host = host
        self.port = port
        self.password = 'QuantumNexus2025'
        self.password_file = password_file
        self.connection = None
        self.redis_server_process = None
        self.redis_running = False
        
        # Redis config file path
        self.redis_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "redis.conf")
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Read password from file if available
        self._load_password()
    
    def initialize(self):
        """Initialize the Quantum Nexus"""
        logger.info("Initializing Quantum Nexus...")
        
        # Check if Redis is running
        if not self._check_redis_running():
            # Create Redis config if needed
            self._create_redis_config()
            
            # Start Redis server
            self._start_redis_server()
        
        # Connect to Redis
        self._connect_to_redis()
        
        return self.connection is not None
    
    def _load_password(self):
        """Load the Redis password from file"""
        if not self.password_file:
            # Default password file location
            self.password_file = os.path.join(self.root_dir, "redis_password.txt")
        
        try:
            if os.path.exists(self.password_file):
                with open(self.password_file, 'r') as f:
                    self.password = f.read().strip()
                logger.info(f"Loaded Redis password from {self.password_file}")
            else:
                logger.warning(f"Password file {self.password_file} not found, using default password")
                
                # Write default password to file
                with open(self.password_file, 'w') as f:
                    f.write(self.password)
                logger.info(f"Created default password file at {self.password_file}")
        except Exception as e:
            logger.error(f"Error loading Redis password: {e}")
    
    def _check_redis_running(self):
        """Check if Redis is already running on the specified port"""
        try:
            # NOTE: This direct redis.Redis() call is acceptable here - we're checking
            # if the Redis server is running BEFORE initializing the Quantum Nexus.
            # Application code should use RedisQuantumNexus, not direct connections.
            r = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                socket_connect_timeout=2
            )
            
            # Try to ping Redis
            response = r.ping()
            r.close()
            
            if response:
                logger.info(f"Redis already running on {self.host}:{self.port}")
                self.redis_running = True
                return True
                
        except (redis.ConnectionError, ConnectionError):
            logger.info(f"Redis not running on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Error checking Redis: {e}")
            
        return False
    
    def _create_redis_config(self):
        """Create Redis configuration file"""
        try:
            with open(self.redis_config, 'w') as f:
                f.write(f"port {self.port}\n")
                f.write("bind 127.0.0.1\n")
                f.write("daemonize no\n")
                f.write(f"requirepass {self.password}\n")
                f.write("appendonly yes\n")
                f.write("appendfsync everysec\n")
                f.write("dir ./\n")
                f.write("loglevel notice\n")
            
            logger.info(f"Created Redis configuration at {self.redis_config}")
            return True
        except Exception as e:
            logger.error(f"Error creating Redis configuration: {e}")
            return False
    
    def _start_redis_server(self):
        """Start the Redis server process"""
        try:
            # Check for redis-server in PATH
            redis_server = self._find_redis_server()
            
            if not redis_server:
                logger.error("Redis server executable not found")
                return False
            
            # Start Redis server
            cmd = [redis_server, self.redis_config]
            
            # Run in a separate thread to avoid blocking
            def run_redis_server():
                try:
                    logger.info(f"Starting Redis server: {' '.join(cmd)}")
                    self.redis_server_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=self.root_dir
                    )
                    
                    # Wait for process to start
                    time.sleep(2)
                    
                    if self.redis_server_process.poll() is None:
                        logger.info("Redis server started successfully")
                        self.redis_running = True
                    else:
                        stdout, stderr = self.redis_server_process.communicate()
                        logger.error(f"Redis server failed to start: {stderr.decode('utf-8')}")
                        self.redis_running = False
                        
                except Exception as e:
                    logger.error(f"Error starting Redis server: {e}")
                    self.redis_running = False
            
            # Start Redis in a thread
            redis_thread = threading.Thread(target=run_redis_server)
            redis_thread.daemon = True
            redis_thread.start()
            
            # Wait for Redis to start
            time.sleep(3)
            
            return self.redis_running
        except Exception as e:
            logger.error(f"Error starting Redis server: {e}")
            return False
    
    def _find_redis_server(self):
        """Find the redis-server executable"""
        # Check common locations
        locations = [
            "redis-server",
            "/usr/bin/redis-server",
            "/usr/local/bin/redis-server",
            "/snap/bin/redis-server",
            os.path.join(self.root_dir, "redis", "redis-server"),
            os.path.join(self.root_dir, "tools", "redis", "redis-server"),
            "C:\\Program Files\\Redis\\redis-server.exe",
            "C:\\Redis\\redis-server.exe",
        ]
        
        for location in locations:
            try:
                # Check if the command exists
                result = subprocess.run(
                    [location, "--version"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    shell=True
                )
                
                if result.returncode == 0:
                    logger.info(f"Found Redis server at: {location}")
                    return location
            except:
                pass
        
        logger.warning("Redis server not found, please install Redis or specify the path to redis-server")
        return None
    
    def _connect_to_redis(self):
        """Connect to the Redis server"""
        try:
            # Try to connect with retries
            max_retries = 5
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    # NOTE: This direct redis.Redis() call is acceptable here - we're initializing
                    # the Quantum Nexus itself. Application code should use RedisQuantumNexus.
                    self.connection = redis.Redis(
                        host=self.host,
                        port=self.port,
                        password=self.password,
                        decode_responses=True
                    )
                    
                    # Test the connection
                    if self.connection.ping():
                        logger.info(f"Connected to Redis at {self.host}:{self.port}")
                        return True
                    
                except (redis.ConnectionError, ConnectionError):
                    if attempt < max_retries - 1:
                        logger.warning(f"Failed to connect to Redis (attempt {attempt+1}/{max_retries}), retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Failed to connect to Redis after {max_retries} attempts")
                        self.connection = None
                        return False
                        
        except Exception as e:
            logger.error(f"Error connecting to Redis: {e}")
            self.connection = None
            return False
    
    def get_connection(self):
        """Get the Redis connection"""
        return self.connection
    
    def shutdown(self):
        """Shutdown the Quantum Nexus"""
        try:
            # Close Redis connection
            if self.connection:
                self.connection.close()
                self.connection = None
            
            # Shutdown Redis server if we started it
            if self.redis_server_process:
                logger.info("Shutting down Redis server")
                self.redis_server_process.terminate()
                self.redis_server_process.wait(timeout=5)
                self.redis_server_process = None
                self.redis_running = False
                
            logger.info("Quantum Nexus shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error shutting down Quantum Nexus: {e}")
            return False

# Singleton instance
_instance = None

def get_instance():
    """Get singleton instance of the Quantum Nexus Initializer"""
    global _instance
    if _instance is None:
        _instance = QuantumNexusInitializer()
    return _instance

def initialize():
    """Initialize the Quantum Nexus"""
    return get_instance().initialize()

def get_connection():
    """Get the Redis connection"""
    return get_instance().get_connection()

def shutdown():
    """Shutdown the Quantum Nexus"""
    return get_instance().shutdown()
