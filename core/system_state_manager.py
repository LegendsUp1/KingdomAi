"""
System State Manager - 2025 SOTA
Automatic state persistence and recovery to prevent data loss on crashes.
Implements auto-save every 5 minutes and crash recovery.
"""

import logging
import json
import pickle
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class SystemStateManager(QObject):
    """
    Manages system state persistence with automatic saving.
    Prevents data loss by saving state every 5 minutes and on critical events.
    """
    
    state_saved = pyqtSignal(str)  # Emitted when state is saved (filepath)
    state_loaded = pyqtSignal(str)  # Emitted when state is loaded (filepath)
    
    _instance: Optional['SystemStateManager'] = None
    
    @classmethod
    def get_instance(cls) -> 'SystemStateManager':
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = SystemStateManager()
        return cls._instance
    
    def __init__(self):
        super().__init__()
        
        # State storage
        self._state: Dict[str, Any] = {}
        self._state_providers: Dict[str, Callable[[], Dict[str, Any]]] = {}
        
        # Persistence settings
        self._state_dir = Path("data/state")
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._state_dir / "system_state.json"
        self._backup_file = self._state_dir / "system_state.backup.json"
        
        # Auto-save timer (every 5 minutes)
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._auto_save)
        self._auto_save_interval = 5 * 60 * 1000  # 5 minutes in milliseconds
        
        # Statistics
        self._stats = {
            'saves_total': 0,
            'saves_auto': 0,
            'saves_manual': 0,
            'last_save_time': None,
            'last_save_duration_ms': 0
        }
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info(f"SystemStateManager initialized - State dir: {self._state_dir}")
    
    def start_auto_save(self) -> None:
        """Start automatic state saving."""
        self._auto_save_timer.start(self._auto_save_interval)
        logger.info(f"Auto-save started - interval: {self._auto_save_interval // 1000}s")
    
    def stop_auto_save(self) -> None:
        """Stop automatic state saving."""
        if self._auto_save_timer.isActive():
            self._auto_save_timer.stop()
            logger.info("Auto-save stopped")
    
    def register_state_provider(self, component_name: str, provider: Callable[[], Dict[str, Any]]) -> None:
        """
        Register a component that provides state data.
        
        Args:
            component_name: Unique name for the component
            provider: Callable that returns a dict of state data
        """
        with self._lock:
            self._state_providers[component_name] = provider
            logger.debug(f"Registered state provider: {component_name}")
    
    def unregister_state_provider(self, component_name: str) -> None:
        """Unregister a state provider."""
        with self._lock:
            if component_name in self._state_providers:
                del self._state_providers[component_name]
                logger.debug(f"Unregistered state provider: {component_name}")
    
    def set_state(self, key: str, value: Any) -> None:
        """Set a state value."""
        with self._lock:
            self._state[key] = value
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        with self._lock:
            return self._state.get(key, default)
    
    def _collect_state(self) -> Dict[str, Any]:
        """Collect state from all registered providers."""
        state = {
            'timestamp': datetime.now().isoformat(),
            'version': '1.0',
            'components': {}
        }
        
        # Add manual state
        state['manual'] = self._state.copy()
        
        # Collect from providers
        for component_name, provider in self._state_providers.items():
            try:
                component_state = provider()
                if component_state:
                    state['components'][component_name] = component_state
            except Exception as e:
                logger.warning(f"Failed to collect state from {component_name}: {e}")
        
        return state
    
    def save_state(self, manual: bool = False) -> bool:
        """
        Save current system state to disk.
        
        Args:
            manual: Whether this is a manual save (vs auto-save)
            
        Returns:
            bool: True if save successful
        """
        start_time = time.time()
        
        try:
            with self._lock:
                # Collect all state
                state = self._collect_state()
                
                # Backup existing state file
                if self._state_file.exists():
                    try:
                        import shutil
                        shutil.copy2(self._state_file, self._backup_file)
                    except Exception as e:
                        logger.warning(f"Failed to create backup: {e}")
                
                # Save to temp file first (atomic write)
                temp_file = self._state_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(state, f, indent=2, default=str)
                
                # Atomic rename
                temp_file.replace(self._state_file)
                
                # Update statistics
                duration_ms = int((time.time() - start_time) * 1000)
                self._stats['saves_total'] += 1
                if manual:
                    self._stats['saves_manual'] += 1
                else:
                    self._stats['saves_auto'] += 1
                self._stats['last_save_time'] = datetime.now().isoformat()
                self._stats['last_save_duration_ms'] = duration_ms
                
                logger.info(f"✅ State saved ({duration_ms}ms) - Components: {len(state['components'])}")
                self.state_saved.emit(str(self._state_file))
                return True
                
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def load_state(self) -> bool:
        """
        Load system state from disk.
        
        Returns:
            bool: True if load successful
        """
        try:
            if not self._state_file.exists():
                logger.info("No saved state found")
                return False
            
            with self._lock:
                with open(self._state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                # Restore manual state
                if 'manual' in state:
                    self._state = state['manual']
                
                # Components will load their own state via get_component_state()
                
                logger.info(f"✅ State loaded - Timestamp: {state.get('timestamp', 'unknown')}")
                self.state_loaded.emit(str(self._state_file))
                return True
                
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            
            # Try backup file
            if self._backup_file.exists():
                logger.info("Attempting to load from backup...")
                try:
                    with open(self._backup_file, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                    if 'manual' in state:
                        self._state = state['manual']
                    logger.info("✅ State loaded from backup")
                    return True
                except Exception as e2:
                    logger.error(f"Failed to load backup: {e2}")
            
            return False
    
    def get_component_state(self, component_name: str) -> Optional[Dict[str, Any]]:
        """
        Get saved state for a specific component.
        
        Args:
            component_name: Name of the component
            
        Returns:
            Dict of component state or None if not found
        """
        try:
            if not self._state_file.exists():
                return None
            
            with open(self._state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            return state.get('components', {}).get(component_name)
            
        except Exception as e:
            logger.warning(f"Failed to get component state for {component_name}: {e}")
            return None
    
    def _auto_save(self) -> None:
        """Auto-save timer callback."""
        logger.debug("Auto-save triggered")
        self.save_state(manual=False)
    
    def shutdown(self) -> None:
        """Shutdown the state manager and perform final save."""
        logger.info("SystemStateManager shutting down...")
        
        # Stop auto-save
        self.stop_auto_save()
        
        # Final save
        logger.info("Performing final state save...")
        self.save_state(manual=True)
        
        logger.info("✅ SystemStateManager shutdown complete")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get state manager statistics."""
        return self._stats.copy()


# Convenience functions
def get_state_manager() -> SystemStateManager:
    """Get the global state manager instance."""
    return SystemStateManager.get_instance()


def save_system_state() -> bool:
    """Save current system state."""
    return get_state_manager().save_state(manual=True)


def load_system_state() -> bool:
    """Load system state from disk."""
    return get_state_manager().load_state()


def register_state_provider(component_name: str, provider: Callable[[], Dict[str, Any]]) -> None:
    """Register a component state provider."""
    get_state_manager().register_state_provider(component_name, provider)
