"""
Kingdom AI VR Tab Initialization
"""
import logging
logger = logging.getLogger("KingdomAI.TabManager")

async def _init_vr_tab(self, tab_frame):
    """Initialize VR interface tab with visualization controls."""
    try:
        # STEP 1: RETRIEVAL - Data sources
        logger.info("VR tab initializing with visualization data sources")
        
        # UI creation based on framework
        if self.using_pyqt:
            from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QComboBox, QSlider, QCheckBox
            from PyQt6.QtCore import Qt
            
            # Layout setup
            layout = tab_frame.layout()
            
            # Header
            header = QFrame()
            header_layout = QHBoxLayout(header)
            title = QLabel("VR Visualization")
            title.setStyleSheet("font-size: 18px; font-weight: bold;")
            self.vr_status = QLabel("Status: Disconnected")
            self.vr_status.setStyleSheet("color: gray;")
            header_layout.addWidget(title, 1)
            header_layout.addWidget(self.vr_status)
            layout.addWidget(header)
            
            # VR Mode section
            mode_frame = QFrame()
            mode_layout = QVBoxLayout(mode_frame)
            mode_layout.addWidget(QLabel("Visualization Mode"))
            
            self.vr_mode_selector = QComboBox()
            self.vr_mode_selector.addItems(["Market Data", "Trading Visualization", "Portfolio Analysis", "Mining Status"])
            mode_layout.addWidget(self.vr_mode_selector)
            
            # Quality settings
            quality_layout = QHBoxLayout()
            quality_layout.addWidget(QLabel("Visual Quality:"))
            self.quality_slider = QSlider(Qt.Orientation.Horizontal)
            self.quality_slider.setRange(1, 5)
            self.quality_slider.setValue(3)
            quality_layout.addWidget(self.quality_slider)
            mode_layout.addLayout(quality_layout)
            
            layout.addWidget(mode_frame)
            
            # Device section
            device_frame = QFrame()
            device_layout = QVBoxLayout(device_frame)
            device_layout.addWidget(QLabel("VR Devices"))
            
            self.device_selector = QComboBox()
            self.device_selector.addItems(["Oculus Quest 2", "HTC Vive", "Valve Index", "No Device"])
            device_layout.addWidget(self.device_selector)
            
            # Auto-connect checkbox
            self.auto_connect = QCheckBox("Auto-connect on startup")
            device_layout.addWidget(self.auto_connect)
            
            layout.addWidget(device_frame)
            
            # Preview section
            preview_frame = QFrame()
            preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
            preview_frame.setMinimumHeight(200)
            preview_layout = QVBoxLayout(preview_frame)
            preview_layout.addWidget(QLabel("VR Preview"))
            self.preview_placeholder = QLabel("VR preview will appear here when connected")
            self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_placeholder.setStyleSheet("background-color: #222; color: #ddd; border: 1px solid #555;")
            preview_layout.addWidget(self.preview_placeholder)
            
            layout.addWidget(preview_frame)
            
            # Actions
            actions = QFrame()
            actions_layout = QHBoxLayout(actions)
            
            connect_btn = QPushButton("Connect VR")
            connect_btn.clicked.connect(self.connect_vr)
            actions_layout.addWidget(connect_btn)
            
            launch_btn = QPushButton("Launch VR View")
            launch_btn.clicked.connect(self.launch_vr)
            actions_layout.addWidget(launch_btn)
            
            settings_btn = QPushButton("VR Settings")
            settings_btn.clicked.connect(self.vr_settings)
            actions_layout.addWidget(settings_btn)
            
            layout.addWidget(actions)
            
            # Register widgets for updates
            if hasattr(self, 'widget_registry'):
                await self.widget_registry.register_widget("vr_status", self.vr_status)
                await self.widget_registry.register_widget("vr_mode", self.vr_mode_selector)
                await self.widget_registry.register_widget("vr_device", self.device_selector)
                await self.widget_registry.register_widget("vr_preview", self.preview_placeholder)
                
        else:  # Tkinter
            import tkinter as tk
            from tkinter import ttk
            
            # Header
            title_frame = ttk.Frame(tab_frame)
            title_frame.pack(fill="x", padx=10, pady=5)
            title_label = ttk.Label(title_frame, text="VR Visualization", font=("Helvetica", 14, "bold"))
            title_label.pack(side="left")
            self.vr_status = ttk.Label(title_frame, text="Status: Disconnected", foreground="gray")
            self.vr_status.pack(side="right")
            
            # VR Mode frame
            mode_frame = ttk.LabelFrame(tab_frame, text="Visualization Mode")
            mode_frame.pack(fill="x", expand=False, padx=10, pady=5)
            
            self.vr_mode_selector = ttk.Combobox(mode_frame, values=["Market Data", "Trading Visualization", "Portfolio Analysis", "Mining Status"])
            self.vr_mode_selector.pack(fill="x", padx=5, pady=5)
            self.vr_mode_selector.current(0)
            
            # Quality frame
            quality_frame = ttk.Frame(mode_frame)
            quality_frame.pack(fill="x", padx=5, pady=5)
            ttk.Label(quality_frame, text="Visual Quality:").pack(side="left")
            self.quality_slider = ttk.Scale(quality_frame, from_=1, to=5, orient=tk.HORIZONTAL)
            self.quality_slider.pack(side="left", fill="x", expand=True)
            self.quality_slider.set(3)
            
            # Device frame
            device_frame = ttk.LabelFrame(tab_frame, text="VR Devices")
            device_frame.pack(fill="x", expand=False, padx=10, pady=5)
            
            self.device_selector = ttk.Combobox(device_frame, values=["Oculus Quest 2", "HTC Vive", "Valve Index", "No Device"])
            self.device_selector.pack(fill="x", padx=5, pady=5)
            self.device_selector.current(3)
            
            # Auto-connect checkbox
            self.auto_connect_var = tk.BooleanVar()
            auto_connect_checkbox = ttk.Checkbutton(device_frame, text="Auto-connect on startup", variable=self.auto_connect_var)
            auto_connect_checkbox.pack(anchor="w", padx=5, pady=5)
            
            # Preview frame
            preview_frame = ttk.LabelFrame(tab_frame, text="VR Preview")
            preview_frame.pack(fill="both", expand=True, padx=10, pady=5)
            
            self.preview_placeholder = ttk.Label(preview_frame, text="VR preview will appear here when connected")
            self.preview_placeholder.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Add a canvas for the preview with a black background
            preview_canvas = tk.Canvas(self.preview_placeholder, bg="#222222", height=150)
            preview_canvas.pack(fill="both", expand=True)
            preview_canvas.create_text(150, 75, text="VR Preview (Connect to view)", fill="#dddddd")
            
            # Actions frame
            actions_frame = ttk.Frame(tab_frame)
            actions_frame.pack(fill="x", padx=10, pady=10)
            
            connect_btn = ttk.Button(actions_frame, text="Connect VR", command=self.connect_vr)
            connect_btn.pack(side="left", padx=5)
            
            launch_btn = ttk.Button(actions_frame, text="Launch VR View", command=self.launch_vr)
            launch_btn.pack(side="left", padx=5)
            
            settings_btn = ttk.Button(actions_frame, text="VR Settings", command=self.vr_settings)
            settings_btn.pack(side="left", padx=5)
            
            # Register widgets for updates
            if hasattr(self, 'widget_registry'):
                await self.widget_registry.register_widget("vr_status", self.vr_status)
                await self.widget_registry.register_widget("vr_mode", self.vr_mode_selector)
                await self.widget_registry.register_widget("vr_device", self.device_selector)
                await self.widget_registry.register_widget("vr_preview", self.preview_placeholder)
        
        # Fetch initial data
        if self.event_bus:
            await self.request_vr_status()
            
        logger.info("VR tab initialized")
        
    except Exception as e:
        logger.error(f"Error initializing VR tab: {e}")

