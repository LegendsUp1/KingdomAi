"""EEG brain-wave signal processor with filtering, FFT, and band extraction."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kingdom_ai.eeg_signal_processor")

BAND_RANGES: Dict[str, Tuple[float, float]] = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 100.0),
}


def _dft_power(signal: List[float], sample_rate: float, freq_lo: float, freq_hi: float) -> float:
    """Compute average power in a frequency band using DFT (pure Python)."""
    n = len(signal)
    if n == 0:
        return 0.0
    bin_lo = max(1, int(freq_lo * n / sample_rate))
    bin_hi = min(n // 2, int(freq_hi * n / sample_rate) + 1)
    power = 0.0
    count = 0
    for k in range(bin_lo, bin_hi):
        real = sum(signal[i] * math.cos(2 * math.pi * k * i / n) for i in range(n))
        imag = sum(signal[i] * math.sin(2 * math.pi * k * i / n) for i in range(n))
        power += (real * real + imag * imag) / (n * n)
        count += 1
    return power / max(count, 1)


def _simple_bandpass(signal: List[float], sample_rate: float, low: float, high: float, order: int = 2) -> List[float]:
    """Crude IIR bandpass approximation using cascaded first-order sections."""
    dt = 1.0 / sample_rate
    rc_hp = 1.0 / (2.0 * math.pi * low) if low > 0 else 1e6
    alpha_hp = rc_hp / (rc_hp + dt)
    rc_lp = 1.0 / (2.0 * math.pi * high)
    alpha_lp = dt / (rc_lp + dt)

    out = list(signal)
    for _ in range(order):
        prev_in = out[0]
        prev_out = out[0]
        for i in range(1, len(out)):
            hp = alpha_hp * (prev_out + out[i] - prev_in)
            prev_in = out[i]
            prev_out = hp
            out[i] = hp
        prev_lp = out[0]
        for i in range(1, len(out)):
            prev_lp = prev_lp + alpha_lp * (out[i] - prev_lp)
            out[i] = prev_lp
    return out


class EEGSignalProcessor:
    """Processes EEG signals — filtering, spectral analysis, and artifact detection."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._last_bands: Optional[Dict[str, float]] = None
        if event_bus:
            event_bus.subscribe("eeg.process.request", self._on_process_request)
        logger.info("EEGSignalProcessor initialised (bands: %s)", ", ".join(BAND_RANGES))

    def process_signal(self, raw_data: List[float], sample_rate: float = 256.0,
                       low_cut: float = 0.5, high_cut: float = 100.0) -> List[float]:
        if not raw_data:
            return []
        mean_val = sum(raw_data) / len(raw_data)
        centered = [x - mean_val for x in raw_data]
        filtered = _simple_bandpass(centered, sample_rate, low_cut, high_cut)
        logger.debug("Processed %d samples (%.1f-%.1fHz)", len(filtered), low_cut, high_cut)
        return filtered

    def extract_bands(self, signal: List[float], sample_rate: float = 256.0) -> Dict[str, float]:
        if not signal:
            return {band: 0.0 for band in BAND_RANGES}
        bands: Dict[str, float] = {}
        for band_name, (lo, hi) in BAND_RANGES.items():
            effective_hi = min(hi, sample_rate / 2.0)
            if lo >= effective_hi:
                bands[band_name] = 0.0
                continue
            power = _dft_power(signal, sample_rate, lo, effective_hi)
            bands[band_name] = round(power, 6)
        self._last_bands = bands
        total = sum(bands.values()) or 1.0
        bands["dominant"] = max(bands, key=lambda k: bands[k] if k != "dominant" else 0)
        bands["total_power"] = round(total, 6)
        return bands

    def detect_artifacts(self, signal: List[float], threshold_uv: float = 100.0) -> List[Dict[str, Any]]:
        if not signal:
            return []
        artifacts: List[Dict[str, Any]] = []
        window = max(1, len(signal) // 20)
        for start in range(0, len(signal) - window + 1, window):
            chunk = signal[start: start + window]
            peak = max(abs(v) for v in chunk)
            if peak > threshold_uv:
                artifacts.append({
                    "start_sample": start,
                    "end_sample": start + window,
                    "peak_amplitude": round(peak, 2),
                    "type": "high_amplitude",
                })
            diffs = [abs(chunk[i + 1] - chunk[i]) for i in range(len(chunk) - 1)]
            if diffs:
                max_diff = max(diffs)
                if max_diff > threshold_uv * 0.5:
                    artifacts.append({
                        "start_sample": start,
                        "end_sample": start + window,
                        "max_slope": round(max_diff, 2),
                        "type": "sharp_transient",
                    })
        return artifacts

    def compute_coherence(self, signal_a: List[float], signal_b: List[float],
                          sample_rate: float = 256.0) -> float:
        length = min(len(signal_a), len(signal_b))
        if length < 4:
            return 0.0
        sa = signal_a[:length]
        sb = signal_b[:length]
        mean_a = sum(sa) / length
        mean_b = sum(sb) / length
        cov = sum((sa[i] - mean_a) * (sb[i] - mean_b) for i in range(length)) / length
        var_a = sum((x - mean_a) ** 2 for x in sa) / length
        var_b = sum((x - mean_b) ** 2 for x in sb) / length
        denom = math.sqrt(var_a * var_b)
        if denom == 0:
            return 0.0
        return round(max(-1.0, min(1.0, cov / denom)), 4)

    def _on_process_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("process request ignored — expected dict")
            return
        action = data.get("action", "bands")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            raw = data.get("signal", [])
            rate = data.get("sample_rate", 256.0)
            if action == "process":
                result["data"] = self.process_signal(raw, rate)
            elif action == "bands":
                filtered = self.process_signal(raw, rate) if raw else []
                result["data"] = self.extract_bands(filtered, rate)
            elif action == "artifacts":
                result["data"] = self.detect_artifacts(raw, data.get("threshold", 100.0))
            elif action == "coherence":
                result["data"] = {"coherence": self.compute_coherence(raw, data.get("signal_b", []), rate)}
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("EEG processing failed")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("eeg.process.result", result)
