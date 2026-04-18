# TAB 9: VR SYSTEM - COMPLETE DATA FLOW MAPPING

## 🎯 OVERVIEW

**Tab Name:** VR System
**Purpose:** Virtual Reality interface integration with gesture recognition, voice commands, sentience monitoring
**Frontend Files:**
- `gui/qt_frames/vr_tab.py` (wrapper)
- `gui/qt_frames/vr_qt_tab.py` (main implementation, ~2907 lines)
- `gui/qt_frames/vr_sentience_monitor.py` (sentience metrics UI)
- `gui/widgets/vr_device_panel.py`
- `gui/widgets/vr_environment_selector.py`
- `gui/widgets/vr_gesture_controls.py`
- `gui/widgets/vr_performance_monitor.py`
- `gui/widgets/vr_3d_viewer.py`
**Backend Files:** `core/vr_system.py`, `core/vr_ai_interface.py`, `core/vr_integration.py`
**VR System Modules:** `vr/ai_interface/gesture_recognition.py`, `vr/ai_interface/voice_commands.py`, `vr/system/device_manager.py`, `vr/system/environment_manager.py`, `vr/system/graphics_renderer.py`
**Event Bus Topics:** See complete list below
**External APIs:** OpenVR/SteamVR, Meta Quest (ADB), Windows Mixed Reality
**Redis Integration:** Port 6380, password `QuantumNexus2025`

---

## 🔌 COMPLETE SIGNAL CONNECTIONS (Qt .connect() Mappings)

### Toolbar Actions
| Control | Signal | Handler | Line |
|---------|--------|---------|------|
| `btn_connect` (QAction) | `triggered` | `toggle_connection()` | 888 |
| `btn_calibrate` (QAction) | `triggered` | `calibrate_vr()` | 893 |
| `btn_reset_view` (QAction) | `triggered` | `reset_view()` | 899 |
| `btn_help` (QAction) | `triggered` | `show_help()` | 927 |
| `env_selector` (QComboBox) | `currentTextChanged` | `on_environment_selected()` | 907 |

### Environment Tab Controls
| Control | Signal | Handler | Line |
|---------|--------|---------|------|
| `lst_environments` (QListWidget) | `itemSelectionChanged` | `on_environment_selected_from_list()` | 989 |
| `btn_refresh_env` (QPushButton) | `clicked` | `_refresh_environments()` | 996 |
| `btn_load_env` (QPushButton) | `clicked` | `_load_environment()` | 1002 |

### Gesture Tab Controls
| Control | Signal | Handler | Line |
|---------|--------|---------|------|
| `gesture_controls` | `gesture_mapping_changed` | `on_gesture_mapping_changed()` | 1043 |
| `gesture_controls` | `gesture_recording_changed` | `on_gesture_recording_changed()` | 1044 |

### Settings Tab Controls
| Control | Signal | Handler | Line |
|---------|--------|---------|------|
| `chk_show_fps` (QCheckBox) | `stateChanged` | `update_setting('show_fps', ...)` | 1064 |
| `chk_enable_voice` (QCheckBox) | `stateChanged` | `update_setting('enable_voice', ...)` | 1070 |
| `chk_enable_gestures` (QCheckBox) | `stateChanged` | `update_setting('enable_gestures', ...)` | 1076 |
| `chk_mirror_display` (QCheckBox) | `stateChanged` | `update_setting('mirror_display', ...)` | 1081 |
| `cmb_mirror_source` (QComboBox) | `currentIndexChanged` | `_on_mirror_source_changed()` | 1101 |

### Timer Connections
| Timer | Interval | Handler | Purpose |
|-------|----------|---------|---------|
| `_vr_view_timer` | 200ms | `_publish_vr_view_frame()` | Stream VR view frames |
| `vr_detection_timer` | 3000ms | `_check_vr_device_connection()` | Detect VR hardware |
| `vr_tracking_timer` | 100ms | `_vr_tracking_update()` | Real-time tracking |
| `update_timer` | 1000ms | `request_metrics_update()` | Sentience metrics |

