#!/usr/bin/env python3
"""
Kingdom AI Mining Dashboard - PyQt6 Implementation

A comprehensive mining dashboard that integrates all mining, farming, and intelligence data
from the Kingdom AI system into a single, unified PyQt6 interface.
"""

import sys
import asyncio
import logging
import json
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import traceback

# PyQt6 Imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QProgressBar, QSplitter, QFormLayout, QGroupBox, QFrame,
    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QTextEdit,
    QMessageBox, QMenu, QMenuBar, QStatusBar, QDialog, QDialogButtonBox,
    QFileDialog, QSystemTrayIcon, QStyle, QSizePolicy, QScrollArea, QToolBar
)
from PyQt6.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal, pyqtSlot, QSize, QPoint, QRectF
from PyQt6.QtGui import (
    QColor, QPalette, QFont, QIcon, QPixmap, QPainter, QPen, QBrush,
    QLinearGradient, QAction, QFontMetrics, QTextCursor, QImage, QPainterPath
)
from PyQt6.QtCharts import (
    QChart, QChartView, QLineSeries, QValueAxis, QBarSet,
    QBarSeries, QBarCategoryAxis, QPieSeries, QPieSlice
)

# Kingdom AI Imports
try:
    from core.mining_system import MiningSystem
    from core.mining_intelligence import MiningIntelligence
    from core.mining_dashboard import MiningDashboard
    from core.event_bus import EventBus
    from core.redis_nexus import RedisNexus
    from core.quantum_mining import QuantumMiningManager
    from core.blockchain.connector import BlockchainConnector
    from core.mining.hardware_monitor import HardwareMonitor
    from core.mining.profitability import ProfitabilityCalculator
    from core.mining.pool_manager import PoolManager
    from core.airdrop.farm_manager import AirdropFarmManager
    from core.utils.logger import get_logger
    from core.utils.kingdom_styles import KingdomStyles
    from core.utils.qt_helpers import create_horizontal_line, create_vertical_line
    from core.utils.qt_charts import (
        create_line_chart, create_bar_chart, create_pie_chart,
        update_chart_theme, ChartTheme
    )
except ImportError as e:
    print(f"Error importing Kingdom AI modules: {e}")
    raise

# Configure logging
logger = get_logger(__name__)

# Constants
REFRESH_INTERVAL = 2000  # ms
MAX_LOG_LINES = 1000
MIN_WINDOW_WIDTH = 1280
MIN_WINDOW_HEIGHT = 768

# Colors
COLOR_PRIMARY = "#2c3e50"
COLOR_SECONDARY = "#34495e"
COLOR_ACCENT = "#3498db"
COLOR_TEXT = "#ecf0f1"
COLOR_TEXT_DISABLED = "#7f8c8d"
COLOR_SUCCESS = "#2ecc71"
COLOR_WARNING = "#f39c12"
COLOR_ERROR = "#e74c3c"
COLOR_BACKGROUND = "#1a252f"

# Fonts
FONT_HEADER = QFont("Segoe UI", 12, QFont.Weight.Bold)
FONT_TITLE = QFont("Segoe UI", 10, QFont.Weight.Bold)
FONT_NORMAL = QFont("Segoe UI", 9)
FONT_MONO = QFont("Consolas", 9)
FONT_SMALL = QFont("Segoe UI", 8)

