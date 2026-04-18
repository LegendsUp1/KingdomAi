# Component Cleanup Guide

## Overview

This guide shows how to properly implement cleanup in GUI components to prevent memory leaks and ensure 24-hour stability.

## The Problem

Many components in the codebase create resources (timers, threads, event subscriptions) but never clean them up. This causes:

- **Memory leaks**: Event handlers accumulate in memory
- **Segfaults**: Timers fire after widgets are deleted
- **Resource exhaustion**: Threads never terminate

## The Solution

Every component MUST implement proper cleanup following this pattern:

## Standard Cleanup Pattern

### 1. Component with QTimer

```python
from PyQt6.QtCore import QTimer
from core.resource_cleanup_manager import register_timer

class MyComponent(QWidget):
    def __init__(self):
        super().__init__()
        
        # Create timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update)
        self.update_timer.start(1000)
        
        # CRITICAL: Register timer for cleanup tracking
        register_timer(f"my_component_update_timer_{id(self)}", self.update_timer)
    
    def cleanup(self):
        """Clean up resources - called on shutdown."""
        # Stop and delete timer
        if hasattr(self, 'update_timer') and self.update_timer:
            self.update_timer.stop()
            self.update_timer.deleteLater()
            self.update_timer = None
    
    def closeEvent(self, event):
        """Handle close event."""
        self.cleanup()
        super().closeEvent(event)
```

### 2. Component with QThread

```python
from PyQt6.QtCore import QThread
from core.resource_cleanup_manager import register_thread

class MyComponent(QWidget):
    def __init__(self):
        super().__init__()
        
        # Create worker thread
        self.worker_thread = QThread()
        self.worker = MyWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()
        
        # CRITICAL: Register thread for cleanup tracking
        register_thread(f"my_component_worker_{id(self)}", self.worker_thread)
    
    def cleanup(self):
        """Clean up resources - called on shutdown."""
        # Stop worker thread
        if hasattr(self, 'worker_thread') and self.worker_thread:
            if self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait(5000)  # Wait up to 5 seconds
            self.worker_thread.deleteLater()
            self.worker_thread = None
        
        # Clean up worker
        if hasattr(self, 'worker') and self.worker:
            self.worker.deleteLater()
            self.worker = None
    
    def closeEvent(self, event):
        """Handle close event."""
        self.cleanup()
        super().closeEvent(event)
```

### 3. Component with Event Bus Subscriptions

```python
from core.event_bus import EventBus
from core.resource_cleanup_manager import register_event_subscription

class MyComponent(QWidget):
    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        
        # Subscribe to events
        self.event_bus.subscribe("data.update", self._handle_data_update)
        self.event_bus.subscribe("status.change", self._handle_status_change)
        
        # CRITICAL: Register subscriptions for cleanup tracking
        register_event_subscription(self.event_bus, "data.update", self._handle_data_update)
        register_event_subscription(self.event_bus, "status.change", self._handle_status_change)
    
    def _handle_data_update(self, data):
        """Handle data update event."""
        pass
    
    def _handle_status_change(self, status):
        """Handle status change event."""
        pass
    
    def cleanup(self):
        """Clean up resources - called on shutdown."""
        # Unsubscribe from events
        if self.event_bus:
            try:
                self.event_bus.unsubscribe("data.update", self._handle_data_update)
                self.event_bus.unsubscribe("status.change", self._handle_status_change)
            except Exception as e:
                logger.warning(f"Failed to unsubscribe: {e}")
    
    def closeEvent(self, event):
        """Handle close event."""
        self.cleanup()
        super().closeEvent(event)
```

### 4. Component with Multiple Resources

```python
from PyQt6.QtCore import QTimer, QThread
from core.resource_cleanup_manager import register_timer, register_thread, register_event_subscription

class ComplexComponent(QWidget):
    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        
        # Multiple timers
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update)
        self.update_timer.start(1000)
        register_timer(f"complex_update_timer_{id(self)}", self.update_timer)
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._animate)
        self.animation_timer.start(50)
        register_timer(f"complex_animation_timer_{id(self)}", self.animation_timer)
        
        # Worker thread
        self.worker_thread = QThread()
        self.worker = MyWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()
        register_thread(f"complex_worker_{id(self)}", self.worker_thread)
        
        # Event subscriptions
        self.event_bus.subscribe("data.update", self._handle_data)
        register_event_subscription(self.event_bus, "data.update", self._handle_data)
    
    def cleanup(self):
        """Clean up ALL resources - called on shutdown."""
        # Stop all timers
        for timer_name in ['update_timer', 'animation_timer']:
            if hasattr(self, timer_name):
                timer = getattr(self, timer_name)
                if timer and timer.isActive():
                    timer.stop()
                    timer.deleteLater()
                setattr(self, timer_name, None)
        
        # Stop worker thread
        if hasattr(self, 'worker_thread') and self.worker_thread:
            if self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait(5000)
            self.worker_thread.deleteLater()
            self.worker_thread = None
        
        # Clean up worker
        if hasattr(self, 'worker') and self.worker:
            self.worker.deleteLater()
            self.worker = None
        
        # Unsubscribe from events
        if self.event_bus:
            try:
                self.event_bus.unsubscribe("data.update", self._handle_data)
            except Exception as e:
                logger.warning(f"Failed to unsubscribe: {e}")
    
    def closeEvent(self, event):
        """Handle close event."""
        self.cleanup()
        super().closeEvent(event)
```

