import binascii
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


class SoapySDRRadioBackend:
    def __init__(self, event_bus=None, publish_chat=None):
        self.event_bus = event_bus
        self._publish_chat = publish_chat

        self._sdr = None
        self._device_args: Optional[Dict[str, str]] = None

        self._rx_stream = None
        self._rx_thread: Optional[threading.Thread] = None
        self._rx_stop = threading.Event()
        self._rx_active = False
        self._rx_config: Dict[str, Any] = {}
        self._rx_last_error: Optional[str] = None

        self._rx_symbol_rate = 1200
        self._rx_deviation_hz = 5000
        self._rx_samples_per_symbol = 0
        self._rx_bits: List[int] = []

        self._tx_last_error: Optional[str] = None

        self._metrics_last_publish = 0.0
        self._rx_frames = 0

        self._sync_bytes = bytes([0x2D, 0xD4])
        self._preamble_len = 8

    def is_available(self) -> bool:
        try:
            import SoapySDR  # noqa: F401

            return True
        except Exception:
            return False

    def enumerate_devices(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        try:
            import SoapySDR

            devices = SoapySDR.Device.enumerate()
            return list(devices) if isinstance(devices, list) else []
        except Exception:
            return []

    def get_status(self) -> Dict[str, Any]:
        return {
            "available": self.is_available(),
            "opened": self._sdr is not None,
            "device_args": self._device_args,
            "rx_active": self._rx_active,
            "rx_config": dict(self._rx_config),
            "rx_last_error": self._rx_last_error,
            "tx_last_error": self._tx_last_error,
            "rx_frames": self._rx_frames,
        }

    def _publish_metrics(self, extra: Optional[Dict[str, Any]] = None) -> None:
        if not self.event_bus:
            return
        now = time.time()
        if now - self._metrics_last_publish < 1.0:
            return
        self._metrics_last_publish = now
        payload = {"timestamp": now, **self.get_status()}
        if extra:
            payload.update(extra)
        try:
            self.event_bus.publish("comms.radio.metrics", payload)
        except Exception:
            return

    def _ensure_open(self, device_args: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        if not self.is_available():
            return False, "SoapySDR_unavailable"

        if self._sdr is not None:
            return True, ""

        try:
            import SoapySDR

            args = device_args
            if args is None:
                devs = self.enumerate_devices()
                if not devs:
                    return False, "no_sdr_devices"
                args = {k: str(v) for k, v in devs[0].items()}
            self._device_args = {k: str(v) for k, v in (args or {}).items()}
            self._sdr = SoapySDR.Device(self._device_args)
            return True, ""
        except Exception as e:
            self._sdr = None
            self._device_args = None
            return False, str(e)

    def _close_stream(self) -> None:
        try:
            if self._sdr is not None and self._rx_stream is not None:
                try:
                    self._sdr.deactivateStream(self._rx_stream)
                except Exception:
                    pass
                try:
                    self._sdr.closeStream(self._rx_stream)
                except Exception:
                    pass
        finally:
            self._rx_stream = None

    def stop_rx(self) -> None:
        self._rx_stop.set()
        t = self._rx_thread
        if t and t.is_alive():
            try:
                t.join(timeout=2.0)
            except Exception:
                pass
        self._rx_thread = None
        self._rx_active = False
        self._close_stream()

    def start_rx(
        self,
        frequency_hz: float,
        sample_rate: int = 1_000_000,
        bandwidth: Optional[float] = None,
        gain: Optional[float] = None,
        channel: int = 0,
        antenna: Optional[str] = None,
        symbol_rate: int = 1200,
        deviation_hz: int = 5000,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        ok, err = self._ensure_open()
        if not ok:
            self._rx_last_error = err
            return False, err, {}

        if self._rx_active:
            return False, "rx_already_active", self.get_status()

        try:
            import SoapySDR
            import numpy as np

            self._rx_symbol_rate = int(symbol_rate)
            self._rx_deviation_hz = int(deviation_hz)
            self._rx_samples_per_symbol = max(1, int(int(sample_rate) / max(1, self._rx_symbol_rate)))
            self._rx_bits = []

            self._rx_config = {
                "frequency_hz": float(frequency_hz),
                "sample_rate": int(sample_rate),
                "bandwidth": float(bandwidth) if bandwidth is not None else None,
                "gain": float(gain) if gain is not None else None,
                "channel": int(channel),
                "antenna": str(antenna) if antenna else None,
                "symbol_rate": int(symbol_rate),
                "deviation_hz": int(deviation_hz),
            }

            rx_dir = getattr(SoapySDR, "SOAPY_SDR_RX", None)
            fmt = getattr(SoapySDR, "SOAPY_SDR_CF32", None)
            if rx_dir is None or fmt is None:
                return False, "SoapySDR_constants_missing", {}

            self._sdr.setSampleRate(rx_dir, channel, int(sample_rate))
            if bandwidth is not None:
                try:
                    self._sdr.setBandwidth(rx_dir, channel, float(bandwidth))
                except Exception:
                    pass
            if antenna:
                try:
                    self._sdr.setAntenna(rx_dir, channel, str(antenna))
                except Exception:
                    pass
            if gain is not None:
                try:
                    self._sdr.setGain(rx_dir, channel, float(gain))
                except Exception:
                    pass

            self._sdr.setFrequency(rx_dir, channel, float(frequency_hz))

            self._rx_stream = self._sdr.setupStream(rx_dir, fmt, [channel])
            self._sdr.activateStream(self._rx_stream)

            self._rx_stop.clear()
            self._rx_active = True
            self._rx_last_error = None

            def _rx_loop() -> None:
                buf = np.zeros(8192, np.complex64)
                while not self._rx_stop.is_set() and self._rx_active:
                    try:
                        sr = self._sdr.readStream(self._rx_stream, [buf], len(buf))
                    except Exception as e:
                        self._rx_last_error = str(e)
                        break

                    ret = None
                    if isinstance(sr, tuple) and sr:
                        ret = int(sr[0])
                    else:
                        ret = int(getattr(sr, "ret", 0))

                    if ret <= 0:
                        continue

                    samples = buf[:ret].copy()
                    self._rx_frames += 1

                    try:
                        pwr = float((samples.real * samples.real + samples.imag * samples.imag).mean())
                        pwr_db = 10.0 * float(np.log10(max(pwr, 1e-12)))
                    except Exception:
                        pwr_db = None

                    if self._rx_samples_per_symbol > 0:
                        try:
                            self._consume_samples(samples, int(sample_rate))
                        except Exception:
                            pass

                    extra = {}
                    if pwr_db is not None:
                        extra["rssi_db"] = pwr_db
                    self._publish_metrics(extra)

                self._rx_active = False
                self._close_stream()

            self._rx_thread = threading.Thread(target=_rx_loop, daemon=True, name="CommsSDRRx")
            self._rx_thread.start()

            return True, "", self.get_status()
        except Exception as e:
            self._rx_last_error = str(e)
            self._rx_active = False
            self._close_stream()
            return False, str(e), {}

    def transmit_fsk(
        self,
        frequency_hz: float,
        payload: bytes,
        sample_rate: int = 1_000_000,
        bandwidth: Optional[float] = None,
        gain: Optional[float] = None,
        channel: int = 0,
        antenna: Optional[str] = None,
        symbol_rate: int = 1200,
        deviation_hz: int = 5000,
        amplitude: float = 0.35,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        ok, err = self._ensure_open()
        if not ok:
            self._tx_last_error = err
            return False, err, {}

        try:
            import SoapySDR
            import numpy as np

            tx_dir = getattr(SoapySDR, "SOAPY_SDR_TX", None)
            rx_dir = getattr(SoapySDR, "SOAPY_SDR_RX", None)
            fmt = getattr(SoapySDR, "SOAPY_SDR_CF32", None)
            if tx_dir is None or rx_dir is None or fmt is None:
                self._tx_last_error = "SoapySDR_constants_missing"
                return False, self._tx_last_error, {}

            if int(getattr(self._sdr, "getNumChannels", lambda *_: 0)(tx_dir)) <= 0:
                self._tx_last_error = "no_tx_channels"
                return False, self._tx_last_error, {}

            if len(payload) > 512:
                return False, "payload_too_large", {}

            self._sdr.setSampleRate(tx_dir, channel, int(sample_rate))
            if bandwidth is not None:
                try:
                    self._sdr.setBandwidth(tx_dir, channel, float(bandwidth))
                except Exception:
                    pass
            if antenna:
                try:
                    self._sdr.setAntenna(tx_dir, channel, str(antenna))
                except Exception:
                    pass
            if gain is not None:
                try:
                    self._sdr.setGain(tx_dir, channel, float(gain))
                except Exception:
                    pass

            self._sdr.setFrequency(tx_dir, channel, float(frequency_hz))

            frame = self._build_frame(payload)
            bits = self._bytes_to_bits(frame)

            samples_per_symbol = max(1, int(int(sample_rate) / max(1, int(symbol_rate))))
            phase = 0.0
            out = np.empty(len(bits) * samples_per_symbol, dtype=np.complex64)
            two_pi = 2.0 * np.pi
            n = np.arange(samples_per_symbol, dtype=np.float64)
            idx = 0
            for bit in bits:
                freq = float(deviation_hz if bit else -deviation_hz)
                ph = phase + (two_pi * freq * n / float(sample_rate))
                out[idx : idx + samples_per_symbol] = (amplitude * np.cos(ph) + 1j * amplitude * np.sin(ph)).astype(
                    np.complex64
                )
                idx += samples_per_symbol
                phase = float(ph[-1] + two_pi * freq / float(sample_rate))

            tx_stream = self._sdr.setupStream(tx_dir, fmt, [channel])
            self._sdr.activateStream(tx_stream)
            try:
                sent = 0
                while sent < len(out):
                    chunk = out[sent : sent + 8192]
                    try:
                        wr = self._sdr.writeStream(tx_stream, [chunk], len(chunk))
                    except Exception:
                        break

                    ret = None
                    if isinstance(wr, tuple) and wr:
                        ret = int(wr[0])
                    else:
                        ret = int(getattr(wr, "ret", 0))

                    if ret <= 0:
                        break
                    sent += ret

                pad = np.zeros(4096, np.complex64)
                try:
                    self._sdr.writeStream(tx_stream, [pad], len(pad))
                except Exception:
                    pass

            finally:
                try:
                    self._sdr.deactivateStream(tx_stream)
                except Exception:
                    pass
                try:
                    self._sdr.closeStream(tx_stream)
                except Exception:
                    pass

            self._tx_last_error = None
            return True, "", {
                "frequency_hz": float(frequency_hz),
                "bytes": len(payload),
                "sample_rate": int(sample_rate),
                "symbol_rate": int(symbol_rate),
                "deviation_hz": int(deviation_hz),
                "frame_crc32": binascii.crc32(payload) & 0xFFFFFFFF,
            }
        except Exception as e:
            self._tx_last_error = str(e)
            return False, str(e), {}

    def _build_frame(self, payload: bytes) -> bytes:
        preamble = bytes([0xAA]) * int(self._preamble_len)
        sync = self._sync_bytes
        length = len(payload).to_bytes(2, "big", signed=False)
        body = length + payload
        crc = (binascii.crc32(body) & 0xFFFFFFFF).to_bytes(4, "big", signed=False)
        return preamble + sync + body + crc

    def _bytes_to_bits(self, data: bytes) -> List[int]:
        bits: List[int] = []
        for b in data:
            for i in range(7, -1, -1):
                bits.append(1 if (b >> i) & 1 else 0)
        return bits

    def _bits_to_bytes(self, bits: List[int]) -> bytes:
        out = bytearray()
        acc = 0
        n = 0
        for bit in bits:
            acc = (acc << 1) | (1 if bit else 0)
            n += 1
            if n == 8:
                out.append(acc & 0xFF)
                acc = 0
                n = 0
        return bytes(out)

    def _consume_samples(self, samples, sample_rate: int) -> None:
        import numpy as np

        if samples is None or len(samples) < 4:
            return

        ph = np.angle(samples[1:] * np.conj(samples[:-1]))
        inst_freq = (ph * float(sample_rate)) / (2.0 * np.pi)

        sps = int(self._rx_samples_per_symbol)
        if sps <= 0:
            return

        n_symbols = int(len(inst_freq) / sps)
        if n_symbols <= 0:
            return

        inst_freq = inst_freq[: n_symbols * sps]
        sym = inst_freq.reshape((n_symbols, sps)).mean(axis=1)
        bits = (sym > 0.0).astype(np.int8).tolist()

        self._rx_bits.extend(int(b) for b in bits)
        if len(self._rx_bits) > 65536:
            self._rx_bits = self._rx_bits[-32768:]

        self._try_decode_frames()

    def _try_decode_frames(self) -> None:
        sync_bits = self._bytes_to_bits(self._sync_bytes)
        bits = self._rx_bits
        if len(bits) < 64:
            return

        max_scan = max(0, len(bits) - 16)
        idx = 0
        while idx < max_scan:
            if bits[idx : idx + 16] != sync_bits:
                idx += 1
                continue

            start = idx + 16
            if start + 16 > len(bits):
                return

            length_bits = bits[start : start + 16]
            length_bytes = self._bits_to_bytes(length_bits)
            if len(length_bytes) < 2:
                idx += 1
                continue

            payload_len = int.from_bytes(length_bytes[:2], "big", signed=False)
            frame_bits = 16 + 16 + (payload_len * 8) + 32
            if idx + frame_bits > len(bits):
                return

            payload_start = start + 16
            payload_end = payload_start + (payload_len * 8)
            crc_start = payload_end
            crc_end = crc_start + 32

            payload = self._bits_to_bytes(bits[payload_start:payload_end])
            crc_bytes = self._bits_to_bytes(bits[crc_start:crc_end])
            if len(crc_bytes) < 4:
                idx += 1
                continue

            body = length_bytes[:2] + payload
            crc_expected = int.from_bytes(crc_bytes[:4], "big", signed=False)
            crc_calc = binascii.crc32(body) & 0xFFFFFFFF
            if crc_calc == crc_expected:
                self._publish_rx_payload(payload)
                del bits[:crc_end]
                max_scan = max(0, len(bits) - 16)
                idx = 0
                continue

            idx += 1

    def _publish_rx_payload(self, payload: bytes) -> None:
        if not self.event_bus:
            return
        try:
            text = payload.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        try:
            self.event_bus.publish(
                "comms.radio.receive.data",
                {
                    "timestamp": time.time(),
                    "payload": text,
                    "payload_hex": payload.hex(),
                    "bytes": len(payload),
                    "config": dict(self._rx_config),
                },
            )
        except Exception:
            pass
