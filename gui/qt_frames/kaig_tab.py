"""
Kingdom AI — $KAIG (KAI Gold) Tab
SOTA 2026: Dedicated desktop tab for KAIG node operation, treasury monitoring,
tokenomics dashboard, and AI-managed buyback visualization.

Works in BOTH Creator and Consumer editions.
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGroupBox, QGridLayout, QProgressBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QSpinBox, QApplication,
)
import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger("KingdomAI.KAIGTab")

try:
    from core.kaig_engine import (
        KAIGEngine, TOTAL_SUPPLY, ESCROW_SUPPLY, TREASURY_SUPPLY,
        COMMUNITY_SUPPLY, TEAM_SUPPLY, TARGET_PRICE, INITIAL_PRICE,
        NODE_REWARD_PER_HOUR, NODE_REWARD_CAP_DAILY, STAKING_APY,
        TRADING_PROFIT_BUYBACK_RATE, TRANSACTION_BURN_RATE,
    )
    KAIG_AVAILABLE = True
except ImportError as e:
    KAIG_AVAILABLE = False
    logger.warning("KAIG engine unavailable: %s", e)

# Kingdom AI color palette
KINGDOM_DARK = "#050510"
KINGDOM_CARD = "#0a0a1a"
KINGDOM_GOLD = "#FFD700"
KINGDOM_CYAN = "#00e5ff"
KINGDOM_BORDER = "#1a1a3a"
NEON_GREEN = "#00ff88"
RED = "#ff4444"
ORANGE = "#ff8800"

CARD_STYLE = f"""
    QGroupBox {{
        background-color: {KINGDOM_CARD};
        border: 1px solid {KINGDOM_BORDER};
        border-radius: 8px;
        margin-top: 12px;
        padding: 14px;
        color: {KINGDOM_CYAN};
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {KINGDOM_GOLD};
    }}
"""

BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {KINGDOM_GOLD};
        color: {KINGDOM_DARK};
        border: none;
        border-radius: 6px;
        padding: 8px 18px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: #ffea00;
    }}
    QPushButton:disabled {{
        background-color: #555;
        color: #888;
    }}
"""

STOP_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {RED};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 18px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: #ff6666;
    }}
"""

PROGRESS_STYLE = f"""
    QProgressBar {{
        background-color: #1a1a2e;
        border: 1px solid {KINGDOM_BORDER};
        border-radius: 6px;
        text-align: center;
        color: {KINGDOM_GOLD};
        font-weight: bold;
    }}
    QProgressBar::chunk {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {KINGDOM_GOLD}, stop:1 {NEON_GREEN});
        border-radius: 5px;
    }}
