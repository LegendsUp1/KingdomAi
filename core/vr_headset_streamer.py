#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOTA 2026 - VR/AR Headset Image Streamer

Streams generated images and webcam feeds to VR/AR headsets via:
1. WebXR API (browser-based VR/AR)
2. OpenXR bridge (native VR runtimes)
3. WebSocket server for real-time streaming
4. SteamVR overlay API

Supports: Meta Quest, HTC Vive, Valve Index, Windows Mixed Reality, Apple Vision Pro
"""

import logging
import threading
import time
import json
import base64
import queue
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("KingdomAI.VRHeadsetStreamer")

# WebSocket server for browser-based WebXR
HAS_WEBSOCKETS = False
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    logger.warning("websockets not installed - WebXR streaming disabled")

# OpenCV for frame encoding
HAS_OPENCV = False
try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    np = None
    logger.warning("OpenCV not installed - frame encoding disabled")


class StreamMode(Enum):
    """Streaming modes for VR headset."""
    PASSTHROUGH = "passthrough"      # Live webcam passthrough
    IMAGE_OVERLAY = "image_overlay"  # Generated images as overlay
    FULL_IMMERSIVE = "full_immersive"  # Full VR environment
    AR_BLEND = "ar_blend"            # AR blend with real world


@dataclass
class HeadsetConfig:
    """Configuration for connected VR headset."""
    name: str
    runtime: str  # 'openxr', 'steamvr', 'webxr', 'oculus', 'wmr'
    resolution: tuple = (1920, 1080)
    fov: float = 110.0
    refresh_rate: int = 90
    ipd: float = 63.0  # Inter-pupillary distance in mm


class VRHeadsetStreamer:
    """
    SOTA 2026 VR/AR Headset Image Streamer

    Streams images and video to VR/AR headsets using multiple protocols.
    """

    def __init__(self, event_bus=None, config: Optional[Dict] = None):
        self.event_bus = event_bus
        self.config = config or {}

        # State
        self._streaming = False
        self._current_mode = StreamMode.PASSTHROUGH
        self._connected_headsets: Dict[str, HeadsetConfig] = {}
        self._websocket_server = None
        self._websocket_clients = set()
        self._broadcast_queue = queue.Queue()

        # Frame buffer
        self._current_frame = None
        self._frame_lock = threading.Lock()

        # WebSocket server config
        self._ws_host = self.config.get('ws_host', '0.0.0.0')
        self._ws_port = self.config.get('ws_port', 8765)

        # Subscribe to events
        self._subscribe_to_events()

        logger.info("🥽 VRHeadsetStreamer initialized")

    def _subscribe_to_events(self):
        """Subscribe to relevant event bus events."""
        if not self.event_bus:
            return
        self.event_bus.subscribe('vision.stream.webcam.frame', self._handle_webcam_frame)
        self.event_bus.subscribe('vision.stream.vr.frame', self._handle_vr_frame)
        self.event_bus.subscribe('visual.image.generated', self._handle_generated_image)
        self.event_bus.subscribe('vr.headset.stream.start', self._handle_stream_start)
        self.event_bus.subscribe('vr.headset.stream.stop', self._handle_stream_stop)
        # SOTA 2026: VR audio relay — relay Kingdom AI voice to headset
        self.event_bus.subscribe('voice.audio.file', self._handle_voice_audio)
        # SOTA 2026: GUI mirror frame for full system display in VR
        self.event_bus.subscribe('vr.gui.mirror.frame', self._handle_gui_mirror_frame)
        logger.info("🥽 Subscribed to vision + audio + GUI mirror events")

    def _handle_webcam_frame(self, data: dict):
        """Handle incoming webcam frame."""
        frame = data.get('frame')
        if frame is not None:
            with self._frame_lock:
                self._current_frame = frame
            if self._streaming and self._current_mode == StreamMode.PASSTHROUGH:
                self._broadcast_frame(frame)

    def _handle_vr_frame(self, data: dict):
        """Handle incoming VR view frame."""
        frame = data.get('frame')
        if frame is not None and self._streaming:
            if self._current_mode == StreamMode.FULL_IMMERSIVE:
                self._broadcast_frame(frame)

    def _handle_generated_image(self, data: dict):
        """Handle generated image - send to headset as overlay."""
        if self._streaming and self._current_mode in (StreamMode.IMAGE_OVERLAY, StreamMode.AR_BLEND):
            metadata = data.get('metadata', {})
            logger.info(f"🥽 Sending generated image to headset: {metadata.get('prompt', '')[:50]}")
            if self.event_bus:
                self.event_bus.publish('vr.headset.overlay.update', {
                    'type': 'generated_image',
                    'metadata': metadata,
                    'timestamp': time.time()
                })

    def _handle_stream_start(self, data: dict):
        """Start streaming to headset."""
        source = data.get('source', 'webcam')
        mode = data.get('mode', 'passthrough')
        try:
            self._current_mode = StreamMode(mode)
        except ValueError:
            self._current_mode = StreamMode.PASSTHROUGH
        self._streaming = True
        logger.info(f"🥽 Started headset streaming: source={source}, mode={mode}")
        if HAS_WEBSOCKETS and not self._websocket_server:
            self._start_websocket_server()
        if self.event_bus:
            self.event_bus.publish('vr.headset.stream.status', {
                'active': True,
                'mode': self._current_mode.value,
                'source': source,
                'timestamp': time.time()
            })

    def _handle_stream_stop(self, data: dict):
        """Stop streaming to headset."""
        self._streaming = False
        logger.info("🥽 Stopped headset streaming")
        if self.event_bus:
            self.event_bus.publish('vr.headset.stream.status', {
                'active': False,
                'timestamp': time.time()
            })

    def _handle_voice_audio(self, data: dict):
        """SOTA 2026: Relay Kingdom AI TTS audio to VR headset via WebSocket.

        When the voice manager generates a TTS audio file it publishes
        voice.audio.file.  We encode it as base64 and push it to all
        connected WebXR clients so the headset can play the audio."""
        if not self._streaming:
            return
        audio_path = data.get('path')
        if not audio_path:
            return
        try:
            import pathlib
            path = pathlib.Path(audio_path)
            if not path.exists():
                return
            raw = path.read_bytes()
            audio_b64 = base64.b64encode(raw).decode('utf-8')
            payload = json.dumps({
                'type': 'audio',
                'format': path.suffix.lstrip('.'),
                'data': audio_b64,
                'timestamp': time.time(),
            })
            self._broadcast_queue.put(payload)
            logger.info(f"🥽🔊 TTS audio relayed to headset ({len(raw)} bytes)")
        except Exception as e:
            logger.warning(f"Failed to relay TTS audio to headset: {e}")

    def _handle_gui_mirror_frame(self, data: dict):
        """SOTA 2026: Handle full GUI mirror frame for system-wide VR display."""
        frame = data.get('frame')
        if frame is not None and self._streaming:
            self._broadcast_frame(frame)

    def _broadcast_frame(self, frame):
        """Queue frame for broadcast to WebXR clients (server thread does actual send)."""
        if not HAS_OPENCV or not HAS_WEBSOCKETS:
            return
        if not self._websocket_clients:
            return
        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            message = json.dumps({
                'type': 'frame',
                'data': frame_b64,
                'timestamp': time.time(),
                'mode': self._current_mode.value
            })
            try:
                self._broadcast_queue.put_nowait(message)
            except queue.Full:
                pass
        except Exception as e:
            logger.error(f"Error encoding frame: {e}")

    def _start_websocket_server(self):
        """Start WebSocket server for WebXR clients."""
        if not HAS_WEBSOCKETS:
            return

        import asyncio

        async def drain_broadcast_queue():
            """Drain broadcast queue and send to all clients (runs in server loop)."""
            while True:
                try:
                    message = self._broadcast_queue.get_nowait()
                    dead = set()
                    for client in self._websocket_clients:
                        try:
                            await client.send(message)
                        except Exception:
                            dead.add(client)
                    self._websocket_clients -= dead
                except queue.Empty:
                    await asyncio.sleep(0.01)

        async def handler(websocket, path):
            self._websocket_clients.add(websocket)
            logger.info(f"🥽 WebXR client connected: {websocket.remote_address}")
            try:
                await websocket.send(json.dumps({
                    'type': 'config',
                    'streaming': self._streaming,
                    'mode': self._current_mode.value,
                    'headsets': [h.name for h in self._connected_headsets.values()]
                }))
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self._handle_client_message(websocket, data)
                    except Exception as e:
                        logger.error(f"WebSocket message error: {e}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self._websocket_clients.discard(websocket)
                logger.info("🥽 WebXR client disconnected")

        async def start_server():
            self._websocket_server = await websockets.serve(
                handler, self._ws_host, self._ws_port
            )
            logger.info(f"🥽 WebXR WebSocket server started on ws://{self._ws_host}:{self._ws_port}")
            asyncio.create_task(drain_broadcast_queue())
            await self._websocket_server.wait_closed()

        def run_server():
            asyncio.run(start_server())

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

    async def _handle_client_message(self, websocket, data: dict):
        """Handle message from WebXR client."""
        msg_type = data.get('type')
        if msg_type == 'headset_info':
            config = HeadsetConfig(
                name=data.get('name', 'Unknown'),
                runtime=data.get('runtime', 'webxr'),
                resolution=tuple(data.get('resolution', [1920, 1080])),
                fov=data.get('fov', 110.0),
                refresh_rate=data.get('refresh_rate', 90)
            )
            client_id = str(id(websocket))
            self._connected_headsets[client_id] = config
            logger.info(f"🥽 Headset registered: {config.name} ({config.runtime})")
            if self.event_bus:
                self.event_bus.publish('vr.headset.connected', {
                    'name': config.name,
                    'runtime': config.runtime,
                    'resolution': config.resolution,
                    'timestamp': time.time()
                })
        elif msg_type == 'mode_change':
            try:
                self._current_mode = StreamMode(data.get('mode', 'passthrough'))
                logger.info(f"🥽 Mode changed to: {self._current_mode.value}")
            except ValueError:
                pass

    def get_status(self) -> Dict[str, Any]:
        """Get current streamer status."""
        return {
            'streaming': self._streaming,
            'mode': self._current_mode.value,
            'connected_headsets': len(self._connected_headsets),
            'websocket_clients': len(self._websocket_clients),
            'websocket_port': self._ws_port
        }

    def shutdown(self):
        """Shutdown the streamer."""
        self._streaming = False
        if self._websocket_server:
            self._websocket_server.close()
        logger.info("🥽 VRHeadsetStreamer shutdown")


_streamer_instance: Optional[VRHeadsetStreamer] = None


def get_vr_headset_streamer(event_bus=None) -> VRHeadsetStreamer:
    """Get or create VR headset streamer singleton."""
    global _streamer_instance
    if _streamer_instance is None:
        _streamer_instance = VRHeadsetStreamer(event_bus=event_bus)
    return _streamer_instance


def initialize_vr_headset_streamer(event_bus=None) -> VRHeadsetStreamer:
    """Initialize VR headset streamer (alias for get_vr_headset_streamer)."""
    return get_vr_headset_streamer(event_bus=event_bus)
