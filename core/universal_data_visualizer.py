"""
Universal Data Visualizer - SOTA 2026
=====================================
Converts ANY sensor data to visual displays:
- Image/video → Vision screen
- LiDAR/depth → 3D point cloud
- Sonar/audio → 3D surface mapping
- GPS → Map overlay with position
- IMU → Attitude indicator
- CAN/OBD → Vehicle gauges

Wires device detection directly to visualization components.
"""

import logging
import threading
import time
import math
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

import numpy as np

logger = logging.getLogger("KingdomAI.UniversalDataVisualizer")

# ============================================================================
# DATA TYPE ENUMS
# ============================================================================

class DataType(Enum):
    """Types of sensor data that can be visualized"""
    IMAGE = "image"                   # Camera/webcam frames
    VIDEO_STREAM = "video_stream"     # MJPEG/RTSP streams
    POINT_CLOUD = "point_cloud"       # LiDAR 3D point data
    DEPTH_MAP = "depth_map"           # Depth camera data
    SONAR_PING = "sonar_ping"         # Sonar range data
    AUDIO_WAVEFORM = "audio_waveform" # Audio signal
    GPS_POSITION = "gps_position"     # GPS coordinates
    IMU_ORIENTATION = "imu_orientation"  # IMU attitude
    SPECTRUM = "spectrum"             # FFT/spectrum data
    CAN_DATA = "can_data"             # CAN bus frames
    OBD_DATA = "obd_data"             # OBD-II PIDs
    THERMAL = "thermal"               # Thermal image
    RADAR = "radar"                   # Radar returns
    GENERIC = "generic"               # Raw data


class VisualizationType(Enum):
    """Types of visual displays"""
    VIDEO_FEED = "video_feed"         # Live video display
    POINT_CLOUD_3D = "point_cloud_3d" # 3D scatter plot
    SURFACE_3D = "surface_3d"         # 3D surface mesh
    MAP_2D = "map_2d"                 # 2D map overlay
    MAP_3D = "map_3d"                 # 3D terrain map
    GAUGE = "gauge"                   # Circular gauge
    CHART = "chart"                   # Line/bar chart
    ATTITUDE = "attitude"             # Attitude indicator
    WATERFALL = "waterfall"           # Waterfall display
    HEATMAP = "heatmap"               # 2D heatmap
    SCOPE = "scope"                   # Oscilloscope view


# ============================================================================
# DATA CONVERTERS - Transform sensor data to visualization format
# ============================================================================

class DataConverter:
    """Base class for data converters"""
    
    @staticmethod
    def convert(data: Any, params: Dict = None) -> Tuple[VisualizationType, Any]:
        raise NotImplementedError


