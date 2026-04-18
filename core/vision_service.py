#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Vision Service - Webcam Capture and Streaming

2026 SOTA: Uses MJPEG streaming from Windows host for WSL2 compatibility.
Based on successful test_webcam_live_wsl2_v3.py implementation.

This service handles webcam capture and publishes frames to the event bus
for display in the Thoth AI Vision Stream panel.

CRITICAL: This service bridges the gap between the UI (which publishes
vision.stream.start/stop) and the actual webcam hardware.
"""

import logging
import threading
import time
import subprocess
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to import OpenCV and requests
try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
    logger.info("✅ OpenCV (cv2) available for vision capture")
except ImportError:
    HAS_OPENCV = False
    cv2 = None
    np = None
    logger.warning("⚠️ OpenCV (cv2) not available - vision capture disabled")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None
    logger.warning("⚠️ requests not available - MJPEG streaming disabled")


def _get_windows_host_ip():
    """Get Windows host IP for WSL2 MJPEG streaming.
    
    SOTA 2026: Uses default gateway first (most reliable for accessing Windows services),
    then falls back to resolv.conf nameserver.
    """
    # Method 1: Default gateway (MOST RELIABLE for Windows services like MJPEG)
    try:
        result = subprocess.run(
            ['ip', 'route', 'show', 'default'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.split()
            if len(parts) >= 3 and parts[0] == 'default' and parts[1] == 'via':
                gateway_ip = parts[2]
                logger.info(f"🖥️ Windows host IP from gateway: {gateway_ip}")
                return gateway_ip
    except Exception:
        pass
    
    # Method 2: resolv.conf nameserver (fallback)
    try:
        with open('/etc/resolv.conf', 'r', encoding='utf-8') as rf:
            for line in rf:
                if line.strip().startswith('nameserver'):
                    host_ip = line.strip().split()[1]
                    if not host_ip.startswith('127.'):
                        logger.info(f"🖥️ Windows host IP from resolv.conf: {host_ip}")
                        return host_ip
    except Exception:
        pass
    
    return "172.20.0.1"  # Default WSL2 gateway


def _is_wsl():
    """Check if running in WSL environment."""
    try:
        if os.path.exists('/proc/version'):
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
    except Exception:
        pass
    return False


class VisionService:
    """
    Vision Service for webcam capture and frame streaming.
    
    2026 SOTA: Uses MJPEG streaming from Windows host for WSL2 compatibility.
    Falls back to direct OpenCV capture on native Windows/Linux.
    
    Subscribes to:
        - vision.stream.start: Start webcam capture
        - vision.stream.stop: Stop webcam capture
    
    Publishes:
        - vision.stream.frame: Video frames from webcam
        - vision.stream.status: Camera status updates
    """
    
    def __init__(self, event_bus=None):
        """Initialize the vision service.
        
        Args:
            event_bus: Event bus for publishing/subscribing to events
        """
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        
        # Camera state
        self._capture: Optional[Any] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._running = False
        self._camera_index = 0  # Default to first camera
        self._target_fps = 30
        self._frame_interval = 1.0 / self._target_fps
        
        # WSL2 MJPEG streaming config - env override: MJPEG_HOST, MJPEG_PORT, or MJPEG_URL
        self._in_wsl = _is_wsl()
        self._mjpeg_port = int(os.environ.get("MJPEG_PORT", "8090"))
        self._mjpeg_url = os.environ.get("MJPEG_URL")
        self._frame_lock = threading.Lock()
        self._latest_frame = None
        self._frame_count = 0
        
        if self._mjpeg_url:
            if "/video.mjpg" in self._mjpeg_url:
                self._mjpeg_url = self._mjpeg_url.replace("/video.mjpg", "/brio.mjpg")
            self.logger.info(f"📹 MJPEG URL from env: {self._mjpeg_url}")
        elif self._in_wsl or os.environ.get("MJPEG_HOST"):
            host_ip = os.environ.get("MJPEG_HOST") or (_get_windows_host_ip() if self._in_wsl else "127.0.0.1")
            self._mjpeg_url = self._auto_detect_mjpeg_url(host_ip)
            if self._mjpeg_url:
                self.logger.info(f"📹 Auto-detected MJPEG at: {self._mjpeg_url}")
            else:
                self._mjpeg_url = f"http://{host_ip}:{self._mjpeg_port}/brio.mjpg"
                self.logger.info(f"📹 MJPEG fallback: {self._mjpeg_url}")
        elif not self._in_wsl:
            self._mjpeg_url = None
            self.logger.info("📹 Native Linux: using V4L2 (cv2.VideoCapture) — no MJPEG")
        
        # Subscribe to events
        if event_bus:
            try:
                event_bus.subscribe_sync('vision.stream.start', self._on_start_stream)
                event_bus.subscribe_sync('vision.stream.stop', self._on_stop_stream)
                logger.info("✅ VisionService subscribed to vision.stream.start/stop events")
            except Exception as e:
                logger.error(f"Failed to subscribe to vision events: {e}")
        
        self.logger.info("✅ VisionService initialized")
    
    def _auto_detect_mjpeg_url(self, host_ip: str) -> Optional[str]:
        """Auto-detect MJPEG server URL by trying multiple ports and endpoints.
        
        SOTA 2026: Tries common ports (8090, 8091) and endpoints (/video.mjpg, /brio.mjpg)
        to find a working camera server.
        """
        if not HAS_REQUESTS:
            return None
        
        ports = [8090, 8091, 5000]
        endpoints = ['/brio.mjpg', '/video.mjpg']
        
        for port in ports:
            for endpoint in endpoints:
                url = f"http://{host_ip}:{port}{endpoint}"
                try:
                    resp = requests.get(url, stream=True, timeout=1)
                    if resp.status_code == 200:
                        self.logger.info(f"✅ Found MJPEG server at {url}")
                        return url
                except Exception:
                    pass
        
        # Try localhost as well (for native Windows)
        if host_ip != "127.0.0.1" and host_ip != "localhost":
            for port in ports:
                for endpoint in endpoints:
                    url = f"http://127.0.0.1:{port}{endpoint}"
                    try:
                        resp = requests.get(url, stream=True, timeout=1)
                        if resp.status_code == 200:
                            self.logger.info(f"✅ Found MJPEG server at {url}")
                            return url
                    except Exception:
                        pass
        
        return None
    
    def _on_start_stream(self, data: Dict[str, Any] = None):
        """Handle vision.stream.start event - start webcam capture."""
        try:
            if not HAS_OPENCV:
                self._publish_status(active=False, error="OpenCV not installed")
                self.logger.error("Cannot start vision stream - OpenCV not installed")
                return
            
            if self._running:
                self.logger.info("Vision stream already running")
                return
            
            # Get camera index from data if provided
            if data and 'camera_index' in data:
                self._camera_index = data['camera_index']
            
            self.logger.info(f"Starting vision stream from camera {self._camera_index}")
            
            # Start capture thread
            self._running = True
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name="VisionCaptureThread"
            )
            self._capture_thread.start()
            
        except Exception as e:
            self.logger.error(f"Error starting vision stream: {e}")
            self._publish_status(active=False, error=str(e))
    
    def _on_stop_stream(self, data: Dict[str, Any] = None):
        """Handle vision.stream.stop event - stop webcam capture."""
        try:
            self.logger.info("Stopping vision stream")
            self._running = False
            
            # Wait for capture thread to stop
            if self._capture_thread and self._capture_thread.is_alive():
                self._capture_thread.join(timeout=2.0)
            
            # Release camera
            if self._capture is not None:
                try:
                    self._capture.release()
                except Exception:
                    pass
                self._capture = None
            
            self._publish_status(active=False)
            self.logger.info("Vision stream stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping vision stream: {e}")
    
    def _capture_loop(self):
        """Main capture loop - runs in separate thread.
        
        2026 SOTA: Uses MJPEG when URL is set (env MJPEG_URL/MJPEG_HOST or WSL), else OpenCV.
        """
        if self._mjpeg_url and HAS_REQUESTS:
            self._capture_loop_mjpeg()
        else:
            self._capture_loop_opencv()
    
    def _capture_loop_mjpeg(self):
        """MJPEG streaming capture for WSL2 (from Windows host webcam server)."""
        try:
            if not self._mjpeg_url:
                self.logger.error("MJPEG URL not configured")
                self._publish_status(active=False, error="MJPEG URL not configured")
                return
            
            self.logger.info(f"📹 Connecting to MJPEG stream: {self._mjpeg_url}")
            
            response = requests.get(self._mjpeg_url, stream=True, timeout=10)
            if response.status_code != 200:
                self.logger.error(f"MJPEG server returned HTTP {response.status_code}")
                self._publish_status(active=False, error=f"HTTP {response.status_code}")
                return
            
            self.logger.info("✅ Connected to MJPEG stream!")
            self._publish_status(active=True, url=self._mjpeg_url)
            
            bytes_buffer = b''
            
            for chunk in response.iter_content(chunk_size=8192):
                if not self._running:
                    break
                
                bytes_buffer += chunk
                
                # Extract complete JPEG frames from buffer
                while True:
                    start = bytes_buffer.find(b'\xff\xd8')
                    if start == -1:
                        bytes_buffer = bytes_buffer[-2:] if len(bytes_buffer) > 2 else bytes_buffer
                        break
                    
                    end = bytes_buffer.find(b'\xff\xd9', start)
                    if end == -1:
                        break
                    
                    # Extract and decode JPEG
                    jpg_data = bytes_buffer[start:end+2]
                    bytes_buffer = bytes_buffer[end+2:]
                    
                    frame = cv2.imdecode(np.frombuffer(jpg_data, np.uint8), cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        frame = cv2.flip(frame, 1)  # Mirror for natural view
                        
                        with self._frame_lock:
                            self._latest_frame = frame
                            self._frame_count += 1
                        
                        # ROOT FIX: Cap at 10 FPS to prevent CPU burn
                        time.sleep(0.1)
                        
                        # Publish frame to event bus (publish_sync for immediate delivery to ThothQt buffer)
                        if self.event_bus:
                            try:
                                payload = {
                                    'frame': frame,
                                    'timestamp': time.time(),
                                    'camera_index': self._camera_index,
                                    'width': frame.shape[1],
                                    'height': frame.shape[0]
                                }
                                if hasattr(self.event_bus, 'publish_sync') and callable(self.event_bus.publish_sync):
                                    self.event_bus.publish_sync('vision.stream.frame', payload)
                                else:
                                    self.event_bus.publish('vision.stream.frame', payload)
                            except Exception:
                                pass
            
            response.close()
            
        except Exception as e:
            self.logger.error(f"MJPEG capture error: {e}")
            self._publish_status(active=False, error=str(e))
        finally:
            self._running = False
            self._publish_status(active=False)
    
    def _capture_loop_opencv(self):
        """Direct OpenCV capture for native Windows/Linux."""
        try:
            # Open camera
            self._capture = cv2.VideoCapture(self._camera_index)
            
            if not self._capture.isOpened():
                self.logger.error(f"Failed to open camera {self._camera_index}")
                self._publish_status(active=False, error=f"Cannot open camera {self._camera_index}")
                self._running = False
                return
            
            # Set camera properties for better performance
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._capture.set(cv2.CAP_PROP_FPS, self._target_fps)
            
            self.logger.info(f"✅ Camera {self._camera_index} opened successfully")
            self._publish_status(active=True)
            
            last_frame_time = 0
            
            while self._running:
                try:
                    # Rate limiting
                    current_time = time.time()
                    elapsed = current_time - last_frame_time
                    if elapsed < self._frame_interval:
                        time.sleep(self._frame_interval - elapsed)
                    
                    # Capture frame
                    ret, frame = self._capture.read()
                    
                    if not ret or frame is None:
                        self.logger.warning("Failed to read frame from camera")
                        time.sleep(0.1)
                        continue
                    
                    last_frame_time = time.time()
                    
                    # Publish frame to event bus (publish_sync for immediate delivery to ThothQt buffer)
                    if self.event_bus:
                        try:
                            payload = {
                                'frame': frame,
                                'timestamp': last_frame_time,
                                'camera_index': self._camera_index,
                                'width': frame.shape[1],
                                'height': frame.shape[0]
                            }
                            if hasattr(self.event_bus, 'publish_sync') and callable(self.event_bus.publish_sync):
                                self.event_bus.publish_sync('vision.stream.frame', payload)
                            else:
                                self.event_bus.publish('vision.stream.frame', payload)
                        except Exception as pub_err:
                            self.logger.debug(f"Frame publish error: {pub_err}")
                    
                except Exception as frame_err:
                    self.logger.error(f"Error in capture loop: {frame_err}")
                    time.sleep(0.1)
            
        except Exception as e:
            self.logger.error(f"Vision capture loop error: {e}")
            self._publish_status(active=False, error=str(e))
        finally:
            # Cleanup
            if self._capture is not None:
                try:
                    self._capture.release()
                except Exception:
                    pass
                self._capture = None
            self._running = False
            self._publish_status(active=False)
    
    def _publish_status(self, active: bool, error: str = None, url: str = None):
        """Publish camera status to event bus."""
        if self.event_bus:
            try:
                status_data = {
                    'active': active,
                    'camera_index': self._camera_index,
                    'timestamp': time.time()
                }
                if error:
                    status_data['error'] = error
                if url:
                    status_data['url'] = url
                
                self.event_bus.publish('vision.stream.status', status_data)
            except Exception as e:
                self.logger.debug(f"Status publish error: {e}")
    
    def start(self):
        """Start the vision service (convenience method)."""
        self._on_start_stream({})
    
    def stop(self):
        """Stop the vision service (convenience method)."""
        self._on_stop_stream({})
    
    def is_running(self) -> bool:
        """Check if vision capture is running."""
        return self._running
    
    def cleanup(self):
        """Clean up resources."""
        self.stop()
        self.logger.info("VisionService cleaned up")


# Singleton instance for global access
_vision_service_instance: Optional[VisionService] = None


def get_vision_service(event_bus=None) -> Optional[VisionService]:
    """Get or create the global VisionService instance."""
    global _vision_service_instance
    
    if _vision_service_instance is None and event_bus is not None:
        _vision_service_instance = VisionService(event_bus)
    
    return _vision_service_instance


def initialize_vision_service(event_bus) -> Optional[VisionService]:
    """Initialize the vision service with the given event bus."""
    global _vision_service_instance
    
    if not HAS_OPENCV:
        logger.warning("⚠️ VisionService not initialized - OpenCV not available")
        return None
    
    _vision_service_instance = VisionService(event_bus)
    logger.info("✅ VisionService initialized and ready")
    return _vision_service_instance
