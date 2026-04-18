#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - File Manager Component

This module provides file system operations, storage management, and integration 
with other Kingdom AI components. It handles file operations safely with proper
error handling and security validation.
"""

import os
import json
import time
import shutil
import logging
import tempfile
import threading
import traceback
from typing import Any, Optional, Union
from datetime import datetime

logger = logging.getLogger("KingdomAI.FileManager")

class FileManager:
    """
    Kingdom AI File Manager

    Handles all file system operations for the Kingdom AI system, including:
    - File creation, reading, writing, and deletion
    - Directory management
    - File synchronization
    - Backup and restore functionality
    - Security checks and validation
    - Temporary file management
    """

    def __init__(self, event_bus=None, config=None, security_manager=None):
        """
        Initialize the FileManager with event bus integration and security.

        Args:
            event_bus: EventBus instance for system communication
            config: ConfigManager instance for configuration settings
            security_manager: SecurityManager instance for security operations
        """
        self.event_bus = event_bus
        self.config = config
        self.security_manager = security_manager
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        
        # Default directories
        self.data_dir = os.path.join(self.root_dir, "data")
        self.cache_dir = os.path.join(self.root_dir, "cache")
        self.temp_dir = os.path.join(self.root_dir, "temp")
        self.backup_dir = os.path.join(self.root_dir, "backups")
        
        # Ensure critical directories exist
        self._initialize_directories()
        
        # File operation lock for thread safety
        self.file_lock = threading.RLock()
        
        # Track file operations for diagnostics
        self.operations_count = {
            "read": 0,
            "write": 0,
            "delete": 0,
            "backup": 0,
            "restore": 0,
            "errors": 0
        }
        
        # Subscribe to system events if event bus available
        if self.event_bus:
            self.register_event_handlers()
            
        logger.info("FileManager initialized successfully")
            
    def _initialize_directories(self):
        """Ensure all required directories exist."""
        try:
            for directory in [self.data_dir, self.cache_dir, self.temp_dir, self.backup_dir]:
                os.makedirs(directory, exist_ok=True)
                
            # Create subdirectories for better organization
            os.makedirs(os.path.join(self.data_dir, "configs"), exist_ok=True)
            os.makedirs(os.path.join(self.data_dir, "models"), exist_ok=True)
            os.makedirs(os.path.join(self.data_dir, "logs"), exist_ok=True)
            os.makedirs(os.path.join(self.backup_dir, "daily"), exist_ok=True)
            os.makedirs(os.path.join(self.backup_dir, "weekly"), exist_ok=True)
            
            logger.debug("All required directories initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize directories: {str(e)}")
            return False
            
    def register_event_handlers(self):
        """Register handlers for system events."""
        if self.event_bus:
            self.event_bus.subscribe_sync("system.file.request", self._handle_file_request)
            self.event_bus.subscribe_sync("system.file.backup", self.create_backup)
            self.event_bus.subscribe_sync("system.file.restore", self.restore_backup)
            self.event_bus.subscribe_sync("system.shutdown", self._handle_shutdown)
            logger.debug("FileManager event handlers registered")
            
    def _handle_file_request(self, event_data):
        """
        Handle file operation requests from other components.
        
        Args:
            event_data: Dictionary containing operation details
        """
        operation = event_data.get("operation")
        filepath = event_data.get("filepath")
        content = event_data.get("content", None)
        response_channel = event_data.get("response_channel", "system.file.response")
        
        result = {"success": False, "operation": operation, "filepath": filepath}
        
        if not filepath:
            result["error"] = "No filepath provided"
        elif operation == "read":
            content = self.read_file(filepath)
            if content is not None:
                result["success"] = True
                result["content"] = content
            else:
                result["error"] = "Failed to read file"
        elif operation == "write":
            if content is None:
                result["error"] = "No content provided for write operation"
            else:
                success = self.write_file(filepath, content)
                result["success"] = success
                if not success:
                    result["error"] = "Failed to write file"
        elif operation == "delete":
            success = self.delete_file(filepath)
            result["success"] = success
            if not success:
                result["error"] = "Failed to delete file"
        else:
            result["error"] = f"Unknown operation: {operation}"
            
        # Send response back on the response channel
        if self.event_bus:
            self.event_bus.publish(response_channel, result)
        
    def read_file(self, filepath: str, default=None, secure=True) -> Optional[Union[str, dict, list]]:
        """
        Read file contents safely with security validation.
        
        Args:
            filepath: Path to the file to read
            default: Default value to return if file doesn't exist
            secure: Whether to perform security validation
            
        Returns:
            File contents or default value if file doesn't exist
        """
        try:
            # Validate filepath for security if requested
            if secure and self.security_manager:
                if not self.security_manager.validate_file_access(filepath, "read"):
                    logger.warning(f"Security validation failed for reading {filepath}")
                    return default
            
            # Basic path validation
            if not os.path.exists(filepath):
                logger.debug(f"File not found: {filepath}")
                return default
            
            with self.file_lock:
                # Handle different file types
                if filepath.endswith(('.json', '.jsonl')):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                    
                elif filepath.endswith(('.yaml', '.yml')):
                    try:
                        import yaml
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = yaml.safe_load(f)
                    except ImportError:
                        logger.warning("YAML support not available, reading as text")
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                
                else:  # Default to text
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                
                self.operations_count["read"] += 1
                return content
                
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {str(e)}")
            self.operations_count["errors"] += 1
            return default
            
    def write_file(self, filepath: str, content: Any, backup=True, secure=True) -> bool:
        """
        Write content to a file safely with security validation.
        
        Args:
            filepath: Path to the file to write
            content: Content to write (string, dict, or list)
            backup: Whether to create a backup of existing file
            secure: Whether to perform security validation
            
        Returns:
            True if file was written successfully, False otherwise
        """
        try:
            # Validate filepath for security if requested
            if secure and self.security_manager:
                if not self.security_manager.validate_file_access(filepath, "write"):
                    logger.warning(f"Security validation failed for writing {filepath}")
                    return False
            
            # Create directory if it doesn't exist
            directory = os.path.dirname(filepath)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            # Create backup if requested and file exists
            if backup and os.path.exists(filepath):
                self._create_file_backup(filepath)
            
            with self.file_lock:
                # Handle different content types
                if isinstance(content, (dict, list)) and filepath.endswith('.json'):
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)
                
                elif isinstance(content, (dict, list)) and filepath.endswith(('.yaml', '.yml')):
                    try:
                        import yaml
                        with open(filepath, 'w', encoding='utf-8') as f:
                            yaml.dump(content, f, default_flow_style=False)
                    except ImportError:
                        logger.warning("YAML support not available, writing as JSON")
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(content, f, indent=2, ensure_ascii=False)
                
                else:  # Default to text
                    # Convert to string if not already
                    if not isinstance(content, str):
                        content = str(content)
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                
                self.operations_count["write"] += 1
                
                # Notify system about file change
                if self.event_bus:
                    self.event_bus.publish("system.file.changed", {
                        "filepath": filepath,
                        "operation": "write",
                        "timestamp": time.time()
                    })
                
                return True
                
        except Exception as e:
            logger.error(f"Error writing file {filepath}: {str(e)}")
            self.operations_count["errors"] += 1
            return False
            
    def delete_file(self, filepath: str, secure=True) -> bool:
        """
        Delete a file safely with security validation.
        
        Args:
            filepath: Path to the file to delete
            secure: Whether to perform security validation
            
        Returns:
            True if file was deleted successfully, False otherwise
        """
        try:
            # Validate filepath for security if requested
            if secure and self.security_manager:
                if not self.security_manager.validate_file_access(filepath, "delete"):
                    logger.warning(f"Security validation failed for deleting {filepath}")
                    return False
            
            # Check if file exists
            if not os.path.exists(filepath):
                logger.debug(f"File not found for deletion: {filepath}")
                return False
            
            # Create backup before deletion
            self._create_file_backup(filepath)
            
            with self.file_lock:
                # Delete file
                os.remove(filepath)
                self.operations_count["delete"] += 1
                
                # Notify system about file deletion
                if self.event_bus:
                    self.event_bus.publish("system.file.changed", {
                        "filepath": filepath,
                        "operation": "delete",
                        "timestamp": time.time()
                    })
                
                return True
                
        except Exception as e:
            logger.error(f"Error deleting file {filepath}: {str(e)}")
            self.operations_count["errors"] += 1
            return False
            
    def _create_file_backup(self, filepath: str) -> Optional[str]:
        """
        Create a backup of a file.
        
        Args:
            filepath: Path to the file to backup
            
        Returns:
            Path to the backup file or None if backup failed
        """
        try:
            if not os.path.exists(filepath):
                return None
                
            # Create backup directory if it doesn't exist
            backup_dir = os.path.join(self.backup_dir, "files")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Generate backup filename with timestamp
            filename = os.path.basename(filepath)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_filepath = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")
            
            # Copy file to backup location
            shutil.copy2(filepath, backup_filepath)
            logger.debug(f"Created backup of {filepath} at {backup_filepath}")
            
            # Cleanup old backups if there are too many
            self._cleanup_old_backups(filepath)
            
            return backup_filepath
            
        except Exception as e:
            logger.error(f"Error creating backup of {filepath}: {str(e)}")
            return None
            
    def _cleanup_old_backups(self, filepath: str, max_backups: int = 10):
        """
        Cleanup old backups of a file, keeping only the most recent ones.
        
        Args:
            filepath: Original file path
            max_backups: Maximum number of backups to keep
        """
        try:
            filename = os.path.basename(filepath)
            backup_dir = os.path.join(self.backup_dir, "files")
            
            # Find all backups for this file
            backups = []
            if os.path.exists(backup_dir):
                for backup_file in os.listdir(backup_dir):
                    if backup_file.startswith(filename + ".") and backup_file.endswith(".bak"):
                        backup_path = os.path.join(backup_dir, backup_file)
                        backups.append((backup_path, os.path.getmtime(backup_path)))
            
            # Sort by modification time (newest first)
            backups.sort(key=lambda x: x[1], reverse=True)
            
            # Remove old backups
            if len(backups) > max_backups:
                for backup_path, _ in backups[max_backups:]:
                    os.remove(backup_path)
                    logger.debug(f"Removed old backup: {backup_path}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old backups for {filepath}: {str(e)}")
            
    def create_backup(self, event_data=None):
        """
        Create a full system backup.
        
        Args:
            event_data: Optional event data containing backup parameters
            
        Returns:
            Path to the backup archive or None if backup failed
        """
        try:
            # Determine backup type and locations
            backup_type = event_data.get("type", "daily") if event_data else "daily"
            backup_dir = os.path.join(self.backup_dir, backup_type)
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create timestamp for backup name
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_name = f"kingdom_backup_{backup_type}_{timestamp}"
            backup_path = os.path.join(backup_dir, backup_name)
            
            # Determine what to backup
            dirs_to_backup = event_data.get("directories", ["data", "config"]) if event_data else ["data", "config"]
            
            # Perform backup for each directory
            backup_paths = []
            for dir_name in dirs_to_backup:
                dir_path = os.path.join(self.root_dir, dir_name)
                if os.path.exists(dir_path):
                    # Create archive
                    archive_path = f"{backup_path}_{dir_name}.zip"
                    shutil.make_archive(
                        os.path.splitext(archive_path)[0],  # Remove .zip extension
                        'zip',
                        self.root_dir,  # Base directory
                        dir_name  # Directory to backup
                    )
                    backup_paths.append(archive_path)
            
            # Notify system about backup completion
            if self.event_bus:
                self.event_bus.publish("system.backup.complete", {
                    "backup_type": backup_type,
                    "backup_paths": backup_paths,
                    "timestamp": time.time()
                })
            
            self.operations_count["backup"] += 1
            logger.info(f"Created {backup_type} backup at {', '.join(backup_paths)}")
            
            # Cleanup old backups
            self._cleanup_old_system_backups(backup_type)
            
            return backup_paths
            
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            self.operations_count["errors"] += 1
            
            # Notify system about backup failure
            if self.event_bus:
                self.event_bus.publish("system.backup.error", {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "timestamp": time.time()
                })
            
            return None
            
    def _cleanup_old_system_backups(self, backup_type: str):
        """
        Cleanup old system backups, keeping only the most recent ones.
        
        Args:
            backup_type: Type of backup to clean up (daily, weekly, etc.)
        """
        try:
            # Determine max backups to keep based on type
            max_backups = {
                "daily": 7,    # Keep the last 7 daily backups
                "weekly": 4,   # Keep the last 4 weekly backups
                "monthly": 12,  # Keep the last 12 monthly backups
                "manual": 10   # Keep the last 10 manual backups
            }.get(backup_type, 5)  # Default to 5 for unknown types
            
            backup_dir = os.path.join(self.backup_dir, backup_type)
            if not os.path.exists(backup_dir):
                return
                
            # Group backup files by their base name
            backup_groups = {}
            for file in os.listdir(backup_dir):
                if file.startswith("kingdom_backup_") and file.endswith(".zip"):
                    # Extract timestamp part from filename
                    parts = file.split('_')
                    if len(parts) >= 4:
                        timestamp = parts[3].split('.')[0]  # Remove extension
                        base_name = '_'.join(parts[:-1])  # Group by everything except timestamp
                        
                        if base_name not in backup_groups:
                            backup_groups[base_name] = []
                        
                        backup_groups[base_name].append({
                            "filepath": os.path.join(backup_dir, file),
                            "timestamp": timestamp,
                            "mtime": os.path.getmtime(os.path.join(backup_dir, file))
                        })
            
            # For each group, keep only the most recent backups
            for base_name, backups in backup_groups.items():
                # Sort by modification time (newest first)
                backups.sort(key=lambda x: x["mtime"], reverse=True)
                
                # Remove old backups
                if len(backups) > max_backups:
                    for backup in backups[max_backups:]:
                        os.remove(backup["filepath"])
                        logger.debug(f"Removed old backup: {backup['filepath']}")
                        
        except Exception as e:
            logger.error(f"Error cleaning up old {backup_type} backups: {str(e)}")
            
    def restore_backup(self, event_data: dict) -> bool:
        """
        Restore a system backup.
        
        Args:
            event_data: Event data containing backup information
            
        Returns:
            True if backup was restored successfully, False otherwise
        """
        try:
            backup_path = event_data.get("backup_path")
            if not backup_path or not os.path.exists(backup_path):
                logger.error(f"Backup path not found: {backup_path}")
                return False
                
            # Create temporary directory for extraction
            temp_extract_dir = tempfile.mkdtemp(dir=self.temp_dir)
            
            # Extract backup
            shutil.unpack_archive(backup_path, temp_extract_dir)
            
            # Determine target directory based on backup filename
            backup_filename = os.path.basename(backup_path)
            target_dir = None
            
            # Parse backup filename to determine target directory
            parts = backup_filename.split('_')
            if len(parts) >= 4:
                dir_part = parts[-1].split('.')[0]  # Remove extension
                target_dir = os.path.join(self.root_dir, dir_part)
            
            if not target_dir:
                logger.error(f"Could not determine target directory from backup filename: {backup_filename}")
                shutil.rmtree(temp_extract_dir)
                return False
                
            # Create backup of current data before restoring
            current_backup_path = self._create_file_backup(target_dir) if os.path.exists(target_dir) else None
            
            # Copy files from temporary directory to target
            source_dir = temp_extract_dir
            # If the backup has subdirectories matching the backup type, adjust source_dir
            if not os.path.exists(os.path.join(source_dir, os.path.basename(target_dir))):
                for item in os.listdir(source_dir):
                    item_path = os.path.join(source_dir, item)
                    if os.path.isdir(item_path) and item == os.path.basename(target_dir):
                        source_dir = item_path
                        break
            
            # Clear target directory and restore from backup
            if os.path.exists(target_dir):
                # Only remove contents, not the directory itself
                for item in os.listdir(target_dir):
                    item_path = os.path.join(target_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
            else:
                os.makedirs(target_dir, exist_ok=True)
            
            # Copy from extract directory to target
            for item in os.listdir(source_dir):
                s = os.path.join(source_dir, item)
                d = os.path.join(target_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            
            # Cleanup temporary directory
            shutil.rmtree(temp_extract_dir)
            
            # Notify system about restore completion
            if self.event_bus:
                self.event_bus.publish("system.restore.complete", {
                    "backup_path": backup_path,
                    "target_dir": target_dir,
                    "timestamp": time.time()
                })
            
            self.operations_count["restore"] += 1
            logger.info(f"Restored backup from {backup_path} to {target_dir}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error restoring backup: {str(e)}")
            self.operations_count["errors"] += 1
            
            # Notify system about restore failure
            if self.event_bus:
                self.event_bus.publish("system.restore.error", {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "timestamp": time.time()
                })
            
            return False
            
    def get_temp_file(self, prefix="kingdom_", suffix=".tmp") -> str:
        """
        Get a temporary file path within the Kingdom AI temp directory.
        
        Args:
            prefix: Prefix for the temporary file
            suffix: Suffix for the temporary file
            
        Returns:
            Path to the temporary file
        """
        os.makedirs(self.temp_dir, exist_ok=True)
        return os.path.join(
            self.temp_dir,
            f"{prefix}{int(time.time())}_{os.urandom(4).hex()}{suffix}"
        )
        
    def cleanup_temp_files(self, max_age_hours=24):
        """
        Cleanup temporary files older than the specified age.
        
        Args:
            max_age_hours: Maximum age of temporary files in hours
        """
        try:
            if not os.path.exists(self.temp_dir):
                return
                
            cutoff_time = time.time() - (max_age_hours * 3600)
            
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)
                
                # Skip directories and non-temporary files
                if os.path.isdir(filepath) or not filename.startswith("kingdom_"):
                    continue
                    
                # Check file modification time
                if os.path.getmtime(filepath) < cutoff_time:
                    try:
                        os.remove(filepath)
                        logger.debug(f"Removed old temporary file: {filepath}")
                    except Exception as e:
                        logger.error(f"Error removing temporary file {filepath}: {str(e)}")
                        
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}")
            
    def _handle_shutdown(self, event_data=None):
        """Handle system shutdown event."""
        logger.info("FileManager shutting down, cleaning up resources...")
        self.cleanup_temp_files(max_age_hours=1)  # Aggressive cleanup on shutdown
        
    def get_status(self) -> dict:
        """
        Get status information about the FileManager.
        
        Returns:
            Dictionary with status information
        """
        return {
            "component": "FileManager",
            "status": "operational",
            "operations": self.operations_count,
            "directories": {
                "data": os.path.exists(self.data_dir),
                "cache": os.path.exists(self.cache_dir),
                "temp": os.path.exists(self.temp_dir),
                "backup": os.path.exists(self.backup_dir)
            }
        }
        
    def __del__(self):
        """Cleanup resources when instance is deleted."""
        try:
            # Unsubscribe from events if event bus is available
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.unsubscribe("system.file.request", self._handle_file_request)
                self.event_bus.unsubscribe("system.file.backup", self.create_backup)
                self.event_bus.unsubscribe("system.file.restore", self.restore_backup)
                self.event_bus.unsubscribe("system.shutdown", self._handle_shutdown)
        except Exception as e:
            # Cannot use logger here as it might be None during interpreter shutdown
            print(f"Error cleaning up FileManager: {str(e)}")
