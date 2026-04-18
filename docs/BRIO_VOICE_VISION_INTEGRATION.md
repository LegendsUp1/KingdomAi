# Brio Webcam + Microphone Integration (Kingdom AI)

This document captures the Brio webcam + microphone integration fixes applied to the Kingdom AI system, with a focus on:

- Ensuring `VoiceManager` is initialized and registered on the global `EventBus` so STT works (`voice.listen` -> `voice.recognition`).
- Ensuring the Thoth AI tab automatically shows the vision preview when the vision stream is active.
- Ensuring microphone selection prioritizes Logitech/Brio devices, with hotplug-friendly re-detection.
- Preventing the main GUI window from disappearing due to garbage-collection.

## Scope

Primary entry point:

- `kingdom_ai_perfect.py`

Primary UI:

- `gui/qt_frames/thoth_qt.py` (Thoth AI tab)

Primary voice runtime:

- `core/voice_manager.py`

Primary vision runtime:

- `components/vision_stream.py`

## Summary of Changes

## 1) VoiceManager initialization + registration

### Problem

The system had TTS wiring via the voice brain service, but STT events (`voice.listen`/`voice.recognition`) were not consistently wired because `core.voice_manager.VoiceManager` was not guaranteed to be created, initialized, and registered on the global `EventBus` during the main launch path.

### Fix

In `kingdom_ai_perfect.py`, right after `VisionStreamComponent` startup, the system now:

- Imports and constructs `VoiceManager(event_bus=event_bus)`
- Awaits `voice_manager.initialize()`
- Registers it via `event_bus.register_component('voice_manager', voice_manager)`

This ensures the voice subsystem subscribes to:

- `voice.listen`
- `voice.recognition` (published by `VoiceManager`)
- `voice.speak` (already used by multiple parts of the system)

## 2) Thoth AI vision preview auto-show

### Problem

The vision stream could be active (auto-started via `vision.stream.start`), but the Thoth AI UI would remain collapsed/hidden, making it look like no frames were coming in.

### Fix

In `gui/qt_frames/thoth_qt.py`, `_update_vision_status_on_main_thread` now:

- Tracks `prev_active` vs `active`.
- When the stream becomes active:
  - Sets `_vision_active = True`.
  - Expands and shows the vision group box (`_vision_container.setChecked(True)` / `.setVisible(True)`).
  - Shows the preview label (`_vision_preview_label.setVisible(True)`).
  - Synchronizes the camera toggle state without triggering recursion.
- When the stream becomes inactive:
  - Clears and hides the preview label.

This makes the Thoth AI vision panel self-healing when the stream is started externally.

## 3) Microphone selection + hotplug re-detection

### Problem

Windows audio devices can change indices when devices are plugged/unplugged or when default devices change. A previously working mic index may become invalid.

### Fix

In `core/voice_manager.py`:

- `_detect_webcam_microphone(force: bool = False)` now supports:
  - Respecting an explicitly configured `mic_device_index` (if provided).
  - A `force=True` path that re-scans devices and re-selects the best candidate.
- Device selection uses **scored keyword preference** (strongly prefers Brio/Logitech-class mics).
- On listen start:
  - Both `_start_listening_sync()` and `start_listening()` re-run detection with `force=True`.
- In `_listen_worker`, microphone initialization is wrapped with retry logic:
  - If `sr.Microphone(device_index=...)` fails, it re-detects with `force=True` and retries.

This improves reliability for:

- Brio/Logitech microphones
- USB hotplug scenarios
- Device index changes after reboot

### Additional robustness fix

`core/voice_manager.py` previously referenced `PriorityQueue()` / `Queue()` without importing them, which could raise a `NameError` if `_load_config()` was used.

This was corrected to use:

- `queue.PriorityQueue()`
- `queue.Queue()`

## 4) Prevent GUI window from disappearing (GC guard)

### Problem

If the top-level `main_window` object is not held by a strong reference, Python can garbage-collect it, which closes the window and can look like “the GUI never appeared”.

### Fix

In `kingdom_ai_perfect.py` (inside `launch_kingdom_async()`), after `create_complete_kingdom_gui()` returns `main_window`, the code now stores a strong reference:

- On the `QApplication` instance: `app._kingdom_main_window = main_window`
- In a module-global: `_KINGDOM_MAIN_WINDOW = main_window`

## 5) AI runtime documentation access (ChatWidget + Ollama Brain)

### Objective

Ensure this documentation file is accessible at runtime to the AI pipeline (ChatWidget → `ai.request` → UnifiedAIRouter → BrainRouter → Ollama).

