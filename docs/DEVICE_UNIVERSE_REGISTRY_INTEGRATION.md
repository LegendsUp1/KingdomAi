# Device Universe Registry Integration Plan

## Executive Summary

This document outlines the implementation plan for integrating authoritative device identification registries into Kingdom AI's device takeover system. The goal is to create a continuously-updated "Device Universe Index" that learns from both public registries and real hardware interactions.

---

## 1. Authoritative Registry Sources (2026 SOTA)

### 1.1 USB Device Registry
- **Source**: `http://www.linux-usb.org/usb.ids`
- **Format**: Plain text, vendor/device ID mapping
- **Update Frequency**: Weekly
- **Coverage**: ~3,000+ vendors, 50,000+ devices
- **Integration**: Parse VID:PID → manufacturer + product name

### 1.2 PCI Device Registry
- **Source**: `https://pci-ids.ucw.cz/pci.ids`
- **Format**: Plain text, vendor/device/subsystem mapping
- **Update Frequency**: Daily
- **Coverage**: Internal hardware (GPUs, NICs, storage controllers)
- **Integration**: Map PCI IDs to device capabilities

### 1.3 IEEE OUI Registry (MAC Addresses)
- **Source**: `https://standards-oui.ieee.org/oui/oui.csv`
- **Format**: CSV (Registry, Assignment, Organization Name, Address)
- **Update Frequency**: Daily
- **Coverage**: 40,000+ organizations
- **Additional**: `cid.csv`, `iab.csv`, `oui36.csv` for smaller blocks
- **Integration**: MAC prefix → vendor identification

### 1.4 Bluetooth Assigned Numbers
- **Source**: `https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Assigned_Numbers/out/en/Assigned_Numbers.pdf`
- **Format**: PDF (structured tables)
- **Update Frequency**: Monthly
- **Coverage**: Company IDs, GATT services, UUIDs, device classes
- **Integration**: BLE service discovery → device type classification

### 1.5 IANA Service Names and Port Numbers
- **Source**: `https://www.iana.org/assignments/service-names-port-numbers`
- **Format**: XML/CSV
- **Update Frequency**: As needed
- **Coverage**: Network services, protocols, port assignments
- **Integration**: Open port → service identification

### 1.6 Nmap OS/Service Fingerprints
- **Source**: Nmap project (nmap-os-db, nmap-service-probes)
- **Format**: Structured text (custom format)
- **Update Frequency**: With Nmap releases
- **Coverage**: OS detection patterns, service version detection
- **Integration**: Network device OS fingerprinting

---

## 2. Implementation Architecture

### 2.1 Registry Manager Component
```python
# core/device_registry_manager.py
class DeviceRegistryManager:
    """Manages device identification registries"""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.registries = {
            'usb': USBRegistry(),
            'pci': PCIRegistry(),
            'oui': OUIRegistry(),
            'bluetooth': BluetoothRegistry(),
            'iana': IANARegistry(),
            'nmap': NmapRegistry()
        }
        self.cache_dir = Path("data/device_registries")
        self.update_interval = 86400  # 24 hours
    
    async def update_all_registries(self):
        """Download and parse all registries"""
        for name, registry in self.registries.items():
            await registry.update()
            self.event_bus.publish(f'registry.{name}.updated', {
                'entries': registry.entry_count,
                'timestamp': datetime.now()
            })
    
    def identify_device(self, device_info: Dict) -> Dict:
        """Identify device using all available registries"""
        results = {}
        
        # USB identification
        if 'vid' in device_info and 'pid' in device_info:
            results['usb'] = self.registries['usb'].lookup(
                device_info['vid'], device_info['pid']
            )
        
        # MAC address identification
        if 'mac_address' in device_info:
            results['vendor'] = self.registries['oui'].lookup(
                device_info['mac_address']
            )
        
        # Bluetooth identification
        if 'bluetooth_services' in device_info:
            results['bluetooth'] = self.registries['bluetooth'].classify(
                device_info['bluetooth_services']
            )
        
        return results
```

### 2.2 Registry Storage Schema
```sql
-- SQLite schema for device registry cache
CREATE TABLE usb_devices (
    vid INTEGER NOT NULL,
    pid INTEGER NOT NULL,
    vendor_name TEXT,
    product_name TEXT,
    device_class TEXT,
    last_updated TIMESTAMP,
    PRIMARY KEY (vid, pid)
);

CREATE TABLE oui_vendors (
    oui_prefix TEXT PRIMARY KEY,
    organization TEXT,
    address TEXT,
    registry_type TEXT,
    last_updated TIMESTAMP
);

CREATE TABLE bluetooth_services (
    uuid TEXT PRIMARY KEY,
    service_name TEXT,
    service_type TEXT,
    assigned_number INTEGER,
    last_updated TIMESTAMP
);

CREATE TABLE device_knowledge (
    device_signature TEXT PRIMARY KEY,
    device_type TEXT,
    manufacturer TEXT,
    model TEXT,
    capabilities TEXT,  -- JSON
    control_protocol TEXT,
    learned_commands TEXT,  -- JSON
    success_rate REAL,
    last_seen TIMESTAMP,
    interaction_count INTEGER
);
```

