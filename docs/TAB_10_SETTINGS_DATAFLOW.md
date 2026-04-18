# TAB 10: SETTINGS - COMPLETE DATA FLOW MAPPING

## 🎯 OVERVIEW

**Tab Name:** Settings
**Purpose:** System configuration and preferences
**Frontend File:** `gui/qt_frames/settings_tab.py`
**Backend Files:** `core/redis_connector.py`, `core/config_manager.py`
**Event Bus Topics:** `settings:updated`, `settings.save`, `settings:reset`, `settings.query.response`, `ui.telemetry`
**Storage:** Redis Quantum Nexus (port 6380), `config/settings.json`

---

## 🔌 ACTUAL SIGNAL CONNECTIONS (Enumerated Dec 2025)

| Line | Signal | Handler | Purpose |
|------|--------|---------|--------|
| 386 | `save_btn.clicked` | `self.save_settings` | Save all settings to storage |
| 389 | `reset_btn.clicked` | `self.reset_to_defaults` | Reset settings to defaults |
| 575 | `browse_btn.clicked` | `self._select_log_path` | Browse for log directory |
| 599 | `sentience_enabled.toggled` | `self._on_sentience_monitoring_toggled` | Toggle sentience monitoring |
| 766 | All `QLineEdit.textChanged` | `self._on_setting_changed` | Mark settings as dirty |
| 768 | All `QSpinBox/QDoubleSpinBox.valueChanged` | `self._on_setting_changed` | Mark settings as dirty |
| 770 | All `QComboBox.currentIndexChanged` | `self._on_setting_changed` | Mark settings as dirty |
| 772 | All `QCheckBox.stateChanged` | `self._on_setting_changed` | Mark settings as dirty |

## 📡 ACTUAL EVENTBUS WIRING (Enumerated Dec 2025)

### Publishes
| Topic | Location | Trigger |
|-------|----------|--------|
| `settings:updated` | `save_settings()` line 910-913 | User clicks Save Settings |
| `settings.save` | `save_settings()` line 911-914 | User clicks Save Settings |
| `settings:reset` | `reset_to_defaults()` line 974-976 | User clicks Reset to Defaults |
| `settings.query.response` | `_handle_settings_query()` line 1157-1159 | Response to settings query |
| `ui.telemetry` | `_emit_ui_telemetry()` line 116 | Button clicks for telemetry |

### Subscriptions (in `_subscribe_to_events` line 809-820, deferred 4.2s)
| Topic | Handler | Purpose |
|-------|---------|--------|
| `settings.updated` | `_handle_settings_update` | External settings update |
| `settings.reset` | `load_settings` | External reset trigger |
| `theme.changed` | `_handle_theme_change` | Theme change notification |
| `settings.saved` | `_handle_settings_saved` | Confirmation of save |
| `api.key.available.*` | `_on_api_key_available` | API key broadcasts (line 134) |
| `api.key.list` | `_on_api_key_list` | API key list updates (line 135) |

---

## 📊 BUTTON MAPPING (3 BUTTONS)

### Button 1: SAVE SETTINGS

**Event Listener:**
```python
self.save_button.clicked.connect(self._on_save_clicked)
```