### SystemKnowledgeLoader integration

The system uses `core/system_knowledge_loader.py` as the authoritative documentation ingestion mechanism for runtime AI knowledge.

This document is included in the loader's preload list:

- `SystemKnowledgeLoader.PRIORITY_DOCS` includes `BRIO_VOICE_VISION_INTEGRATION.md`

So it is loaded and cached on startup.

### Startup wiring (main entry point)

In `kingdom_ai_perfect.py`, the production startup path initializes and registers the loader:

- `knowledge_loader = get_knowledge_loader(event_bus=event_bus)`
- `event_bus.register_component("system_knowledge_loader", knowledge_loader)`

This ensures the loader is available via `event_bus.get_component("system_knowledge_loader")`.

### BrainRouter conditional documentation injection

In `kingdom_ai/ai/brain_router.py`, the router conditionally injects a bounded excerpt of this doc into the model prompt when the user prompt is relevant (e.g. contains `brio`, `logitech`, or `voice vision integration`).

This makes the Ollama brain able to answer questions about the Brio voice+vision wiring without requiring manual copy/paste.

## Event Bus Contracts (What to Expect)

Vision stream:

- `vision.stream.start` (request start)
- `vision.stream.stop` (request stop)
- `vision.stream.status` payload:
  - `{"active": bool, "url": str, "error"?: str}`
- `vision.stream.frame` payload:
  - `{"frame": np.ndarray, "timestamp": float}`

Voice:

- `voice.listen` payload:
  - `{"action": "start" | "stop"}`
- `voice.recognition` payload:
  - `{"text": str, "confidence": float, "timestamp": str, ...}`
- `voice.speak` payload:
  - `{"text": str, "voice"?: str, "priority"?: str, ...}`

## How to Verify

## A) Startup verification (logs)

When you run the system, look for:

- `VisionStreamComponent initialized`
- `VoiceManager initialized and REGISTERED`

## B) Thoth AI tab: Vision

- Ensure the vision stream is started (either via auto-start or the UI toggle).
- In the Thoth AI tab:
  - The vision group box should auto-expand when the stream reports active.
  - The preview should show frames once they arrive.

If you are using the Brio MJPEG server, common URLs:

- `http://localhost:8090/brio.mjpg`
- `http://127.0.0.1:8090/brio.mjpg`

## C) Thoth AI tab: Voice input

- Click the mic button.
- The UI should show the listening confirmation message.
- When speech is recognized:
  - A `voice.recognition` event is emitted.
  - Thoth UI should receive it and route text into chat.

## Troubleshooting

## Vision preview stays blank

- Confirm `vision.stream.status` is reporting `active=True`.
- Confirm the source URL/device can be opened by OpenCV.
- If MJPEG is used, confirm the MJPEG server is running and reachable.

## WSL2 Webcam Display (Dec 31, 2025) - Updated Jan 8, 2026

### Problem
`cv2.imshow()` doesn't work in WSL2 due to missing GTK+/Cocoa support. PyQt6 display showed black screen or frozen image.

### Root Causes & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Black screen | WSLg Wayland display issues | Set `QT_QPA_PLATFORM=xcb` BEFORE PyQt6 import |
| No frames received | MJPEG multipart format not parsed correctly | Find JPEG markers `\xff\xd8`/`\xff\xd9` within multipart stream |
| Still image (not live) | Qt signal flooding overwhelmed event loop | Use QTimer polling (120 FPS) instead of signal emissions |
| Webcam light off | ffmpeg using unsupported 60 FPS and pix_fmt | Default to 30 FPS, removed `-pix_fmt yuyv422` |
| **Frozen display (Jan 2026)** | **ffmpeg gets STUCK sending same frame** | **Added `/restart` endpoint + `force_restart()` method** |

### SOTA 2026 Zero-Latency Optimizations (Jan 8, 2026)

Based on extensive research, the following optimizations achieve near-zero latency:

#### ffmpeg Server Optimizations (`brio_mjpeg_server.py`)
```python
# SOTA 2026 Ultra-low latency flags
"-fflags", "+nobuffer+flush_packets",  # Disable buffering
"-flags", "low_delay",                  # Enable low delay mode
"-probesize", "32",                     # Minimal probe for fast start
"-analyzeduration", "0",                # Skip analysis for instant start
"-use_wallclock_as_timestamps", "1",    # Accurate timestamps
"-thread_queue_size", "1024",           # Smooth capture queue
"-qscale:v", "3",                       # Higher quality (lower = better)
```

