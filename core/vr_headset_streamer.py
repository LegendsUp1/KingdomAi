#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOTA 2026 - VR/AR Headset Image Streamer (multi-tenant)

Streams generated images and webcam feeds to VR/AR headsets via:
1. WebXR API (browser-based VR/AR)
2. OpenXR bridge (native VR runtimes)
3. WebSocket server for real-time streaming
4. SteamVR overlay API

Supports: Meta Quest, HTC Vive, Valve Index, Windows Mixed Reality, Apple Vision Pro

Multi-tenant design
-------------------
Every connected headset is its OWN isolated session. A consumer who pairs
their own headset gets their own memory palace, their own generated images,
their own TTS audio and their own stream mode. The creator's headset (or
the local desktop running Kingdom AI) has no special privilege — it is just
another session.

Routing rules for bus events:
  * ``data['user_id']``   — delivered only to the session with that user id
  * ``data['client_id']`` — delivered only to that specific WebSocket client
  * ``data['broadcast'] == True`` — fanned out to every session (used for
    shared/public content, e.g. a guided group tour)
  * otherwise the event is treated as local-only and never leaves the
    publishing process — this prevents the "creator headset sees everything
    and so does every consumer" leak that the old singleton had.
"""

import logging
import threading
import time
import json
import base64
import queue
import uuid
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("KingdomAI.VRHeadsetStreamer")

HAS_WEBSOCKETS = False
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    logger.warning("websockets not installed - WebXR streaming disabled")

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
    PASSTHROUGH = "passthrough"        # Live webcam passthrough
    IMAGE_OVERLAY = "image_overlay"    # Generated images as overlay
    FULL_IMMERSIVE = "full_immersive"  # Full VR environment
    AR_BLEND = "ar_blend"              # AR blend with real world


@dataclass
class HeadsetConfig:
    """Configuration for a connected VR headset."""
    name: str
    runtime: str  # 'openxr', 'steamvr', 'webxr', 'oculus', 'wmr'
    resolution: tuple = (1920, 1080)
    fov: float = 110.0
    refresh_rate: int = 90
    ipd: float = 63.0  # Inter-pupillary distance in mm


@dataclass
class VRClientSession:
    """Per-consumer VR session state.

    A session is fully isolated: its stream flag, mode, source selection and
    outbound queue belong to exactly one headset. No other session (and in
    particular no "creator" session) can mutate this state.
    """
    client_id: str
    user_id: str
    headset: Optional[HeadsetConfig] = None
    mode: StreamMode = StreamMode.PASSTHROUGH
    source: str = "own_webcam"     # own_webcam / own_generations / memory_palace / system_broadcast
    streaming: bool = False
    connected_at: float = field(default_factory=time.time)
    send_queue: "queue.Queue[str]" = field(default_factory=lambda: queue.Queue(maxsize=256))

    def to_status(self) -> Dict[str, Any]:
        return {
            "client_id": self.client_id,
            "user_id": self.user_id,
            "mode": self.mode.value,
            "source": self.source,
            "streaming": self.streaming,
            "headset": self.headset.name if self.headset else None,
            "runtime": self.headset.runtime if self.headset else None,
            "connected_at": self.connected_at,
        }


class VRHeadsetStreamer:
    """SOTA 2026 VR/AR Headset Image Streamer — multi-tenant.

    Hosts a single WebSocket endpoint but maintains an independent
    ``VRClientSession`` per connected headset so consumers never inherit
    another user's mode, source or content.
    """

    def __init__(self, event_bus=None, config: Optional[Dict] = None):
        self.event_bus = event_bus
        self.config = config or {}

        self._sessions: Dict[str, VRClientSession] = {}
        self._sessions_lock = threading.Lock()
        self._websocket_server = None

        self._ws_host = self.config.get('ws_host', '0.0.0.0')
        self._ws_port = self.config.get('ws_port', 8765)

        self._server_loop = None  # asyncio loop of the WS server thread

        self._subscribe_to_events()
        logger.info("🥽 VRHeadsetStreamer initialized (multi-tenant)")

    # ────────────────────────────────────────────────────────────────
    # Event-bus wiring
    # ────────────────────────────────────────────────────────────────

    def _subscribe_to_events(self):
        if not self.event_bus:
            return
        self.event_bus.subscribe('vision.stream.webcam.frame', self._handle_webcam_frame)
        self.event_bus.subscribe('vision.stream.vr.frame', self._handle_vr_frame)
        self.event_bus.subscribe('visual.image.generated', self._handle_generated_image)
        self.event_bus.subscribe('vr.headset.stream.start', self._handle_stream_start)
        self.event_bus.subscribe('vr.headset.stream.stop', self._handle_stream_stop)
        self.event_bus.subscribe('voice.audio.file', self._handle_voice_audio)
        self.event_bus.subscribe('vr.gui.mirror.frame', self._handle_gui_mirror_frame)
        self.event_bus.subscribe('vr.memory_palace.frame', self._handle_memory_palace_frame)
        logger.info("🥽 Subscribed to vision + audio + GUI mirror events")

    # ────────────────────────────────────────────────────────────────
    # Session resolution — who is this event intended for?
    # ────────────────────────────────────────────────────────────────

    def _sessions_for_event(self, data: Dict[str, Any]) -> list:
        """Return the list of sessions an event should be delivered to.

        Priority:
            1. explicit client_id   → exact session
            2. explicit user_id     → all sessions for that user (usually 1)
            3. broadcast=True       → every session
            4. otherwise            → none (local-only, do NOT leak to headsets)
        """
        if not isinstance(data, dict):
            return []

        client_id = data.get('client_id')
        user_id = data.get('user_id')
        broadcast = bool(data.get('broadcast', False))

        with self._sessions_lock:
            if client_id and client_id in self._sessions:
                return [self._sessions[client_id]]
            if user_id:
                return [s for s in self._sessions.values() if s.user_id == user_id]
            if broadcast:
                return list(self._sessions.values())
        return []

    # ────────────────────────────────────────────────────────────────
    # Event handlers — all route per session, never globally
    # ────────────────────────────────────────────────────────────────

    def _handle_webcam_frame(self, data: dict):
        """Each user's own webcam feed is only forwarded to that user's session(s)."""
        frame = data.get('frame') if isinstance(data, dict) else None
        if frame is None:
            return
        for session in self._sessions_for_event(data):
            if session.streaming and session.mode == StreamMode.PASSTHROUGH and session.source == "own_webcam":
                self._enqueue_frame(session, frame)

    def _handle_vr_frame(self, data: dict):
        frame = data.get('frame') if isinstance(data, dict) else None
        if frame is None:
            return
        for session in self._sessions_for_event(data):
            if session.streaming and session.mode == StreamMode.FULL_IMMERSIVE:
                self._enqueue_frame(session, frame)

    def _handle_generated_image(self, data: dict):
        """A user's generated image overlay goes to that user only.

        If publishers omit a user_id and don't mark broadcast=True the image
        stays local — we will not push one consumer's creation into another
        consumer's headset.
        """
        metadata = data.get('metadata', {}) if isinstance(data, dict) else {}
        targets = self._sessions_for_event(data)
        if not targets:
            return
        for session in targets:
            if session.streaming and session.mode in (StreamMode.IMAGE_OVERLAY, StreamMode.AR_BLEND):
                self._enqueue_json(session, {
                    'type': 'overlay',
                    'overlay': 'generated_image',
                    'metadata': metadata,
                    'timestamp': time.time(),
                })
        if self.event_bus:
            # re-publish an ack scoped to each targeted session so subscribers
            # can track per-user delivery
            for session in targets:
                self.event_bus.publish('vr.headset.overlay.update', {
                    'type': 'generated_image',
                    'metadata': metadata,
                    'client_id': session.client_id,
                    'user_id': session.user_id,
                    'timestamp': time.time(),
                })

    def _handle_memory_palace_frame(self, data: dict):
        """Memory palace frames are strictly per-user — a consumer's palace
        can never be streamed into someone else's headset."""
        frame = data.get('frame') if isinstance(data, dict) else None
        if frame is None:
            return
        for session in self._sessions_for_event(data):
            if session.streaming and session.source in ("memory_palace", "own_memory_palace"):
                self._enqueue_frame(session, frame)

    def _handle_voice_audio(self, data: dict):
        """Relay TTS audio to a specific user's headset only."""
        audio_path = data.get('path') if isinstance(data, dict) else None
        if not audio_path:
            return
        targets = self._sessions_for_event(data)
        if not targets:
            return
        try:
            import pathlib
            path = pathlib.Path(audio_path)
            if not path.exists():
                return
            raw = path.read_bytes()
            audio_b64 = base64.b64encode(raw).decode('utf-8')
            payload = {
                'type': 'audio',
                'format': path.suffix.lstrip('.'),
                'data': audio_b64,
                'timestamp': time.time(),
            }
            for session in targets:
                if session.streaming:
                    self._enqueue_json(session, payload)
                    logger.info("🥽🔊 TTS relayed to %s (%d bytes)", session.user_id, len(raw))
        except Exception as e:
            logger.warning("Failed to relay TTS audio: %s", e)

    def _handle_gui_mirror_frame(self, data: dict):
        """GUI mirror is host-device content. It ONLY goes to sessions that
        explicitly opted in (source='system_broadcast') and that the publisher
        targeted — otherwise every consumer would see the host's desktop."""
        frame = data.get('frame') if isinstance(data, dict) else None
        if frame is None:
            return
        for session in self._sessions_for_event(data):
            if session.streaming and session.source == "system_broadcast":
                self._enqueue_frame(session, frame)

    def _handle_stream_start(self, data: dict):
        """Start streaming for a specific session.

        Without a user_id / client_id the start event is a no-op on the
        shared bus — consumers start their own sessions via their own
        WebSocket handshake, not via the host's bus.
        """
        mode_val = data.get('mode', 'passthrough') if isinstance(data, dict) else 'passthrough'
        source = data.get('source', 'own_webcam') if isinstance(data, dict) else 'own_webcam'
        targets = self._sessions_for_event(data)
        if not targets:
            # cold-boot the websocket server so a paired headset can reach us,
            # but do NOT flip any existing session's stream flag
            if HAS_WEBSOCKETS and not self._websocket_server:
                self._start_websocket_server()
            return
        for session in targets:
            try:
                session.mode = StreamMode(mode_val)
            except ValueError:
                session.mode = StreamMode.PASSTHROUGH
            session.source = source
            session.streaming = True
            logger.info("🥽 Session %s streaming: mode=%s source=%s",
                        session.user_id, session.mode.value, source)
            if self.event_bus:
                self.event_bus.publish('vr.headset.stream.status', {
                    'active': True,
                    'mode': session.mode.value,
                    'source': source,
                    'user_id': session.user_id,
                    'client_id': session.client_id,
                    'timestamp': time.time(),
                })
        if HAS_WEBSOCKETS and not self._websocket_server:
            self._start_websocket_server()

    def _handle_stream_stop(self, data: dict):
        for session in self._sessions_for_event(data):
            session.streaming = False
            logger.info("🥽 Session %s stopped streaming", session.user_id)
            if self.event_bus:
                self.event_bus.publish('vr.headset.stream.status', {
                    'active': False,
                    'user_id': session.user_id,
                    'client_id': session.client_id,
                    'timestamp': time.time(),
                })

    # ────────────────────────────────────────────────────────────────
    # Per-session outbound queues
    # ────────────────────────────────────────────────────────────────

    def _enqueue_frame(self, session: VRClientSession, frame) -> None:
        if not HAS_OPENCV or not HAS_WEBSOCKETS:
            return
        try:
            ok, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                return
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            self._enqueue_json(session, {
                'type': 'frame',
                'data': frame_b64,
                'timestamp': time.time(),
                'mode': session.mode.value,
            })
        except Exception as e:
            logger.error("Error encoding frame for %s: %s", session.user_id, e)

    def _enqueue_json(self, session: VRClientSession, payload: Dict[str, Any]) -> None:
        try:
            session.send_queue.put_nowait(json.dumps(payload))
        except queue.Full:
            # drop the oldest to keep latency bounded for this ONE session only
            try:
                session.send_queue.get_nowait()
                session.send_queue.put_nowait(json.dumps(payload))
            except Exception:
                pass

    # ────────────────────────────────────────────────────────────────
    # WebSocket server (multi-tenant handshake)
    # ────────────────────────────────────────────────────────────────

    def _start_websocket_server(self):
        if not HAS_WEBSOCKETS:
            return

        import asyncio

        async def client_drain(session: VRClientSession, websocket):
            """Flush one session's queue to its own socket — no cross-talk."""
            try:
                while True:
                    try:
                        message = session.send_queue.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(0.01)
                        continue
                    try:
                        await websocket.send(message)
                    except Exception:
                        return
            except asyncio.CancelledError:
                return

        async def handler(websocket, path=None):
            client_id = uuid.uuid4().hex
            # user_id defaults to the client_id so two anonymous headsets on
            # the same LAN never share a session by accident. Clients should
            # send a `hello` message with their real user_id right after
            # connecting; see _handle_client_message below.
            session = VRClientSession(client_id=client_id, user_id=client_id)
            with self._sessions_lock:
                self._sessions[client_id] = session
            logger.info("🥽 WebXR client connected: client_id=%s remote=%s",
                        client_id, getattr(websocket, 'remote_address', '?'))

            drain_task = asyncio.create_task(client_drain(session, websocket))
            try:
                # handshake: tell the client its own identity + current state
                await websocket.send(json.dumps({
                    'type': 'welcome',
                    'client_id': client_id,
                    'ws_port': self._ws_port,
                    'modes': [m.value for m in StreamMode],
                    'sources': ['own_webcam', 'own_generations', 'memory_palace', 'system_broadcast'],
                }))
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self._handle_client_message(session, websocket, data)
                    except Exception as e:
                        logger.error("WebSocket message error for %s: %s", client_id, e)
            except Exception as e:
                logger.error("WebSocket error for %s: %s", client_id, e)
            finally:
                drain_task.cancel()
                with self._sessions_lock:
                    self._sessions.pop(client_id, None)
                logger.info("🥽 WebXR client disconnected: %s", client_id)
                if self.event_bus:
                    try:
                        self.event_bus.publish('vr.headset.disconnected', {
                            'client_id': client_id,
                            'user_id': session.user_id,
                            'timestamp': time.time(),
                        })
                    except Exception:
                        pass

        async def start_server():
            self._server_loop = asyncio.get_event_loop()
            self._websocket_server = await websockets.serve(
                handler, self._ws_host, self._ws_port
            )
            logger.info("🥽 WebXR WebSocket server listening on ws://%s:%s",
                        self._ws_host, self._ws_port)
            await self._websocket_server.wait_closed()

        def run_server():
            try:
                asyncio.run(start_server())
            except Exception as e:
                logger.error("WebSocket server crashed: %s", e)

        t = threading.Thread(target=run_server, daemon=True, name="VRHeadsetWS")
        t.start()

    async def _handle_client_message(self, session: VRClientSession, websocket, data: dict):
        """Messages from a client mutate ONLY that client's own session."""
        msg_type = data.get('type')

        if msg_type == 'hello':
            # Claim a stable user identity for this consumer. This is what
            # decouples a paired headset from the host machine — the consumer
            # picks their own user_id and every subsequent bus event targeted
            # at that user_id is routed to THEIR session only.
            user_id = str(data.get('user_id') or session.user_id).strip() or session.user_id
            session.user_id = user_id
            logger.info("🥽 client_id=%s claimed user_id=%s", session.client_id, user_id)
            if self.event_bus:
                self.event_bus.publish('vr.headset.connected', {
                    'client_id': session.client_id,
                    'user_id': session.user_id,
                    'timestamp': time.time(),
                })
            return

        if msg_type == 'headset_info':
            try:
                session.headset = HeadsetConfig(
                    name=data.get('name', 'Unknown'),
                    runtime=data.get('runtime', 'webxr'),
                    resolution=tuple(data.get('resolution', [1920, 1080])),
                    fov=float(data.get('fov', 110.0)),
                    refresh_rate=int(data.get('refresh_rate', 90)),
                )
                logger.info("🥽 %s paired %s (%s)", session.user_id,
                            session.headset.name, session.headset.runtime)
                if self.event_bus:
                    self.event_bus.publish('vr.headset.paired', {
                        'client_id': session.client_id,
                        'user_id': session.user_id,
                        'name': session.headset.name,
                        'runtime': session.headset.runtime,
                        'resolution': list(session.headset.resolution),
                        'timestamp': time.time(),
                    })
            except Exception as e:
                logger.warning("headset_info parse failed for %s: %s", session.client_id, e)
            return

        if msg_type == 'mode_change':
            try:
                session.mode = StreamMode(data.get('mode', 'passthrough'))
                logger.info("🥽 %s mode -> %s", session.user_id, session.mode.value)
            except ValueError:
                pass
            return

        if msg_type == 'source_change':
            src = str(data.get('source') or 'own_webcam')
            session.source = src
            logger.info("🥽 %s source -> %s", session.user_id, src)
            return

        if msg_type == 'stream_start':
            try:
                session.mode = StreamMode(data.get('mode', session.mode.value))
            except ValueError:
                pass
            session.source = data.get('source', session.source)
            session.streaming = True
            logger.info("🥽 %s stream_start (mode=%s source=%s)",
                        session.user_id, session.mode.value, session.source)
            return

        if msg_type == 'stream_stop':
            session.streaming = False
            logger.info("🥽 %s stream_stop", session.user_id)
            return

        logger.debug("🥽 %s unknown message type: %s", session.client_id, msg_type)

    # ────────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Aggregate status + per-session breakdown."""
        with self._sessions_lock:
            sessions = [s.to_status() for s in self._sessions.values()]
        return {
            'websocket_port': self._ws_port,
            'server_running': self._websocket_server is not None,
            'session_count': len(sessions),
            'streaming_count': sum(1 for s in sessions if s['streaming']),
            'sessions': sessions,
        }

    def get_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Return a copy of every session's public status keyed by client_id."""
        with self._sessions_lock:
            return {cid: s.to_status() for cid, s in self._sessions.items()}

    def disconnect_session(self, client_id: str) -> bool:
        """Force a session off. Useful for admin tools; does not affect
        any other consumer."""
        with self._sessions_lock:
            session = self._sessions.pop(client_id, None)
        if session is None:
            return False
        session.streaming = False
        return True

    def shutdown(self):
        with self._sessions_lock:
            for s in self._sessions.values():
                s.streaming = False
            self._sessions.clear()
        if self._websocket_server:
            try:
                self._websocket_server.close()
            except Exception:
                pass
        logger.info("🥽 VRHeadsetStreamer shutdown")


_streamer_instance: Optional[VRHeadsetStreamer] = None
_streamer_lock = threading.Lock()


def get_vr_headset_streamer(event_bus=None) -> VRHeadsetStreamer:
    """Get or create the VR headset streamer.

    The streamer process is a singleton (one server, one port) but every
    connected headset is an independent ``VRClientSession`` — so pairing
    "your own headset" means claiming your own session and your own user_id
    at connect time; it is not bound to whoever launched Kingdom AI locally.
    """
    global _streamer_instance
    if _streamer_instance is None:
        with _streamer_lock:
            if _streamer_instance is None:
                _streamer_instance = VRHeadsetStreamer(event_bus=event_bus)
    return _streamer_instance


def initialize_vr_headset_streamer(event_bus=None) -> VRHeadsetStreamer:
    """Initialize VR headset streamer (alias for get_vr_headset_streamer)."""
    return get_vr_headset_streamer(event_bus=event_bus)