**Event Handler:**
```python
def _on_save_clicked(self):
    """Save all settings to Redis and config file"""
    try:
        # Gather all settings from GUI
        settings = self._gather_settings()
        
        # Validate settings
        if not self._validate_settings(settings):
            self._show_error("Invalid settings detected")
            return
        
        # Disable button during save
        self.save_button.setEnabled(False)
        self.save_button.setText("⏳ Saving...")
        
        # Publish save event
        self.event_bus.publish('settings.save', {
            'settings': settings,
            'timestamp': time.time()
        })
        
        logger.info("💾 Saving settings...")
        
    except Exception as e:
        logger.error(f"Settings save failed: {e}")
        self._show_error(str(e))
    finally:
        QTimer.singleShot(1000, lambda: self.save_button.setEnabled(True))
        QTimer.singleShot(1000, lambda: self.save_button.setText("💾 Save Settings"))

def _gather_settings(self):
    """Gather all settings from GUI inputs"""
    settings = {
        # General
        'theme': self.theme_combo.currentText(),
        'language': self.language_combo.currentText(),
        'auto_start': self.auto_start_checkbox.isChecked(),
        
        # Network
        'redis_host': self.redis_host_input.text(),
        'redis_port': int(self.redis_port_input.text()),
        'redis_password': self.redis_password_input.text(),
        
        # Trading
        'default_exchange': self.default_exchange_combo.currentText(),
        'trading_enabled': self.trading_enabled_checkbox.isChecked(),
        'max_trade_size': float(self.max_trade_size_input.text()),
        
        # Mining
        'mining_threads': int(self.mining_threads_spinbox.value()),
        'mining_algorithm': self.mining_algo_combo.currentText(),
        
        # Blockchain
        'default_network': self.default_network_combo.currentText(),
        'gas_price_multiplier': float(self.gas_multiplier_input.text()),
        
        # AI
        'default_model': self.default_model_combo.currentText(),
        'ai_temperature': float(self.ai_temp_slider.value()) / 100,
        'voice_enabled': self.voice_enabled_checkbox.isChecked(),
        
        # Logging
        'log_level': self.log_level_combo.currentText(),
        'log_path': self.log_path_input.text(),
        
        # Performance
        'cpu_limit': int(self.cpu_limit_spinbox.value()),
        'memory_limit': int(self.memory_limit_spinbox.value()),
        
        # Security
        'require_password': self.password_checkbox.isChecked(),
        'auto_lock_minutes': int(self.auto_lock_spinbox.value())
    }
    
    return settings
```

**Backend Processing:**
```python
# File: core/config_manager.py
class ConfigManager:
    async def _handle_save_settings(self, event_data):
        """Save settings to Redis and config file"""
        settings = event_data['settings']
        
        try:
            # Save to Redis Quantum Nexus
            await self._save_to_redis(settings)
            
            # Save to config file
            await self._save_to_file(settings)
            
            # Apply runtime settings
            await self._apply_settings(settings)
            
            logger.info("✅ Settings saved successfully")
            
            # Publish success
            await self.event_bus.publish('settings.saved', {
                'success': True,
                'settings_count': len(settings)
            })
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            await self.event_bus.publish('settings.save_failed', {
                'error': str(e)
            })
    
    async def _save_to_redis(self, settings):
        """Save settings to Redis Quantum Nexus"""
        import redis.asyncio as aioredis
        
        # Connect to Redis
        redis_client = await aioredis.create_redis_pool(
            f"redis://:{settings['redis_password']}@{settings['redis_host']}:{settings['redis_port']}"
        )
        
        # Save each setting
        for key, value in settings.items():
            redis_key = f"settings:{key}"
            await redis_client.set(redis_key, json.dumps(value))
        
        logger.info(f"✅ Saved {len(settings)} settings to Redis")
        
        redis_client.close()
        await redis_client.wait_closed()
    
    async def _save_to_file(self, settings):
        """Save settings to config/settings.json"""
        import json
        
        config_file = 'config/settings.json'
        
        with open(config_file, 'w') as f:
            json.dump(settings, f, indent=4)
        
        logger.info(f"✅ Saved settings to {config_file}")
    
    async def _apply_settings(self, settings):
        """Apply settings to running systems"""
        # Update trading system
        if settings['trading_enabled']:
            await self.event_bus.publish('trading.update_settings', {
                'max_trade_size': settings['max_trade_size'],
                'default_exchange': settings['default_exchange']
            })
        
        # Update mining system
        await self.event_bus.publish('mining.update_settings', {
            'threads': settings['mining_threads'],
            'algorithm': settings['mining_algorithm']
        })
        
        # Update AI system
        await self.event_bus.publish('ai.update_settings', {
            'default_model': settings['default_model'],
            'temperature': settings['ai_temperature'],
            'voice_enabled': settings['voice_enabled']
        })
        
        logger.info("✅ Settings applied to all systems")
```