#### Client Stream Optimizations (`components/vision_stream.py`)
- **Larger chunks (8192 bytes)**: Faster buffer fill, lower syscall overhead
- **Extract ALL frames per chunk**: Process every complete JPEG in buffer
- **Minimal buffer management**: Keep only last 2 bytes when no marker found
- **Skip AI on most frames**: VL-JEPA processes every 5th frame only

### Diagnostic Tools

1. **`test_frame_motion_detector.py`** - Detects if stream is stuck vs live
   ```bash
   python test_frame_motion_detector.py
   # Output: "FRAMES ARE CHANGING" (good) or "ALL FRAMES IDENTICAL" (stuck)
   ```

2. **Restart stuck ffmpeg from WSL2**:
   ```bash
   curl -s http://172.20.0.1:8090/restart
   ```

### Files Modified

1. **`components/vision_stream.py`**
   - Added `_zero_latency_mode = True` (default) - skips slow filters for mirror-like speed
   - Added `_enhance_enabled = False` (default) - enhancement disabled for zero latency
   - Added `_process_vl_jepa_async()` - non-blocking VL-JEPA AI vision processing
   - Added `set_zero_latency()` method to toggle mirror mode
   - **SOTA 2026**: 8192 byte chunks, extract ALL frames per chunk
   - VL-JEPA integration via `vl_jepa.vision_frame` events

2. **`core/vr_system.py`**
   - Added `_vl_jepa_enabled`, `_vl_jepa`, `_zero_latency_mode` attributes
   - Added `_on_vr_frame()` method for VL-JEPA VR vision processing
   - Subscribes to `vr.frame` events for AI gesture/scene understanding

3. **`brio_mjpeg_server.py`**
   - Removed `-pix_fmt yuyv422` (not supported by all webcams)
   - Default FPS is 30 (60 FPS not supported by Brio 100)
   - **SOTA 2026**: Added ultra-low latency ffmpeg flags
   - **Added `/restart` endpoint** to fix stuck ffmpeg
   - **Added `force_restart()` method** for programmatic restart

4. **`test_webcam_live_wsl2_v3.py`** (working test script)
   - QTimer at 8ms (120 FPS) for instant feedback
   - First-frame signaling with `threading.Event()`
   - 8192 byte chunks for faster initial buffer fill

5. **`test_frame_motion_detector.py`** (diagnostic tool)
   - Captures 20 frames, computes MD5 hashes
   - Reports unique vs identical frames
   - Detects stuck ffmpeg vs live stream

### Starting Webcam Server (Windows)

```powershell
# Method 1: Using the auto-start script
cd "C:\Users\Yeyian PC\Documents\Python Scripts\New folder"
.\start_brio_mjpeg_server.ps1

# Method 2: Direct launch
$env:KINGDOM_VISION_MODE = "fast"
python brio_mjpeg_server.py
```

### Testing in WSL2

```bash
# Test motion detection first
python test_frame_motion_detector.py

# If motion detected, run display test
python test_webcam_live_wsl2_v3.py
```

### Architecture Flow

```
[Windows Webcam] → [ffmpeg MJPEG] → [HTTP :8090] → [WSL2 VisionStreamComponent]
                        ↓                                    ↓
               [SOTA 2026 flags]              [8192 byte chunks, extract ALL frames]
                        ↓                                    ↓
               [/restart endpoint]            [ZERO LATENCY] → [Qt Display immediately]
                                                             ↓
                                              [VL-JEPA Async] → [AI every 5th frame]
```

### Troubleshooting: Frozen Display

If display shows static image but stream FPS counter is incrementing:

1. **Run motion detector**:
   ```bash
   python test_frame_motion_detector.py
   ```

2. **If "ALL FRAMES IDENTICAL"** → ffmpeg is stuck:
   ```bash
   curl -s http://172.20.0.1:8090/restart
   ```

3. **If "FRAMES ARE CHANGING"** → Qt display bug, restart test script

## Voice input does not capture

- Confirm `VoiceManager initialized and REGISTERED` appears in logs.
- Confirm mic permissions and that `SpeechRecognition` works on your machine.
- Try toggling the mic off/on (listen start triggers re-detection).
- Check device names; the selector prioritizes keywords like:
  - `brio`, `logitech`, `c930`, `c922`, `c920`, `webcam`, `camera`, `stream`

## GUI window still not visible

- The system now keeps a strong reference to the main window to prevent GC.
- If it is still not visible:
  - Check if it opened off-screen (multi-monitor/disconnected monitor history).
  - Check for a modal dialog blocking the UI.
  - Check that only **one** `QApplication` exists.

---

Last updated: 2025-12-31
