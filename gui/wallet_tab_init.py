"""
Kingdom AI Wallet Tab Initialization
"""
import logging
logger = logging.getLogger("KingdomAI.TabManager")

async def _init_wallet_tab(self, tab_frame):
    """Initialize cryptocurrency wallet tab with balance tracking and transactions."""
    try:
        # STEP 1: RETRIEVAL - Data sources
        logger.info("Wallet tab initializing with wallet data sources")
        
        # UI creation based on framework
        if self.using_pyqt:
            from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QTableWidget
            from PyQt6.QtCore import Qt
            
            # Layout setup
            layout = tab_frame.layout()
            
            # Header
            header = QFrame()
            header_layout = QHBoxLayout(header)
            title = QLabel("Cryptocurrency Wallet")
            title.setStyleSheet("font-size: 18px; font-weight: bold;")
            self.wallet_status = QLabel("Status: Initializing...")
            header_layout.addWidget(title, 1)
            header_layout.addWidget(self.wallet_status)
            layout.addWidget(header)
            
            # Balance section
            balance_frame = QFrame()
            balance_layout = QVBoxLayout(balance_frame)
            balance_layout.addWidget(QLabel("Wallet Balances"))
            self.balance_table = QTableWidget(0, 4)
            self.balance_table.setHorizontalHeaderLabels(["Currency", "Balance", "USD Value", "24h Change"])
            balance_layout.addWidget(self.balance_table)
            self.total_balance = QLabel("$0.00")
            balance_layout.addWidget(self.total_balance)
            layout.addWidget(balance_frame)
            
            # Transactions
            tx_frame = QFrame()
            tx_layout = QVBoxLayout(tx_frame)
            tx_layout.addWidget(QLabel("Recent Transactions"))
            self.tx_table = QTableWidget(0, 4)
            self.tx_table.setHorizontalHeaderLabels(["Date", "Type", "Amount", "Status"])
            tx_layout.addWidget(self.tx_table)
            layout.addWidget(tx_frame)
            
            # Actions
            actions = QFrame()
            actions_layout = QHBoxLayout(actions)
            actions_layout.addWidget(QPushButton("Send", clicked=lambda: self.send_crypto()))
            actions_layout.addWidget(QPushButton("Receive", clicked=lambda: self.receive_crypto()))
            actions_layout.addWidget(QPushButton("Refresh", clicked=lambda: self.refresh_wallet()))
            layout.addWidget(actions)
            
            # Register widgets for updates
            if hasattr(self, 'widget_registry'):
                await self.widget_registry.register_widget("wallet_status", self.wallet_status)
                await self.widget_registry.register_widget("balance_table", self.balance_table)
                await self.widget_registry.register_widget("tx_table", self.tx_table)
                
        else:  # Tkinter
            import tkinter as tk
            from tkinter import ttk
            
            # Header
            title_frame = ttk.Frame(tab_frame)
            title_frame.pack(fill="x", padx=10, pady=5)
            title_label = ttk.Label(title_frame, text="Cryptocurrency Wallet", font=("Helvetica", 14, "bold"))
            title_label.pack(side="left")
            self.wallet_status = ttk.Label(title_frame, text="Status: Initializing...")
            self.wallet_status.pack(side="right")
            
            # Balance section
            balance_frame = ttk.LabelFrame(tab_frame, text="Wallet Balances")
            balance_frame.pack(fill="both", expand=True, padx=10, pady=5)
            
            # Create table with scrollbar
            balance_columns = ("currency", "balance", "usd_value", "change")
            self.balance_table = ttk.Treeview(balance_frame, columns=balance_columns, show="headings")
            self.balance_table.heading("currency", text="Currency")
            self.balance_table.heading("balance", text="Balance")
            self.balance_table.heading("usd_value", text="USD Value")
            self.balance_table.heading("change", text="24h Change")
            self.balance_table.pack(fill="both", expand=True)
            
            # Total balance
            total_frame = ttk.Frame(balance_frame)
            total_frame.pack(fill="x", padx=5, pady=5)
            ttk.Label(total_frame, text="Total Balance (USD):").pack(side="left")
            self.total_balance = ttk.Label(total_frame, text="$0.00")
            self.total_balance.pack(side="left", padx=5)
            
            # Transaction section
            tx_frame = ttk.LabelFrame(tab_frame, text="Recent Transactions")
            tx_frame.pack(fill="both", expand=True, padx=10, pady=5)
            
            tx_columns = ("date", "type", "amount", "status")
            self.tx_table = ttk.Treeview(tx_frame, columns=tx_columns, show="headings")
            self.tx_table.heading("date", text="Date")
            self.tx_table.heading("type", text="Type")
            self.tx_table.heading("amount", text="Amount")
            self.tx_table.heading("status", text="Status")
            self.tx_table.pack(fill="both", expand=True)
            
            # Actions frame
            actions_frame = ttk.Frame(tab_frame)
            actions_frame.pack(fill="x", padx=10, pady=10)
            
            send_btn = ttk.Button(actions_frame, text="Send", command=self.send_crypto)
            send_btn.pack(side="left", padx=5)
            
            receive_btn = ttk.Button(actions_frame, text="Receive", command=self.receive_crypto)
            receive_btn.pack(side="left", padx=5)
            
            refresh_btn = ttk.Button(actions_frame, text="Refresh", command=self.refresh_wallet)
            refresh_btn.pack(side="left", padx=5)
            
            # Register widgets for updates
            if hasattr(self, 'widget_registry'):
                await self.widget_registry.register_widget("wallet_status", self.wallet_status)
                await self.widget_registry.register_widget("balance_table", self.balance_table)
                await self.widget_registry.register_widget("tx_table", self.tx_table)
        
        # Fetch initial data
        if self.event_bus:
            await self.request_wallet_data()
            
        logger.info("Wallet tab initialized")
        
    except Exception as e:
        logger.error(f"Error initializing wallet tab: {e}")

async def update_wallet_data(self, data):
    """Update wallet with balance and transaction data."""
    try:
        logger.info(f"Received wallet data update")
        
        # Update status
        if hasattr(self, 'wallet_status'):
            status = data.get('status', 'Unknown')
            if self.using_pyqt:
                self.wallet_status.setText(f"Status: {status}")
            else:
                self.wallet_status.config(text=f"Status: {status}")
                
        # Update balances
        if 'balances' in data and hasattr(self, 'balance_table'):
            balances = data.get('balances', [])
            self._update_balance_table(balances)
            
        # Update transactions
        if 'transactions' in data and hasattr(self, 'tx_table'):
            transactions = data.get('transactions', [])
            self._update_transaction_table(transactions)
            
        # Update total balance
        if 'total_balance_usd' in data and hasattr(self, 'total_balance'):
            total = data.get('total_balance_usd', 0)
            formatted_total = f"${total:,.2f}"
            if self.using_pyqt:
                self.total_balance.setText(formatted_total)
            else:
                self.total_balance.config(text=formatted_total)
                
    except Exception as e:
        logger.error(f"Error updating wallet data: {e}")
