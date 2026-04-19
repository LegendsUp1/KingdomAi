#!/usr/bin/env python3
"""
SOTA 2026: Windows Camera MJPEG Server for WSL2 Integration

This script runs on Windows and streams webcam video as MJPEG over HTTP,
allowing WSL2 applications (like Kingdom AI) to access the webcam.

USAGE:
    1. Run this script on Windows: python windows_camera_server.py
    2. In WSL2, access the stream: http://<windows-ip>:8090/video.mjpg
    3. Or use localhost if using port forwarding: http://localhost:8090/video.mjpg

FEATURES:
    - Logitech Brio 4K optimization
    - MJPEG streaming for low latency
    - REST API for camera control
    - Auto-detection of available cameras

Based on SOTA 2026 research: https://medium.com/@mominaman/stream-webcam-to-wsl-opencv-983e90ed7301
"""

import cv2
import threading
import time
import argparse
import sys
from flask import Flask, Response, jsonify, render_template_string

app = Flask(__name__)

# Global camera state
camera = None
camera_lock = threading.Lock()
output_frame = None
frame_lock = threading.Lock()

# Camera settings
CAMERA_INDEX = 1  # Brio is usually index 1
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FPS = 15
JPEG_QUALITY = 70


def find_cameras():
    """Find all available cameras."""
    available = []
    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available.append(i)
            cap.release()
    return available


def init_camera(index=None):
    """Initialize the camera with Brio-optimized settings."""
    global camera, CAMERA_INDEX
    
    if index is not None:
        CAMERA_INDEX = index
    
    with camera_lock:
        if camera is not None:
            camera.release()
        
        # Try DirectShow on Windows for best Brio compatibility
        camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        
        if not camera.isOpened():
            print(f"❌ Failed to open camera {CAMERA_INDEX}")
            return False
        
        # Set Brio-optimized settings
        camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('M', 'J', 'P', 'G'))
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        camera.set(cv2.CAP_PROP_FPS, FPS)
        camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        
        # Verify settings
        actual_width = camera.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = camera.get(cv2.CAP_PROP_FPS)
        
        print(f"✅ Camera {CAMERA_INDEX} initialized: {int(actual_width)}x{int(actual_height)} @ {int(actual_fps)}fps")
        return True


def capture_frames():
    """Background thread to capture frames continuously."""
    global output_frame, camera
    
    while True:
        try:
            with camera_lock:
                if camera is None or not camera.isOpened():
                    time.sleep(0.1)
                    continue
                
                ret, frame = camera.read()
            
            if not ret or frame is None:
                time.sleep(0.01)
                continue
            
            # Resize if frame is too large (prevents OOM)
            h, w = frame.shape[:2]
            if w > FRAME_WIDTH or h > FRAME_HEIGHT:
                frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            
            # Encode as JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
            _, jpeg = cv2.imencode('.jpg', frame, encode_param)
            
            with frame_lock:
                output_frame = jpeg.tobytes()
            
            time.sleep(1.0 / FPS)
        except Exception as e:
            print(f'Frame capture error: {e}')
            time.sleep(0.1)


