"""
SOTA 2026 Radio Communications Command Center
==============================================
Professional-grade RF communications interface with:
- Full-screen spectrum analyzer with waterfall display
- All frequency types: Bluetooth, Scalar, Radio, Ultrasonic, Robotics, WiFi, Zigbee, LoRa
- Two-way send/receive signal interface
- Fullscreen toggle for immersive operation
- Real-time FFT visualization using PyQtGraph
"""
import logging
import math
import time
import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QPen, QBrush, QFont, QPainterPath
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGroupBox,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QScrollArea,
    QSplitter,
    QFrame,
    QSizePolicy,
    QComboBox,
    QSlider,
    QTabWidget,
    QGridLayout,
    QStackedWidget,
    QProgressBar,
    QCheckBox,
    QToolButton,
    QScrollArea,
)

logger = logging.getLogger(__name__)

# Try importing PyQtGraph for real-time spectrum visualization
try:
    import pyqtgraph as pg
    import numpy as np
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False
    pg = None
    np = None


class FrequencyBand(Enum):
    """RF Frequency Bands - Complete Spectrum Coverage"""
    # Sub-audio and Scalar
    SCALAR = ("Scalar/Tesla", 0.000001, 0.00003, "#FF00FF")  # Experimental scalar waves
    ELF = ("ELF", 0.000003, 0.00003, "#9400D3")  # Extremely Low Frequency
    SLF = ("SLF", 0.00003, 0.0003, "#8A2BE2")  # Super Low Frequency
    ULF = ("ULF", 0.0003, 0.003, "#7B68EE")  # Ultra Low Frequency
    VLF = ("VLF", 0.003, 0.03, "#6A5ACD")  # Very Low Frequency - Submarine comms
    
    # Radio Bands
    LF = ("LF", 0.03, 0.3, "#4169E1")  # Low Frequency - Navigation
    MF = ("MF/AM", 0.3, 3.0, "#1E90FF")  # Medium Frequency - AM Radio
    HF = ("HF/Shortwave", 3.0, 30.0, "#00BFFF")  # High Frequency - Amateur/Shortwave
    VHF = ("VHF", 30.0, 300.0, "#00CED1")  # Very High Frequency - FM/TV/Aviation
    UHF = ("UHF", 300.0, 3000.0, "#20B2AA")  # Ultra High Frequency - TV/Cellular/GPS
    
    # Microwave Bands
    SHF = ("SHF/Microwave", 3000.0, 30000.0, "#3CB371")  # Super High Frequency - Satellite/Radar
    EHF = ("EHF/mmWave", 30000.0, 300000.0, "#228B22")  # Extremely High - 5G mmWave
    
    # Ultrasonic (acoustic but relevant for robotics)
    ULTRASONIC = ("Ultrasonic", 0.00002, 0.001, "#FFD700")  # 20Hz - 1MHz acoustic
    
    # IoT Specific Bands
    LORA_EU = ("LoRa EU", 868.0, 868.6, "#FF6347")  # LoRa Europe
    LORA_US = ("LoRa US", 902.0, 928.0, "#FF4500")  # LoRa North America
    ZIGBEE = ("Zigbee", 2400.0, 2483.5, "#DC143C")  # Zigbee/Thread
    BLUETOOTH = ("Bluetooth", 2400.0, 2483.5, "#00FFFF")  # Bluetooth/BLE
    WIFI_24 = ("WiFi 2.4G", 2400.0, 2500.0, "#7FFF00")  # WiFi 2.4 GHz
    WIFI_5G = ("WiFi 5G", 5150.0, 5850.0, "#ADFF2F")  # WiFi 5 GHz
    WIFI_6E = ("WiFi 6E", 5925.0, 7125.0, "#32CD32")  # WiFi 6E
    
    # Robotics Remote Control
    RC_27MHZ = ("RC 27MHz", 26.995, 27.255, "#FFA500")  # Toy remote control
    RC_40MHZ = ("RC 40MHz", 40.66, 40.70, "#FF8C00")  # RC vehicles
    RC_433MHZ = ("RC 433MHz", 433.05, 434.79, "#FF7F50")  # ISM band RC
    RC_24GHZ = ("RC 2.4GHz", 2400.0, 2483.5, "#FF6B6B")  # Modern RC systems
    
    # Cellular
    LTE = ("LTE/4G", 700.0, 2700.0, "#9370DB")  # LTE bands
    NR_5G = ("5G NR", 600.0, 52600.0, "#BA55D3")  # 5G New Radio
    
    def __init__(self, display_name_or_tuple, freq_min_mhz=None, freq_max_mhz=None, color=None):
        # Enum passes a single tuple as first arg; unpack so .display_name etc. are correct
        if isinstance(display_name_or_tuple, (list, tuple)) and len(display_name_or_tuple) >= 4:
            self.display_name = display_name_or_tuple[0]
            self.freq_min_mhz = display_name_or_tuple[1]
            self.freq_max_mhz = display_name_or_tuple[2]
            self.color = display_name_or_tuple[3]
        else:
            self.display_name = display_name_or_tuple
            self.freq_min_mhz = freq_min_mhz or 0.0
            self.freq_max_mhz = freq_max_mhz or 0.0
            self.color = color or "#7aa2f7"


@dataclass
class CommChannel:
    """Communication channel configuration"""
    name: str
    frequency_mhz: float
    bandwidth_khz: float
    modulation: str
    power_dbm: float
    direction: str  # "TX", "RX", "DUPLEX"
    protocol: str
    active: bool = False


# Predefined channels for quick access
PRESET_CHANNELS: List[CommChannel] = [
    CommChannel("FM Radio", 100.0, 200.0, "FM", 0.0, "RX", "Broadcast"),
    CommChannel("Amateur 2m", 146.52, 25.0, "FM", 5.0, "DUPLEX", "Ham Radio"),
    CommChannel("WiFi Ch1", 2412.0, 22000.0, "OFDM", 20.0, "DUPLEX", "WiFi"),
    CommChannel("Bluetooth", 2402.0, 1000.0, "GFSK", 4.0, "DUPLEX", "BLE"),
    CommChannel("LoRa EU", 868.1, 125.0, "CSS", 14.0, "DUPLEX", "LoRaWAN"),
    CommChannel("Zigbee", 2405.0, 2000.0, "OQPSK", 0.0, "DUPLEX", "802.15.4"),
    CommChannel("RC Control", 2450.0, 1000.0, "DSSS", 20.0, "TX", "Robotics"),
    CommChannel("Ultrasonic", 0.04, 20.0, "Pulse", -10.0, "DUPLEX", "Sonar"),
]