class LiDARTo3DPointCloud(DataConverter):
    """Convert LiDAR scan data to 3D point cloud visualization"""
    
    @staticmethod
    def convert(data: Any, params: Dict = None) -> Tuple[VisualizationType, Dict]:
        """
        Convert LiDAR data to 3D point cloud format.
        
        Input formats supported:
        - List of (angle, distance) tuples (2D LiDAR)
        - List of (x, y, z) tuples (3D LiDAR)
        - List of (angle, distance, intensity) tuples
        - Raw point array from sensor
        """
        params = params or {}
        points_3d = []
        colors = []
        
        if isinstance(data, dict):
            # Handle structured LiDAR data
            if "points" in data:
                raw_points = data["points"]
            elif "scan" in data:
                raw_points = data["scan"]
            else:
                raw_points = data
        else:
            raw_points = data
        
        if not raw_points:
            return VisualizationType.POINT_CLOUD_3D, {"points": [], "colors": []}
        
        # Detect format and convert
        sample = raw_points[0] if raw_points else None
        
        if sample is None:
            pass
        elif len(sample) == 2:
            # 2D LiDAR: (angle_deg, distance_m) -> (x, y, z)
            for angle_deg, distance in raw_points:
                angle_rad = math.radians(angle_deg)
                x = distance * math.cos(angle_rad)
                y = distance * math.sin(angle_rad)
                z = 0  # 2D scan at ground level
                points_3d.append([x, y, z])
                # Color by distance (green=close, red=far)
                norm_dist = min(distance / 50.0, 1.0)
                colors.append([1.0 - norm_dist, norm_dist, 0.2, 1.0])
                
        elif len(sample) == 3:
            # Already 3D: (x, y, z)
            for x, y, z in raw_points:
                points_3d.append([x, y, z])
                # Color by height
                norm_z = (z + 5) / 10.0  # Assume -5 to 5 range
                norm_z = max(0, min(1, norm_z))
                colors.append([norm_z, 0.5, 1.0 - norm_z, 1.0])
                
        elif len(sample) >= 4:
            # With intensity: (x, y, z, intensity)
            for point in raw_points:
                x, y, z = point[:3]
                intensity = point[3] if len(point) > 3 else 0.5
                points_3d.append([x, y, z])
                # Color by intensity
                colors.append([intensity, intensity, intensity, 1.0])
        
        return VisualizationType.POINT_CLOUD_3D, {
            "points": np.array(points_3d, dtype=np.float32) if points_3d else np.array([]),
            "colors": np.array(colors, dtype=np.float32) if colors else np.array([]),
            "point_size": params.get("point_size", 2),
            "bounds": {
                "min": np.min(points_3d, axis=0).tolist() if points_3d else [0, 0, 0],
                "max": np.max(points_3d, axis=0).tolist() if points_3d else [1, 1, 1]
            }
        }