### VRQTSignals (Internal Qt Signals)
| Signal | Connected To | Line |
|--------|--------------|------|
| `signals.status_updated` | `update_status()` | 1125 |
| `signals.connection_changed` | `on_connection_changed()` | 1126 |
| `signals.device_updated` | `update_device_info()` | 1127 |
| `signals.tracking_updated` | `update_tracking()` | 1128 |
| `signals.environment_updated` | `update_environment()` | 1129 |
| `signals.performance_updated` | `update_performance()` | 1130 |
| `signals.gesture_detected` | `on_gesture_detected()` | 1131 |
| `signals.voice_command` | `on_voice_command()` | 1132 |
| `signals.ai_response` | `on_ai_response()` | 1133 |
| `signals.shutdown_requested` | `vr_worker.shutdown()` | 1169 |

### VRSystemWorker Thread Signals
| Worker Signal | Connected To | Line |
|---------------|--------------|------|
| `vr_worker.status_updated` | `signals.status_updated` | 1159 |
| `vr_worker.connection_changed` | `signals.connection_changed` | 1160 |
| `vr_worker.device_updated` | `signals.device_updated` | 1161 |
| `vr_worker.tracking_updated` | `signals.tracking_updated` | 1162 |
| `vr_worker.environment_updated` | `signals.environment_updated` | 1163 |
| `vr_worker.performance_updated` | `signals.performance_updated` | 1164 |
| `vr_worker.gesture_detected` | `signals.gesture_detected` | 1165 |
| `vr_worker.voice_command` | `signals.voice_command` | 1166 |
| `vr_worker.ai_response` | `signals.ai_response` | 1167 |

### Redis Manager Signals
| Signal | Handler | Line |
|--------|---------|------|
| `redis_manager.signals.connected` | `on_redis_connected()` | 647 |
| `redis_manager.signals.disconnected` | `on_redis_disconnected()` | 648 |
| `redis_manager.signals.message_received` | `on_redis_message()` | 649 |

### VRSentienceMonitor Controls (vr_sentience_monitor.py)
| Control | Signal | Handler | Line |
|---------|--------|---------|------|
| `toggle_button` (QPushButton) | `clicked` | `toggle_monitoring()` | 250 |
| `threshold_slider` (QSlider) | `valueChanged` | `update_threshold()` | 253 |
| `update_timer` (QTimer) | `timeout` | `request_metrics_update()` | 277 |

---

## 📊 BUTTON MAPPING (4 BUTTONS)

### Button 1: REFRESH

**Event Listener:**
```python
self.refresh_button.clicked.connect(self._on_refresh_clicked)
```

**Event Handler:**
```python
def _on_refresh_clicked(self):
    """Refresh VR environments list"""
    try:
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("⏳ Refreshing...")
        
        # Publish refresh event
        self.event_bus.publish('vr.refresh', {
            'timestamp': time.time()
        })
        
        logger.info("🔄 Refreshing VR environments...")
        
    except Exception as e:
        logger.error(f"VR refresh failed: {e}")
    finally:
        QTimer.singleShot(2000, lambda: self.refresh_button.setEnabled(True))
        QTimer.singleShot(2000, lambda: self.refresh_button.setText("🔄 Refresh"))
```

**Backend Processing:**
```python
# File: core/vr_system.py
class VRSystem:
    async def _handle_refresh(self, event_data):
        """Refresh available VR environments"""
        try:
            # Scan for VR environments
            environments = self._scan_environments()
            
            # Check VR hardware
            vr_hardware = self._detect_vr_hardware()
            
            # Get environment stats
            env_stats = []
            for env in environments:
                stats = {
                    'name': env['name'],
                    'type': env['type'],
                    'size': env['size'],
                    'last_used': env.get('last_used'),
                    'quality': env.get('quality', 'high')
                }
                env_stats.append(stats)
            
            logger.info(f"✅ Found {len(environments)} VR environments")
            
            # Publish results
            await self.event_bus.publish('vr.environments_loaded', {
                'environments': env_stats,
                'hardware': vr_hardware,
                'count': len(environments)
            })
            
        except Exception as e:
            logger.error(f"VR refresh error: {e}")
            await self.event_bus.publish('vr.refresh_failed', {
                'error': str(e)
            })
    
    def _scan_environments(self):
        """Scan for available VR environments"""
        import os
        
        vr_dir = 'vr_environments'
        environments = []
        
        if os.path.exists(vr_dir):
            for file in os.listdir(vr_dir):
                if file.endswith('.vrenv'):
                    environments.append({
                        'name': file[:-6],
                        'type': 'custom',
                        'size': os.path.getsize(os.path.join(vr_dir, file)),
                        'path': os.path.join(vr_dir, file)
                    })
        
        # Add default environments
        default_envs = [
            {'name': 'Trading Floor', 'type': 'default', 'size': 0},
            {'name': 'Mining Cave', 'type': 'default', 'size': 0},
            {'name': 'Blockchain Space', 'type': 'default', 'size': 0},
            {'name': 'AI Nexus', 'type': 'default', 'size': 0}
        ]
        
        return environments + default_envs
    
    def _detect_vr_hardware(self):
        """Detect connected VR hardware"""
        hardware = {
            'headset': None,
            'controllers': [],
            'tracking': None
        }
        
        try:
            # Try to detect Oculus/Meta Quest
            import subprocess
            result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
            if 'device' in result.stdout:
                hardware['headset'] = 'Oculus Quest'
        except:
            pass
        
        # Check for SteamVR
        try:
            import os
            steamvr_path = os.path.expanduser('~/.steam/steam/steamapps/common/SteamVR')
            if os.path.exists(steamvr_path):
                hardware['tracking'] = 'SteamVR'
        except:
            pass
        
        return hardware
```