### 2.3 Learning System Integration
```python
# core/device_learning_system.py
class DeviceLearningSystem:
    """Learns device behavior from interactions"""
    
    def __init__(self, event_bus, registry_manager):
        self.event_bus = event_bus
        self.registry_manager = registry_manager
        self.knowledge_db = Path("data/device_knowledge.db")
        
        # Subscribe to device events
        self.event_bus.subscribe('device.command.sent', self.record_command)
        self.event_bus.subscribe('device.command.response', self.record_response)
        self.event_bus.subscribe('device.takeover.complete', self.record_takeover)
    
    def record_command(self, event_data):
        """Record successful command patterns"""
        device_id = event_data['device_id']
        command = event_data['command']
        
        # Update knowledge base
        self._update_knowledge(device_id, {
            'command': command,
            'timestamp': datetime.now(),
            'success': True
        })
    
    def record_response(self, event_data):
        """Learn from device responses"""
        device_id = event_data['device_id']
        response = event_data['response']
        
        # Parse response patterns
        patterns = self._extract_patterns(response)
        self._update_knowledge(device_id, {
            'response_patterns': patterns
        })
    
    def get_device_profile(self, device_info):
        """Get learned profile for device"""
        signature = self._generate_signature(device_info)
        return self._load_knowledge(signature)
```

---

## 3. Persistent Logbook Implementation

### 3.1 JSONL Format (Recommended)
```python
# core/device_logbook.py
class DeviceLogbook:
    """Persistent event logging in JSONL format"""
    
    def __init__(self, log_dir="data/device_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_log = None
        self.rotation_size = 100 * 1024 * 1024  # 100MB
    
    def log_event(self, event_type: str, event_data: Dict):
        """Append event to JSONL log"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'data': event_data
        }
        
        # Rotate log if needed
        if self._should_rotate():
            self._rotate_log()
        
        # Append to current log
        with open(self._get_current_log(), 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def query_events(self, event_type=None, start_time=None, end_time=None):
        """Query events from logs"""
        results = []
        for log_file in self._get_log_files():
            with open(log_file, 'r') as f:
                for line in f:
                    entry = json.loads(line)
                    if self._matches_query(entry, event_type, start_time, end_time):
                        results.append(entry)
        return results
```

### 3.2 SQLite Format (Alternative)
```python
# core/device_logbook_sqlite.py
class DeviceLogbookSQLite:
    """Persistent event logging in SQLite"""
    
    def __init__(self, db_path="data/device_events.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()
    
    def _create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS device_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                device_id TEXT,
                event_data TEXT,  -- JSON
                INDEX idx_timestamp (timestamp),
                INDEX idx_event_type (event_type),
                INDEX idx_device_id (device_id)
            )
        ''')
    
    def log_event(self, event_type: str, event_data: Dict):
        """Insert event into database"""
        self.conn.execute(
            'INSERT INTO device_events (event_type, device_id, event_data) VALUES (?, ?, ?)',
            (event_type, event_data.get('device_id'), json.dumps(event_data))
        )
        self.conn.commit()
    
    def query_events(self, event_type=None, device_id=None, limit=1000):
        """Query events from database"""
        query = 'SELECT * FROM device_events WHERE 1=1'
        params = []
        
        if event_type:
            query += ' AND event_type = ?'
            params.append(event_type)
        
        if device_id:
            query += ' AND device_id = ?'
            params.append(device_id)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        return cursor.fetchall()
```

---

## 4. Integration with Existing System

### 4.1 EventBus Integration
```python
# Modify core/event_bus.py
class EventBus:
    def __init__(self):
        # ... existing code ...
        
        # Add persistent logbook
        self.logbook = DeviceLogbook()  # or DeviceLogbookSQLite()
        
        # Add registry manager
        self.registry_manager = DeviceRegistryManager(self)
        
        # Add learning system
        self.learning_system = DeviceLearningSystem(self, self.registry_manager)
    
    def publish(self, event_type: str, data: Any = None):
        # ... existing code ...
        
        # Log to persistent storage
        if event_type.startswith('device.'):
            self.logbook.log_event(event_type, data)
        
        # ... rest of existing code ...
```

### 4.2 HostDeviceManager Integration
```python
# Modify core/host_device_manager.py
class HostDeviceManager:
    def __init__(self, event_bus):
        # ... existing code ...
        
        # Add registry manager reference
        self.registry_manager = event_bus.registry_manager
        
        # Add learning system reference
        self.learning_system = event_bus.learning_system
    
    def _classify_device(self, device_info):
        # Use registry manager for identification
        identification = self.registry_manager.identify_device(device_info)
        
        # Check learned knowledge
        profile = self.learning_system.get_device_profile(device_info)
        
        # Merge registry + learned data
        return {**identification, **profile}
```