"""


def _gold_label(text: str, size: int = 14, bold: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {KINGDOM_GOLD}; font-size: {size}px;"
                      f"{' font-weight: bold;' if bold else ''}")
    return lbl


def _cyan_label(text: str, size: int = 12) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {KINGDOM_CYAN}; font-size: {size}px;")
    return lbl


def _value_label(text: str, size: int = 16, color: str = NEON_GREEN) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: bold;")
    return lbl


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {KINGDOM_BORDER};")
    line.setMaximumHeight(1)
    return line


class KAIGTab(QWidget):
    """
    $KAIG (KAI Gold) dedicated tab — node operation, treasury, tokenomics.
    """

    def __init__(self, event_bus=None, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.engine: Optional[KAIGEngine] = None
        self._node_timer = QTimer(self)
        self._node_timer.timeout.connect(self._node_heartbeat)
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_all_stats)
        self._stats_apply_timer = QTimer(self)
        self._stats_apply_timer.setSingleShot(True)
        self._stats_apply_timer.timeout.connect(self._apply_cached_kaig_stats)

        self.setStyleSheet(f"background-color: {KINGDOM_DARK};")
        self._setup_complete_ui()

        # Initialize engine
        try:
            if KAIG_AVAILABLE:
                self.engine = KAIGEngine.get_instance(event_bus=event_bus)
                logger.info("KAIG Tab initialized with engine")
                self._refresh_all_stats()
        except Exception as e:
            logger.error("Failed to initialize KAIG engine: %s", e)

        # Subscribe to live KAIG events for real-time UI updates
        if self.event_bus and hasattr(self.event_bus, 'subscribe'):
            self.event_bus.subscribe("kaig.status.update", self._on_kaig_live_update)
            self.event_bus.subscribe("kaig.buyback", self._on_kaig_buyback_event)
            self.event_bus.subscribe("kaig.node.status", self._on_kaig_node_event)
            self.event_bus.subscribe("trading.profit", self._on_trading_profit_event)
            self.event_bus.subscribe("mining.reward_update", self._on_mining_reward_event)
            self.event_bus.subscribe("kaig.phase.transition", self._on_phase_transition)
            self.event_bus.subscribe("kaig.autopilot.ai_insight", self._on_ai_insight)
            self.event_bus.subscribe("kaig.ath.update", self._on_ath_update)
            logger.info("KAIG Tab: subscribed to 8 live event channels")

        # Refresh stats every 30 seconds
        self._stats_timer.start(30000)

    def _setup_complete_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        title = _gold_label("$KAIG — KAI Gold", size=22)
        subtitle = _cyan_label("AI-Managed Cryptocurrency • Revenue-Backed • $10 Target", size=12)
        header_left = QVBoxLayout()
        header_left.addWidget(title)
        header_left.addWidget(subtitle)
        header.addLayout(header_left)
        header.addStretch()

        # Price display
        self.price_label = _value_label("$0.1000", size=28, color=KINGDOM_GOLD)
        self.price_target_label = _cyan_label("Target: $10.00", size=11)
        price_col = QVBoxLayout()
        price_col.setAlignment(Qt.AlignmentFlag.AlignRight)
        price_col.addWidget(self.price_label)
        price_col.addWidget(self.price_target_label)
        header.addLayout(price_col)
        main_layout.addLayout(header)

        # Price progress bar
        self.price_progress = QProgressBar()
        self.price_progress.setRange(0, 10000)  # 0-100.00%
        self.price_progress.setValue(100)  # 1% ($0.10 of $10)
        self.price_progress.setFormat("Price Progress: %p% to $10 target")
        self.price_progress.setMaximumHeight(22)
        self.price_progress.setStyleSheet(PROGRESS_STYLE)
        main_layout.addWidget(self.price_progress)

        # Sub-tabs
        self.sub_tabs = QTabWidget()
        self.sub_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {KINGDOM_BORDER};
                background-color: {KINGDOM_DARK};
            }}
            QTabBar::tab {{
                background-color: {KINGDOM_CARD};
                color: {KINGDOM_CYAN};
                padding: 8px 16px;
                border: 1px solid {KINGDOM_BORDER};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background-color: {KINGDOM_DARK};
                color: {KINGDOM_GOLD};
                border-bottom: 2px solid {KINGDOM_GOLD};
            }}
        """)

        self.sub_tabs.addTab(self._build_node_tab(), "⚡ Node")
        self.sub_tabs.addTab(self._build_treasury_tab(), "🏦 Treasury")
        self.sub_tabs.addTab(self._build_tokenomics_tab(), "📊 Tokenomics")
        self.sub_tabs.addTab(self._build_escrow_tab(), "🔒 Escrow")
        self.sub_tabs.addTab(self._build_transactions_tab(), "📜 Ledger")
        self.sub_tabs.addTab(self._build_roadmap_tab(), "🗺️ Roadmap")
        self.sub_tabs.addTab(self._build_install_phone_tab(), "📱 Install on My Phone")
        main_layout.addWidget(self.sub_tabs)

    # ══════════════════════════════════════════════════════════════
    # NODE SUB-TAB
    # ══════════════════════════════════════════════════════════════
    def _build_node_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(10)

        # Node Status Card
        node_group = QGroupBox("KAIG Node")
        node_group.setStyleSheet(CARD_STYLE)
        ng = QGridLayout(node_group)

        ng.addWidget(_cyan_label("Node ID:"), 0, 0)
        self.node_id_label = _value_label("—", size=13, color=KINGDOM_CYAN)
        ng.addWidget(self.node_id_label, 0, 1)

        ng.addWidget(_cyan_label("Status:"), 1, 0)
        self.node_status_label = _value_label("OFFLINE", size=14, color=RED)
        ng.addWidget(self.node_status_label, 1, 1)

        ng.addWidget(_cyan_label("Uptime:"), 2, 0)
        self.node_uptime_label = _value_label("0:00:00", size=13)
        ng.addWidget(self.node_uptime_label, 2, 1)

        ng.addWidget(_cyan_label("Session Earned:"), 3, 0)
        self.node_session_earned = _value_label("0.000000 KAIG", size=13)
        ng.addWidget(self.node_session_earned, 3, 1)

        ng.addWidget(_cyan_label("Today Earned:"), 4, 0)
        self.node_today_earned = _value_label("0.000000 KAIG", size=13)
        ng.addWidget(self.node_today_earned, 4, 1)

        ng.addWidget(_cyan_label("Total Earned:"), 5, 0)
        self.node_total_earned = _value_label("0.000000 KAIG", size=14, color=KINGDOM_GOLD)
        ng.addWidget(self.node_total_earned, 5, 1)

        ng.addWidget(_cyan_label("Balance:"), 6, 0)
        self.node_balance = _value_label("0.000000 KAIG", size=14, color=KINGDOM_GOLD)
        ng.addWidget(self.node_balance, 6, 1)

        ng.addWidget(_cyan_label("Daily Cap:"), 7, 0)
        self.node_daily_cap = _cyan_label(f"{NODE_REWARD_CAP_DAILY} KAIG/day" if KAIG_AVAILABLE else "—")
        ng.addWidget(self.node_daily_cap, 7, 1)

        ng.addWidget(_cyan_label("Reward Rate:"), 8, 0)
        self.node_reward_rate = _cyan_label(f"{NODE_REWARD_PER_HOUR} KAIG/hr" if KAIG_AVAILABLE else "—")
        ng.addWidget(self.node_reward_rate, 8, 1)

        cl.addWidget(node_group)

        # Node Controls
        ctrl_layout = QHBoxLayout()
        self.start_node_btn = QPushButton("▶ Start Node")
        self.start_node_btn.setStyleSheet(BUTTON_STYLE)
        self.start_node_btn.clicked.connect(self._start_node)
        ctrl_layout.addWidget(self.start_node_btn)

        self.stop_node_btn = QPushButton("■ Stop Node")
        self.stop_node_btn.setStyleSheet(STOP_BUTTON_STYLE)
        self.stop_node_btn.setEnabled(False)
        self.stop_node_btn.clicked.connect(self._stop_node)
        ctrl_layout.addWidget(self.stop_node_btn)
        cl.addLayout(ctrl_layout)

        # Contribution Metrics
        contrib_group = QGroupBox("Node Contributions (Real Resources)")
        contrib_group.setStyleSheet(CARD_STYLE)
        cg = QGridLayout(contrib_group)

        cg.addWidget(_cyan_label("Bandwidth Relayed:"), 0, 0)
        self.bandwidth_label = _value_label("0 MB", size=13)
        cg.addWidget(self.bandwidth_label, 0, 1)

        cg.addWidget(_cyan_label("Compute Tasks:"), 1, 0)
        self.compute_label = _value_label("0", size=13)
        cg.addWidget(self.compute_label, 1, 1)

        cg.addWidget(_cyan_label("Staked Amount:"), 2, 0)
        self.stake_label = _value_label("0 KAIG", size=13)
        cg.addWidget(self.stake_label, 2, 1)

        cg.addWidget(_cyan_label("Staking APY:"), 3, 0)
        self.apy_label = _value_label(f"{STAKING_APY * 100:.1f}%" if KAIG_AVAILABLE else "—",
                                       size=13, color=NEON_GREEN)
        cg.addWidget(self.apy_label, 3, 1)
        cl.addWidget(contrib_group)

        # Network Stats
        net_group = QGroupBox("KAIG Network")
        net_group.setStyleSheet(CARD_STYLE)
        netg = QGridLayout(net_group)

        netg.addWidget(_cyan_label("Total Nodes:"), 0, 0)
        self.net_total_nodes = _value_label("0", size=13)
        netg.addWidget(self.net_total_nodes, 0, 1)

        netg.addWidget(_cyan_label("Online Nodes:"), 1, 0)
        self.net_online_nodes = _value_label("0", size=13, color=NEON_GREEN)
        netg.addWidget(self.net_online_nodes, 1, 1)

        netg.addWidget(_cyan_label("Total Staked:"), 2, 0)
        self.net_total_staked = _value_label("0 KAIG", size=13)
        netg.addWidget(self.net_total_staked, 2, 1)

        netg.addWidget(_cyan_label("Total Rewards Distributed:"), 3, 0)
        self.net_total_rewards = _value_label("0 KAIG", size=13, color=KINGDOM_GOLD)
        netg.addWidget(self.net_total_rewards, 3, 1)
        cl.addWidget(net_group)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return w

    # ══════════════════════════════════════════════════════════════
    # TREASURY SUB-TAB
    # ══════════════════════════════════════════════════════════════
    def _build_treasury_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(10)

        # AI Treasury Status
        treasury_group = QGroupBox("AI-Managed Treasury")
        treasury_group.setStyleSheet(CARD_STYLE)
        tg = QGridLayout(treasury_group)

        tg.addWidget(_cyan_label("Internal Price:"), 0, 0)
        self.treasury_price = _value_label("$0.1000", size=16, color=KINGDOM_GOLD)
        tg.addWidget(self.treasury_price, 0, 1)

        tg.addWidget(_cyan_label("Progress to $10:"), 1, 0)
        self.treasury_progress = _value_label("1.00%", size=14, color=NEON_GREEN)
        tg.addWidget(self.treasury_progress, 1, 1)

        tg.addWidget(_cyan_label("KAIG Held by Treasury:"), 2, 0)
        self.treasury_kaig_held = _value_label("15,000,000 KAIG", size=13)
        tg.addWidget(self.treasury_kaig_held, 2, 1)

        tg.addWidget(_cyan_label("Treasury Value (USD):"), 3, 0)
        self.treasury_value = _value_label("$0", size=14, color=KINGDOM_GOLD)
        tg.addWidget(self.treasury_value, 3, 1)
        cl.addWidget(treasury_group)

        # Buyback Engine
        buyback_group = QGroupBox("Revenue → Buyback Engine")
        buyback_group.setStyleSheet(CARD_STYLE)
        bg = QGridLayout(buyback_group)

        bg.addWidget(_cyan_label("Total Buyback (USD):"), 0, 0)
        self.buyback_total_usd = _value_label("$0.00", size=14, color=NEON_GREEN)
        bg.addWidget(self.buyback_total_usd, 0, 1)

        bg.addWidget(_cyan_label("Total KAIG Bought Back:"), 1, 0)
        self.buyback_total_kaig = _value_label("0 KAIG", size=14)
        bg.addWidget(self.buyback_total_kaig, 1, 1)

        bg.addWidget(_cyan_label("Pending Buyback:"), 2, 0)
        self.buyback_pending = _value_label("$0.00", size=13, color=ORANGE)
        bg.addWidget(self.buyback_pending, 2, 1)

        bg.addWidget(_cyan_label("Number of Buybacks:"), 3, 0)
        self.buyback_count = _value_label("0", size=13)
        bg.addWidget(self.buyback_count, 3, 1)

        bg.addWidget(_cyan_label("Profit → Buyback Rate:"), 4, 0)
        rate_txt = f"{TRADING_PROFIT_BUYBACK_RATE * 100:.0f}%" if KAIG_AVAILABLE else "—"
        bg.addWidget(_value_label(rate_txt, size=13, color=NEON_GREEN), 4, 1)
        cl.addWidget(buyback_group)

        # How it works
        info_group = QGroupBox("How KAIG Buyback Works")
        info_group.setStyleSheet(CARD_STYLE)
        ig = QVBoxLayout(info_group)
        steps = [
            "1. Kingdom AI trades crypto on exchanges (BTC, ETH, SOL, etc.)",
            "2. Trading profits are recorded by the AI engine",
            f"3. {int(TRADING_PROFIT_BUYBACK_RATE*100)}% of profits automatically allocated to KAIG buyback",
            "4. Treasury buys KAIG from internal market at current price",
            "5. Buy pressure increases KAIG price toward $10 target",
            "6. Transaction fees (0.1%) are burned — permanent supply reduction",
            "7. Strong internal economy established BEFORE public listing",
        ]
        for step in steps:
            ig.addWidget(_cyan_label(step, size=11))
        cl.addWidget(info_group)

        # Reserves
        reserves_group = QGroupBox("Multi-Asset Reserves")
        reserves_group.setStyleSheet(CARD_STYLE)
        rg = QGridLayout(reserves_group)
        rg.addWidget(_gold_label("Asset", size=12), 0, 0)
        rg.addWidget(_gold_label("Amount", size=12), 0, 1)

        self.reserve_btc = _value_label("0.000000 BTC", size=12)
        self.reserve_eth = _value_label("0.000000 ETH", size=12)
        self.reserve_usdc = _value_label("$0.00 USDC", size=12)
        rg.addWidget(_cyan_label("BTC"), 1, 0)
        rg.addWidget(self.reserve_btc, 1, 1)
        rg.addWidget(_cyan_label("ETH"), 2, 0)
        rg.addWidget(self.reserve_eth, 2, 1)
        rg.addWidget(_cyan_label("USDC"), 3, 0)
        rg.addWidget(self.reserve_usdc, 3, 1)
        cl.addWidget(reserves_group)

        # Recent Buybacks Table
        bb_table_group = QGroupBox("Recent Buybacks")
        bb_table_group.setStyleSheet(CARD_STYLE)
        btl = QVBoxLayout(bb_table_group)
        self.buyback_table = QTableWidget(0, 5)
        self.buyback_table.setHorizontalHeaderLabels(
            ["Time", "USD Spent", "KAIG Acquired", "Price Before", "Price After"])
        self.buyback_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.buyback_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {KINGDOM_CARD};
                color: {KINGDOM_CYAN};
                border: none;
                gridline-color: {KINGDOM_BORDER};
            }}
            QHeaderView::section {{
                background-color: #0d0d20;
                color: {KINGDOM_GOLD};
                border: 1px solid {KINGDOM_BORDER};
                padding: 4px;
                font-weight: bold;
            }}
        """)
        self.buyback_table.setMaximumHeight(180)
        btl.addWidget(self.buyback_table)
        cl.addWidget(bb_table_group)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return w

    # ══════════════════════════════════════════════════════════════
    # TOKENOMICS SUB-TAB
    # ══════════════════════════════════════════════════════════════
    def _build_tokenomics_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(10)

        # Supply Overview
        supply_group = QGroupBox("KAIG Supply Distribution (Fixed 100M)")
        supply_group.setStyleSheet(CARD_STYLE)
        sg = QGridLayout(supply_group)

        allocations = [
            ("Escrow (Time-Locked)", ESCROW_SUPPLY, "70%", KINGDOM_GOLD),
            ("Treasury (AI-Managed)", TREASURY_SUPPLY, "15%", NEON_GREEN),
            ("Community (Mining/Referrals)", COMMUNITY_SUPPLY, "10%", KINGDOM_CYAN),
            ("Team/Dev (4yr Vest)", TEAM_SUPPLY, "5%", ORANGE),
        ] if KAIG_AVAILABLE else []

        for i, (label, amount, pct, color) in enumerate(allocations):
            sg.addWidget(_cyan_label(label), i, 0)
            sg.addWidget(_value_label(f"{amount:,.0f} KAIG ({pct})", size=13, color=color), i, 1)
        cl.addWidget(supply_group)

        # Live Metrics
        metrics_group = QGroupBox("Live Network Metrics")
        metrics_group.setStyleSheet(CARD_STYLE)
        mg = QGridLayout(metrics_group)

        mg.addWidget(_cyan_label("Total Supply:"), 0, 0)
        self.metric_total_supply = _value_label("100,000,000 KAIG", size=13)
        mg.addWidget(self.metric_total_supply, 0, 1)

        mg.addWidget(_cyan_label("Circulating Supply:"), 1, 0)
        self.metric_circulating = _value_label("0 KAIG", size=13)
        mg.addWidget(self.metric_circulating, 1, 1)

        mg.addWidget(_cyan_label("Total Burned:"), 2, 0)
        self.metric_burned = _value_label("0 KAIG", size=13, color=RED)
        mg.addWidget(self.metric_burned, 2, 1)

        mg.addWidget(_cyan_label("Effective Supply:"), 3, 0)
        self.metric_effective = _value_label("100,000,000 KAIG", size=13)
        mg.addWidget(self.metric_effective, 3, 1)

        mg.addWidget(_cyan_label("Active Wallets:"), 4, 0)
        self.metric_wallets = _value_label("0", size=13)
        mg.addWidget(self.metric_wallets, 4, 1)

        mg.addWidget(_cyan_label("Total Transactions:"), 5, 0)
        self.metric_transactions = _value_label("0", size=13)
        mg.addWidget(self.metric_transactions, 5, 1)
        cl.addWidget(metrics_group)

        # Anti-Failure Design
        design_group = QGroupBox("Anti-Failure Design (Lessons from Pi Coin)")
        design_group.setStyleSheet(CARD_STYLE)
        dg = QVBoxLayout(design_group)
        anti_failures = [
            ("✅ Real utility", "Pay fees, unlock features, governance — not fake mining"),
            ("✅ Revenue-backed", "Trading profits fund treasury — not ads/engagement"),
            ("✅ Fixed supply", "100M cap with burns — not 100B inflationary like Pi"),
            ("✅ Escrow-controlled", "XRP-style time-locks — no sudden dumps"),
            ("✅ AI buybacks", "50% of profits auto-buy KAIG — constant price support"),
            ("✅ Pre-listing economy", "Internal value established BEFORE exchange listing"),
            ("✅ Real nodes", "Bandwidth + compute contribution — not button tapping"),
            ("✅ Deflationary", "0.1% transaction burns — supply shrinks over time"),
        ]
        for title, desc in anti_failures:
            row = QHBoxLayout()
            row.addWidget(_value_label(title, size=12, color=NEON_GREEN))
            row.addWidget(_cyan_label(f"— {desc}", size=11))
            row.addStretch()
            dg.addLayout(row)
        cl.addWidget(design_group)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return w

    # ══════════════════════════════════════════════════════════════
    # ESCROW SUB-TAB
    # ══════════════════════════════════════════════════════════════
    def _build_escrow_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(10)

        escrow_group = QGroupBox("XRP-Style Escrow System")
        escrow_group.setStyleSheet(CARD_STYLE)
        eg = QGridLayout(escrow_group)

        eg.addWidget(_cyan_label("Total Locked:"), 0, 0)
        self.escrow_locked = _value_label("70,000,000 KAIG", size=14, color=KINGDOM_GOLD)
        eg.addWidget(self.escrow_locked, 0, 1)

        eg.addWidget(_cyan_label("Total Released (net):"), 1, 0)
        self.escrow_released = _value_label("0 KAIG", size=13, color=NEON_GREEN)
        eg.addWidget(self.escrow_released, 1, 1)

        eg.addWidget(_cyan_label("Total Re-Locked:"), 2, 0)
        self.escrow_relocked = _value_label("0 KAIG", size=13)
        eg.addWidget(self.escrow_relocked, 2, 1)

        eg.addWidget(_cyan_label("Re-Lock Rate:"), 3, 0)
        eg.addWidget(_value_label("75%", size=13, color=NEON_GREEN), 3, 1)

        eg.addWidget(_cyan_label("Locked Slots:"), 4, 0)
        self.escrow_locked_slots = _value_label("140", size=13)
        eg.addWidget(self.escrow_locked_slots, 4, 1)

        eg.addWidget(_cyan_label("Released Slots:"), 5, 0)
        self.escrow_released_slots = _value_label("0", size=13)
        eg.addWidget(self.escrow_released_slots, 5, 1)

        eg.addWidget(_cyan_label("Next Release:"), 6, 0)
        self.escrow_next_release = _value_label("—", size=13, color=ORANGE)
        eg.addWidget(self.escrow_next_release, 6, 1)

        eg.addWidget(_cyan_label("Monthly Cap:"), 7, 0)
        eg.addWidget(_value_label("500,000 KAIG", size=13), 7, 1)

        eg.addWidget(_cyan_label("Net Monthly Addition:"), 8, 0)
        eg.addWidget(_value_label("~125,000 KAIG (after 75% re-lock)",
                                   size=13, color=KINGDOM_CYAN), 8, 1)
        cl.addWidget(escrow_group)

        # Escrow explanation
        explain_group = QGroupBox("How KAIG Escrow Works (Modeled on XRP)")
        explain_group.setStyleSheet(CARD_STYLE)
        exg = QVBoxLayout(explain_group)
        explanations = [
            "• 70M KAIG locked at genesis in 140 time-locked escrow slots",
            "• Each slot holds 500,000 KAIG and unlocks monthly",
            "• 75% of unlocked tokens are automatically re-locked at end of queue",
            "• Only ~125,000 KAIG enters circulation per month (controlled inflation)",
            "• All escrow operations are transparent and auditable on-chain",
            "• Prevents sudden market flooding — builds investor confidence",
            "• Modeled on Ripple's proven escrow: $7.8B daily volume, rank #4",
        ]
        for exp in explanations:
            exg.addWidget(_cyan_label(exp, size=11))
        cl.addWidget(explain_group)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return w

    # ══════════════════════════════════════════════════════════════
    # TRANSACTIONS SUB-TAB
    # ══════════════════════════════════════════════════════════════
    def _build_transactions_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.tx_table = QTableWidget(0, 5)
        self.tx_table.setHorizontalHeaderLabels(
            ["Time", "Type", "Amount", "Reason", "Balance After"])
        self.tx_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.tx_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {KINGDOM_CARD};
                color: {KINGDOM_CYAN};
                border: 1px solid {KINGDOM_BORDER};
                gridline-color: {KINGDOM_BORDER};
            }}
            QHeaderView::section {{
                background-color: #0d0d20;
                color: {KINGDOM_GOLD};
                border: 1px solid {KINGDOM_BORDER};
                padding: 4px;
                font-weight: bold;
            }}
        """)

        refresh_btn = QPushButton("Refresh Ledger")
        refresh_btn.setStyleSheet(BUTTON_STYLE)
        refresh_btn.setMaximumWidth(200)
        refresh_btn.clicked.connect(self._refresh_transactions)

        layout.addWidget(refresh_btn)
        layout.addWidget(self.tx_table)
        return w

    # ══════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════
    def _start_node(self):
        if not self.engine:
            return
        result = self.engine.node.start()
        if result.get("status") == "started":
            self.start_node_btn.setEnabled(False)
            self.stop_node_btn.setEnabled(True)
            self.node_status_label.setText("ONLINE")
            self.node_status_label.setStyleSheet(
                f"color: {NEON_GREEN}; font-size: 14px; font-weight: bold;")
            self._node_timer.start(30000)  # Heartbeat every 30s
            logger.info("KAIG Node started: %s", result.get("node_id"))

    def _stop_node(self):
        if not self.engine:
            return
        self._node_timer.stop()
        result = self.engine.node.stop()
        self.start_node_btn.setEnabled(True)
        self.stop_node_btn.setEnabled(False)
        self.node_status_label.setText("OFFLINE")
        self.node_status_label.setStyleSheet(
            f"color: {RED}; font-size: 14px; font-weight: bold;")
        logger.info("KAIG Node stopped: earned %.6f KAIG",
                    result.get("session_earned", 0))

    def _node_heartbeat(self):
        if not self.engine or not self.engine.node.is_running:
            return
        beat = self.engine.node.heartbeat()
        if not beat:
            return

        # Update uptime
        uptime = self.engine.node.uptime_seconds
        h, m, s = int(uptime // 3600), int((uptime % 3600) // 60), int(uptime % 60)
        self.node_uptime_label.setText(f"{h}:{m:02d}:{s:02d}")

        if beat.get("status") == "rewarded":
            self.node_session_earned.setText(
                f"{beat['session_earned']:.6f} KAIG")
            self.node_today_earned.setText(
                f"{beat['today_earned']:.6f} KAIG")
            self.node_balance.setText(
                f"{beat['balance']:.6f} KAIG")
        elif beat.get("status") == "daily_cap_reached":
            self.node_today_earned.setText(
                f"{beat['today_earned']:.6f} KAIG (CAP REACHED)")

        # Also check escrow releases
        self.engine.check_escrow_releases()

    def _refresh_all_stats(self):
        if not self.engine:
            return
        if getattr(self, '_kaig_refresh_running', False):
            return
        self._kaig_refresh_running = True
        import threading as _th
        def _fetch():
            try:
                status = self.engine.get_full_status()
                if status:
                    self._cached_kaig_status = status
                    if hasattr(self, '_stats_apply_timer'):
                        self._stats_apply_timer.start(0)
            except Exception:
                pass
            finally:
                self._kaig_refresh_running = False
        _th.Thread(target=_fetch, daemon=True, name="KAIGStatsRefresh").start()

    def _apply_cached_kaig_stats(self):
        status = getattr(self, '_cached_kaig_status', None)
        if not status or not isinstance(status, dict):
            return
        try:
            self._apply_kaig_status(status)
        except Exception as e:
            logger.debug("KAIG stats apply error: %s", e)

    def _apply_kaig_status(self, status):
        try:

            # Price
            price = status.get("current_price", INITIAL_PRICE)
            self.price_label.setText(f"${price:.4f}")
            progress = min(int((price / TARGET_PRICE) * 10000), 10000)
            self.price_progress.setValue(progress)

            # Node
            node = status.get("node", {})
            self.node_id_label.setText(node.get("node_id", "—"))
            ns = node.get("status", "offline")
            self.node_status_label.setText(ns.upper())
            color = NEON_GREEN if ns == "online" else RED
            self.node_status_label.setStyleSheet(
                f"color: {color}; font-size: 14px; font-weight: bold;")
            self.node_total_earned.setText(
                f"{node.get('total_earned', 0):.6f} KAIG")
            self.node_balance.setText(
                f"{node.get('balance', 0):.6f} KAIG")
            self.bandwidth_label.setText(
                f"{node.get('bandwidth_contributed_mb', 0):.1f} MB")
            self.compute_label.setText(str(node.get("compute_tasks", 0)))
            self.stake_label.setText(
                f"{node.get('stake_amount', 0):.2f} KAIG")

            # Network
            net = status.get("network", {})
            self.net_total_nodes.setText(str(net.get("total_nodes", 0)))
            self.net_online_nodes.setText(str(net.get("online_nodes", 0)))
            self.net_total_staked.setText(
                f"{net.get('total_staked', 0):,.2f} KAIG")
            self.net_total_rewards.setText(
                f"{net.get('total_rewards_distributed', 0):,.6f} KAIG")

            # Treasury
            treasury = status.get("treasury", {})
            self.treasury_price.setText(
                f"${treasury.get('internal_price', INITIAL_PRICE):.4f}")
            self.treasury_progress.setText(
                f"{treasury.get('progress_to_target', 0):.2f}%")
            self.treasury_kaig_held.setText(
                f"{treasury.get('kaig_held_by_treasury', 0):,.0f} KAIG")
            self.treasury_value.setText(
                f"${treasury.get('treasury_value_usd', 0):,.2f}")
            self.buyback_total_usd.setText(
                f"${treasury.get('total_buyback_usd', 0):,.2f}")
            self.buyback_total_kaig.setText(
                f"{treasury.get('total_buyback_kaig', 0):,.2f} KAIG")
            self.buyback_pending.setText(
                f"${treasury.get('pending_buyback_usd', 0):,.2f}")
            self.buyback_count.setText(str(treasury.get("num_buybacks", 0)))

            reserves = treasury.get("reserves", {})
            self.reserve_btc.setText(f"{reserves.get('BTC', 0):.6f} BTC")
            self.reserve_eth.setText(f"{reserves.get('ETH', 0):.6f} ETH")
            self.reserve_usdc.setText(f"${reserves.get('USDC', 0):,.2f} USDC")

            # Buyback table
            recent_bb = treasury.get("recent_buybacks", [])
            self.buyback_table.setRowCount(len(recent_bb))
            for row, bb in enumerate(reversed(recent_bb)):
                ts = bb.get("timestamp", "")[:19]
                self.buyback_table.setItem(row, 0, QTableWidgetItem(ts))
                self.buyback_table.setItem(row, 1, QTableWidgetItem(
                    f"${bb.get('usd_amount', 0):,.2f}"))
                self.buyback_table.setItem(row, 2, QTableWidgetItem(
                    f"{bb.get('kaig_amount', 0):,.2f}"))
                self.buyback_table.setItem(row, 3, QTableWidgetItem(
                    f"${bb.get('price_before', 0):.4f}"))
                self.buyback_table.setItem(row, 4, QTableWidgetItem(
                    f"${bb.get('price_after', 0):.4f}"))

            # Escrow
            escrow = status.get("escrow", {})
            self.escrow_locked.setText(
                f"{escrow.get('total_locked', ESCROW_SUPPLY):,.0f} KAIG")
            self.escrow_released.setText(
                f"{escrow.get('total_released', 0):,.0f} KAIG")
            self.escrow_relocked.setText(
                f"{escrow.get('total_relocked', 0):,.0f} KAIG")
            self.escrow_locked_slots.setText(str(escrow.get("locked_slots", 0)))
            self.escrow_released_slots.setText(str(escrow.get("released_slots", 0)))
            nr = escrow.get("next_release_date", "—")
            if nr and nr != "—":
                self.escrow_next_release.setText(nr[:10])
            else:
                self.escrow_next_release.setText("—")

            # Ledger metrics
            ledger = status.get("ledger", {})
            self.metric_circulating.setText(
                f"{ledger.get('total_circulating', 0):,.2f} KAIG")
            self.metric_burned.setText(
                f"{ledger.get('total_burned', 0):,.6f} KAIG")
            self.metric_effective.setText(
                f"{ledger.get('effective_supply', TOTAL_SUPPLY):,.0f} KAIG")
            self.metric_wallets.setText(str(ledger.get("num_wallets", 0)))
            self.metric_transactions.setText(str(ledger.get("num_transactions", 0)))

        except Exception as e:
            logger.error("Failed to refresh KAIG stats: %s", e)

    def _refresh_transactions(self):
        if not self.engine:
            return
        txs = self.engine.ledger.recent_transactions(50)
        self.tx_table.setRowCount(len(txs))
        for row, tx in enumerate(reversed(txs)):
            ts = tx.get("timestamp", "")[:19]
            tx_type = tx.get("type", "?")
            amount = tx.get("amount", 0)
            reason = tx.get("reason", "")
            bal_after = tx.get("balance_after", "—")
            self.tx_table.setItem(row, 0, QTableWidgetItem(ts))
            self.tx_table.setItem(row, 1, QTableWidgetItem(tx_type))
            self.tx_table.setItem(row, 2, QTableWidgetItem(f"{amount:.6f}"))
            self.tx_table.setItem(row, 3, QTableWidgetItem(reason))
            bal_str = f"{bal_after:.6f}" if isinstance(bal_after, float) else str(bal_after)
            self.tx_table.setItem(row, 4, QTableWidgetItem(bal_str))

    # ══════════════════════════════════════════════════════════════
    # ROADMAP SUB-TAB
    # ══════════════════════════════════════════════════════════════
    def _build_roadmap_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(10)

        # Load rollout plan
        plan_data = {}
        current_phase_id = "phase_0_genesis"
        if KAIG_AVAILABLE:
            try:
                plan_data = KAIGEngine.get_rollout_plan()
                engine = KAIGEngine.get_instance()
                if engine:
                    phase_info = engine.get_current_phase()
                    current_phase_id = phase_info.get("current_phase_id", "phase_0_genesis")
            except Exception:
                pass

        phases = plan_data.get("rollout_phases", {})
        phase_order = [
            "phase_0_genesis", "phase_1_accumulation",
            "phase_2_stabilization", "phase_3_pre_listing", "phase_4_listing"
        ]
        phase_icons = {
            "phase_0_genesis": "🌱", "phase_1_accumulation": "📈",
            "phase_2_stabilization": "🏗️", "phase_3_pre_listing": "🔍",
            "phase_4_listing": "🚀",
        }

        for pid in phase_order:
            pdata = phases.get(pid, {})
            name = pdata.get("name", pid)
            duration = pdata.get("duration", "")
            status = pdata.get("status", "PLANNED")
            objectives = pdata.get("objectives", [])
            ai_actions = pdata.get("ai_actions", [])
            metrics = pdata.get("success_metrics", {})
            icon = phase_icons.get(pid, "")
            is_current = (pid == current_phase_id)

            border_color = KINGDOM_GOLD if is_current else KINGDOM_BORDER
            badge = " ← CURRENT" if is_current else ""
            group = QGroupBox(f"{icon} {name}{badge}  [{duration}]")
            group.setStyleSheet(f"""
                QGroupBox {{
                    background-color: {KINGDOM_CARD};
                    border: {'2px' if is_current else '1px'} solid {border_color};
                    border-radius: 8px;
                    padding: 14px 10px 10px 10px;
                    margin-top: 10px;
                    font-weight: bold;
                    color: {KINGDOM_GOLD if is_current else KINGDOM_CYAN};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 6px;
                    color: {KINGDOM_GOLD if is_current else KINGDOM_CYAN};
                    font-size: 13px;
                }}
            """)
            gl = QVBoxLayout(group)

            status_color = NEON_GREEN if status == "ACTIVE" else ORANGE if status == "PLANNED" else "#888"
            sl = _value_label(f"Status: {status}", size=11, color=status_color)
            gl.addWidget(sl)

            if objectives:
                gl.addWidget(_gold_label("Objectives:", size=11))
                for obj in objectives[:5]:
                    gl.addWidget(_cyan_label(f"  • {obj}", size=10))

            if metrics:
                gl.addWidget(_gold_label("Success Metrics:", size=11))
                for mk, mv in list(metrics.items())[:4]:
                    mk_display = mk.replace("_", " ").title()
                    gl.addWidget(_cyan_label(f"  • {mk_display}: {mv}", size=10))

            if ai_actions:
                gl.addWidget(_gold_label("AI Actions:", size=11))
                for action in ai_actions[:3]:
                    gl.addWidget(_value_label(f"  🤖 {action}", size=10, color=NEON_GREEN))

            cl.addWidget(group)

        # Implemented Patterns section
        patterns = plan_data.get("research_patterns_implemented", {})
        if patterns:
            pat_group = QGroupBox("Proven Patterns Implemented")
            pat_group.setStyleSheet(CARD_STYLE)
            pg = QVBoxLayout(pat_group)
            for key, pdata in patterns.items():
                if key == "anti_pi_coin_design":
                    continue
                source = pdata.get("source", key)
                took = pdata.get("what_we_took", "")
                pg.addWidget(_gold_label(f"• {source}", size=10))
                pg.addWidget(_cyan_label(f"    → {took}", size=10))
            cl.addWidget(pat_group)

        # Competitive Advantages
        advantages = plan_data.get("competitive_advantages", [])
        if advantages:
            adv_group = QGroupBox("Competitive Advantages")
            adv_group.setStyleSheet(CARD_STYLE)
            ag = QVBoxLayout(adv_group)
            for adv in advantages:
                ag.addWidget(_value_label(f"  ✅ {adv}", size=10, color=NEON_GREEN))
            cl.addWidget(adv_group)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return w

    # ══════════════════════════════════════════════════════════════
    # LIVE EVENT HANDLERS — real-time UI updates from event bus
    # ══════════════════════════════════════════════════════════════
    def _on_kaig_live_update(self, data):
        """Handle kaig.status.update — refresh key metrics immediately."""
        try:
            if isinstance(data, dict):
                price = data.get("price", 0)
                if price > 0:
                    self.price_label.setText(f"${price:.4f}")
                    self.treasury_price.setText(f"${price:.4f}")
                    progress = min(int((price / TARGET_PRICE) * 10000), 10000)
                    self.price_progress.setValue(progress)
                bb_usd = data.get("total_buyback_usd", 0)
                bb_kaig = data.get("total_buyback_kaig", 0)
                if bb_usd > 0:
                    self.buyback_total_usd.setText(f"${bb_usd:,.2f}")
                    self.buyback_total_kaig.setText(f"{bb_kaig:,.2f} KAIG")
        except Exception as e:
            logger.debug("KAIG live update error: %s", e)

    def _on_kaig_buyback_event(self, data):
        """Handle kaig.buyback — a buyback just executed, refresh stats."""
        try:
            self._refresh_all_stats()
        except Exception:
            pass

    def _on_kaig_node_event(self, data):
        """Handle kaig.node.status — node started/stopped."""
        try:
            if isinstance(data, dict):
                status = data.get("status", "")
                if status == "started":
                    self.node_status_label.setText("ONLINE")
                    self.node_status_label.setStyleSheet(
                        f"color: {NEON_GREEN}; font-size: 14px; font-weight: bold;")
                elif status == "stopped":
                    self.node_status_label.setText("OFFLINE")
                    self.node_status_label.setStyleSheet(
                        f"color: {RED}; font-size: 14px; font-weight: bold;")
        except Exception:
            pass

    def _on_trading_profit_event(self, data):
        """Handle trading.profit — profit detected, UI will refresh on next cycle."""
        try:
            if isinstance(data, dict):
                profit = data.get("profit_usd", 0) or data.get("profit", 0)
                if profit > 0:
                    logger.info("KAIG Tab: trading profit $%.2f detected", profit)
                    # Trigger immediate refresh since buyback may have executed
                    self._refresh_all_stats()
        except Exception:
            pass

    def _on_mining_reward_event(self, data):
        """Handle mining.reward_update — mining rewards flowing into KAIG."""
        try:
            if isinstance(data, dict):
                reward = data.get("estimated_reward", 0)
                if reward > 0:
                    logger.debug("KAIG Tab: mining reward %.8f BTC", reward)
        except Exception:
            pass

    def _on_phase_transition(self, data):
        """Handle kaig.phase.transition — refresh roadmap and stats."""
        try:
            if isinstance(data, dict):
                new_phase = data.get("new_phase", "")
                ai_rec = data.get("ai_recommendation", "")
                logger.info("KAIG Tab: Phase transition to %s | AI: %s", new_phase, ai_rec)
                self._refresh_all_stats()
        except Exception:
            pass

    def _on_ai_insight(self, data):
        """Handle kaig.autopilot.ai_insight — log AI strategic recommendation."""
        try:
            if isinstance(data, dict):
                rec = data.get("recommendation", "")
                if rec:
                    logger.info("KAIG Tab: AI Insight — %s", rec[:200])
        except Exception:
            pass

    def _on_ath_update(self, data):
        """Handle kaig.ath.update — new crypto ATH detected, KAIG floor raised."""
        try:
            if isinstance(data, dict):
                coin = data.get("new_ath_coin", "")
                price = data.get("new_ath_price", 0)
                floor = data.get("kaig_price_floor", 0)
                if coin and price:
                    logger.info("KAIG Tab: New ATH — %s $%s | KAIG floor: $%s",
                                coin, f"{price:,.2f}", f"{floor:,.2f}")
                    self._refresh_all_stats()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════
    # INSTALL ON MY PHONE (Kaig Wi-Fi QR) -- creator only
    # ══════════════════════════════════════════════════════════════
    def _build_install_phone_tab(self) -> QWidget:
        """Creator-only panel that launches core/creator_install_server.py
        and shows a QR so the creator can scan from their phone and install
        the creator app over the desktop's Wi-Fi network."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        heading = QLabel("Install Kingdom AI on My Phone")
        heading.setStyleSheet(f"color: {KINGDOM_GOLD}; font-size: 20px; font-weight: bold;")
        layout.addWidget(heading)

        explainer = QLabel(
            "Click the button below to start a short-lived Wi-Fi server on this "
            "desktop. A QR code will appear. Scan it with your iPhone camera "
            "(or any Android phone on the same Wi-Fi) and the creator app will "
            "install automatically. The server auto-shuts after one successful "
            "install or 10 minutes, whichever comes first."
        )
        explainer.setWordWrap(True)
        explainer.setStyleSheet(f"color: {KINGDOM_CYAN}; font-size: 12px;")
        layout.addWidget(explainer)

        self._install_qr_label = QLabel()
        self._install_qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._install_qr_label.setMinimumHeight(320)
        self._install_qr_label.setStyleSheet(
            f"background: #0A0E17; border: 1px solid {KINGDOM_BORDER}; border-radius: 12px;"
        )
        layout.addWidget(self._install_qr_label)

        self._install_status = QLabel("Server idle. Click the button to begin.")
        self._install_status.setStyleSheet(f"color: {KINGDOM_CYAN}; font-size: 11px;")
        self._install_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._install_status)

        btn = QPushButton("📱  Install Kingdom AI on My Phone (Wi-Fi)")
        btn.setMinimumHeight(44)
        btn.clicked.connect(self._on_install_phone_clicked)
        layout.addWidget(btn)

        warning = QLabel(
            "Reminder: this flow is for YOUR phones only. The consumer app is a "
            "separate, sanitized build on kingdom-ai.netlify.app. The server "
            "below refuses any client outside your Wi-Fi subnet and uses a "
            "one-shot token."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #888; font-size: 10px; padding-top: 8px;")
        layout.addWidget(warning)

        layout.addStretch(1)
        return w

    def _on_install_phone_clicked(self):
        """Launch the creator install server and render a QR code."""
        try:
            from pathlib import Path as _Path
            from core.creator_install_server import CreatorInstallServer
        except Exception as e:
            self._install_status.setText(f"Cannot import install server: {e}")
            return

        try:
            artifact_dir = _Path.home() / "KingdomAI-Private"
            if not artifact_dir.exists():
                self._install_status.setText(
                    f"Missing {artifact_dir}. Run scripts/build_creator_pwa.sh first "
                    "(and scripts/build_creator_apk.sh if you plan to scan from Android)."
                )
                return
            srv = CreatorInstallServer(artifact_dir=artifact_dir)
            url, token, qr_data = srv.start()
            self._install_status.setText(
                f"Server listening. Scan with your phone camera within 10 minutes.\n{url}"
            )
            self._render_install_qr(qr_data)
        except Exception as e:
            self._install_status.setText(f"Failed to start install server: {e}")

    def _render_install_qr(self, data: str):
        """Render the QR into self._install_qr_label."""
        try:
            import qrcode
            from io import BytesIO
            from PyQt6.QtGui import QPixmap
            img = qrcode.make(data)
            buf = BytesIO()
            img.save(buf, format="PNG")
            pix = QPixmap()
            pix.loadFromData(buf.getvalue(), "PNG")
            self._install_qr_label.setPixmap(pix)
        except Exception as e:
            self._install_qr_label.setText(f"QR render failed ({e}).\nURL: {data}")
