#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI GUI Launcher

This module provides a standalone GUI launcher for the Kingdom AI system
that can be used in WSL and other environments where threading might be an issue.
"""

import os
import sys
import logging
import tkinter as tk
from tkinter import ttk
import json
import socket
import threading
import time

# Setup logging
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(_LOG_DIR, 'kingdom_gui.log'))
    ]
)

logger = logging.getLogger('KingdomAI.GUILauncher')

class GUIStandalone:
    """Standalone GUI launcher for Kingdom AI."""
    
    def __init__(self):
        """Initialize the GUI launcher."""
        self.root = None
        self.main_frame = None
        self.is_running = False
        self.socket = None
        self.socket_thread = None
        self.message_queue = []
        
    def initialize(self):
        """Initialize the GUI."""
        try:
            # Create the root window
            self.root = tk.Tk()
            self.root.title("Kingdom AI")
            self.root.geometry("1200x800")
            self.root.minsize(800, 600)
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            
            # Create a style
            style = ttk.Style()
            style.configure("TFrame", background="#1E1E1E")
            style.configure("TLabel", background="#1E1E1E", foreground="#FFFFFF")
            style.configure("TButton", background="#333333", foreground="#FFFFFF")
            
            # Create main frame
            self.main_frame = ttk.Frame(self.root, style="TFrame")
            self.main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Add a label
            title_label = ttk.Label(
                self.main_frame, 
                text="Kingdom AI",
                font=("Helvetica", 24),
                style="TLabel"
            )
            title_label.pack(pady=20)
            
            # Add a subtitle
            subtitle_label = ttk.Label(
                self.main_frame,
                text="System Initialized",
                font=("Helvetica", 12),
                style="TLabel"
            )
            subtitle_label.pack(pady=10)
            
            # Create a status message
            self.status_var = tk.StringVar()
            self.status_var.set("Welcome to Kingdom AI")
            status_label = ttk.Label(
                self.main_frame,
                textvariable=self.status_var,
                font=("Helvetica", 10),
                style="TLabel"
            )
            status_label.pack(pady=10)
            
            # Create a frame for dashboard
            dashboard_frame = ttk.Frame(self.main_frame, style="TFrame")
            dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Start the socket server for IPC
            self._start_socket_server()
            
            # Mark as running
            self.is_running = True
            logger.info("GUI initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing GUI: {e}")
            return False
            
    def start(self):
        """Start the GUI main loop."""
        if not self.is_running:
            if not self.initialize():
                logger.error("Failed to initialize GUI")
                return False
                
        try:
            # Schedule periodic updates
            self._schedule_updates()
            
            # Start the main loop
            logger.info("Starting main loop")
            self.root.mainloop()
            logger.info("Main loop ended")
            return True
        except Exception as e:
            logger.error(f"Error starting GUI: {e}")
            return False
            
    def _on_close(self):
        """Handle window close event."""
        try:
            logger.info("Closing GUI")
            self.is_running = False
            
            # Close socket
            if self.socket:
                self.socket.close()
                
            # Destroy root
            if self.root:
                self.root.destroy()
                
            logger.info("GUI closed")
        except Exception as e:
            logger.error(f"Error closing GUI: {e}")
            
    def _start_socket_server(self):
        """Start a socket server for IPC."""
        try:
            # Create a socket server
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind(('localhost', 9876))
            self.socket.listen(1)
            
            # Start a thread to handle connections
            self.socket_thread = threading.Thread(target=self._handle_connections, daemon=True)
            self.socket_thread.start()
            
            logger.info("Socket server started")
        except Exception as e:
            logger.error(f"Error starting socket server: {e}")
            
    def _handle_connections(self):
        """Handle socket connections."""
        while self.is_running:
            try:
                # Accept connection
                client, addr = self.socket.accept()
                logger.info(f"Connection from {addr}")
                
                # Receive data
                data = client.recv(4096)
                if data:
                    # Process data
                    self._process_message(data.decode('utf-8'))
                    
                # Close connection
                client.close()
            except Exception as e:
                if self.is_running:
                    logger.error(f"Error handling connection: {e}")
                else:
                    break
                    
    def _process_message(self, message):
        """Process a message from the main application."""
        try:
            # Parse JSON message
            data = json.loads(message)
            
            # Add to queue
            self.message_queue.append(data)
            
            # Update status if provided
            if 'status' in data:
                self.status_var.set(data['status'])
                
            logger.info(f"Processed message: {data}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
    def _schedule_updates(self):
        """Schedule periodic UI updates."""
        if not self.is_running:
            return
            
        try:
            # Process any messages in the queue
            while self.message_queue:
                message = self.message_queue.pop(0)
                self._update_ui(message)
                
            # Schedule next update
            self.root.after(100, self._schedule_updates)
        except Exception as e:
            logger.error(f"Error in scheduled update: {e}")
            
    def _update_ui(self, message):
        """Update the UI based on a message."""
        try:
            # Check message type
            if 'type' in message:
                msg_type = message['type']
                
                if msg_type == 'status':
                    # Update status
                    if 'text' in message:
                        self.status_var.set(message['text'])
                elif msg_type == 'update':
                    # Handle component update
                    pass
                elif msg_type == 'alert':
                    # Show alert
                    if 'text' in message:
                        tk.messagebox.showinfo("Alert", message['text'])
                        
            logger.info(f"UI updated with message: {message}")
        except Exception as e:
            logger.error(f"Error updating UI: {e}")

def main():
    """Main entry point for the standalone GUI."""
    try:
        gui = GUIStandalone()
        gui.start()
        return 0
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1
        
if __name__ == "__main__":
    sys.exit(main())
