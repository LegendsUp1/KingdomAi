"""
Kingdom AI — Health Dashboard Tab
SOTA 2026: Real-time wearable health monitoring GUI.

Displays:
  - Real-time heart rate, HRV, SpO2, stress, body temperature
  - Connected wearable devices
  - Health trend charts (rolling 24h)
  - AI health insights from HealthAdvisor
  - Anomaly alerts from HealthAnomalyDetector
  - BLE device scanner
  - Protection status (dormant/active flags)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QScrollArea, QTextEdit, QFrame,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger("KingdomAI.GUI.HealthDashboard")

CYAN = "#00FFFF"
NEON_GREEN = "#39FF14"
MAGENTA = "#FF00FF"
RED = "#FF3333"
YELLOW = "#FFD700"
DARK_BG = "#0a0a1a"
CARD_BG = "#111128"
BORDER = "#1a1a3e"

CARD_STYLE = f"""
    QGroupBox {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
        margin-top: 12px;
        padding: 12px;
        color: {CYAN};
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
        color: {CYAN};
    }}
"""

LABEL_STYLE = f"color: #aaaacc; font-size: 11px;"
VALUE_STYLE = f"color: {NEON_GREEN}; font-size: 22px; font-weight: bold;"
UNIT_STYLE = f"color: #777799; font-size: 10px;"

BUTTON_STYLE = f"""
    QPushButton {{
        background-color: #1a1a3e;
        color: {CYAN};
        border: 1px solid {CYAN};
        border-radius: 4px;
        padding: 6px 14px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: #2a2a5e;
    }}
    QPushButton:pressed {{
        background-color: {CYAN};
        color: #000;
    }}