class MiningWorker(QObject):
    """Worker thread for handling mining operations and data updates"""
    
    # Signals
    stats_updated = pyqtSignal(dict)  # Mining statistics
    hardware_updated = pyqtSignal(dict)  # Hardware status
    pools_updated = pyqtSignal(list)  # Mining pools
    airdrops_updated = pyqtSignal(list)  # Airdrop opportunities
    algorithm_updated = pyqtSignal(dict)  # Mining algorithm info
    error_occurred = pyqtSignal(str)  # Error messages
    log_message = pyqtSignal(str, str)  # Log messages (message, level)
    
    def __init__(self, event_bus: EventBus = None):
        super().__init__()
        # Use provided event bus or get singleton instance
        if event_bus is None:
            from core.event_bus import EventBus
            self.event_bus = EventBus.get_instance() if hasattr(EventBus, 'get_instance') else EventBus()
            self.log("⚠️ MiningWorker: No event_bus provided, using singleton/new instance", "WARNING")
        else:
            self.event_bus = event_bus
            self.log("✅ MiningWorker: Using provided global event_bus", "INFO")
        self.running = True
        self.mining_system = None
        self.mining_intel = None
        self.quantum_manager = None
        self.hardware_monitor = None
        self.pool_manager = None
        self.airdrop_manager = None
        self.blockchain_connector = None
        self.last_update = time.time()
    
    def log(self, message: str, level: str = "INFO"):
        """Emit a log message"""
        self.log_message.emit(message, level)
    
    async def initialize(self) -> bool:
        """Initialize all mining components"""
        try:
            self.log("Initializing mining worker...")
            
            # Initialize Redis connection (required)
            try:
                self.redis = RedisNexus(host='localhost', port=6380, password='QuantumNexus2025')
                await self.redis.connect()
                if not self.redis.is_connected():
                    raise ConnectionError("Failed to connect to Redis Quantum Nexus")
                self.log("Connected to Redis Quantum Nexus")
            except Exception as e:
                error_msg = f"Failed to connect to Redis: {str(e)}"
                self.log(error_msg, "ERROR")
                self.error_occurred.emit(error_msg)
                return False
            
            # Initialize mining system
            try:
                self.mining_system = MiningSystem(event_bus=self.event_bus)
                await self.mining_system.initialize()
                self.log("Mining system initialized")
            except Exception as e:
                error_msg = f"Failed to initialize mining system: {str(e)}"
                self.log(error_msg, "ERROR")
                self.error_occurred.emit(error_msg)
                return False
            
            # Initialize mining intelligence
            try:
                self.mining_intel = MiningIntelligence(event_bus=self.event_bus, redis_nexus=self.redis)
                await self.mining_intel.initialize()
                self.log("Mining intelligence initialized")
            except Exception as e:
                error_msg = f"Failed to initialize mining intelligence: {str(e)}"
                self.log(error_msg, "ERROR")
                # Continue without mining intelligence
            
            # Initialize quantum mining manager
            try:
                self.quantum_manager = QuantumMiningManager(event_bus=self.event_bus)
                await self.quantum_manager.initialize()
                self.log("Quantum mining manager initialized")
            except Exception as e:
                error_msg = f"Failed to initialize quantum manager: {str(e)}"
                self.log(error_msg, "WARNING")
                # Continue without quantum mining
            
            # Initialize hardware monitor
            try:
                self.hardware_monitor = HardwareMonitor(event_bus=self.event_bus)
                await self.hardware_monitor.initialize()
                self.log("Hardware monitor initialized")
            except Exception as e:
                error_msg = f"Failed to initialize hardware monitor: {str(e)}"
                self.log(error_msg, "WARNING")
            
            # Initialize pool manager
            try:
                self.pool_manager = PoolManager(event_bus=self.event_bus)
                await self.pool_manager.initialize()
                self.log("Pool manager initialized")
            except Exception as e:
                error_msg = f"Failed to initialize pool manager: {str(e)}"
                self.log(error_msg, "WARNING")
            
            # Initialize airdrop manager
            try:
                self.airdrop_manager = AirdropFarmManager(event_bus=self.event_bus)
                await self.airdrop_manager.initialize()
                self.log("Airdrop manager initialized")
            except Exception as e:
                error_msg = f"Failed to initialize airdrop manager: {str(e)}"
                self.log(error_msg, "WARNING")
            
            # Initialize blockchain connector
            try:
                self.blockchain_connector = BlockchainConnector(event_bus=self.event_bus)
                await self.blockchain_connector.initialize()
                self.log("Blockchain connector initialized")
            except Exception as e:
                error_msg = f"Failed to initialize blockchain connector: {str(e)}"
                self.log(error_msg, "WARNING")
            
            self.log("Mining worker initialization complete")
            return True
            
        except Exception as e:
            error_msg = f"Error initializing mining worker: {str(e)}\n{traceback.format_exc()}"
            self.log(error_msg, "ERROR")
            self.error_occurred.emit(error_msg)
            return False
    
    async def run(self):
        """Main worker loop"""
        self.log("Starting mining worker loop")
        try:
            self.running = True
            while self.running:
                start_time = time.time()
                try:
                    # Update mining stats
                    if self.mining_system:
                        try:
                            stats = await self.mining_system.get_stats()
                            if stats:
                                self.stats_updated.emit(stats)
                        except Exception as e:
                            self.log(f"Error updating stats: {str(e)}", "ERROR")
                    
                    # Update hardware info
                    if self.hardware_monitor:
                        try:
                            hardware = await self.hardware_monitor.get_hardware_info()
                            if hardware:
                                self.hardware_updated.emit(hardware)
                        except Exception as e:
                            self.log(f"Error updating hardware info: {str(e)}", "ERROR")
                    
                    # Update pool info
                    if self.pool_manager:
                        try:
                            pools = await self.pool_manager.get_pools()
                            if pools:
                                self.pools_updated.emit(pools)
                        except Exception as e:
                            self.log(f"Error updating pool info: {str(e)}", "ERROR")
                    
                    # Update airdrops
                    if self.airdrop_manager:
                        try:
                            airdrops = await self.airdrop_manager.get_opportunities()
                            if airdrops:
                                self.airdrops_updated.emit(airdrops)
                        except Exception as e:
                            self.log(f"Error updating airdrops: {str(e)}", "ERROR")
                    
                    # Update algorithm info
                    if self.mining_intel:
                        try:
                            algo_info = await self.mining_intel.get_optimal_algorithm()
                            if algo_info:
                                self.algorithm_updated.emit(algo_info)
                        except Exception as e:
                            self.log(f"Error updating algorithm info: {str(e)}", "ERROR")
                    
                    # Calculate time to sleep to maintain refresh rate
                    elapsed = (time.time() - start_time) * 1000  # ms
                    sleep_time = max(0, (REFRESH_INTERVAL - elapsed) / 1000)
                    await asyncio.sleep(sleep_time)
                    
                except asyncio.CancelledError:
                    self.log("Mining worker loop cancelled")
                    break
                except Exception as e:
                    self.log(f"Error in mining worker loop: {str(e)}\n{traceback.format_exc()}", "ERROR")
                    await asyncio.sleep(5)  # Prevent tight loop on error
        
        except Exception as e:
            error_msg = f"Fatal error in mining worker: {str(e)}\n{traceback.format_exc()}"
            self.log(error_msg, "CRITICAL")
            self.error_occurred.emit(error_msg)
        finally:
            self.log("Mining worker stopped")
    
    async def cleanup(self):
        """Clean up resources"""
        self.running = False
        
        if self.mining_system:
            try:
                await self.mining_system.cleanup()
            except Exception as e:
                self.log(f"Error cleaning up mining system: {str(e)}", "ERROR")
        
        if self.redis:
            try:
                await self.redis.close()
            except Exception as e:
                self.log(f"Error closing Redis connection: {str(e)}", "ERROR")
        
        self.log("Mining worker cleanup complete")

