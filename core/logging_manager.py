#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Logging System Module
Provides centralized, structured logging capabilities with multiple handlers,
log rotation, and integration with the event bus system.
"""

import os
import sys
import time
import json
import logging
import logging.handlers
from typing import Dict, Any
import threading
import traceback
import datetime
import queue

class LoggingManager:
    """
    Advanced Logging System for Kingdom AI.
    
    Provides structured logging with features like:
    - Multiple log destinations (file, console, event bus)
    - Log rotation and archiving
    - Log level management per component
    - Structured JSON format option
    - Integration with event bus for log event broadcasting
    - Thread-safe operations
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the Logging Manager.
        
        Args:
            event_bus: Event bus for publishing log events
            config: Configuration dictionary
        """
        self.event_bus = event_bus
        self.config = config or {}
        self.root_logger = logging.getLogger('KingdomAI')
        self.component_loggers = {}
        self.log_queue = queue.Queue()
        self.log_processor_thread = None
        self.running = False
        self.lock = threading.RLock()
        
        # Default logging configuration
        self.default_config = {
            'level': 'INFO',
            'file_logging': True,
            'console_logging': True,
            'json_format': True,
            'log_directory': os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs"),
            'max_file_size_mb': 10,
            'backup_count': 5,
            'component_levels': {
                'SecurityManager': 'DEBUG',
                'EventBus': 'INFO',
                'ErrorResolutionSystem': 'DEBUG'
            },
            'log_to_event_bus': True,
            'event_bus_level': 'INFO',
            'include_thread_info': True,
            'include_process_info': True
        }
        
        # Merge with provided config
        if self.config:
            self._merge_config()
        else:
            self.config = self.default_config
            
        # Initialize logging
        self._setup_logging()
    
    def initialize(self) -> bool:
        """
        Initialize the logging system.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Ensure log directory exists
            os.makedirs(self.config['log_directory'], exist_ok=True)
            
            # Start log processor thread if event bus is available
            if self.event_bus and self.config['log_to_event_bus']:
                self.running = True
                self.log_processor_thread = threading.Thread(
                    target=self._log_processor,
                    daemon=True,
                    name="LogProcessorThread"
                )
                self.log_processor_thread.start()
            
            self.root_logger.info("Logging Manager initialized successfully")
            return True
            
        except Exception as e:
            # Handle initialization errors
            sys.stderr.write(f"ERROR: Failed to initialize logging system: {str(e)}\n")
            return False
    
    def _merge_config(self) -> None:
        """Merge provided configuration with defaults."""
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    def _setup_logging(self) -> None:
        """Set up the logging system with handlers and formatters."""
        # Reset root logger to ensure clean setup
        for handler in list(self.root_logger.handlers):
            self.root_logger.removeHandler(handler)
        
        # Set root logger level
        level = getattr(logging, self.config['level'].upper())
        self.root_logger.setLevel(level)
        
        # Set up standard formatters
        if self.config['json_format']:
            formatter = JsonLogFormatter(
                include_thread=self.config['include_thread_info'],
                include_process=self.config['include_process_info']
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # Add file handler if enabled
        if self.config['file_logging']:
            try:
                os.makedirs(self.config['log_directory'], exist_ok=True)
                
                # Main log file with rotation
                main_log_file = os.path.join(self.config['log_directory'], 'kingdom.log')
                file_handler = logging.handlers.RotatingFileHandler(
                    main_log_file,
                    maxBytes=self.config['max_file_size_mb'] * 1024 * 1024,
                    backupCount=self.config['backup_count']
                )
                file_handler.setFormatter(formatter)
                self.root_logger.addHandler(file_handler)
                
                # Error log file with rotation
                error_log_file = os.path.join(self.config['log_directory'], 'kingdom_error.log')
                error_handler = logging.handlers.RotatingFileHandler(
                    error_log_file,
                    maxBytes=self.config['max_file_size_mb'] * 1024 * 1024,
                    backupCount=self.config['backup_count']
                )
                error_handler.setLevel(logging.ERROR)
                error_handler.setFormatter(formatter)
                self.root_logger.addHandler(error_handler)
                
            except Exception as e:
                sys.stderr.write(f"ERROR: Failed to set up file logging: {str(e)}\n")
        
        # Add console handler if enabled
        if self.config['console_logging']:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.root_logger.addHandler(console_handler)
        
        # Set up event bus handler if enabled
        if self.event_bus and self.config['log_to_event_bus']:
            event_bus_level = getattr(logging, self.config['event_bus_level'].upper())
            event_bus_handler = EventBusLogHandler(
                self.event_bus,
                self.log_queue,
                level=event_bus_level
            )
            self.root_logger.addHandler(event_bus_handler)
    
    def get_logger(self, component_name: str) -> logging.Logger:
        """
        Get a logger for a specific component.
        
        Args:
            component_name: Name of the component
            
        Returns:
            logging.Logger: Logger instance for the component
        """
        with self.lock:
            if component_name in self.component_loggers:
                return self.component_loggers[component_name]
            
            # Create logger
            logger = logging.getLogger(f"KingdomAI.{component_name}")
            
            # Set component-specific level if configured
            if 'component_levels' in self.config and component_name in self.config['component_levels']:
                level_name = self.config['component_levels'][component_name]
                level = getattr(logging, level_name.upper())
                logger.setLevel(level)
            
            self.component_loggers[component_name] = logger
            return logger
    
    def set_component_level(self, component_name: str, level: str) -> bool:
        """
        Set the logging level for a specific component.
        
        Args:
            component_name: Name of the component
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            
        Returns:
            bool: True if level was set, False otherwise
        """
        try:
            with self.lock:
                # Update configuration
                if 'component_levels' not in self.config:
                    self.config['component_levels'] = {}
                
                self.config['component_levels'][component_name] = level
                
                # Update logger if it exists
                if component_name in self.component_loggers:
                    level_value = getattr(logging, level.upper())
                    self.component_loggers[component_name].setLevel(level_value)
                
                return True
        except Exception as e:
            self.root_logger.error(f"Failed to set log level for {component_name}: {str(e)}")
            return False
    
    def set_global_level(self, level: str) -> bool:
        """
        Set the global logging level.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            
        Returns:
            bool: True if level was set, False otherwise
        """
        try:
            level_value = getattr(logging, level.upper())
            
            with self.lock:
                # Update configuration
                self.config['level'] = level
                
                # Update root logger
                self.root_logger.setLevel(level_value)
                
                return True
        except Exception as e:
            self.root_logger.error(f"Failed to set global log level: {str(e)}")
            return False
    
    def _log_processor(self) -> None:
        """Process logs from the queue and publish to event bus."""
        while self.running:
            try:
                # Get log record from queue with timeout
                record = self.log_queue.get(timeout=1.0)
                
                # Process and publish to event bus
                if self.event_bus:
                    self.event_bus.publish(
                        channel='system.logs',
                        data=record,
                        priority=3  # Medium priority for regular logs
                    )
                
                self.log_queue.task_done()
                
            except queue.Empty:
                # Queue timeout, continue loop
                continue
                
            except Exception as e:
                # Write error to stderr as logger might be unavailable
                sys.stderr.write(f"ERROR: Log processor error: {str(e)}\n")
                try:
                    # Sleep briefly to avoid tight error loop
                    time.sleep(0.1)
                except:
                    pass
    
    def rotate_logs(self) -> bool:
        """
        Force rotation of log files.
        
        Returns:
            bool: True if rotation successful, False otherwise
        """
        try:
            with self.lock:
                for handler in self.root_logger.handlers:
                    if isinstance(handler, logging.handlers.RotatingFileHandler):
                        handler.doRollover()
                
                self.root_logger.info("Log files rotated")
                return True
                
        except Exception as e:
            self.root_logger.error(f"Failed to rotate logs: {str(e)}")
            return False
    
    def archive_old_logs(self, days: int = 30) -> int:
        """
        Archive log files older than specified days.
        
        Args:
            days: Number of days to keep logs before archiving
            
        Returns:
            int: Number of archived log files
        """
        try:
            log_dir = self.config['log_directory']
            archive_dir = os.path.join(log_dir, 'archive')
            os.makedirs(archive_dir, exist_ok=True)
            
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            archived_count = 0
            
            for filename in os.listdir(log_dir):
                if not filename.endswith('.log'):
                    continue
                
                file_path = os.path.join(log_dir, filename)
                file_mtime = os.path.getmtime(file_path)
                
                if file_mtime < cutoff_time:
                    # Archive the file
                    archive_timestamp = datetime.datetime.fromtimestamp(file_mtime).strftime('%Y%m%d')
                    archive_filename = f"{filename}.{archive_timestamp}"
                    archive_path = os.path.join(archive_dir, archive_filename)
                    
                    # Ensure we don't overwrite existing archive
                    counter = 1
                    while os.path.exists(archive_path):
                        archive_path = os.path.join(archive_dir, f"{archive_filename}.{counter}")
                        counter += 1
                    
                    os.rename(file_path, archive_path)
                    archived_count += 1
            
            self.root_logger.info(f"Archived {archived_count} log files")
            return archived_count
            
        except Exception as e:
            self.root_logger.error(f"Failed to archive logs: {str(e)}")
            return 0
    
    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the logging system.
        
        Returns:
            dict: Dictionary with logging statistics
        """
        stats = {
            'global_level': logging.getLevelName(self.root_logger.level),
            'component_levels': {},
            'handler_count': len(self.root_logger.handlers),
            'queue_size': self.log_queue.qsize() if hasattr(self, 'log_queue') else 0,
            'log_directories': {
                'main': self.config['log_directory'],
                'exists': os.path.exists(self.config['log_directory'])
            }
        }
        
        # Add component levels
        for component, logger in self.component_loggers.items():
            stats['component_levels'][component] = logging.getLevelName(logger.level)
        
        # Add handler information
        stats['handlers'] = []
        for handler in self.root_logger.handlers:
            handler_info = {
                'type': handler.__class__.__name__,
                'level': logging.getLevelName(handler.level)
            }
            
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                handler_info['file'] = handler.baseFilename
                handler_info['max_bytes'] = handler.maxBytes
                handler_info['backup_count'] = handler.backupCount
            
            stats['handlers'].append(handler_info)
        
        return stats
    
    def shutdown(self) -> None:
        """Perform a clean shutdown of the logging system."""
        self.root_logger.info("Shutting down Logging Manager...")
        
        # Stop log processor thread
        self.running = False
        
        if self.log_processor_thread and self.log_processor_thread.is_alive():
            self.log_processor_thread.join(timeout=2.0)
        
        # Flush all handlers
        for handler in self.root_logger.handlers:
            try:
                handler.flush()
                handler.close()
            except:
                pass
        
        self.root_logger.info("Logging Manager shutdown complete")


class JsonLogFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    """
    
    def __init__(self, include_thread=True, include_process=True):
        """
        Initialize JSON formatter.
        
        Args:
            include_thread: Whether to include thread information
            include_process: Whether to include process information
        """
        super().__init__()
        self.include_thread = include_thread
        self.include_process = include_process
    
    def format(self, record):
        """
        Format log record as JSON.
        
        Args:
            record: Log record
            
        Returns:
            str: JSON-formatted log record
        """
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'name': record.name,
            'message': record.getMessage()
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add thread information if enabled
        if self.include_thread:
            log_data['thread'] = {
                'id': record.thread,
                'name': record.threadName
            }
        
        # Add process information if enabled
        if self.include_process:
            log_data['process'] = {
                'id': record.process,
                'name': record.processName
            }
        
        # Add extra attributes if present
        if hasattr(record, 'props'):
            log_data.update(record.props)
        
        return json.dumps(log_data)


class EventBusLogHandler(logging.Handler):
    """
    Log handler that sends logs to the event bus.
    """
    
    def __init__(self, event_bus, log_queue, level=logging.INFO):
        """
        Initialize event bus log handler.
        
        Args:
            event_bus: Event bus instance
            log_queue: Queue for asynchronous log processing
            level: Minimum log level to handle
        """
        super().__init__(level)
        self.event_bus = event_bus
        self.log_queue = log_queue
    
    def emit(self, record):
        """
        Emit a log record to the event bus.
        
        Args:
            record: Log record
        """
        try:
            # Format record for event bus
            log_data = {
                'timestamp': self.formatter.formatTime(record) if self.formatter else time.time(),
                'level': record.levelname,
                'level_number': record.levelno,
                'name': record.name,
                'message': record.getMessage(),
                'pathname': record.pathname,
                'lineno': record.lineno,
                'thread': {
                    'id': record.thread,
                    'name': record.threadName
                },
                'process': {
                    'id': record.process,
                    'name': record.processName
                }
            }
            
            # Add exception information if present
            if record.exc_info:
                log_data['exception'] = {
                    'type': record.exc_info[0].__name__,
                    'message': str(record.exc_info[1]),
                    'traceback': ''.join(traceback.format_exception(*record.exc_info))
                }
            
            # Queue log for async processing
            self.log_queue.put(log_data)
            
        except Exception:
            self.handleError(record)
