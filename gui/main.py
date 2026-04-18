import tkinter as tk
from tkinter import ttk, messagebox
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class KingdomAIGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Kingdom AI System")
        self.root.geometry("800x600")

        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add status label
        self.status_label = ttk.Label(self.main_frame, text="Kingdom AI Status: Initializing...")
        self.status_label.grid(row=0, column=0, pady=10)
        
    def update_status(self, status):
        self.status_label.config(text=f"Kingdom AI Status: {status}")
        
    def show_error(self, error_msg):
        logger.error(error_msg)
        messagebox.showerror("Error", error_msg)