---

### Button 2: LOAD ENVIRONMENT

**Event Listener:**
```python
self.load_button.clicked.connect(self._on_load_clicked)
```

**Event Handler:**
```python
def _on_load_clicked(self):
    """Load selected VR environment"""
    try:
        selected = self.env_list.currentRow()
        
        if selected < 0:
            self._show_error("Please select an environment")
            return
        
        env_name = self.env_list.item(selected).text()
        
        # Disable button during load
        self.load_button.setEnabled(False)
        self.load_button.setText("⏳ Loading...")
        
        # Publish load event
        self.event_bus.publish('vr.load_environment', {
            'environment': env_name,
            'quality': self.quality_combo.currentText(),
            'timestamp': time.time()
        })
        
        logger.info(f"🔥 Loading VR environment: {env_name}")
        
    except Exception as e:
        logger.error(f"VR load failed: {e}")
        self._show_error(str(e))
```

**Backend Processing:**
```python
async def _handle_load_environment(self, event_data):
    """Load VR environment and initialize scene"""
    env_name = event_data['environment']
    quality = event_data.get('quality', 'high')
    
    try:
        logger.info(f"Loading VR environment: {env_name}")
        
        # Load environment data
        env_data = self._load_environment_data(env_name)
        
        # Initialize VR scene
        scene = self._create_vr_scene(env_data, quality)
        
        # Setup VR camera
        camera = self._setup_vr_camera()
        
        # Load 3D objects
        objects = self._load_3d_objects(env_data)
        
        # Setup lighting
        lighting = self._setup_lighting(quality)
        
        # Initialize VR controllers
        controllers = self._init_controllers()
        
        logger.info(f"✅ VR environment loaded: {env_name}")
        
        # Publish success
        await self.event_bus.publish('vr.environment_loaded', {
            'environment': env_name,
            'scene_objects': len(objects),
            'quality': quality,
            'ready': True
        })
        
    except Exception as e:
        logger.error(f"Failed to load VR environment: {e}")
        await self.event_bus.publish('vr.load_failed', {
            'environment': env_name,
            'error': str(e)
        })

def _create_vr_scene(self, env_data, quality):
    """Create VR scene with 3D objects"""
    scene = {
        'name': env_data['name'],
        'objects': [],
        'skybox': self._create_skybox(quality),
        'ground': self._create_ground(),
        'lighting': [],
        'quality_level': quality
    }
    
    # Add environment-specific objects
    if env_data['name'] == 'Trading Floor':
        scene['objects'].extend([
            {'type': 'monitor', 'pos': (0, 1, -2), 'data': 'trading_charts'},
            {'type': 'desk', 'pos': (0, 0, 0)},
            {'type': 'chair', 'pos': (0, 0, 1)}
        ])
    elif env_data['name'] == 'Mining Cave':
        scene['objects'].extend([
            {'type': 'mining_rig', 'pos': (-2, 0, -2)},
            {'type': 'mining_rig', 'pos': (2, 0, -2)},
            {'type': 'monitor', 'pos': (0, 1, -1), 'data': 'mining_stats'}
        ])
    elif env_data['name'] == 'AI Nexus':
        scene['objects'].extend([
            {'type': 'hologram', 'pos': (0, 1.5, -2), 'data': 'thoth_ai'},
            {'type': 'neural_network', 'pos': (0, 0, 0), 'animated': True}
        ])
    
    return scene
```

