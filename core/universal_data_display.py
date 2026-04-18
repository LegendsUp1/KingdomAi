"""
Universal Data Display Orchestrator - SOTA 2026
================================================
Master orchestrator that wires ALL Kingdom AI data sources to visualization.

Connects:
- All sensor data (LiDAR, sonar, GPS, IMU, cameras)
- Trading/market data (prices, predictions, charts)
- Blockchain data (transactions, wallets, contracts)
- Mining data (hashrate, pools, earnings)
- AI/ML predictions and analytics
- Signal analyzer data (RF, Bluetooth, WiFi)
- Any user-requested data from any system component

Outputs to:
- Vision stream (2D display)
- VR environment (3D immersive)
- Charts, gauges, 3D models, animations
- Real-time updates on user request

IMPORTANT: This file ONLY wires existing components - no new functionality.
"""

import logging
import threading
import asyncio
import time
import json
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger("KingdomAI.UniversalDataDisplay")

# ============================================================================
# DATA SOURCE REGISTRY - All Kingdom AI data sources
# ============================================================================

class DataSourceCategory(Enum):
    """Categories of data sources in Kingdom AI"""
    # Sensors & Hardware
    VISION = "vision"                # Cameras, microscopes, telescopes
    LIDAR = "lidar"                  # LiDAR sensors
    SONAR = "sonar"                  # Sonar/ultrasonic
    GPS = "gps"                      # GPS/GNSS
    IMU = "imu"                      # Inertial measurement
    THERMAL = "thermal"              # Thermal cameras
    SIGNAL = "signal"                # RF/Bluetooth/WiFi signals
    
    # Trading & Finance
    TRADING = "trading"              # Live market data
    PREDICTIONS = "predictions"      # AI predictions
    PORTFOLIO = "portfolio"          # Portfolio data
    ORDERS = "orders"                # Order book, trades
    
    # Blockchain
    BLOCKCHAIN = "blockchain"        # Chain data
    WALLET = "wallet"                # Wallet balances
    TRANSACTIONS = "transactions"    # TX history
    CONTRACTS = "contracts"          # Smart contracts
    
    # Mining
    MINING = "mining"                # Mining stats
    HASHRATE = "hashrate"            # Hashrate data
    POOLS = "pools"                  # Pool stats
    
    # AI/Analytics
    ANALYTICS = "analytics"          # Analytics data
    AI_RESPONSE = "ai_response"      # AI chat responses
    SENTIENCE = "sentience"          # Sentience metrics
    
    # System
    DEVICES = "devices"              # Connected devices
    SYSTEM = "system"                # System metrics
    CUSTOM = "custom"                # User-defined


class DisplayMode(Enum):
    """Display output modes"""
    VISION_2D = "vision_2d"          # 2D video/image display
    VR_3D = "vr_3d"                  # VR immersive 3D
    CHART = "chart"                  # Line/bar charts
    GAUGE = "gauge"                  # Circular gauges
    TABLE = "table"                  # Data table
    MAP = "map"                      # Geographic map
    POINT_CLOUD = "point_cloud"      # 3D point cloud
    SURFACE_3D = "surface_3d"        # 3D surface
    ANIMATION = "animation"          # Animated visualization
    TEXT = "text"                    # Text/numbers
    MIXED = "mixed"                  # Multiple modes


@dataclass
class DataDisplayRequest:
    """Request for data display"""
    source: str                      # Data source identifier
    category: DataSourceCategory     # Category
    display_mode: DisplayMode        # How to display
    query: Optional[str] = None      # Optional query/filter
    realtime: bool = True            # Real-time updates
    vr_enabled: bool = False         # Show in VR
    animation: bool = False          # Animate the data
    history_depth: int = 0           # How much history to show


@dataclass
class DataDisplayResponse:
    """Response with visualization data"""
    source: str
    category: str
    display_mode: str
    data: Any
    visualization: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    vr_scene: Optional[Dict] = None
    animation_frames: Optional[List] = None


# ============================================================================
# UNIVERSAL DATA DISPLAY ORCHESTRATOR
# ============================================================================

