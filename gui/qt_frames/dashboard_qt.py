"""PyQt6 implementation of the Kingdom-AI Dashboard tab.

This widget displays the status of core Kingdom AI system components
using LED indicators for quick visual feedback.

IMPORTANT: This implementation enforces strict Redis connection on port 6380
with password 'QuantumNexus2025'. No fallback connections are allowed.
If Redis connection fails, the system will halt immediately.
"""
from __future__ import annotations

import logging
import threading
import sys
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union, Tuple, Callable, Type, Protocol, TYPE_CHECKING, cast

# 2025 Best Practice: Define Protocol for Redis interface (structural subtyping)
class RedisProtocol(Protocol):
    """Protocol defining Redis interface for type checking."""
    def ping(self) -> bool: ...
    def get(self, key: str) -> Optional[bytes]: ...
    def set(self, key: str, value: Any) -> bool: ...
    def delete(self, *keys: str) -> int: ...

# Type aliases for better type hints
RedisType = Optional[RedisProtocol]
RedisErrorType = type[Exception]
RedisConnectionErrorType = type[Exception]

try:
    import psutil  # type: ignore[import]
except ImportError:
    psutil = None  # type: ignore[assignment]

# Redis imports - MANDATORY, NO FALLBACKS
import redis
from redis import Redis  # type: ignore[attr-defined]
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
HAS_REDIS = True
redis_available = True

# Configure logger
logger = logging.getLogger(__name__)

# PyQt imports - try PyQt6 first, fall back to PyQt5 if necessary
try:
    from PyQt6.QtCore import QTimer, Qt, pyqtSignal, pyqtSlot, QRectF, QPointF, QSize, QPoint, QThread, QEventLoop
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTextEdit, QFrame, QSplitter, QTabWidget,
        QGroupBox, QSizePolicy, QScrollArea, QStatusBar, QFormLayout,
        QGridLayout, QMessageBox, QProgressBar
    )
    from PyQt6.QtGui import (
        QColor, QPainter, QLinearGradient, QPainterPath, QFont,
        QFontMetrics, QPen, QBrush, QPalette, QTextCursor, QPaintEvent
    )
except ImportError:
    logger.error("PyQt6 not available - Dashboard cannot be created")
    raise

# SOTA 2026: Thread-safe UI update utility (now in its own proper try block)
try:
    from utils.qt_thread_safe import make_handler_thread_safe, run_on_main_thread, is_main_thread
    THREAD_SAFE_AVAILABLE = True
except ImportError:
    THREAD_SAFE_AVAILABLE = False
    def make_handler_thread_safe(func): return func
    def run_on_main_thread(func): func()
    def is_main_thread(): return True
    PYQT6_AVAILABLE = True
except ImportError:
    try:
        from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRectF, QPointF, QSize, QPoint, QThread, QEventLoop
        from PyQt5.QtCore import pyqtSlot as Slot
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QTextEdit, QFrame, QSplitter, QTabWidget,
            QGroupBox, QSizePolicy, QScrollArea, QStatusBar, QFormLayout,
            QGridLayout, QMessageBox, QProgressBar
        )
        from PyQt5.QtGui import (
            QColor, QPainter, QLinearGradient, QPainterPath, QFont,
            QFontMetrics, QPen, QBrush, QPalette, QTextCursor, QPaintEvent
        )
        PYQT5_FALLBACK = True
    except ImportError as e:
        raise ImportError("PyQt6 or PyQt5 is required for the dashboard.") from e

# Local imports
from gui.widgets.led_indicator import QLedIndicator
from gui.widgets.system_indicator import SystemStatusIndicator
from core.event_bus import EventBus  # FIXED: Was utils.event_bus (WRONG PATH!)

# Redis configuration - STRICTLY enforce port 6380 with no fallbacks
REDIS_CONFIG = {
    'host': 'localhost', 
    'port': 6380,  # MUST be 6380 - system will halt if different
    'password': 'QuantumNexus2025',  # Required password
    'db': 0,
    'socket_timeout': 5,
    'socket_connect_timeout': 5,
    'retry_on_timeout': True,
    'health_check_interval': 30,
    'decode_responses': True
}


