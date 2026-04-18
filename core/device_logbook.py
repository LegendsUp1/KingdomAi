"""
KINGDOM AI - Persistent Device Logbook System
2026 SOTA - Dual-format persistent device history tracking

Features:
- JSONL format for human-readable logs and easy parsing
- SQLite format for fast queries and analytics
- Automatic device learning from interaction history
- Pattern recognition for device behavior
- Cross-session device memory
"""

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger("KingdomAI.DeviceLogbook")


def _is_wsl2() -> bool:
    """Detect if running inside WSL2."""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False


class DeviceEventType(Enum):
    """Types of device events to log"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    TAKEOVER_STARTED = "takeover_started"
    TAKEOVER_COMPLETE = "takeover_complete"
    TAKEOVER_FAILED = "takeover_failed"
    COMMAND_SENT = "command_sent"
    COMMAND_RESPONSE = "command_response"
    FIRMWARE_FLASHED = "firmware_flashed"
    CAPABILITY_DISCOVERED = "capability_discovered"
    ERROR = "error"
    WIFI_CONFIGURED = "wifi_configured"
    DFU_TRIGGERED = "dfu_triggered"


@dataclass
class DeviceLogEntry:
    """Single device log entry"""
    timestamp: float
    event_type: str
    device_id: str
    device_name: str
    device_category: str
    port: str = ""
    vid: int = 0
    pid: int = 0
    vendor: str = ""
    product: str = ""
    serial: str = ""
    event_data: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        if self.event_data is None:
            data['event_data'] = {}
        return data
    
    def to_jsonl(self) -> str:
        """Convert to JSONL format (single line JSON)"""
        return json.dumps(self.to_dict(), separators=(',', ':'))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceLogEntry':
        """Create from dictionary"""
        return cls(**data)


class DeviceLogbook:
    """
    2026 SOTA Persistent Device Logbook
    
    Dual-format storage:
    - JSONL: Human-readable, append-only, easy to parse
    - SQLite: Fast queries, analytics, aggregations
    
    Features:
    - Automatic device learning from history
    - Pattern recognition (successful commands, common errors)
    - Cross-session device memory
    - Performance analytics
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        default_dir = Path(__file__).parent.parent / "data" / "device_logbook"
        self.data_dir = data_dir or default_dir
        
        # WSL2 FIX: SQLite on /mnt/c (NTFS via 9P) has broken file locking
        if _is_wsl2() and str(self.data_dir).startswith('/mnt/'):
            self.data_dir = Path.home() / '.kingdom_ai' / 'device_logbook'
            logger.info(f"WSL2 detected: using Linux-native path for SQLite: {self.data_dir}")
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()
        
        # JSONL log file (append-only)
        self.jsonl_path = self.data_dir / "device_logbook.jsonl"
        
        # SQLite database for queries
        self.db_path = self.data_dir / "device_logbook.db"
        self._init_database()
        
        # In-memory cache for recent events
        self.recent_events: List[DeviceLogEntry] = []
        self.max_recent = 1000
        
        # Device learning cache
        self.device_patterns: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"📖 DeviceLogbook initialized at {self.data_dir}")
    
    def _init_database(self):
        """Initialize SQLite database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # WAL mode for better concurrency and reliability
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # Main events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    device_name TEXT,
                    device_category TEXT,
                    port TEXT,
                    vid INTEGER,
                    pid INTEGER,
                    vendor TEXT,
                    product TEXT,
                    serial TEXT,
                    event_data TEXT,
                    success INTEGER,
                    error_message TEXT
                )
            """)
            
            # Device summary table (aggregated stats per device)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_summary (
                    device_id TEXT PRIMARY KEY,
                    device_name TEXT,
                    device_category TEXT,
                    first_seen REAL,
                    last_seen REAL,
                    total_connections INTEGER DEFAULT 0,
                    successful_takeovers INTEGER DEFAULT 0,
                    failed_takeovers INTEGER DEFAULT 0,
                    total_commands INTEGER DEFAULT 0,
                    successful_commands INTEGER DEFAULT 0,
                    learned_capabilities TEXT,
                    learned_commands TEXT,
                    notes TEXT
                )
            """)
            
            # Create indexes for fast queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON device_events(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_id ON device_events(device_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON device_events(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_category ON device_events(device_category)")
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Device logbook database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize logbook database: {e}")
    
    def log_event(self, entry: DeviceLogEntry):
        """Log a device event to both JSONL and SQLite"""
        try:
            with self._lock:
                # Write to JSONL (append-only)
                with open(self.jsonl_path, 'a', encoding='utf-8') as f:
                    f.write(entry.to_jsonl() + '\n')
                
                # Write to SQLite
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                event_data_json = json.dumps(entry.event_data) if entry.event_data else "{}"
                
                cursor.execute("""
                    INSERT INTO device_events (
                        timestamp, event_type, device_id, device_name, device_category,
                        port, vid, pid, vendor, product, serial,
                        event_data, success, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.timestamp, entry.event_type, entry.device_id, entry.device_name,
                    entry.device_category, entry.port, entry.vid, entry.pid,
                    entry.vendor, entry.product, entry.serial,
                    event_data_json, 1 if entry.success else 0, entry.error_message
                ))
                
                conn.commit()
                conn.close()
                
                # Update in-memory cache
                self.recent_events.append(entry)
                if len(self.recent_events) > self.max_recent:
                    self.recent_events.pop(0)
                
                # Update device summary
                self._update_device_summary(entry)
                
        except Exception as e:
            logger.error(f"Failed to log device event: {e}")
    
    def _update_device_summary(self, entry: DeviceLogEntry):
        """Update aggregated device statistics with 2026 SOTA retry logic and WAL mode"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 2026 SOTA: Use WAL mode for better concurrency and reduced I/O errors
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode
                conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and performance
                conn.execute("PRAGMA cache_size=10000")  # Increase cache for better performance
                cursor = conn.cursor()
                
                # Get or create summary
                cursor.execute("SELECT * FROM device_summary WHERE device_id = ?", (entry.device_id,))
                row = cursor.fetchone()
                
                if row is None:
                    # Create new summary
                    cursor.execute("""
                        INSERT INTO device_summary (
                            device_id, device_name, device_category, first_seen, last_seen,
                            total_connections, successful_takeovers, failed_takeovers,
                            total_commands, successful_commands
                        ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0)
                    """, (entry.device_id, entry.device_name, entry.device_category, entry.timestamp, entry.timestamp))
                
                # Update counters based on event type
                if entry.event_type == DeviceEventType.CONNECTED.value:
                    cursor.execute("""
                        UPDATE device_summary 
                        SET total_connections = total_connections + 1, last_seen = ?
                        WHERE device_id = ?
                    """, (entry.timestamp, entry.device_id))
                
                elif entry.event_type == DeviceEventType.TAKEOVER_COMPLETE.value:
                    cursor.execute("""
                        UPDATE device_summary 
                        SET successful_takeovers = successful_takeovers + 1, last_seen = ?
                        WHERE device_id = ?
                    """, (entry.timestamp, entry.device_id))
                
                elif entry.event_type == DeviceEventType.TAKEOVER_FAILED.value:
                    cursor.execute("""
                        UPDATE device_summary 
                        SET failed_takeovers = failed_takeovers + 1, last_seen = ?
                        WHERE device_id = ?
                    """, (entry.timestamp, entry.device_id))
                
                elif entry.event_type == DeviceEventType.COMMAND_SENT.value:
                    cursor.execute("""
                        UPDATE device_summary 
                        SET total_commands = total_commands + 1, last_seen = ?
                        WHERE device_id = ?
                    """, (entry.timestamp, entry.device_id))
                    
                    if entry.success:
                        cursor.execute("""
                            UPDATE device_summary 
                            SET successful_commands = successful_commands + 1
                            WHERE device_id = ?
                        """, (entry.device_id,))
                
                conn.commit()
                conn.close()
                return  # Success, exit retry loop
                
            except Exception as e:
                if attempt == max_retries - 1:
                    # Final attempt failed - use in-memory fallback
                    logger.warning(f"⚠️ Device summary update failed after {max_retries} attempts, using in-memory fallback: {e}")
                    self._update_device_summary_in_memory(entry)
                    return
                else:
                    logger.warning(f"Device summary update attempt {attempt + 1} failed, retrying: {e}")
                    import time
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
    
    def _update_device_summary_in_memory(self, entry: DeviceLogEntry):
        """Fallback in-memory device summary when database fails"""
        try:
            # Store in memory cache as fallback
            cache_key = f"device_summary_{entry.device_id}"
            if not hasattr(self, '_memory_cache'):
                self._memory_cache = {}
            
            if cache_key not in self._memory_cache:
                self._memory_cache[cache_key] = {
                    'device_id': entry.device_id,
                    'device_name': entry.device_name,
                    'device_category': entry.device_category,
                    'first_seen': entry.timestamp,
                    'last_seen': entry.timestamp,
                    'total_connections': 0,
                    'successful_takeovers': 0,
                    'failed_takeovers': 0,
                    'total_commands': 0,
                    'successful_commands': 0
                }
            
            # Update in-memory summary
            summary = self._memory_cache[cache_key]
            summary['last_seen'] = entry.timestamp
            
            if entry.event_type == DeviceEventType.CONNECTED.value:
                summary['total_connections'] += 1
            elif entry.event_type == DeviceEventType.TAKEOVER_COMPLETE.value:
                summary['successful_takeovers'] += 1
            elif entry.event_type == DeviceEventType.TAKEOVER_FAILED.value:
                summary['failed_takeovers'] += 1
            elif entry.event_type == DeviceEventType.COMMAND_SENT.value:
                summary['total_commands'] += 1
                if entry.success:
                    summary['successful_commands'] += 1
            
            logger.debug(f"✅ Device summary updated in memory for {entry.device_id}")
            
        except Exception as e:
            logger.error(f"❌ Even in-memory fallback failed: {e}")
    
    def get_device_history(self, device_id: str, limit: int = 100) -> List[DeviceLogEntry]:
        """Get event history for a specific device"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT timestamp, event_type, device_id, device_name, device_category,
                       port, vid, pid, vendor, product, serial, event_data, success, error_message
                FROM device_events
                WHERE device_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (device_id, limit))
            
            entries = []
            for row in cursor.fetchall():
                event_data = json.loads(row[11]) if row[11] else {}
                entry = DeviceLogEntry(
                    timestamp=row[0],
                    event_type=row[1],
                    device_id=row[2],
                    device_name=row[3],
                    device_category=row[4],
                    port=row[5],
                    vid=row[6],
                    pid=row[7],
                    vendor=row[8],
                    product=row[9],
                    serial=row[10],
                    event_data=event_data,
                    success=bool(row[12]),
                    error_message=row[13]
                )
                entries.append(entry)
            
            conn.close()
            return entries
            
        except Exception as e:
            logger.error(f"Failed to get device history: {e}")
            return []
    
    def get_device_summary(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get aggregated statistics for a device"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM device_summary WHERE device_id = ?", (device_id,))
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return {
                    "device_id": row[0],
                    "device_name": row[1],
                    "device_category": row[2],
                    "first_seen": row[3],
                    "last_seen": row[4],
                    "total_connections": row[5],
                    "successful_takeovers": row[6],
                    "failed_takeovers": row[7],
                    "total_commands": row[8],
                    "successful_commands": row[9],
                    "learned_capabilities": json.loads(row[10]) if row[10] else [],
                    "learned_commands": json.loads(row[11]) if row[11] else {},
                    "notes": row[12]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get device summary: {e}")
            return None
    
    def learn_device_patterns(self, device_id: str) -> Dict[str, Any]:
        """Analyze device history to learn patterns and behaviors"""
        try:
            history = self.get_device_history(device_id, limit=500)
            
            patterns = {
                "successful_commands": {},
                "failed_commands": {},
                "common_errors": {},
                "capabilities": [],
                "connection_reliability": 0.0,
                "takeover_success_rate": 0.0,
                "command_success_rate": 0.0,
                "preferred_baud_rate": None,
                "firmware_type": None
            }
            
            total_connections = 0
            successful_connections = 0
            total_takeovers = 0
            successful_takeovers = 0
            total_commands = 0
            successful_commands = 0
            
            baud_rates = {}
            
            for entry in history:
                # Count connections
                if entry.event_type == DeviceEventType.CONNECTED.value:
                    total_connections += 1
                    if entry.success:
                        successful_connections += 1
                
                # Count takeovers
                if entry.event_type == DeviceEventType.TAKEOVER_COMPLETE.value:
                    total_takeovers += 1
                    successful_takeovers += 1
                elif entry.event_type == DeviceEventType.TAKEOVER_FAILED.value:
                    total_takeovers += 1
                
                # Analyze commands
                if entry.event_type == DeviceEventType.COMMAND_SENT.value:
                    total_commands += 1
                    command = entry.event_data.get("command", "") if entry.event_data else ""
                    
                    if entry.success:
                        successful_commands += 1
                        patterns["successful_commands"][command] = patterns["successful_commands"].get(command, 0) + 1
                    else:
                        patterns["failed_commands"][command] = patterns["failed_commands"].get(command, 0) + 1
                        error = entry.error_message
                        if error:
                            patterns["common_errors"][error] = patterns["common_errors"].get(error, 0) + 1
                
                # Track baud rates
                if entry.event_data and "baud_rate" in entry.event_data:
                    baud = entry.event_data["baud_rate"]
                    baud_rates[baud] = baud_rates.get(baud, 0) + 1
                
                # Collect capabilities
                if entry.event_type == DeviceEventType.CAPABILITY_DISCOVERED.value:
                    caps = entry.event_data.get("capabilities", []) if entry.event_data else []
                    for cap in caps:
                        if cap not in patterns["capabilities"]:
                            patterns["capabilities"].append(cap)
            
            # Calculate rates
            if total_connections > 0:
                patterns["connection_reliability"] = successful_connections / total_connections
            
            if total_takeovers > 0:
                patterns["takeover_success_rate"] = successful_takeovers / total_takeovers
            
            if total_commands > 0:
                patterns["command_success_rate"] = successful_commands / total_commands
            
            # Find preferred baud rate
            if baud_rates:
                patterns["preferred_baud_rate"] = max(baud_rates.items(), key=lambda x: x[1])[0]
            
            # Cache patterns
            with self._lock:
                self.device_patterns[device_id] = patterns
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to learn device patterns: {e}")
            return {}
    
    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get list of all known devices"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT device_id, device_name, device_category, last_seen, 
                       total_connections, successful_takeovers
                FROM device_summary
                ORDER BY last_seen DESC
            """)
            
            devices = []
            for row in cursor.fetchall():
                devices.append({
                    "device_id": row[0],
                    "device_name": row[1],
                    "device_category": row[2],
                    "last_seen": row[3],
                    "total_connections": row[4],
                    "successful_takeovers": row[5]
                })
            
            conn.close()
            return devices
            
        except Exception as e:
            logger.error(f"Failed to get all devices: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall logbook statistics"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Total events
            cursor.execute("SELECT COUNT(*) FROM device_events")
            total_events = cursor.fetchone()[0]
            
            # Total devices
            cursor.execute("SELECT COUNT(*) FROM device_summary")
            total_devices = cursor.fetchone()[0]
            
            # Events by type
            cursor.execute("SELECT event_type, COUNT(*) FROM device_events GROUP BY event_type")
            events_by_type = dict(cursor.fetchall())
            
            # Recent activity (last 24 hours)
            cutoff = time.time() - 86400
            cursor.execute("SELECT COUNT(*) FROM device_events WHERE timestamp > ?", (cutoff,))
            recent_events = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "total_events": total_events,
                "total_devices": total_devices,
                "events_by_type": events_by_type,
                "recent_events_24h": recent_events,
                "jsonl_size_mb": self.jsonl_path.stat().st_size / (1024 * 1024) if self.jsonl_path.exists() else 0,
                "db_size_mb": self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get logbook stats: {e}")
            return {}


# Singleton instance
_logbook_instance: Optional[DeviceLogbook] = None
_logbook_lock = threading.Lock()


def get_device_logbook() -> DeviceLogbook:
    """Get or create the global device logbook instance"""
    global _logbook_instance
    
    if _logbook_instance is None:
        with _logbook_lock:
            if _logbook_instance is None:
                _logbook_instance = DeviceLogbook()
    
    return _logbook_instance
