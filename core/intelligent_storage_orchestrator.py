#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOTA 2026 - Intelligent Storage Orchestrator for Kingdom AI

AI-powered storage management that:
- Monitors C: drive space in real-time
- Automatically places data on external drives (D:, E:)
- Uses Ollama brain to decide optimal data placement
- Moves old/cold data to external storage when C: gets low
- Ensures Redis, logs, mining data, AI cache never fill C: drive
"""

import os
import sys
import json
import shutil
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("KingdomAI.IntelligentStorage")


@dataclass
class StorageDevice:
    """Represents a storage device"""
    name: str
    drive_letter: str  # Windows: "C:", "D:"
    mount_point: str   # WSL: "/mnt/c", "/mnt/d"
    total_gb: float
    free_gb: float
    used_gb: float
    is_system: bool = False
    is_external: bool = False
    priority: int = 0  # Higher = prefer for new data


@dataclass
class DataCategory:
    """Category of data with storage rules"""
    name: str
    current_path: str
    preferred_device: str  # "system", "external_primary", "external_secondary"
    size_mb: float = 0.0
    can_move: bool = True
    is_critical: bool = False


class IntelligentStorageOrchestrator:
    """
    AI-powered storage orchestrator that manages data placement
    across multiple drives to prevent C: drive from filling up.
    """
    
    def __init__(self, event_bus=None, ollama_brain=None):
        self.event_bus = event_bus
        self.ollama_brain = ollama_brain
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread = None
        
        # Detect environment
        self.in_wsl = self._detect_wsl()
        
        # Storage devices
        self.devices: Dict[str, StorageDevice] = {}
        self._scan_storage_devices()
        
        # Data categories to manage
        self.data_categories: Dict[str, DataCategory] = {}
        self._initialize_data_categories()
        
        # Configuration
        self.min_free_space_gb = 20  # Trigger cleanup when C: has < 20GB free
        self.target_free_space_gb = 50  # Try to maintain 50GB free on C:
        self.check_interval = 300  # Check every 5 minutes
        
        logger.info("🧠 Intelligent Storage Orchestrator initialized")
        logger.info(f"   Detected {len(self.devices)} storage devices")
        logger.info(f"   Managing {len(self.data_categories)} data categories")
    
    def _detect_wsl(self) -> bool:
        """Detect if running in WSL"""
        try:
            if os.path.exists('/proc/version'):
                with open('/proc/version', 'r') as f:
                    content = f.read().lower()
                    return 'microsoft' in content or 'wsl' in content
        except Exception:
            pass
        return False
    
    def _scan_storage_devices(self) -> None:
        """Scan and register all available storage devices"""
        if self.in_wsl:
            # WSL: Check /mnt/* for Windows drives
            self._scan_wsl_mounts()
        else:
            # Native Windows/Linux
            self._scan_native_drives()
    
    def _scan_wsl_mounts(self) -> None:
        """Scan WSL mount points for Windows drives"""
        import subprocess
        
        # Get disk usage for each /mnt/* mount
        for drive_letter in ['c', 'd', 'e', 'f']:
            mount_point = f"/mnt/{drive_letter}"
            if not os.path.exists(mount_point):
                continue
            
            try:
                # Get disk usage
                result = subprocess.run(
                    ['df', '-BG', mount_point],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) >= 2:
                        parts = lines[1].split()
                        if len(parts) >= 4:
                            total_str = parts[1].rstrip('G')
                            used_str = parts[2].rstrip('G')
                            free_str = parts[3].rstrip('G')
                            
                            try:
                                total_gb = float(total_str)
                                used_gb = float(used_str)
                                free_gb = float(free_str)
                                
                                device = StorageDevice(
                                    name=f"Drive {drive_letter.upper()}:",
                                    drive_letter=f"{drive_letter.upper()}:",
                                    mount_point=mount_point,
                                    total_gb=total_gb,
                                    free_gb=free_gb,
                                    used_gb=used_gb,
                                    is_system=(drive_letter == 'c'),
                                    is_external=(drive_letter != 'c'),
                                    priority=0 if drive_letter == 'c' else (100 if drive_letter == 'd' else 50)
                                )
                                
                                self.devices[drive_letter] = device
                                logger.info(f"   📀 {device.name}: {device.free_gb:.1f}GB free / {device.total_gb:.1f}GB total")
                            except ValueError:
                                pass
            except Exception as e:
                logger.debug(f"Failed to scan {mount_point}: {e}")
    
    def _scan_native_drives(self) -> None:
        """Scan native Windows/Linux drives"""
        try:
            import psutil
            
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    
                    drive_letter = partition.device
                    if sys.platform == 'win32':
                        drive_letter = partition.device.rstrip('\\')
                    
                    is_system = (partition.mountpoint == '/' or 
                                partition.mountpoint.startswith('C:') or
                                partition.device.startswith('/dev/sda'))
                    
                    device = StorageDevice(
                        name=partition.device,
                        drive_letter=drive_letter,
                        mount_point=partition.mountpoint,
                        total_gb=usage.total / (1024**3),
                        free_gb=usage.free / (1024**3),
                        used_gb=usage.used / (1024**3),
                        is_system=is_system,
                        is_external=not is_system,
                        priority=0 if is_system else 100
                    )
                    
                    self.devices[drive_letter] = device
                    logger.info(f"   📀 {device.name}: {device.free_gb:.1f}GB free / {device.total_gb:.1f}GB total")
                except Exception as e:
                    logger.debug(f"Failed to get usage for {partition.device}: {e}")
        except ImportError:
            logger.warning("psutil not available - limited storage detection")
    
    def _initialize_data_categories(self) -> None:
        """Initialize data categories that Kingdom AI uses"""
        project_root = Path(__file__).parent.parent
        
        # Define data categories with their current locations
        categories = {
            'redis_data': DataCategory(
                name='Redis RDB/AOF Data',
                current_path=str(project_root / 'data' / 'redis'),
                preferred_device='external_primary',
                can_move=True,
                is_critical=True
            ),
            'redis_logs': DataCategory(
                name='Redis Logs',
                current_path=str(project_root / 'logs' / 'redis'),
                preferred_device='external_primary',
                can_move=True,
                is_critical=False
            ),
            'mining_data': DataCategory(
                name='Mining Data',
                current_path=str(project_root / 'data' / 'mining'),
                preferred_device='external_primary',
                can_move=True,
                is_critical=True
            ),
            'wallet_backups': DataCategory(
                name='Wallet Backups',
                current_path=str(project_root / 'data' / 'wallets'),
                preferred_device='external_primary',
                can_move=True,
                is_critical=True
            ),
            'ai_cache': DataCategory(
                name='AI Model Cache',
                current_path=str(project_root / 'data' / 'ai_cache'),
                preferred_device='external_primary',
                can_move=True,
                is_critical=False
            ),
            'logs': DataCategory(
                name='System Logs',
                current_path=str(project_root / 'logs'),
                preferred_device='external_secondary',
                can_move=True,
                is_critical=False
            ),
            'exports': DataCategory(
                name='Exports',
                current_path=str(project_root / 'exports'),
                preferred_device='external_primary',
                can_move=True,
                is_critical=False
            ),
            'scraped_content': DataCategory(
                name='Scraped Web Content',
                current_path=str(project_root / 'data' / 'scraped_content'),
                preferred_device='external_secondary',
                can_move=True,
                is_critical=False
            ),
            'learned_knowledge': DataCategory(
                name='Learned Knowledge',
                current_path=str(project_root / 'data' / 'learned_knowledge'),
                preferred_device='external_primary',
                can_move=True,
                is_critical=True
            )
        }
        
        self.data_categories = categories
        
        # Calculate current sizes
        for cat_id, category in self.data_categories.items():
            category.size_mb = self._get_directory_size_mb(category.current_path)
    
    def _get_directory_size_mb(self, path: str) -> float:
        """Get size of directory in MB"""
        try:
            total_size = 0
            path_obj = Path(path)
            if path_obj.exists():
                for item in path_obj.rglob('*'):
                    if item.is_file():
                        try:
                            total_size += item.stat().st_size
                        except Exception:
                            pass
            return total_size / (1024 * 1024)
        except Exception:
            return 0.0
    
    def get_optimal_storage_plan(self) -> Dict[str, Any]:
        """
        Use Ollama brain to determine optimal storage configuration.
        Returns a plan for where each data category should be stored.
        """
        # Prepare context for Ollama
        context = {
            'devices': {
                name: {
                    'free_gb': dev.free_gb,
                    'total_gb': dev.total_gb,
                    'is_system': dev.is_system,
                    'is_external': dev.is_external
                }
                for name, dev in self.devices.items()
            },
            'data_categories': {
                name: {
                    'size_mb': cat.size_mb,
                    'current_path': cat.current_path,
                    'is_critical': cat.is_critical,
                    'preferred_device': cat.preferred_device
                }
                for name, cat in self.data_categories.items()
            },
            'constraints': {
                'min_free_space_gb': self.min_free_space_gb,
                'target_free_space_gb': self.target_free_space_gb
            }
        }
        
        # Get system drive status
        system_drive = self.devices.get('c')
        if system_drive and system_drive.free_gb < self.min_free_space_gb:
            urgency = "CRITICAL"
        elif system_drive and system_drive.free_gb < self.target_free_space_gb:
            urgency = "HIGH"
        else:
            urgency = "NORMAL"
        
        # Ask Ollama brain for optimal plan (native Linux paths)
        data_root = os.environ.get("KINGDOM_DATA_ROOT") or str(Path.home() / ".kingdom_ai")
        if self.ollama_brain:
            prompt = f"""You are Kingdom AI's storage orchestrator on native Linux.
