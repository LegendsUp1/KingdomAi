import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    QTimer,
    QSortFilterProxyModel,
    QRegularExpression,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _EventHistoryModel(QAbstractTableModel):
    def __init__(self, max_rows: int = 5000, parent=None):
        super().__init__(parent)
        self._events: List[Dict[str, Any]] = []
        self._max_rows = max_rows
        self._columns = [
            ("Seq", "seq"),
            ("Time", "timestamp"),
            ("Event", "event_type"),
            ("Thread", "thread"),
            ("Preview", "preview"),
        ]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._events)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        if not (0 <= index.row() < len(self._events)):
            return None

        event = self._events[index.row()]
        key = self._columns[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            value = event.get(key)
            if key == "timestamp":
                try:
                    return datetime.fromtimestamp(float(value)).strftime("%H:%M:%S.%f")[:-3]
                except Exception:
                    return str(value)
            return "" if value is None else str(value)

        if role == Qt.ItemDataRole.UserRole:
            return event

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # type: ignore[override]
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section][0]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def append_events(self, new_events: List[Dict[str, Any]]) -> None:
        if not new_events:
            return

        start = len(self._events)
        end = start + len(new_events) - 1
        self.beginInsertRows(QModelIndex(), start, end)
        self._events.extend(new_events)
        self.endInsertRows()

        overflow = len(self._events) - self._max_rows
        if overflow > 0:
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            del self._events[:overflow]
            self.endRemoveRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._events = []
        self.endResetModel()

    def last_seq(self) -> int:
        try:
            if not self._events:
                return 0
            return int(self._events[-1].get("seq", 0))
        except Exception:
            return 0


class EventBusTelemetryPanel(QWidget):
    def __init__(self, event_bus=None, parent=None):
        super().__init__(parent)
        self._bus = event_bus
        self._last_seq = 0

        self._model = _EventHistoryModel(max_rows=5000, parent=self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setDynamicSortFilter(True)
        try:
            self._proxy.setFilterKeyColumn(-1)
        except Exception:
            pass

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter (event type / preview)")
        self._filter.textChanged.connect(self._on_filter_changed)

        self._pause = QCheckBox("Pause")
        self._auto_scroll = QCheckBox("Auto-scroll")
        self._auto_scroll.setChecked(True)

        self._count_label = QLabel("0")

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._poll_events)

        header = QHBoxLayout()
        header.addWidget(QLabel("Events:"))
        header.addWidget(self._count_label)
        header.addStretch(1)
        header.addWidget(self._filter)
        header.addWidget(self._pause)
        header.addWidget(self._auto_scroll)
        header.addWidget(self._refresh_btn)
        header.addWidget(self._clear_btn)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)

        self._details = QTextEdit()
        self._details.setReadOnly(True)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._table)
        splitter.addWidget(self._details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(splitter)

        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_events)
        self._timer.start(1000)  # SOTA 2026 FIX: 1s saves CPU vs 100ms; telemetry doesn't need 10Hz

        self.setStyleSheet(
            "QWidget{background-color:#0a0a1e;color:#ffffff;}"
            "QLineEdit{background-color:#1a1a2e;border:1px solid #2a2a4a;padding:4px;border-radius:4px;}"
            "QTextEdit{background-color:#1a1a2e;border:1px solid #2a2a4a;}"
            "QTableView{background-color:#0f0f26;alternate-background-color:#141436;gridline-color:#2a2a4a;}"
            "QHeaderView::section{background-color:#1a1a2e;color:#ffffff;border:1px solid #2a2a4a;padding:4px;}"
            "QPushButton{background-color:#1a1a2e;border:1px solid #2a2a4a;padding:4px 8px;border-radius:4px;}"
            "QPushButton:hover{border:1px solid #00ffff;}"
        )

    def _on_filter_changed(self, text: str) -> None:
        try:
            rx = QRegularExpression(text)
            self._proxy.setFilterRegularExpression(rx)
        except Exception:
            try:
                self._proxy.setFilterRegularExpression(text)
            except Exception:
                pass

    def _clear(self) -> None:
        try:
            if self._bus and hasattr(self._bus, "clear_event_history"):
                self._bus.clear_event_history()
        except Exception:
            pass
        self._model.clear()
        self._details.setPlainText("")
        self._last_seq = 0
        self._count_label.setText("0")

    def _poll_events(self) -> None:
        if self._pause.isChecked():
            return
        if not self._bus:
            return
        if not hasattr(self._bus, "get_event_history_since"):
            return
        try:
            new_events = self._bus.get_event_history_since(self._last_seq)
        except Exception:
            return
        if not new_events:
            return

        self._model.append_events(new_events)
        self._last_seq = max(self._last_seq, self._model.last_seq())
        self._count_label.setText(str(self._model.rowCount()))

        if self._auto_scroll.isChecked():
            try:
                if self._proxy.rowCount() > 0:
                    idx = self._proxy.index(self._proxy.rowCount() - 1, 0)
                    self._table.scrollTo(idx)
            except Exception:
                pass

    def _on_selection_changed(self, *_args) -> None:
        try:
            idxs = self._table.selectionModel().selectedRows()
            if not idxs:
                return
            proxy_idx = idxs[0]
            src_idx = self._proxy.mapToSource(proxy_idx)
            event = self._model.data(src_idx, Qt.ItemDataRole.UserRole)
            if not isinstance(event, dict):
                return

            payload = event.get("data")
            if isinstance(payload, (dict, list)):
                body = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
            else:
                try:
                    body = repr(payload)
                except Exception:
                    body = "<unreprable>"

            header = {
                "seq": event.get("seq"),
                "timestamp": event.get("timestamp"),
                "event_type": event.get("event_type"),
                "thread": event.get("thread"),
            }
            text = json.dumps(header, indent=2, ensure_ascii=False, default=str) + "\n\n" + body
            self._details.setPlainText(text)
        except Exception:
            return