---

## 5. Expansion Beyond Serial: Next Steps

### 5.1 Bluetooth Control Implementation
```python
# core/bluetooth_controller.py
class BluetoothController:
    """Real Bluetooth device control"""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.paired_devices = {}
    
    async def pair_device(self, device_address: str):
        """Pair with Bluetooth device"""
        # Use bleak for BLE, pybluez for Classic
        from bleak import BleakClient
        
        async with BleakClient(device_address) as client:
            if await client.is_connected():
                self.paired_devices[device_address] = client
                self.event_bus.publish('bluetooth.paired', {
                    'address': device_address
                })
                return True
        return False
    
    async def send_command(self, device_address: str, characteristic_uuid: str, data: bytes):
        """Send command to BLE device"""
        client = self.paired_devices.get(device_address)
        if client:
            await client.write_gatt_char(characteristic_uuid, data)
            self.event_bus.publish('bluetooth.command.sent', {
                'address': device_address,
                'uuid': characteristic_uuid,
                'data': data.hex()
            })
```

### 5.2 RF Transmission (SDR Required)
```python
# core/rf_transmitter.py
class RFTransmitter:
    """RF signal transmission via SDR"""
    
    def __init__(self, event_bus, sdr_device='hackrf'):
        self.event_bus = event_bus
        self.sdr_device = sdr_device
        self._init_sdr()
    
    def _init_sdr(self):
        """Initialize SDR hardware"""
        if self.sdr_device == 'hackrf':
            # Use SoapySDR or hackrf library
            pass
        elif self.sdr_device == 'rtlsdr':
            # RTL-SDR is RX only
            raise ValueError("RTL-SDR cannot transmit")
    
    def transmit_signal(self, frequency: float, data: bytes, modulation='OOK'):
        """Transmit RF signal"""
        # Requires SDR hardware capable of TX (HackRF, LimeSDR, etc.)
        self.event_bus.publish('rf.transmission', {
            'frequency': frequency,
            'modulation': modulation,
            'data_length': len(data)
        })
```

---

## 6. Implementation Roadmap

### Phase 1: Registry Integration (Week 1-2)
- [ ] Implement DeviceRegistryManager
- [ ] Download and parse USB/PCI/OUI registries
- [ ] Create SQLite cache schema
- [ ] Integrate with HostDeviceManager

### Phase 2: Persistent Logbook (Week 2-3)
- [ ] Implement JSONL logbook
- [ ] Wire EventBus persistence
- [ ] Add query interface
- [ ] Create log rotation mechanism

### Phase 3: Learning System (Week 3-4)
- [ ] Implement DeviceLearningSystem
- [ ] Create device knowledge schema
- [ ] Wire event subscriptions
- [ ] Build pattern recognition

### Phase 4: Bluetooth Control (Week 4-5)
- [ ] Implement BluetoothController
- [ ] Add pairing functionality
- [ ] Implement GATT command transmission
- [ ] Test with real BLE devices

### Phase 5: RF Expansion (Week 5-6)
- [ ] Implement RFTransmitter (requires SDR hardware)
- [ ] Add signal replay capability
- [ ] Integrate with DeviceTakeoverSystem
- [ ] Test with user-owned RF devices

---

## 7. Hardware Requirements for Full Implementation

### 7.1 Current (Serial/USB)
- ✅ Windows PC or WSL2 environment
- ✅ USB ports for microcontrollers
- ✅ Serial devices (Particle, Arduino, ESP32, etc.)

### 7.2 Bluetooth Control
- 🔌 Bluetooth 5.0+ adapter (built-in or USB)
- 🔌 BLE-capable devices to control

### 7.3 RF Transmission
- 🔌 **HackRF One** ($300) - Full-duplex SDR, 1MHz-6GHz
- 🔌 **LimeSDR Mini** ($159) - 10MHz-3.5GHz, USB 3.0
- 🔌 **ADALM-Pluto** ($149) - 325MHz-3.8GHz, educational SDR

### 7.4 IR Control
- 🔌 IR LED + transistor circuit
- 🔌 Arduino/ESP32 for IR transmission

---

## 8. Conclusion

This plan provides a comprehensive path to:
1. **Integrate authoritative device registries** for universal identification
2. **Implement persistent logging** for learning and audit
3. **Expand control beyond serial** to Bluetooth, RF, and IR
4. **Build a learning system** that improves with every interaction

**Next Action**: User must choose:
- **Logbook format**: JSONL or SQLite
- **Implementation priority**: Registry integration, persistent logging, or Bluetooth control

---

*Integration plan created: 2026-01-21*
*Status: Ready for implementation*
*Hardware: Serial/USB fully supported, Bluetooth/RF requires additional hardware*
