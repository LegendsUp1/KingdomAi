"""
XRP GUI Module
Handles graphical user interface for XRP operations
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional
from .xrp_client import XRPClient
from .xrp_wallet import XRPWallet
from .xrp_transaction import XRPTransaction
from .xrp_dex import XRPDex

logger = logging.getLogger(__name__)

class XRPGUI:
    def __init__(self, client: XRPClient):
        self.client = client
        self.wallet = XRPWallet(client)
        self.transaction = XRPTransaction(client)
        self.dex = XRPDex(client)
        
        self.root = tk.Tk()
        self.root.title("Kingdom AI - XRP Dashboard")
        self.setup_gui()
        
    def setup_gui(self):
        """Setup the main GUI components"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        
        # Create tabs
        self.wallet_tab = ttk.Frame(self.notebook)
        self.transaction_tab = ttk.Frame(self.notebook)
        self.dex_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.wallet_tab, text="Wallet")
        self.notebook.add(self.transaction_tab, text="Transactions")
        self.notebook.add(self.dex_tab, text="DEX")
        
        self.notebook.pack(expand=True, fill="both")
        
        # Setup individual tabs
        self.setup_wallet_tab()
        self.setup_transaction_tab()
        self.setup_dex_tab()
        
    def setup_wallet_tab(self):
        """Setup wallet management tab"""
        # Create wallet frame
        wallet_frame = ttk.LabelFrame(self.wallet_tab, text="Wallet Management")
        wallet_frame.pack(padx=10, pady=5, fill="x")
        
        # Add wallet controls
        ttk.Button(wallet_frame, text="Create New Wallet", 
                  command=self.create_wallet).pack(pady=5)
        ttk.Button(wallet_frame, text="Load Wallet", 
                  command=self.load_wallet).pack(pady=5)
        ttk.Button(wallet_frame, text="Check Balance", 
                  command=self.check_balance).pack(pady=5)
                  
    def setup_transaction_tab(self):
        """Setup transaction management tab"""
        # Create transaction frame
        tx_frame = ttk.LabelFrame(self.transaction_tab, text="Send XRP")
        tx_frame.pack(padx=10, pady=5, fill="x")
        
        # Add transaction controls
        ttk.Label(tx_frame, text="Destination:").pack(pady=2)
        self.dest_entry = ttk.Entry(tx_frame)
        self.dest_entry.pack(pady=2)
        
        ttk.Label(tx_frame, text="Amount:").pack(pady=2)
        self.amount_entry = ttk.Entry(tx_frame)
        self.amount_entry.pack(pady=2)
        
        ttk.Button(tx_frame, text="Send XRP", 
                  command=self.send_xrp).pack(pady=5)
                  
    def setup_dex_tab(self):
        """Setup DEX management tab"""
        # Create DEX frame
        dex_frame = ttk.LabelFrame(self.dex_tab, text="DEX Operations")
        dex_frame.pack(padx=10, pady=5, fill="x")
        
        # Add DEX controls
        ttk.Button(dex_frame, text="View Order Book", 
                  command=self.view_order_book).pack(pady=5)
        ttk.Button(dex_frame, text="Create Offer", 
                  command=self.create_offer).pack(pady=5)
        ttk.Button(dex_frame, text="View My Offers", 
                  command=self.view_offers).pack(pady=5)
        
    async def create_wallet(self):
        """Create new wallet handler"""
        try:
            result = self.wallet.create_wallet()
            if result["status"] == "success":
                messagebox.showinfo("Success", 
                    f"Wallet created!\nAddress: {result['address']}\nSeed: {result['seed']}")
            else:
                messagebox.showerror("Error", result["message"])
        except Exception as e:
            logger.error(f"Failed to create wallet: {e}")
            messagebox.showerror("Error", str(e))
            
    async def load_wallet(self):
        """Load existing wallet handler"""
        seed = tk.simpledialog.askstring("Load Wallet", 
            "Enter wallet seed:", show="*")
        if seed:
            try:
                result = self.wallet.load_wallet(seed)
                if result["status"] == "success":
                    messagebox.showinfo("Success", 
                        f"Wallet loaded!\nAddress: {result['address']}")
                else:
                    messagebox.showerror("Error", result["message"])
            except Exception as e:
                logger.error(f"Failed to load wallet: {e}")
                messagebox.showerror("Error", str(e))
                
    async def check_balance(self):
        """Check wallet balance handler"""
        try:
            result = await self.wallet.get_balance()
            if result["status"] == "success":
                messagebox.showinfo("Balance", 
                    f"Current balance: {result['balance']} XRP")
            else:
                messagebox.showerror("Error", result["message"])
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            messagebox.showerror("Error", str(e))
            
    def run(self):
        """Start the GUI"""
        self.root.mainloop()