class MiningDashboard(QMainWindow):
    """Main mining dashboard window"""
    
    def __init__(self, event_bus: EventBus = None):
        super().__init__()
        # Use provided event bus or get singleton instance
        if event_bus is None:
            from core.event_bus import EventBus
            self.event_bus = EventBus.get_instance() if hasattr(EventBus, 'get_instance') else EventBus()
            print("⚠️ MiningDashboard: No event_bus provided, using singleton/new instance")
        else:
            self.event_bus = event_bus
            print("✅ MiningDashboard: Using provided global event_bus")
        self.worker = None
        self.worker_thread = None
        self.mining_active = False
        self.quantum_mining_active = False
        self.current_stats = {}
        self.current_hardware = {}
        self.current_pools = []
        self.current_airdrops = []
        self.current_algorithm = {}
        
        # Initialize UI
        self.init_ui()
        
        # Start worker thread
        self.start_worker()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Kingdom AI - Mining Dashboard")
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        
        # Set application style
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_BACKGROUND};
                color: {COLOR_TEXT};
            }}
            QTabWidget::pane {{
                border: 1px solid {COLOR_SECONDARY};
                border-radius: 4px;
                padding: 5px;
                background: {COLOR_SECONDARY};
            }}
            QTabBar::tab {{
                background: {COLOR_PRIMARY};
                color: {COLOR_TEXT};
                padding: 8px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected, QTabBar::tab:hover {{
                background: {COLOR_ACCENT};
            }}
            QLabel {{
                color: {COLOR_TEXT};
            }}
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
            QPushButton:disabled {{
                background-color: #7f8c8d;
            }}
            QTableWidget {{
                background-color: {COLOR_SECONDARY};
                border: 1px solid {COLOR_PRIMARY};
                gridline-color: {COLOR_PRIMARY};
                color: {COLOR_TEXT};
            }}
            QHeaderView::section {{
                background-color: {COLOR_PRIMARY};
                color: white;
                padding: 4px;
                border: none;
            }}
            QProgressBar {{
                border: 1px solid {COLOR_PRIMARY};
                border-radius: 4px;
                text-align: center;
                background: {COLOR_SECONDARY};
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_ACCENT};
                width: 10px;
            }}
        """)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Add tabs
        self.setup_dashboard_tab()
        self.setup_hardware_tab()
        self.setup_mining_tab()
        self.setup_quantum_tab()
        self.setup_airdrop_tab()
        self.setup_analytics_tab()
        self.setup_settings_tab()
        
        main_layout.addWidget(self.tab_widget)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Apply custom styles
        self.apply_styles()
    
    def apply_styles(self):
        """Apply custom styles to the UI"""
        # Set window icon if available
        try:
            self.setWindowIcon(QIcon("assets/images/kingdom_icon.png"))
        except:
            pass
    
    def start_worker(self):
        """Start the worker thread"""
        self.worker_thread = QThread()
        self.worker = MiningWorker(self.event_bus)
        self.worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker.stats_updated.connect(self.update_stats)
        self.worker.hardware_updated.connect(self.update_hardware)
        self.worker.pools_updated.connect(self.update_pools)
        self.worker.airdrops_updated.connect(self.update_airdrops)
        self.worker.algorithm_updated.connect(self.update_algorithm)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.log_message.connect(self.handle_log_message)
        
        # Start thread
        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()
        
        # Initialize worker asynchronously
        asyncio.ensure_future(self.initialize_worker())
    
    async def initialize_worker(self):
        """Initialize the worker asynchronously"""
        try:
            success = await self.worker.initialize()
            if not success:
                self.statusBar().showMessage("Failed to initialize mining worker", 5000)
        except Exception as e:
            self.handle_error(f"Error initializing worker: {str(e)}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.worker:
            asyncio.ensure_future(self.cleanup())
        event.accept()
    
    async def cleanup(self):
        """Clean up resources"""
        if self.worker:
            await self.worker.cleanup()
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
    
    # ===== UI Setup Methods =====
    
    def setup_dashboard_tab(self):
        """Setup the dashboard tab with key metrics and charts"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Stats summary row
        stats_layout = QHBoxLayout()
        
        # Hashrate card
        self.hashrate_card = self.create_stat_card(
            "Total Hashrate", "0 H/s", "Speed across all devices")
        stats_layout.addWidget(self.hashrate_card)
        
        # Shares card
        self.shares_card = self.create_stat_card(
            "Shares", "0/0 (0%)", "Accepted/Rejected shares")
        stats_layout.addWidget(self.shares_card)
        
        # Earnings card
        self.earnings_card = self.create_stat_card(
            "24h Earnings", "0.00000000 BTC", "≈ $0.00")
        stats_layout.addWidget(self.earnings_card)
        
        # Uptime card
        self.uptime_card = self.create_stat_card(
            "Uptime", "00:00:00", "Mining duration")
        stats_layout.addWidget(self.uptime_card)
        
        layout.addLayout(stats_layout)
        
        # Charts row
        charts_layout = QHBoxLayout()
        
        # Hashrate chart
        self.hashrate_chart = self.create_chart("Hashrate (H/s)")
        charts_layout.addWidget(self.hashrate_chart, 2)
        
        # Efficiency chart
        self.efficiency_chart = self.create_chart("Efficiency (H/W)")
        charts_layout.addWidget(self.efficiency_chart, 1)
        
        layout.addLayout(charts_layout, 1)
        
        # Mining pools table
        pools_label = QLabel("Active Mining Pools")
        pools_label.setFont(FONT_HEADER)
        layout.addWidget(pools_label)
        
        self.pools_table = QTableWidget()
        self.pools_table.setColumnCount(5)
        self.pools_table.setHorizontalHeaderLabels(["Pool", "URL", "Status", "Workers", "Hashrate"])
        self.pools_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.pools_table)
        
        self.tab_widget.addTab(tab, "Dashboard")
    
    def setup_hardware_tab(self):
        """Setup the hardware monitoring tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Hardware summary
        hw_summary = QGroupBox("Hardware Summary")
        hw_layout = QGridLayout()
        
        # CPU Info
        self.cpu_label = QLabel("CPU: Loading...")
        self.cpu_usage = QProgressBar()
        hw_layout.addWidget(QLabel("CPU:"), 0, 0)
        hw_layout.addWidget(self.cpu_label, 0, 1)
        hw_layout.addWidget(self.cpu_usage, 0, 2)
        
        # GPU Info
        self.gpu_label = QLabel("GPU: Not detected")
        self.gpu_usage = QProgressBar()
        hw_layout.addWidget(QLabel("GPU:"), 1, 0)
        hw_layout.addWidget(self.gpu_label, 1, 1)
        hw_layout.addWidget(self.gpu_usage, 1, 2)
        
        # Memory
        self.mem_label = QLabel("Memory: 0.0/0.0 GB (0%)")
        self.mem_usage = QProgressBar()
        hw_layout.addWidget(QLabel("Memory:"), 2, 0)
        hw_layout.addWidget(self.mem_label, 2, 1)
        hw_layout.addWidget(self.mem_usage, 2, 2)
        
        hw_summary.setLayout(hw_layout)
        layout.addWidget(hw_summary)
        
        # Hardware details table
        self.hw_table = QTableWidget()
        self.hw_table.setColumnCount(4)
        self.hw_table.setHorizontalHeaderLabels(["Device", "Type", "Status", "Hashrate"])
        self.hw_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.hw_table, 1)
        
        self.tab_widget.addTab(tab, "Hardware")
    
    def setup_mining_tab(self):
        """Setup the mining control tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Mining controls
        controls_group = QGroupBox("Mining Controls")
        controls_layout = QVBoxLayout()
        
        # Algorithm selection
        algo_layout = QHBoxLayout()
        algo_layout.addWidget(QLabel("Algorithm:"))
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(["Autodetect", "SHA-256", "Scrypt", "X11"])
        algo_layout.addWidget(self.algo_combo)
    
    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self.running = True
    
    async def run(self):
        """Main worker loop"""
        while self.running:
            try:
                # Fetch latest data from event bus
                stats = await self.event_bus.request("mining.stats.get", {})
                if stats:
                    self.update_signal.emit({"type": "stats", "data": stats})
                
                # Add more data fetches here
                
            except Exception as e:
                logger.error(f"Error in mining worker: {e}")
            
            await asyncio.sleep(1)  # Update every second

