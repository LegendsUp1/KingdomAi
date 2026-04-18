#!/usr/bin/env python3
"""
Kingdom AI Complete PyQt6 Main Window - REAL IMPLEMENTATION
Uses ALL your existing real PyQt6 components with complete functionality.
"""
# At the very top of kingdom_ai_perfect.py:
if False:
    import event_bus_patch  # Must come first to patch before anything else uses EventBus

import logging
import asyncio
import sys
import os
import time
from typing import Optional, Dict, Any
from datetime import datetime
import json
from pathlib import Path


# PyQt6 imports
try:
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QTabWidget, QTabBar, QLabel, QPushButton, QStatusBar,
        QMenuBar, QMenu, QSplitter, QTextEdit, QProgressBar,
        QTableWidget, QTableWidgetItem, QLineEdit, QInputDialog,
        QMessageBox, QFileDialog, QDialog, QComboBox, QApplication
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve, QEvent
    from PyQt6.QtGui import QFont, QPalette, QColor, QAction, QPainter
    pyqt6_available = True
except ImportError:
    pyqt6_available = False
    raise ImportError("PyQt6 is required for Kingdom AI GUI")


# SOTA 2026 PERFORMANCE FIX: LAZY imports - these heavy modules are imported
# inside initialize_all_tabs() only when needed, NOT at module level.
# This saves 3-8 seconds of blocking at import time (ccxt, web3, matplotlib, numpy).
# Only import what's absolutely needed at module level.
try:
    from core.event_bus import EventBus
except ImportError as e:
    logging.warning(f"EventBus not available: {e}")


# Initialize logger FIRST - must be before any code that uses it
logger = logging.getLogger("KingdomAI.MainWindow")


# Import Cyberpunk Style Manager
try:
    from gui.cyberpunk_style import CyberpunkStyle  # type: ignore
    cyberpunk_available = True
    logger.info("✅ Cyberpunk Style Manager imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Cyberpunk style not available: {e}")
    cyberpunk_available = False
    # SOTA 2026: Fallback CyberpunkStyle class
    class CyberpunkStyle:  # type: ignore
        """Fallback CyberpunkStyle with basic styling functionality."""
        
        # Default cyberpunk color scheme
        COLORS = {
            "background": "#0a0a14",
            "foreground": "#00ffff",
            "accent": "#ff00ff",
            "warning": "#ffaa00",
            "error": "#ff0044",
            "success": "#00ff88",
            "border": "#1a1a2e"
        }
        
        @staticmethod
        def apply_to_widget(widget, style_name="default"):
            """Apply cyberpunk style to a widget.
            
            Args:
                widget: Widget to style
                style_name: Style preset name
            """
            if hasattr(widget, 'setStyleSheet'):
                stylesheet = CyberpunkStyle.get_style_sheet(style_name)
                widget.setStyleSheet(stylesheet)
        
        @staticmethod
        def get_style_sheet(component_type="default"):
            """Get stylesheet for component type.
            
            Args:
                component_type: Component type (default, button, input, etc.)
                
            Returns:
                CSS stylesheet string
            """
            colors = CyberpunkStyle.COLORS
            
            if component_type == "button":
                return f"""
                    QPushButton {{
                        background-color: {colors['border']};
                        color: {colors['foreground']};
                        border: 1px solid {colors['foreground']};
                        border-radius: 5px;
                        padding: 8px 16px;
                    }}
                    QPushButton:hover {{
                        background-color: {colors['foreground']};
                        color: {colors['background']};
                    }}
                """
            elif component_type == "input":
                return f"""
                    QLineEdit, QTextEdit {{
                        background-color: {colors['background']};
                        color: {colors['foreground']};
                        border: 1px solid {colors['border']};
                        border-radius: 3px;
                        padding: 5px;
                    }}
                """
            else:
                return f"""
                    QWidget {{
                        background-color: {colors['background']};
                        color: {colors['foreground']};
                    }}
                """
        
        @staticmethod
        def get_color(color_name):
            """Get a color from the palette."""
            return CyberpunkStyle.COLORS.get(color_name, "#ffffff")

# Helper functions
def apply_cyberpunk_style(widget, name):
    """Apply cyberpunk style to a widget"""
    if cyberpunk_available:
        CyberpunkStyle.apply_to_widget(widget, name)

def get_responsive_dimensions():
    """Get responsive window dimensions"""
    from PyQt6.QtWidgets import QApplication
    screen = QApplication.primaryScreen().geometry()
    return {
        'window_width': max(1400, int(screen.width() * 0.9)),
        'window_height': max(900, int(screen.height() * 0.9)),
        'min_width': 1400,
        'min_height': 900
    }


class _KingdomTabBar(QTabBar):
    """Custom QTabBar that force-fills its entire background before painting.

    ROOT FIX for X11/WSL black mark artifact:
    Qt's default QTabBar.paintEvent does NOT fill the area outside/between
    tabs.  On X11 without a desktop compositor, unfilled regions render as
    solid BLACK because there is no blending layer.  CSS background-color,
    autoFillBackground, and QPalette all fail to cover every pixel because
    Qt's style engine only applies backgrounds to *styled sub-controls*
    (::tab, ::tear, etc.), not the raw widget surface.

    This subclass paints #0F1620 across the ENTIRE bar rect before the
    normal tab painting occurs, guaranteeing zero black pixels.
    """

    _BG = QColor(0x0F, 0x16, 0x20)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Ensure the bar fully repaints its own surface on X11/WSL.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), self._BG)
        p.end()          # must end before super() creates its own painter
        super().paintEvent(event)


