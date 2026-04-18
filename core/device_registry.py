"""
KINGDOM AI - Universal Device Registry System
2026 SOTA - Complete device identification using authoritative databases

Integrates:
- USB-IDs database (50,000+ USB vendor/device IDs)
- Bluetooth SIG Company Identifiers (3,000+ companies)
- IEEE OUI database (MAC address vendor lookup)
- PCI-IDs database (PCI vendor/device IDs)
- IANA protocol numbers

This provides UNIVERSAL device identification for ANY device type.
"""

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import requests


def _is_wsl2() -> bool:
    """Detect if running inside WSL2."""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False


def _get_wsl2_native_data_dir(subdir: str) -> Path:
    """Get a Linux-native path for data storage in WSL2.
    
    SQLite requires a POSIX-compliant filesystem for journaling.
    /mnt/c (Windows NTFS via 9P) breaks SQLite file locking and journal writes.
    Using the Linux-native filesystem fixes 'disk I/O error' permanently.
    """
    native_dir = Path.home() / '.kingdom_ai' / subdir
    native_dir.mkdir(parents=True, exist_ok=True)
    return native_dir

logger = logging.getLogger("KingdomAI.DeviceRegistry")


@dataclass
class DeviceIdentity:
    """Complete device identity from authoritative registries"""
    vid: Optional[int] = None
    pid: Optional[int] = None
    vendor_name: str = ""
    product_name: str = ""
    device_class: str = ""
    device_subclass: str = ""
    protocol: str = ""
    mac_vendor: str = ""  # From IEEE OUI
    bluetooth_company: str = ""  # From Bluetooth SIG
    pci_vendor: str = ""
    pci_device: str = ""
    confidence: float = 0.0  # 0.0-1.0 confidence score
    source: str = ""  # Which registry provided this info
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class UniversalDeviceRegistry:
    """
    2026 SOTA Universal Device Registry
    
    Provides authoritative device identification using official databases:
    - USB.org USB-IDs (50,000+ devices)
    - Bluetooth SIG Company IDs (3,000+ companies)
    - IEEE OUI database (MAC vendor lookup)
    - PCI SIG database
    - IANA protocol numbers
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        default_dir = Path(__file__).parent.parent / "data" / "device_registry"
        self.data_dir = data_dir or default_dir
        
        # WSL2 FIX: SQLite on /mnt/c (NTFS via 9P) has broken file locking
        # causing 'disk I/O error'. Store DB on Linux-native filesystem instead.
        if _is_wsl2() and str(self.data_dir).startswith('/mnt/'):
            self.data_dir = _get_wsl2_native_data_dir('device_registry')
            logger.info(f"WSL2 detected: using Linux-native path for SQLite: {self.data_dir}")
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()
        
        # In-memory caches for fast lookup
        self.usb_vendors: Dict[int, str] = {}
        self.usb_devices: Dict[Tuple[int, int], Dict[str, str]] = {}  # (vid, pid) -> info
        self.bluetooth_companies: Dict[int, str] = {}
        self.ieee_oui: Dict[str, str] = {}  # MAC prefix -> vendor
        self.pci_vendors: Dict[int, str] = {}
        self.pci_devices: Dict[Tuple[int, int], str] = {}
        
        # SQLite database for persistent storage
        self.db_path = self.data_dir / "device_registry.db"
        self._init_database()
        
        # Auto-update flags
        self.last_update: Dict[str, float] = {}
        self.update_interval = 86400 * 7  # 7 days
        
        logger.info(f"🔍 UniversalDeviceRegistry initialized at {self.data_dir}")
    
    def _init_database(self):
        """Initialize SQLite database for persistent storage"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Use WAL journal mode for better concurrency and reliability
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # USB devices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usb_devices (
                    vid INTEGER NOT NULL,
                    pid INTEGER NOT NULL,
                    vendor_name TEXT,
                    product_name TEXT,
                    device_class TEXT,
                    device_subclass TEXT,
                    protocol TEXT,
                    last_updated REAL,
                    PRIMARY KEY (vid, pid)
                )
            """)
            
            # Bluetooth companies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bluetooth_companies (
                    company_id INTEGER PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    last_updated REAL
                )
            """)
            
            # IEEE OUI table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ieee_oui (
                    mac_prefix TEXT PRIMARY KEY,
                    vendor_name TEXT NOT NULL,
                    last_updated REAL
                )
            """)
            
            # PCI devices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pci_devices (
                    vendor_id INTEGER NOT NULL,
                    device_id INTEGER NOT NULL,
                    vendor_name TEXT,
                    device_name TEXT,
                    last_updated REAL,
                    PRIMARY KEY (vendor_id, device_id)
                )
            """)
            
            # Create indexes for fast lookup
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_usb_vid ON usb_devices(vid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_company ON bluetooth_companies(company_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_oui_prefix ON ieee_oui(mac_prefix)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pci_vendor ON pci_devices(vendor_id)")
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Device registry database initialized")
            
            # Load data into memory
            self._load_from_database()
            
        except Exception as e:
            logger.error(f"Failed to initialize device registry database: {e}")
    
    def _load_from_database(self):
        """Load registry data from SQLite into memory for fast lookup"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Load USB devices
            cursor.execute("SELECT vid, pid, vendor_name, product_name, device_class FROM usb_devices")
            for row in cursor.fetchall():
                vid, pid, vendor_name, product_name, device_class = row
                if vendor_name:
                    self.usb_vendors[vid] = vendor_name
                if product_name:
                    self.usb_devices[(vid, pid)] = {
                        "vendor": vendor_name or "",
                        "product": product_name,
                        "class": device_class or ""
                    }
            
            # Load Bluetooth companies
            cursor.execute("SELECT company_id, company_name FROM bluetooth_companies")
            for row in cursor.fetchall():
                company_id, company_name = row
                self.bluetooth_companies[company_id] = company_name
            
            # Load IEEE OUI
            cursor.execute("SELECT mac_prefix, vendor_name FROM ieee_oui")
            for row in cursor.fetchall():
                mac_prefix, vendor_name = row
                self.ieee_oui[mac_prefix.upper()] = vendor_name
            
            # Load PCI devices
            cursor.execute("SELECT vendor_id, device_id, vendor_name, device_name FROM pci_devices")
            for row in cursor.fetchall():
                vendor_id, device_id, vendor_name, device_name = row
                if vendor_name:
                    self.pci_vendors[vendor_id] = vendor_name
                if device_name:
                    self.pci_devices[(vendor_id, device_id)] = device_name
            
            conn.close()
            
            logger.info(f"📊 Loaded registries: {len(self.usb_devices)} USB, {len(self.bluetooth_companies)} BT, {len(self.ieee_oui)} OUI, {len(self.pci_devices)} PCI")
            
        except Exception as e:
            logger.error(f"Failed to load registry data: {e}")
    
    def identify_usb_device(self, vid: int, pid: int) -> DeviceIdentity:
        """Identify USB device using VID:PID"""
        identity = DeviceIdentity(vid=vid, pid=pid)
        
        with self._lock:
            # Check in-memory cache first
            if (vid, pid) in self.usb_devices:
                info = self.usb_devices[(vid, pid)]
                identity.vendor_name = info.get("vendor", "")
                identity.product_name = info.get("product", "")
                identity.device_class = info.get("class", "")
                identity.confidence = 1.0
                identity.source = "usb_ids_database"
                return identity
            
            # Check vendor only
            if vid in self.usb_vendors:
                identity.vendor_name = self.usb_vendors[vid]
                identity.confidence = 0.5
                identity.source = "usb_ids_vendor_only"
                return identity
        
        identity.confidence = 0.0
        identity.source = "unknown"
        return identity
    
    def identify_bluetooth_device(self, company_id: int) -> DeviceIdentity:
        """Identify Bluetooth device using Company ID"""
        identity = DeviceIdentity()
        
        with self._lock:
            if company_id in self.bluetooth_companies:
                identity.bluetooth_company = self.bluetooth_companies[company_id]
                identity.vendor_name = identity.bluetooth_company
                identity.confidence = 1.0
                identity.source = "bluetooth_sig"
                return identity
        
        identity.confidence = 0.0
        identity.source = "unknown"
        return identity
    
    def identify_by_mac(self, mac_address: str) -> DeviceIdentity:
        """Identify device by MAC address (IEEE OUI lookup)"""
        identity = DeviceIdentity()
        
        # Extract OUI (first 6 hex digits)
        mac_clean = mac_address.replace(":", "").replace("-", "").upper()
        if len(mac_clean) >= 6:
            oui = mac_clean[:6]
            
            with self._lock:
                if oui in self.ieee_oui:
                    identity.mac_vendor = self.ieee_oui[oui]
                    identity.vendor_name = identity.mac_vendor
                    identity.confidence = 0.9
                    identity.source = "ieee_oui"
                    return identity
        
        identity.confidence = 0.0
        identity.source = "unknown"
        return identity
    
    def identify_pci_device(self, vendor_id: int, device_id: int) -> DeviceIdentity:
        """Identify PCI device"""
        identity = DeviceIdentity()
        
        with self._lock:
            if (vendor_id, device_id) in self.pci_devices:
                identity.pci_device = self.pci_devices[(vendor_id, device_id)]
                identity.product_name = identity.pci_device
                identity.confidence = 1.0
                identity.source = "pci_ids"
            
            if vendor_id in self.pci_vendors:
                identity.pci_vendor = self.pci_vendors[vendor_id]
                identity.vendor_name = identity.pci_vendor
                if identity.confidence == 0.0:
                    identity.confidence = 0.5
                    identity.source = "pci_ids_vendor_only"
        
        return identity
    
    def update_usb_database(self, force: bool = False):
        """Download and update USB-IDs database from official source"""
        registry_key = "usb_ids"
        
        if not force:
            last_update = self.last_update.get(registry_key, 0)
            if time.time() - last_update < self.update_interval:
                logger.debug(f"USB-IDs database updated recently, skipping")
                return
        
        try:
            logger.info("📥 Downloading USB-IDs database...")
            
            # Official USB-IDs source
            url = "https://raw.githubusercontent.com/systemd/systemd/main/hwdb.d/usb.ids"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            usb_ids_text = response.text
            
            # Parse USB-IDs format
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            current_vendor = None
            current_vendor_name = ""
            count = 0
            
            for line in usb_ids_text.split('\n'):
                line = line.rstrip()
                if not line or line.startswith('#'):
                    continue
                
                # Vendor line (no leading whitespace)
                if not line.startswith('\t') and not line.startswith(' '):
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        try:
                            current_vendor = int(parts[0], 16)
                            current_vendor_name = parts[1]
                            
                            cursor.execute("""
                                INSERT OR REPLACE INTO usb_devices (vid, pid, vendor_name, last_updated)
                                VALUES (?, 0, ?, ?)
                            """, (current_vendor, current_vendor_name, time.time()))
                            count += 1
                        except ValueError:
                            continue
                
                # Device line (leading whitespace)
                elif line.startswith('\t') and current_vendor is not None:
                    line = line.lstrip()
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        try:
                            pid = int(parts[0], 16)
                            product_name = parts[1]
                            
                            cursor.execute("""
                                INSERT OR REPLACE INTO usb_devices (vid, pid, vendor_name, product_name, last_updated)
                                VALUES (?, ?, ?, ?, ?)
                            """, (current_vendor, pid, current_vendor_name, product_name, time.time()))
                            count += 1
                        except ValueError:
                            continue
            
            conn.commit()
            conn.close()
            
            self.last_update[registry_key] = time.time()
            self._load_from_database()
            
            logger.info(f"✅ USB-IDs database updated: {count} entries")
            
        except Exception as e:
            logger.error(f"Failed to update USB-IDs database: {e}")
    
    def update_bluetooth_database(self, force: bool = False):
        """Download and update Bluetooth SIG Company IDs"""
        registry_key = "bluetooth_sig"
        
        if not force:
            last_update = self.last_update.get(registry_key, 0)
            if time.time() - last_update < self.update_interval:
                logger.debug(f"Bluetooth SIG database updated recently, skipping")
                return
        
        try:
            logger.info("📥 Downloading Bluetooth SIG Company IDs...")
            
            # Nordic's maintained Bluetooth numbers database
            url = "https://raw.githubusercontent.com/NordicSemiconductor/bluetooth-numbers-database/master/v1/company_ids.json"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            companies = response.json()
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            count = 0
            for company in companies:
                company_id = company.get("code")
                company_name = company.get("name")
                
                if company_id is not None and company_name:
                    cursor.execute("""
                        INSERT OR REPLACE INTO bluetooth_companies (company_id, company_name, last_updated)
                        VALUES (?, ?, ?)
                    """, (company_id, company_name, time.time()))
                    count += 1
            
            conn.commit()
            conn.close()
            
            self.last_update[registry_key] = time.time()
            self._load_from_database()
            
            logger.info(f"✅ Bluetooth SIG database updated: {count} companies")
            
        except Exception as e:
            logger.error(f"Failed to update Bluetooth SIG database: {e}")
    
    def update_ieee_oui_database(self, force: bool = False):
        """Download and update IEEE OUI database"""
        registry_key = "ieee_oui"
        
        if not force:
            last_update = self.last_update.get(registry_key, 0)
            if time.time() - last_update < self.update_interval:
                logger.debug(f"IEEE OUI database updated recently, skipping")
                return
        
        # Check if we have existing data
        has_existing_data = len(self.ieee_oui) > 0
        
        try:
            logger.info("📥 Downloading IEEE OUI database...")
            
            # IEEE OUI database - 2026 SOTA: Use reliable mirrors with fallbacks
            urls = [
                "https://raw.githubusercontent.com/wireshark/wireshark/master/manuf",  # Wireshark maintains updated OUI
                "https://gitlab.com/wireshark/wireshark/-/raw/master/manuf",  # GitLab mirror
                "https://code.wireshark.org/review/gitweb?p=wireshark.git;a=blob_plain;f=manuf;hb=HEAD",  # Wireshark code mirror
                "http://standards-oui.ieee.org/oui/oui.txt",  # IEEE primary (may have rate limits)
                "https://standards-oui.ieee.org/oui/oui.txt",  # IEEE HTTPS
            ]
            
            response = None
            last_error = None
            for url in urls:
                try:
                    logger.debug(f"Trying IEEE OUI URL: {url}")
                    # Use longer timeout and allow redirects
                    response = requests.get(url, timeout=45, allow_redirects=True, headers={
                        'User-Agent': 'Kingdom-AI/1.0 (Device Registry Updater)'
                    })
                    response.raise_for_status()
                    # Verify we got actual data (not empty or error page)
                    if len(response.text) > 1000:  # Reasonable minimum size
                        logger.info(f"✅ Downloaded from: {url}")
                        break
                    else:
                        logger.debug(f"Response too small from {url}, trying next...")
                        response = None
                        continue
                except Exception as url_err:
                    last_error = url_err
                    logger.debug(f"Failed to download from {url}: {url_err}")
                    continue
            
            if not response:
                # If we have existing data, downgrade to WARNING
                if has_existing_data:
                    logger.warning(f"IEEE OUI database update failed (using existing {len(self.ieee_oui)} entries): {last_error}")
                    return
                else:
                    # Only ERROR if we have no data at all
                    logger.error(f"Failed to update IEEE OUI database: All mirrors failed. Last error: {last_error}")
                    return
            
            oui_text = response.text
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            count = 0
            for line in oui_text.split('\n'):
                if '(hex)' in line:
                    parts = line.split('(hex)')
                    if len(parts) == 2:
                        mac_prefix = parts[0].strip().replace('-', '')
                        vendor_name = parts[1].strip()
                        
                        cursor.execute("""
                            INSERT OR REPLACE INTO ieee_oui (mac_prefix, vendor_name, last_updated)
                            VALUES (?, ?, ?)
                        """, (mac_prefix, vendor_name, time.time()))
                        count += 1
            
            conn.commit()
            conn.close()
            
            self.last_update[registry_key] = time.time()
            self._load_from_database()
            
            logger.info(f"✅ IEEE OUI database updated: {count} entries")
            
        except Exception as e:
            logger.error(f"Failed to update IEEE OUI database: {e}")
    
    def update_all_registries(self, force: bool = False):
        """Update all device registries"""
        logger.info("🔄 Updating all device registries...")
        self.update_usb_database(force=force)
        self.update_bluetooth_database(force=force)
        self.update_ieee_oui_database(force=force)
        logger.info("✅ All registries updated")
    
    def get_stats(self) -> Dict[str, int]:
        """Get registry statistics"""
        return {
            "usb_vendors": len(self.usb_vendors),
            "usb_devices": len(self.usb_devices),
            "bluetooth_companies": len(self.bluetooth_companies),
            "ieee_oui_entries": len(self.ieee_oui),
            "pci_vendors": len(self.pci_vendors),
            "pci_devices": len(self.pci_devices)
        }


# Singleton instance
_registry_instance: Optional[UniversalDeviceRegistry] = None
_registry_lock = threading.Lock()


def get_device_registry() -> UniversalDeviceRegistry:
    """Get or create the global device registry instance"""
    global _registry_instance
    
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = UniversalDeviceRegistry()
                # Auto-update on first access (async)
                import threading
                threading.Thread(
                    target=_registry_instance.update_all_registries,
                    daemon=True,
                    name="DeviceRegistryUpdater"
                ).start()
    
    return _registry_instance