Analyze this storage situation and provide an optimal data placement plan.

Current Storage Status:
{json.dumps(context, indent=2)}

Urgency Level: {urgency}

Task: Create a storage plan that:
1. Moves Redis data onto the configured data root ({data_root}) immediately
   to fix the MISCONF error.
2. Places mining data and wallet backups under the same data root.
3. Keeps only essential runtime data inside the repo working tree.
4. Maintains at least {self.target_free_space_gb}GB free on the root filesystem.

Respond with JSON format:
{{
  "moves": [
    {{"category": "redis_data", "from": "current_path", "to": "{data_root}/redis/data", "reason": "Fix Redis MISCONF error"}},
    ...
  ],
  "priority": "HIGH|NORMAL|LOW",
  "estimated_space_freed_gb": 0.0
}}"""
            
            try:
                response = self.ollama_brain.generate(prompt)
                # Parse JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    plan = json.loads(json_match.group())
                    return plan
            except Exception as e:
                logger.warning(f"Ollama brain planning failed: {e}")
        
        # Fallback: Create basic plan without AI
        return self._create_basic_storage_plan()
    
    def _create_basic_storage_plan(self) -> Dict[str, Any]:
        """Create basic storage plan without AI assistance"""
        moves = []
        
        # Get external drive paths
        external_primary = self.devices.get('d')
        external_secondary = self.devices.get('e')
        
        if not external_primary:
            logger.error("No external drive D: found - cannot create storage plan")
            return {'moves': [], 'priority': 'CRITICAL', 'estimated_space_freed_gb': 0.0}
        
        # Map preferred devices to actual paths
        device_map = {
            'external_primary': external_primary.mount_point if self.in_wsl else external_primary.drive_letter,
            'external_secondary': external_secondary.mount_point if external_secondary and self.in_wsl else (external_secondary.drive_letter if external_secondary else None)
        }
        
        total_freed = 0.0
        
        for cat_id, category in self.data_categories.items():
            target_device = device_map.get(category.preferred_device)
            if target_device and category.can_move:
                # Create new path on external drive
                if self.in_wsl:
                    new_path = f"{target_device}/KingdomAI/{cat_id}"
                else:
                    new_path = f"{target_device}\\KingdomAI\\{cat_id}"
                
                moves.append({
                    'category': cat_id,
                    'from': category.current_path,
                    'to': new_path,
                    'size_mb': category.size_mb,
                    'reason': f'Move {category.name} to external storage'
                })
                
                total_freed += category.size_mb / 1024  # Convert to GB
        
        return {
            'moves': moves,
            'priority': 'HIGH',
            'estimated_space_freed_gb': round(total_freed, 2)
        }
    
    def execute_storage_plan(self, plan: Dict[str, Any]) -> bool:
        """Execute the storage plan by moving data"""
        logger.info(f"🚀 Executing storage plan: {len(plan.get('moves', []))} moves")
        logger.info(f"   Estimated space to free: {plan.get('estimated_space_freed_gb', 0)}GB")
        
        success_count = 0
        fail_count = 0
        
        for move in plan.get('moves', []):
            category = move['category']
            from_path = move['from']
            to_path = move['to']
            reason = move.get('reason', 'Storage optimization')
            
            logger.info(f"   📦 Moving {category}: {from_path} → {to_path}")
            logger.info(f"      Reason: {reason}")
            
            if self._move_data(from_path, to_path, category):
                success_count += 1
                logger.info(f"      ✅ Success")
                
                # Update category path
                if category in self.data_categories:
                    self.data_categories[category].current_path = to_path
            else:
                fail_count += 1
                logger.error(f"      ❌ Failed")
        
        logger.info(f"✅ Storage plan executed: {success_count} successful, {fail_count} failed")
        
        # Publish event
        if self.event_bus:
            self.event_bus.publish('storage.plan.executed', {
                'success_count': success_count,
                'fail_count': fail_count,
                'plan': plan
            })
        
        return fail_count == 0
    
    def _move_data(self, from_path: str, to_path: str, category: str) -> bool:
        """Move data from one location to another (handles cross-device moves)"""
        try:
            from_path_obj = Path(from_path)
            to_path_obj = Path(to_path)
            
            # If source doesn't exist, just create target
            if not from_path_obj.exists():
                to_path_obj.mkdir(parents=True, exist_ok=True)
                logger.info(f"      Created new directory: {to_path}")
                return True
            
            # Check if source is already a symlink - don't move symlinks
            if from_path_obj.is_symlink():
                logger.info(f"      Source is symlink - skipping: {from_path}")
                return True
            
            # Check if source and dest are the same (resolve symlinks)
            try:
                if from_path_obj.resolve() == to_path_obj.resolve():
                    logger.info(f"      Source and dest are same - skipping: {from_path}")
                    return True
            except Exception:
                pass
            
            # Create target directory
            to_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Move data - handle cross-device moves properly
            if from_path_obj.is_dir():
                # For directories: copy then remove (handles cross-device)
                try:
                    # Use copytree for cross-device compatibility
                    shutil.copytree(str(from_path_obj), str(to_path_obj), dirs_exist_ok=True)
                    logger.info(f"      Copied directory to: {to_path}")
                    
                    # Remove original after successful copy (only if not a symlink)
                    if not from_path_obj.is_symlink():
                        shutil.rmtree(str(from_path_obj))
                        logger.info(f"      Removed original: {from_path}")
                    
                    # Create symlink at old location for compatibility
                    try:
                        if self.in_wsl and not from_path_obj.exists():
                            os.symlink(to_path, from_path)
                            logger.info(f"      Created symlink: {from_path} → {to_path}")
                    except Exception as e:
                        logger.warning(f"      Could not create symlink: {e}")
                except Exception as e:
                    # If copy failed, don't remove original
                    logger.error(f"      Failed to copy directory: {e}")
                    return False
            else:
                # For files: copy then remove
                try:
                    shutil.copy2(str(from_path_obj), str(to_path_obj))
                    os.remove(str(from_path_obj))
                except Exception as e:
                    logger.error(f"      Failed to copy file: {e}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Failed to move {from_path} to {to_path}: {e}")
            return False
    
    def start_monitoring(self) -> None:
        """Start monitoring storage and auto-managing data placement"""
        if self._monitoring:
            logger.warning("Storage monitoring already running")
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("🔍 Storage monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop storage monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("⏹️ Storage monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._monitoring:
            try:
                # Re-scan devices
                self._scan_storage_devices()
                
                # Check if action needed
                system_drive = self.devices.get('c')
                if system_drive and system_drive.free_gb < self.min_free_space_gb:
                    logger.warning(f"⚠️ C: drive low on space: {system_drive.free_gb:.1f}GB free")
                    logger.info("🧠 Asking Ollama brain for storage optimization plan...")
                    
                    # Get and execute plan
                    plan = self.get_optimal_storage_plan()
                    if plan.get('moves'):
                        self.execute_storage_plan(plan)
                
                # Sleep until next check
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in storage monitoring loop: {e}")
                time.sleep(60)  # Wait a minute before retrying
    
    def get_storage_status(self) -> Dict[str, Any]:
        """Get current storage status"""
        return {
            'devices': {
                name: {
                    'free_gb': dev.free_gb,
                    'total_gb': dev.total_gb,
                    'used_gb': dev.used_gb,
                    'percent_used': round((dev.used_gb / dev.total_gb) * 100, 1) if dev.total_gb > 0 else 0,
                    'is_system': dev.is_system,
                    'is_external': dev.is_external
                }
                for name, dev in self.devices.items()
            },
            'data_categories': {
                name: {
                    'size_mb': cat.size_mb,
                    'current_path': cat.current_path,
                    'preferred_device': cat.preferred_device,
                    'is_critical': cat.is_critical
                }
                for name, cat in self.data_categories.items()
            },
            'monitoring': self._monitoring
        }


# Singleton instance
_storage_orchestrator = None

def get_storage_orchestrator(event_bus=None, ollama_brain=None) -> IntelligentStorageOrchestrator:
    """Get singleton storage orchestrator instance"""
    global _storage_orchestrator
    if _storage_orchestrator is None:
        _storage_orchestrator = IntelligentStorageOrchestrator(event_bus, ollama_brain)
    return _storage_orchestrator


__all__ = ['IntelligentStorageOrchestrator', 'get_storage_orchestrator', 'StorageDevice', 'DataCategory']