class UniversalDataDisplayOrchestrator:
    """
    SOTA 2026: Master orchestrator for ALL Kingdom AI data display.
    
    Wires every data source to visualization outputs (vision stream, VR).
    Handles user requests for data in any format.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._lock = threading.Lock()
        
        # Data source registrations
        self._data_sources: Dict[str, Dict[str, Any]] = {}
        self._active_displays: Dict[str, DataDisplayRequest] = {}
        self._display_callbacks: Dict[str, List[Callable]] = {}
        
        # Connected subsystems (lazy-loaded)
        self._visualizer = None
        self._vr_system = None
        self._vision_stream = None
        self._signal_analyzer = None
        self._trading_system = None
        self._blockchain = None
        self._mining = None
        
        # Initialize connections
        self._init_subsystems()
        self._subscribe_to_all_events()
        
        logger.info("🎯 UniversalDataDisplayOrchestrator initialized")
        logger.info("   📊 Ready to display ANY data in ANY format")
    
    def _init_subsystems(self):
        """Initialize connections to all Kingdom AI subsystems"""
        
        # Universal Data Visualizer
        try:
            from core.universal_data_visualizer import get_universal_visualizer
            self._visualizer = get_universal_visualizer(self.event_bus)
            logger.info("   ✅ UniversalDataVisualizer connected")
        except ImportError as e:
            logger.warning(f"   ⚠️ UniversalDataVisualizer not available: {e}")
        
        # VR System
        try:
            from core.vr_integration import VRSystem
            self._vr_system = VRSystem(simulation_mode=True)
            logger.info("   ✅ VR System connected")
        except ImportError as e:
            logger.warning(f"   ⚠️ VR System not available: {e}")
        
        # Vision Stream
        try:
            from components.vision_stream import VisionStreamComponent
            # Will be set externally or via event
            logger.info("   ✅ Vision Stream available")
        except ImportError as e:
            logger.warning(f"   ⚠️ Vision Stream not available: {e}")
        
        # Signal Analyzer
        try:
            from core.signal_analyzer import get_signal_analyzer
            self._signal_analyzer = get_signal_analyzer(self.event_bus)
            logger.info("   ✅ Signal Analyzer connected")
        except ImportError as e:
            logger.debug(f"   Signal Analyzer not loaded: {e}")
        
        # Register all data source categories
        self._register_data_sources()
    
    def _register_data_sources(self):
        """Register all available data sources"""
        
        # Sensor sources
        self._data_sources["vision"] = {
            "category": DataSourceCategory.VISION,
            "events": ["vision.stream.frame", "vision.capture"],
            "display_modes": [DisplayMode.VISION_2D, DisplayMode.VR_3D]
        }
        self._data_sources["lidar"] = {
            "category": DataSourceCategory.LIDAR,
            "events": ["lidar.scan", "lidar.pointcloud"],
            "display_modes": [DisplayMode.POINT_CLOUD, DisplayMode.VR_3D]
        }
        self._data_sources["sonar"] = {
            "category": DataSourceCategory.SONAR,
            "events": ["sonar.ping", "sonar.scan"],
            "display_modes": [DisplayMode.SURFACE_3D, DisplayMode.VR_3D]
        }
        self._data_sources["gps"] = {
            "category": DataSourceCategory.GPS,
            "events": ["gps.position", "gps.track"],
            "display_modes": [DisplayMode.MAP, DisplayMode.VR_3D]
        }
        self._data_sources["imu"] = {
            "category": DataSourceCategory.IMU,
            "events": ["imu.orientation", "imu.attitude"],
            "display_modes": [DisplayMode.GAUGE, DisplayMode.VR_3D]
        }
        self._data_sources["thermal"] = {
            "category": DataSourceCategory.THERMAL,
            "events": ["thermal.frame", "thermal.data"],
            "display_modes": [DisplayMode.VISION_2D, DisplayMode.VR_3D]
        }
        self._data_sources["signals"] = {
            "category": DataSourceCategory.SIGNAL,
            "events": ["signals.scan.complete", "signals.device.discovered"],
            "display_modes": [DisplayMode.TABLE, DisplayMode.CHART, DisplayMode.VR_3D]
        }
        
        # Trading sources
        self._data_sources["trading"] = {
            "category": DataSourceCategory.TRADING,
            "events": ["trading.price.update", "trading.orderbook", "market.data"],
            "display_modes": [DisplayMode.CHART, DisplayMode.TABLE, DisplayMode.VR_3D]
        }
        self._data_sources["predictions"] = {
            "category": DataSourceCategory.PREDICTIONS,
            "events": ["trading.prediction", "ai.prediction"],
            "display_modes": [DisplayMode.CHART, DisplayMode.VR_3D, DisplayMode.ANIMATION]
        }
        self._data_sources["portfolio"] = {
            "category": DataSourceCategory.PORTFOLIO,
            "events": ["portfolio.update", "portfolio.balance"],
            "display_modes": [DisplayMode.CHART, DisplayMode.TABLE, DisplayMode.GAUGE]
        }
        
        # Blockchain sources
        self._data_sources["blockchain"] = {
            "category": DataSourceCategory.BLOCKCHAIN,
            "events": ["blockchain.block", "blockchain.status"],
            "display_modes": [DisplayMode.TABLE, DisplayMode.VR_3D]
        }
        self._data_sources["wallet"] = {
            "category": DataSourceCategory.WALLET,
            "events": ["wallet.balance", "wallet.update"],
            "display_modes": [DisplayMode.TABLE, DisplayMode.GAUGE]
        }
        self._data_sources["transactions"] = {
            "category": DataSourceCategory.TRANSACTIONS,
            "events": ["transaction.new", "transaction.confirmed"],
            "display_modes": [DisplayMode.TABLE, DisplayMode.ANIMATION]
        }
        
        # Mining sources
        self._data_sources["mining"] = {
            "category": DataSourceCategory.MINING,
            "events": ["mining.stats", "mining.hashrate"],
            "display_modes": [DisplayMode.CHART, DisplayMode.GAUGE, DisplayMode.VR_3D]
        }
        
        # AI/Analytics sources
        self._data_sources["analytics"] = {
            "category": DataSourceCategory.ANALYTICS,
            "events": ["analytics.result", "analytics.update"],
            "display_modes": [DisplayMode.CHART, DisplayMode.TABLE, DisplayMode.VR_3D]
        }
        self._data_sources["ai"] = {
            "category": DataSourceCategory.AI_RESPONSE,
            "events": ["ai.response", "thoth.response"],
            "display_modes": [DisplayMode.TEXT, DisplayMode.ANIMATION]
        }
        
        # Device sources
        self._data_sources["devices"] = {
            "category": DataSourceCategory.DEVICES,
            "events": ["device.connected", "device.disconnected", "device.data"],
            "display_modes": [DisplayMode.TABLE, DisplayMode.VR_3D]
        }
        
        logger.info(f"   📋 Registered {len(self._data_sources)} data sources")
    
    def _subscribe_to_all_events(self):
        """Subscribe to ALL relevant events from all systems"""
        if not self.event_bus:
            return
        
        try:
            subscribe = getattr(self.event_bus, "subscribe_sync", None) or getattr(self.event_bus, "subscribe", None)
            if not callable(subscribe):
                return
            
            # Subscribe to all registered data source events
            for source_id, source_info in self._data_sources.items():
                for event_topic in source_info.get("events", []):
                    try:
                        subscribe(event_topic, lambda data, src=source_id, topic=event_topic: 
                                  self._on_data_event(src, topic, data))
                    except Exception as e:
                        logger.debug(f"Could not subscribe to {event_topic}: {e}")
            
            # Subscribe to visualization requests
            subscribe("display.request", self._on_display_request)
            subscribe("display.show", self._on_display_request)
            subscribe("data.visualize", self._on_display_request)
            
            # Subscribe to VR events
            subscribe("vr.display.request", self._on_vr_display_request)
            
            logger.info("   📡 Subscribed to all data events")
            
        except Exception as e:
            logger.error(f"Event subscription error: {e}")
    
    def _on_data_event(self, source_id: str, topic: str, data: Dict[str, Any]):
        """Handle incoming data from any source"""
        
        # Check if this source has active displays
        if source_id in self._active_displays:
            request = self._active_displays[source_id]
            self._route_to_display(source_id, data, request)
        
        # Store latest data
        with self._lock:
            if source_id not in self._data_sources:
                self._data_sources[source_id] = {}
            self._data_sources[source_id]["latest_data"] = data
            self._data_sources[source_id]["last_update"] = datetime.now().isoformat()
    
    def _on_display_request(self, data: Dict[str, Any]):
        """Handle user request to display data"""
        source = data.get("source", data.get("data_source", ""))
        mode = data.get("mode", data.get("display_mode", "auto"))
        vr = data.get("vr", data.get("vr_enabled", False))
        query = data.get("query", "")
        
        self.display_data(source, display_mode=mode, vr_enabled=vr, query=query)
    
    def _on_vr_display_request(self, data: Dict[str, Any]):
        """Handle VR-specific display request"""
        data["vr_enabled"] = True
        self._on_display_request(data)
    
    def _route_to_display(self, source_id: str, data: Any, request: DataDisplayRequest):
        """Route data to appropriate display output"""
        
        # Convert data to visualization format
        vis_data = self._convert_for_display(data, request)
        
        # Send to vision stream (2D)
        if request.display_mode in [DisplayMode.VISION_2D, DisplayMode.CHART, 
                                     DisplayMode.GAUGE, DisplayMode.TABLE]:
            self._send_to_vision(source_id, vis_data)
        
        # Send to VR (3D)
        if request.vr_enabled or request.display_mode in [DisplayMode.VR_3D, 
                                                           DisplayMode.POINT_CLOUD,
                                                           DisplayMode.SURFACE_3D]:
            self._send_to_vr(source_id, vis_data)
        
        # Publish visualization event
        if self.event_bus:
            self.event_bus.publish("visualization.update", {
                "source": source_id,
                "mode": request.display_mode.value,
                "data": vis_data,
                "timestamp": time.time()
            })
    
    def _convert_for_display(self, data: Any, request: DataDisplayRequest) -> Dict[str, Any]:
        """Convert raw data to display format"""
        
        # Use UniversalDataVisualizer if available
        if self._visualizer:
            try:
                # Map category to data type
                from core.universal_data_visualizer import DataType
                type_map = {
                    DataSourceCategory.VISION: DataType.IMAGE,
                    DataSourceCategory.LIDAR: DataType.POINT_CLOUD,
                    DataSourceCategory.SONAR: DataType.SONAR_PING,
                    DataSourceCategory.GPS: DataType.GPS_POSITION,
                    DataSourceCategory.IMU: DataType.IMU_ORIENTATION,
                    DataSourceCategory.THERMAL: DataType.THERMAL,
                }
                data_type = type_map.get(request.category)
                if data_type:
                    vis_type, vis_data = self._visualizer.convert_to_visualization(data, data_type)
                    return {"type": vis_type.value, "visualization": vis_data, "raw": data}
            except Exception as e:
                logger.debug(f"Visualizer conversion error: {e}")
        
        # Default conversion
        return {"type": "raw", "data": data, "display_mode": request.display_mode.value}
    
    def _send_to_vision(self, source_id: str, vis_data: Dict):
        """Send visualization to vision stream"""
        if self.event_bus:
            self.event_bus.publish("vision.display.update", {
                "source": source_id,
                "data": vis_data,
                "timestamp": time.time()
            })
    
    def _send_to_vr(self, source_id: str, vis_data: Dict):
        """Send visualization to VR environment"""
        if self._vr_system:
            # Create VR scene object
            vr_scene = {
                "source": source_id,
                "objects": [],
                "data": vis_data
            }
            
            # Convert to VR objects based on data type
            if vis_data.get("type") == "point_cloud_3d":
                vr_scene["objects"].append({
                    "type": "pointcloud",
                    "points": vis_data.get("visualization", {}).get("points", []),
                    "colors": vis_data.get("visualization", {}).get("colors", [])
                })
            elif vis_data.get("type") == "surface_3d":
                vr_scene["objects"].append({
                    "type": "mesh",
                    "vertices": vis_data.get("visualization", {}).get("vertices", []),
                    "faces": vis_data.get("visualization", {}).get("faces", [])
                })
            
            if self.event_bus:
                self.event_bus.publish("vr.scene.update", vr_scene)
    
    # =========================================================================
    # PUBLIC API - User-facing methods
    # =========================================================================
    
    def display_data(self, source: str, display_mode: str = "auto", 
                     vr_enabled: bool = False, query: str = None,
                     animation: bool = False) -> DataDisplayResponse:
        """
        Display data from any source in requested format.
        
        Args:
            source: Data source name (e.g., "trading", "vision", "signals")
            display_mode: How to display ("auto", "chart", "3d", "vr", "table")
            vr_enabled: Show in VR environment
            query: Optional filter/query
            animation: Animate the visualization
            
        Returns:
            DataDisplayResponse with visualization data
        """
        logger.info(f"📊 Display request: {source} -> {display_mode}")
        
        # Resolve source
        source_info = self._data_sources.get(source, {})
        category = source_info.get("category", DataSourceCategory.CUSTOM)
        
        # Determine display mode
        if display_mode == "auto":
            available_modes = source_info.get("display_modes", [DisplayMode.TABLE])
            mode = available_modes[0] if available_modes else DisplayMode.TABLE
        else:
            mode_map = {
                "chart": DisplayMode.CHART,
                "3d": DisplayMode.VR_3D,
                "vr": DisplayMode.VR_3D,
                "table": DisplayMode.TABLE,
                "gauge": DisplayMode.GAUGE,
                "map": DisplayMode.MAP,
                "pointcloud": DisplayMode.POINT_CLOUD,
                "surface": DisplayMode.SURFACE_3D,
                "video": DisplayMode.VISION_2D,
                "animation": DisplayMode.ANIMATION,
                "text": DisplayMode.TEXT,
            }
            mode = mode_map.get(display_mode.lower(), DisplayMode.TABLE)
        
        if vr_enabled:
            mode = DisplayMode.VR_3D
        
        # Create request
        request = DataDisplayRequest(
            source=source,
            category=category,
            display_mode=mode,
            query=query,
            realtime=True,
            vr_enabled=vr_enabled,
            animation=animation
        )
        
        # Register active display
        with self._lock:
            self._active_displays[source] = request
        
        # Get current data
        current_data = self._get_source_data(source, query)
        
        # Route to display
        if current_data:
            self._route_to_display(source, current_data, request)
        
        # Build response
        vis_data = self._convert_for_display(current_data, request) if current_data else {}
        
        return DataDisplayResponse(
            source=source,
            category=category.value if hasattr(category, 'value') else str(category),
            display_mode=mode.value,
            data=current_data,
            visualization=vis_data,
            vr_scene={"enabled": vr_enabled} if vr_enabled else None
        )
    
    def _get_source_data(self, source: str, query: str = None) -> Any:
        """Get current data from a source"""
        
        source_info = self._data_sources.get(source, {})
        
        # Return cached latest data
        if "latest_data" in source_info:
            return source_info["latest_data"]
        
        # Try to fetch from subsystems
        if source == "signals" and self._signal_analyzer:
            return {"signals": [s.to_dict() for s in self._signal_analyzer.get_all_signals()]}
        
        if source == "devices":
            try:
                from core.host_device_manager import get_host_device_manager
                manager = get_host_device_manager(self.event_bus)
                return manager.get_summary()
            except:
                pass
        
        return None
    
    def get_available_sources(self) -> List[Dict[str, Any]]:
        """Get list of all available data sources"""
        sources = []
        for source_id, info in self._data_sources.items():
            sources.append({
                "id": source_id,
                "category": info.get("category", DataSourceCategory.CUSTOM).value,
                "display_modes": [m.value for m in info.get("display_modes", [])],
                "has_data": "latest_data" in info
            })
        return sources
    
    def stop_display(self, source: str):
        """Stop displaying data from a source"""
        with self._lock:
            if source in self._active_displays:
                del self._active_displays[source]
        logger.info(f"🛑 Stopped display for: {source}")


# ============================================================================
# SINGLETON AND GETTERS
# ============================================================================

_display_orchestrator: Optional[UniversalDataDisplayOrchestrator] = None

def get_data_display_orchestrator(event_bus=None) -> UniversalDataDisplayOrchestrator:
    """Get or create the global UniversalDataDisplayOrchestrator"""
    global _display_orchestrator
    if _display_orchestrator is None:
        _display_orchestrator = UniversalDataDisplayOrchestrator(event_bus)
    return _display_orchestrator


# ============================================================================
# MCP TOOLS FOR AI CHAT CONTROL
# ============================================================================

class DataDisplayMCPTools:
    """MCP tools for AI to control data display via chat"""
    
    def __init__(self, orchestrator: UniversalDataDisplayOrchestrator):
        self.orchestrator = orchestrator
    
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "show_data",
                "description": "Display any data from Kingdom AI systems (trading, signals, devices, blockchain, mining, etc.) in any format (chart, 3D, VR, table)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Data source: vision, lidar, sonar, gps, signals, trading, predictions, portfolio, blockchain, wallet, mining, analytics, devices"
                        },
                        "display_mode": {
                            "type": "string",
                            "enum": ["auto", "chart", "3d", "vr", "table", "gauge", "map", "video", "animation"],
                            "description": "How to display the data"
                        },
                        "vr_enabled": {
                            "type": "boolean",
                            "description": "Show in VR environment"
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional filter query"
                        }
                    },
                    "required": ["source"]
                }
            },
            {
                "name": "list_data_sources",
                "description": "List all available data sources that can be displayed",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "show_in_vr",
                "description": "Display data in VR environment (3D immersive)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Data source to display in VR"},
                        "scene_type": {
                            "type": "string",
                            "enum": ["pointcloud", "surface", "chart3d", "map3d", "custom"],
                            "description": "Type of VR scene"
                        }
                    },
                    "required": ["source"]
                }
            },
            {
                "name": "show_on_vision",
                "description": "Display data on the vision stream (2D display)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "overlay": {"type": "boolean", "description": "Overlay on existing video"}
                    },
                    "required": ["source"]
                }
            },
            {
                "name": "stop_display",
                "description": "Stop displaying data from a source",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"}
                    },
                    "required": ["source"]
                }
            },
            {
                "name": "convert_to_3d",
                "description": "Convert any data to 3D visualization (point cloud, surface, or map)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "mode": {
                            "type": "string",
                            "enum": ["pointcloud", "surface", "map"],
                            "description": "3D conversion mode"
                        }
                    },
                    "required": ["source"]
                }
            },
            {
                "name": "animate_data",
                "description": "Create animated visualization of data over time",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "duration": {"type": "number", "description": "Animation duration in seconds"}
                    },
                    "required": ["source"]
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if tool_name == "show_data":
                source = parameters.get("source", "")
                mode = parameters.get("display_mode", "auto")
                vr = parameters.get("vr_enabled", False)
                query = parameters.get("query")
                
                response = self.orchestrator.display_data(source, mode, vr, query)
                return {
                    "success": True,
                    "source": response.source,
                    "display_mode": response.display_mode,
                    "has_data": response.data is not None,
                    "vr_enabled": vr
                }
            
            elif tool_name == "list_data_sources":
                sources = self.orchestrator.get_available_sources()
                return {"success": True, "sources": sources, "count": len(sources)}
            
            elif tool_name == "show_in_vr":
                source = parameters.get("source", "")
                response = self.orchestrator.display_data(source, "vr", vr_enabled=True)
                return {
                    "success": True,
                    "source": source,
                    "vr_scene": "created",
                    "display_mode": "vr_3d"
                }
            
            elif tool_name == "show_on_vision":
                source = parameters.get("source", "")
                response = self.orchestrator.display_data(source, "video")
                return {
                    "success": True,
                    "source": source,
                    "display_mode": "vision_2d"
                }
            
            elif tool_name == "stop_display":
                source = parameters.get("source", "")
                self.orchestrator.stop_display(source)
                return {"success": True, "source": source, "status": "stopped"}
            
            elif tool_name == "convert_to_3d":
                source = parameters.get("source", "")
                mode = parameters.get("mode", "pointcloud")
                response = self.orchestrator.display_data(source, mode)
                return {
                    "success": True,
                    "source": source,
                    "3d_mode": mode
                }
            
            elif tool_name == "animate_data":
                source = parameters.get("source", "")
                response = self.orchestrator.display_data(source, "animation", animation=True)
                return {
                    "success": True,
                    "source": source,
                    "animation": "started"
                }
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"DataDisplay tool error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print(" UNIVERSAL DATA DISPLAY ORCHESTRATOR TEST ".center(70))
    print("="*70 + "\n")
    
    orchestrator = get_data_display_orchestrator()
    
    print("📋 Available Data Sources:")
    for source in orchestrator.get_available_sources():
        print(f"   • {source['id']} ({source['category']})")
        print(f"     Modes: {', '.join(source['display_modes'][:3])}")
    
    print("\n🎯 Test Display Request:")
    response = orchestrator.display_data("signals", display_mode="table")
    print(f"   Source: {response.source}")
    print(f"   Mode: {response.display_mode}")
    print(f"   Has Data: {response.data is not None}")
    
    print("\n" + "="*70 + "\n")