**Data Flow:**
```
User modifies settings → Click "Save Settings"
    ↓
_on_save_clicked()
    ↓
_gather_settings() - Collect all GUI values
    ↓
_validate_settings() - Check validity
    ↓
event_bus.publish('settings.save', settings)
    ↓
Config Manager Backend
    ↓
Save to Redis Quantum Nexus (port 6380)
    ↓
Save to config/settings.json
    ↓
Apply settings to running systems:
    ├─→ Trading System
    ├─→ Mining System
    ├─→ AI System
    └─→ Blockchain System
    ↓
event_bus.publish('settings.saved')
    ↓
GUI shows: "✅ Settings saved successfully"
```

---

### Button 2: RESET TO DEFAULTS

**Event Listener:**
```python
self.reset_button.clicked.connect(self._on_reset_clicked)
```

**Event Handler:**
```python
def _on_reset_clicked(self):
    """Reset all settings to default values"""
    reply = QMessageBox.warning(
        self,
        'Reset Settings',
        'Reset all settings to default values?\n\n'
        'This will overwrite your current configuration.',
        QMessageBox.Yes | QMessageBox.No
    )
    
    if reply == QMessageBox.Yes:
        self.event_bus.publish('settings.reset', {})
```

**Backend:**
```python
async def _handle_reset_settings(self, event_data):
    """Reset all settings to defaults"""
    default_settings = {
        # General
        'theme': 'cyberpunk',
        'language': 'en',
        'auto_start': False,
        
        # Network
        'redis_host': 'localhost',
        'redis_port': 6380,
        'redis_password': 'QuantumNexus2025',
        
        # Trading
        'default_exchange': 'binance',
        'trading_enabled': False,
        'max_trade_size': 1000.0,
        
        # Mining
        'mining_threads': 4,
        'mining_algorithm': 'sha256',
        
        # Blockchain
        'default_network': 'ethereum',
        'gas_price_multiplier': 1.0,
        
        # AI
        'default_model': 'llama3.1',
        'ai_temperature': 0.7,
        'voice_enabled': True,
        
        # Logging
        'log_level': 'INFO',
        'log_path': 'logs/',
        
        # Performance
        'cpu_limit': 80,
        'memory_limit': 4096,
        
        # Security
        'require_password': False,
        'auto_lock_minutes': 30
    }
    
    # Save defaults
    await self._save_to_redis(default_settings)
    await self._save_to_file(default_settings)
    await self._apply_settings(default_settings)
    
    logger.info("✅ Settings reset to defaults")
    
    # Publish success
    await self.event_bus.publish('settings.reset_complete', {
        'settings': default_settings
    })
```

**GUI Update:**
```python
def _on_reset_complete(self, event_data):
    """Update GUI with default settings"""
    settings = event_data['settings']
    
    # Update all GUI inputs with default values
    self.theme_combo.setCurrentText(settings['theme'])
    self.language_combo.setCurrentText(settings['language'])
    self.auto_start_checkbox.setChecked(settings['auto_start'])
    
    self.redis_host_input.setText(settings['redis_host'])
    self.redis_port_input.setText(str(settings['redis_port']))
    
    self.default_exchange_combo.setCurrentText(settings['default_exchange'])
    self.trading_enabled_checkbox.setChecked(settings['trading_enabled'])
    
    # ... update all other inputs
    
    # Show success message
    QMessageBox.information(
        self,
        'Settings Reset',
        'All settings have been reset to default values.'
    )
```

---

### Button 3: BROWSE LOG PATH

**Event Listener:**
```python
self.browse_log_button.clicked.connect(self._on_browse_log_clicked)
```

**Event Handler:**
```python
def _on_browse_log_clicked(self):
    """Browse for log directory"""
    directory = QFileDialog.getExistingDirectory(
        self,
        "Select Log Directory",
        self.log_path_input.text() or "logs/"
    )
    
    if directory:
        self.log_path_input.setText(directory)
        logger.info(f"Log path selected: {directory}")
```

---

## ⚙️ SETTINGS CATEGORIES

### General Settings
- Theme (Cyberpunk, Dark, Light)
- Language (EN, ES, FR, DE, ZH, JA)
- Auto-start on boot
- Minimize to tray

