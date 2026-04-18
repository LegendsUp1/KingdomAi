# Webcam Successful Tests Analysis

## test_webcam_live_wsl2_v3.py (SUCCESSFUL)

- **Flow**: `main()` tests connectivity with `requests.get(mjpeg_url, timeout=3)`. If it fails, exits with code 1 (no window). If OK, creates `WebcamWindow(mjpeg_url)`.
- **Key**: Window creates `MJPEGReader(mjpeg_url)` and calls **`reader.start()` immediately** – reader thread starts regardless.
- **Display**: `startup_timer` (10ms) runs `_check_first_frame`. When `reader.first_frame_ready.is_set()`, stops startup timer, clears "Connecting...", starts **`frame_timer.start(8)`** (~120 FPS poll).
- **Frame extraction**: `find(b'\xff\xd8')` / `find(b'\xff\xd9')`, chunk 8192.
- **IP**: `get_windows_host_ip()` uses `ip route show default` (via), then resolv.conf. Does **not** test which IP works.

## test_kingdom_unified.py (SUCCESSFUL)

- **IP**: `get_windows_host_ip()` **tests each candidate IP** with `requests.get(f"http://{ip}:8090/brio.mjpg", timeout=2)` and **returns the IP that responds**.
- **Start**: `QTimer.singleShot(100, self._start_webcam)` – delay 100ms then `reader.start()` + `startup_timer.start(10)`.
- **Reader**: `_read_loop` has **reconnection loop** – on disconnect/error it sleeps and retries. So even if server is not up at first, when it comes up, reader connects.
- **Display**: Same – when `first_frame_ready`, start `frame_timer.start(8)`.
- **Frame extraction**: `rfind(b'\xff\xd9')` / `rfind(b'\xff\xd8', 0, end)`, chunk 4096, buffer cap 2M.

## thoth_qt.py (CURRENT – BROKEN)

- **Flow**: `_start_mjpeg_camera()` checks server with `requests.get(mjpeg_url, timeout=2)`. If not running, tries PowerShell auto-start, **sleep(8)**, retry. If still not running: sets "Camera: MJPEG server not running!" and **`return`**.
- **Root cause**: When the server is not running we **never start the reader thread or the poll timer**. So no frames are ever requested or displayed.
- **Difference**: Successful tests **always start the reader** (and optionally delay 100ms). The reader’s loop retries. In thoth_qt we **exit before starting the reader** when the initial check fails.

## Fix (from successful logic)

1. **Do not return** when MJPEG server check fails. Always start the reader thread and the 8ms poll timer (and status "Connecting..."). Rely on `_mjpeg_read_loop`’s existing retry logic to connect when the server is available.
2. Optionally: Prefer **testing which IP works** (like test_kingdom_unified) when building mjpeg_url in WSL.
3. Optionally: On native Windows, add **direct OpenCV** fallback (cv2.VideoCapture(0)) when MJPEG is not available so the camera works without the server.