## Components That Need Cleanup

Based on code analysis, these components need cleanup() methods added:

### High Priority (Active Timers/Threads)

1. **`gui/qt_frames/vr_qt_tab.py`**
   - 4+ timers: `_vr_view_timer`, `vr_detection_timer`, `vr_tracking_timer`, `device_monitor_timer`
   - 1 thread: `vr_thread`
   - Event subscriptions

2. **`gui/qt_frames/wallet_tab.py`**
   - 3+ timers: `update_timer`, `price_timer`, `_accum_update_timer`
   - Event subscriptions

3. **`gui/qt_frames/trading/trading_window.py`**
   - Multiple timers for market data
   - WebSocket connections
   - Event subscriptions

4. **`gui/widgets/sentience_status_meter.py`**
   - Animation timers: `_animation_timer`, `_timer`, `_update_timer`

5. **`gui/qt_frames/thoth_qt.py`**
   - Worker threads for async operations
   - Voice input thread
   - Event subscriptions

### Medium Priority (Timers Only)

6. **`gui/qt_frames/trading/widgets/positions.py`** - `animation_timer`
7. **`gui/qt_frames/trading/widgets/order_book.py`** - `animation_timer`
8. **`gui/qt_frames/trading/widgets/orders.py`** - `_animation_timer`
9. **`gui/qt_frames/trading/widgets/market_data.py`** - `animation_timer`
10. **`gui/widgets/vr_performance_monitor.py`** - `stats_timer`, `frame_timer`
11. **`gui/widgets/vr_gesture_controls.py`** - `animation_timer`
12. **`gui/widgets/typing_indicator.py`** - `animation_timer`

## Cleanup Checklist

For each component, ensure:

- [ ] `cleanup()` method exists
- [ ] All QTimers are stopped and deleted
- [ ] All QThreads are quit, waited, and deleted
- [ ] All event subscriptions are unsubscribed
- [ ] All resources are registered with ResourceCleanupManager
- [ ] `closeEvent()` calls `cleanup()`
- [ ] `cleanup()` can be called multiple times safely (idempotent)

## Testing Cleanup

### Test 1: Verify cleanup() is called
```python
import logging
logger = logging.getLogger(__name__)

def cleanup(self):
    logger.info(f"Cleanup called for {self.__class__.__name__}")
    # ... rest of cleanup
```

### Test 2: Verify timers are stopped
```python
def cleanup(self):
    if hasattr(self, 'my_timer'):
        assert not self.my_timer.isActive(), "Timer still active after cleanup!"
```

### Test 3: Verify threads are terminated
```python
def cleanup(self):
    if hasattr(self, 'my_thread'):
        assert not self.my_thread.isRunning(), "Thread still running after cleanup!"
```

## Common Mistakes

### ❌ WRONG: Timer not stopped
```python
def closeEvent(self, event):
    # Timer keeps running!
    event.accept()
```

### ✅ CORRECT: Timer stopped and deleted
```python
def closeEvent(self, event):
    if hasattr(self, 'timer') and self.timer:
        self.timer.stop()
        self.timer.deleteLater()
    event.accept()
```

### ❌ WRONG: Thread not waited
```python
def cleanup(self):
    self.thread.quit()  # Thread may still be running!
```

### ✅ CORRECT: Thread quit and waited
```python
def cleanup(self):
    if self.thread.isRunning():
        self.thread.quit()
        self.thread.wait(5000)  # Wait up to 5 seconds
```

### ❌ WRONG: Event subscription never unsubscribed
```python
def __init__(self, event_bus):
    event_bus.subscribe("event", self.handler)
    # Never unsubscribed - memory leak!
```

### ✅ CORRECT: Event subscription unsubscribed
```python
def __init__(self, event_bus):
    self.event_bus = event_bus
    self.event_bus.subscribe("event", self.handler)

def cleanup(self):
    self.event_bus.unsubscribe("event", self.handler)
```

## Summary

**Every component MUST**:
1. Implement `cleanup()` method
2. Stop all timers
3. Terminate all threads
4. Unsubscribe all event handlers
5. Register resources with ResourceCleanupManager
6. Call `cleanup()` in `closeEvent()`

This ensures **no resource leaks** and **24-hour stability**.