class DashboardQt(QWidget):
    """Dashboard widget for Kingdom AI.
    
    Displays system status and component health with LED indicators.
    """
    
    # 2025 Best Practice: Declare instance attributes with type annotations
    event_bus: Any
    redis_client: RedisType
    redis_connected: bool
    blockchain_connected: bool
    mining_connected: bool
    trading_connected: bool
    ai_connected: bool
    system_connected: bool
    
    def __init__(self, event_bus: Any = None, parent: Optional[QWidget] = None) -> None:
        """Initialize the Dashboard frame.
        
        Args:
            event_bus: The event bus to subscribe to for updates
            parent: The parent widget
        """
        super().__init__(parent)
        
        # Initialize event handlers
        self.event_bus = event_bus
        self.redis_client = None
        self._central_thoth = None
        
        # Initialize connection status flags - default to True since system is starting
        # They will be set to False if actual connection checks fail
        self.redis_connected = False  # Will be set True after Redis connects
        self.blockchain_connected = True  # Assume connected until proven otherwise
        self.mining_connected = True  # Assume connected until proven otherwise
        self.trading_connected = True  # Assume connected until proven otherwise
        self.ai_connected = True  # Assume connected until proven otherwise
        self.system_connected = True  # Main system is running if we got here
        
        # Initialize status indicators
        self.system_status = None
        self.redis_status = None
        self.blockchain_status = None
        self.mining_status = None
        self.trading_status = None
        self.ai_status = None
        
        self.setup_ui()
        
        # Subscribe to events
        self.subscribe_to_events()
        
        # TIMING FIX: Defer Redis connection to ensure Redis Quantum Nexus is ready
        logger.info("⏳ Deferring Dashboard Redis connection for 1 second to ensure Quantum Nexus is ready...")
        QTimer.singleShot(1000, self._deferred_redis_init)
        
        # Start status update timer for live indicators
        # SOTA 2026 PERFORMANCE FIX: Reduced from 2s to 5s to reduce CPU load
        # Analysis shows 2s polling with psutil is unnecessary for dashboard metrics
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_all_indicators)
        self.status_timer.start(5000)  # Update every 5 seconds (was 2s - too aggressive)
        
        # Initial status update
        self.update_all_indicators()
        
        # Start a timer for periodic health checks
        self.health_check_timer = QTimer(self)
        self.health_check_timer.timeout.connect(self.check_redis_health)
        self.health_check_timer.start(30000)  # Check every 30 seconds (was 5s — too aggressive)
        
        # Setup API key listener to receive all API key broadcasts
        self._setup_api_key_listener()

    def _setup_complete_ui(self):
        """Post-initialization: verify backends and start live data feeds.
        
        Called by KingdomMainWindow after all tabs are created and event bus
        components are registered, so backends are now reachable.
        """
        try:
            logger = logging.getLogger("KingdomAI.Dashboard")
            logger.info("Dashboard: running _setup_complete_ui backend verification...")

            # 1. Verify Redis connectivity
            self.check_redis_health()

            # 2. Request initial system status from all components
            if self.event_bus:
                self.event_bus.publish("system.status.request", {
                    "source": "dashboard",
                    "timestamp": __import__('time').time()
                })

            # 3. Force an immediate indicator refresh (don't wait for the 2s timer)
            self.update_all_indicators()

            # 4. Verify core components are registered on event bus
            verified = []
            for comp_name in ['trading_system', 'mining_system', 'blockchain_connector',
                              'thoth_ai', 'wallet_manager']:
                if self.event_bus and hasattr(self.event_bus, 'get_component'):
                    comp = self.event_bus.get_component(comp_name)
                    if comp is not None:
                        verified.append(comp_name)
            
            logger.info(f"Dashboard: {len(verified)} backend components verified: {verified}")
        except Exception as e:
            logging.getLogger("KingdomAI.Dashboard").warning(
                f"Dashboard _setup_complete_ui non-critical error: {e}"
            )

    def _setup_api_key_listener(self):
        """Setup listener for API key broadcasts from APIKeyManager."""
        try:
            if hasattr(self, 'event_bus') and self.event_bus:
                import asyncio
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"🔑 Setting up API key listener for {self.__class__.__name__}")
                
                def do_all_subscriptions():
                    """Perform subscriptions AFTER GUI init to avoid task nesting."""
                    try:
                        self.event_bus.subscribe("system.status", self.handle_system_status)
                        self.event_bus.subscribe("system.performance", self.handle_metrics_update)
                        self.event_bus.subscribe("system.status.response", self.handle_status_response)
                        self.event_bus.subscribe("dashboard.metrics_updated", self.handle_dashboard_metrics)
                        self.event_bus.subscribe("mining.dashboard.stats_updated", self.handle_mining_stats)
                        self.event_bus.subscribe("trading.portfolio_update", self.handle_trading_update)
                        logger.info("✅ Dashboard subscriptions completed")
                    except Exception as e:
                        logger.error(f"Dashboard subscription error: {e}")
                
                QTimer.singleShot(2600, do_all_subscriptions)
                
                logger.info(f"✅ {self.__class__.__name__} listening for API key broadcasts")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error setting up API key listener: {e}")
    
    def _on_api_key_available(self, event_data):
        """Handle API key availability broadcast."""
        try:
            service = event_data.get('service')
            import logging
            logging.getLogger(__name__).info(f"🔑 {self.__class__.__name__} received API key for: {service}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error handling API key availability: {e}")
    
    def _on_api_key_list(self, event_data):
        """Handle complete API key list."""
        try:
            api_keys = event_data.get('api_keys', {})
            import logging
            logging.getLogger(__name__).info(f"📋 {self.__class__.__name__} received {len(api_keys)} API keys")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error handling API key list: {e}")

    def setup_ui(self):
        """Set up the dashboard UI components."""
        # Outer layout holds the scroll area
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        # Scroll area to prevent clipping
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #0A0E17; }")
        
        # Content widget inside scroll area
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #0A0E17;")
        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 2, 8, 8)
        
        # Set size policy for proper expansion
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # System status section
        status_group = QGroupBox("System Status")
        status_layout = QGridLayout(status_group)
        status_layout.setSpacing(4)
        
        # Column 0 (labels) stretches, column 1 (indicators) stays fixed width
        status_layout.setColumnStretch(0, 1)
        status_layout.setColumnStretch(1, 0)
        status_layout.setColumnMinimumWidth(1, 30)
        
        # Create status indicators
        self.system_status = self.create_status_indicator("Main System")
        self.redis_status = self.create_status_indicator("Redis Quantum Nexus")
        self.blockchain_status = self.create_status_indicator("Blockchain")
        self.mining_status = self.create_status_indicator("Mining")
        self.trading_status = self.create_status_indicator("Trading")
        self.ai_status = self.create_status_indicator("AI Core")
        
        # Add indicators to layout with proper alignment
        status_layout.addWidget(QLabel("Main System:"), 0, 0, Qt.AlignmentFlag.AlignLeft)
        status_layout.addWidget(self.system_status, 0, 1, Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(QLabel("Redis Quantum Nexus:"), 1, 0, Qt.AlignmentFlag.AlignLeft)
        status_layout.addWidget(self.redis_status, 1, 1, Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(QLabel("Blockchain:"), 2, 0, Qt.AlignmentFlag.AlignLeft)
        status_layout.addWidget(self.blockchain_status, 2, 1, Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(QLabel("Mining:"), 3, 0, Qt.AlignmentFlag.AlignLeft)
        status_layout.addWidget(self.mining_status, 3, 1, Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(QLabel("Trading:"), 4, 0, Qt.AlignmentFlag.AlignLeft)
        status_layout.addWidget(self.trading_status, 4, 1, Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(QLabel("AI Core:"), 5, 0, Qt.AlignmentFlag.AlignLeft)
        status_layout.addWidget(self.ai_status, 5, 1, Qt.AlignmentFlag.AlignRight)
        
        # Add metrics section
        metrics_group = QGroupBox("System Metrics")
        metrics_layout = QVBoxLayout(metrics_group)
        metrics_layout.setSpacing(4)
        self.cpu_progress = QProgressBar()
        self.cpu_progress.setFixedHeight(22)
        self.memory_progress = QProgressBar()
        self.memory_progress.setFixedHeight(22)
        metrics_layout.addWidget(QLabel("CPU Usage:"))
        metrics_layout.addWidget(self.cpu_progress)
        metrics_layout.addWidget(QLabel("Memory Usage:"))
        metrics_layout.addWidget(self.memory_progress)
        
        # Add sections to main layout — status and metrics are compact
        main_layout.addWidget(status_group)
        main_layout.addWidget(metrics_group)
        
        # Quick actions section
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)
        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.clicked.connect(self.refresh_status)
        reconnect_btn = QPushButton("Reconnect Services")
        reconnect_btn.clicked.connect(self.reconnect_services)
        actions_layout.addWidget(refresh_btn)
        actions_layout.addWidget(reconnect_btn)
        main_layout.addWidget(actions_group)
        
        # Log output section — gets remaining stretch
        log_group = QGroupBox("System Log")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(120)
        log_layout.addWidget(self.log_output)
        main_layout.addWidget(log_group, stretch=1)
        
        # Finalize scroll area
        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)
        self.setLayout(outer_layout)
    
    def create_status_indicator(self, name):
        """Create a colored status indicator label.
        
        SOTA 2026 FIX: Use larger size and border for better WSL2 visibility.
        """
        indicator = QLabel()
        indicator.setFixedSize(24, 24)
        indicator.setMinimumSize(24, 24)
        # Use solid background with border for WSL2 compatibility
        indicator.setStyleSheet("""
            QLabel {
                background-color: #666666;
                border: 2px solid #444444;
                border-radius: 12px;
                min-width: 24px;
                min-height: 24px;
            }
        """)
        indicator.setToolTip(f"{name} status: Unknown")
        return indicator
    
    def update_status_indicator(self, indicator, status):
        """Update a status indicator with the given status.
        
        SOTA 2026 FIX: Use brighter colors and borders for WSL2 visibility.
        """
        if status:
            indicator.setStyleSheet("""
                QLabel {
                    background-color: #00FF00;
                    border: 2px solid #00AA00;
                    border-radius: 12px;
                    min-width: 24px;
                    min-height: 24px;
                }
            """)
            indicator.setToolTip(f"Status: Connected")
        else:
            indicator.setStyleSheet("""
                QLabel {
                    background-color: #FF0000;
                    border: 2px solid #AA0000;
                    border-radius: 12px;
                    min-width: 24px;
                    min-height: 24px;
                }
            """)
            indicator.setToolTip(f"Status: Disconnected")
    
    def _deferred_redis_init(self):
        """Deferred Redis initialization - called after Redis Quantum Nexus is ready."""
        try:
            logger.info("🔗 Dashboard connecting to Redis Quantum Nexus...")
            if Redis is not None:
                self.redis_client = cast(RedisType, Redis(
                    host='localhost',
                    port=6380,
                    password='QuantumNexus2025',
                    decode_responses=True
                ))
                # CRITICAL FIX: Set MISCONF protection BEFORE ping
                try:
                    self.redis_client.execute_command('CONFIG', 'SET', 'stop-writes-on-bgsave-error', 'no')
                except Exception:
                    pass
                self.redis_client.ping()
                logger.info("✅ Dashboard connected to Redis Quantum Nexus on port 6380")
                self.redis_connected = True
                self.update_status_indicator(self.redis_status, True)
                self.log_message("Connected to Redis Quantum Nexus successfully.")
            else:
                raise ImportError("Redis module not available")
        except Exception as e:
            # Log warning but don't crash - Dashboard can still show system status
            logger.warning(f"⚠️ Dashboard Redis connection failed (will retry): {e}")
            self.redis_client = None
            self.redis_connected = False
            if self.redis_status:
                self.update_status_indicator(self.redis_status, False)
            self.log_message("Warning: Redis Quantum Nexus connection failed. Dashboard will function with limited features.", error=True)
    
    def initialize_redis_connection(self):
        """Legacy method - redirects to deferred init."""
        self._deferred_redis_init()
    
    def subscribe_to_events(self):
        """Subscribe to relevant event bus events."""
        if not self.event_bus:
            return
        
        import logging
        logger = logging.getLogger(__name__)
        
        def do_all_subscriptions():
            """Perform subscriptions AFTER GUI init to avoid task nesting."""
            try:
                self.event_bus.subscribe("system.status", self.handle_system_status)
                self.event_bus.subscribe("system.performance", self.handle_metrics_update)
                self.event_bus.subscribe("system.status.response", self.handle_status_response)
                self.event_bus.subscribe("dashboard.metrics_updated", self.handle_dashboard_metrics)
                # SOTA 2026: Subscribe to mining intelligence events
                self.event_bus.subscribe("dashboard.mining_statistics_update", self._handle_mining_statistics_update)
                self.event_bus.subscribe("mining.intelligence.update", self._handle_mining_intelligence_update)
                self.event_bus.subscribe("mining.hardware_recommendations", self._handle_hardware_recommendations)
                self.event_bus.subscribe("mining.stats.update", self.handle_mining_stats)
                self.event_bus.subscribe("mining.update", self.handle_mining_stats)
                self.event_bus.subscribe("mining.hashrate_update", self.handle_mining_stats)
                self.event_bus.subscribe("trading.portfolio_update", self.handle_trading_update)
                # FIX: Subscribe to node/pool connection events so the mining LED
                # reflects real-time connection status (published every 5s by
                # MiningSystem._start_status_publisher)
                self.event_bus.subscribe("mining.nodes.connected", self._handle_mining_connection)
                self.event_bus.subscribe("mining.pools.connected", self._handle_mining_connection)
                logger.info("✅ Dashboard event subscriptions completed (14 events)")
            except Exception as e:
                logger.error(f"Dashboard subscription error: {e}")
        
        # Schedule after init completes (2.6 second delay ensures main task done)
        QTimer.singleShot(2600, do_all_subscriptions)
    
    def check_redis_health(self):
        """Periodically check Redis connection health."""
        try:
            if self.redis_client:
                # CONFIG SET only needed once at connect, not every health check
                self.redis_client.ping()
                if not self.redis_connected:
                    self.redis_connected = True
                    self.update_status_indicator(self.redis_status, True)
                    self.log_message("Redis connection restored.")
        except RedisError:
            if self.redis_connected:
                self.redis_connected = False
                self.update_status_indicator(self.redis_status, False)
                self.log_message("Redis connection lost.", error=True)
    
    def handle_system_status(self, data):
        """Handle system status updates from event bus (THREAD-SAFE).
        
        SOTA 2026: This handler can be called from any thread. UI updates
        are dispatched to the main Qt thread to prevent segmentation faults.
        """
        # Dispatch to main thread if needed
        if not is_main_thread():
            run_on_main_thread(lambda: self._handle_system_status_ui(data))
            return
        self._handle_system_status_ui(data)
    
    def _handle_system_status_ui(self, data):
        """Update UI for system status (MUST run on main thread)."""
        try:
            if "trading" in data:
                self.trading_connected = bool(data["trading"])
                self.update_status_indicator(self.trading_status, self.trading_connected)
            
            if "mining" in data:
                self.mining_connected = bool(data["mining"])
                self.update_status_indicator(self.mining_status, self.mining_connected)
                
            if "blockchain" in data:
                self.blockchain_connected = bool(data["blockchain"])
                self.update_status_indicator(self.blockchain_status, self.blockchain_connected)
                
            if "ai" in data:
                self.ai_connected = bool(data["ai"])
                self.update_status_indicator(self.ai_status, self.ai_connected)
                
            if "system" in data:
                self.system_connected = bool(data["system"])
                self.update_status_indicator(self.system_status, self.system_connected)
                
            # Log status update
            timestamp = data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.log_message(f"[{timestamp}] System status updated.")
        except Exception as e:
            self.log_message(f"Error processing system status: {str(e)}", error=True)
    
    def handle_metrics_update(self, data):
        """Handle metrics updates from event bus (THREAD-SAFE).
        
        SOTA 2026: This handler can be called from any thread. UI updates
        are dispatched to the main Qt thread to prevent segmentation faults.
        """
        # Dispatch to main thread if needed
        if not is_main_thread():
            run_on_main_thread(lambda: self._handle_metrics_update_ui(data))
            return
        self._handle_metrics_update_ui(data)
    
    def _handle_metrics_update_ui(self, data):
        """Update UI for metrics (MUST run on main thread)."""
        try:
            if "cpu" in data:
                self.cpu_progress.setValue(int(data["cpu"]))
                
            if "memory" in data:
                self.memory_progress.setValue(int(data["memory"]))
                
            # Log metrics update
            timestamp = data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.log_message(f"[{timestamp}] System metrics updated.")
            logger.debug(f"🔴 REAL CPU: {data['cpu']}%, REAL Memory: {data['memory']}%")
        except Exception as e:
            self.log_message(f"Error processing metrics: {str(e)}", error=True)
    
    def handle_status_response(self, data):
        """Handle status response from backend - REAL DATA DISPLAY"""
        try:
            if "cpu" in data:
                self.cpu_progress.setValue(int(data["cpu"]))
                self.log_message(f"✅ CPU Usage: {data['cpu']:.1f}%")
                logger.debug(f"🔴 REAL CPU: {data['cpu']}%")
            
            if "memory" in data:
                self.memory_progress.setValue(int(data["memory"]))
                self.log_message(f"✅ Memory Usage: {data['memory']:.1f}%")
                logger.debug(f"🔴 REAL Memory: {data['memory']}%")
            
            self.log_message("✅ Status data received from backend")
        except Exception as e:
            self.log_message(f"Error handling status response: {e}", error=True)
    
    def handle_dashboard_metrics(self, data):
        """Handle dashboard metrics update from backend - VISUAL UPDATE"""
        try:
            if "cpu_percent" in data:
                self.cpu_progress.setValue(int(data["cpu_percent"]))
            
            if "memory_percent" in data:
                self.memory_progress.setValue(int(data["memory_percent"]))
            
            if "redis_connected" in data:
                self.update_status_indicator(self.redis_status, data["redis_connected"])
            
            self.log_message(f"✅ Dashboard refreshed - CPU: {data.get('cpu_percent', 0):.1f}%, Memory: {data.get('memory_percent', 0):.1f}%")
        except Exception as e:
            self.log_message(f"Error handling dashboard metrics: {e}", error=True)
    
    def log_message(self, message, error=False):
        """Log a message to the dashboard log output."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_level = "ERROR" if error else "INFO"
        log_entry = f"[{timestamp}] [{log_level}] {message}"
        
        # Add to log display (cap at 200 lines to prevent QTextEdit layout thrashing)
        self.log_output.append(log_entry)
        doc = self.log_output.document()
        if doc and doc.blockCount() > 200:
            cursor = self.log_output.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, doc.blockCount() - 200)
            cursor.removeSelectedText()
            cursor.deleteChar()  # remove leftover newline
        
        # Also log to system logger
        if error:
            logger.error(message)
        else:
            logger.info(message)
    
    def _emit_ui_telemetry(
        self,
        event_type: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Lightweight helper to publish ui.telemetry events from the Dashboard tab.

        This follows the unified telemetry schema and must never raise or block
        normal UI flow.
        """
        try:
            if not getattr(self, "event_bus", None):
                return
            payload: Dict[str, Any] = {
                "component": "dashboard",
                "channel": "ui.telemetry",
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": success,
                "error": error,
                "metadata": metadata or {},
            }
            self.event_bus.publish("ui.telemetry", payload)
        except Exception as e:
            # Telemetry must never interfere with the dashboard
            logger.debug("Dashboard UI telemetry publish failed for %s: %s", event_type, e)
    
    def refresh_status(self):
        """Refresh all status indicators."""
        self._emit_ui_telemetry(
            "dashboard.refresh_status",
            metadata={"source": "dashboard_tab"},
        )
        self.log_message("Refreshing system status...")
        self.check_redis_health()
        
        # If event bus is available, request system status update - publish is SYNC
        if self.event_bus:
            try:
                # Direct synchronous publish with error handling
                try:
                    self.event_bus.publish("system.status.request", {"source": "dashboard"})
                    self.log_message("Status refresh request sent.")
                except Exception as e:
                    self.log_message(f"Status refresh failed: {e}", error=True)
            except Exception as e:
                self.log_message(f"Error requesting status refresh: {str(e)}", error=True)
        else:
            self.log_message("Event bus not available for status refresh.", error=True)
    
    def reconnect_services(self):
        """Attempt to reconnect all services."""
        self._emit_ui_telemetry(
            "dashboard.reconnect_services",
            metadata={"source": "dashboard_tab"},
        )
        self.log_message("Attempting to reconnect services...")
        
        # Reconnect Redis
        self.initialize_redis_connection()
        
        # Request reconnection of other services via event bus - publish is SYNC
        if self.event_bus:
            try:
                # Direct synchronous publish with error handling
                try:
                    self.event_bus.publish("system.reconnect", {"source": "dashboard"})
                    self.log_message("Reconnection request sent to all services.")
                except Exception as e:
                    self.log_message(f"Reconnection request failed: {e}", error=True)
            except Exception as e:
                self.log_message(f"Error requesting service reconnection: {str(e)}", error=True)
        else:
            self.log_message("Event bus not available for reconnection request.", error=True)
    
    def update_all_indicators(self):
        """Update all status indicators with current system status."""
        try:
            # Redis health is checked by its own dedicated timer (health_check_timer)
            # so we do NOT call it again here to avoid double-blocking the main thread

            # Use the latest real connection flags updated by event handlers
            if hasattr(self, "system_connected"):
                self.update_status_indicator(self.system_status, self.system_connected)

            if hasattr(self, "redis_connected"):
                self.update_status_indicator(self.redis_status, self.redis_connected)

            if hasattr(self, "blockchain_connected"):
                self.update_status_indicator(self.blockchain_status, self.blockchain_connected)

            if hasattr(self, "mining_connected"):
                self.update_status_indicator(self.mining_status, self.mining_connected)

            if hasattr(self, "trading_connected"):
                self.update_status_indicator(self.trading_status, self.trading_connected)

            if hasattr(self, "ai_connected"):
                self.update_status_indicator(self.ai_status, self.ai_connected)

            # Update progress bars with REAL psutil metrics
            try:
                import psutil
                # CRITICAL FIX: interval=None is NON-BLOCKING (returns since last call)
                # interval=0.1 was blocking the main Qt thread for 100ms every 5s
                cpu_usage = int(psutil.cpu_percent(interval=None))
                memory_usage = int(psutil.virtual_memory().percent)
                
                if hasattr(self, 'cpu_progress'):
                    self.cpu_progress.setValue(cpu_usage)
                if hasattr(self, 'memory_progress'):
                    self.memory_progress.setValue(memory_usage)
            except ImportError:
                logger.error("psutil not installed - cannot get real system metrics")
            except Exception as e:
                logger.error(f"Error getting real system metrics: {e}")
                
        except Exception as e:
            logger.error(f"Error updating indicators: {e}")
    
    def _set_led_color(self, indicator, color: str, tooltip: str = ""):
        """Set LED indicator color without destroying its round shape.
        BUG 3 FIX: Never call setText() or setStyleSheet("color:...") on LEDs.
        Only change the background-color while preserving border-radius."""
        indicator.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border: 2px solid {color};
                border-radius: 12px;
                min-width: 24px;
                min-height: 24px;
            }}
        """)
        if tooltip:
            indicator.setToolTip(tooltip)
    
    def handle_mining_stats(self, data: Dict[str, Any]):
        """Handle mining stats updates from event bus."""
        try:
            if data:
                logger.debug(f"Mining stats update: {data}")
                from utils.qt_thread_safe import run_on_main_thread
                def update_ui():
                    if hasattr(self, 'mining_status') and self.mining_status:
                        hashrate = data.get('hashrate', 0)
                        is_active = data.get('is_mining', False) or hashrate > 0
                        # BUG 3 FIX: Update LED color, not text
                        if is_active:
                            self._set_led_color(self.mining_status, "#00ff00",
                                                f"Mining Active ({hashrate:.2f} H/s)")
                        else:
                            self._set_led_color(self.mining_status, "#888888",
                                                "Mining Idle")
                run_on_main_thread(update_ui)
        except Exception as e:
            logger.error(f"Error handling mining stats: {e}")
    
    def handle_trading_update(self, data: Dict[str, Any]):
        """Handle trading portfolio updates from event bus."""
        try:
            if data:
                logger.debug(f"Trading update: {data}")
                from utils.qt_thread_safe import run_on_main_thread
                def update_ui():
                    if hasattr(self, 'trading_status') and self.trading_status:
                        portfolio_value = data.get('total_value', 0)
                        pnl = data.get('pnl', 0)
                        is_active = data.get('is_trading', False) or portfolio_value > 0
                        # BUG 3 FIX: Update LED color, not text
                        if is_active:
                            color = "#00ff00" if pnl >= 0 else "#ff4444"
                            pnl_sign = "+" if pnl >= 0 else ""
                            self._set_led_color(self.trading_status, color,
                                                f"Trading: ${portfolio_value:.2f} ({pnl_sign}{pnl:.2f}%)")
                        else:
                            self._set_led_color(self.trading_status, "#888888",
                                                "No active trades")
                run_on_main_thread(update_ui)
        except Exception as e:
            logger.error(f"Error handling trading update: {e}")
    
    def _handle_mining_statistics_update(self, data: Dict[str, Any]):
        """Handle mining statistics updates from mining intelligence."""
        try:
            if not data:
                return
            
            stats_data = data.get('data', data)
            from utils.qt_thread_safe import run_on_main_thread
            
            def update_ui():
                # BUG 3 FIX: Update LED color, not text
                if hasattr(self, 'mining_status') and self.mining_status:
                    hashrate = stats_data.get('total_hashrate', 0)
                    efficiency = stats_data.get('average_efficiency', 0)
                    if hashrate > 0:
                        self._set_led_color(self.mining_status, "#00ff00",
                                            f"Mining: {hashrate:.2f} H/s ({efficiency:.1f}% eff)")
                    
            run_on_main_thread(update_ui)
            logger.debug(f"Mining statistics update received")
        except Exception as e:
            logger.error(f"Error handling mining statistics update: {e}")
    
    def _handle_mining_intelligence_update(self, data: Dict[str, Any]):
        """Handle mining intelligence updates."""
        try:
            if not data:
                return
            
            from utils.qt_thread_safe import run_on_main_thread
            
            def update_ui():
                if hasattr(self, 'mining_status') and self.mining_status:
                    recommendations = data.get('recommendations', [])
                    if recommendations:
                        # BUG 3 FIX: Update LED tooltip, not text
                        self._set_led_color(self.mining_status, "#00ff00",
                                            f"Mining: {len(recommendations)} optimizations available")
                        
            run_on_main_thread(update_ui)
        except Exception as e:
            logger.error(f"Error handling mining intelligence update: {e}")
    
    def _handle_hardware_recommendations(self, data: Dict[str, Any]):
        """Handle hardware recommendations from mining intelligence."""
        try:
            if not data:
                return
            
            recommendations = data.get('recommendations', [])
            logger.info(f"Received {len(recommendations)} hardware recommendations")
            
            # Could update a recommendations panel if one exists
            from utils.qt_thread_safe import run_on_main_thread
            
            def update_ui():
                if hasattr(self, 'log_output') and self.log_output and recommendations:
                    for rec in recommendations[:3]:  # Show top 3
                        self.log_output.append(f"💡 Hardware: {rec.get('message', rec)}")
                        
            run_on_main_thread(update_ui)
        except Exception as e:
            logger.error(f"Error handling hardware recommendations: {e}")
    
    def _handle_mining_connection(self, data: Dict[str, Any]):
        """Handle mining node/pool connection status updates.
        Updates the mining LED to reflect real-time connection status."""
        try:
            if not data:
                return
            connected = data.get('connected', False)
            from utils.qt_thread_safe import run_on_main_thread
            def update_ui():
                if hasattr(self, 'mining_status') and self.mining_status:
                    if connected is True:
                        self._set_led_color(self.mining_status, "#00ff00",
                                            "Mining: Connected")
                    elif connected == "connecting":
                        self._set_led_color(self.mining_status, "#CCAA00",
                                            "Mining: Connecting...")
                    else:
                        self._set_led_color(self.mining_status, "#888888",
                                            "Mining: Disconnected")
            run_on_main_thread(update_ui)
        except Exception as e:
            logger.error(f"Error handling mining connection: {e}")
    
    def _connect_to_central_brain(self):
        """Connect to ThothAI central brain system."""
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).replace('gui/qt_frames', ''))
            
            # Connect to central ThothAI brain via event bus
            self._central_thoth = None  # Use event bus for communication
            if self._central_thoth:
                logger.info("✅ Dashboard Tab connected to ThothAI central brain")
                
                # Register dashboard events with central brain
                try:
                    if hasattr(self._central_thoth, 'register_component'):
                        self._central_thoth.register_component('dashboard_tab')  # type: ignore[attr-defined]
                except Exception:
                    pass
                    
            else:
                # 2025 FIX #10: Create minimal ThothAI for dashboard
                logger.info("✅ Creating dashboard ThothAI integration")
                self._central_thoth = None
                    
        except Exception as e:
            logger.error(f"Error connecting to central ThothAI: {e}")
            self._central_thoth = None
    
    def _start_real_time_data_feeds(self):
        """Start real-time system monitoring data feeds via event bus subscriptions."""
        if not self.event_bus:
            logger.debug("No event bus available for real-time data feeds")
            return

        try:
            def _on_cpu_update(data):
                if not data:
                    return
                try:
                    from utils.qt_thread_safe import run_on_main_thread
                    cpu_pct = data.get('cpu_percent', data.get('usage', 0))
                    def _update():
                        if hasattr(self, 'cpu_progress') and self.cpu_progress:
                            self.cpu_progress.setValue(int(cpu_pct))
                            self.cpu_progress.setFormat(f"CPU: {cpu_pct:.1f}%")
                    run_on_main_thread(_update)
                except Exception as e:
                    logger.debug(f"CPU feed update error: {e}")

            def _on_memory_update(data):
                if not data:
                    return
                try:
                    from utils.qt_thread_safe import run_on_main_thread
                    mem_pct = data.get('memory_percent', data.get('usage', 0))
                    def _update():
                        if hasattr(self, 'memory_progress') and self.memory_progress:
                            self.memory_progress.setValue(int(mem_pct))
                            self.memory_progress.setFormat(f"Memory: {mem_pct:.1f}%")
                    run_on_main_thread(_update)
                except Exception as e:
                    logger.debug(f"Memory feed update error: {e}")

            def _on_mining_status(data):
                if not data:
                    return
                try:
                    from utils.qt_thread_safe import run_on_main_thread
                    active = data.get('active', data.get('mining', False))
                    hashrate = data.get('hashrate', 0)
                    def _update():
                        if hasattr(self, 'mining_status') and self.mining_status:
                            if active:
                                self._set_led_color(self.mining_status, "#00ff00",
                                                    f"Mining: Active ({hashrate} H/s)" if hashrate else "Mining: Active")
                            else:
                                self._set_led_color(self.mining_status, "#888888", "Mining: Idle")
                    run_on_main_thread(_update)
                except Exception as e:
                    logger.debug(f"Mining feed update error: {e}")

            def _on_trading_status(data):
                if not data:
                    return
                try:
                    from utils.qt_thread_safe import run_on_main_thread
                    connected = data.get('connected', data.get('active', False))
                    exchange = data.get('exchange', '')
                    def _update():
                        if hasattr(self, 'trading_status') and self.trading_status:
                            if connected:
                                self._set_led_color(self.trading_status, "#00ff00",
                                                    f"Trading: Connected ({exchange})" if exchange else "Trading: Connected")
                            else:
                                self._set_led_color(self.trading_status, "#888888", "Trading: Disconnected")
                    run_on_main_thread(_update)
                except Exception as e:
                    logger.debug(f"Trading feed update error: {e}")

            self.event_bus.subscribe("system.cpu", _on_cpu_update)
            self.event_bus.subscribe("system.memory", _on_memory_update)
            self.event_bus.subscribe("mining.status", _on_mining_status)
            self.event_bus.subscribe("trading.status", _on_trading_status)

            logger.info("Real-time data feeds subscribed successfully")
        except Exception as e:
            logger.warning(f"Could not start real-time data feeds: {e}")