async def update_vr_status(self, data):
    """Update VR status with connection information."""
    try:
        logger.info("Received VR status update")
        
        # Update connection status
        if hasattr(self, 'vr_status'):
            status = data.get('status', 'Disconnected')
            status_text = f"Status: {status}"
            
            if self.using_pyqt:
                self.vr_status.setText(status_text)
                if status == "Connected":
                    self.vr_status.setStyleSheet("color: green;")
                elif status == "Disconnected":
                    self.vr_status.setStyleSheet("color: gray;")
                elif status == "Error":
                    self.vr_status.setStyleSheet("color: red;")
            else:
                self.vr_status.config(text=status_text)
                if status == "Connected":
                    self.vr_status.config(foreground="green")
                elif status == "Disconnected":
                    self.vr_status.config(foreground="gray")
                elif status == "Error":
                    self.vr_status.config(foreground="red")
                    
        # Update device selection
        if 'available_devices' in data and hasattr(self, 'device_selector'):
            devices = data.get('available_devices', [])
            
            if devices:
                if self.using_pyqt:
                    current = self.device_selector.currentText()
                    self.device_selector.clear()
                    self.device_selector.addItems(devices)
                    # Try to restore selection
                    index = self.device_selector.findText(current)
                    if index >= 0:
                        self.device_selector.setCurrentIndex(index)
                else:
                    current = self.device_selector.get()
                    self.device_selector['values'] = devices
                    if current in devices:
                        self.device_selector.set(current)
                    else:
                        self.device_selector.current(0)
                        
    except Exception as e:
        logger.error(f"Error updating VR status: {e}")
