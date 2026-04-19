"""Lab Streaming Layer synchronization engine for neuroscience data streams."""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger("kingdom_ai.lsl_sync_engine")

_CLOCK_EPOCH = time.time()


def _lsl_clock() -> float:
    return time.time() - _CLOCK_EPOCH


class _StreamInfo:
    __slots__ = ("stream_id", "name", "stream_type", "channel_count", "sample_rate",
                 "created_at", "sample_count", "buffer")

    def __init__(self, name: str, stream_type: str, channel_count: int, sample_rate: float) -> None:
        self.stream_id: str = uuid.uuid4().hex[:12]
        self.name = name
        self.stream_type = stream_type
        self.channel_count = channel_count
        self.sample_rate = sample_rate
        self.created_at: float = _lsl_clock()
        self.sample_count: int = 0
        self.buffer: Deque[Tuple[float, List[float]]] = deque(maxlen=int(sample_rate * 60))


class LSLSyncEngine:
    """Time-stamps and synchronises multiple data streams (LSL-compatible simulation)."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._streams: Dict[str, _StreamInfo] = {}
        self._sync_offsets: Dict[str, float] = {}
        self._master_clock_start: float = _lsl_clock()
        if event_bus:
            event_bus.subscribe("lsl.sync.request", self._on_sync_request)
        logger.info("LSLSyncEngine initialised (clock_epoch=%.4f)", _CLOCK_EPOCH)

    def create_stream(self, name: str, stream_type: str = "EEG",
                      channel_count: int = 8, sample_rate: float = 256.0) -> Dict[str, Any]:
        info = _StreamInfo(name, stream_type, channel_count, sample_rate)
        self._streams[info.stream_id] = info
        self._sync_offsets[info.stream_id] = 0.0
        logger.info("Created stream '%s' id=%s type=%s channels=%d rate=%.1f",
                     name, info.stream_id, stream_type, channel_count, sample_rate)
        return {
            "stream_id": info.stream_id,
            "name": name,
            "type": stream_type,
            "channel_count": channel_count,
            "sample_rate": sample_rate,
        }

    def push_sample(self, stream_id: str, sample_data: List[float],
                    timestamp: Optional[float] = None) -> Dict[str, Any]:
        info = self._streams.get(stream_id)
        if not info:
            return {"error": f"Stream '{stream_id}' not found"}
        if len(sample_data) != info.channel_count:
            return {"error": f"Expected {info.channel_count} channels, got {len(sample_data)}"}
        ts = timestamp if timestamp is not None else _lsl_clock()
        corrected_ts = ts + self._sync_offsets.get(stream_id, 0.0)
        info.buffer.append((corrected_ts, list(sample_data)))
        info.sample_count += 1
        return {"stream_id": stream_id, "timestamp": corrected_ts, "sample_count": info.sample_count}

    def push_chunk(self, stream_id: str, chunk: List[List[float]]) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for sample in chunk:
            results.append(self.push_sample(stream_id, sample))
        errors = [r for r in results if "error" in r]
        if errors:
            return {"error": errors[0]["error"], "pushed": len(results) - len(errors)}
        return {"stream_id": stream_id, "pushed": len(results)}

    def resolve_streams(self, stream_type: Optional[str] = None) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []
        for info in self._streams.values():
            if stream_type and info.stream_type != stream_type:
                continue
            found.append({
                "stream_id": info.stream_id,
                "name": info.name,
                "type": info.stream_type,
                "channel_count": info.channel_count,
                "sample_rate": info.sample_rate,
                "sample_count": info.sample_count,
                "buffer_sec": len(info.buffer) / max(info.sample_rate, 1),
            })
        return found

    def synchronize_streams(self, reference_id: str) -> Dict[str, Any]:
        ref = self._streams.get(reference_id)
        if not ref:
            return {"error": f"Reference stream '{reference_id}' not found"}
        if not ref.buffer:
            return {"error": "Reference stream has no samples"}
        ref_latest_ts = ref.buffer[-1][0]
        adjustments: Dict[str, float] = {}
        for sid, info in self._streams.items():
            if sid == reference_id or not info.buffer:
                continue
            their_latest = info.buffer[-1][0]
            offset = ref_latest_ts - their_latest
            self._sync_offsets[sid] = self._sync_offsets.get(sid, 0.0) + offset
            adjustments[sid] = round(offset, 6)
        logger.info("Synchronised %d streams to reference '%s'", len(adjustments), reference_id)
        return {"reference": reference_id, "adjustments": adjustments}

    def get_sync_status(self) -> Dict[str, Any]:
        stream_stats: Dict[str, Any] = {}
        for sid, info in self._streams.items():
            latest_ts = info.buffer[-1][0] if info.buffer else None
            stream_stats[sid] = {
                "name": info.name,
                "type": info.stream_type,
                "samples": info.sample_count,
                "latest_timestamp": latest_ts,
                "offset": round(self._sync_offsets.get(sid, 0.0), 6),
            }
        max_drift = 0.0
        timestamps = [s["latest_timestamp"] for s in stream_stats.values() if s["latest_timestamp"] is not None]
        if len(timestamps) > 1:
            max_drift = max(timestamps) - min(timestamps)
        return {
            "stream_count": len(self._streams),
            "max_drift_sec": round(max_drift, 6),
            "master_uptime_sec": round(_lsl_clock() - self._master_clock_start, 4),
            "streams": stream_stats,
        }

    def remove_stream(self, stream_id: str) -> Dict[str, Any]:
        if stream_id not in self._streams:
            return {"error": f"Stream '{stream_id}' not found"}
        info = self._streams.pop(stream_id)
        self._sync_offsets.pop(stream_id, None)
        logger.info("Removed stream '%s' (%s)", info.name, stream_id)
        return {"removed": stream_id, "name": info.name}

    def _on_sync_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("sync request ignored — expected dict")
            return
        action = data.get("action", "status")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            if action == "create":
                result["data"] = self.create_stream(
                    data.get("name", "stream"), data.get("type", "EEG"),
                    data.get("channel_count", 8), data.get("sample_rate", 256.0))
            elif action == "resolve":
                result["data"] = self.resolve_streams(data.get("type"))
            elif action == "status":
                result["data"] = self.get_sync_status()
            elif action == "sync":
                result["data"] = self.synchronize_streams(data.get("reference_id", ""))
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("LSL sync request failed")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("lsl.sync.status", result)