### Network Settings
- Redis host and port
- Redis password
- Event bus configuration
- Network timeout

### Trading Settings
- Default exchange
- Trading enabled/disabled
- Max trade size
- Risk management
- Order types

### Mining Settings
- Number of threads
- Mining algorithm
- Pool configuration
- Overclocking

### Blockchain Settings
- Default network
- Gas price multiplier
- RPC provider preference
- Transaction timeout

### AI Settings
- Default model
- Temperature
- Context length
- Voice enabled
- Voice type

### Logging Settings
- Log level (DEBUG, INFO, WARNING, ERROR)
- Log path
- Max log size
- Log rotation

### Performance Settings
- CPU limit (%)
- Memory limit (MB)
- Thread pool size
- Cache size

### Security Settings
- Require password
- Auto-lock timeout
- API key encryption
- Backup settings

---

## 📡 EVENT BUS BINDINGS (Updated Dec 2025)

| Event Topic | Publisher | Subscriber | Trigger | Data |
|-------------|-----------|------------|---------|------|
| `settings:updated` | Settings GUI | All Components | Save button clicked | All settings dict |
| `settings.save` | Settings GUI | Config Manager | Save button clicked | All settings dict |
| `settings:reset` | Settings GUI | Config Manager | Reset button clicked | Default settings |
| `settings.query.response` | Settings GUI | Query requester | Response to query | Requested setting value |
| `settings.updated` | External | Settings GUI | External update | Updated settings |
| `settings.reset` | External | Settings GUI | External reset | None |
| `theme.changed` | External | Settings GUI | Theme change | New theme name |
| `settings.saved` | Config Manager | Settings GUI | Save complete | Success status |
| `ui.telemetry` | Settings GUI | TelemetryCollector | Button clicks | component, event_type, metadata |

---

## 💾 PERSISTENCE

### Storage Locations

**1. Redis Quantum Nexus (Primary)**
- Host: localhost
- Port: 6380
- Password: QuantumNexus2025
- Keys: `settings:*`

**2. Config File (Backup)**
- Path: `config/settings.json`
- Format: JSON
- Readable by all systems

**3. Environment Variables (Secrets)**
- Path: `.env`
- Format: KEY=VALUE
- Encrypted secrets only

---

## 📡 UI TELEMETRY & TELEMETRYCOLLECTOR

The Settings tab emits UI telemetry events on `ui.telemetry` when users save
settings or reset to defaults.

- **Channel:** `ui.telemetry`
- **Component:** `settings`
- **Representative event types:**
  - `settings.save_clicked`
  - `settings.reset_to_defaults_clicked`

Example payload shape:

```json
{
  "component": "settings",
  "channel": "ui.telemetry",
  "event_type": "settings.save_clicked",
  "timestamp": "2025-10-24T12:34:56Z",
  "success": true,
  "error": null,
  "metadata": {"source": "settings_tab"}
}
```

The **TelemetryCollector** subscribes to `ui.telemetry` and aggregates these
events with those from all other tabs for centralized monitoring.

## ✅ VERIFICATION

**Test Settings:**

```bash
# 1. Launch Kingdom AI
python3 -B kingdom_ai_perfect.py

# 2. Go to Settings tab

# 3. Modify some settings:
#    - Change theme to "Dark"
#    - Change mining threads to 8
#    - Change AI temperature to 0.9

# 4. Click "Save Settings"

# Monitor logs:
tail -f logs/kingdom_error.log | grep settings

# Expected:
# 💾 Saving settings...
# ✅ Saved 25 settings to Redis
# ✅ Saved settings to config/settings.json
# ✅ Settings applied to all systems
# ✅ Settings saved successfully

# 5. Verify Redis:
redis-cli -p 6380 -a QuantumNexus2025
> GET settings:theme
"dark"
> GET settings:mining_threads
"8"

# 6. Verify config file:
cat config/settings.json
# Should show all saved settings

# 7. Test Reset:
# Click "Reset to Defaults"
# Verify all settings return to defaults
```

---

**Status:** ✅ COMPLETE - System configuration with Redis persistence
