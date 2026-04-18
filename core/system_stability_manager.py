#!/usr/bin/env python3
"""
🛡️ KINGDOM AI SYSTEM STABILITY MANAGER 🛡️
Prevents crashes after long runtime (24+ hours) by managing:
- Memory leaks from QTimers, threads, and event handlers
- Resource exhaustion (file handles, connections, memory)
- System state persistence and auto-save
- Crash recovery and watchdog mechanisms
- Automatic cleanup and garbage collection
"""

import os
import sys
import gc
import psutil
import logging
import threading
import time
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, asdict
import traceback

logger = logging.getLogger(__name__)

@dataclass
class SystemState:
    """System state snapshot for persistence"""
    timestamp: str
    uptime_seconds: float
    memory_usage_mb: float
    cpu_percent: float
    active_threads: int
    active_timers: int
    open_files: int
    network_connections: int
    redis_connected: bool
    components_status: Dict[str, str]
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemState':
        return cls(**data)


class SystemStabilityManager:
    """
    Manages system stability and prevents crashes during long runtime.
    
    Features:
    - Automatic memory cleanup and garbage collection
    - QTimer leak prevention
    - Thread monitoring and cleanup
    - Resource limit enforcement
    - System state persistence
    - Crash recovery
    - Watchdog monitoring
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self, state_dir: str = "data/system_state"):
        """Initialize the stability manager."""
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Runtime tracking
        self.start_time = time.time()
        self.last_cleanup = time.time()
        self.last_state_save = time.time()
        self.last_gc_collect = time.time()
        
        # Resource tracking
        self.active_timers: Set[Any] = set()
        self.active_threads: Set[threading.Thread] = set()
        self.registered_components: Dict[str, Any] = {}
        self.cleanup_callbacks: List[callable] = []
        
        # Configuration
        self.cleanup_interval = 300  # 5 minutes
        self.state_save_interval = 600  # 10 minutes
        self.gc_interval = 180  # 3 minutes
        self.max_memory_mb = 4096  # 4GB limit
        self.max_threads = 100
        self.max_timers = 50
        
        # Monitoring
        self.process = psutil.Process()
        self.memory_warnings = 0
        self.thread_warnings = 0
        
        # Watchdog
        self.watchdog_enabled = True
        self.watchdog_thread = None
        self.shutdown_event = threading.Event()
        
        logger.info("🛡️ System Stability Manager initialized")
    
    @classmethod
    def get_instance(cls, state_dir: str = "data/system_state") -> 'SystemStabilityManager':
        """Get singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(state_dir)
            return cls._instance
    
    def start_watchdog(self):
        """Start the watchdog monitoring thread."""
        if self.watchdog_thread is None or not self.watchdog_thread.is_alive():
            self.shutdown_event.clear()
            self.watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                daemon=True,
                name="SystemStabilityWatchdog"
            )
            self.watchdog_thread.start()
            logger.info("🐕 Watchdog monitoring started")
    
    def stop_watchdog(self):
        """Stop the watchdog monitoring thread."""
        self.shutdown_event.set()
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=5)
        logger.info("🐕 Watchdog monitoring stopped")
    
    def _watchdog_loop(self):
        """Main watchdog monitoring loop."""
        logger.info("🐕 Watchdog loop started - monitoring system stability")
        
        while not self.shutdown_event.is_set():
            try:
                current_time = time.time()
                
                # Periodic cleanup
                if current_time - self.last_cleanup >= self.cleanup_interval:
                    self.perform_cleanup()
                    self.last_cleanup = current_time
                
                # Periodic state save
                if current_time - self.last_state_save >= self.state_save_interval:
                    self.save_system_state()
                    self.last_state_save = current_time
                
                # Periodic garbage collection
                if current_time - self.last_gc_collect >= self.gc_interval:
                    self.force_garbage_collection()
                    self.last_gc_collect = current_time
                
                # Check resource limits
                self.check_resource_limits()
                
                # Sleep for 30 seconds before next check
                self.shutdown_event.wait(30)
                
            except Exception as e:
                logger.error(f"Watchdog error: {e}\n{traceback.format_exc()}")
                self.shutdown_event.wait(60)  # Wait longer on error
    
    def perform_cleanup(self):
        """Perform comprehensive system cleanup."""
        logger.info("🧹 Performing system cleanup...")
        
        try:
            # Clean up dead threads
            dead_threads = [t for t in self.active_threads if not t.is_alive()]
            for thread in dead_threads:
                self.active_threads.discard(thread)
            if dead_threads:
                logger.info(f"🧹 Cleaned up {len(dead_threads)} dead threads")
            
            # Run registered cleanup callbacks
            for callback in self.cleanup_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.warning(f"Cleanup callback failed: {e}")
            
            # Force garbage collection
            self.force_garbage_collection()
            
            logger.info("✅ System cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    def force_garbage_collection(self):
        """Force Python garbage collection."""
        try:
            before = len(gc.get_objects())
            collected = gc.collect()
            after = len(gc.get_objects())
            
            logger.info(f"🗑️ Garbage collection: {collected} objects collected, {before - after} freed")
            
        except Exception as e:
            logger.error(f"Garbage collection failed: {e}")
    
    def check_resource_limits(self):
        """Check if resource limits are being exceeded."""
        try:
            # Check memory usage
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            if memory_mb > self.max_memory_mb:
                self.memory_warnings += 1
                logger.warning(f"⚠️ Memory usage ({memory_mb:.1f}MB) exceeds limit ({self.max_memory_mb}MB)")
                
                if self.memory_warnings >= 3:
                    logger.critical("🚨 CRITICAL: Memory limit exceeded multiple times - forcing cleanup")
                    self.perform_cleanup()
                    self.memory_warnings = 0
            else:
                self.memory_warnings = 0
            
            # Check thread count
            thread_count = threading.active_count()
            if thread_count > self.max_threads:
                self.thread_warnings += 1
                logger.warning(f"⚠️ Thread count ({thread_count}) exceeds limit ({self.max_threads})")
                
                if self.thread_warnings >= 3:
                    logger.critical("🚨 CRITICAL: Thread limit exceeded - cleaning up dead threads")
                    self.perform_cleanup()
                    self.thread_warnings = 0
            else:
                self.thread_warnings = 0
            
            # Check timer count
            if len(self.active_timers) > self.max_timers:
                logger.warning(f"⚠️ Timer count ({len(self.active_timers)}) exceeds limit ({self.max_timers})")
            
        except Exception as e:
            logger.error(f"Resource limit check failed: {e}")
    
    def save_system_state(self) -> bool:
        """Save current system state to disk."""
        try:
            state = self.capture_system_state()
            
            # Save as JSON
            state_file = self.state_dir / f"state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(state_file, 'w') as f:
                json.dump(state.to_dict(), f, indent=2)
            
            # Also save as latest
            latest_file = self.state_dir / "state_latest.json"
            with open(latest_file, 'w') as f:
                json.dump(state.to_dict(), f, indent=2)
            
            # Clean up old state files (keep last 10)
            self._cleanup_old_states()
            
            logger.info(f"💾 System state saved: {state_file.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save system state: {e}")
            return False
    
    def capture_system_state(self) -> SystemState:
        """Capture current system state."""
        try:
            memory_info = self.process.memory_info()
            cpu_percent = self.process.cpu_percent(interval=0.1)
            
            # Get open files count safely
            try:
                open_files = len(self.process.open_files())
            except (psutil.AccessDenied, AttributeError):
                open_files = 0
            
            # Get network connections count safely
            try:
                connections = len(self.process.connections())
            except (psutil.AccessDenied, AttributeError):
                connections = 0
            
            components_status = {
                name: "active" if hasattr(comp, 'is_active') and comp.is_active else "unknown"
                for name, comp in self.registered_components.items()
            }
            
            return SystemState(
                timestamp=datetime.now().isoformat(),
                uptime_seconds=time.time() - self.start_time,
                memory_usage_mb=memory_info.rss / 1024 / 1024,
                cpu_percent=cpu_percent,
                active_threads=threading.active_count(),
                active_timers=len(self.active_timers),
                open_files=open_files,
                network_connections=connections,
                redis_connected=self._check_redis_connection(),
                components_status=components_status
            )
            
        except Exception as e:
            logger.error(f"Failed to capture system state: {e}")
            return SystemState(
                timestamp=datetime.now().isoformat(),
                uptime_seconds=time.time() - self.start_time,
                memory_usage_mb=0,
                cpu_percent=0,
                active_threads=0,
                active_timers=0,
                open_files=0,
                network_connections=0,
                redis_connected=False,
                components_status={},
                last_error=str(e)
            )
    
    def _check_redis_connection(self) -> bool:
        """Check if Redis is connected."""
        try:
            from core.redis_connector import RedisConnector
            redis = RedisConnector.get_instance()
            return redis.is_connected() if hasattr(redis, 'is_connected') else False
        except Exception:
            return False
    
    def _cleanup_old_states(self):
        """Clean up old state files, keeping only the last 10."""
        try:
            state_files = sorted(
                self.state_dir.glob("state_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # Keep latest.json and last 10 timestamped files
            for state_file in state_files[10:]:
                if state_file.name != "state_latest.json":
                    state_file.unlink()
                    
        except Exception as e:
            logger.warning(f"Failed to cleanup old states: {e}")
    
    def load_latest_state(self) -> Optional[SystemState]:
        """Load the latest saved system state."""
        try:
            latest_file = self.state_dir / "state_latest.json"
            if latest_file.exists():
                with open(latest_file, 'r') as f:
                    data = json.load(f)
                return SystemState.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load latest state: {e}")
        return None
    
    def register_component(self, name: str, component: Any):
        """Register a component for monitoring."""
        self.registered_components[name] = component
        logger.debug(f"Registered component: {name}")
    
    def register_timer(self, timer: Any):
        """Register a QTimer for tracking."""
        self.active_timers.add(timer)
    
    def unregister_timer(self, timer: Any):
        """Unregister a QTimer."""
        self.active_timers.discard(timer)
    
    def register_thread(self, thread: threading.Thread):
        """Register a thread for tracking."""
        self.active_threads.add(thread)
    
    def register_cleanup_callback(self, callback: callable):
        """Register a cleanup callback to be called during cleanup."""
        self.cleanup_callbacks.append(callback)
    
    def get_uptime(self) -> float:
        """Get system uptime in seconds."""
        return time.time() - self.start_time
    
    def get_uptime_str(self) -> str:
        """Get formatted uptime string."""
        uptime = self.get_uptime()
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        return f"{hours}h {minutes}m {seconds}s"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current system statistics."""
        try:
            memory_info = self.process.memory_info()
            
            return {
                "uptime": self.get_uptime_str(),
                "memory_mb": memory_info.rss / 1024 / 1024,
                "cpu_percent": self.process.cpu_percent(interval=0.1),
                "threads": threading.active_count(),
                "timers": len(self.active_timers),
                "components": len(self.registered_components)
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    def shutdown(self):
        """Shutdown the stability manager."""
        logger.info("🛡️ Shutting down System Stability Manager...")
        
        # Stop watchdog
        self.stop_watchdog()
        
        # Save final state
        self.save_system_state()
        
        # Final cleanup
        self.perform_cleanup()
        
        logger.info("✅ System Stability Manager shutdown complete")


# Global instance
_stability_manager = None

def get_stability_manager() -> SystemStabilityManager:
    """Get the global stability manager instance."""
    global _stability_manager
    if _stability_manager is None:
        _stability_manager = SystemStabilityManager.get_instance()
    return _stability_manager


def initialize_stability_system():
    """Initialize and start the stability system."""
    manager = get_stability_manager()
    manager.start_watchdog()
    logger.info("🛡️ System stability system initialized and watchdog started")
    return manager


if __name__ == "__main__":
    # Test the stability manager
    logging.basicConfig(level=logging.INFO)
    manager = initialize_stability_system()
    
    print("\n" + "="*80)
    print("🛡️ SYSTEM STABILITY MANAGER TEST")
    print("="*80)
    
    # Show initial stats
    stats = manager.get_stats()
    print(f"\n📊 Initial Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Save state
    print(f"\n💾 Saving system state...")
    manager.save_system_state()
    
    # Load state
    print(f"\n📂 Loading latest state...")
    state = manager.load_latest_state()
    if state:
        print(f"  Timestamp: {state.timestamp}")
        print(f"  Memory: {state.memory_usage_mb:.1f}MB")
        print(f"  Threads: {state.active_threads}")
    
    print("\n✅ Test complete - watchdog will continue running")
    print("Press Ctrl+C to stop...\n")
    
    try:
        while True:
            time.sleep(10)
            stats = manager.get_stats()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Uptime: {stats['uptime']}, Memory: {stats['memory_mb']:.1f}MB, Threads: {stats['threads']}")
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        manager.shutdown()