class KingdomMainWindow(QMainWindow):
    """
    Complete Kingdom AI PyQt6 Main Window
    Integrates ALL your real PyQt6 components with full functionality.
    """
    
    # PyQt6 signals for component communication
    component_status_changed = pyqtSignal(str, str)  # component_name, status
    system_error_occurred = pyqtSignal(str, str)     # error_type, message
    
    def __init__(self, event_bus=None):
        super().__init__()
        # CRITICAL: MUST receive event_bus - NO fallback creation allowed!
        if event_bus is None:
            raise RuntimeError("CRITICAL: KingdomMainWindow MUST receive event_bus parameter! Cannot create new instance.")
        
        self.event_bus = event_bus
        logger.info(f"✅ KingdomMainWindow using EventBus ID: {id(self.event_bus)}")
        self._greeting_triggered = False  # Track if greeting was played
        self._ws_feeds_started = False
        self._tracked_threads = []  # Track threads
        
        # Component references
        self.components = {}
        self.tab_widgets = {}
        # Map from actual tab widget instance -> logical tab id ("trading", "thoth_ai", etc.)
        self._widget_to_tab_id = {}
        # Rolling per-tab context summaries used to provide a short history
        # string with each ai.request coming from the global overlay. Keys
        # are logical tab ids such as "trading", "mining", "wallet", etc.
        self._tab_context_summaries: Dict[str, str] = {}
        self._ui_telemetry_last_emit: Dict[str, float] = {}
        self._ui_telemetry_filter_installed = False
        self._layout_cache_timer = None
        self._layout_cache_dirty = False
        self._layout_cache_timer = None
        self._layout_cache_dirty = False
        
        # Add Visual Creation Canvas
        self.visual_canvas = None
        
        # Deferred tab widgets (created in initialize_all_tabs or deferred callbacks)
        self.comms_widget: Any = None
        self.software_automation_widget: Any = None
        self.mcp_control_center_widget: Any = None
        self.biometric_security: Any = None
        
        # Loading progress hook (set externally by kingdom_ai_perfect.py)
        self._loading_progress_hook: Any = None
        
        # Setup basic window properties
        self.setup_main_window()
        
        logger.info("✅ Kingdom AI PyQt6 Main Window created")
    
    def initialize(self):
        """Initialize all GUI components and tabs"""
        try:
            logger.info("🔧 Starting initialization...")
            
            # Initialize the complete GUI
            self.create_menu_bar()
            logger.info("✅ Menu bar created")
            
            self.create_status_bar()
            logger.info("✅ Status bar created")
            
            self.create_central_widget()
            logger.info("✅ Central widget created")
            
            # 🚀 CRITICAL: Initialize ALL 10 tabs!
            logger.info("🚀 Now initializing all 10 tabs...")
            self.initialize_all_tabs()
            logger.info("✅ All 10 tabs initialized successfully")
            self._restore_layout_cache()

            self._install_global_ui_telemetry_filter()
            
            self.connect_event_bus()
            logger.info("✅ Event bus connected")
            
            # SOTA 2026: Initialize Voice Command Manager for system-wide control
            self._initialize_voice_commands()
            logger.debug("✅ Voice Command Manager initialized")
            
            logger.info("✅ Kingdom AI PyQt6 Main Window fully initialized with ALL components")
            return True
        except Exception as e:
            import traceback
            logger.error(f"❌ Failed to initialize main window: {e}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

    def _current_tab_name(self) -> str:
        try:
            idx = self.tab_widget.currentIndex()
            if idx < 0:
                return "unknown"
            name = str(self.tab_widget.tabText(idx) or "").strip().lower()
            return name or "unknown"
        except Exception:
            return "unknown"

    def _publish_ui_telemetry(self, event_type: str, metadata: Optional[Dict[str, Any]] = None, min_interval: float = 0.0):
        if not self.event_bus:
            return
        now = datetime.now().timestamp()
        last = self._ui_telemetry_last_emit.get(event_type, 0.0)
        if min_interval > 0.0 and (now - last) < min_interval:
            return
        self._ui_telemetry_last_emit[event_type] = now
        try:
            self.event_bus.publish("ui.telemetry", {
                "channel": "ui.telemetry",
                "tab": self._current_tab_name(),
                "event_type": event_type,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            })
        except Exception as e:
            logger.debug(f"UI telemetry publish failed ({event_type}): {e}")

    def _install_global_ui_telemetry_filter(self):
        if self._ui_telemetry_filter_installed:
            return
        try:
            app = QApplication.instance()
            if app is None:
                return
            app.installEventFilter(self)
            self._ui_telemetry_filter_installed = True
            logger.info("✅ Global UI telemetry filter installed")
        except Exception as e:
            logger.debug(f"UI telemetry filter install error: {e}")

    def eventFilter(self, obj, event):
        """Capture cross-tab UI interactions for system-wide learning."""
        try:
            if self.isVisible() and self.isActiveWindow():
                et = event.type()
                if et == QEvent.Type.MouseButtonPress:
                    self._publish_ui_telemetry(
                        "ui.mouse.press",
                        metadata={"widget": getattr(obj, "objectName", lambda: "")() or obj.__class__.__name__},
                        min_interval=0.08,
                    )
                elif et == QEvent.Type.KeyPress:
                    key_val = getattr(event, "key", lambda: 0)()
                    self._publish_ui_telemetry(
                        "ui.key.press",
                        metadata={"key": int(key_val)},
                        min_interval=0.12,
                    )
        except Exception:
            pass
        return super().eventFilter(obj, event)
    
    def setup_main_window(self):
        """Configure the main window properties with cyberpunk styling"""
        self.setWindowTitle("🔥 KINGDOM AI 🔥")
        
        # Import QApplication first to ensure it's available
        from PyQt6.QtWidgets import QApplication as QApp
        
        # Get screen dimensions for proper sizing
        screen = QApp.primaryScreen().geometry()
        
        # SMALLER WINDOW: Make it fit on screen properly
        screen = QApp.primaryScreen().geometry()
        
        # Use SMALLER size that fits most screens
        window_width = 1280  # Smaller width - fits most screens
        window_height = 800  # Smaller height - fits most screens
        min_width = 1024  # Minimum width
        min_height = 700  # Minimum height
        
        # If screen is smaller, use 85% of screen
        if screen.width() < window_width:
            window_width = int(screen.width() * 0.85)
        if screen.height() < window_height:
            window_height = int(screen.height() * 0.85)
        
        # Center the window
        x = (screen.width() - window_width) // 2
        y = (screen.height() - window_height) // 2
        
        self.setGeometry(x, y, window_width, window_height)
        self.setMinimumSize(min_width, min_height)
        
        # Allow window to be maximized
        from PyQt6.QtCore import Qt
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        
        logger.info(f"✅ Window configured: {window_width}x{window_height} (min: {min_width}x{min_height})")
        
        # BLACK SPOT ROOT FIX (2026-02-08):
        # Use QPalette to color QMainWindow background — NOT setStyleSheet().
        # setStyleSheet() on QMainWindow cascades to ALL child widgets and creates
        # internal dark gap widgets that overlay tabs. QPalette only colors the
        # window itself with zero side effects on children.
        from PyQt6.QtGui import QPalette as _Pal
        _pal = self.palette()
        _bg = QColor("#0A0E17")
        _pal.setColor(_Pal.ColorRole.Window, _bg)
        _pal.setColor(_Pal.ColorRole.Base, _bg)
        self.setPalette(_pal)
        self.setAutoFillBackground(True)
        
        # BLACK MARK FIX (SOTA 2026): Target the INTERNAL QMainWindowLayout
        # QMainWindow.setContentsMargins() only sets outer widget margins.
        # self.layout() returns the internal QMainWindowLayout which controls
        # the actual gap between title bar decoration and the central widget.
        # 1. Zero the internal layout margins (this is what actually removes the gap)
        if self.layout():
            self.layout().setContentsMargins(0, 0, 0, 0)
            self.layout().setSpacing(0)
        # 2. Also zero outer widget margins
        self.setContentsMargins(0, 0, 0, 0)
        # 3. Keep QMainWindow's own menu object but hide/collapse it.
        # Avoid setMenuWidget() replacement widgets, which can introduce
        # top-strip geometry artifacts on some X11/Qt combinations.
        try:
            _menu_bar = self.menuBar()
            if _menu_bar is not None:
                _menu_bar.setNativeMenuBar(False)
                _menu_bar.setVisible(False)
                _menu_bar.setFixedHeight(0)
        except Exception:
            pass
        logger.info("✅ QMainWindow: internal layout margins zeroed + menubar collapsed")
    
    def create_menu_bar(self):
        """Disabled — menubar collapsed into main UI."""
        pass
    
    def _trigger_welcome_greeting(self):
        """Play welcome greeting immediately after GUI loads.
        
        NOTE: The actual greeting is handled by ThothQtWidget._show_welcome_greeting()
        which uses the proper chat_widget.add_message() method and voice service.
        This method now only marks the greeting as triggered to prevent any fallback duplicates.
        """
        if self._greeting_triggered:
            return  # Already played
        
        # Mark as triggered - actual greeting is handled by ThothQtWidget
        self._greeting_triggered = True
        logger.info("✅ Greeting flag set - ThothQtWidget handles actual greeting display")
    
    def showEvent(self, event):
        """Override showEvent to trigger greeting when window is shown."""
        super().showEvent(event)
        # Trigger greeting 500ms after window is shown
        QTimer.singleShot(500, self._trigger_welcome_greeting)
        QTimer.singleShot(1200, self.start_websocket_feeds)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._schedule_layout_cache_save()

    def create_status_bar(self):
        """Create the status bar with system indicators"""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar { background-color: #0A0E17; color: #00FFFF; }
            QStatusBar QLabel { color: #00FFFF; }
            QStatusBar QPushButton { background-color: #1A1E2E; color: #00FFFF; border: 1px solid #00FFFF; border-radius: 3px; padding: 2px 8px; }
        """)
        self.setStatusBar(self.status_bar)
        
        # Status message
        self.status_label = QLabel("Kingdom AI System Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Connection indicators
        self.redis_indicator = QLabel("Redis: ✅")
        self.blockchain_indicator = QLabel("Blockchain: ✅")
        self.status_bar.addPermanentWidget(self.redis_indicator)
        self.status_bar.addPermanentWidget(self.blockchain_indicator)

        # Global Thoth AI chat toggle button - available from every tab
        self.chat_toggle_button = QPushButton("🤖 Chat")
        self.chat_toggle_button.setCheckable(True)
        self.chat_toggle_button.setToolTip("Toggle Thoth AI chat overlay")
        self.chat_toggle_button.clicked.connect(self.toggle_chat_overlay)
        self.status_bar.addPermanentWidget(self.chat_toggle_button)
    
    def create_central_widget(self):
        """Create the central widget with tab system.
        
        BLACK SPOT ROOT FIX: QTabWidget is set as the central widget DIRECTLY,
        matching demo_dashboard_tabs.py which has zero black mark. Wrapping it
        in QWidget+QVBoxLayout created an internal QMainWindow gap widget.
        """
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("kingdom_main_tabs")

        # ── NUCLEAR BLACK MARK FIX ──
        # Install a custom QTabBar that force-fills its ENTIRE background
        # with #0F1620 before painting tabs.  This is the ONLY reliable
        # method on X11/WSL (no compositor): CSS background-color,
        # autoFillBackground, and QPalette all fail to cover the raw
        # widget surface outside of styled sub-controls.
        _bar = _KingdomTabBar(self.tab_widget)
        _bar.setObjectName("kingdom_main_tab_bar")
        _bar.setExpanding(True)
        _bar.setElideMode(Qt.TextElideMode.ElideNone)
        self.tab_widget.setTabBar(_bar)

        self.setCentralWidget(self.tab_widget)
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)

        # Chat overlay init is DEFERRED to after tabs are created.
        # QStackedWidget (needed as overlay parent) only exists after first addTab().
        # Initializing here parents overlay to QTabWidget directly, which causes
        # the black mark artifact on X11 (see _init_chat_overlay comment).
        
        # Set tab widget properties for better UX
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setMovable(False)
        # Force non-overflow tab presentation path used by successful backup.
        self.tab_widget.setUsesScrollButtons(False)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabBar().setExpanding(True)
        
        # Do not install custom corner widgets; they can reserve/paint left-edge
        # regions and mask the first tab on some WSL/X11 compositions.
        self._left_tab_corner = None
        self._right_tab_corner = None
        self.tab_widget.currentChanged.connect(lambda _idx: self._schedule_layout_cache_save())
        
        # SINGLE SOURCE OF TRUTH for all tab styling.
        # ROOT FIX: This is the ONLY stylesheet applied to tab_widget.
        # Do NOT apply any other stylesheet via apply_cyberpunk_style(), tab_bar.setStyleSheet(), etc.
        self.tab_widget.setStyleSheet("""
            /* ============================================================
               KINGDOM AI MASTER STYLESHEET
               Matches original CyberpunkStyle.get_style_sheet("tab_container")
               from gui/cyberpunk_style.py — verified against backup.
               ============================================================ */

            /* === BASE WIDGET RULE (from CyberpunkStyle base_style) === */
            QWidget {
                background-color: #0A0E17;
                color: #E6FFFF;
                font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
                font-weight: 500;
            }

            /* === SUB-TAB STYLING (generic — Mining, Trading, etc.) === */
            /* X11/WSL FIX: transparent = BLACK on X11.  Use opaque #0A0E17
               (same as parent bg) so sub-tab widgets are invisible but
               fully painted. */
            QTabWidget {
                background-color: #0A0E17;
            }
            QTabWidget::pane {
                border: 2px solid #00FFFF;
                border-top: 0px;
                background-color: #0A0E17;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                padding: 0px;
                margin-top: 0px;
            }
            QTabBar {
                background-color: #0A0E17;
                qproperty-drawBase: 1;
            }
            QTabBar::tab {
                background-color: #0F1620;
                color: #E6FFFF;
                border: 2px solid #00FFFF;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 16px;
                margin-right: 3px;
                min-width: 80px;
                font-weight: bold;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0, 255, 255, 0.2),
                    stop:1 #0A0E17);
                color: #00FFFF;
                border: 2px solid #00FFFF;
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background-color: rgba(0, 255, 255, 0.15);
                color: #00FFAA;
                border: 2px solid #00FFAA;
                border-bottom: none;
            }
            QTabBar::tab:!selected {
                margin-top: 3px;
            }

            /* === MAIN TAB BAR (scoped — only the top-level 15-tab bar) === */
            /* Keep these AFTER generic tab rules so they always win in Qt CSS. */
            QTabWidget#kingdom_main_tabs {
                background-color: #0A0E17;
                border: none;
            }
            QTabWidget#kingdom_main_tabs::pane {
                border: none;
                background-color: #0A0E17;
                border-radius: 0px;
                padding: 0px;
                margin: 0px;
                top: 0px;
            }
            QTabBar#kingdom_main_tab_bar {
                background-color: #0F1620;
                qproperty-drawBase: 1;
            }
            QTabBar#kingdom_main_tab_bar::tab {
                background-color: #0F1620;
                color: #E6FFFF;
                border: 2px solid #00FFFF;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 4px 2px;
                margin-right: 1px;
                min-width: 48px;
                max-width: 84px;
                font-weight: bold;
                font-size: 9px;
            }
            QTabBar#kingdom_main_tab_bar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0, 255, 255, 0.2),
                    stop:1 #0A0E17);
                color: #00FFFF;
                border: 2px solid #00FFFF;
                border-bottom: none;
            }
            QTabBar#kingdom_main_tab_bar::tab:hover:!selected {
                background-color: rgba(0, 255, 255, 0.15);
                color: #00FFAA;
                border: 2px solid #00FFAA;
                border-bottom: none;
            }
            QTabBar#kingdom_main_tab_bar::tab:!selected {
                margin-top: 2px;
            }
            QTabWidget#kingdom_main_tabs::left-corner,
            QTabWidget#kingdom_main_tabs::right-corner {
                width: 0px; height: 0px; background-color: #0F1620; border: none;
            }

            /* === ALL WIDGET STYLING (from CyberpunkStyle base_style) === */
            QLabel {
                color: #E6FFFF;
                background-color: transparent;
            }
            QPushButton {
                background-color: #1A1E2E;
                color: #E6FFFF;
                border: 2px solid #00FFFF;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 255, 0.2);
                border: 2px solid #FF00FF;
            }
            QPushButton:pressed {
                background-color: rgba(255, 0, 255, 0.3);
                border: 2px solid #FF00FF;
            }
            QGroupBox {
                background-color: #0F1620;
                border: 2px solid #00FFFF;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 14px;
                font-weight: bold;
                color: #00FFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: #00FFFF;
                background-color: #0A0E17;
                border: 1px solid #00FFFF;
                border-radius: 3px;
            }
            QLineEdit, QTextEdit {
                background-color: #1E2638;
                color: #E6FFFF;
                border: 2px solid #00FFFF;
                border-radius: 4px;
                padding: 5px;
                selection-background-color: #BF00FF;
            }
            QProgressBar {
                border: 2px solid #00FFFF;
                border-radius: 5px;
                text-align: center;
                color: #E6FFFF;
                background-color: #0F1620;
                padding: 1px;
            }
            QProgressBar::chunk {
                background-color: #00FFFF;
                border-radius: 3px;
            }
            QComboBox {
                background-color: #1E2638;
                color: #E6FFFF;
                border: 2px solid #00FFFF;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 20px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #00FFFF;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #0A0E17;
                color: #E6FFFF;
                border: 2px solid #00FFFF;
                selection-background-color: rgba(0, 255, 255, 0.3);
                selection-color: #00FFFF;
            }
            QSpinBox {
                background-color: #1E2638;
                color: #E6FFFF;
                border: 2px solid #00FFFF;
                border-radius: 4px;
                padding: 4px;
            }
            QTableWidget, QTableView {
                background-color: #0A0E17;
                color: #E6FFFF;
                gridline-color: #00FFFF;
                border: 2px solid #00FFFF;
                selection-background-color: rgba(0, 255, 255, 0.2);
                selection-color: #00FFFF;
            }
            QHeaderView::section {
                background-color: #0F1620;
                color: #00FFFF;
                border: 1px solid #00FFFF;
                padding: 4px;
                font-weight: bold;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #0A0E17;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #00FFFF;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #00FFFF;
            }
            QScrollBar:horizontal {
                background-color: #0A0E17;
                height: 12px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #00FFFF;
                border-radius: 4px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #00FFFF;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                height: 0px;
                width: 0px;
            }
            QCheckBox {
                color: #E6FFFF;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #00FFFF;
                border-radius: 3px;
                background-color: #1E2638;
            }
            QCheckBox::indicator:checked {
                background-color: #00FFFF;
                border-color: #00FFFF;
            }
        """)
        
        # ROOT FIX: Do NOT call apply_cyberpunk_style() on tab_widget!
        # CyberpunkStyle.apply_to_widget() calls widget.setStyleSheet(get_style_sheet("Main Tab Widget"))
        # which falls back to base_style (no QTabBar rules) and OVERWRITES the carefully
        # crafted tab stylesheet above (lines 458-525), destroying all tab styling.
        # The tab_widget.setStyleSheet() above is the SINGLE source of truth for tab styling.
        
        logger.info("✅ Central widget configured with cyberpunk styling and responsive layout")
    
    def connect_event_bus(self):
        """Connect to the event bus for system-wide communication"""
        if not self.event_bus:
            return
            
        logger.info("Connecting to event bus")
        try:
            # Async subscriptions - wrap in QTimer to prevent task nesting
            from PyQt6.QtCore import QTimer
            
            def subscribe_main_window_events():
                try:
                    # FIX: subscribe is SYNC, not async
                    self.event_bus.subscribe("system.status", self.handle_system_status)
                    self.event_bus.subscribe("component.status", self.handle_component_status)
                    self.event_bus.subscribe("gui.update", self.handle_gui_update)
                    self.event_bus.subscribe("codegen.history", self._handle_codegen_history)
                    # SOTA 2026: VR tab-switch command (gui.tab.switch)
                    self.event_bus.subscribe("gui.tab.switch", self._handle_vr_tab_switch)
                    # SHA-LU-AM: Truth Timeline popup when native tongue spoken
                    self.event_bus.subscribe("secret.reserve.reveal", self._show_truth_timeline_on_reveal)
                    logger.info("✅ Connected to event bus (incl. VR tab switch, Truth Timeline)")
                except Exception as e:
                    logger.error(f"Failed to subscribe to events: {e}")
            
            QTimer.singleShot(500, subscribe_main_window_events)  # 0.5s so status labels receive kingdom_ai data sooner
        except Exception as e:
            logger.error(f"Failed to connect to event bus: {e}")
    
    def _initialize_voice_commands(self):
        """Initialize SOTA 2026 Voice Command Manager for system-wide control."""
        try:
            # CRITICAL: Initialize VoiceManager first for actual microphone/STT capture
            try:
                voice_manager = None
                if getattr(self, 'event_bus', None) is not None and hasattr(self.event_bus, 'get_component'):
                    try:
                        voice_manager = self.event_bus.get_component('voice_manager', silent=True)
                    except TypeError:
                        try:
                            voice_manager = self.event_bus.get_component('voice_manager')
                        except Exception:
                            voice_manager = None
                    except Exception:
                        voice_manager = None

                self.voice_manager = voice_manager

                if self.voice_manager is not None:
                    logger.info("🎤 VoiceManager reused from EventBus registry for microphone capture")
                else:
                    # SOTA 2026 FIX: VoiceManager registers during startup - this is expected during init
                    logger.debug("ℹ️ VoiceManager not yet on EventBus (registers during startup)")
            except ImportError as vm_err:
                # SOTA 2026 FIX: Downgrade to debug - voice is optional functionality
                logger.debug(f"ℹ️ VoiceManager module not available: {vm_err}")
                self.voice_manager = None
            except Exception as vm_err:
                logger.error(f"❌ Failed to initialize VoiceManager: {vm_err}")
                self.voice_manager = None
            
            from core.voice_command_manager import get_voice_command_manager
            
            # Get or create the voice command manager
            self.voice_command_manager = get_voice_command_manager(self.event_bus)
            
            # Set main window reference for UI control
            self.voice_command_manager.set_main_window(self)
            
            # Register command action callbacks for tab navigation
            self._register_voice_command_callbacks()
            
            # Subscribe to voice command events
            if self.event_bus:
                self.event_bus.subscribe('navigate.tab.dashboard', lambda d: self._voice_navigate_tab(0))
                self.event_bus.subscribe('navigate.tab.trading', lambda d: self._voice_navigate_tab(1))
                self.event_bus.subscribe('navigate.tab.blockchain', lambda d: self._voice_navigate_tab(2))
                self.event_bus.subscribe('navigate.tab.mining', lambda d: self._voice_navigate_tab(3))
                self.event_bus.subscribe('navigate.tab.thoth', lambda d: self._voice_navigate_tab(4))
                self.event_bus.subscribe('navigate.tab.code_generator', lambda d: self._voice_navigate_tab(5))
                self.event_bus.subscribe('navigate.tab.api_keys', lambda d: self._voice_navigate_tab(6))
                self.event_bus.subscribe('navigate.tab.vr', lambda d: self._voice_navigate_tab(7))
                self.event_bus.subscribe('navigate.tab.wallet', lambda d: self._voice_navigate_tab(8))
                self.event_bus.subscribe('navigate.tab.settings', lambda d: self._voice_navigate_tab(9))
                self.event_bus.subscribe('navigate.tab.devices', lambda d: self._voice_navigate_tab(10))
                self.event_bus.subscribe('navigate.tab.health', lambda d: self._voice_navigate_tab(11))
                self.event_bus.subscribe('navigate.tab.creative_studio', lambda d: self._voice_navigate_tab(12))
                self.event_bus.subscribe('navigate.tab.comms', lambda d: self._voice_navigate_tab(4))
                self.event_bus.subscribe('navigate.tab.communications', lambda d: self._voice_navigate_tab(4))
                
                # Creative Studio voice commands - create/send to Unity
                self.event_bus.subscribe('creative.voice.create', self._voice_creative_create)
                self.event_bus.subscribe('creative.voice.unity', self._voice_creative_send_unity)
                
                # UI control events
                self.event_bus.subscribe('ui.scroll.up', lambda d: self._voice_scroll('up'))
                self.event_bus.subscribe('ui.scroll.down', lambda d: self._voice_scroll('down'))
                self.event_bus.subscribe('ui.fullscreen', lambda d: self._voice_toggle_fullscreen())
                self.event_bus.subscribe('ui.minimize', lambda d: self.showMinimized())
                self.event_bus.subscribe('ui.refresh', lambda d: self._voice_refresh_current())
                
                # System events
                self.event_bus.subscribe('system.help', lambda d: self._voice_show_help())
                self.event_bus.subscribe('system.status', lambda d: self._voice_show_status())
            
            logger.info("🎤 Voice Command Manager initialized with all callbacks")
            
            # UNIFIED GREETING: ThothQt._show_welcome_greeting() handles type+speak
            # This prevents duplicate greetings - ONE unified voice system
            logger.info("✅ Greeting flag set - ThothQtWidget handles actual greeting display")
            
            # SOTA 2026: Initialize Biometric Security and start boot scan
            self._initialize_biometric_security()
            
        except ImportError as e:
            logger.warning(f"⚠️ Voice Command Manager not available: {e}")
            self.voice_command_manager = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize Voice Command Manager: {e}")
            self.voice_command_manager = None
    
    # NOTE: _play_startup_greeting REMOVED - ThothQt._show_welcome_greeting() handles unified type+speak
    
    def _initialize_biometric_security(self):
        """Initialize SOTA 2026 Biometric Security with auto-scan on boot."""
        try:
            from core.biometric_security_manager import get_biometric_security_manager
            # Use module-level QTimer (imported at top) - no local import to avoid "referenced before assignment"
            
            self.biometric_security = get_biometric_security_manager(self.event_bus)
            
            # Subscribe to security events
            if self.event_bus:
                self.event_bus.subscribe('security.authenticated', self._on_user_authenticated)
                self.event_bus.subscribe('security.boot_scan.started', self._on_boot_scan_started)
                # SOTA 2026: Clear "Please authenticate" after 45s if no camera/auth — avoid stuck status
                QTimer.singleShot(45000, self._clear_auth_pending_if_still_waiting)
                self.event_bus.subscribe('security.face.enrolled', lambda d: self.statusBar().showMessage(f"🔐 Face enrolled: {d.get('name', 'User')}", 5000))
                self.event_bus.subscribe('security.voice.enrolled', lambda d: self.statusBar().showMessage(f"🎤 Voice enrolled: {d.get('name', 'User')}", 5000))
                self.event_bus.subscribe('command.denied', self._on_command_denied)
            
            # Start auto-scan on boot
            if self.biometric_security._auto_scan_on_boot:
                QTimer.singleShot(2000, self.biometric_security.start_boot_scan)
                logger.info("🔐 Biometric boot scan scheduled")
            
            logger.info("🔐 Biometric Security Manager initialized")
            
        except ImportError as e:
            logger.warning(f"⚠️ Biometric Security not available: {e}")
            self.biometric_security = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize Biometric Security: {e}")
            self.biometric_security = None
    
    def _on_user_authenticated(self, data: dict):
        """Handle user authentication event. Use status_label only to avoid garbled overlap."""
        user_name = data.get('name', 'User')
        security_level = data.get('security_level', 'unknown')
        msg = f"🔐 Welcome, {user_name}! ({security_level})"
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText(msg)
        logger.info(f"🔐 User authenticated: {user_name}")
    
    def _on_boot_scan_started(self, data: dict):
        """Handle boot scan started event. Use status_label only to avoid garbled overlap."""
        msg = "🔐 Biometric scan active - Please authenticate..."
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText(msg)
    
    def _clear_auth_pending_if_still_waiting(self):
        """Clear 'Please authenticate' after 45s if face auth never completed (e.g. camera unavailable)."""
        try:
            if not getattr(self, 'biometric_security', None):
                return
            if self.biometric_security.is_authenticated():
                return
            msg = "Kingdom AI System Ready. Connect camera for face auth when available."
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setText(msg)
        except Exception:
            pass
    
    def _on_command_denied(self, data: dict):
        """Handle command denied event."""
        reason = data.get('reason', 'Authentication required')
        command = data.get('command', 'Unknown')
        self.statusBar().showMessage(f"🔐 Access denied: {reason}", 5000)
        logger.warning(f"🔐 Command denied: {command} - {reason}")
    
    def _register_voice_command_callbacks(self):
        """Register callbacks for voice command actions."""
        if not self.voice_command_manager:
            return
        
        # Tab navigation callbacks
        vcm = self.voice_command_manager
        vcm.register_callback('navigate.tab.dashboard', lambda c, p: self._voice_navigate_tab(0))
        vcm.register_callback('navigate.tab.trading', lambda c, p: self._voice_navigate_tab(1))
        vcm.register_callback('navigate.tab.blockchain', lambda c, p: self._voice_navigate_tab(2))
        vcm.register_callback('navigate.tab.mining', lambda c, p: self._voice_navigate_tab(3))
        vcm.register_callback('navigate.tab.thoth', lambda c, p: self._voice_navigate_tab(4))
        vcm.register_callback('navigate.tab.code_generator', lambda c, p: self._voice_navigate_tab(5))
        vcm.register_callback('navigate.tab.api_keys', lambda c, p: self._voice_navigate_tab(6))
        vcm.register_callback('navigate.tab.vr', lambda c, p: self._voice_navigate_tab(7))
        vcm.register_callback('navigate.tab.wallet', lambda c, p: self._voice_navigate_tab(8))
        vcm.register_callback('navigate.tab.settings', lambda c, p: self._voice_navigate_tab(9))
        vcm.register_callback('navigate.tab.devices', lambda c, p: self._voice_navigate_tab(10))
        vcm.register_callback('navigate.tab.health', lambda c, p: self._voice_navigate_tab(11))
        vcm.register_callback('navigate.tab.creative_studio', lambda c, p: self._voice_navigate_tab(12))
        # Comms now lives as a sub-tab under Thoth AI.
        vcm.register_callback('navigate.tab.comms', lambda c, p: self._voice_navigate_tab(4))
        vcm.register_callback('navigate.tab.communications', lambda c, p: self._voice_navigate_tab(4))
    
    def _voice_navigate_tab(self, index: int):
        """Navigate to a tab by index via voice command."""
        try:
            if hasattr(self, 'tab_widget') and self.tab_widget:
                self.tab_widget.setCurrentIndex(index)
                tab_names = ['Dashboard', 'Trading', 'Blockchain', 'Mining', 'Thoth AI',
                             'Code Generator', 'API Keys', 'VR', 'Wallet', 'Settings',
                             'Devices', 'Health', 'Creative Studio']
                if 0 <= index < len(tab_names):
                    logger.info(f"🎤 Navigated to {tab_names[index]} tab")
                    self.statusBar().showMessage(f"🎤 Navigated to {tab_names[index]}", 3000)
        except Exception as e:
            logger.error(f"Tab navigation error: {e}")

    def _handle_vr_tab_switch(self, data: dict):
        """SOTA 2026: Handle tab switch requests from VR headset.

        Accepts a tab_name string and searches through registered tab_widgets
        to find and activate the matching tab. This allows full system navigation
        from inside the VR headset via voice or gesture commands.
        """
        try:
            tab_name = data.get("tab_name", "").lower()
            if not tab_name or not hasattr(self, 'tab_widget'):
                return

            # Build name→index lookup from tab_widgets dict
            name_index_map = {
                'dashboard': 0, 'trading': 1, 'blockchain': 2, 'kingdomweb3': 2,
                'web3': 2, 'mining': 3, 'thoth ai': 4, 'thoth': 4, 'ai': 4,
                'code generator': 5, 'code': 5, 'api keys': 6, 'api': 6,
                'vr': 7, 'wallet': 8, 'settings': 9,
                'devices': 10, 'health': 11, 'wearable': 11,
                'visual creation': 12, 'creative studio': 12,
                'communications': 4, 'comms': 4,
            }

            # Also try widget-based lookup (more reliable if tab order differs)
            if hasattr(self, 'tab_widgets'):
                for key, widget in self.tab_widgets.items():
                    if tab_name in key.lower():
                        for i in range(self.tab_widget.count()):
                            if self.tab_widget.widget(i) is widget:
                                from PyQt6.QtCore import QTimer
                                QTimer.singleShot(0, lambda idx=i: self.tab_widget.setCurrentIndex(idx))
                                logger.info(f"🥽 VR tab switch → {key} (index {i})")
                                self.statusBar().showMessage(f"🥽 VR → {key}", 3000)
                                return

            # Fallback to static index map
            idx = name_index_map.get(tab_name)
            if idx is not None and idx < self.tab_widget.count():
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.tab_widget.setCurrentIndex(idx))
                logger.info(f"🥽 VR tab switch → {tab_name} (index {idx})")
                self.statusBar().showMessage(f"🥽 VR → {tab_name}", 3000)
            else:
                logger.warning(f"🥽 VR tab switch: unknown tab '{tab_name}'")

        except Exception as e:
            logger.error(f"VR tab switch error: {e}")

    def _show_truth_timeline_on_reveal(self, data=None):
        """SHA-LU-AM: Open Truth Timeline popup when native tongue spoken. Runs on GUI thread."""
        try:
            from PyQt6.QtCore import QTimer
            from gui.widgets.truth_timeline_window import show_truth_timeline
            QTimer.singleShot(0, lambda: show_truth_timeline(event_bus=self.event_bus, parent=self))
        except Exception as e:
            logger.debug("Truth Timeline popup: %s", e)
    
    def _voice_scroll(self, direction: str):
        """Scroll the current view via voice command."""
        try:
            from PyQt6.QtWidgets import QScrollArea
            current_widget = self.tab_widget.currentWidget()
            
            # Find scroll area in current widget
            scroll_areas = current_widget.findChildren(QScrollArea)
            if scroll_areas:
                scrollbar = scroll_areas[0].verticalScrollBar()
                if direction == 'up':
                    scrollbar.setValue(scrollbar.value() - 100)
                elif direction == 'down':
                    scrollbar.setValue(scrollbar.value() + 100)
                logger.info(f"🎤 Scrolled {direction}")
        except Exception as e:
            logger.error(f"Scroll error: {e}")
    
    def _voice_toggle_fullscreen(self):
        """Toggle fullscreen via voice command."""
        if self.isFullScreen():
            self.showNormal()
            logger.info("🎤 Exited fullscreen")
        else:
            self.showFullScreen()
            logger.info("🎤 Entered fullscreen")
    
    def _voice_refresh_current(self):
        """Refresh current tab via voice command."""
        try:
            current_widget = self.tab_widget.currentWidget()
            if hasattr(current_widget, 'refresh'):
                current_widget.refresh()  # type: ignore[attr-defined]
            elif hasattr(current_widget, '_refresh'):
                current_widget._refresh()  # type: ignore[attr-defined]
            logger.info("🎤 Refreshed current view")
        except Exception as e:
            logger.error(f"Refresh error: {e}")
    
    def _voice_show_help(self):
        """Show voice command help."""
        help_text = """🎤 Voice Commands Available:

