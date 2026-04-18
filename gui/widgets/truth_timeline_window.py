#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Truth Timeline Window — SHA-LU-AM (שלום).

Separate GUI screen that pops up when the native tongue is spoken.
Shows all facts and times. Timeline. No mistakes. No bullshit.
Kiber (Queber), Tataria, Quivara. Dark ages. Ley lines. Dragons/whales.
Records of who was who. Fact-checked. True history.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger("KingdomAI.TruthTimeline")


class TruthTimelineWindow(QDialog):
    """Popup window: all facts and times when SHA-LU-AM spoken."""

    def __init__(self, event_bus=None, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.setWindowTitle("Truth Timeline — SHA-LU-AM (שלום)")
        self.setMinimumSize(900, 600)
        self.setStyleSheet("""
            QDialog { background-color: #0a0a14; }
            QLabel { color: #00ffff; font-size: 12px; }
            QTextEdit { background-color: #0d0d1a; color: #e0e0e0; border: 1px solid #1a1a2e; }
            QPushButton { background-color: #0a2a2a; color: #00ffff; border: 1px solid #00ffff; }
            QTabWidget::pane { border: 1px solid #1a1a2e; background: #0a0a14; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Truth Timeline — All Facts & Times")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff88;")
        layout.addWidget(title)
        sub = QLabel("Kiber • Tataria • Quivara • Dark Ages • Ley Lines • Dragons/Whales • True History")
        sub.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(sub)
        self.tabs = QTabWidget()
        self.timeline_text = QTextEdit()
        self.timeline_text.setReadOnly(True)
        self.tabs.addTab(self.timeline_text, "Timeline")
        self.facts_text = QTextEdit()
        self.facts_text.setReadOnly(True)
        self.tabs.addTab(self.facts_text, "All Facts")
        self.foundation_text = QTextEdit()
        self.foundation_text.setReadOnly(True)
        self.tabs.addTab(self.foundation_text, "Foundation")
        layout.addWidget(self.tabs)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def load_and_display(self):
        """Load from Secret Reserve and display."""
        try:
            from core.redis_nexus import get_redis_nexus
            from core.truth_timeline_data import load_all_facts
            nexus = get_redis_nexus()
            data = load_all_facts(nexus)
            # Timeline
            lines = []
            for e in data["timeline"][:100]:
                t = e.get("t", "?")
                src = e.get("source", "")
                txt = (e.get("text", "") or "")[:400]
                ts = e.get("ts", "")
                lines.append(f"[{t}] {src} (ts={ts})\n{txt}\n")
            self.timeline_text.setPlainText("\n".join(lines) if lines else "No timeline entries yet.")
            # All facts
            all_facts = []
            for f in data["gathered"]:
                if isinstance(f, dict):
                    all_facts.append(f"[GATHERED] {f.get('source','')} | {f.get('text','')[:300]}")
            for f in data["documents"]:
                if isinstance(f, dict):
                    all_facts.append(f"[DOC] ts={f.get('ts')} | {f.get('excerpt','')[:300]}")
            for f in data["truth_records"]:
                if isinstance(f, dict):
                    all_facts.append(f"[TRUTH] ts={f.get('ts')} | {f.get('text','')[:300]}")
            self.facts_text.setPlainText("\n\n".join(all_facts) if all_facts else "No facts yet.")
            # Foundation
            self.foundation_text.setPlainText(data["foundation"] or "No foundation wisdom loaded.")
        except Exception as e:
            logger.debug("Truth timeline display: %s", e)
            self.timeline_text.setPlainText(f"Error loading: {e}")


def show_truth_timeline(event_bus=None, parent=None):
    """Show the Truth Timeline popup. Call when SHA-LU-AM spoken."""
    w = TruthTimelineWindow(event_bus=event_bus, parent=parent)
    w.load_and_display()
    w.exec()
