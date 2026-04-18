#!/usr/bin/env python3
"""
Comprehensive Analysis Chart - SOTA 2026
Visualizes past/present/future market analysis with live trading data
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import deque
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTextEdit, QSplitter, QGroupBox, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class AnalysisDataModel:
    """Synthesizes past/present/future market states with categorization"""
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or "logs/analysis/comprehensive_model.json"
        self.historical_analyses = deque(maxlen=1000)
        self.historical_prices = {}
        self.historical_opportunities = deque(maxlen=500)
        self.current_market_state = {}
        self.current_analysis = None
        self.current_opportunities = []
        self.price_predictions = {}
        self.categories = {
            'arbitrage': [], 'whale_movements': [], 'sentiment': [],
            'technical': [], 'anomalies': [], 'risk': [], 'ai_predictions': []
        }
        self.stats = {
            'total_analyses': 0, 'total_opportunities_found': 0,
            'total_trades_suggested': 0, 'last_update': None
        }
        self.logger = logger
        self._load_from_disk()
    
    def add_analysis(self, analysis: Dict[str, Any]) -> None:
        """Add new analysis to the model."""
        try:
            timestamp = analysis.get('timestamp', datetime.now().isoformat())
            self.historical_analyses.append({'timestamp': timestamp, 'data': analysis})
            self.current_analysis = analysis
            self.current_market_state = {
                'timestamp': timestamp,
                'markets_analyzed': analysis.get('markets_analyzed', []),
                'exchange_data': analysis.get('exchange_data', {}),
                'sentiment': analysis.get('sentiment_data', {})
            }
            self._categorize_analysis(analysis)
            self.stats['total_analyses'] += 1
            self.stats['last_update'] = timestamp
            
            opportunities = analysis.get('top_opportunities', [])
            self.current_opportunities = opportunities
            for opp in opportunities:
                self.historical_opportunities.append({'timestamp': timestamp, 'opportunity': opp})
                self.stats['total_opportunities_found'] += 1
            
            markets = analysis.get('markets_analyzed', [])
            for market in markets:
                symbol = market.get('symbol', '')
                price = market.get('price', 0)
                if symbol and price:
                    if symbol not in self.historical_prices:
                        self.historical_prices[symbol] = deque(maxlen=1000)
                    self.historical_prices[symbol].append((timestamp, price))
            
            if self.stats['total_analyses'] % 10 == 0:
                self._save_to_disk()
        except Exception as e:
            self.logger.error(f"Error adding analysis: {e}")
    
    def _categorize_analysis(self, analysis: Dict[str, Any]) -> None:
        """Categorize analysis data."""
        try:
            if 'arbitrage_opportunities' in analysis:
                self.categories['arbitrage'].extend(analysis['arbitrage_opportunities'])
            if 'whale_transactions' in analysis:
                self.categories['whale_movements'].extend(analysis['whale_transactions'])
            if 'sentiment_data' in analysis:
                self.categories['sentiment'].append(analysis['sentiment_data'])
            if 'technical_indicators' in analysis:
                self.categories['technical'].append(analysis['technical_indicators'])
            if 'anomalies' in analysis:
                self.categories['anomalies'].extend(analysis['anomalies'])
            if 'risk_assessment' in analysis:
                self.categories['risk'].append(analysis['risk_assessment'])
            if 'ai_predictions' in analysis:
                self.categories['ai_predictions'].extend(analysis['ai_predictions'])
            
            for category in self.categories:
                if len(self.categories[category]) > 100:
                    self.categories[category] = self.categories[category][-100:]
        except Exception as e:
            self.logger.error(f"Error categorizing: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        return self.stats.copy()
    
    def get_current_state(self) -> Dict[str, Any]:
        return self.current_market_state
    
    def _save_to_disk(self) -> None:
        try:
            Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
            data = {
                'stats': self.stats,
                'current_state': self.current_market_state,
                'last_saved': datetime.now().isoformat()
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving: {e}")
    
    def _load_from_disk(self) -> None:
        try:
            if Path(self.storage_path).exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.stats = data.get('stats', self.stats)
        except Exception as e:
            self.logger.debug(f"Could not load: {e}")


class ComprehensiveAnalysisChart(QWidget):
    """Comprehensive Analysis Visualization Chart - SOTA 2026"""
    
    analysis_updated = pyqtSignal(dict)
    
    def __init__(self, parent=None, event_bus=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.logger = logger
        self.data_model = AnalysisDataModel()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "logs")
        self._analysis_log_path = os.path.join(_log_dir, "analysis", "trading_analysis_stream.ndjson")
        self._analysis_index_path = os.path.join(_log_dir, "analysis", "comprehensive_model.json")
        self.selected_symbol = None
        self.selected_category = 'all'
        self._init_ui()
        self._start_update_timer()
        self.logger.info("✅ Comprehensive Analysis Chart initialized")

    def _append_ndjson(self, obj: Dict[str, Any]) -> None:
        """Append one record to the analysis audit log (NDJSON)."""
        try:
            Path(self._analysis_log_path).parent.mkdir(parents=True, exist_ok=True)
            record = {
                "ts": datetime.now().isoformat(),
                "record": obj,
            }
            with open(self._analysis_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            self.logger.error(f"Error writing analysis log: {e}")
    
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        header = self._create_header()
        layout.addWidget(header)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_panel = self._create_visualization_panel()
        splitter.addWidget(left_panel)
        right_panel = self._create_data_panel()
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        
        footer = self._create_footer()
        layout.addWidget(footer)
    
    def _create_header(self) -> QWidget:
        header = QGroupBox("📊 Comprehensive Market Analysis - Past/Present/Future")
        header.setStyleSheet("QGroupBox { font-weight: bold; border: 2px solid #00ff00; }")
        layout = QHBoxLayout(header)
        
        layout.addWidget(QLabel("Symbol:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItem("All Symbols")
        layout.addWidget(self.symbol_combo)
        
        layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(['all', 'arbitrage', 'whale_movements', 'sentiment', 'technical', 'anomalies', 'risk', 'ai_predictions'])
        layout.addWidget(self.category_combo)
        
        layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_display)
        layout.addWidget(refresh_btn)
        
        return header
    
    def _create_visualization_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.viz_tabs = QTabWidget()
        self.viz_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.price_display = QTextEdit()
        self.price_display.setReadOnly(True)
        self.price_display.setStyleSheet("QTextEdit { background-color: #0a0a0a; color: #00ff00; }")
        self.viz_tabs.addTab(self.price_display, "📈 Price Analysis")
        
        self.opportunities_table = QTableWidget()
        self.opportunities_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.opportunities_table.setColumnCount(6)
        self.opportunities_table.setHorizontalHeaderLabels(['Time', 'Type', 'Symbol', 'Opportunity', 'Confidence', 'Status'])
        self.viz_tabs.addTab(self.opportunities_table, "💎 Opportunities")
        
        self.category_display = QTextEdit()
        self.category_display.setReadOnly(True)
        self.category_display.setStyleSheet("QTextEdit { background-color: #0a0a0a; color: #00ff00; }")
        self.viz_tabs.addTab(self.category_display, "📊 Categories")
        
        self.live_feed = QTextEdit()
        self.live_feed.setReadOnly(True)
        self.live_feed.setStyleSheet("QTextEdit { background-color: #0a0a0a; color: #00ff00; }")
        self.viz_tabs.addTab(self.live_feed, "🔴 Live Feed")
        
        layout.addWidget(self.viz_tabs)
        return panel
    
    def _create_data_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        stats_group = QGroupBox("📊 Statistics")
        stats_layout = QVBoxLayout(stats_group)
        self.stats_display = QTextEdit()
        self.stats_display.setReadOnly(True)
        self.stats_display.setMaximumHeight(200)
        stats_layout.addWidget(self.stats_display)
        layout.addWidget(stats_group)
        
        state_group = QGroupBox("🔴 Current State")
        state_layout = QVBoxLayout(state_group)
        self.state_display = QTextEdit()
        self.state_display.setReadOnly(True)
        state_layout.addWidget(self.state_display)
        layout.addWidget(state_group)
        
        return panel
    
    def _create_footer(self) -> QWidget:
        footer = QGroupBox()
        footer.setMaximumHeight(60)
        layout = QHBoxLayout(footer)
        self.status_label = QLabel("Status: Ready")
        layout.addWidget(self.status_label)
        layout.addStretch()
        self.last_update_label = QLabel("Last Update: Never")
        layout.addWidget(self.last_update_label)
        return footer
    
    def add_analysis(self, analysis: Dict[str, Any]) -> None:
        try:
            # Always persist the raw record so it can be read anytime.
            # This is append-only and does not overwrite previous data.
            self._append_ndjson(analysis)

            self.data_model.add_analysis(analysis)
            self._update_display()
            self._add_to_live_feed(f"✅ New analysis: {len(analysis.get('markets_analyzed', []))} markets")
            self.analysis_updated.emit(analysis)
        except Exception as e:
            self.logger.error(f"Error adding analysis: {e}")
    
    def _update_display(self) -> None:
        try:
            stats = self.data_model.get_statistics()
            self.stats_display.setPlainText(f"Total Analyses: {stats['total_analyses']}\nOpportunities: {stats['total_opportunities_found']}")
            
            state = self.data_model.get_current_state()
            self.state_display.setPlainText(f"Markets: {len(state.get('markets_analyzed', []))}\nTimestamp: {state.get('timestamp', 'N/A')}")
            
            self.last_update_label.setText(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            self.logger.error(f"Error updating display: {e}")
    
    def _add_to_live_feed(self, message: str) -> None:
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.live_feed.append(f"[{timestamp}] {message}")
    
    def _refresh_display(self) -> None:
        self._update_display()
    
    def _start_update_timer(self) -> None:
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(5000)