class SpectrumAnalyzerWidget(QWidget):
    """
    SOTA 2026 Real-Time Spectrum Analyzer with Waterfall Display
    Uses PyQtGraph for high-performance visualization (1000+ FPS capable)
    """
    
    frequency_selected = pyqtSignal(float)  # Emitted when user clicks on spectrum
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._center_freq_mhz = 100.0
        self._span_mhz = 20.0
        self._sample_rate = 2.4e6
        self._fft_size = 1024
        self._waterfall_history: List[Any] = []
        self._max_waterfall_rows = 100
        self._current_band = FrequencyBand.VHF
        self._event_bus = None  # Will be set by parent tab if available
        
        self._setup_ui()
        self._setup_spectrum_timer()
    
    def set_event_bus(self, event_bus):
        """Set event bus for real SDR data access."""
        self._event_bus = event_bus
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # Give the analyzer breathing room so borders/handles never cut through the content.
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        # region agent log
        try:
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "C1",
                    "location": "thoth_comms_tab.py:SpectrumAnalyzerWidget:_setup_ui",
                    "message": "Spectrum UI setup",
                    "data": {"has_pyqtgraph": bool(HAS_PYQTGRAPH)},
                    "timestamp": int(time.time() * 1000),
                }) + "\n")
        except Exception:
            pass
        # endregion
        
        if HAS_PYQTGRAPH:
            # Configure PyQtGraph for dark theme
            pg.setConfigOptions(antialias=True, background='#0a0a12', foreground='#7aa2f7')
            
            # Spectrum plot (FFT magnitude)
            self.spectrum_plot = pg.PlotWidget(title="RF Spectrum Analyzer")
            self.spectrum_plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.spectrum_plot.setLabel('left', 'Power', units='dBm')
            self.spectrum_plot.setLabel('bottom', 'Frequency', units='MHz')
            self.spectrum_plot.showGrid(x=True, y=True, alpha=0.3)
            self.spectrum_plot.setYRange(-120, 0)
            self.spectrum_plot.setMouseEnabled(x=True, y=True)
            
            # Create spectrum curve with gradient fill
            self.spectrum_curve = self.spectrum_plot.plot([], [], pen=pg.mkPen('#00ff88', width=2))
            self.spectrum_fill = pg.FillBetweenItem(
                self.spectrum_curve, 
                pg.PlotDataItem([0], [-120]),
                brush=pg.mkBrush(0, 255, 136, 50)
            )
            self.spectrum_plot.addItem(self.spectrum_fill)
            
            # Peak markers
            self.peak_marker = pg.ScatterPlotItem(size=10, brush=pg.mkBrush('#ff0055'))
            self.spectrum_plot.addItem(self.peak_marker)
            
            # Waterfall plot (spectrogram)
            self.waterfall_widget = pg.PlotWidget(title="Waterfall Display")
            self.waterfall_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.waterfall_widget.setLabel('left', 'Time')
            self.waterfall_widget.setLabel('bottom', 'Frequency', units='MHz')
            self.waterfall_img = pg.ImageItem()
            self.waterfall_widget.addItem(self.waterfall_img)
            
            # Color map for waterfall (plasma-like)
            colors = [
                (0, 0, 0),
                (45, 0, 90),
                (120, 0, 180),
                (200, 50, 100),
                (255, 150, 0),
                (255, 255, 100),
                (255, 255, 255)
            ]
            cmap = pg.ColorMap(pos=np.linspace(0, 1, len(colors)), color=colors)
            self.waterfall_img.setLookupTable(cmap.getLookupTable())
            
            # Splitter for spectrum and waterfall
            splitter = QSplitter(Qt.Orientation.Vertical)
            splitter.setHandleWidth(3)
            splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            splitter.addWidget(self.spectrum_plot)
            splitter.addWidget(self.waterfall_widget)
            splitter.setSizes([300, 200])
            
            layout.addWidget(splitter)
            
            # Click handler for frequency selection
            self.spectrum_plot.scene().sigMouseClicked.connect(self._on_spectrum_click)
        else:
            # Fallback: Simple visual display without PyQtGraph
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            container_layout.addStretch(1)

            self._fallback_label = QLabel("📡 Spectrum Analyzer\n(Install pyqtgraph + numpy for visualization)")
            self._fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._fallback_label.setMinimumHeight(260)
            self._fallback_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._fallback_label.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #1a1b26, stop:0.5 #24283b, stop:1 #1a1b26);
                    color: #7aa2f7;
                    font-size: 18px;
                    border: 2px solid #3b4261;
                    border-radius: 10px;
                    padding: 40px;
                }
            """)
            container_layout.addWidget(self._fallback_label, stretch=0)
            container_layout.addStretch(1)

            layout.addWidget(container)
    
    def _setup_spectrum_timer(self):
        """Setup timer for spectrum updates (real SDR data via event bus or awaiting data)"""
        self._spectrum_timer = QTimer(self)
        self._spectrum_timer.timeout.connect(self._update_spectrum)
        self._spectrum_timer.setInterval(200)  # SOTA 2026 FIX: 200ms (5 FPS) saves CPU
    
    def start_spectrum(self):
        """Start spectrum analyzer updates"""
        # region agent log
        try:
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "C2",
                    "location": "thoth_comms_tab.py:SpectrumAnalyzerWidget:start_spectrum",
                    "message": "Spectrum start requested",
                    "data": {"timer_active": bool(self._spectrum_timer.isActive())},
                    "timestamp": int(time.time() * 1000),
                }) + "\n")
        except Exception:
            pass
        # endregion
        self._spectrum_timer.start()
    
    def stop_spectrum(self):
        """Stop spectrum analyzer updates"""
        self._spectrum_timer.stop()
    
    def set_center_frequency(self, freq_mhz: float):
        """Set center frequency in MHz"""
        self._center_freq_mhz = freq_mhz
        self._update_frequency_range()
    
    def set_span(self, span_mhz: float):
        """Set frequency span in MHz"""
        self._span_mhz = span_mhz
        self._update_frequency_range()
    
    def set_band(self, band: FrequencyBand):
        """Set to a specific frequency band"""
        self._current_band = band
        center = (band.freq_min_mhz + band.freq_max_mhz) / 2
        span = band.freq_max_mhz - band.freq_min_mhz
        self.set_center_frequency(center)
        self.set_span(max(span * 1.2, 1.0))  # 20% margin
    
    def _update_frequency_range(self):
        """Update plot X-axis range"""
        if HAS_PYQTGRAPH:
            freq_min = self._center_freq_mhz - self._span_mhz / 2
            freq_max = self._center_freq_mhz + self._span_mhz / 2
            self.spectrum_plot.setXRange(freq_min, freq_max)
            self.waterfall_widget.setXRange(freq_min, freq_max)
    
    def _update_spectrum(self):
        """Update spectrum display with new data"""
        if not HAS_PYQTGRAPH:
            return
        # region agent log
        try:
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "C3",
                    "location": "thoth_comms_tab.py:SpectrumAnalyzerWidget:_update_spectrum",
                    "message": "Spectrum update tick",
                    "data": {"center_mhz": self._center_freq_mhz, "span_mhz": self._span_mhz},
                    "timestamp": int(time.time() * 1000),
                }) + "\n")
        except Exception:
            pass
        # endregion
        
        # Get real spectrum data from SDR hardware via event bus, or show awaiting message
        freq_min = self._center_freq_mhz - self._span_mhz / 2
        freq_max = self._center_freq_mhz + self._span_mhz / 2
        freqs = np.linspace(freq_min, freq_max, self._fft_size)
        
        # Try to get real FFT data from event bus or SDR component
        noise_floor = None
        if self._event_bus:
            try:
                # Query for real spectrum data
                if hasattr(self._event_bus, 'get_component'):
                    sdr_component = self._event_bus.get_component('sdr_interface', silent=True)
                    if sdr_component and hasattr(sdr_component, 'get_fft_data'):
                        fft_data = sdr_component.get_fft_data(freq_min, freq_max, self._fft_size)
                        if fft_data is not None:
                            noise_floor = np.asarray(fft_data)
            except Exception as e:
                logger.debug(f"Real SDR data query failed: {e}")
        
        # Fallback: Show awaiting data message (no simulated data)
        if noise_floor is None:
            # Show flat noise floor with "Awaiting data" indicator
            noise_floor = np.full(self._fft_size, -120.0)  # Flat line at noise floor
            # Add a small indicator at center frequency to show system is active
            center_idx = self._fft_size // 2
            noise_floor[center_idx] = -100.0  # Small blip to show system is running
        
        # Update spectrum curve
        self.spectrum_curve.setData(freqs, noise_floor)
        
        # Find and mark peak
        peak_idx = np.argmax(noise_floor)
        self.peak_marker.setData([freqs[peak_idx]], [noise_floor[peak_idx]])
        
        # Update waterfall
        self._waterfall_history.append(noise_floor.copy())
        if len(self._waterfall_history) > self._max_waterfall_rows:
            self._waterfall_history.pop(0)
        
        if len(self._waterfall_history) > 1:
            waterfall_data = np.array(self._waterfall_history)
            # Normalize to 0-255 for colormap
            waterfall_norm = ((waterfall_data + 120) / 120 * 255).clip(0, 255).astype(np.uint8)
            self.waterfall_img.setImage(waterfall_norm.T, autoLevels=False)
            self.waterfall_img.setRect(freq_min, 0, self._span_mhz, len(self._waterfall_history))
    
    def _on_spectrum_click(self, event):
        """Handle click on spectrum to select frequency"""
        if HAS_PYQTGRAPH:
            pos = event.scenePos()
            if self.spectrum_plot.sceneBoundingRect().contains(pos):
                mouse_point = self.spectrum_plot.plotItem.vb.mapSceneToView(pos)
                freq_mhz = mouse_point.x()
                self.frequency_selected.emit(freq_mhz)
    
    def inject_real_data(self, fft_data: Any, freq_min: float, freq_max: float):
        """Inject real FFT data from SDR hardware"""
        if not HAS_PYQTGRAPH or fft_data is None:
            return
        
        try:
            data = np.asarray(fft_data)
            freqs = np.linspace(freq_min, freq_max, len(data))
            self.spectrum_curve.setData(freqs, data)
            
            # Update waterfall
            self._waterfall_history.append(data.copy())
            if len(self._waterfall_history) > self._max_waterfall_rows:
                self._waterfall_history.pop(0)
        except Exception as e:
            logger.debug(f"Error injecting spectrum data: {e}")


class ThothCommunicationsTab(QWidget):
    """
    SOTA 2026 Radio Communications Command Center
    =============================================
    Professional-grade RF communications interface featuring:
    - Full-screen spectrum analyzer with waterfall display
    - All frequency types: Bluetooth, Scalar, Radio, Ultrasonic, Robotics
    - Two-way send/receive signal interface
    - Fullscreen toggle for immersive operation
    """
    
    _scan_response_signal = pyqtSignal(dict)
    _status_response_signal = pyqtSignal(dict)
    _sonar_metrics_signal = pyqtSignal(dict)
    _radio_response_signal = pyqtSignal(str, dict)
    _radio_data_signal = pyqtSignal(dict)
    _call_response_signal = pyqtSignal(str, dict)
    _call_metrics_signal = pyqtSignal(dict)
    _vision_status_signal = pyqtSignal(dict)
    _log_signal = pyqtSignal(str)
    _spectrum_data_signal = pyqtSignal(object, float, float)  # FFT data, freq_min, freq_max

    def __init__(self, event_bus=None, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self._parent_window = parent
        # Fix layout: tab content must expand to fill the tab so it displays properly
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 300)

        # State tracking
        self._video_active = False
        self._sonar_active = False
        self._radio_rx_active = False
        self._radio_tx_active = False
        self._call_active = False
        self._is_fullscreen = False
        self._current_mode = "RX"  # "RX", "TX", or "DUPLEX"
        self._selected_channel: Optional[CommChannel] = None

        self._build_ui()
        self._wire_signals()
        self._subscribe_events()
        self._apply_cyberpunk_style()

    def _build_ui(self) -> None:
        """Build the SOTA 2026 Radio Communications Command Center UI"""
        self._main_layout = QVBoxLayout(self)
        # Small margin/spacing so frame borders never visually overlap child widgets
        self._main_layout.setContentsMargins(2, 2, 2, 2)
        self._main_layout.setSpacing(2)

        # ═══════════════════════════════════════════════════════════════════
        # TOP COMMAND BAR - Fullscreen toggle, mode selection, status
        # ═══════════════════════════════════════════════════════════════════
        self._build_command_bar()

        # ═══════════════════════════════════════════════════════════════════
        # MAIN CONTENT AREA - Spectrum + Controls (Splitter for resize)
        # ═══════════════════════════════════════════════════════════════════
        self._content_splitter = QSplitter(Qt.Orientation.Vertical)
        self._content_splitter.setHandleWidth(4)
        self._content_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # SPECTRUM ANALYZER (TOP - Takes most space when fullscreen)
        self._spectrum_container = QFrame()
        self._spectrum_container.setObjectName("spectrumContainer")
        self._spectrum_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        spectrum_layout = QVBoxLayout(self._spectrum_container)
        spectrum_layout.setContentsMargins(8, 8, 8, 8)
        # Extra spacing so the band selector frame border never draws through the spectrum widget
        spectrum_layout.setSpacing(8)
        
        # Frequency band selector bar
        self._build_band_selector(spectrum_layout)
        
        # Spectrum analyzer widget - reasonable height range for proper display
        self.spectrum_analyzer = SpectrumAnalyzerWidget(self)
        # Give the analyzer enough vertical room that its contents (including the
        self.spectrum_analyzer.setMinimumHeight(250)
        self.spectrum_analyzer.setMaximumHeight(400)  # Allow more room when needed
        self.spectrum_analyzer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.spectrum_analyzer.frequency_selected.connect(self._on_frequency_selected)
        # Pass event bus to spectrum analyzer for real SDR data access
        if self.event_bus:
            self.spectrum_analyzer.set_event_bus(self.event_bus)
        spectrum_layout.addWidget(self.spectrum_analyzer, stretch=1)
        
        self._content_splitter.addWidget(self._spectrum_container)

        # CONTROL PANELS (BOTTOM) - SOTA 2026 FIX: Proper scrollable controls
        # SPECTRUM CONTAINER - Must accommodate analyzer height with padding
        self._spectrum_container.setMinimumHeight(300)  # Match analyzer minimum + padding
        self._controls_container = QFrame()
        self._controls_container.setObjectName("controlsContainer")
        # CONTROLS CONTAINER - More reasonable minimum height
        self._controls_container.setMinimumHeight(350)  # Reduced from 500 - less restrictive
        self._controls_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        controls_layout = QVBoxLayout(self._controls_container)
        controls_layout.setContentsMargins(8, 8, 8, 8)
        controls_layout.setSpacing(8)
        
        # Scroll area so duplex + channel + legacy all visible when space is limited
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)  # Always show scrollbar
        controls_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        controls_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll_content = QWidget()
        # SOTA 2026 FIX: Set reasonable minimum height for scroll content
        scroll_content.setMinimumHeight(600)  # Reduced from 900 - enough for all control panels
        scroll_content_layout = QVBoxLayout(scroll_content)
        scroll_content_layout.setContentsMargins(0, 0, 12, 10)  # Right margin for scrollbar, reduced bottom margin
        scroll_content_layout.setSpacing(15)
        
        # Two-way communication panel (TX/RX)
        self._build_duplex_panel(scroll_content_layout)
        
        # Channel presets and quick actions
        self._build_channel_panel(scroll_content_layout)
        
        # Legacy communication groups (Video, Sonar, Radio, Call)
        self._build_legacy_groups(scroll_content_layout)
        
        # SOTA 2026 FIX: Add spacer at end to allow full scrolling to bottom
        scroll_content_layout.addStretch(1)
        
        controls_scroll.setWidget(scroll_content)
        controls_layout.addWidget(controls_scroll, stretch=1)  # Scroll area gets all stretch
        
        self._content_splitter.addWidget(self._controls_container)
        # SOTA 2026 FIX: More balanced splitter proportions
        self._content_splitter.setStretchFactor(0, 1)  # spectrum - normal stretch
        self._content_splitter.setStretchFactor(1, 1)  # controls - equal stretch (was 2)
        # Initial proportions - more balanced split
        self._content_splitter.setSizes([400, 400])  # Equal initial split
        # Allow collapsing spectrum to minimum to see more controls
        self._content_splitter.setCollapsible(0, False)  # Don't allow collapsing spectrum
        self._content_splitter.setCollapsible(1, False)  # Don't allow collapsing controls
        
        self._main_layout.addWidget(self._content_splitter, stretch=1)

        # ═══════════════════════════════════════════════════════════════════
        # BOTTOM STATUS BAR - Signal strength, frequency readout, log
        # ═══════════════════════════════════════════════════════════════════
        self._build_status_bar()

    def _build_command_bar(self) -> None:
        """Build top command bar with fullscreen toggle and mode selection"""
        command_bar = QFrame()
        command_bar.setObjectName("commandBar")
        command_bar.setFixedHeight(60)
        bar_layout = QHBoxLayout(command_bar)
        bar_layout.setContentsMargins(12, 8, 12, 8)
        bar_layout.setSpacing(12)

        # Title
        title = QLabel("📡 RADIO COMMS COMMAND CENTER")
        title.setObjectName("commandTitle")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff88;")
        bar_layout.addWidget(title)

        bar_layout.addStretch()

        # Mode selection: RX / TX / DUPLEX
        mode_label = QLabel("MODE:")
        mode_label.setStyleSheet("color: #a9b1d6; font-weight: bold;")
        bar_layout.addWidget(mode_label)

        self.mode_rx_btn = QPushButton("📥 RX")
        self.mode_rx_btn.setCheckable(True)
        self.mode_rx_btn.setChecked(True)
        self.mode_rx_btn.clicked.connect(lambda: self._set_mode("RX"))
        bar_layout.addWidget(self.mode_rx_btn)

        self.mode_tx_btn = QPushButton("📤 TX")
        self.mode_tx_btn.setCheckable(True)
        self.mode_tx_btn.clicked.connect(lambda: self._set_mode("TX"))
        bar_layout.addWidget(self.mode_tx_btn)

        self.mode_duplex_btn = QPushButton("🔄 DUPLEX")
        self.mode_duplex_btn.setCheckable(True)
        self.mode_duplex_btn.clicked.connect(lambda: self._set_mode("DUPLEX"))
        bar_layout.addWidget(self.mode_duplex_btn)

        bar_layout.addSpacing(20)

        # Scan interfaces button
        self.scan_button = QPushButton("🔍 Scan")
        self.scan_button.clicked.connect(self._on_scan_clicked)
        bar_layout.addWidget(self.scan_button)

        # Status refresh button
        self.status_button = QPushButton("🔄 Status")
        self.status_button.clicked.connect(self._on_status_clicked)
        bar_layout.addWidget(self.status_button)

        bar_layout.addSpacing(20)

        # Fullscreen toggle button
        self.fullscreen_btn = QPushButton("⛶ FULLSCREEN")
        self.fullscreen_btn.setObjectName("fullscreenBtn")
        self.fullscreen_btn.setCheckable(True)
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        bar_layout.addWidget(self.fullscreen_btn)

        self._main_layout.addWidget(command_bar)

    def _build_band_selector(self, parent_layout: QVBoxLayout) -> None:
        """Build frequency band quick-select buttons"""
        band_frame = QFrame()
        band_frame.setObjectName("bandSelector")
        band_layout = QHBoxLayout(band_frame)
        band_layout.setContentsMargins(4, 4, 4, 4)
        band_layout.setSpacing(4)

        band_label = QLabel("BAND:")
        band_label.setStyleSheet("color: #a9b1d6; font-weight: bold;")
        band_layout.addWidget(band_label)

        # Quick band buttons
        band_groups = [
            ("📻 Radio", [FrequencyBand.MF, FrequencyBand.HF, FrequencyBand.VHF, FrequencyBand.UHF]),
            ("📶 IoT", [FrequencyBand.BLUETOOTH, FrequencyBand.WIFI_24, FrequencyBand.ZIGBEE, FrequencyBand.LORA_EU]),
            ("🤖 RC", [FrequencyBand.RC_27MHZ, FrequencyBand.RC_433MHZ, FrequencyBand.RC_24GHZ]),
            ("🔊 Sonic", [FrequencyBand.ULTRASONIC]),
            ("⚡ Scalar", [FrequencyBand.SCALAR, FrequencyBand.ELF, FrequencyBand.VLF]),
            ("📱 Cell", [FrequencyBand.LTE, FrequencyBand.NR_5G]),
        ]

        self._band_buttons: Dict[str, QComboBox] = {}
        
        for group_name, bands in band_groups:
            group_btn = QComboBox()
            group_btn.setMinimumWidth(100)
            group_btn.addItem(group_name)
            for band in bands:
                group_btn.addItem(f"  {band.display_name}", band)
            group_btn.currentIndexChanged.connect(
                lambda idx, cb=group_btn: self._on_band_selected(cb, idx)
            )
            band_layout.addWidget(group_btn)
            self._band_buttons[group_name] = group_btn

        band_layout.addStretch()

        # Manual frequency input
        freq_label = QLabel("FREQ:")
        freq_label.setStyleSheet("color: #a9b1d6; font-weight: bold;")
        band_layout.addWidget(freq_label)

        self.freq_input = QDoubleSpinBox()
        self.freq_input.setRange(0.000001, 300000.0)
        self.freq_input.setDecimals(6)
        self.freq_input.setValue(100.0)
        self.freq_input.setSuffix(" MHz")
        self.freq_input.setMinimumWidth(140)
        self.freq_input.valueChanged.connect(self._on_freq_input_changed)
        band_layout.addWidget(self.freq_input)

        # Span control
        span_label = QLabel("SPAN:")
        span_label.setStyleSheet("color: #a9b1d6; font-weight: bold;")
        band_layout.addWidget(span_label)

        self.span_input = QDoubleSpinBox()
        self.span_input.setRange(0.001, 10000.0)
        self.span_input.setDecimals(3)
        self.span_input.setValue(20.0)
        self.span_input.setSuffix(" MHz")
        self.span_input.setMinimumWidth(100)
        self.span_input.valueChanged.connect(self._on_span_input_changed)
        band_layout.addWidget(self.span_input)

        # Start/Stop spectrum button
        self.spectrum_toggle = QPushButton("▶ START")
        self.spectrum_toggle.setCheckable(True)
        self.spectrum_toggle.clicked.connect(self._toggle_spectrum)
        band_layout.addWidget(self.spectrum_toggle)

        parent_layout.addWidget(band_frame)

    def _build_duplex_panel(self, parent_layout: QVBoxLayout) -> None:
        """Build two-way send/receive communication panel"""
        duplex_group = QGroupBox("📡 TWO-WAY SIGNAL TRANSCEIVER")
        duplex_group.setObjectName("duplexGroup")
        duplex_group.setMinimumHeight(260)
        duplex_layout = QGridLayout(duplex_group)
        duplex_layout.setContentsMargins(12, 16, 12, 12)
        duplex_layout.setSpacing(10)

        # Row 0: RX Section
        rx_label = QLabel("📥 RECEIVE (RX)")
        rx_label.setStyleSheet("font-weight: bold; color: #00ff88; font-size: 14px;")
        duplex_layout.addWidget(rx_label, 0, 0)

        self.rx_status = QLabel("● STANDBY")
        # This label doubles as the overall radio status indicator used by status handlers.
        # Keep a reference name that legacy code expects so we don't crash at runtime.
        self.radio_status_label = self.rx_status
        self.rx_status.setMinimumWidth(90)
        self.rx_status.setStyleSheet("color: #a9b1d6;")
        duplex_layout.addWidget(self.rx_status, 0, 1)

        self.rx_signal_bar = QProgressBar()
        self.rx_signal_bar.setRange(-120, 0)
        self.rx_signal_bar.setValue(-100)
        self.rx_signal_bar.setFormat("%v dBm")
        self.rx_signal_bar.setStyleSheet("""
            QProgressBar { background: #1a1b26; border: 1px solid #3b4261; border-radius: 4px; height: 20px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #00ff88, stop:0.5 #ffff00, stop:1 #ff0055); }
        """)
        duplex_layout.addWidget(self.rx_signal_bar, 0, 2)

        self.radio_rx_toggle = QPushButton("▶ START RX")
        self.radio_rx_toggle.setMinimumWidth(110)
        self.radio_rx_toggle.setCheckable(True)
        self.radio_rx_toggle.clicked.connect(self._on_radio_rx_toggled)
        duplex_layout.addWidget(self.radio_rx_toggle, 0, 3)

        # Let the signal bar column stretch to avoid buttons/text getting squeezed
        duplex_layout.setColumnStretch(0, 0)
        duplex_layout.setColumnStretch(1, 0)
        duplex_layout.setColumnStretch(2, 1)
        duplex_layout.setColumnStretch(3, 0)

        # Row 1: RX Data display
        self.rx_data_display = QTextEdit()
        self.rx_data_display.setReadOnly(True)
        self.rx_data_display.setMinimumHeight(120)
        self.rx_data_display.setPlaceholderText("Received data will appear here...")
        duplex_layout.addWidget(self.rx_data_display, 1, 0, 1, 4)

        # Row 2: TX Section
        tx_label = QLabel("📤 TRANSMIT (TX)")
        tx_label.setStyleSheet("font-weight: bold; color: #ff6b6b; font-size: 14px;")
        duplex_layout.addWidget(tx_label, 2, 0)

        self.tx_status = QLabel("● IDLE")
        self.tx_status.setStyleSheet("color: #a9b1d6;")
        duplex_layout.addWidget(self.tx_status, 2, 1)

        self.tx_power_slider = QSlider(Qt.Orientation.Horizontal)
        self.tx_power_slider.setRange(-30, 30)
        self.tx_power_slider.setValue(0)
        self.tx_power_slider.setTickInterval(10)
        self.tx_power_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        duplex_layout.addWidget(self.tx_power_slider, 2, 2)

        self.tx_power_label = QLabel("0 dBm")
        self.tx_power_label.setMinimumWidth(60)
        self.tx_power_slider.valueChanged.connect(
            lambda v: self.tx_power_label.setText(f"{v} dBm")
        )
        duplex_layout.addWidget(self.tx_power_label, 2, 3)

        # Row 3: TX Data input
        tx_input_layout = QHBoxLayout()
        self.tx_data_input = QLineEdit()
        self.tx_data_input.setPlaceholderText("Enter data to transmit...")
        tx_input_layout.addWidget(self.tx_data_input, stretch=1)

        self.radio_tx_button = QPushButton("📡 TRANSMIT")
        self.radio_tx_button.clicked.connect(self._on_radio_transmit_clicked)
        tx_input_layout.addWidget(self.radio_tx_button)

        duplex_layout.addLayout(tx_input_layout, 3, 0, 1, 4)

        parent_layout.addWidget(duplex_group)

    def _build_channel_panel(self, parent_layout: QVBoxLayout) -> None:
        """Build preset channel selection panel"""
        channel_group = QGroupBox("📻 CHANNEL PRESETS & PROTOCOLS")
        channel_group.setObjectName("channelGroup")
        channel_layout = QHBoxLayout(channel_group)
        channel_layout.setContentsMargins(12, 16, 12, 12)
        channel_layout.setSpacing(8)

        # Channel preset buttons
        for channel in PRESET_CHANNELS:
            btn = QPushButton(f"{channel.name}\n{channel.frequency_mhz:.2f} MHz")
            btn.setMinimumSize(100, 50)
            btn.setCheckable(True)
            btn.setProperty("channel", channel)
            btn.clicked.connect(lambda checked, ch=channel: self._select_channel(ch))
            channel_layout.addWidget(btn)

        channel_layout.addStretch()

        parent_layout.addWidget(channel_group)

    def _build_legacy_groups(self, parent_layout: QVBoxLayout) -> None:
        """Build legacy communication groups (Video, Sonar, Call) in tabs"""
        legacy_tabs = QTabWidget()
        legacy_tabs.setObjectName("legacyTabs")
        # SOTA 2026 FIX: Increase minimum height so tab contents are fully visible
        legacy_tabs.setMinimumHeight(280)
        legacy_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Video Tab
        video_tab = QWidget()
        self._build_video_group_content(video_tab)
        legacy_tabs.addTab(video_tab, "📹 Video")

        # Sonar Tab
        sonar_tab = QWidget()
        self._build_sonar_group_content(sonar_tab)
        legacy_tabs.addTab(sonar_tab, "🔊 Sonar")

        # Call Tab
        call_tab = QWidget()
        self._build_call_group_content(call_tab)
        legacy_tabs.addTab(call_tab, "📞 Voice Call")

        parent_layout.addWidget(legacy_tabs)

    def _build_video_group_content(self, parent: QWidget) -> None:
        """Build video stream controls"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.video_status_label = QLabel("Video: OFF")
        self.video_status_label.setStyleSheet("color: #a9b1d6;")
        top_row.addWidget(self.video_status_label)
        top_row.addStretch()

        self.video_toggle = QPushButton("Start Video")
        self.video_toggle.setCheckable(True)
        self.video_toggle.toggled.connect(self._on_video_toggled)
        top_row.addWidget(self.video_toggle)
        layout.addLayout(top_row)

        url_row = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setStyleSheet("color: #a9b1d6;")
        url_row.addWidget(url_label)

        self.video_url_input = QLineEdit()
        self.video_url_input.setPlaceholderText("http://<host>:8090/brio.mjpg")
        url_row.addWidget(self.video_url_input, stretch=1)

        self.video_default_button = QPushButton("Use Default")
        self.video_default_button.clicked.connect(self._on_video_use_default)
        url_row.addWidget(self.video_default_button)
        layout.addLayout(url_row)

        layout.addStretch()

    def _build_sonar_group_content(self, parent: QWidget) -> None:
        """Build sonar/ultrasonic distance sensor controls (SOTA 2026 - Device Takeover)"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.sonar_status_label = QLabel("Sonar: OFF")
        self.sonar_status_label.setStyleSheet("color: #a9b1d6;")
        top_row.addWidget(self.sonar_status_label)
        top_row.addStretch()

        self.sonar_toggle = QPushButton("Start Sonar")
        self.sonar_toggle.setCheckable(True)
        self.sonar_toggle.toggled.connect(self._on_sonar_toggled)
        top_row.addWidget(self.sonar_toggle)
        layout.addLayout(top_row)

        metrics_row = QHBoxLayout()
        self.sonar_distance_label = QLabel("Distance: -- cm")
        self.sonar_distance_label.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 14px;")
        metrics_row.addWidget(self.sonar_distance_label)

        self.sonar_rms_label = QLabel("RMS: --")
        self.sonar_rms_label.setStyleSheet("color: #a9b1d6;")
        metrics_row.addWidget(self.sonar_rms_label)

        self.sonar_peak_label = QLabel("Peak Hz: --")
        self.sonar_peak_label.setStyleSheet("color: #a9b1d6;")
        metrics_row.addWidget(self.sonar_peak_label)
        metrics_row.addStretch()
        layout.addLayout(metrics_row)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Device:"))
        self.sonar_device_combo = QComboBox()
        self.sonar_device_combo.setMinimumWidth(200)
        self.sonar_device_combo.setToolTip("Select a taken-over device with ultrasonic sensor")
        device_row.addWidget(self.sonar_device_combo, stretch=1)
        
        self.sonar_refresh_btn = QPushButton("🔄")
        self.sonar_refresh_btn.setToolTip("Refresh device list")
        self.sonar_refresh_btn.setMaximumWidth(30)
        self.sonar_refresh_btn.clicked.connect(self._refresh_sonar_devices)
        device_row.addWidget(self.sonar_refresh_btn)
        layout.addLayout(device_row)

        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("Trigger Pin:"))
        self.sonar_trig_input = QLineEdit("D2")
        self.sonar_trig_input.setMaximumWidth(50)
        self.sonar_trig_input.setToolTip("HC-SR04 trigger pin (e.g., D2)")
        config_row.addWidget(self.sonar_trig_input)

        config_row.addWidget(QLabel("Echo Pin:"))
        self.sonar_echo_input = QLineEdit("D3")
        self.sonar_echo_input.setMaximumWidth(50)
        self.sonar_echo_input.setToolTip("HC-SR04 echo pin (e.g., D3)")
        config_row.addWidget(self.sonar_echo_input)

        config_row.addWidget(QLabel("Interval (ms):"))
        self.sonar_interval_input = QSpinBox()
        self.sonar_interval_input.setRange(100, 5000)
        self.sonar_interval_input.setValue(500)
        self.sonar_interval_input.setToolTip("Reading interval in milliseconds")
        config_row.addWidget(self.sonar_interval_input)
        config_row.addStretch()
        layout.addLayout(config_row)

        layout.addStretch()
        
        QTimer.singleShot(1000, self._refresh_sonar_devices)

    def _build_call_group_content(self, parent: QWidget) -> None:
        """Build UDP voice call controls"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.call_status_label = QLabel("Call: OFF")
        self.call_status_label.setStyleSheet("color: #a9b1d6;")
        top_row.addWidget(self.call_status_label)
        top_row.addStretch()

        self.call_toggle = QPushButton("Start Call")
        self.call_toggle.setCheckable(True)
        self.call_toggle.toggled.connect(self._on_call_toggled)
        top_row.addWidget(self.call_toggle)
        layout.addLayout(top_row)

        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("Host:"))
        self.call_host_input = QLineEdit()
        self.call_host_input.setPlaceholderText("peer IP / hostname")
        config_row.addWidget(self.call_host_input, stretch=1)

        config_row.addWidget(QLabel("Port:"))
        self.call_port_input = QSpinBox()
        self.call_port_input.setRange(1, 65535)
        self.call_port_input.setValue(50000)
        config_row.addWidget(self.call_port_input)

        config_row.addWidget(QLabel("Local:"))
        self.call_local_port_input = QSpinBox()
        self.call_local_port_input.setRange(0, 65535)
        self.call_local_port_input.setValue(50000)
        config_row.addWidget(self.call_local_port_input)
        layout.addLayout(config_row)

        metrics_row = QHBoxLayout()
        self.call_tx_label = QLabel("TX: 0")
        self.call_tx_label.setStyleSheet("color: #a9b1d6;")
        metrics_row.addWidget(self.call_tx_label)

        self.call_rx_label = QLabel("RX: 0")
        self.call_rx_label.setStyleSheet("color: #a9b1d6;")
        metrics_row.addWidget(self.call_rx_label)

        self.call_queue_label = QLabel("Queue: 0")
        self.call_queue_label.setStyleSheet("color: #a9b1d6;")
        metrics_row.addWidget(self.call_queue_label)
        metrics_row.addStretch()
        layout.addLayout(metrics_row)

        # Audio config
        audio_row = QHBoxLayout()
        audio_row.addWidget(QLabel("SR:"))
        self.call_sample_rate_input = QSpinBox()
        self.call_sample_rate_input.setRange(8000, 192000)
        self.call_sample_rate_input.setValue(48000)
        audio_row.addWidget(self.call_sample_rate_input)

        audio_row.addWidget(QLabel("Block:"))
        self.call_blocksize_input = QSpinBox()
        self.call_blocksize_input.setRange(160, 4096)
        self.call_blocksize_input.setValue(960)
        audio_row.addWidget(self.call_blocksize_input)
        audio_row.addStretch()
        layout.addLayout(audio_row)

        layout.addStretch()

    def _build_status_bar(self) -> None:
        """Build bottom status bar with signal info and event log"""
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        # Status bar with reasonable minimum height
        status_bar.setMinimumHeight(100)  # Reduced from 120 - less restrictive
        bar_layout = QVBoxLayout(status_bar)
        bar_layout.setContentsMargins(8, 4, 8, 4)
        bar_layout.setSpacing(4)

        # Status row
        status_row = QHBoxLayout()
        
        self.freq_display = QLabel("FREQ: 100.000 MHz")
        self.freq_display.setStyleSheet("font-family: monospace; color: #00ff88; font-size: 14px;")
        status_row.addWidget(self.freq_display)

        status_row.addSpacing(20)

        self.signal_display = QLabel("SIGNAL: -100 dBm")
        self.signal_display.setStyleSheet("font-family: monospace; color: #ffff00;")
        status_row.addWidget(self.signal_display)

        status_row.addSpacing(20)

        self.mode_display = QLabel("MODE: RX")
        self.mode_display.setStyleSheet("font-family: monospace; color: #7aa2f7;")
        status_row.addWidget(self.mode_display)

        status_row.addStretch()

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(lambda: self.log_output.clear())
        status_row.addWidget(clear_log_btn)

        bar_layout.addLayout(status_row)

        # Event log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        # Allow the log area to shrink when vertical space is tight while still
        # growing nicely when the window is large.
        self.log_output.setMinimumHeight(80)
        self.log_output.setPlaceholderText("Event log...")
        bar_layout.addWidget(self.log_output)

        # Hidden scan output (for compatibility)
        self.scan_output = QTextEdit()
        self.scan_output.setVisible(False)

        self._main_layout.addWidget(status_bar)

    def _apply_cyberpunk_style(self) -> None:
        """Apply SOTA 2026 cyberpunk styling to the entire tab"""
        self.setStyleSheet("""
            /* Main container */
            ThothCommunicationsTab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0a0a12, stop:0.5 #1a1b26, stop:1 #0a0a12);
            }
            
            /* Command bar */
            #commandBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a1b26, stop:0.5 #24283b, stop:1 #1a1b26);
                border-bottom: 2px solid #00ff88;
            }
            
            /* Spectrum container */
            #spectrumContainer {
                background: #0a0a12;
                border: 1px solid #3b4261;
                border-radius: 8px;
            }
            
            /* Band selector */
            #bandSelector {
                background: #1a1b26;
                border: 1px solid #3b4261;
                border-radius: 4px;
            }
            
            /* Controls container */
            #controlsContainer {
                background: #0d0d14;
                border: 1px solid #3b4261;
                border-radius: 8px;
            }
            
            /* Status bar */
            #statusBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a1b26, stop:0.5 #24283b, stop:1 #1a1b26);
                border-top: 2px solid #7aa2f7;
            }
            
            /* Buttons */
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b4261, stop:1 #2a2f4a);
                color: #c0caf5;
                border: 1px solid #4a4f6a;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a5271, stop:1 #3a3f5a);
                border-color: #7aa2f7;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00aa66, stop:1 #007744);
                border-color: #00ff88;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #2a2f4a;
            }
            
            /* Fullscreen button special styling */
            #fullscreenBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7aa2f7, stop:1 #5a82d7);
                color: #ffffff;
                font-size: 14px;
                padding: 10px 20px;
            }
            #fullscreenBtn:checked {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff6b6b, stop:1 #cc4444);
                border-color: #ff0055;
            }
            
            /* Group boxes */
            QGroupBox {
                background: #1a1b26;
                border: 2px solid #3b4261;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
                font-weight: bold;
                color: #7aa2f7;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #00ff88;
            }
            
            /* Duplex group special */
            #duplexGroup {
                border-color: #00ff88;
            }
            
            /* Channel group */
            #channelGroup {
                border-color: #ff6b6b;
            }
            
            /* Text inputs */
            QLineEdit, QTextEdit {
                background: #1a1b26;
                color: #c0caf5;
                border: 1px solid #3b4261;
                border-radius: 4px;
                padding: 6px;
                selection-background-color: #7aa2f7;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #7aa2f7;
            }
            
            /* Spin boxes */
            QSpinBox, QDoubleSpinBox {
                background: #1a1b26;
                color: #c0caf5;
                border: 1px solid #3b4261;
                border-radius: 4px;
                padding: 4px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #7aa2f7;
            }
            
            /* Combo boxes */
            QComboBox {
                background: #1a1b26;
                color: #c0caf5;
                border: 1px solid #3b4261;
                border-radius: 4px;
                padding: 6px;
            }
            QComboBox:hover {
                border-color: #7aa2f7;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background: #1a1b26;
                color: #c0caf5;
                selection-background-color: #3b4261;
            }
            
            /* Tab widget */
            QTabWidget::pane {
                background: #1a1b26;
                border: 1px solid #3b4261;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #2a2f4a;
                color: #a9b1d6;
                border: 1px solid #3b4261;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #3b4261;
                color: #00ff88;
                border-bottom-color: transparent;
            }
            QTabBar::tab:hover {
                background: #3b4261;
            }
            
            /* Progress bars */
            QProgressBar {
                background: #1a1b26;
                border: 1px solid #3b4261;
                border-radius: 4px;
                text-align: center;
                color: #c0caf5;
            }
            
            /* Sliders */
            QSlider::groove:horizontal {
                background: #1a1b26;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #7aa2f7;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #00ff88;
            }
            
            /* Splitter */
            QSplitter::handle {
                background: #3b4261;
            }
            QSplitter::handle:hover {
                background: #7aa2f7;
            }
            
            /* Labels */
            QLabel {
                color: #a9b1d6;
            }
            
            /* Scrollbars */
            QScrollBar:vertical {
                background: #1a1b26;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #3b4261;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #7aa2f7;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    # ═══════════════════════════════════════════════════════════════════════
    # NEW SOTA 2026 EVENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════

    def _set_mode(self, mode: str) -> None:
        """Set communication mode: RX, TX, or DUPLEX"""
        self._current_mode = mode
        self.mode_rx_btn.setChecked(mode == "RX")
        self.mode_tx_btn.setChecked(mode == "TX")
        self.mode_duplex_btn.setChecked(mode == "DUPLEX")
        self.mode_display.setText(f"MODE: {mode}")
        self._append_log(f"Mode changed to {mode}")

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode - spectrum takes whole screen"""
        self._is_fullscreen = not self._is_fullscreen
        
        if self._is_fullscreen:
            # Hide controls, maximize spectrum
            self._controls_container.hide()
            available_height = max(1, self.height())
            # Give essentially all space to the spectrum area
            self._content_splitter.setSizes([available_height - 1, 1])
            self.fullscreen_btn.setText("✕ EXIT FULLSCREEN")
            self._append_log("Entered fullscreen mode")
        else:
            # Show controls, restore normal view
            self._controls_container.show()
            available_height = max(1, self.height())
            # Default back to a 65/35 split without enforcing a huge minimum on the bottom.
            top = int(available_height * 0.65)
            bottom = max(self._controls_container.minimumHeight(), available_height - top)
            self._content_splitter.setSizes([top, bottom])
            self.fullscreen_btn.setText("⛶ FULLSCREEN")
            self._append_log("Exited fullscreen mode")

    def _toggle_spectrum(self) -> None:
        """Start/stop spectrum analyzer"""
        if self.spectrum_toggle.isChecked():
            self.spectrum_analyzer.start_spectrum()
            self.spectrum_toggle.setText("⏹ STOP")
            self._append_log("Spectrum analyzer started")
            # region agent log
            try:
                with open("debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "pre-fix",
                        "hypothesisId": "C2",
                        "location": "thoth_comms_tab.py:ThothCommunicationsTab:_toggle_spectrum:on",
                        "message": "Spectrum toggled ON",
                        "data": {},
                        "timestamp": int(time.time() * 1000),
                    }) + "\n")
            except Exception:
                pass
            # endregion
        else:
            self.spectrum_analyzer.stop_spectrum()
            self.spectrum_toggle.setText("▶ START")
            self._append_log("Spectrum analyzer stopped")
            # region agent log
            try:
                with open("debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "pre-fix",
                        "hypothesisId": "C2",
                        "location": "thoth_comms_tab.py:ThothCommunicationsTab:_toggle_spectrum:off",
                        "message": "Spectrum toggled OFF",
                        "data": {},
                        "timestamp": int(time.time() * 1000),
                    }) + "\n")
            except Exception:
                pass
            # endregion

    def _on_band_selected(self, combo: QComboBox, idx: int) -> None:
        """Handle frequency band selection from dropdown"""
        if idx == 0:
            return  # Header item selected
        
        band = combo.itemData(idx)
        if band and isinstance(band, FrequencyBand):
            self.spectrum_analyzer.set_band(band)
            center = (band.freq_min_mhz + band.freq_max_mhz) / 2
            self.freq_input.setValue(center)
            self.freq_display.setText(f"FREQ: {center:.3f} MHz")
            self._append_log(f"Selected band: {band.display_name} ({band.freq_min_mhz:.3f} - {band.freq_max_mhz:.3f} MHz)")

    def _on_freq_input_changed(self, value: float) -> None:
        """Handle manual frequency input change"""
        self.spectrum_analyzer.set_center_frequency(value)
        self.freq_display.setText(f"FREQ: {value:.6f} MHz")

    def _on_span_input_changed(self, value: float) -> None:
        """Handle span input change"""
        self.spectrum_analyzer.set_span(value)

    def _on_frequency_selected(self, freq_mhz: float) -> None:
        """Handle frequency selection from spectrum click"""
        self.freq_input.setValue(freq_mhz)
        self.freq_display.setText(f"FREQ: {freq_mhz:.6f} MHz")
        self._append_log(f"Selected frequency: {freq_mhz:.6f} MHz")

    def _select_channel(self, channel: CommChannel) -> None:
        """Select a preset channel"""
        self._selected_channel = channel
        self.freq_input.setValue(channel.frequency_mhz)
        self.spectrum_analyzer.set_center_frequency(channel.frequency_mhz)
        self.spectrum_analyzer.set_span(channel.bandwidth_khz / 1000 * 10)  # 10x bandwidth for span
        self.freq_display.setText(f"FREQ: {channel.frequency_mhz:.3f} MHz")
        
        # Set mode based on channel direction
        if channel.direction == "TX":
            self._set_mode("TX")
        elif channel.direction == "RX":
            self._set_mode("RX")
        else:
            self._set_mode("DUPLEX")
        
        self._append_log(f"Selected channel: {channel.name} @ {channel.frequency_mhz} MHz ({channel.protocol})")

    def _on_radio_rx_toggled(self, checked: bool = None) -> None:
        """Handle RX toggle - wrapper for compatibility"""
        if checked is None:
            checked = self.radio_rx_toggle.isChecked()
        
        if not self.event_bus:
            return

        freq_mhz = float(self.freq_input.value())
        if checked:
            self._append_log(f"Starting RX @ {freq_mhz:.6f} MHz")
            self.rx_status.setText("● RECEIVING")
            self.rx_status.setStyleSheet("color: #00ff88;")
            self.radio_rx_toggle.setText("⏹ STOP RX")
            self.event_bus.publish("comms.radio.receive.start", {"frequency_mhz": freq_mhz})
        else:
            self._append_log("Stopping RX")
            self.rx_status.setText("● STANDBY")
            self.rx_status.setStyleSheet("color: #a9b1d6;")
            self.radio_rx_toggle.setText("▶ START RX")
            self.event_bus.publish("comms.radio.receive.stop", {})

    def _on_radio_transmit_clicked(self) -> None:
        """Handle transmit button click"""
        if not self.event_bus:
            return

        freq_mhz = float(self.freq_input.value())
        payload_text = self.tx_data_input.text().strip()
        power_dbm = self.tx_power_slider.value()
        
        if not payload_text:
            self._append_log("TX Error: No data to transmit")
            return
        
        self._append_log(f"Transmitting @ {freq_mhz:.6f} MHz, {power_dbm} dBm: {payload_text[:50]}...")
        self.tx_status.setText("● TRANSMITTING")
        self.tx_status.setStyleSheet("color: #ff6b6b;")
        
        self.event_bus.publish(
            "comms.radio.transmit",
            {
                "frequency_mhz": freq_mhz,
                "payload": payload_text,
                "power_dbm": power_dbm,
            },
        )
        
        # Reset status after brief delay
        QTimer.singleShot(1000, lambda: self._reset_tx_status())

    def _reset_tx_status(self) -> None:
        """Reset TX status indicator"""
        self.tx_status.setText("● IDLE")
        self.tx_status.setStyleSheet("color: #a9b1d6;")

    # ═══════════════════════════════════════════════════════════════════════
    # LEGACY COMPATIBILITY - Keep old method signatures working
    # ═══════════════════════════════════════════════════════════════════════

    def _build_video_group(self, parent_layout: QVBoxLayout) -> None:
        """Legacy: Build video group — delegates to tabbed implementation."""
        if hasattr(self, '_build_video_group_content'):
            self._build_video_group_content(parent_layout)
        else:
            self._append_log("Video group: using tabbed UI")

    def _build_sonar_group(self, parent_layout: QVBoxLayout) -> None:
        """Legacy: Build sonar group — delegates to tabbed implementation."""
        if hasattr(self, '_build_sonar_group_content'):
            self._build_sonar_group_content(parent_layout)
        else:
            self._append_log("Sonar group: using tabbed UI")

    def _build_radio_group(self, parent_layout: QVBoxLayout) -> None:
        """Legacy: Build radio group — delegates to duplex panel."""
        if hasattr(self, '_build_duplex_panel'):
            self._build_duplex_panel(parent_layout)
        else:
            self._append_log("Radio group: using duplex panel UI")

    def _build_call_group(self, parent_layout: QVBoxLayout) -> None:
        """Legacy: Build call group — delegates to tabbed implementation."""
        if hasattr(self, '_build_call_group_content'):
            self._build_call_group_content(parent_layout)
        else:
            self._append_log("Call group: using tabbed UI")

    def _expand_all_groups(self) -> None:
        """Legacy: Expand all groups - not applicable in new UI"""
        self._append_log("All panels expanded")

    def _collapse_all_groups(self) -> None:
        """Legacy: Collapse all groups - not applicable in new UI"""
        self._append_log("All panels collapsed")

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL WIRING AND EVENT SUBSCRIPTIONS  
    # ═══════════════════════════════════════════════════════════════════════

    def _wire_signals(self) -> None:
        self._scan_response_signal.connect(self._handle_scan_response_ui)
        self._status_response_signal.connect(self._handle_status_response_ui)
        self._sonar_metrics_signal.connect(self._handle_sonar_metrics_ui)
        self._radio_response_signal.connect(self._handle_radio_response_ui)
        self._radio_data_signal.connect(self._handle_radio_data_ui)
        self._call_response_signal.connect(self._handle_call_response_ui)
        self._call_metrics_signal.connect(self._handle_call_metrics_ui)
        self._vision_status_signal.connect(self._handle_vision_status_ui)
        self._log_signal.connect(self._append_log)

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return

        subscribe = getattr(self.event_bus, "subscribe_sync", None) or getattr(self.event_bus, "subscribe", None)
        if not callable(subscribe):
            return

        subscribe("comms.scan.response", self._on_scan_response)
        subscribe("comms.status.response", self._on_status_response)
        subscribe("comms.sonar.metrics", self._on_sonar_metrics)
        subscribe("comms.radio.transmit.response", lambda d: self._on_radio_response("transmit", d))
        subscribe("comms.radio.receive.start.response", lambda d: self._on_radio_response("rx_start", d))
        subscribe("comms.radio.receive.stop.response", lambda d: self._on_radio_response("rx_stop", d))
        subscribe("comms.radio.receive.data", self._on_radio_data)
        subscribe("comms.call.start.response", lambda d: self._on_call_response("start", d))
        subscribe("comms.call.stop.response", lambda d: self._on_call_response("stop", d))
        subscribe("comms.call.status.response", lambda d: self._on_call_response("status", d))
        subscribe("comms.call.metrics", self._on_call_metrics)
        subscribe("vision.stream.status", self._on_vision_status)
        subscribe("comms.spectrum.data", self._on_spectrum_data_event)

    def _on_scan_clicked(self) -> None:
        if not self.event_bus:
            return
        self._append_log("Publishing comms.scan")
        self.event_bus.publish("comms.scan", {})

    def _on_status_clicked(self) -> None:
        if not self.event_bus:
            return
        self._append_log("Publishing comms.status.request")
        self.event_bus.publish("comms.status.request", {})

    def _on_video_use_default(self) -> None:
        if self.video_url_input.text().strip():
            return
        default_url = self._infer_default_mjpeg_url()
        if default_url:
            self.video_url_input.setText(default_url)

    def _on_video_toggled(self, checked: bool) -> None:
        if not self.event_bus:
            return

        if checked:
            payload: Dict[str, Any] = {}
            url = self.video_url_input.text().strip()
            if url:
                payload["url"] = url
            self.video_status_label.setText("Video: starting...")
            self.video_status_label.setStyleSheet("color: #FFFF00; border: none;")
            self._append_log(f"Publishing comms.video.start ({'custom url' if url else 'default'})")
            self.event_bus.publish("comms.video.start", payload)
        else:
            self.video_status_label.setText("Video: stopping...")
            self.video_status_label.setStyleSheet("color: #FFFF00; border: none;")
            self._append_log("Publishing comms.video.stop")
            self.event_bus.publish("comms.video.stop", {})

    def _on_sonar_toggled(self, checked: bool) -> None:
        if not self.event_bus:
            return

        if checked:
            device_id = self.sonar_device_combo.currentData()
            if not device_id:
                self.sonar_status_label.setText("Sonar: No device selected!")
                self.sonar_status_label.setStyleSheet("color: #f7768e; border: none;")
                self.sonar_toggle.setChecked(False)
                return
            
            payload: Dict[str, Any] = {
                "device_id": device_id,
                "trigger_pin": self.sonar_trig_input.text().strip() or "D2",
                "echo_pin": self.sonar_echo_input.text().strip() or "D3",
                "interval_ms": int(self.sonar_interval_input.value()),
            }

            self.sonar_status_label.setText("Sonar: starting...")
            self.sonar_status_label.setStyleSheet("color: #FFFF00; border: none;")
            self._append_log(f"Publishing comms.sonar.start for device {device_id}")
            self.event_bus.publish("comms.sonar.start", payload)
        else:
            self.sonar_status_label.setText("Sonar: stopping...")
            self.sonar_status_label.setStyleSheet("color: #FFFF00; border: none;")
            self._append_log("Publishing comms.sonar.stop")
            self.event_bus.publish("comms.sonar.stop", {})
    
    def _refresh_sonar_devices(self) -> None:
        """Refresh the list of available devices for sonar (taken-over microcontrollers)."""
        self.sonar_device_combo.clear()
        self.sonar_device_combo.addItem("-- Select Device --", None)
        
        try:
            host_device_manager = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                host_device_manager = self.event_bus.get_component('host_device_manager', silent=True)
            
            if not host_device_manager:
                try:
                    from core.host_device_manager import get_host_device_manager
                    host_device_manager = get_host_device_manager()
                except Exception:
                    pass
            
            if host_device_manager:
                takeover_manager = getattr(host_device_manager, '_takeover_manager', None)
                if takeover_manager:
                    taken_over = takeover_manager.list_taken_over_devices()
                    for device_id, info in taken_over.items():
                        name = info.get('name', device_id)
                        port = info.get('port', '')
                        self.sonar_device_combo.addItem(f"✅ {name} ({port})", device_id)
                
                all_devices = host_device_manager.get_all_devices()
                mcu_categories = ['arduino', 'esp32', 'stm32', 'teensy', 'pico', 'serial']
                for dev in all_devices:
                    cat = getattr(dev, 'category', None)
                    cat_value = cat.value if hasattr(cat, 'value') else str(cat)
                    if cat_value in mcu_categories:
                        dev_id = getattr(dev, 'id', None)
                        dev_name = getattr(dev, 'name', dev_id)
                        if dev_id and not any(self.sonar_device_combo.itemData(i) == dev_id 
                                               for i in range(self.sonar_device_combo.count())):
                            self.sonar_device_combo.addItem(f"📟 {dev_name}", dev_id)
        except Exception as e:
            self._append_log(f"Error refreshing sonar devices: {e}")

    def _on_call_toggled(self, checked: bool) -> None:
        if not self.event_bus:
            return

        if checked:
            host = self.call_host_input.text().strip() or "127.0.0.1"
            port = int(self.call_port_input.value())
            local_port = int(self.call_local_port_input.value())
            payload: Dict[str, Any] = {
                "remote_host": host,
                "remote_port": port,
                "sample_rate": int(self.call_sample_rate_input.value()),
                "blocksize": int(self.call_blocksize_input.value()),
                "channels": 1,
            }
            if local_port > 0:
                payload["local_port"] = local_port
            self.call_status_label.setText("Call: starting...")
            self.call_status_label.setStyleSheet("color: #FFFF00; border: none;")
            self._append_log(f"Publishing comms.call.start ({host}:{port})")
            self.event_bus.publish("comms.call.start", payload)
        else:
            self.call_status_label.setText("Call: stopping...")
            self.call_status_label.setStyleSheet("color: #FFFF00; border: none;")
            self._append_log("Publishing comms.call.stop")
            self.event_bus.publish("comms.call.stop", {})

    def _on_scan_response(self, data: Any) -> None:
        if isinstance(data, dict):
            self._scan_response_signal.emit(data)

    def _on_status_response(self, data: Any) -> None:
        if isinstance(data, dict):
            self._status_response_signal.emit(data)

    def _on_sonar_metrics(self, data: Any) -> None:
        if isinstance(data, dict):
            self._sonar_metrics_signal.emit(data)

    def _on_radio_response(self, kind: str, data: Any) -> None:
        if isinstance(data, dict):
            self._radio_response_signal.emit(kind, data)

    def _on_radio_data(self, data: Any) -> None:
        if isinstance(data, dict):
            self._radio_data_signal.emit(data)

    def _on_call_response(self, kind: str, data: Any) -> None:
        if isinstance(data, dict):
            self._call_response_signal.emit(kind, data)

    def _on_call_metrics(self, data: Any) -> None:
        if isinstance(data, dict):
            self._call_metrics_signal.emit(data)

    def _on_vision_status(self, data: Any) -> None:
        if isinstance(data, dict):
            self._vision_status_signal.emit(data)
    
    def _on_spectrum_data_event(self, data: Any) -> None:
        """Handle real spectrum FFT data from SDR hardware."""
        if isinstance(data, dict) and self.spectrum_analyzer:
            fft_data = data.get('fft_data')
            freq_min = data.get('freq_min')
            freq_max = data.get('freq_max')
            if fft_data is not None and freq_min is not None and freq_max is not None:
                self.spectrum_analyzer.inject_real_data(fft_data, freq_min, freq_max)

    def _handle_scan_response_ui(self, payload: dict) -> None:
        success = bool(payload.get("success"))
        data = payload.get("data") if success else None
        if isinstance(data, dict):
            self.scan_output.setPlainText(self._format_scan(data))
            mjpeg_url = (
                ((data.get("video") or {}).get("mjpeg_url"))
                if isinstance(data.get("video"), dict)
                else None
            )
            if mjpeg_url and not self.video_url_input.text().strip():
                self.video_url_input.setText(str(mjpeg_url))
        else:
            self.scan_output.setPlainText(f"Scan failed: {payload}")

        self._append_log("Received comms.scan.response")

    def _handle_status_response_ui(self, payload: dict) -> None:
        success = bool(payload.get("success"))
        data = payload.get("data") if success else None
        if not isinstance(data, dict):
            self._append_log(f"comms.status.response error: {payload}")
            return

        sonar = data.get("sonar") if isinstance(data.get("sonar"), dict) else {}
        listening = bool(sonar.get("listening"))
        backend = sonar.get("backend")

        self._sonar_active = listening
        self._set_checked(self.sonar_toggle, listening)

        self.sonar_status_label.setText(
            f"Sonar: {'ON' if listening else 'OFF'}" + (f" ({backend})" if backend else "")
        )
        self.sonar_status_label.setStyleSheet(
            "color: #9ece6a; border: none;" if listening else "color: #a9b1d6; border: none;"
        )

        last = sonar.get("last") if isinstance(sonar.get("last"), dict) else {}
        if last:
            rms = last.get("rms")
            peak = last.get("peak_hz")
            if rms is not None:
                self.sonar_rms_label.setText(f"RMS: {rms:.4f}" if isinstance(rms, (int, float)) else f"RMS: {rms}")
            if peak is not None:
                self.sonar_peak_label.setText(
                    f"Peak Hz: {peak:.1f}" if isinstance(peak, (int, float)) else f"Peak Hz: {peak}"
                )

        radio = data.get("radio") if isinstance(data.get("radio"), dict) else {}
        rx_active = bool(radio.get("rx_active"))
        if rx_active != self._radio_rx_active:
            self._radio_rx_active = rx_active
            self._set_checked(self.radio_rx_toggle, rx_active)
            if rx_active:
                self.radio_status_label.setText("Radio: RX ON")
                self.radio_status_label.setStyleSheet("color: #9ece6a; border: none;")
            else:
                self.radio_status_label.setText("Radio: idle")
                self.radio_status_label.setStyleSheet("color: #a9b1d6; border: none;")

        call = data.get("call") if isinstance(data.get("call"), dict) else {}
        call_active = bool(call.get("active"))
        self._call_active = call_active
        self._set_checked(self.call_toggle, call_active)
        remote = call.get("remote")
        if call_active:
            remote_txt = f" ({remote})" if remote else ""
            self.call_status_label.setText(f"Call: ON{remote_txt}")
            self.call_status_label.setStyleSheet("color: #9ece6a; border: none;")
        else:
            self.call_status_label.setText("Call: OFF")
            self.call_status_label.setStyleSheet("color: #a9b1d6; border: none;")
        self.call_tx_label.setText(f"TX: {call.get('tx_packets', 0)}")
        self.call_rx_label.setText(f"RX: {call.get('rx_packets', 0)}")
        self.call_queue_label.setText(f"Queue: {call.get('rx_queue', 0)}")

        self._append_log("Received comms.status.response")

    def _handle_sonar_metrics_ui(self, payload: dict) -> None:
        distance = payload.get("distance_cm")
        rms = payload.get("rms")
        peak = payload.get("peak_hz")
        device_id = payload.get("device_id")
        backend = payload.get("backend", "unknown")

        if distance is not None:
            if isinstance(distance, (int, float)) and distance >= 0:
                self.sonar_distance_label.setText(f"Distance: {distance:.1f} cm")
                self.sonar_distance_label.setStyleSheet("color: #9ece6a; font-weight: bold; font-size: 14px;")
            else:
                self.sonar_distance_label.setText("Distance: OUT OF RANGE")
                self.sonar_distance_label.setStyleSheet("color: #f7768e; font-weight: bold; font-size: 14px;")

        if rms is not None:
            self.sonar_rms_label.setText(f"RMS: {rms:.4f}" if isinstance(rms, (int, float)) else f"RMS: {rms}")
        if peak is not None:
            self.sonar_peak_label.setText(
                f"Peak Hz: {peak:.1f}" if isinstance(peak, (int, float)) else f"Peak Hz: {peak}"
            )

        if not self._sonar_active:
            self._sonar_active = True
            status_text = f"Sonar: ON ({backend})"
            if device_id:
                status_text = f"Sonar: ON - {device_id[:20]}"
            self.sonar_status_label.setText(status_text)
            self.sonar_status_label.setStyleSheet("color: #9ece6a; border: none;")

    def _handle_radio_response_ui(self, kind: str, payload: dict) -> None:
        self._append_log(f"Radio response ({kind}): {payload}")

        success = bool(payload.get("success"))
        if kind == "rx_start":
            self._radio_rx_active = success
            if success:
                self.radio_status_label.setText("Radio: RX ON")
                self.radio_status_label.setStyleSheet("color: #9ece6a; border: none;")
            else:
                self._set_checked(self.radio_rx_toggle, False)
                self.radio_status_label.setText("Radio: RX ERROR")
                self.radio_status_label.setStyleSheet("color: #f7768e; border: none;")
        elif kind == "rx_stop":
            self._radio_rx_active = False
            self.radio_status_label.setText("Radio: idle")
            self.radio_status_label.setStyleSheet("color: #a9b1d6; border: none;")
            self._set_checked(self.radio_rx_toggle, False)

    def _handle_radio_data_ui(self, payload: dict) -> None:
        try:
            text = payload.get("payload")
            hz = (payload.get("config") or {}).get("frequency_hz")
            freq_str = f"{float(hz) / 1_000_000.0:.6f} MHz" if isinstance(hz, (int, float)) else ""
            self._append_log(f"Radio RX data {freq_str}: {text}")
        except Exception:
            self._append_log(f"Radio RX data: {payload}")

    def _handle_call_response_ui(self, kind: str, payload: dict) -> None:
        self._append_log(f"Call response ({kind}): {payload}")
        success = bool(payload.get("success"))
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if kind == "start":
            self._call_active = success
            if success:
                self.call_status_label.setText("Call: ON")
                self.call_status_label.setStyleSheet("color: #9ece6a; border: none;")
            else:
                self.call_status_label.setText("Call: ERROR")
                self.call_status_label.setStyleSheet("color: #f7768e; border: none;")
                self._set_checked(self.call_toggle, False)
        elif kind == "stop":
            self._call_active = False
            self.call_status_label.setText("Call: OFF")
            self.call_status_label.setStyleSheet("color: #a9b1d6; border: none;")
            self._set_checked(self.call_toggle, False)

        if data:
            self.call_tx_label.setText(f"TX: {data.get('tx_packets', 0)}")
            self.call_rx_label.setText(f"RX: {data.get('rx_packets', 0)}")
            self.call_queue_label.setText(f"Queue: {data.get('rx_queue', 0)}")

    def _handle_call_metrics_ui(self, payload: dict) -> None:
        active = bool(payload.get("active"))
        self._call_active = active
        if active and "remote" in payload:
            self.call_status_label.setText(f"Call: ON ({payload.get('remote')})")
            self.call_status_label.setStyleSheet("color: #9ece6a; border: none;")
        elif not active:
            self.call_status_label.setText("Call: OFF")
            self.call_status_label.setStyleSheet("color: #a9b1d6; border: none;")
        self._set_checked(self.call_toggle, active)
        self.call_tx_label.setText(f"TX: {payload.get('tx_packets', 0)}")
        self.call_rx_label.setText(f"RX: {payload.get('rx_packets', 0)}")
        self.call_queue_label.setText(f"Queue: {payload.get('rx_queue', 0)}")

    def _handle_vision_status_ui(self, payload: dict) -> None:
        active = bool(payload.get("active", False))
        url = payload.get("url")
        error = payload.get("error")

        self._video_active = active

        if error:
            self.video_status_label.setText(f"Video: ERROR ({error})")
            self.video_status_label.setStyleSheet("color: #f7768e; border: none;")
        else:
            if active:
                text = "Video: ON"
                if url:
                    text += f" ({url})"
                self.video_status_label.setText(text)
                self.video_status_label.setStyleSheet("color: #9ece6a; border: none;")
            else:
                self.video_status_label.setText("Video: OFF")
                self.video_status_label.setStyleSheet("color: #a9b1d6; border: none;")

        self._set_checked(self.video_toggle, active)

    def _append_log(self, message: str) -> None:
        try:
            self.log_output.append(message)
        except Exception:
            pass

    def _infer_default_mjpeg_url(self) -> Optional[str]:
        if not self.event_bus or not hasattr(self.event_bus, "get_component"):
            return None
        try:
            comms = self.event_bus.get_component("communication_capabilities", silent=True)
        except TypeError:
            try:
                comms = self.event_bus.get_component("communication_capabilities")
            except Exception:
                comms = None
        except Exception:
            comms = None

        if comms is None or not callable(getattr(comms, "scan_interfaces", None)):
            return None

        try:
            info = comms.scan_interfaces()
        except Exception:
            return None

        if not isinstance(info, dict):
            return None

        video = info.get("video")
        if isinstance(video, dict):
            url = video.get("mjpeg_url")
            if url:
                return str(url)

        return None

    def _set_checked(self, button: QPushButton, checked: bool) -> None:
        try:
            was_blocked = button.blockSignals(True)
            button.setChecked(bool(checked))
            button.blockSignals(was_blocked)
            if button is self.video_toggle:
                button.setText("Stop Video" if checked else "Start Video")
            elif button is self.sonar_toggle:
                button.setText("Stop Sonar" if checked else "Start Sonar")
            elif button is self.radio_rx_toggle:
                button.setText("Stop RX" if checked else "Start RX")
            elif button is self.call_toggle:
                button.setText("Stop Call" if checked else "Start Call")
        except Exception:
            pass

    def _format_scan(self, data: Dict[str, Any]) -> str:
        audio = data.get("audio") if isinstance(data.get("audio"), dict) else {}
        video = data.get("video") if isinstance(data.get("video"), dict) else {}
        radio = data.get("radio") if isinstance(data.get("radio"), dict) else {}
        call = data.get("call") if isinstance(data.get("call"), dict) else {}

        lines = []
        lines.append("COMMUNICATION SCAN")
        lines.append("")
        lines.append(f"Audio: default mic index = {audio.get('default_mic_index')}")
        lines.append(f"Video: default webcam index = {video.get('default_webcam_index')}")
        lines.append(f"Video: MJPEG URL = {video.get('mjpeg_url')}")
        lines.append("")

        sdr_tools = radio.get("sdr_tools") if isinstance(radio.get("sdr_tools"), dict) else {}
        python_mods = radio.get("python_modules") if isinstance(radio.get("python_modules"), dict) else {}
        tools_present = [k for k, v in sdr_tools.items() if v]
        mods_present = [k for k, v in python_mods.items() if v]

        lines.append(f"Radio/SDR tools detected = {tools_present if tools_present else 'none'}")
        lines.append(f"Radio/SDR python modules detected = {mods_present if mods_present else 'none'}")
        soapy = radio.get("soapy_devices") if isinstance(radio.get("soapy_devices"), list) else []
        if soapy:
            lines.append(f"Radio/SoapySDR devices detected = {len(soapy)}")
        udp_voice = call.get("udp_voice") if isinstance(call.get("udp_voice"), dict) else {}
        supported = udp_voice.get("supported")
        lines.append(f"Call (UDP voice) supported = {supported}")
        return "\n".join(lines)