def generate_mjpeg():
    """Generate MJPEG stream."""
    global output_frame
    
    while True:
        with frame_lock:
            if output_frame is None:
                time.sleep(0.01)
                continue
            frame = output_frame
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/')
def index():
    """Home page with camera preview."""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Kingdom AI Camera Server</title>
    <style>
        body { font-family: Arial, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        h1 { color: #00d4ff; }
        img { max-width: 100%; border: 2px solid #00d4ff; border-radius: 8px; }
        .info { background: #16213e; padding: 15px; border-radius: 8px; margin: 10px 0; }
        code { background: #0f3460; padding: 2px 8px; border-radius: 4px; }
        a { color: #00d4ff; }
    </style>
</head>
<body>
    <h1>🎥 Kingdom AI Camera Server</h1>
    <div class="info">
        <p><strong>MJPEG Stream URL:</strong> <code>http://localhost:8090/video.mjpg</code></p>
        <p><strong>Snapshot URL:</strong> <code>http://localhost:8090/snapshot.jpg</code></p>
        <p><strong>For WSL2:</strong> Use <code>http://$(cat /etc/resolv.conf | grep nameserver | cut -d' ' -f2):8090/video.mjpg</code></p>
    </div>
    <h2>Live Preview:</h2>
    <img src="/video.mjpg" alt="Camera Stream">
    <div class="info">
        <p><a href="/api/cameras">📋 List Cameras</a> | <a href="/api/status">📊 Status</a></p>
    </div>
</body>
</html>
    ''')


@app.route('/video.mjpg')
@app.route('/brio.mjpg')
def video_feed():
    """MJPEG video stream endpoint."""
    return Response(generate_mjpeg(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/snapshot.jpg')
def snapshot():
    """Single JPEG snapshot."""
    global output_frame
    with frame_lock:
        if output_frame is None:
            return "No frame available", 503
        return Response(output_frame, mimetype='image/jpeg')


@app.route('/api/cameras')
def api_cameras():
    """List available cameras."""
    return jsonify({
        'cameras': find_cameras(),
        'current': CAMERA_INDEX
    })


@app.route('/api/status')
def api_status():
    """Get server status."""
    with camera_lock:
        is_open = camera is not None and camera.isOpened()
    
    return jsonify({
        'status': 'running',
        'camera_open': is_open,
        'camera_index': CAMERA_INDEX,
        'resolution': f'{FRAME_WIDTH}x{FRAME_HEIGHT}',
        'fps': FPS,
        'endpoints': {
            'mjpeg': '/video.mjpg',
            'brio_mjpeg': '/brio.mjpg',
            'snapshot': '/snapshot.jpg'
        }
    })


@app.route('/api/switch/<int:index>')
def api_switch_camera(index):
    """Switch to a different camera."""
    if init_camera(index):
        return jsonify({'success': True, 'camera': index})
    return jsonify({'success': False, 'error': f'Failed to open camera {index}'}), 500


def main():
    parser = argparse.ArgumentParser(description='Windows Camera MJPEG Server for WSL2')
    parser.add_argument('--camera', '-c', type=int, default=1,
                        help='Camera index (default: 1 for Brio)')
    parser.add_argument('--port', '-p', type=int, default=8090,
                        help='Server port (default: 8090)')
    parser.add_argument('--width', '-W', type=int, default=640,
                        help='Frame width (default: 640)')
    parser.add_argument('--height', '-H', type=int, default=480,
                        help='Frame height (default: 480)')
    parser.add_argument('--fps', '-f', type=int, default=15,
                        help='Frames per second (default: 15)')
    parser.add_argument('--quality', '-q', type=int, default=70,
                        help='JPEG quality 1-100 (default: 70)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List available cameras and exit')
    
    args = parser.parse_args()
    
    if args.list:
        cameras = find_cameras()
        print(f"Available cameras: {cameras}")
        return 0
    
    global CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT, FPS, JPEG_QUALITY
    CAMERA_INDEX = args.camera
    FRAME_WIDTH = args.width
    FRAME_HEIGHT = args.height
    FPS = args.fps
    JPEG_QUALITY = args.quality
    
    print("=" * 60)
    print("🎥 Kingdom AI Camera Server - SOTA 2026")
    print("=" * 60)
    
    # Find available cameras
    cameras = find_cameras()
    print(f"Available cameras: {cameras}")
    
    if not cameras:
        print("❌ No cameras found!")
        return 1
    
    if CAMERA_INDEX not in cameras:
        print(f"⚠️ Camera {CAMERA_INDEX} not available, using {cameras[0]}")
        CAMERA_INDEX = cameras[0]
    
    # Initialize camera
    if not init_camera(CAMERA_INDEX):
        print("❌ Failed to initialize camera")
        return 1
    
    # Start capture thread
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()
    print("✅ Frame capture thread started")
    
    # Print connection info
    print()
    print("📡 Server starting...")
    print(f"   Local:     http://localhost:{args.port}")
    print(f"   MJPEG:     http://localhost:{args.port}/video.mjpg")
    print(f"   Snapshot:  http://localhost:{args.port}/snapshot.jpg")
    print()
    print("💡 WSL2 Usage:")
    print(f"   cv2.VideoCapture('http://localhost:{args.port}/video.mjpg')")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=args.port, threaded=True)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    finally:
        with camera_lock:
            if camera is not None:
                camera.release()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