"""


class VitalCard(QFrame):
    """A single vital sign display card."""

    def __init__(self, label: str, unit: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 8px;")
        self.setMinimumSize(140, 90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self._label = QLabel(label)
        self._label.setStyleSheet(LABEL_STYLE)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._value = QLabel("--")
        self._value.setStyleSheet(VALUE_STYLE)
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value)

        self._unit = QLabel(unit)
        self._unit.setStyleSheet(UNIT_STYLE)
        self._unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._unit)

    def set_value(self, value: str, color: str = NEON_GREEN) -> None:
        self._value.setText(str(value))
        self._value.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold;")


class HealthDashboardTab(QWidget):
    """Health monitoring dashboard GUI tab."""

    vitals_updated = pyqtSignal(dict)
    insight_received = pyqtSignal(dict)
    anomaly_received = pyqtSignal(dict)

    def __init__(self, parent=None, event_bus=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.setStyleSheet(f"background-color: {DARK_BG};")

        self._setup_ui()
        self._subscribe_events()
        self._connect_signals()

        # Refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._request_vitals_update)
        self._refresh_timer.start(10000)  # 10 second refresh

        logger.info("HealthDashboardTab initialized")

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Title bar
        title_bar = QHBoxLayout()
        title = QLabel("HEALTH MONITORING")
        title.setStyleSheet(f"color: {CYAN}; font-size: 18px; font-weight: bold;")
        title_bar.addWidget(title)

        self._status_label = QLabel("DORMANT")
        self._status_label.setStyleSheet(f"color: {YELLOW}; font-size: 12px; font-weight: bold;")
        title_bar.addStretch()
        title_bar.addWidget(self._status_label)

        self._activate_btn = QPushButton("Activate Health Monitoring")
        self._activate_btn.setStyleSheet(BUTTON_STYLE)
        self._activate_btn.clicked.connect(self._toggle_activation)
        title_bar.addWidget(self._activate_btn)

        main_layout.addLayout(title_bar)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {DARK_BG}; }}")
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)

        # Vital signs cards
        vitals_group = QGroupBox("REAL-TIME VITALS")
        vitals_group.setStyleSheet(CARD_STYLE)
        vitals_grid = QGridLayout()
        vitals_grid.setSpacing(8)

        self._hr_card = VitalCard("Heart Rate", "BPM")
        self._hrv_card = VitalCard("HRV (RMSSD)", "ms")
        self._spo2_card = VitalCard("SpO2", "%")
        self._stress_card = VitalCard("Stress", "/100")
        self._temp_card = VitalCard("Body Temp", "°C")
        self._rr_card = VitalCard("Resp. Rate", "/min")
        self._steps_card = VitalCard("Steps Today", "")
        self._sleep_card = VitalCard("Sleep Score", "/100")
        self._readiness_card = VitalCard("Readiness", "/100")
        self._battery_card = VitalCard("Body Battery", "/100")

        cards = [
            self._hr_card, self._hrv_card, self._spo2_card, self._stress_card,
            self._temp_card, self._rr_card, self._steps_card, self._sleep_card,
            self._readiness_card, self._battery_card,
        ]
        for i, card in enumerate(cards):
            vitals_grid.addWidget(card, i // 5, i % 5)

        vitals_group.setLayout(vitals_grid)
        scroll_layout.addWidget(vitals_group)

        # Devices + Insights side by side
        middle_row = QHBoxLayout()

        # Connected devices
        devices_group = QGroupBox("CONNECTED DEVICES")
        devices_group.setStyleSheet(CARD_STYLE)
        devices_layout = QVBoxLayout()

        self._devices_table = QTableWidget(0, 4)
        self._devices_table.setHorizontalHeaderLabels(["Device", "Brand", "Type", "Status"])
        self._devices_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._devices_table.setStyleSheet(f"""
            QTableWidget {{ background-color: {DARK_BG}; color: #ccc; gridline-color: {BORDER}; border: none; }}
            QHeaderView::section {{ background-color: {CARD_BG}; color: {CYAN}; border: 1px solid {BORDER}; padding: 4px; }}
        """)
        self._devices_table.setMaximumHeight(150)
        devices_layout.addWidget(self._devices_table)

        devices_btn_row = QHBoxLayout()
        self._scan_ble_btn = QPushButton("Scan BLE Devices")
        self._scan_ble_btn.setStyleSheet(BUTTON_STYLE)
        self._scan_ble_btn.clicked.connect(self._scan_ble)
        devices_btn_row.addWidget(self._scan_ble_btn)

        self._refresh_devices_btn = QPushButton("Refresh")
        self._refresh_devices_btn.setStyleSheet(BUTTON_STYLE)
        self._refresh_devices_btn.clicked.connect(self._refresh_devices)
        devices_btn_row.addWidget(self._refresh_devices_btn)
        devices_layout.addLayout(devices_btn_row)

        devices_group.setLayout(devices_layout)
        middle_row.addWidget(devices_group, 1)

        # Health insights
        insights_group = QGroupBox("AI HEALTH INSIGHTS")
        insights_group.setStyleSheet(CARD_STYLE)
        insights_layout = QVBoxLayout()

        self._insights_text = QTextEdit()
        self._insights_text.setReadOnly(True)
        self._insights_text.setMaximumHeight(180)
        self._insights_text.setStyleSheet(f"""
            QTextEdit {{ background-color: {DARK_BG}; color: #ccccee; border: 1px solid {BORDER};
                        border-radius: 4px; padding: 6px; font-size: 11px; }}
        """)
        self._insights_text.setPlaceholderText("Health insights will appear here when monitoring is active...")
        insights_layout.addWidget(self._insights_text)

        insights_group.setLayout(insights_layout)
        middle_row.addWidget(insights_group, 1)

        scroll_layout.addLayout(middle_row)

        # Anomaly alerts
        alerts_group = QGroupBox("ANOMALY ALERTS")
        alerts_group.setStyleSheet(CARD_STYLE)
        alerts_layout = QVBoxLayout()

        self._alerts_table = QTableWidget(0, 4)
        self._alerts_table.setHorizontalHeaderLabels(["Time", "Type", "Severity", "Details"])
        self._alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._alerts_table.setStyleSheet(f"""
            QTableWidget {{ background-color: {DARK_BG}; color: #ccc; gridline-color: {BORDER}; border: none; }}
            QHeaderView::section {{ background-color: {CARD_BG}; color: {CYAN}; border: 1px solid {BORDER}; padding: 4px; }}
        """)
        self._alerts_table.setMaximumHeight(150)
        alerts_layout.addWidget(self._alerts_table)

        alerts_group.setLayout(alerts_layout)
        scroll_layout.addWidget(alerts_group)

        # Protection flags status
        flags_group = QGroupBox("PROTECTION MODULE STATUS")
        flags_group.setStyleSheet(CARD_STYLE)
        flags_layout = QVBoxLayout()

        self._flags_table = QTableWidget(0, 2)
        self._flags_table.setHorizontalHeaderLabels(["Module", "Status"])
        self._flags_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._flags_table.setStyleSheet(f"""
            QTableWidget {{ background-color: {DARK_BG}; color: #ccc; gridline-color: {BORDER}; border: none; }}
            QHeaderView::section {{ background-color: {CARD_BG}; color: {CYAN}; border: 1px solid {BORDER}; padding: 4px; }}
        """)
        self._flags_table.setMaximumHeight(200)
        flags_layout.addWidget(self._flags_table)

        flags_group.setLayout(flags_layout)
        scroll_layout.addWidget(flags_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Signal connections (thread-safe UI updates)
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.vitals_updated.connect(self._on_vitals_ui_update)
        self.insight_received.connect(self._on_insight_ui_update)
        self.anomaly_received.connect(self._on_anomaly_ui_update)

    def _on_vitals_ui_update(self, data: dict) -> None:
        """Update vital cards from event data (main thread)."""
        hr = data.get("heart_rate")
        if hr is not None:
            color = NEON_GREEN
            if hr < 50 or hr > 150:
                color = RED
            elif hr < 60 or hr > 100:
                color = YELLOW
            self._hr_card.set_value(str(hr), color)

        hrv = data.get("hrv_rmssd")
        if hrv is not None:
            self._hrv_card.set_value(f"{hrv:.0f}")

        spo2 = data.get("spo2")
        if spo2 is not None:
            color = NEON_GREEN if spo2 >= 95 else (YELLOW if spo2 >= 90 else RED)
            self._spo2_card.set_value(str(spo2), color)

        stress = data.get("stress_level")
        if stress is not None:
            color = NEON_GREEN if stress < 40 else (YELLOW if stress < 70 else RED)
            self._stress_card.set_value(str(stress), color)

        temp = data.get("body_temperature")
        if temp is not None:
            self._temp_card.set_value(f"{temp:.1f}")

        rr = data.get("respiratory_rate")
        if rr is not None:
            self._rr_card.set_value(f"{rr:.0f}")

        steps = data.get("steps_today")
        if steps is not None:
            self._steps_card.set_value(f"{steps:,}")

        sleep = data.get("sleep_score")
        if sleep is not None:
            color = NEON_GREEN if sleep >= 80 else (YELLOW if sleep >= 60 else RED)
            self._sleep_card.set_value(str(sleep), color)

        readiness = data.get("readiness_score")
        if readiness is not None:
            color = NEON_GREEN if readiness >= 80 else (YELLOW if readiness >= 60 else RED)
            self._readiness_card.set_value(str(readiness), color)

        bb = data.get("body_battery")
        if bb is not None:
            color = NEON_GREEN if bb >= 60 else (YELLOW if bb >= 30 else RED)
            self._battery_card.set_value(str(bb), color)

    def _on_insight_ui_update(self, data: dict) -> None:
        """Append health insight to text area."""
        title = data.get("title", "Insight")
        advice = data.get("advice", "")
        priority = data.get("priority", "low")
        color = NEON_GREEN if priority == "low" else (YELLOW if priority == "medium" else RED)
        ts = data.get("created_at", "")[:19]
        self._insights_text.append(
            f'<span style="color:{color}"><b>[{ts}] {title}</b></span><br>{advice}<br>'
        )

    def _on_anomaly_ui_update(self, data: dict) -> None:
        """Add anomaly alert to table."""
        row = self._alerts_table.rowCount()
        self._alerts_table.insertRow(row)

        ts = data.get("timestamp", "")[:19]
        atype = data.get("type", "unknown")
        severity = data.get("severity", "warning")
        msg = data.get("message", "")

        self._alerts_table.setItem(row, 0, QTableWidgetItem(ts))
        self._alerts_table.setItem(row, 1, QTableWidgetItem(atype))

        sev_item = QTableWidgetItem(severity.upper())
        if severity == "critical":
            sev_item.setForeground(QColor(RED))
        elif severity == "warning":
            sev_item.setForeground(QColor(YELLOW))
        self._alerts_table.setItem(row, 2, sev_item)
        self._alerts_table.setItem(row, 3, QTableWidgetItem(msg[:80]))

        # Keep max 50 alerts
        while self._alerts_table.rowCount() > 50:
            self._alerts_table.removeRow(0)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _toggle_activation(self) -> None:
        if not self.event_bus:
            return
        # Toggle key health flags
        health_flags = ["wearable_hub", "health_anomaly_detector", "health_advisor", "health_dashboard_live"]
        for flag in health_flags:
            self.event_bus.publish("protection.flag.set", {
                "module": flag,
                "active": True,
                "source": "health_dashboard",
            })
        self._status_label.setText("ACTIVE")
        self._status_label.setStyleSheet(f"color: {NEON_GREEN}; font-size: 12px; font-weight: bold;")
        self._activate_btn.setText("Health Monitoring Active")
        logger.info("Health monitoring activated from dashboard")

    def _scan_ble(self) -> None:
        if self.event_bus:
            self.event_bus.publish("health.ble.scan", {"timeout": 10.0})

    def _refresh_devices(self) -> None:
        if self.event_bus:
            self.event_bus.publish("health.devices.query", {})

    def _request_vitals_update(self) -> None:
        if self.event_bus:
            self.event_bus.publish("health.vitals.query", {})

    # ------------------------------------------------------------------
    # Event bus subscriptions
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("health.vitals.updated", self._on_vitals_event)
        self.event_bus.subscribe("health.vitals.current", self._on_vitals_event)
        self.event_bus.subscribe("health.insight.new", self._on_insight_event)
        self.event_bus.subscribe("health.anomaly.detected", self._on_anomaly_event)
        self.event_bus.subscribe("health.devices.list", self._on_devices_event)
        self.event_bus.subscribe("health.ble.scan_results", self._on_ble_scan_event)
        self.event_bus.subscribe("protection.flag.status", self._on_flags_event)
        self.event_bus.subscribe("protection.flag.changed", self._on_flag_changed)

    def _on_vitals_event(self, data: Any) -> None:
        if isinstance(data, dict):
            self.vitals_updated.emit(data)

    def _on_insight_event(self, data: Any) -> None:
        if isinstance(data, dict):
            self.insight_received.emit(data)

    def _on_anomaly_event(self, data: Any) -> None:
        if isinstance(data, dict):
            self.anomaly_received.emit(data)

    def _on_devices_event(self, data: Any) -> None:
        if isinstance(data, dict):
            devices = data.get("devices", [])
            QTimer.singleShot(0, lambda: self._update_devices_table(devices))

    def _on_ble_scan_event(self, data: Any) -> None:
        if isinstance(data, dict):
            devices = data.get("devices", [])
            QTimer.singleShot(0, lambda: self._update_ble_results(devices))

    def _on_flags_event(self, data: Any) -> None:
        if isinstance(data, dict):
            QTimer.singleShot(0, lambda: self._update_flags_table(data))

    def _on_flag_changed(self, data: Any) -> None:
        if isinstance(data, dict):
            module = data.get("module", "")
            active = data.get("active", False)
            if module in ("wearable_hub", "health_anomaly_detector", "__all__"):
                if active:
                    self._status_label.setText("ACTIVE")
                    self._status_label.setStyleSheet(f"color: {NEON_GREEN}; font-size: 12px; font-weight: bold;")

    # ------------------------------------------------------------------
    # Table updates
    # ------------------------------------------------------------------

    def _update_devices_table(self, devices: List[Dict]) -> None:
        self._devices_table.setRowCount(0)
        for d in devices:
            row = self._devices_table.rowCount()
            self._devices_table.insertRow(row)
            self._devices_table.setItem(row, 0, QTableWidgetItem(d.get("name", "")))
            self._devices_table.setItem(row, 1, QTableWidgetItem(d.get("brand", "")))
            self._devices_table.setItem(row, 2, QTableWidgetItem(d.get("connection_type", "")))

            status = d.get("status", "unknown")
            status_item = QTableWidgetItem(status)
            if status == "connected":
                status_item.setForeground(QColor(NEON_GREEN))
            else:
                status_item.setForeground(QColor(YELLOW))
            self._devices_table.setItem(row, 3, status_item)

    def _update_ble_results(self, devices: List[Dict]) -> None:
        # Show BLE scan results in devices table with "ble" type
        for d in devices:
            if d.get("has_heart_rate"):
                row = self._devices_table.rowCount()
                self._devices_table.insertRow(row)
                self._devices_table.setItem(row, 0, QTableWidgetItem(d.get("name", "Unknown BLE")))
                self._devices_table.setItem(row, 1, QTableWidgetItem("BLE"))
                self._devices_table.setItem(row, 2, QTableWidgetItem("ble"))
                self._devices_table.setItem(row, 3, QTableWidgetItem(f"RSSI: {d.get('rssi', '?')}"))

    def _update_flags_table(self, flags: Dict[str, bool]) -> None:
        self._flags_table.setRowCount(0)
        for module, active in sorted(flags.items()):
            row = self._flags_table.rowCount()
            self._flags_table.insertRow(row)
            self._flags_table.setItem(row, 0, QTableWidgetItem(module))

            status_item = QTableWidgetItem("ACTIVE" if active else "DORMANT")
            status_item.setForeground(QColor(NEON_GREEN if active else YELLOW))
            self._flags_table.setItem(row, 1, status_item)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def register_event_handlers(self) -> None:
        """Called by TabManager after tab creation."""
        self._subscribe_events()
        # Request initial data
        if self.event_bus:
            self.event_bus.publish("health.devices.query", {})
            self.event_bus.publish("protection.flag.query", {})