**Data Flow:**
```
User selects environment → Click "Load Environment"
    ↓
_on_load_clicked()
    ↓
Get selected environment name
    ↓
event_bus.publish('vr.load_environment')
    ↓
VR System Backend
    ↓
Load environment configuration
    ↓
Create VR scene with 3D objects
    ↓
Setup camera and controllers
    ↓
Load textures and models
    ↓
Initialize lighting
    ↓
event_bus.publish('vr.environment_loaded')
    ↓
GUI updates: "Environment Ready"
    ↓
VR view renders scene
```

---

### Button 3: RESET TO DEFAULTS

**Event Listener:**
```python
self.reset_button.clicked.connect(self._on_reset_clicked)
```

**Event Handler:**
```python
def _on_reset_clicked(self):
    """Reset VR settings to defaults"""
    reply = QMessageBox.question(
        self,
        'Reset VR Settings',
        'Reset all VR settings to default values?',
        QMessageBox.Yes | QMessageBox.No
    )
    
    if reply == QMessageBox.Yes:
        self.event_bus.publish('vr.reset_settings', {})
```

**Backend:**
```python
async def _handle_reset_settings(self, event_data):
    """Reset VR settings to defaults"""
    default_settings = {
        'quality': 'high',
        'fov': 110,
        'ipd': 63,  # Interpupillary distance (mm)
        'tracking_mode': 'inside-out',
        'comfort_mode': True,
        'snap_turning': False,
        'movement_speed': 1.0
    }
    
    # Apply defaults
    self.settings = default_settings
    
    # Save to config
    self._save_settings()
    
    await self.event_bus.publish('vr.settings_reset', {
        'settings': default_settings
    })
```

---

### Button 4: VR MODE TOGGLE (Implicit)

**Event Handler:**
```python
def _toggle_vr_mode(self, enabled):
    """Toggle VR mode on/off"""
    if enabled:
        # Enter VR mode
        self.event_bus.publish('vr.mode_enter', {})
    else:
        # Exit VR mode
        self.event_bus.publish('vr.mode_exit', {})
```

**Backend:**
```python
async def _handle_enter_vr_mode(self, event_data):
    """Enter VR mode"""
    try:
        # Check hardware
        if not self._check_vr_hardware():
            raise Exception("No VR hardware detected")
        
        # Initialize VR runtime
        self._init_vr_runtime()
        
        # Start VR rendering loop
        self._start_vr_loop()
        
        logger.info("✅ Entered VR mode")
        
        await self.event_bus.publish('vr.mode_active', {
            'mode': 'vr'
        })
        
    except Exception as e:
        logger.error(f"Failed to enter VR mode: {e}")
        await self.event_bus.publish('vr.mode_failed', {
            'error': str(e)
        })
```

---

## 🥽 VR INTEGRATION

### Supported VR Systems

**Hardware Support:**
- Meta Quest (1, 2, 3, Pro)
- Valve Index
- HTC Vive
- Windows Mixed Reality
- PSVR (limited)

**Software Integration:**
- OpenVR/SteamVR
- Oculus SDK
- OpenXR (cross-platform)

---

## 📡 COMPLETE EVENT BUS BINDINGS

### VR Tab Publishes (event_bus.publish)
| Event Topic | Method | Trigger | Data |
|-------------|--------|---------|------|
| `ui.telemetry` | `_emit_ui_telemetry()` | All UI actions | `{component, event_type, success, metadata}` |
| `vr.refresh` | `_refresh_environments()` | Refresh button | `{environments: []}` |
| `vision.stream.vr.frame` | `_publish_vr_view_frame()` | Timer (200ms) | `{frame: np.ndarray, timestamp}` |
| `vision.stream.vr.status` | `_publish_vr_stream_status()` | Mirror toggle | `{active, source, mirror_mode, runtime}` |
| `vr.status` (Redis) | `update_status()` | Status changes | `{message, level}` |

### VR Tab Subscribes (event_bus.subscribe)
| Event Topic | Handler | Purpose |
|-------------|---------|---------|
| `vr.environments_updated` | `_handle_vr_environments()` | Receive environment list |
| `vr.status` | `_handle_vr_status()` | Receive VR status updates |
| `vr.command` | `_handle_vr_command()` | Receive VR commands |
| `thoth.thinking` | `_handle_brain_thinking()` | AI thinking state |
| `thoth.status` | `_handle_brain_status()` | AI connection status |