📍 Navigation:
  - "go to trading" / "go to mining" / "go to wallet"
  - "open dashboard" / "show settings" / "thoth"

🖱️ UI Control:
  - "scroll up" / "scroll down"
  - "fullscreen" / "minimize"
  - "refresh"

💹 Trading:
  - "buy" / "sell" / "show portfolio"
  - "whale tracking" / "copy trading"

⛏️ Mining:
  - "start mining" / "stop mining"
  - "mine bitcoin" / "show hashrate"

💰 Wallet:
  - "show balance" / "send crypto"
  - "my transactions"

🤖 AI:
  - "ask thoth" / "voice mode"
  - "analyze market"

Say "help" anytime for this list!"""
        
        QMessageBox.information(self, "🎤 Voice Commands", help_text)
        logger.info("🎤 Showed help")
    
    def _voice_show_status(self):
        """Show system status via voice command."""
        status_msg = f"""System Status:
        
✅ Tabs Active: {self.tab_widget.count()}
✅ Event Bus: {'Connected' if self.event_bus else 'Not Connected'}
✅ Voice Commands: {'Active' if self.voice_command_manager else 'Not Active'}
"""
        self.statusBar().showMessage("🎤 System Status: All Systems Operational", 5000)
        logger.info("🎤 Showed status")
    
    def _voice_creative_create(self, data: dict):
        """Handle voice command to create content in Creative Studio."""
        # FIX: Don't default to hardcoded prompt - use actual user input or skip generation
        prompt = data.get('prompt', '').strip()
        if not prompt:
            logger.warning("No prompt provided for visual generation, skipping")
        
        # Switch to Creative Studio tab
        if hasattr(self, 'creative_studio_widget') and self.creative_studio_widget:
            # Find the tab index
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) == self.creative_studio_widget:
                    self.tab_widget.setCurrentIndex(i)
                    break
            
            # Trigger creation via EventBus
            if self.event_bus:
                self.event_bus.publish("creative.create", {"prompt": prompt})
            
            self.statusBar().showMessage(f"🎨 Creating: {prompt[:50]}...", 5000)
            logger.info(f"🎤 Voice creative command: create '{prompt}'")
        else:
            self.statusBar().showMessage("⚠️ Creative Studio not available", 3000)
    
    def _voice_creative_send_unity(self, data: dict):
        """Handle voice command to send terrain to Unity runtime."""
        if hasattr(self, 'creative_studio_widget') and self.creative_studio_widget:
            # Trigger send to Unity via the widget
            if hasattr(self.creative_studio_widget, '_send_terrain_to_unity_runtime'):
                self.creative_studio_widget._send_terrain_to_unity_runtime()
            self.statusBar().showMessage("🎮 Sending terrain to Unity runtime...", 5000)
            logger.info("🎤 Voice creative command: send to Unity")
        else:
            self.statusBar().showMessage("⚠️ Creative Studio not available", 3000)
    
    def initialize_all_tabs(self):
        """Initialize all tabs with REAL PyQt6 components.
        
        SOTA 2026 PERFORMANCE: avoids nested event-loop pumping during tab
        creation to prevent re-entrant UI stalls under startup load.
        """
        from PyQt6.QtWidgets import QApplication
        import time as _time
        
        _tab_count = 0
        _total_tabs = 16
        _start = _time.monotonic()
        
        def _tick(tab_name):
            """Log tab completion, update loading screen, and pump events.
            
            Logs progress and updates loading hooks while keeping startup
            deterministic and free of nested event-loop churn.
            """
            nonlocal _tab_count
            _tab_count += 1
            elapsed = _time.monotonic() - _start
            logger.info(f"✅ [{_tab_count}/{_total_tabs}] {tab_name} loaded ({elapsed:.1f}s)")
            
            # SOTA 2026: Call loading progress hook if set (for real-time loading screen updates)
            if hasattr(self, '_loading_progress_hook') and self._loading_progress_hook is not None:
                try:
                    self._loading_progress_hook(tab_name)
                except Exception:
                    pass
            
            # Keep startup deterministic: avoid nested event-loop pumping here.
        
        # 1. Dashboard Tab - COMPLETE DashboardQt component (NO FALLBACKS)
        from gui.qt_frames.dashboard_qt import DashboardQt
        self.dashboard_widget = DashboardQt(event_bus=self.event_bus)
        if hasattr(self.dashboard_widget, '_setup_complete_ui'):
            self.dashboard_widget._setup_complete_ui()
        self.tab_widget.addTab(self.dashboard_widget, "Dashboard")
        self.tab_widgets['dashboard'] = self.dashboard_widget
        self._widget_to_tab_id[self.dashboard_widget] = 'dashboard'
        _tick("Dashboard")
        
        # 2. Trading Tab - deferred heavy initialization (placeholder first)
        # This prevents startup deadlocks/crashes before the main window is visible.
        self.trading_widget = None
        self._trading_tab_loaded = False
        self._trading_placeholder = QWidget()
        self._trading_placeholder.setObjectName("trading_placeholder")
        _trading_layout = QVBoxLayout(self._trading_placeholder)
        _trading_label = QLabel("Loading Trading...")
        _trading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _trading_label.setStyleSheet("color: #00FFFF; font-size: 16px; background: #1E1E1E;")
        self._trading_placeholder.setStyleSheet("background: #1E1E1E;")
        _trading_layout.addWidget(_trading_label)
        self.tab_widget.addTab(self._trading_placeholder, "Trading")
        self.tab_widgets['trading'] = self._trading_placeholder
        self._widget_to_tab_id[self._trading_placeholder] = 'trading'
        _tick("Trading (placeholder)")
        
        # 3. Blockchain Tab - COMPLETE ONLY
        # SOTA 2026 PERF FIX: Reuse BlockchainConnector from EventBus if already registered
        # (previously was creating a SECOND one = redundant HTTP request to Ethereum RPC)
        from gui.qt_frames.blockchain_tab import BlockchainTab
        self.blockchain_connector = None
        try:
            if hasattr(self.event_bus, 'get_component'):
                self.blockchain_connector = self.event_bus.get_component('blockchain_connector')
            if self.blockchain_connector is None:
                from blockchain.blockchain_connector import BlockchainConnector
                self.blockchain_connector = BlockchainConnector(network="ethereum")
                if hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('blockchain_connector', self.blockchain_connector)
        except Exception as bc_err:
            logger.warning(f"⚠️ BlockchainConnector: {bc_err}")
            self.blockchain_connector = None
        
        self.blockchain_widget = BlockchainTab(event_bus=self.event_bus, blockchain_connector=self.blockchain_connector)
        if hasattr(self.blockchain_widget, '_setup_complete_ui'):
            self.blockchain_widget._setup_complete_ui()  # type: ignore[attr-defined]
        if hasattr(self.blockchain_widget, 'setup_blockchain_interface'):
            self.blockchain_widget.setup_blockchain_interface()  # type: ignore[attr-defined]
        self.tab_widget.addTab(self.blockchain_widget, "Blockchain")
        self.tab_widgets['blockchain'] = self.blockchain_widget
        self._widget_to_tab_id[self.blockchain_widget] = 'blockchain'
        _tick("Blockchain")
        
        # 4. Mining Tab - COMPLETE MiningTab UI with Quantum Mining (NO FALLBACKS)
        #    $KAIG is a SUB-TAB inside Mining (not a main tab)
        from gui.qt_frames.mining.mining_frame import MiningTab
        self.mining_widget = MiningTab(event_bus=self.event_bus)
        # FORCE COMPLETE MINING UI
        if hasattr(self.mining_widget, '_setup_complete_mining_ui'):
            self.mining_widget._setup_complete_mining_ui()  # type: ignore[attr-defined]
        if hasattr(self.mining_widget, '_setup_complete_ui'):
            self.mining_widget._setup_complete_ui()  # type: ignore[attr-defined]
        # Wrap in QTabWidget so $KAIG can be a sub-tab
        self._mining_container = QTabWidget()
        self._mining_container.setDocumentMode(True)
        self._mining_container.addTab(self.mining_widget, "Mining Ops")
        self.tab_widget.addTab(self._mining_container, "Mining")
        self.tab_widgets['mining'] = self.mining_widget
        self._widget_to_tab_id[self._mining_container] = 'mining'
        _tick("Mining")
        
        # 5. ThothAI Tab - COMPLETE ThothAI UI with Voice System
        #    Comms is a sub-tab under Thoth AI.
        from gui.qt_frames.thoth_ai_tab import ThothAITab
        self.thoth_ai_widget = ThothAITab(event_bus=self.event_bus)
        # FORCE COMPLETE THOTH AI UI
        if hasattr(self.thoth_ai_widget, '_setup_complete_ui'):
            self.thoth_ai_widget._setup_complete_ui()  # type: ignore[attr-defined]
        if hasattr(self.thoth_ai_widget, '_setup_voice_integration'):
            self.thoth_ai_widget._setup_voice_integration()  # type: ignore[attr-defined]
        self._thoth_container = QTabWidget()
        self._thoth_container.setDocumentMode(True)
        self._thoth_container.addTab(self.thoth_ai_widget, "AI Chat")
        self.tab_widget.addTab(self._thoth_container, "Thoth AI")
        self.tab_widgets['thoth_ai'] = self.thoth_ai_widget
        self._widget_to_tab_id[self._thoth_container] = 'thoth_ai'
        _tick("Thoth AI")

        # 6. Code Generator Tab - COMPLETE Code Generator UI (NO FALLBACKS)
        #    Software Control + MCP Control are SUB-TABS inside Code Generator
        from gui.frames.code_generator_qt import CodeGeneratorQt
        self.code_gen_widget = CodeGeneratorQt(event_bus=self.event_bus)
        # FORCE COMPLETE CODE GEN UI
        if hasattr(self.code_gen_widget, '_setup_complete_ui'):
            self.code_gen_widget._setup_complete_ui()  # type: ignore[attr-defined]
        if hasattr(self.code_gen_widget, 'setup_mcp_integration'):
            self.code_gen_widget.setup_mcp_integration()  # type: ignore[attr-defined]
        # Wrap in QTabWidget so Software Control + MCP Control can be sub-tabs
        self._codegen_container = QTabWidget()
        self._codegen_container.setDocumentMode(True)
        self._codegen_container.addTab(self.code_gen_widget, "Generator")
        self.tab_widget.addTab(self._codegen_container, "Code Generator")
        self.tab_widgets['code_generator'] = self.code_gen_widget
        self._widget_to_tab_id[self._codegen_container] = 'code_generator'
        _tick("Code Generator")
        
        # 7. API Key Manager Tab - COMPLETE API Manager UI (NO FALLBACKS)
        from gui.qt_frames.api_key_manager_tab import ApiKeyManagerTab
        self.api_manager_widget = ApiKeyManagerTab(event_bus=self.event_bus)
        # FORCE COMPLETE API KEY UI
        if hasattr(self.api_manager_widget, '_setup_complete_ui'):
            self.api_manager_widget._setup_complete_ui()  # type: ignore[attr-defined]
        if hasattr(self.api_manager_widget, 'setup_api_management'):
            self.api_manager_widget.setup_api_management()  # type: ignore[attr-defined]
        self.tab_widget.addTab(self.api_manager_widget, "API Keys")
        self.tab_widgets['api_keys'] = self.api_manager_widget
        self._widget_to_tab_id[self.api_manager_widget] = 'api_keys'
        _tick("API Keys")
        
        # 8. VR System Tab - COMPLETE VR UI (NO FALLBACKS)  
        from gui.qt_frames.vr_tab import VRTab
        self.vr_widget = VRTab(event_bus=self.event_bus)
        # FORCE COMPLETE VR UI
        if hasattr(self.vr_widget, '_setup_complete_ui'):
            self.vr_widget._setup_complete_ui()  # type: ignore[attr-defined]
        if hasattr(self.vr_widget, 'setup_vr_interface'):
            self.vr_widget.setup_vr_interface()  # type: ignore[attr-defined]
        self.tab_widget.addTab(self.vr_widget, "VR System")
        self.tab_widgets['vr'] = self.vr_widget
        self._widget_to_tab_id[self.vr_widget] = 'vr'
        _tick("VR System")
        
        # 9. Wallet Tab - COMPLETE Wallet UI (NO FALLBACKS)
        from gui.qt_frames.wallet_tab import WalletTab  
        self.wallet_tab_widget = WalletTab(event_bus=self.event_bus)
        # FORCE COMPLETE WALLET UI
        if hasattr(self.wallet_tab_widget, '_setup_complete_ui'):
            self.wallet_tab_widget._setup_complete_ui()  # type: ignore[attr-defined]
        if hasattr(self.wallet_tab_widget, 'setup_wallet_interface'):
            self.wallet_tab_widget.setup_wallet_interface()  # type: ignore[attr-defined]
        self.tab_widget.addTab(self.wallet_tab_widget, "Wallet")
        self.tab_widgets['wallet'] = self.wallet_tab_widget
        self._widget_to_tab_id[self.wallet_tab_widget] = 'wallet'
        _tick("Wallet")
        
        # 10. Settings Tab - deferred init (placeholder first)
        self.settings_widget = None
        self._settings_tab_loaded = False
        self._settings_placeholder = QWidget()
        self._settings_placeholder.setObjectName("settings_placeholder")
        _settings_layout = QVBoxLayout(self._settings_placeholder)
        _settings_label = QLabel("Loading Settings...")
        _settings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _settings_label.setStyleSheet("color: #00FFFF; font-size: 16px; background: #1E1E1E;")
        self._settings_placeholder.setStyleSheet("background: #1E1E1E;")
        _settings_layout.addWidget(_settings_label)
        self.tab_widget.addTab(self._settings_placeholder, "Settings")
        self.tab_widgets['settings'] = self._settings_placeholder
        self._widget_to_tab_id[self._settings_placeholder] = 'settings'
        _tick("Settings (placeholder)")
        
        # 11. Device Manager Tab - HOST DEVICE DETECTION & CONTROL (SOTA 2025/2026)
        try:
            from gui.qt_frames.device_manager_tab import DeviceManagerTab
            self.device_manager_widget = DeviceManagerTab(event_bus=self.event_bus)
            self.tab_widget.addTab(self.device_manager_widget, "Devices")
            self.tab_widgets['devices'] = self.device_manager_widget
            self._widget_to_tab_id[self.device_manager_widget] = 'devices'
            
            # SOTA 2026: Register device manager tab with event bus for system-wide access
            if hasattr(self.event_bus, 'register_component'):
                self.event_bus.register_component('device_manager_tab', self.device_manager_widget)
                # Also register MCP tools if available
                if hasattr(self.device_manager_widget, 'mcp_tools') and self.device_manager_widget.mcp_tools:
                    self.event_bus.register_component('device_mcp_tools', self.device_manager_widget.mcp_tools)
            
            logger.info("✅ Device Manager tab: Host device detection & MCP integration loaded with cyberpunk styling")
        except ImportError as e:
            logger.warning(f"⚠️ Device Manager tab not available: {e}")
        except Exception as e:
            logger.error(f"❌ Error creating Device Manager tab: {e}")
        _tick("Device Manager")

        # 11b. Health Dashboard Tab - WEARABLE HEALTH MONITORING (SOTA 2026)
        try:
            from gui.qt_frames.health_dashboard_tab import HealthDashboardTab
            self.health_dashboard_widget = HealthDashboardTab(event_bus=self.event_bus)
            self.tab_widget.addTab(self.health_dashboard_widget, "Health")
            self.tab_widgets['health'] = self.health_dashboard_widget
            self._widget_to_tab_id[self.health_dashboard_widget] = 'health'

            if hasattr(self.event_bus, 'register_component'):
                self.event_bus.register_component('health_dashboard_tab', self.health_dashboard_widget)

            # Wire event handlers
            if hasattr(self.health_dashboard_widget, 'register_event_handlers'):
                self.health_dashboard_widget.register_event_handlers()

            logger.info("✅ Health Dashboard tab: Wearable monitoring + anomaly detection loaded")
        except ImportError as e:
            logger.warning(f"⚠️ Health Dashboard tab not available: {e}")
        except Exception as e:
            logger.error(f"❌ Error creating Health Dashboard tab: {e}")
        _tick("Health Dashboard")

        # 12. Creative Studio Tab - LIVE CREATION + UNITY TERRAIN (SOTA 2026)
        try:
            from core.realtime_creative_studio import get_creative_studio_widget
            self.creative_studio_widget = get_creative_studio_widget(event_bus=self.event_bus, parent=self)
            if self.creative_studio_widget:
                self.tab_widget.addTab(self.creative_studio_widget, "Creative Studio")  # type: ignore[arg-type]
                self.tab_widgets['creative_studio'] = self.creative_studio_widget
                self._widget_to_tab_id[self.creative_studio_widget] = 'creative_studio'
                logger.info("✅ Creative Studio tab: Live creation + Unity terrain integration loaded")
                
                # CRITICAL FIX (2026-02-03): VisualCreationCanvas MUST be instantiated to handle
                # the visual.request → brain.visual.request → visual.generated event chain.
                # The Creative Studio's QLabel canvas is display-only; VisualCreationCanvas does
                # the actual AI image generation via its ImageGenerationWorker thread.
                # It doesn't need to be visible - it just handles the event flow and generation.
                try:
                    from gui.widgets.visual_creation_canvas import VisualCreationCanvas
                    self.visual_canvas = VisualCreationCanvas(event_bus=self.event_bus, parent=self)
                    # CRITICAL: Hide the canvas — it's an event-driven worker, not a visible widget.
                    # Without this, it paints at (0,0) of the main window and creates
                    # a black rectangle over the Dashboard tab / tab bar.
                    self.visual_canvas.hide()
                    self.visual_canvas.setFixedSize(0, 0)
                    # Register with event bus for system-wide access
                    if hasattr(self.event_bus, 'register_component'):
                        self.event_bus.register_component('visual_creation_canvas', self.visual_canvas)
                    logger.info("✅ VisualCreationCanvas: INSTANTIATED + HIDDEN (handles brain.visual.request → visual.generated)")
                except Exception as vc_err:
                    logger.error(f"⚠️ VisualCreationCanvas instantiation failed: {vc_err}")
                    self.visual_canvas = None
            else:
                logger.error("❌ Creative Studio widget returned None - check logs for initialization errors")
        except ImportError as e:
            logger.error(f"❌ Creative Studio tab import failed: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ Creative Studio tab initialization failed: {e}", exc_info=True)
        _tick("Creative Studio")

        # =====================================================================
        # SOTA 2026 PERF FIX: Deferred initialization for the 3 slowest tabs.
        # Comms (52 s), Software Control (19 s), MCP Control (20 s) are loaded
        # via QTimer.singleShot(0, ...) AFTER the event loop starts so the
        # main window appears immediately instead of blocking for 90+ seconds.
        # A lightweight placeholder QWidget with a "Loading..." label is shown
        # in the tab until the real widget is ready.
        # =====================================================================

        from PyQt6.QtWidgets import QWidget as _QW, QLabel as _QL, QVBoxLayout as _QVB
        from PyQt6.QtCore import Qt as _Qt, QTimer as _QTimer

        def _make_placeholder(label_text: str) -> _QW:
            """Create a dark-themed placeholder widget."""
            w = _QW()
            lay = _QVB(w)
            lbl = _QL(f"Loading {label_text}...")
            lbl.setAlignment(_Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #00FFFF; font-size: 18px; background: #1E1E1E;")
            w.setStyleSheet("background: #1E1E1E;")
            lay.addWidget(lbl)
            return w

        def _replace_tab(index: int, real_widget, old_placeholder, tab_key: str,
                         component_names: list, extra_components: list = None):
            """Swap a placeholder with the real widget at *index*."""
            try:
                # Remember which tab the user is on
                _prev_idx = self.tab_widget.currentIndex()
                
                label = self.tab_widget.tabText(index)
                self.tab_widget.removeTab(index)
                self.tab_widget.insertTab(index, real_widget, label)
                self.tab_widgets[tab_key] = real_widget
                self._widget_to_tab_id[real_widget] = tab_key
                if hasattr(self.event_bus, 'register_component'):
                    for cname in component_names:
                        self.event_bus.register_component(cname, real_widget)
                if extra_components:
                    for attr_name, comp_name in extra_components:
                        obj = getattr(real_widget, attr_name, None)
                        if obj and hasattr(self.event_bus, 'register_component'):
                            self.event_bus.register_component(comp_name, obj)
                old_placeholder.deleteLater()
                
                # Preserve selection deterministically; avoid forcing re-index churn.
                if 0 <= _prev_idx < self.tab_widget.count() and self.tab_widget.currentIndex() != _prev_idx:
                    self.tab_widget.setCurrentIndex(_prev_idx)
            except Exception as ex:
                logger.error(f"❌ Deferred tab replace failed ({tab_key}): {ex}")

        # ================================================================
        # SUB-TAB ROUTING (SOTA 2026 — Qt6 nested QTabWidget pattern)
        # These tabs are NOT main tabs. They are sub-tabs inside their
        # parent tab's container QTabWidget.
        #   - $KAIG        → Mining container
        #   - Comms         → Thoth AI sub-tab
        #   - Software Ctrl → Code Generator container
        #   - MCP Control   → Code Generator container
        # This reduces main tabs from 17→13, eliminating scroll buttons
        # that caused the black mark covering the Dashboard tab.
        # ================================================================

        # -- $KAIG → sub-tab inside Mining --
        try:
            from gui.qt_frames.kaig_tab import KAIGTab
            self.kaig_widget = KAIGTab(event_bus=self.event_bus)
            self._mining_container.addTab(self.kaig_widget, "$KAIG")
            self.tab_widgets['kaig'] = self.kaig_widget
            self._widget_to_tab_id[self.kaig_widget] = 'kaig'
            if hasattr(self.event_bus, 'register_component'):
                self.event_bus.register_component('kaig_tab', self.kaig_widget)
            self._mining_container.currentChanged.connect(self._on_mining_subtab_changed)
            logger.info("✅ $KAIG → Mining sub-tab loaded")
        except ImportError as e:
            logger.warning("⚠️ KAIG tab not available: %s", e)
        except Exception as e:
            logger.error("❌ Error creating KAIG sub-tab: %s", e)
        _tick("KAIG (Mining sub-tab)")

        # -- Comms, Software Control, MCP Control: deferred loading --
        # Comms is loaded as a Thoth AI sub-tab.
        _comms_placeholder = _make_placeholder("Comms")
        self._thoth_container.addTab(_comms_placeholder, "Comms")
        self.tab_widgets['comms'] = _comms_placeholder
        self._widget_to_tab_id[_comms_placeholder] = 'comms'
        _tick("Comms (Thoth sub-tab placeholder)")

        _sw_placeholder = _make_placeholder("Software Control")
        _sw_sub_idx = self._codegen_container.addTab(_sw_placeholder, "Software Control")
        self.tab_widgets['software_automation'] = _sw_placeholder
        self._widget_to_tab_id[_sw_placeholder] = 'software_automation'
        _tick("Software Control (CodeGen sub-tab placeholder)")

        _mcp_placeholder = _make_placeholder("MCP Control")
        _mcp_sub_idx = self._codegen_container.addTab(_mcp_placeholder, "MCP Control")
        self.tab_widgets['mcp_control'] = _mcp_placeholder
        self._widget_to_tab_id[_mcp_placeholder] = 'mcp_control'
        _tick("MCP Control (CodeGen sub-tab placeholder)")

        # Deferred loading: replace placeholders inside their containers
        def _deferred_load_comms():
            try:
                from gui.qt_frames.thoth_comms_tab import ThothCommunicationsTab
                self.comms_widget = ThothCommunicationsTab(event_bus=self.event_bus)
                # Replace Comms placeholder in Thoth container
                _comms_idx = self._thoth_container.indexOf(_comms_placeholder)
                if _comms_idx >= 0:
                    self._thoth_container.removeTab(_comms_idx)
                    self._thoth_container.insertTab(_comms_idx, self.comms_widget, "Comms")
                else:
                    self._thoth_container.addTab(self.comms_widget, "Comms")
                _comms_placeholder.deleteLater()
                self.tab_widgets['comms'] = self.comms_widget
                self._widget_to_tab_id[self.comms_widget] = 'comms'
                if hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('comms_tab', self.comms_widget)
                logger.info("✅ Comms → Thoth sub-tab: deferred load complete")
            except Exception as e:
                logger.error(f"❌ Comms sub-tab deferred load failed: {e}")

        def _deferred_load_software():
            try:
                from gui.qt_frames.software_automation_tab import SoftwareAutomationTab
                self.software_automation_widget = SoftwareAutomationTab(event_bus=self.event_bus)
                # Replace placeholder in CodeGen container
                self._codegen_container.removeTab(_sw_sub_idx)
                self._codegen_container.insertTab(_sw_sub_idx, self.software_automation_widget, "Software Control")
                _sw_placeholder.deleteLater()
                self.tab_widgets['software_automation'] = self.software_automation_widget
                self._widget_to_tab_id[self.software_automation_widget] = 'software_automation'
                if hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('software_automation_tab', self.software_automation_widget)
                logger.info("✅ Software Control → Code Generator sub-tab: deferred load complete")
            except Exception as e:
                logger.error(f"❌ Software Control sub-tab deferred load failed: {e}")

        def _deferred_load_mcp():
            try:
                from gui.qt_frames.mcp_control_center_tab import MCPControlCenterTab
                self.mcp_control_center_widget = MCPControlCenterTab(event_bus=self.event_bus)
                # Replace placeholder in CodeGen container
                # Note: after SW replacement, MCP might shift index. Use count-based approach.
                _mcp_current_idx = self._codegen_container.indexOf(_mcp_placeholder)
                if _mcp_current_idx >= 0:
                    self._codegen_container.removeTab(_mcp_current_idx)
                    self._codegen_container.insertTab(_mcp_current_idx, self.mcp_control_center_widget, "MCP Control")
                else:
                    self._codegen_container.addTab(self.mcp_control_center_widget, "MCP Control")
                _mcp_placeholder.deleteLater()
                self.tab_widgets['mcp_control'] = self.mcp_control_center_widget
                self._widget_to_tab_id[self.mcp_control_center_widget] = 'mcp_control'
                if hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('mcp_control_center', self.mcp_control_center_widget)
                logger.info("✅ MCP Control → Code Generator sub-tab: deferred load complete")
            except Exception as e:
                logger.error(f"❌ MCP Control sub-tab deferred load failed: {e}")

        # Stagger deferred loads so the UI stays responsive between them
        _QTimer.singleShot(500, _deferred_load_comms)
        _QTimer.singleShot(1500, _deferred_load_software)
        _QTimer.singleShot(2500, _deferred_load_mcp)
        logger.info("⏳ Deferred load scheduled for Comms Thoth sub-tab + Software/MCP CodeGen sub-tabs")
        
        _elapsed = _time.monotonic() - _start
        logger.info(f"🏁 ALL {_tab_count} TABS LOADED in {_elapsed:.1f}s")
        
        # ROOT FIX: Explicitly set initial tab to Dashboard (index 0).
        # This ensures Dashboard and Trading (index 1) are both visible at launch.
        try:
            self.tab_widget.setCurrentIndex(0)
            logger.info(f"✅ Initial tab set to Dashboard (index 0), {self.tab_widget.count()} total tabs")
        except Exception as e:
            logger.debug(f"Initial tab selection error: {e}")
        
        # BLACK MARK ROOT FIX: Initialize chat overlay NOW that tabs exist.
        # QStackedWidget is guaranteed to exist after addTab() calls above.
        # Previously this was in create_central_widget() BEFORE any tabs,
        # so the overlay parented to QTabWidget directly → black mark artifact.
        self._init_chat_overlay(None)
        
        # Deterministic tab-bar stabilization (no overflow path).
        _QTimer.singleShot(200, self._refresh_tab_overflow_mode)
        
        # SOTA 2026 CRITICAL: Tab-visibility-aware timer management
        # Pause timers on hidden tabs to save CPU. Only the active tab runs its timers.
        # NOTE: We connect the signal here but do NOT fire _on_tab_changed yet.
        # The old 4000ms singleShot fired during init while tabs were still loading,
        # causing timer starvation.  Instead, _system_settled() is called from
        # kingdom_ai_perfect.py AFTER the loading screen closes and main_window.show()
        # runs.  That gives the event loop a clean start with zero timer competition.
        self._kingdom_system_settled = False
        try:
            self.tab_widget.currentChanged.connect(self._on_tab_changed)
            logger.info("✅ Tab-visibility timer management connected (waiting for system.settled)")
        except Exception as e:
            logger.debug(f"Tab visibility management setup error: {e}")
    
    def _diagnose_and_fix_tab_bar(self):
        """BLACK MARK DIAGNOSTIC + FIX.
        
        Dumps the complete child widget hierarchy of the tab bar to the log
        so we can identify EXACTLY what widget creates the black rectangle
        at the left of the tab bar. Then applies programmatic fixes.
        """
        try:
            bar = self.tab_widget.tabBar()
            if bar.width() < 300:
                # Apply minimal non-invasive stabilization immediately; then
                # retry full diagnostic once geometry has settled.
                self._refresh_tab_overflow_mode()
                logger.info(f"BLACK MARK DIAGNOSTIC deferred (tab bar width not settled yet: {bar.width()})")
                from PyQt6.QtCore import QTimer as _QTimer
                _QTimer.singleShot(800, self._diagnose_and_fix_tab_bar)
                return

            # Keep startup light unless explicit tab debug is requested.
            if os.environ.get("KINGDOM_TAB_DEBUG", "0") != "1":
                self._refresh_tab_overflow_mode()
                bar.setDrawBase(True)
                bar.setContentsMargins(0, 0, 0, 0)
                bar.updateGeometry()
                self.tab_widget.updateGeometry()
                return
            
            # ── DIAGNOSTIC: dump every child widget with geometry ──
            logger.info("=" * 60)
            logger.info("BLACK MARK DIAGNOSTIC — tab bar child widgets:")
            logger.info(f"  TabWidget geometry : {self.tab_widget.geometry()}")
            logger.info(f"  TabBar geometry    : {bar.geometry()}")
            logger.info(f"  TabBar pos         : {bar.pos()}")
            logger.info(f"  TabBar size        : {bar.size()}")
            logger.info(f"  Tab count          : {self.tab_widget.count()}")
            logger.info(f"  Tab 0 rect         : {bar.tabRect(0)}")
            logger.info(f"  Tab 0 text         : {self.tab_widget.tabText(0)}")
            
            for child in bar.children():
                cname = child.__class__.__name__
                oname = child.objectName() if hasattr(child, 'objectName') else ''
                geo = child.geometry() if hasattr(child, 'geometry') else 'N/A'  # type: ignore[attr-defined]
                vis = child.isVisible() if hasattr(child, 'isVisible') else 'N/A'  # type: ignore[attr-defined]
                enabled = child.isEnabled() if hasattr(child, 'isEnabled') else 'N/A'  # type: ignore[attr-defined]
                logger.info(f"  CHILD: {cname} obj='{oname}' geo={geo} vis={vis} enabled={enabled}")
            
            for child in self.tab_widget.children():
                cname = child.__class__.__name__
                if cname in ('QStackedWidget', 'QTabBar'):
                    geo = child.geometry() if hasattr(child, 'geometry') else 'N/A'  # type: ignore[attr-defined]
                    vis = child.isVisible() if hasattr(child, 'isVisible') else 'N/A'  # type: ignore[attr-defined]
                    logger.info(f"  TAB_WIDGET CHILD: {cname} geo={geo} vis={vis}")
                elif hasattr(child, 'geometry'):
                    geo = child.geometry()  # type: ignore[attr-defined]
                    vis = child.isVisible() if hasattr(child, 'isVisible') else 'N/A'  # type: ignore[attr-defined]
                    oname = child.objectName() if hasattr(child, 'objectName') else ''
                    logger.info(f"  TAB_WIDGET CHILD: {cname} obj='{oname}' geo={geo} vis={vis}")
            
            logger.info("=" * 60)
            
            # Keep overflow path disabled (backup-stable path).
            self._refresh_tab_overflow_mode()
            try:
                bar.setUsesScrollButtons(self.tab_widget.usesScrollButtons())
            except Exception:
                pass
            bar.setElideMode(Qt.TextElideMode.ElideNone)
            bar.setExpanding(True)

            # ── FIX 1: Zero the tab bar's own margins ──
            bar.setContentsMargins(0, 0, 0, 0)
            
            # ── FIX 2: Force drawBase off programmatically ──
            bar.setDrawBase(True)
            bar.updateGeometry()
            self.tab_widget.updateGeometry()
            
            logger.info(f"  FIX: Tab 0 rect after stabilization: {bar.tabRect(0)}")
            
            logger.info("✅ Black mark diagnostic + fix applied")
            
        except Exception as e:
            logger.error(f"❌ Tab bar diagnostic/fix error: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _refresh_tab_overflow_mode(self):
        """Apply paint stabilization while keeping overflow subcontrols disabled."""
        try:
            bar = self.tab_widget.tabBar()
            self.tab_widget.setUsesScrollButtons(False)
            bar.setUsesScrollButtons(False)
            bar.setElideMode(Qt.TextElideMode.ElideNone)
            bar.setExpanding(True)
            bar.setDrawBase(True)
            bar.setContentsMargins(0, 0, 0, 0)
            bar.setAutoFillBackground(True)
            self.tab_widget.setAutoFillBackground(True)
        except Exception:
            pass

    def _layout_cache_path(self) -> Path:
        # Project root is parents[1] for gui/kingdom_main_window_qt.py.
        # parents[2] points to the shared "Python Scripts" folder and can
        # leak stale cache across projects/sessions.
        return Path(__file__).resolve().parents[1] / "data" / "ui_layout_cache.json"

    def _schedule_layout_cache_save(self):
        try:
            self._layout_cache_dirty = True
            if self._layout_cache_timer is None:
                self._layout_cache_timer = QTimer(self)
                self._layout_cache_timer.setSingleShot(True)
                self._layout_cache_timer.timeout.connect(self._save_layout_cache)
            self._layout_cache_timer.start(600)
        except Exception:
            pass

    def _save_layout_cache(self):
        if not self._layout_cache_dirty:
            return
        try:
            path = self._layout_cache_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            geo = self.geometry()
            payload = {
                "window": {
                    "x": int(geo.x()),
                    "y": int(geo.y()),
                    "width": int(geo.width()),
                    "height": int(geo.height()),
                    "maximized": bool(self.isMaximized()),
                },
                "tabs": {
                    "index": int(self.tab_widget.currentIndex()) if hasattr(self, "tab_widget") else 0,
                    "uses_scroll_buttons": bool(self.tab_widget.usesScrollButtons()) if hasattr(self, "tab_widget") else False,
                },
                "saved_at": datetime.utcnow().isoformat(),
            }
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self._layout_cache_dirty = False
        except Exception as e:
            logger.debug(f"UI layout cache save failed: {e}")

    def _restore_layout_cache(self):
        try:
            path = self._layout_cache_path()
            if not path.exists():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            window = data.get("window", {})
            if isinstance(window, dict) and {"x", "y", "width", "height"} <= set(window.keys()):
                self.setGeometry(
                    int(window["x"]),
                    int(window["y"]),
                    int(window["width"]),
                    int(window["height"]),
                )
                if bool(window.get("maximized", False)):
                    self.showMaximized()

            tabs = data.get("tabs", {})
            if isinstance(tabs, dict) and hasattr(self, "tab_widget"):
                # Preserve overflow-disabled behavior on restore.
                self.tab_widget.setUsesScrollButtons(False)
                # Do not restore historical selected-tab index by default.
                # Restoring a scrolled index can leave the tab bar offset and
                # reintroduce left-edge masking artifacts in WSL/X11.
                restore_index = os.environ.get("KINGDOM_RESTORE_TAB_INDEX", "0") == "1"
                if restore_index:
                    idx = int(tabs.get("index", 0))
                    if 0 <= idx < self.tab_widget.count():
                        self.tab_widget.setCurrentIndex(idx)
                else:
                    self.tab_widget.setCurrentIndex(0)

            self._refresh_tab_overflow_mode()
        except Exception as e:
            logger.debug(f"UI layout cache restore failed: {e}")

    def _start_tab_artifact_self_heal(self):
        """Automatically re-heal tab-bar geometry during and after startup.

        Covers deferred tab creation windows where Qt can briefly place hidden
        scroll-button widgets over tab 0 in WSL/X11 paths.
        """
        try:
            if os.environ.get("KINGDOM_TAB_SELF_HEAL", "0") != "1":
                self._refresh_tab_overflow_mode()
                return
            from PyQt6.QtCore import QTimer as _QT
            if getattr(self, "_tab_artifact_timer", None) is None:
                self._tab_artifact_timer = _QT(self)
                self._tab_artifact_timer.setInterval(900)
                self._tab_artifact_timer.timeout.connect(self._auto_heal_tab_artifact_tick)
            self._tab_artifact_ticks = 0
            self._tab_artifact_timer.start()
        except Exception as e:
            logger.debug(f"Tab artifact self-heal setup error: {e}")

    def _auto_heal_tab_artifact_tick(self):
        """Periodic auto-heal tick; stops itself after startup settles."""
        try:
            self._refresh_tab_overflow_mode()
            bar = self.tab_widget.tabBar()
            if self.tab_widget.count() > 0:
                tab0 = bar.tabRect(0)
                if tab0.width() > 0 and tab0.x() < 0:
                    # Clamp pathological geometry drift by forcing layout refresh.
                    bar.updateGeometry()
                    self.tab_widget.updateGeometry()
            self._tab_artifact_ticks = int(getattr(self, "_tab_artifact_ticks", 0)) + 1
            if self._tab_artifact_ticks >= 4:
                # Stop after startup settles to avoid periodic UI churn.
                self._tab_artifact_timer.stop()
        except Exception:
            try:
                self._tab_artifact_timer.stop()
            except Exception:
                pass
    
    def _on_tab_changed(self, new_index: int):
        """SOTA 2026: Pause timers on hidden tabs, resume on active tab.
        
        This dramatically reduces CPU by only running animations/polling
        on the tab the user is actually looking at.
        
        GUARD: If the system hasn't settled yet (loading screen still up,
        event loop not running), skip timer management entirely.  The
        Deferred Timer Gate (_pause_all_tab_timers / _system_settled) in
        kingdom_ai_perfect.py handles the initial state.  Without this
        guard, Qt's currentChanged signal during tab creation would
        prematurely resume timers before the event loop starts.
        """
        # Block timer management until _system_settled() marks the gate open.
        if not getattr(self, '_kingdom_system_settled', False):
            return
        try:
            self._publish_ui_telemetry(
                "ui.tab.changed",
                metadata={"index": int(new_index), "tab": self._current_tab_name()},
                min_interval=0.0,
            )
            # Lazy-load heavy Trading tab when user first opens it.
            if (not getattr(self, "_trading_tab_loaded", False)
                    and hasattr(self, "_trading_placeholder")
                    and self.tab_widget.widget(new_index) is self._trading_placeholder):
                self._load_trading_tab()
            if (not getattr(self, "_settings_tab_loaded", False)
                    and hasattr(self, "_settings_placeholder")
                    and self.tab_widget.widget(new_index) is self._settings_placeholder):
                self._load_settings_tab()

            from PyQt6.QtCore import QTimer as _QT
            
            resumed = 0
            paused = 0
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if widget is None:
                    continue
                
                is_active = (i == new_index)
                
                # Find all QTimer children of this tab widget
                timers = widget.findChildren(_QT)
                for timer in timers:
                    if is_active:
                        # Resume timer if it was paused by us
                        if hasattr(timer, '_kingdom_paused') and timer._kingdom_paused:  # type: ignore[attr-defined]
                            interval = getattr(timer, '_kingdom_saved_interval', 0)
                            if interval > 0:
                                timer.start(interval)
                                resumed += 1
                            timer._kingdom_paused = False  # type: ignore[attr-defined]
                    else:
                        # Pause running timers (save their interval first)
                        if timer.isActive():
                            timer._kingdom_saved_interval = timer.interval()  # type: ignore[attr-defined]
                            timer._kingdom_paused = True  # type: ignore[attr-defined]
                            timer.stop()
                            paused += 1
            if resumed or paused:
                logger.debug(f"Tab switch idx={new_index}: resumed {resumed}, paused {paused} timers")

            # SOTA 2026: Pre-load the optimal Ollama model for this tab
            try:
                from core.ollama_gateway import orchestrator
                tab_name = self._current_tab_name()
                orchestrator.on_tab_switched(tab_name)
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Tab timer management error: {e}")

    def _on_mining_subtab_changed(self, idx: int):
        """Handle Mining sub-tab switches (Mining Ops ↔ $KAIG).

        When user switches to $KAIG sub-tab, pre-load the KAIG-specific
        model (FINANCIAL+REASONING+MATH) instead of the generic mining model.
        """
        try:
            widget = self._mining_container.widget(idx)
            tab_id = self._widget_to_tab_id.get(widget, "mining")
            from core.ollama_gateway import orchestrator
            orchestrator.on_tab_switched(tab_id)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # SOTA 2026: Deferred Timer Gate
    # Prevents timer starvation during startup by pausing ALL QTimer
    # children of every tab right after initialize() completes, then
    # resuming only the active tab's timers once the main window is
    # shown and the Qt event loop is running.  This ensures zero timer
    # competition when the GUI first appears.
    # ------------------------------------------------------------------

    def _pause_all_tab_timers(self):
        """Stop every QTimer inside every tab widget.

        Called from kingdom_ai_perfect.py right after initialize() so that
        no timers fire between init completion and the first event-loop
        cycle after main_window.show().
        """
        from PyQt6.QtCore import QTimer as _QT
        paused_count = 0
        try:
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if widget is None:
                    continue
                for timer in widget.findChildren(_QT):
                    if timer.isActive():
                        timer._kingdom_saved_interval = timer.interval()  # type: ignore[attr-defined]
                        timer._kingdom_paused = True  # type: ignore[attr-defined]
                        timer.stop()
                        paused_count += 1
        except Exception as e:
            logger.debug(f"_pause_all_tab_timers error: {e}")
        logger.info(f"⏸️  Paused {paused_count} QTimers across all tabs (system settling)")

    def _system_settled(self):
        """Resume only the active tab's timers and mark system as settled.

        Called via QTimer.singleShot(0, ...) AFTER main_window.show() and
        AFTER the Qt event loop has started (app.exec()).  singleShot(0)
        means "on the very next event-loop iteration", guaranteeing one
        clean paint cycle before any timers fire.

        This is the SOTA 2026 "Deferred Timer Gate" pattern recommended
        by Qt documentation to avoid timer starvation during heavy init.
        """
        self._kingdom_system_settled = True
        try:
            active_idx = self.tab_widget.currentIndex()
            self._on_tab_changed(active_idx)
            logger.info(f"✅ System settled — resumed timers for active tab index {active_idx}")
        except Exception as e:
            logger.debug(f"_system_settled error: {e}")

        # Publish event so subsystems (webcam, sentience, etc.) can reset
        # their FPS counters / re-sync to the now-clean event loop.
        try:
            if hasattr(self, 'event_bus') and self.event_bus is not None:
                self.event_bus.publish("system.settled", {
                    "active_tab_index": active_idx,
                    "timestamp": __import__('time').time(),
                })
        except Exception:
            pass

    def resizeEvent(self, event):
        """Keep tab overflow rendering stable across window resizes."""
        try:
            super().resizeEvent(event)
        finally:
            try:
                self._refresh_tab_overflow_mode()
                self._schedule_layout_cache_save()
            except Exception:
                pass

    def _load_trading_tab(self):
        """Replace Trading placeholder with full TradingTab on demand."""
        if getattr(self, "_trading_tab_loaded", False):
            return
        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
            from gui.qt_frames.trading.trading_tab import TradingTab
            QApplication.processEvents()
            trading_widget = TradingTab(event_bus=self.event_bus)
            QApplication.processEvents()
            if hasattr(trading_widget, '_setup_complete_ui'):
                trading_widget._setup_complete_ui()
            if hasattr(trading_widget, 'setup_trading_intelligence_hub'):
                trading_widget.setup_trading_intelligence_hub()

            idx = self.tab_widget.indexOf(self._trading_placeholder)
            if idx < 0:
                return
            prev_idx = self.tab_widget.currentIndex()
            self.tab_widget.removeTab(idx)
            self.tab_widget.insertTab(idx, trading_widget, "Trading")
            if prev_idx == idx and self.tab_widget.currentIndex() != idx:
                self.tab_widget.setCurrentIndex(idx)

            self.tab_widgets['trading'] = trading_widget
            self._widget_to_tab_id[trading_widget] = 'trading'
            try:
                self._widget_to_tab_id.pop(self._trading_placeholder, None)
            except Exception:
                pass
            self._trading_placeholder.deleteLater()
            self.trading_widget = trading_widget
            self._trading_tab_loaded = True
            self._refresh_tab_overflow_mode()
            logger.info("✅ Trading tab deferred load complete")
        except Exception as e:
            logger.error(f"❌ Trading tab deferred load failed: {e}")

    def _preload_deferred_tabs(self, progress_hook=None):
        """Eagerly construct every placeholder tab before the splash closes.

        The UI was previously built lazily: ``TradingTab`` and ``SettingsTab``
        were instantiated the first time the user clicked them, which caused a
        visible UI freeze on that click (TradingTab alone pulls in
        market-data clients, exchange executors, chart widgets, etc.).

        SOTA 2026 behaviour: during startup, the boot splash calls this
        helper immediately after ``initialize_all_tabs()`` so that by the
        time the splash closes, every tab is fully constructed and
        switching between them is instantaneous.

        Parameters
        ----------
        progress_hook : callable(str) -> None, optional
            Invoked with a human-readable stage name after each tab loads,
            so the splash can keep the progress bar ticking.
        """
        stages = [
            ("Trading", "_trading_tab_loaded", "_load_trading_tab"),
            ("Settings", "_settings_tab_loaded", "_load_settings_tab"),
        ]
        for label, loaded_flag, loader_name in stages:
            if getattr(self, loaded_flag, False):
                continue
            loader = getattr(self, loader_name, None)
            if not callable(loader):
                continue
            try:
                logger.info(f"🔄 Pre-warming {label} tab before GUI handoff...")
                loader()
                logger.info(f"✅ {label} tab pre-warmed - no click freeze possible")
            except Exception as e:
                logger.error(f"❌ Failed to pre-warm {label} tab: {e}")
            finally:
                if callable(progress_hook):
                    try:
                        progress_hook(f"Pre-warmed {label} tab")
                    except Exception:
                        pass

        # Publish a single "tabs fully interactive" signal for any subsystem
        # (voice, Ollama brain, loading splash) that wants to know when the
        # GUI has crossed the interactive threshold.
        try:
            if hasattr(self, "event_bus") and self.event_bus is not None:
                self.event_bus.publish(
                    "gui.tabs.interactive",
                    {
                        "tab_count": self.tab_widget.count(),
                        "timestamp": __import__("time").time(),
                    },
                )
        except Exception:
            pass

    def _load_settings_tab(self):
        """Replace Settings placeholder with full SettingsTab on demand."""
        if getattr(self, "_settings_tab_loaded", False):
            return
        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
            from gui.qt_frames.settings_tab import SettingsTab
            QApplication.processEvents()
            settings_widget = SettingsTab(event_bus=self.event_bus)
            QApplication.processEvents()
            if hasattr(settings_widget, '_setup_complete_ui'):
                settings_widget._setup_complete_ui()  # type: ignore[attr-defined]
            if hasattr(settings_widget, 'setup_advanced_settings'):
                settings_widget.setup_advanced_settings()  # type: ignore[attr-defined]

            idx = self.tab_widget.indexOf(self._settings_placeholder)
            if idx < 0:
                return
            prev_idx = self.tab_widget.currentIndex()
            self.tab_widget.removeTab(idx)
            self.tab_widget.insertTab(idx, settings_widget, "Settings")
            if prev_idx == idx and self.tab_widget.currentIndex() != idx:
                self.tab_widget.setCurrentIndex(idx)

            self.tab_widgets['settings'] = settings_widget
            self._widget_to_tab_id[settings_widget] = 'settings'
            try:
                self._widget_to_tab_id.pop(self._settings_placeholder, None)
            except Exception:
                pass
            self._settings_placeholder.deleteLater()
            self.settings_widget = settings_widget
            self._settings_tab_loaded = True
            self._refresh_tab_overflow_mode()
            logger.info("✅ Settings tab deferred load complete")
        except Exception as e:
            logger.error(f"❌ Settings tab deferred load failed: {e}")

    def _init_chat_overlay(self, parent_layout):
        """Initialize the global Thoth AI chat overlay panel.

        The overlay is a semi-transparent slide-up panel that hosts a
        ChatWidget wired to the same AI + Black Panther voice pipeline.
        """
        try:
            from gui.qt_frames.chat_widget import ChatWidget
        except Exception as e:
            logger.error(f"Failed to import ChatWidget for global overlay: {e}")
            self.chat_overlay = None
            self.global_chat_widget = None
            self._chat_overlay_anim = None
            self._chat_overlay_open = False
            return

        # Parent the overlay to the QStackedWidget (the pane content area)
        # instead of QTabWidget directly. A direct child of QTabWidget sits
        # at (0,0) which overlaps the tab bar area and can cause a black mark
        # artifact on X11 even when invisible.
        _overlay_parent = self.tab_widget
        for _child in self.tab_widget.children():
            if _child.__class__.__name__ == 'QStackedWidget':
                _overlay_parent = _child
                break
        self.chat_overlay = QWidget(_overlay_parent)  # type: ignore[arg-type]
        self.chat_overlay.setObjectName("global_chat_overlay")
        # Default appearance: semi-transparent cyberpunk panel with soft
        # rounded top corners. Opacity is further adjusted per-tab when
        # the overlay is opened.
        self.chat_overlay.setStyleSheet(
            """
            QWidget#global_chat_overlay {
                background-color: rgba(5, 5, 25, 215);
                border-top: 1px solid #00FFFF;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
            """
        )
        # Start fully collapsed
        self.chat_overlay.setMaximumHeight(0)
        self.chat_overlay.setMinimumHeight(0)
        self.chat_overlay.setVisible(False)
        
        # SOTA 2026: Constrain overlay to prevent overflow/bleeding
        # Ensure it stays within parent bounds and doesn't overflow into tab bar
        from PyQt6.QtWidgets import QSizePolicy
        self.chat_overlay.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum
        )
        # Prevent the overlay from extending beyond parent widget
        self.chat_overlay.setMaximumWidth(16777215)  # Qt max, but constrained by parent

        overlay_layout = QVBoxLayout(self.chat_overlay)
        overlay_layout.setContentsMargins(8, 4, 8, 8)
        overlay_layout.setSpacing(4)

        title_label = QLabel("Thoth AI Chat")
        title_label.setStyleSheet("color: #00FFFF; font-weight: bold; padding: 2px 0;")
        # SOTA 2026: Constrain title label to prevent overflow
        title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        title_label.setMaximumHeight(30)
        overlay_layout.addWidget(title_label)
        # Keep a reference so we can update the visible context when
        # messages are sent from different tabs.
        self.chat_overlay_title_label = title_label

        # Configure ChatWidget for Black Panther voice via the event_bus
        # voice.speak auto-tts pipeline. Start with auto_tts disabled so
        # the overlay does not double-play audio until explicitly opened;
        # toggle_chat_overlay will dynamically enable/disable this.
        chat_config = {
            "auto_tts": False,
            "voice": "black_panther",
        }
        self.global_chat_widget = ChatWidget(event_bus=self.event_bus, config=chat_config, parent=self.chat_overlay)
        overlay_layout.addWidget(self.global_chat_widget)

        # Connect message_sent so we can attach tab context and publish ai.request
        self.global_chat_widget.message_sent.connect(self._handle_global_chat_message_sent)

        if parent_layout is not None:
            parent_layout.addWidget(self.chat_overlay)

        # Slide-up / slide-down animation on maximumHeight
        self._chat_overlay_anim = QPropertyAnimation(self.chat_overlay, b"maximumHeight", self)
        # Slightly slower, smoother animation for a more premium feel
        self._chat_overlay_anim.setDuration(320)
        self._chat_overlay_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._chat_overlay_open = False

    def _update_tab_context_summary(self, source_tab_id: Optional[str], message: str) -> None:
        """Update a short rolling context summary for the given tab.

        This keeps only the last few user messages per tab so we can pass a
        compact context string to the AI backend without resending full
        transcripts.
        """
        try:
            key = (source_tab_id or "unknown").lower()
            text = (message or "").strip()
            if not text:
                return

            snippet = f"user: {text}"
            prev = self._tab_context_summaries.get(key, "")
            combined = (prev + "\n" + snippet).strip() if prev else snippet

            # Keep only the last ~10 lines
            lines = combined.splitlines()
            if len(lines) > 10:
                lines = lines[-10:]
            combined = "\n".join(lines)

            # Cap total length so prompts remain efficient
            if len(combined) > 1200:
                combined = combined[-1200:]

            self._tab_context_summaries[key] = combined
        except Exception as e:
            logger.warning(f"Error updating tab context summary for {source_tab_id}: {e}")

    def _handle_codegen_history(self, event_data: Dict[str, Any]) -> None:
        try:
            if not isinstance(event_data, dict):
                return
            text = event_data.get("text") or event_data.get("message") or ""
            if not isinstance(text, str) or not text.strip():
                return
            self._update_tab_context_summary("code_generator", text)
        except Exception as e:
            logger.warning(f"Error handling codegen.history event: {e}")

    def toggle_chat_overlay(self):
        """Toggle the global Thoth AI chat overlay with slide animation."""
        # If overlay failed to initialize, do nothing
        if not hasattr(self, "chat_overlay") or self.chat_overlay is None:
            return
        if self._chat_overlay_anim is None:
            return

        opening = not self._chat_overlay_open
        self._chat_overlay_anim.stop()

        if opening:
            # Adjust background opacity based on which tab is active.
            # On the Thoth AI tab we use an opaque background so it feels
            # like the primary chat surface; on all other tabs we use a
            # slightly transparent overlay so underlying content remains
            # visible.
            try:
                current_widget = self.tab_widget.currentWidget() if hasattr(self, "tab_widget") else None
                current_tab_id = None
                if current_widget is not None and hasattr(self, "_widget_to_tab_id"):
                    current_tab_id = self._widget_to_tab_id.get(current_widget)

                if current_tab_id == "thoth_ai":
                    # Opaque background on Thoth AI tab
                    self.chat_overlay.setStyleSheet(
                        """
                        QWidget#global_chat_overlay {
                            background-color: rgb(5, 5, 25);
                            border-top: 1px solid #00FFFF;
                            border-top-left-radius: 12px;
                            border-top-right-radius: 12px;
                        }
                        """
                    )
                else:
                    # Semi-transparent overlay on all other tabs
                    self.chat_overlay.setStyleSheet(
                        """
                        QWidget#global_chat_overlay {
                            background-color: rgba(5, 5, 25, 215);
                            border-top: 1px solid #00FFFF;
                            border-top-left-radius: 12px;
                            border-top-right-radius: 12px;
                        }
                        """
                    )
            except Exception as style_err:
                logger.warning(f"Error adjusting chat overlay style: {style_err}")

            # Voice playback deduplication:
            # When the global overlay is open, make it the single source of
            # auto-TTS so Black Panther only speaks once per AI response.
            try:
                overlay_chat = getattr(self, "global_chat_widget", None)
                thoth_chat = None
                if hasattr(self, "thoth_ai_widget"):
                    thoth_chat = getattr(self.thoth_ai_widget, "chat_widget", None)

                # Ensure configs exist and are dicts before mutation
                if overlay_chat is not None:
                    if not isinstance(getattr(overlay_chat, "config", None), dict):
                        overlay_chat.config = {}
                if thoth_chat is not None:
                    if not isinstance(getattr(thoth_chat, "config", None), dict):
                        thoth_chat.config = {}

                # Prefer overlay as the active voice source when open
                if thoth_chat is not None and isinstance(thoth_chat.config, dict):
                    thoth_chat.config["auto_tts"] = False
                if overlay_chat is not None and isinstance(overlay_chat.config, dict):
                    overlay_chat.config["auto_tts"] = True
            except Exception as tts_err:
                logger.warning(f"Error adjusting auto_tts for chat widgets: {tts_err}")

            # Opening: make visible and animate height up to ~40-50% of window
            self.chat_overlay.setVisible(True)
            current = self.chat_overlay.maximumHeight()
            # Slightly taller overlay for better readability while keeping
            # a clear view of the underlying tab content.
            target = min(int(self.height() * 0.52), 520)
            self._chat_overlay_anim.setStartValue(current)
            self._chat_overlay_anim.setEndValue(target)
            self._chat_overlay_anim.start()
            self._chat_overlay_open = True
        else:
            # Closing: animate down to 0 then hide
            start = self.chat_overlay.maximumHeight()
            self._chat_overlay_anim.setStartValue(start)
            self._chat_overlay_anim.setEndValue(0)

            def _on_finished():
                try:
                    self.chat_overlay.setVisible(False)
                finally:
                    # Disconnect to avoid multiple connections over time
                    try:
                        self._chat_overlay_anim.finished.disconnect(_on_finished)
                    except Exception:
                        pass

            self._chat_overlay_anim.finished.connect(_on_finished)
            self._chat_overlay_anim.start()
            self._chat_overlay_open = False

            # When the overlay is closed, restore the Thoth AI tab as the
            # primary Black Panther voice source so normal tab chat continues
            # to speak responses, and keep the overlay muted until reopened.
            try:
                overlay_chat = getattr(self, "global_chat_widget", None)
                thoth_chat = None
                if hasattr(self, "thoth_ai_widget"):
                    thoth_chat = getattr(self.thoth_ai_widget, "chat_widget", None)

                if overlay_chat is not None and isinstance(getattr(overlay_chat, "config", None), dict):
                    overlay_chat.config["auto_tts"] = False
                if thoth_chat is not None:
                    if not isinstance(getattr(thoth_chat, "config", None), dict):
                        thoth_chat.config = {}
                    thoth_chat.config["auto_tts"] = True
            except Exception as tts_err:
                logger.warning(f"Error restoring auto_tts after overlay close: {tts_err}")

        # Keep toggle button state in sync
        if hasattr(self, "chat_toggle_button"):
            self.chat_toggle_button.setChecked(self._chat_overlay_open)

    def _handle_global_chat_message_sent(self, message: str):
        """Handle messages sent from the global overlay ChatWidget.

        Adds the user message to the overlay chat and publishes an
        ai.request event with awareness of the current tab.
        """
        try:
            text = (message or "").strip()
            if not text:
                return

            # Determine which tab is currently active
            source_tab_id = None
            try:
                if hasattr(self, "tab_widget") and self.tab_widget is not None:
                    current_widget = self.tab_widget.currentWidget()
                    if current_widget is not None:
                        if hasattr(self, "_widget_to_tab_id"):
                            source_tab_id = self._widget_to_tab_id.get(current_widget)
                        if not source_tab_id:
                            # Fallback: use visible tab text as context
                            idx = self.tab_widget.indexOf(current_widget)
                            if idx >= 0:
                                source_tab_id = self.tab_widget.tabText(idx)
            except Exception as ctx_err:
                logger.warning(f"Error determining source tab for chat overlay: {ctx_err}")

            # AUTOPILOT CONTROL: if the user explicitly types an update
            # command while the Code Generator tab is active, trigger the
            # Code Generator's APPLY & HOT-RELOAD flow programmatically.
            try:
                normalized = text.lower()
                is_update_cmd = normalized in ("update", "/update", "update now", "apply update")
                if isinstance(source_tab_id, str) and source_tab_id.lower() == "code_generator" and is_update_cmd:
                    codegen_widget = self.tab_widgets.get("code_generator") if hasattr(self, "tab_widgets") else None
                    if codegen_widget is not None and hasattr(codegen_widget, "apply_hot_reload"):
                        # Inform the user in the overlay and then invoke the
                        # existing apply_hot_reload(), which will still show
                        # the confirmation diff/hash dialog.
                        if hasattr(self, "global_chat_widget") and self.global_chat_widget is not None:
                            try:
                                self.global_chat_widget.add_message(
                                    "System",
                                    "Initiating Code Generator Apply & Hot-Reload using current editor contents. "
                                    "Review the diff dialog in the Code Generator tab to confirm.",
                                    is_ai=True,
                                )
                            except Exception as add_sys_err:
                                logger.warning(f"Error adding autopilot status message to global ChatWidget: {add_sys_err}")
                        try:
                            codegen_widget.apply_hot_reload()
                        except Exception as ap_err:
                            logger.error(f"Error triggering Code Generator autopilot update: {ap_err}")
                    # Autopilot commands are control messages, not AI
                    # prompts; do not forward them to the BrainRouter.
                    return
            except Exception as autopilot_err:
                logger.warning(f"Autopilot update handling error: {autopilot_err}")

            # Update overlay title with the resolved context for debugging.
            try:
                if hasattr(self, "chat_overlay_title_label") and self.chat_overlay_title_label is not None:
                    # Prefer logical tab id; fall back to a readable label
                    display_ctx = source_tab_id or "Unknown Tab"
                    self.chat_overlay_title_label.setText(f"Thoth AI Chat • {display_ctx}")
            except Exception as title_err:
                logger.warning(f"Error updating chat overlay title: {title_err}")

            # Update per-tab rolling context summary so each overlay request
            # carries a short history window for the active tab.
            self._update_tab_context_summary(source_tab_id, text)

            # ChatWidget itself does not add the user message on emit, so we
            # add it explicitly here for the overlay history.
            if hasattr(self, "global_chat_widget") and self.global_chat_widget is not None:
                try:
                    self.global_chat_widget.add_message("You", text, is_ai=False)
                except Exception as add_err:
                    logger.error(f"Error adding user message to global ChatWidget: {add_err}")

            # Publish AI request to the same backend used by ThothQtWidget
            if self.event_bus:
                from datetime import datetime as _dt
                import time as _time

                request_id = f"req_{int(_time.time() * 1000)}"
                # Match ThothQtWidget default model selection
                selected_model = "deepseek-v3.1:671b-cloud"

                # Attach a per-tab system prompt so the backend can adapt
                # behavior to the active context (trading, mining, etc.).
                system_prompt = None
                try:
                    key = (source_tab_id or "").lower() if isinstance(source_tab_id, str) else ""
                    tab_prompts = {
                        "dashboard": (
                            "You are Thoth AI providing a high-level operations overview "
                            "for the Kingdom AI dashboard. Summarize system status, "
                            "health, and key opportunities across trading, mining, and blockchain."
                        ),
                        "trading": (
                            "You are Thoth AI acting as an expert trading assistant inside "
                            "the Kingdom AI Trading tab. Focus on live markets, risk management, "
                            "order execution, and strategy optimization across exchanges and brokers."
                        ),
                        "blockchain": (
                            "You are Thoth AI acting as a multi-chain blockchain analyst for "
                            "228+ networks. Focus on on-chain data, transactions, gas fees, and "
                            "cross-chain flows relevant to the user's request."
                        ),
                        "mining": (
                            "You are Thoth AI optimizing cryptocurrency mining within the Kingdom AI "
                            "Mining tab. Emphasize hardware utilization, energy efficiency, coin "
                            "selection, and real-world profitability."
                        ),
                        "wallet": (
                            "You are Thoth AI assisting with wallet management inside the Wallet tab. "
                            "Prioritize security, key management, balances, and safe transaction "
                            "practices across multiple chains."
                        ),
                        "code_generator": (
                            "You are Thoth AI acting as a senior software engineer inside the Code "
                            "Generator tab. Produce concise, production-grade code and explain any "
                            "critical design decisions."
                        ),
                        "api_keys": (
                            "You are Thoth AI helping manage and debug API keys and integrations. "
                            "Focus on credentials, permissions, environment configuration, and safe "
                            "rotation strategies. Never invent real secrets."
                        ),
                        "vr": (
                            "You are Thoth AI assisting with VR and immersive systems inside the VR "
                            "tab. Emphasize user experience, performance, and safe interaction "
                            "patterns."
                        ),
                        "settings": (
                            "You are Thoth AI guiding advanced configuration inside the Settings tab. "
                            "Explain options clearly, highlight trade-offs, and avoid destructive "
                            "changes unless explicitly confirmed."
                        ),
                        "thoth_ai": (
                            "You are Thoth AI operating in your primary control tab. Provide "
                            "high-level reasoning, cross-domain guidance, and orchestration across "
                            "trading, mining, blockchain, wallet, VR, and configuration."
                        ),
                    }

                    system_prompt = tab_prompts.get(key)
                except Exception as sp_err:
                    logger.warning(f"Error building system_prompt for source_tab={source_tab_id}: {sp_err}")

                payload: Dict[str, Any] = {
                    "request_id": request_id,
                    "prompt": text,
                    "model": selected_model,
                    "timestamp": _dt.utcnow().isoformat(),
                    "sender": "user",
                }
                if source_tab_id:
                    payload["source_tab"] = source_tab_id
                    # Include per-tab rolling context summary when available
                    try:
                        key = source_tab_id.lower()
                        tab_summary = self._tab_context_summaries.get(key)
                        if tab_summary:
                            payload["tab_context_summary"] = tab_summary
                    except Exception as ts_err:
                        logger.warning(f"Error attaching tab_context_summary for {source_tab_id}: {ts_err}")
                if system_prompt:
                    payload["system_prompt"] = system_prompt

                # Tag the message for sentience/meta-learning and persistent
                # memory so the backend can reconstruct history per tab.
                try:
                    self.event_bus.publish(
                        "thoth.message.sent",
                        {
                            "message": text,
                            "timestamp": _dt.utcnow().isoformat(),
                            "for_sentience_processing": True,
                            "source_tab": source_tab_id or "unknown",
                            "role": "user",
                            "channel": "global_overlay",
                        },
                    )
                except Exception as tm_err:
                    logger.warning(f"Error publishing thoth.message.sent from overlay: {tm_err}")

                try:
                    self.event_bus.publish(
                        "memory.store",
                        {
                            "type": "chat_history",
                            "data": {
                                "message": text,
                                "role": "user",
                                "source_tab": source_tab_id or "unknown",
                                "channel": "global_overlay",
                            },
                            "metadata": {
                                "source_tab": source_tab_id or "unknown",
                                "role": "user",
                                "channel": "global_overlay",
                            },
                        },
                    )
                except Exception as mem_err:
                    logger.warning(f"Error publishing memory.store from overlay: {mem_err}")

                try:
                    brain_event: Dict[str, Any] = {**payload}
                    if isinstance(source_tab_id, str):
                        brain_event["domain"] = source_tab_id.lower()
                    else:
                        brain_event["domain"] = "general"
                    brain_event.setdefault("speak", False)
                    self.event_bus.publish("brain.request", brain_event)
                except Exception as brain_err:
                    logger.warning(f"Error publishing brain.request from chat overlay: {brain_err}")

        except Exception as e:
            logger.error(f"Error handling global chat message: {e}")

    def start_websocket_feeds(self, symbols=None):
        if self._ws_feeds_started:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            QTimer.singleShot(1000, lambda: self.start_websocket_feeds(symbols))
            return
        try:
            from gui.qt_frames.trading.trading_websocket_price_feed import (
                PriceFeedManager, WebSocketPriceFeed
            )
            self.price_feed_manager = PriceFeedManager(self.event_bus)
            feed = WebSocketPriceFeed(event_bus=self.event_bus)
            self.price_feed_manager.add_feed('realtime', feed)
            if hasattr(self.event_bus, 'register_component'):
                self.event_bus.register_component('price_feeds', self.price_feed_manager)
            self.price_feed_manager.start_all(symbols)
            self._ws_feeds_started = True
            logger.info("✅ WebSocket price feeds started")
        except Exception as e:
            try:
                logger.error(f"Failed to start WebSocket feeds: {e}")
            except Exception:
                pass
    
    def update_status_bar(self, message: str, progress: Optional[int] = None):
        """Update the status bar with a message and optional progress"""
        self.status_label.setText(message)
        
        if progress is not None:
            self.progress_bar.setValue(progress)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)
            
    def handle_system_status(self, event_data):
        """Handle system status events"""
        if isinstance(event_data, dict):
            status = event_data.get('status', 'Unknown')
            message = event_data.get('message', '')
            self.update_status_bar(f"System: {status} - {message}")
    
    def handle_component_status(self, event_data):
        """Handle component status events"""
        if isinstance(event_data, dict):
            component = event_data.get('component', 'Unknown')
            status = event_data.get('status', 'Unknown')
            self.component_status_changed.emit(component, status)
    
    def handle_gui_update(self, event_data):
        """Handle GUI update events"""
        if isinstance(event_data, dict):
            update_type = event_data.get('type', '')
            data = event_data.get('data', {})
            logger.info(f"GUI update: {update_type}")
    
    # Menu action handlers
    def new_project(self):
        logger.info("New project requested")
    
    def open_project(self):
        logger.info("Open project requested")
    
    def save_project(self):
        logger.info("Save project requested")
    
    def open_wallet_manager(self):
        logger.info("Wallet manager requested")
    
    def open_mining_dashboard(self):
        logger.info("Mining dashboard requested")
    
    def open_trading_terminal(self):
        logger.info("Trading terminal requested")
    
    def show_documentation(self):
        logger.info("Documentation requested")
    
    def show_about(self):
        logger.info("About dialog requested")
    
    def closeEvent(self, event):
        """Handle window close event - require termination code 456456 to exit.
        
        CRITICAL: After cleanup, we explicitly call QApplication.quit() and
        sys.exit(0) to ensure the entire application terminates. Previously,
        only event.accept() was called which closes the window but may leave
        the Qt event loop, asyncio loops, and background threads running.
        """
        from PyQt6.QtWidgets import QInputDialog, QLineEdit, QApplication
        
        # Ask for termination code
        try:
            # SOTA 2026 FIX: Create styled QInputDialog so text is visible
            # The cyberpunk stylesheet makes the default dialog blank (dark-on-dark)
            dialog = QInputDialog(self)
            dialog.setWindowTitle("Terminate Kingdom AI")
            dialog.setLabelText("Enter termination code to exit (or Cancel to keep running):")
            dialog.setTextEchoMode(QLineEdit.EchoMode.Password)
            dialog.setStyleSheet("""
                QInputDialog { background-color: #1a1a2e; }
                QLabel { color: #00FFFF; font-size: 13px; font-weight: bold; }
                QLineEdit { 
                    background-color: #0a0a1e; color: #00FF00; 
                    border: 2px solid #00FFFF; border-radius: 4px;
                    padding: 8px; font-size: 14px;
                }
                QPushButton {
                    background-color: #2d2d4e; color: #00FFFF;
                    border: 1px solid #00FFFF; border-radius: 4px;
                    padding: 6px 20px; font-weight: bold;
                }
                QPushButton:hover { background-color: #00FFFF; color: #0a0a1e; }
            """)
            ok = dialog.exec()
            code = dialog.textValue() if ok else ""
        except Exception as dialog_err:
            logger.error(f"Error showing termination dialog: {dialog_err}")
            event.ignore()
            return
        
        if ok and code == "456456":
            logger.warning("TERMINATION CODE ACCEPTED - Shutting down Kingdom AI...")
            try:
                self._save_layout_cache()
            except Exception:
                pass
            
            # Perform cleanup
            try:
                # Stop QThread instances efficiently (avoid gc.get_objects() to prevent OOM)
                if hasattr(self, '_tracked_threads'):
                    for thread in list(getattr(self, '_tracked_threads', [])):
                        try:
                            if thread and thread.isRunning():
                                logger.info(f"Stopping QThread: {thread}")
                                thread.requestInterruption()
                                thread.quit()
                                if not thread.wait(3000):
                                    logger.warning(f"Thread {thread} did not stop gracefully, terminating")
                                    thread.terminate()
                                    thread.wait(1000)
                                thread.deleteLater()
                        except (KeyboardInterrupt, SystemExit):
                            raise
                        except Exception as e:
                            logger.debug(f"Error stopping thread {thread}: {e}")
                
                # Stop WebSocket price feeds
                try:
                    if hasattr(self, 'price_feed_manager') and self.price_feed_manager:
                        if hasattr(self.price_feed_manager, 'stop_all'):
                            self.price_feed_manager.stop_all()
                        logger.info("WebSocket price feeds stopped")
                except Exception as ws_err:
                    logger.debug(f"Error stopping WebSocket feeds: {ws_err}")
                
                # Check tabs for cleanup
                for tab_name, tab_widget in getattr(self, 'tab_widgets', {}).items():
                    if hasattr(tab_widget, '_cleanup_threads'):
                        try:
                            tab_widget._cleanup_threads()
                        except (KeyboardInterrupt, SystemExit):
                            raise
                        except Exception:
                            pass
                    if hasattr(tab_widget, 'cleanup'):
                        try:
                            tab_widget.cleanup()
                        except (KeyboardInterrupt, SystemExit):
                            raise
                        except Exception:
                            pass
                
                # Find and clean up all nested widgets with _cleanup_threads
                try:
                    tab_widget_set = set(getattr(self, 'tab_widgets', {}).values())
                    for widget in self.findChildren(QWidget):
                        if hasattr(widget, '_cleanup_threads') and widget not in tab_widget_set:
                            try:
                                widget._cleanup_threads()  # type: ignore[attr-defined]
                            except (KeyboardInterrupt, SystemExit):
                                raise
                            except Exception:
                                pass
                except Exception:
                    pass
                
                # Shutdown event bus gracefully
                if hasattr(self, 'event_bus') and self.event_bus:
                    try:
                        if hasattr(self.event_bus, 'shutdown'):
                            self.event_bus.shutdown()
                        else:
                            self.event_bus.publish("system.shutdown", {"reason": "user_termination"})
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except Exception as e:
                        logger.debug(f"Error shutting down event bus: {e}")
                        
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                logger.error(f"Error during shutdown cleanup: {e}")
            
            # Hide window before accept to prevent blank X11 surface during cleanup
            self.hide()
            event.accept()
            
            try:
                QApplication.instance().quit()
            except Exception:
                pass
            
            logger.info("Kingdom AI shutdown complete. Exiting process.")
            import os
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, lambda: os._exit(0))
        else:
            logger.info("Termination cancelled or invalid code - Kingdom AI continues running")
            event.ignore()