class MiningDashboardQt(QMainWindow):
    """Main mining dashboard window"""
    
    def __init__(self, event_bus: Optional[EventBus] = None, parent: Optional[QWidget] = None, config: Optional[Dict] = None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.config = config or {}
        self.worker = None
        self.worker_thread = None
        self.mining_system = None
        self.mining_intel = None
        self.quantum_manager = None
        self.hardware_monitor = None
        self.pool_manager = None
        self.airdrop_manager = None
        self.blockchain_connector = None
        self.redis_nexus = None
        
        # Initialize Redis connection
        self.init_redis()
        
        self.setWindowTitle("Kingdom AI Mining Dashboard")
        self.setMinimumSize(1280, 800)
        
        self.init_ui()
        self.apply_styles()
        self.start_worker()
        
    def init_redis(self):
        """Initialize Redis connection - STRICT ENFORCEMENT
        
        According to system requirements, the application must halt and exit
        if Redis connection fails. No fallback is permitted.
        """
        try:
            from core.redis_nexus import RedisNexus
            # Connect to Redis with strict parameters
            self.redis_nexus = RedisNexus(
                host='localhost',
                port=6380,
                password='QuantumNexus2025',
                db=0
            )
            
            # Verify connection is active
            if not self.redis_nexus.ping():
                error_msg = "Failed to ping Redis Quantum Nexus. Connection failed."
                self.logger.critical(error_msg)
                QMessageBox.critical(
                    self, 
                    "Critical Redis Connection Error",
                    f"{error_msg}\n\nThe application will now exit."
                )
                sys.exit(1)
            
            # Set connection status if we have the widget
            if hasattr(self, 'connection_status'):
                self.connection_status.setText("Connected")
                self.connection_status.setStyleSheet("color: green; font-weight: bold;")
                
            # Log success
            self.logger.info("Successfully connected to Redis Quantum Nexus")
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize Redis: {str(e)}"
            self.logger.critical(error_msg)
            
            # Show critical error and exit
            QMessageBox.critical(
                self, 
                "Critical Redis Connection Error",
                f"{error_msg}\n\nThe application will now exit."
            )
            sys.exit(1)
    
    def init_ui(self):
        """Initialize the user interface"""
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Add tabs
        self.tab_widget.addTab(self.create_dashboard_tab(), "Dashboard")
        self.tab_widget.addTab(self.create_hardware_tab(), "Hardware")
        self.tab_widget.addTab(self.create_mining_tab(), "Mining")
        self.tab_widget.addTab(self.create_quantum_tab(), "Quantum")
        self.tab_widget.addTab(self.create_airdrop_tab(), "Airdrops")
        self.tab_widget.addTab(self.create_analytics_tab(), "Analytics")
        self.tab_widget.addTab(self.create_settings_tab(), "Settings")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Connect signals
        self.start_button.clicked.connect(self.start_mining)
        self.stop_button.clicked.connect(self.stop_mining)
    
    def create_dashboard_tab(self) -> QWidget:
        """Create the main dashboard tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Summary cards
        cards_layout = QHBoxLayout()
        
        # Hashrate card
        self.hashrate_card = self.create_summary_card("Hashrate", "0 H/s", "speed")
        cards_layout.addWidget(self.hashrate_card)
        
        # Active workers card
        self.workers_card = self.create_summary_card("Active Workers", "0", "workers")
        cards_layout.addWidget(self.workers_card)
        
        # 24h reward card
        self.reward_card = self.create_summary_card("24h Reward", "0 KDA", "reward")
        cards_layout.addWidget(self.reward_card)
        
        # Uptime card
        self.uptime_card = self.create_summary_card("Uptime", "00:00:00", "uptime")
        cards_layout.addWidget(self.uptime_card)
        
        layout.addLayout(cards_layout)
        
        # Charts
        charts_layout = QHBoxLayout()
        
        # Hashrate chart
        self.hashrate_chart = self.create_chart_widget("Hashrate (24h)", "line")
        charts_layout.addWidget(self.hashrate_chart)
        
        # Profitability chart
        self.profit_chart = self.create_chart_widget("Profitability (7d)", "line")
        charts_layout.addWidget(self.profit_chart)
        
        layout.addLayout(charts_layout)
        
        # Recent shares
        shares_group = QGroupBox("Recent Shares")
        shares_layout = QVBoxLayout()
        
        self.shares_table = QTableWidget()
        self.shares_table.setColumnCount(4)
        self.shares_table.setHorizontalHeaderLabels(["Time", "Share", "Status", "Difficulty"])
        self.shares_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.shares_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        shares_layout.addWidget(self.shares_table)
        shares_group.setLayout(shares_layout)
        layout.addWidget(shares_group)
        
        return tab
    
    def create_hardware_tab(self) -> QWidget:
        """Create the hardware monitoring tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Device details
        details_group = QGroupBox("Device Details")
        details_layout = QFormLayout()
        
        self.device_name = QLabel("N/A")
        self.device_status = QLabel("N/A")
        self.device_temp = QLabel("N/A")
        self.device_power = QLabel("N/A")
        self.device_efficiency = QLabel("N/A")
        
        details_layout.addRow("Device:", self.device_name)
        details_layout.addRow("Status:", self.device_status)
        details_layout.addRow("Temperature:", self.device_temp)
        details_layout.addRow("Power Usage:", self.device_power)
        details_layout.addRow("Efficiency:", self.device_efficiency)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        return tab
    
    def create_mining_tab(self) -> QWidget:
        """Create the mining control tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Mining controls
        controls_group = QGroupBox("Mining Controls")
        controls_layout = QGridLayout()
        
        # Algorithm selection
        controls_layout.addWidget(QLabel("Algorithm:"), 0, 0)
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(["RandomX", "KawPow", "CuckooCycle", "Autolykos2"])
        controls_layout.addWidget(self.algo_combo, 0, 1)
        
        # Intensity
        controls_layout.addWidget(QLabel("Intensity:"), 1, 0)
        self.intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.intensity_slider.setRange(1, 10)
        self.intensity_slider.setValue(5)
        controls_layout.addWidget(self.intensity_slider, 1, 1)
        
        # Start/Stop buttons
        self.start_button = QPushButton("Start Mining")
        self.stop_button = QPushButton("Stop Mining")
        self.stop_button.setEnabled(False)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        
        controls_layout.addLayout(button_layout, 2, 0, 1, 2)
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Mining pools
        pools_group = QGroupBox("Mining Pools")
        pools_layout = QVBoxLayout()
        
        # Pool management buttons
        pool_buttons = QHBoxLayout()
        self.add_pool_btn = QPushButton("Add Pool")
        self.edit_pool_btn = QPushButton("Edit Pool")
        self.remove_pool_btn = QPushButton("Remove")
        self.refresh_pools_btn = QPushButton("Refresh")
        
        pool_buttons.addWidget(self.add_pool_btn)
        pool_buttons.addWidget(self.edit_pool_btn)
        pool_buttons.addWidget(self.remove_pool_btn)
        pool_buttons.addStretch()
        pool_buttons.addWidget(self.refresh_pools_btn)
        
        pools_layout.addLayout(pool_buttons)
        
        # Pools table
        self.pools_table = QTableWidget()
        self.pools_table.setColumnCount(5)
        self.pools_table.setHorizontalHeaderLabels(["Pool", "URL", "Status", "Workers", "Hashrate"])
        self.pools_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pools_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pools_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        pools_layout.addWidget(self.pools_table)
        pools_group.setLayout(pools_layout)
        layout.addWidget(pools_group)
        
        # Mining log
        log_group = QGroupBox("Mining Log")
        log_layout = QVBoxLayout()
        
        self.mining_log = QTextEdit()
        self.mining_log.setReadOnly(True)
        self.mining_log.setFont(FONT_MONO)
        
        log_buttons = QHBoxLayout()
        self.clear_log_btn = QPushButton("Clear Log")
        self.copy_log_btn = QPushButton("Copy to Clipboard")
        self.save_log_btn = QPushButton("Save Log...")
        
        log_buttons.addWidget(self.clear_log_btn)
        log_buttons.addWidget(self.copy_log_btn)
        log_buttons.addStretch()
        log_buttons.addWidget(self.save_log_btn)
        
        log_layout.addWidget(self.mining_log)
        log_layout.addLayout(log_buttons)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Connect signals
        self.start_button.clicked.connect(self.start_mining)
        self.stop_button.clicked.connect(self.stop_mining)
        self.add_pool_btn.clicked.connect(self.add_pool)
        self.edit_pool_btn.clicked.connect(self.edit_pool)
        self.remove_pool_btn.clicked.connect(self.remove_pool)
        self.refresh_pools_btn.clicked.connect(self.refresh_pools)
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.copy_log_btn.clicked.connect(self.copy_log)
        self.save_log_btn.clicked.connect(self.save_log)
        
        return tab