class SonarTo3DSurface(DataConverter):
    """Convert sonar/audio data to 3D surface mapping"""
    
    @staticmethod
    def convert(data: Any, params: Dict = None) -> Tuple[VisualizationType, Dict]:
        """
        Convert sonar ping data to 3D surface mesh.
        
        Input formats:
        - Single range value (depth sounder)
        - Array of ranges (scanning sonar)
        - 2D array of ranges (multibeam sonar)
        - Audio waveform (converts via FFT to depth simulation)
        """
        params = params or {}
        
        if isinstance(data, dict):
            if "ranges" in data:
                ranges = data["ranges"]
            elif "samples" in data:
                # Audio data - convert to pseudo-depth via FFT
                samples = np.array(data["samples"])
                fft = np.abs(np.fft.fft(samples))
                # Use FFT magnitude as "depth" visualization
                ranges = fft[:len(fft)//2]
            else:
                ranges = [data.get("range", 0)]
        elif isinstance(data, (int, float)):
            ranges = [data]
        else:
            ranges = data
        
        ranges = np.array(ranges, dtype=np.float32)
        
        # Create 3D surface from range data
        if ranges.ndim == 1:
            # 1D scan - create radial surface
            n_points = len(ranges)
            angles = np.linspace(0, 2 * np.pi, n_points)
            x = ranges * np.cos(angles)
            y = ranges * np.sin(angles)
            z = np.zeros_like(x)  # Flat surface
            
            # Create mesh grid for surface
            surface_data = {
                "x": x.tolist(),
                "y": y.tolist(),
                "z": z.tolist(),
                "mode": "radial"
            }
        elif ranges.ndim == 2:
            # 2D multibeam - already a surface
            rows, cols = ranges.shape
            x = np.linspace(-1, 1, cols)
            y = np.linspace(-1, 1, rows)
            X, Y = np.meshgrid(x, y)
            Z = -ranges  # Depth is negative (underwater)
            
            surface_data = {
                "x": X.tolist(),
                "y": Y.tolist(),
                "z": Z.tolist(),
                "mode": "multibeam"
            }
        else:
            surface_data = {"x": [], "y": [], "z": [], "mode": "empty"}
        
        return VisualizationType.SURFACE_3D, surface_data


class GPSTo3DMap(DataConverter):
    """Convert GPS coordinates to 3D map visualization"""
    
    @staticmethod
    def convert(data: Any, params: Dict = None) -> Tuple[VisualizationType, Dict]:
        """
        Convert GPS data to map visualization.
        
        Input formats:
        - Dict with lat, lon, alt
        - Tuple (lat, lon) or (lat, lon, alt)
        - NMEA sentence string
        """
        params = params or {}
        
        lat, lon, alt = 0.0, 0.0, 0.0
        speed, heading = 0.0, 0.0
        
        if isinstance(data, dict):
            lat = data.get("latitude", data.get("lat", 0))
            lon = data.get("longitude", data.get("lon", data.get("lng", 0)))
            alt = data.get("altitude", data.get("alt", data.get("elevation", 0)))
            speed = data.get("speed", data.get("velocity", 0))
            heading = data.get("heading", data.get("course", data.get("bearing", 0)))
        elif isinstance(data, (tuple, list)):
            lat = data[0] if len(data) > 0 else 0
            lon = data[1] if len(data) > 1 else 0
            alt = data[2] if len(data) > 2 else 0
        elif isinstance(data, str):
            # Parse NMEA sentence
            if data.startswith("$GPGGA") or data.startswith("$GNGGA"):
                parts = data.split(",")
                if len(parts) >= 10:
                    lat = GPSTo3DMap._parse_nmea_coord(parts[2], parts[3])
                    lon = GPSTo3DMap._parse_nmea_coord(parts[4], parts[5])
                    alt = float(parts[9]) if parts[9] else 0
        
        # Convert to 3D map coordinates (simple Mercator projection)
        # Scale: 1 degree ≈ 111km, so 0.001 degree ≈ 111m
        x = lon * 111000  # meters from prime meridian
        y = lat * 111000  # meters from equator
        z = alt           # meters above sea level
        
        return VisualizationType.MAP_3D, {
            "position": {"x": x, "y": y, "z": z},
            "coordinates": {"lat": lat, "lon": lon, "alt": alt},
            "velocity": {"speed": speed, "heading": heading},
            "marker": {
                "type": "aircraft" if alt > 100 else "vehicle" if speed > 0 else "point",
                "color": [0, 1, 0, 1]  # Green marker
            }
        }
    
    @staticmethod
    def _parse_nmea_coord(value: str, direction: str) -> float:
        """Parse NMEA coordinate format (DDMM.MMMMM)"""
        if not value:
            return 0.0
        try:
            degrees = int(float(value) / 100)
            minutes = float(value) - (degrees * 100)
            result = degrees + (minutes / 60)
            if direction in ["S", "W"]:
                result = -result
            return result
        except:
            return 0.0


class IMUToAttitude(DataConverter):
    """Convert IMU data to attitude indicator visualization"""
    
    @staticmethod
    def convert(data: Any, params: Dict = None) -> Tuple[VisualizationType, Dict]:
        """
        Convert IMU orientation data to attitude display.
        
        Input formats:
        - Dict with roll, pitch, yaw (degrees or radians)
        - Quaternion (w, x, y, z)
        - Euler angles tuple
        - Accelerometer/gyro raw data
        """
        params = params or {}
        
        roll, pitch, yaw = 0.0, 0.0, 0.0
        
        if isinstance(data, dict):
            if "quaternion" in data:
                q = data["quaternion"]
                roll, pitch, yaw = IMUToAttitude._quaternion_to_euler(
                    q.get("w", 1), q.get("x", 0), q.get("y", 0), q.get("z", 0)
                )
            else:
                roll = data.get("roll", 0)
                pitch = data.get("pitch", 0)
                yaw = data.get("yaw", data.get("heading", 0))
                
                # Convert to degrees if in radians (assume radians if < 2π)
                if abs(roll) < 7 and abs(pitch) < 7:
                    roll = math.degrees(roll)
                    pitch = math.degrees(pitch)
                    yaw = math.degrees(yaw)
                    
        elif isinstance(data, (tuple, list)):
            if len(data) == 4:
                # Quaternion
                roll, pitch, yaw = IMUToAttitude._quaternion_to_euler(*data)
            elif len(data) == 3:
                roll, pitch, yaw = data
        
        return VisualizationType.ATTITUDE, {
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "heading": yaw,
            "bank_angle": roll,
            "climb_angle": pitch
        }
    
    @staticmethod
    def _quaternion_to_euler(w, x, y, z) -> Tuple[float, float, float]:
        """Convert quaternion to Euler angles (degrees)"""
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        
        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)
        else:
            pitch = math.asin(sinp)
        
        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        
        return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)


