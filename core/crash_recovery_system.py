"""
Crash Recovery System for Kingdom AI - SOTA 2026

Provides automatic crash recovery and session persistence for 24/7 operation.
"""

import os
import json
import time
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CrashRecoverySystem:
    """System for crash recovery and session persistence."""
    
    def __init__(self, recovery_dir: str = "data/recovery"):
        """Initialize crash recovery system.
        
        Args:
            recovery_dir: Directory for recovery snapshots
        """
        self.recovery_dir = recovery_dir
        self.session_id = str(uuid.uuid4())[:8]
        self.start_time = datetime.now()
        self.snapshots = {}
        self.event_bus = None
        
        # Create recovery directory
        os.makedirs(recovery_dir, exist_ok=True)
        
        logger.info(f"Crash Recovery System initialized - Session: {self.session_id}")
    
    def set_event_bus(self, event_bus):
        """Set event bus for publishing recovery events."""
        self.event_bus = event_bus
    
    def save_snapshot(self, component_name: str, state: Dict[str, Any]) -> bool:
        """Save a component state snapshot.
        
        Args:
            component_name: Name of component
            state: Component state to save
            
        Returns:
            True if successful
        """
        try:
            snapshot = {
                "component": component_name,
                "session_id": self.session_id,
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat(),
                "state": state
            }
            
            # Save to memory
            self.snapshots[component_name] = snapshot
            
            # Save to disk
            snapshot_file = os.path.join(
                self.recovery_dir, 
                f"{component_name}_{self.session_id}.json"
            )
            with open(snapshot_file, 'w') as f:
                json.dump(snapshot, f, indent=2, default=str)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save snapshot for {component_name}: {e}")
            return False
    
    def load_snapshot(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Load the latest snapshot for a component.
        
        Args:
            component_name: Name of component
            
        Returns:
            Component state or None
        """
        try:
            # Try memory first
            if component_name in self.snapshots:
                return self.snapshots[component_name].get("state")
            
            # Try disk - find latest snapshot file
            pattern = f"{component_name}_"
            snapshot_files = [
                f for f in os.listdir(self.recovery_dir) 
                if f.startswith(pattern) and f.endswith('.json')
            ]
            
            if not snapshot_files:
                return None
            
            # Get most recent
            latest_file = max(
                snapshot_files,
                key=lambda f: os.path.getmtime(os.path.join(self.recovery_dir, f))
            )
            
            with open(os.path.join(self.recovery_dir, latest_file), 'r') as f:
                snapshot = json.load(f)
                return snapshot.get("state")
                
        except Exception as e:
            logger.error(f"Failed to load snapshot for {component_name}: {e}")
            return None
    
    def cleanup_old_snapshots(self, max_age_hours: int = 24):
        """Remove snapshots older than max_age_hours.
        
        Args:
            max_age_hours: Maximum age in hours
        """
        try:
            cutoff_time = time.time() - (max_age_hours * 3600)
            
            for filename in os.listdir(self.recovery_dir):
                filepath = os.path.join(self.recovery_dir, filename)
                if os.path.isfile(filepath):
                    if os.path.getmtime(filepath) < cutoff_time:
                        os.remove(filepath)
                        logger.debug(f"Removed old snapshot: {filename}")
        except Exception as e:
            logger.error(f"Failed to cleanup old snapshots: {e}")
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "snapshot_count": len(self.snapshots),
            "recovery_dir": self.recovery_dir
        }


# Global instance
_crash_recovery_system: Optional[CrashRecoverySystem] = None


def initialize_crash_recovery(recovery_dir: str = "data/recovery") -> CrashRecoverySystem:
    """Initialize the global crash recovery system.
    
    Args:
        recovery_dir: Directory for recovery snapshots
        
    Returns:
        CrashRecoverySystem instance
    """
    global _crash_recovery_system
    
    if _crash_recovery_system is None:
        _crash_recovery_system = CrashRecoverySystem(recovery_dir)
    
    return _crash_recovery_system


def get_crash_recovery_system() -> Optional[CrashRecoverySystem]:
    """Get the global crash recovery system instance."""
    return _crash_recovery_system
