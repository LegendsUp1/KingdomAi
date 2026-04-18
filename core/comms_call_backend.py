import os
import queue
import socket
import threading
import time
from typing import Any, Dict, Optional, Tuple

def _is_wsl2() -> bool:
    """Detect if running in WSL2 environment."""
    try:
        with open("/proc/version", "r") as f:
            content = f.read().lower()
            return "microsoft" in content or "wsl" in content
    except Exception:
        return False

_IN_WSL2 = _is_wsl2()


class UDPAudioCallBackend:
    def __init__(self, event_bus=None, publish_chat=None):
        self.event_bus = event_bus
        self._publish_chat = publish_chat

        self._stop = threading.Event()
        self._active = False

        self._sock: Optional[socket.socket] = None
        self._remote: Optional[Tuple[str, int]] = None
        self._local_port: Optional[int] = None

        self._rx_queue: "queue.Queue[bytes]" = queue.Queue(maxsize=180)
        self._threads: list[threading.Thread] = []

        self.sample_rate = 48000
        self.blocksize = 960
        self.channels = 1

        self.tx_packets = 0
        self.rx_packets = 0
        self.last_rx_ts: Optional[float] = None
        self.last_tx_ts: Optional[float] = None
        self._last_metrics_publish = 0.0

    def is_active(self) -> bool:
        return self._active

    def get_status(self) -> Dict[str, Any]:
        return {
            "active": self._active,
            "remote": {"host": self._remote[0], "port": self._remote[1]} if self._remote else None,
            "local_port": self._local_port,
            "sample_rate": self.sample_rate,
            "blocksize": self.blocksize,
            "channels": self.channels,
            "tx_packets": self.tx_packets,
            "rx_packets": self.rx_packets,
            "last_rx_ts": self.last_rx_ts,
            "last_tx_ts": self.last_tx_ts,
            "rx_queue": getattr(self._rx_queue, "qsize", lambda: 0)(),
        }

    def start(
        self,
        remote_host: str,
        remote_port: int,
        local_port: Optional[int] = None,
        sample_rate: int = 48000,
        blocksize: int = 960,
        channels: int = 1,
    ) -> Tuple[bool, str]:
        if self._active:
            return False, "call_already_active"

        if _IN_WSL2:
            return False, "wsl2_audio_not_supported_use_windows_host_bridge"

        try:
            import sounddevice as sd
        except Exception:
            return False, "sounddevice_unavailable"

        try:
            self.sample_rate = int(sample_rate)
            self.blocksize = int(blocksize)
            self.channels = int(channels)
            self._remote = (str(remote_host), int(remote_port))

            if local_port is None:
                local_port = int(remote_port)
            self._local_port = int(local_port)

            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2**20)
            except Exception:
                pass
            self._sock.bind(("0.0.0.0", self._local_port))
            self._sock.settimeout(0.25)

            self.tx_packets = 0
            self.rx_packets = 0
            self.last_rx_ts = None
            self.last_tx_ts = None
            self._last_metrics_publish = 0.0

            while not self._rx_queue.empty():
                try:
                    self._rx_queue.get_nowait()
                except Exception:
                    break

            self._stop.clear()
            self._active = True

            self._threads = [
                threading.Thread(
                    target=self._capture_loop,
                    args=(sd,),
                    daemon=True,
                    name="CommsCallCapture",
                ),
                threading.Thread(
                    target=self._recv_loop,
                    daemon=True,
                    name="CommsCallRecv",
                ),
                threading.Thread(
                    target=self._playback_loop,
                    args=(sd,),
                    daemon=True,
                    name="CommsCallPlayback",
                ),
            ]
            for t in self._threads:
                t.start()

            return True, ""
        except Exception as e:
            self.stop()
            return False, str(e)

    def stop(self) -> None:
        self._stop.set()
        self._active = False

        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

        for t in list(self._threads):
            try:
                if t.is_alive():
                    t.join(timeout=1.0)
            except Exception:
                pass
        self._threads = []

        while not self._rx_queue.empty():
            try:
                self._rx_queue.get_nowait()
            except Exception:
                break

    def _capture_loop(self, sd) -> None:
        remote = self._remote
        sock = self._sock
        if remote is None or sock is None:
            self._active = False
            return

        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                blocksize=self.blocksize,
            ) as stream:
                while not self._stop.is_set() and self._active:
                    data, _overflowed = stream.read(self.blocksize)
                    if not data:
                        continue
                    try:
                        sock.sendto(data, remote)
                        self.tx_packets += 1
                        self.last_tx_ts = time.time()
                    except Exception:
                        pass
                    self._maybe_publish_metrics()
        except Exception as e:
            if callable(self._publish_chat):
                self._publish_chat(f"Call capture error: {e}")
            self._active = False

    def _recv_loop(self) -> None:
        sock = self._sock
        if sock is None:
            self._active = False
            return

        while not self._stop.is_set() and self._active:
            try:
                data, _addr = sock.recvfrom(65536)
            except socket.timeout:
                continue
            except Exception:
                break

            if not data:
                continue

            self.rx_packets += 1
            self.last_rx_ts = time.time()
            try:
                self._rx_queue.put_nowait(data)
            except Exception:
                pass
            self._maybe_publish_metrics()

        self._active = False

    def _playback_loop(self, sd) -> None:
        silence = b"\x00" * (self.blocksize * self.channels * 2)
        try:
            with sd.RawOutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                blocksize=self.blocksize,
            ) as stream:
                while not self._stop.is_set() and self._active:
                    try:
                        data = self._rx_queue.get(timeout=0.25)
                    except Exception:
                        data = silence
                    if not data:
                        data = silence
                    try:
                        stream.write(data)
                    except Exception:
                        pass
                    self._maybe_publish_metrics()
        except Exception as e:
            if callable(self._publish_chat):
                self._publish_chat(f"Call playback error: {e}")
            self._active = False

    def _maybe_publish_metrics(self) -> None:
        if not self.event_bus:
            return
        now = time.time()
        if now - self._last_metrics_publish < 1.0:
            return
        self._last_metrics_publish = now
        try:
            self.event_bus.publish(
                "comms.call.metrics",
                {"timestamp": now, **self.get_status()},
            )
        except Exception:
            pass