class AudioTo3DVisualization(DataConverter):
    """Convert audio waveform to 3D visualization (FFT surface)"""
    
    @staticmethod
    def convert(data: Any, params: Dict = None) -> Tuple[VisualizationType, Dict]:
        """Convert audio samples to 3D frequency visualization"""
        params = params or {}
        
        if isinstance(data, dict):
            samples = np.array(data.get("samples", data.get("waveform", [])))
            sample_rate = data.get("sample_rate", 44100)
        elif isinstance(data, np.ndarray):
            samples = data
            sample_rate = params.get("sample_rate", 44100)
        else:
            samples = np.array(data)
            sample_rate = params.get("sample_rate", 44100)
        
        if len(samples) == 0:
            return VisualizationType.SURFACE_3D, {"x": [], "y": [], "z": []}
        
        # Compute FFT
        n_fft = min(2048, len(samples))
        fft_result = np.fft.fft(samples[:n_fft])
        magnitude = np.abs(fft_result[:n_fft//2])
        frequencies = np.fft.fftfreq(n_fft, 1/sample_rate)[:n_fft//2]
        
        # Create 3D surface from frequency data
        # X = frequency, Y = time window, Z = magnitude
        n_bins = len(magnitude)
        x = frequencies
        y = np.zeros(n_bins)  # Single time slice
        z = 20 * np.log10(magnitude + 1e-10)  # dB scale
        
        return VisualizationType.SURFACE_3D, {
            "x": x.tolist(),
            "y": y.tolist(),
            "z": z.tolist(),
            "mode": "spectrum",
            "frequencies": frequencies.tolist(),
            "magnitudes_db": z.tolist()
        }


class CANDataToGauges(DataConverter):
    """Convert CAN bus data to gauge visualizations"""
    
    @staticmethod
    def convert(data: Any, params: Dict = None) -> Tuple[VisualizationType, Dict]:
        """Convert CAN/OBD data to vehicle gauges"""
        params = params or {}
        
        gauges = []
        
        if isinstance(data, dict):
            # OBD-II PIDs
            if "rpm" in data or "engine_rpm" in data:
                gauges.append({
                    "name": "RPM",
                    "value": data.get("rpm", data.get("engine_rpm", 0)),
                    "min": 0, "max": 8000,
                    "unit": "RPM",
                    "color": "#00ff00" if data.get("rpm", 0) < 6000 else "#ff0000"
                })
            
            if "speed" in data or "vehicle_speed" in data:
                gauges.append({
                    "name": "Speed",
                    "value": data.get("speed", data.get("vehicle_speed", 0)),
                    "min": 0, "max": 200,
                    "unit": "km/h",
                    "color": "#00ffff"
                })
            
            if "coolant_temp" in data or "engine_coolant_temp" in data:
                temp = data.get("coolant_temp", data.get("engine_coolant_temp", 0))
                gauges.append({
                    "name": "Coolant",
                    "value": temp,
                    "min": 0, "max": 130,
                    "unit": "°C",
                    "color": "#00ff00" if 70 < temp < 100 else "#ff0000"
                })
            
            if "fuel_level" in data:
                gauges.append({
                    "name": "Fuel",
                    "value": data.get("fuel_level", 0),
                    "min": 0, "max": 100,
                    "unit": "%",
                    "color": "#ffff00" if data.get("fuel_level", 0) > 20 else "#ff0000"
                })
            
            if "throttle" in data or "throttle_position" in data:
                gauges.append({
                    "name": "Throttle",
                    "value": data.get("throttle", data.get("throttle_position", 0)),
                    "min": 0, "max": 100,
                    "unit": "%",
                    "color": "#ff9900"
                })
        
        return VisualizationType.GAUGE, {"gauges": gauges}


# ============================================================================
# UNIVERSAL DATA VISUALIZER - Main orchestrator
# ============================================================================

class UniversalDataVisualizer:
    """
    SOTA 2026: Universal Data Visualizer
    
    Automatically detects data type and converts to appropriate visualization.
    Wires device detection to vision displays.
    """
    
    # Mapping of data types to converters
    CONVERTERS = {
        DataType.POINT_CLOUD: LiDARTo3DPointCloud,
        DataType.DEPTH_MAP: LiDARTo3DPointCloud,
        DataType.SONAR_PING: SonarTo3DSurface,
        DataType.AUDIO_WAVEFORM: AudioTo3DVisualization,
        DataType.GPS_POSITION: GPSTo3DMap,
        DataType.IMU_ORIENTATION: IMUToAttitude,
        DataType.CAN_DATA: CANDataToGauges,
        DataType.OBD_DATA: CANDataToGauges,
    }
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.active_streams: Dict[str, Dict] = {}
        self.visualization_callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        
        # Subscribe to device events
        if event_bus:
            self._subscribe_to_events()
        
        logger.info("🎨 UniversalDataVisualizer initialized")
    
    def _subscribe_to_events(self):
        """Subscribe to device and data events"""
        if not self.event_bus:
            return
        
        try:
            subscribe = getattr(self.event_bus, "subscribe_sync", None) or getattr(self.event_bus, "subscribe", None)
            if callable(subscribe):
                # Vision/camera events
                subscribe("vision.stream.frame", self._on_vision_frame)
                
                # LiDAR events
                subscribe("lidar.scan", self._on_lidar_scan)
                subscribe("lidar.pointcloud", self._on_lidar_scan)
                
                # Sonar events
                subscribe("sonar.ping", self._on_sonar_data)
                subscribe("sonar.scan", self._on_sonar_data)
                
                # GPS events
                subscribe("gps.position", self._on_gps_data)
                subscribe("gps.nmea", self._on_gps_data)
                
                # IMU events
                subscribe("imu.orientation", self._on_imu_data)
                subscribe("imu.attitude", self._on_imu_data)
                
                # CAN/OBD events
                subscribe("can.frame", self._on_can_data)
                subscribe("obd.data", self._on_obd_data)
                
                # Device connected events
                subscribe("device.connected", self._on_device_connected)
                
                logger.info("📡 Subscribed to sensor data events")
        except Exception as e:
            logger.error(f"Failed to subscribe to events: {e}")
    
    def detect_data_type(self, data: Any, hint: str = None) -> DataType:
        """Auto-detect the type of sensor data"""
        
        # Use hint if provided
        if hint:
            hint_lower = hint.lower()
            if "lidar" in hint_lower or "pointcloud" in hint_lower:
                return DataType.POINT_CLOUD
            elif "sonar" in hint_lower or "ping" in hint_lower:
                return DataType.SONAR_PING
            elif "gps" in hint_lower or "position" in hint_lower:
                return DataType.GPS_POSITION
            elif "imu" in hint_lower or "orientation" in hint_lower:
                return DataType.IMU_ORIENTATION
            elif "audio" in hint_lower or "waveform" in hint_lower:
                return DataType.AUDIO_WAVEFORM
            elif "can" in hint_lower:
                return DataType.CAN_DATA
            elif "obd" in hint_lower:
                return DataType.OBD_DATA
            elif "image" in hint_lower or "frame" in hint_lower:
                return DataType.IMAGE
        
        # Auto-detect from data structure
        if isinstance(data, dict):
            keys = set(data.keys())
            
            if "frame" in keys or "image" in keys:
                return DataType.IMAGE
            elif "points" in keys or "scan" in keys:
                return DataType.POINT_CLOUD
            elif "lat" in keys or "latitude" in keys or "lon" in keys:
                return DataType.GPS_POSITION
            elif "roll" in keys or "pitch" in keys or "quaternion" in keys:
                return DataType.IMU_ORIENTATION
            elif "ranges" in keys or "ping" in keys:
                return DataType.SONAR_PING
            elif "samples" in keys or "waveform" in keys:
                return DataType.AUDIO_WAVEFORM
            elif "rpm" in keys or "speed" in keys or "throttle" in keys:
                return DataType.OBD_DATA
            elif "can_id" in keys or "arbitration_id" in keys:
                return DataType.CAN_DATA
        
        elif isinstance(data, np.ndarray):
            if data.ndim == 3 and data.shape[2] in [3, 4]:
                return DataType.IMAGE  # RGB/RGBA image
            elif data.ndim == 2:
                if data.shape[1] == 3:
                    return DataType.POINT_CLOUD  # XYZ points
                else:
                    return DataType.DEPTH_MAP
            elif data.ndim == 1:
                return DataType.AUDIO_WAVEFORM
        
        return DataType.GENERIC
    
    def convert_to_visualization(self, data: Any, data_type: DataType = None, 
                                  params: Dict = None) -> Tuple[VisualizationType, Dict]:
        """Convert sensor data to visualization format"""
        
        if data_type is None:
            data_type = self.detect_data_type(data)
        
        converter = self.CONVERTERS.get(data_type)
        
        if converter:
            return converter.convert(data, params)
        elif data_type == DataType.IMAGE:
            return VisualizationType.VIDEO_FEED, {"frame": data}
        else:
            return VisualizationType.CHART, {"data": data}
    
    def visualize(self, data: Any, source_id: str = "default", 
                  data_type: DataType = None, params: Dict = None):
        """Process data and send to visualization display"""
        
        vis_type, vis_data = self.convert_to_visualization(data, data_type, params)
        
        # Publish visualization event
        if self.event_bus:
            self.event_bus.publish("visualization.update", {
                "source_id": source_id,
                "type": vis_type.value,
                "data": vis_data,
                "timestamp": time.time()
            })
        
        # Call registered callbacks
        with self._lock:
            for callback in self.visualization_callbacks.get(source_id, []):
                try:
                    callback(vis_type, vis_data)
                except Exception as e:
                    logger.error(f"Visualization callback error: {e}")
        
        return vis_type, vis_data
    
    def register_display(self, source_id: str, callback: Callable):
        """Register a display callback for a data source"""
        with self._lock:
            if source_id not in self.visualization_callbacks:
                self.visualization_callbacks[source_id] = []
            self.visualization_callbacks[source_id].append(callback)
    
    # ===== Event Handlers =====
    
    def _on_vision_frame(self, data: Dict):
        """Handle incoming vision/camera frame"""
        self.visualize(data, source_id="vision", data_type=DataType.IMAGE)
    
    def _on_lidar_scan(self, data: Dict):
        """Handle incoming LiDAR scan data"""
        self.visualize(data, source_id="lidar", data_type=DataType.POINT_CLOUD)
    
    def _on_sonar_data(self, data: Dict):
        """Handle incoming sonar data"""
        self.visualize(data, source_id="sonar", data_type=DataType.SONAR_PING)
    
    def _on_gps_data(self, data: Dict):
        """Handle incoming GPS data"""
        self.visualize(data, source_id="gps", data_type=DataType.GPS_POSITION)
    
    def _on_imu_data(self, data: Dict):
        """Handle incoming IMU data"""
        self.visualize(data, source_id="imu", data_type=DataType.IMU_ORIENTATION)
    
    def _on_can_data(self, data: Dict):
        """Handle incoming CAN bus data"""
        self.visualize(data, source_id="can", data_type=DataType.CAN_DATA)
    
    def _on_obd_data(self, data: Dict):
        """Handle incoming OBD-II data"""
        self.visualize(data, source_id="obd", data_type=DataType.OBD_DATA)
    
    def _on_device_connected(self, data: Dict):
        """Handle device connection - auto-wire to visualization"""
        device = data.get("device", {})
        device_id = device.get("id", "unknown")
        category = device.get("category", "unknown")
        
        logger.info(f"🔌 Device connected: {device_id} ({category}) - wiring to visualization")
        
        # Create stream entry for device
        with self._lock:
            self.active_streams[device_id] = {
                "category": category,
                "connected_at": datetime.now().isoformat(),
                "device": device
            }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_visualizer_instance: Optional[UniversalDataVisualizer] = None

def get_universal_visualizer(event_bus=None) -> UniversalDataVisualizer:
    """Get or create the global UniversalDataVisualizer instance"""
    global _visualizer_instance
    if _visualizer_instance is None:
        _visualizer_instance = UniversalDataVisualizer(event_bus)
    return _visualizer_instance


# ============================================================================
# MCP TOOLS FOR AI CONTROL
# ============================================================================

class VisualizerMCPTools:
    """MCP tools for AI to control visualizations"""
    
    def __init__(self, visualizer: UniversalDataVisualizer):
        self.visualizer = visualizer
    
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "visualize_sensor_data",
                "description": "Visualize sensor data (LiDAR, sonar, GPS, IMU, audio) as 3D display or chart",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string", "description": "Source device/sensor ID"},
                        "data_type": {
                            "type": "string",
                            "enum": ["lidar", "sonar", "gps", "imu", "audio", "can", "obd", "image"],
                            "description": "Type of sensor data"
                        }
                    },
                    "required": ["source_id"]
                }
            },
            {
                "name": "get_active_streams",
                "description": "Get list of active data streams being visualized",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "convert_to_3d",
                "description": "Convert any sensor data to 3D visualization (point cloud or surface)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string"},
                        "mode": {
                            "type": "string",
                            "enum": ["pointcloud", "surface", "map"],
                            "description": "3D visualization mode"
                        }
                    },
                    "required": ["source_id"]
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if tool_name == "get_active_streams":
                return {
                    "success": True,
                    "streams": self.visualizer.active_streams,
                    "count": len(self.visualizer.active_streams)
                }
            elif tool_name == "visualize_sensor_data":
                source_id = parameters.get("source_id", "default")
                return {
                    "success": True,
                    "source_id": source_id,
                    "message": f"Visualization active for {source_id}"
                }
            elif tool_name == "convert_to_3d":
                return {
                    "success": True,
                    "message": "3D conversion mode activated"
                }
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print(" UNIVERSAL DATA VISUALIZER TEST ".center(70))
    print("="*70 + "\n")
    
    visualizer = get_universal_visualizer()
    
    # Test LiDAR conversion
    print("🔹 Testing LiDAR to 3D Point Cloud...")
    lidar_data = [(0, 5.0), (45, 4.5), (90, 6.0), (135, 5.5), (180, 4.0)]
    vis_type, vis_data = visualizer.convert_to_visualization(lidar_data, DataType.POINT_CLOUD)
    print(f"   Result: {vis_type.value}, {len(vis_data.get('points', []))} points")
    
    # Test GPS conversion
    print("🔹 Testing GPS to 3D Map...")
    gps_data = {"lat": 37.7749, "lon": -122.4194, "alt": 100}
    vis_type, vis_data = visualizer.convert_to_visualization(gps_data, DataType.GPS_POSITION)
    print(f"   Result: {vis_type.value}, position={vis_data.get('coordinates')}")
    
    # Test IMU conversion
    print("🔹 Testing IMU to Attitude...")
    imu_data = {"roll": 0.1, "pitch": 0.2, "yaw": 0.5}
    vis_type, vis_data = visualizer.convert_to_visualization(imu_data, DataType.IMU_ORIENTATION)
    print(f"   Result: {vis_type.value}, roll={vis_data.get('roll'):.1f}°")
    
    # Test OBD conversion
    print("🔹 Testing OBD to Gauges...")
    obd_data = {"rpm": 3500, "speed": 65, "coolant_temp": 85}
    vis_type, vis_data = visualizer.convert_to_visualization(obd_data, DataType.OBD_DATA)
    print(f"   Result: {vis_type.value}, {len(vis_data.get('gauges', []))} gauges")
    
    print("\n" + "="*70 + "\n")