### VRSentienceMonitor Publishes
| Event Topic | Method | Trigger | Data |
|-------------|--------|---------|------|
| `ui.telemetry` | `_emit_ui_telemetry()` | All UI actions | `{component: "vr_sentience", ...}` |
| `vr.sentience.metrics.request` | `request_metrics_update()` | Timer (1s) | `{timestamp}` |
| `vr.sentience.toggle` | `toggle_monitoring()` | Toggle button | `{enabled, timestamp}` |
| `vr.sentience.threshold.adjust` | `update_threshold()` | Slider change | `{threshold, timestamp}` |

### VRSentienceMonitor Subscribes
| Event Topic | Handler | Purpose |
|-------------|---------|---------|
| `vr.sentience.metrics.update` | `_on_metrics_update()` | Receive metrics data |
| `vr.sentience.status` | `_on_status_update()` | Receive status changes |
| `vr.experience.enhance` | `_on_experience_enhanced()` | Experience enhancement |
| `vr.experience.revert` | `_on_experience_reverted()` | Experience reversion |

### Legacy Event Topics (Original)
| Event Topic | Publisher | Subscriber | Trigger | Data |
|-------------|-----------|------------|---------|------|
| `vr.refresh` | VR GUI | VR System | Refresh button | Empty |
| `vr.environments_loaded` | VR System | VR GUI | Scan complete | Environment list |
| `vr.load_environment` | VR GUI | VR System | Load button | Environment name |
| `vr.environment_loaded` | VR System | VR GUI | Load complete | Scene data |
| `vr.reset_settings` | VR GUI | VR System | Reset button | Empty |
| `vr.settings_reset` | VR System | VR GUI | Reset complete | Default settings |
| `vr.mode_enter` | VR GUI | VR System | VR mode toggle | Empty |
| `vr.mode_active` | VR System | VR GUI | VR mode entered | Mode status |

---

## 📡 UI TELEMETRY & TELEMETRYCOLLECTOR

The VR tab emits UI telemetry events on `ui.telemetry` for connection toggles,
calibration, view resets, settings resets, and environment selection.

- **Channel:** `ui.telemetry`
- **Component:** `vr`
- **Representative event types:**
  - `vr.toggle_connection_clicked`
  - `vr.calibrate_clicked`
  - `vr.reset_view_clicked`
  - `vr.reset_settings_clicked`
  - `vr.environment_selected`

Example payload shape:

```json
{
  "component": "vr",
  "channel": "ui.telemetry",
  "event_type": "vr.environment_selected",
  "timestamp": "2025-10-24T12:34:56Z",
  "success": true,
  "error": null,
  "metadata": {"environment_id": "Trading Floor"}
}
```

These events are consumed by the shared **TelemetryCollector** for unified,
non-blocking VR UI telemetry.

## ✅ VERIFICATION

**Test VR System:**

```bash
# 1. Launch Kingdom AI
python3 -B kingdom_ai_perfect.py

# 2. Go to VR tab

# 3. Click "Refresh"
# Expected: List of available environments

# 4. Select "Trading Floor"

# 5. Click "Load Environment"

# Monitor logs:
tail -f logs/kingdom_error.log | grep vr

# Expected:
# 🔄 Refreshing VR environments...
# ✅ Found 4 VR environments
# 🔥 Loading VR environment: Trading Floor
# ✅ VR environment loaded: Trading Floor

# Note: Full VR requires hardware
# Without VR headset: Preview mode in 2D window
```

---

**Status:** ✅ COMPLETE - VR system integration (works with/without hardware)

---

## 🔄 DEFERRED INITIALIZATION PATTERNS

### QTimer.singleShot Deferred Calls
| Delay | Method | Purpose | Line |
|-------|--------|---------|------|
| 100ms | `_start_vr_device_monitoring()` | Wait for __init__ to complete | 530 |
| 1000ms | `_deferred_redis_init()` | Wait for Redis Quantum Nexus | 534 |
| 4200ms | `subscribe_all()` | Deferred EventBus subscriptions | 1672 |

---

## 🧵 THREADING ARCHITECTURE

### QThread Workers
| Thread | Worker Class | Purpose |
|--------|--------------|---------|
| `vr_thread` | `VRSystemWorker` | VR system background processing |
| `VRDetectionThread` | (inline class) | Non-blocking VR hardware detection |

### Worker Signals
The `VRSystemWorker` mirrors all `VRQTSignals` for thread-safe communication:
- `status_updated(str, str)` - message, level
- `connection_changed(bool)` - connected
- `device_updated(dict)` - device data
- `tracking_updated(dict)` - tracking data
- `environment_updated(dict)` - environment data
- `performance_updated(dict)` - performance data
- `gesture_detected(dict)` - gesture data
- `voice_command(dict)` - voice command data
- `ai_response(dict)` - AI response data

---

## 🛑 CLEANUP & SHUTDOWN

### cleanup() Method (lines 2305-2361)
Stops all timers and threads on tab close:
1. Disables `_timers_enabled` flag
2. Calls `_sync_vr_timers()` to stop all timers
3. Calls `vr_worker.shutdown()` if running
4. Calls `vr_thread.quit()` and `wait()`
5. Stops individual timers: `update_timer`, `_vr_view_timer`, `vr_detection_timer`, `vr_tracking_timer`, `device_monitor_timer`
6. Requests interruption on `_vr_detection_thread`
7. Disconnects `redis_manager`

---

## 📋 HANDLER → BACKEND CALL MAPPING

| Handler | Backend Call(s) | EventBus Topic(s) |
|---------|-----------------|-------------------|
| `toggle_connection()` | `connect_vr()` or `disconnect_vr()` → `vr_worker.initialize()` or `vr_worker.shutdown()` | `ui.telemetry` (vr.toggle_connection_clicked) |
| `calibrate_vr()` | `signals.calibration_requested.emit()` | `ui.telemetry` (vr.calibrate_clicked) |
| `reset_view()` | `signals.reset_view_requested.emit()` | `ui.telemetry` (vr.reset_view_clicked) |
| `on_environment_selected()` | `signals.environment_change_requested.emit()` | `ui.telemetry` (vr.environment_selected) |
| `_refresh_environments()` | Local list update | `vr.refresh` |
| `_load_environment()` | `_central_thoth.load_vr_environment()` | (status update) |
| `update_setting()` | `signals.settings_updated.emit()` | `vision.stream.vr.status` |
| `toggle_monitoring()` | (UI update) | `vr.sentience.toggle` |
| `update_threshold()` | (UI update) | `vr.sentience.threshold.adjust` |
| `request_metrics_update()` | (request) | `vr.sentience.metrics.request` |

---

## 📅 LAST UPDATED

**Date:** 2025-12-24
**Session:** VR Tab Forensic Enumeration
**Changes:**
- Added complete Qt signal connection mappings (30+ connections)
- Added VRSentienceMonitor control mappings
- Added complete EventBus publish/subscribe tables
- Added threading architecture documentation
- Added deferred initialization patterns
- Added cleanup/shutdown flow
- Added handler → backend call mapping table

---

## 🧠 VL-JEPA Integration (Dec 31, 2025)

### New Attributes in `core/vr_system.py`
```python
self._vl_jepa_enabled = True
self._vl_jepa = None  # Lazy loaded
self._zero_latency_mode = True  # Mirror-like instant feedback
```

### New Event Subscription
| Event | Handler | Purpose |
|-------|---------|---------|
| `vr.frame` | `_on_vr_frame()` | VL-JEPA vision processing |

### New Method: `_on_vr_frame()`
```python
async def _on_vr_frame(self, data: Dict[str, Any]):
    """SOTA 2026: Process VR frame with VL-JEPA for AI-powered vision understanding."""
    if not self._vl_jepa_enabled:
        return
    
    # Lazy load VL-JEPA
    if self._vl_jepa is None:
        from core.vl_jepa import VLJEPAIntegration
        self._vl_jepa = VLJEPAIntegration(event_bus=self.event_bus)
    
    # Send to VL-JEPA for gesture/scene understanding (async, non-blocking)
    self.event_bus.publish("vl_jepa.vr_frame", {
        "frame": frame,
        "timestamp": timestamp,
        "device": "vr_headset",
        "tracking": {
            "head_position": self.head_position,
            "head_rotation": self.head_rotation,
        }
    })
```

### VL-JEPA Output Events
| Event | Data | Purpose |
|-------|------|---------|
| `vl_jepa.gesture_recognized` | `{gesture, confidence, prototype_id}` | Gesture detection |
| `vl_jepa.scene_understanding` | `{description, embedding}` | Scene analysis |
