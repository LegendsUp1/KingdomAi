#!/usr/bin/env python3
"""
Settings Frame for Kingdom AI GUI.
Provides system-wide configuration and customization options.
"""

import tkinter as tk
from tkinter import ttk
import logging
import os
import sys
from datetime import datetime
import json

from .base_frame import BaseFrame
from ..kingdom_style import KingdomStyles

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class SettingsFrame(BaseFrame):
    """Settings frame for managing system-wide configuration in Kingdom AI."""
    
    def __init__(self, parent, event_bus=None, config_manager=None, api_key_connector=None, name="SettingsFrame", **kwargs):
        """Initialize the settings frame.
        
        Args:
            parent: The parent widget
            event_bus: The event bus for publishing/subscribing to events
            config_manager: Configuration manager for settings
            api_key_connector: Connector for accessing API keys
            name: Name of the frame
            **kwargs: Additional kwargs for the frame
        """
        # Initialize BaseFrame
        super().__init__(parent, event_bus, config_manager, name=name, api_key_connector=api_key_connector, **kwargs)
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Settings categories
        self.settings_categories = [
            "General", "Trading", "Mining", "Wallet", "API Keys", 
            "Advanced", "Appearance", "Network", "Storage", "Updates"
        ]
        
        # Settings data structure
        self.settings = {
            "General": {
                "startup_mode": "auto",
                "log_level": "info",
                "auto_update": True,
                "show_welcome": True
            },
            "Trading": {
                "default_exchange": "binance",
                "trade_confirmation": True,
                "max_leverage": 5,
                "default_position_size": 1.0
            },
            "Mining": {
                "auto_start": False,
                "use_gpu": True,
                "power_limit": 80,
                "mining_pool": "auto"
            },
            "Wallet": {
                "auto_backup": True,
                "backup_frequency": "daily",
                "show_balances": True,
                "default_currency": "USD"
            },
            "API Keys": {
                "key_encryption": True,
                "key_validation": True
            },
            "Advanced": {
                "debug_mode": False,
                "redis_port": 6380,  # Redis Quantum Nexus
                "thread_limit": 16,
                "memory_limit": 4096
            },
            "Appearance": {
                "theme": "dark",
                "animation_speed": 1.0,
                "font_size": "medium",
                "compact_mode": False
            },
            "Network": {
                "connection_timeout": 30,
                "retry_attempts": 3,
                "proxy_enabled": False,
                "proxy_address": ""
            },
            "Storage": {
                "data_directory": "data",
                "auto_cleanup": True,
                "retention_days": 30,
                "compression": True
            },
            "Updates": {
                "check_frequency": "daily",
                "auto_download": True,
                "install_beta": False,
                "update_channel": "stable"
            }
        }
        
        # UI elements
        self.category_listbox = None
        self.settings_notebook = None
        self.settings_frames = {}
        self.settings_widgets = {}
    
    async def initialize(self) -> bool:
        """Initialize the settings frame.
        
        Returns:
            bool: Success status
        """
        self.logger.info("Initializing Settings frame")
        
        try:
            # Call parent initialization
            await super().initialize()
            
            # Load saved settings if available
            await self._load_settings()
            
            # Create settings-specific layout
            self._create_settings_layout()
            
            # Register for events - must await async call
            await self._subscribe_to_events()
            
            # Update status
            self.update_status("Settings frame initialized", 100)
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing Settings Frame: {e}")
            self.update_status(f"Initialization error: {e}", 0)
            return False
    
    async def _subscribe_to_events(self):
        """Subscribe to settings-specific events."""
        try:
            if self.event_bus:
                # Properly await async subscriptions
                await self._safe_subscribe("settings.update", self._handle_settings_update)
                await self._safe_subscribe("settings.reset", self._handle_settings_reset)
                await self._safe_subscribe("settings.save", self._handle_settings_save)
                await self._safe_subscribe("settings.load", self._handle_settings_load)
        except Exception as e:
            self.logger.error(f"Error subscribing to events: {e}")
    
    async def _load_settings(self):
        """Load saved settings from config manager."""
        try:
            if self.config_manager:
                # Try to load settings from config manager
                settings = await self.config_manager.get_config("settings")
                if settings:
                    # Update settings with loaded values, preserving defaults for any missing values
                    for category, category_settings in settings.items():
                        if category in self.settings:
                            self.settings[category].update(category_settings)
                    self.logger.info("Settings loaded from config manager")
            else:
                self.logger.warning("Config manager not available, using default settings")
                
            # Try to load from a local settings file as fallback
            settings_file = os.path.join("config", "settings.json")
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r') as f:
                        file_settings = json.load(f)
                        
                    # Update settings with loaded values, preserving defaults for any missing values
                    for category, category_settings in file_settings.items():
                        if category in self.settings:
                            self.settings[category].update(category_settings)
                            
                    self.logger.info("Settings loaded from local file")
                except Exception as e:
                    self.logger.error(f"Error loading settings from file: {e}")
                
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")
    
    def _create_settings_layout(self):
        """Create the settings layout with categories and configuration options."""
        try:
            # Create main container with split pane
            self.paned_window = tk.PanedWindow(
                self.content_frame, 
                orient=tk.HORIZONTAL,
                bg=KingdomStyles.COLORS["frame_bg"],
                sashwidth=4,
                sashpad=2
            )
            self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create left panel for categories
            left_panel = tk.Frame(self.paned_window, bg=KingdomStyles.COLORS["frame_bg"])
            self.paned_window.add(left_panel, width=200)
            
            # Create category header
            category_header = tk.Label(
                left_panel,
                text="Settings Categories",
                font=("Orbitron", 12, "bold"),
                fg=KingdomStyles.COLORS["primary"],
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            category_header.pack(fill=tk.X, padx=5, pady=5)
            
            # Create scrollable listbox for categories
            listbox_frame = tk.Frame(left_panel, bg=KingdomStyles.COLORS["frame_bg"])
            listbox_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            scrollbar = tk.Scrollbar(listbox_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.category_listbox = tk.Listbox(
                listbox_frame,
                bg=KingdomStyles.COLORS["panel_bg"],
                fg=KingdomStyles.COLORS["text"],
                font=("Segoe UI", 10),
                selectbackground=KingdomStyles.COLORS["primary"],
                selectforeground=KingdomStyles.COLORS["text"],
                activestyle="none",
                highlightthickness=0,
                bd=1,
                exportselection=0,
                yscrollcommand=scrollbar.set
            )
            self.category_listbox.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=self.category_listbox.yview)
            
            # Add categories to listbox
            for category in self.settings_categories:
                self.category_listbox.insert(tk.END, category)
            
            # Bind selection event
            self.category_listbox.bind("<<ListboxSelect>>", self._on_category_select)
            
            # Create right panel for settings content
            right_panel = tk.Frame(self.paned_window, bg=KingdomStyles.COLORS["frame_bg"])
            self.paned_window.add(right_panel, width=400)
            
            # Create settings header
            self.settings_header = tk.Label(
                right_panel,
                text="General Settings",
                font=("Orbitron", 14, "bold"),
                fg=KingdomStyles.COLORS["primary"],
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            self.settings_header.pack(fill=tk.X, padx=10, pady=10)
            
            # Create settings content frame
            self.settings_content = tk.Frame(right_panel, bg=KingdomStyles.COLORS["frame_bg"])
            self.settings_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            # Create all category frames
            self._create_category_frames()
            
            # Show first category by default
            self.category_listbox.selection_set(0)
            self._on_category_select(None)
            
            # Create action buttons
            button_frame = tk.Frame(right_panel, bg=KingdomStyles.COLORS["frame_bg"])
            button_frame.pack(fill=tk.X, padx=10, pady=10)
            
            save_button = self.create_button(
                text="Save Settings",
                command=self._save_settings,
                parent=button_frame
            )
            save_button.pack(side=tk.RIGHT, padx=5)
            
            reset_button = self.create_button(
                text="Reset to Defaults",
                command=self._reset_settings,
                parent=button_frame
            )
            reset_button.pack(side=tk.RIGHT, padx=5)
            
            # Create status bar
            self._create_status_bar()
            
        except Exception as e:
            self.logger.error(f"Error creating settings layout: {e}")
    
    def _create_category_frames(self):
        """Create frames for all settings categories."""
        try:
            # Clear any existing frames
            for widget in self.settings_content.winfo_children():
                widget.destroy()
            
            self.settings_frames = {}
            self.settings_widgets = {}
            
            # Create a frame for each category
            for category in self.settings_categories:
                frame = tk.Frame(self.settings_content, bg=KingdomStyles.COLORS["frame_bg"])
                self.settings_frames[category] = frame
                
                # Initialize widgets dict for this category
                self.settings_widgets[category] = {}
                
                # Create settings for this category
                if category in self.settings:
                    self._create_settings_for_category(category, self.settings[category], frame)
                
                # Hide the frame initially
                frame.pack_forget()
                
        except Exception as e:
            self.logger.error(f"Error creating category frames: {e}")
    
    def _create_settings_for_category(self, category, settings_dict, parent_frame):
        """Create settings widgets for a category.
        
        Args:
            category: The category name
            settings_dict: Dictionary of settings for this category
            parent_frame: Parent frame to place widgets in
        """
        try:
            # Create a LabelFrame for each setting
            for i, (setting_name, setting_value) in enumerate(settings_dict.items()):
                # Create the settings control based on the type of setting
                self._create_setting_control(category, setting_name, setting_value, parent_frame, row=i)
                
        except Exception as e:
            self.logger.error(f"Error creating settings for category {category}: {e}")
    
    def _create_setting_control(self, category, setting_name, setting_value, parent_frame, row=0):
        """Create an appropriate control for a setting based on its type.
        
        Args:
            category: The category name
            setting_name: The setting name
            setting_value: The setting value
            parent_frame: Parent frame to place widget in
            row: Row position in the grid
        """
        try:
            # Create a container frame for this setting
            setting_frame = tk.Frame(parent_frame, bg=KingdomStyles.COLORS["frame_bg"])
            setting_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # Format the setting name for display
            display_name = setting_name.replace("_", " ").title()
            
            # Create label
            label = tk.Label(
                setting_frame,
                text=display_name,
                font=("Segoe UI", 10),
                fg=KingdomStyles.COLORS["text"],
                bg=KingdomStyles.COLORS["frame_bg"],
                anchor=tk.W,
                width=20
            )
            label.pack(side=tk.LEFT, padx=5)
            
            # Create the appropriate control based on the setting type
            if isinstance(setting_value, bool):
                # Boolean toggle
                var = tk.BooleanVar(value=setting_value)
                control = ttk.Checkbutton(
                    setting_frame,
                    variable=var,
                    style="Switch.TCheckbutton"
                )
                control.pack(side=tk.RIGHT, padx=5)
                
                # Store the control and variable
                self.settings_widgets[category][setting_name] = {
                    "control": control,
                    "variable": var
                }
                
            elif isinstance(setting_value, int):
                # Integer spinner
                var = tk.IntVar(value=setting_value)
                
                if setting_name.endswith("port"):
                    # Port number (range 1-65535)
                    min_val, max_val = 1, 65535
                elif setting_name.endswith("limit"):
                    # Limit (range 1-100)
                    min_val, max_val = 1, 100
                else:
                    # Default range
                    min_val, max_val = 0, 9999
                
                control = ttk.Spinbox(
                    setting_frame,
                    from_=min_val,
                    to=max_val,
                    textvariable=var,
                    width=10
                )
                control.pack(side=tk.RIGHT, padx=5)
                
                # Store the control and variable
                self.settings_widgets[category][setting_name] = {
                    "control": control,
                    "variable": var
                }
                
            elif isinstance(setting_value, float):
                # Float spinner or slider
                var = tk.DoubleVar(value=setting_value)
                
                if setting_name == "animation_speed":
                    # Slider for animation speed (0.1-2.0)
                    control = ttk.Scale(
                        setting_frame,
                        from_=0.1,
                        to=2.0,
                        variable=var,
                        orient=tk.HORIZONTAL,
                        length=150
                    )
                    # Add value label
                    value_label = tk.Label(
                        setting_frame,
                        textvariable=var,
                        width=4,
                        font=("Segoe UI", 9),
                        fg=KingdomStyles.COLORS["text"],
                        bg=KingdomStyles.COLORS["frame_bg"]
                    )
                    value_label.pack(side=tk.RIGHT, padx=5)
                else:
                    # Default float spinner
                    control = ttk.Spinbox(
                        setting_frame,
                        from_=0.0,
                        to=100.0,
                        increment=0.1,
                        textvariable=var,
                        width=10
                    )
                
                control.pack(side=tk.RIGHT, padx=5)
                
                # Store the control and variable
                self.settings_widgets[category][setting_name] = {
                    "control": control,
                    "variable": var
                }
                
            elif isinstance(setting_value, str):
                # String entry or combobox
                var = tk.StringVar(value=setting_value)
                
                # Determine if this should be a dropdown
                if setting_name in ["log_level", "theme", "startup_mode", "update_channel", 
                                   "backup_frequency", "default_exchange", "mining_pool",
                                   "default_currency", "check_frequency", "font_size"]:
                    # Create a combobox with appropriate options
                    options = self._get_options_for_setting(setting_name)
                    control = ttk.Combobox(
                        setting_frame,
                        textvariable=var,
                        values=options,
                        state="readonly",
                        width=15
                    )
                else:
                    # Regular text entry
                    control = ttk.Entry(
                        setting_frame,
                        textvariable=var,
                        width=20
                    )
                
                control.pack(side=tk.RIGHT, padx=5)
                
                # Store the control and variable
                self.settings_widgets[category][setting_name] = {
                    "control": control,
                    "variable": var
                }
            
        except Exception as e:
            self.logger.error(f"Error creating control for setting {setting_name}: {e}")
    
    def _get_options_for_setting(self, setting_name):
        """Get appropriate options for a dropdown setting.
        
        Args:
            setting_name: The name of the setting
            
        Returns:
            list: List of options for the dropdown
        """
        # Return appropriate options based on setting name
        if setting_name == "log_level":
            return ["debug", "info", "warning", "error", "critical"]
        elif setting_name == "theme":
            return ["dark", "light", "system", "cyberpunk", "matrix"]
        elif setting_name == "startup_mode":
            return ["auto", "manual", "minimal", "full"]
        elif setting_name == "update_channel":
            return ["stable", "beta", "dev", "nightly"]
        elif setting_name == "backup_frequency":
            return ["hourly", "daily", "weekly", "monthly", "never"]
        elif setting_name == "default_exchange":
            return ["binance", "coinbase", "kraken", "kucoin", "ftx", "custom"]
        elif setting_name == "mining_pool":
            return ["auto", "ethermine", "f2pool", "hiveon", "flexpool", "custom"]
        elif setting_name == "default_currency":
            return ["USD", "EUR", "GBP", "JPY", "BTC", "ETH"]
        elif setting_name == "check_frequency":
            return ["startup", "daily", "weekly", "never"]
        elif setting_name == "font_size":
            return ["small", "medium", "large", "extra-large"]
        else:
            return []
    
    def _on_category_select(self, event):
        """Handle category selection event.
        
        Args:
            event: The selection event
        """
        try:
            # Get the selected category
            selection = self.category_listbox.curselection()
            if not selection:
                return
                
            index = selection[0]
            category = self.category_listbox.get(index)
            
            # Update header
            self.settings_header.config(text=f"{category} Settings")
            
            # Hide all frames
            for frame in self.settings_frames.values():
                frame.pack_forget()
                
            # Show the selected frame
            if category in self.settings_frames:
                self.settings_frames[category].pack(fill=tk.BOTH, expand=True)
                
        except Exception as e:
            self.logger.error(f"Error handling category selection: {e}")
    
    def _save_settings(self):
        """Save current settings."""
        try:
            # Update settings from UI controls
            for category, settings_dict in self.settings_widgets.items():
                for setting_name, widget_dict in settings_dict.items():
                    if "variable" in widget_dict:
                        # Get the value from the control
                        value = widget_dict["variable"].get()
                        
                        # Update the settings dictionary
                        self.settings[category][setting_name] = value
            
            # Save to config manager if available
            if self.config_manager:
                self.config_manager.set_config("settings", self.settings)
                self.logger.info("Settings saved to config manager")
            
            # Also save to local file as backup
            try:
                # Ensure config directory exists
                os.makedirs("config", exist_ok=True)
                
                # Save settings to file
                with open(os.path.join("config", "settings.json"), 'w') as f:
                    json.dump(self.settings, f, indent=4)
                    
                self.logger.info("Settings saved to local file")
            except Exception as e:
                self.logger.error(f"Error saving settings to file: {e}")
            
            # Publish settings update event
            if self.event_bus:
                self.event_bus.publish_sync("settings.updated", {
                    "timestamp": datetime.now().isoformat(),
                    "source": "settings_frame"
                })
            
            # Update status
            self.update_status("Settings saved successfully", 100)
            
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            self.show_error(f"Error saving settings: {e}")
    
    def _reset_settings(self):
        """Reset settings to default values."""
        try:
            # Get the currently selected category
            selection = self.category_listbox.curselection()
            if not selection:
                return
                
            index = selection[0]
            category = self.category_listbox.get(index)
            
            # Reset the UI controls for this category
            if category in self.settings_widgets:
                # Re-create the frame for this category
                self.settings_frames[category].destroy()
                self.settings_frames[category] = tk.Frame(self.settings_content, bg=KingdomStyles.COLORS["frame_bg"])
                
                # Create default settings for this category
                default_settings = {
                    "General": {
                        "startup_mode": "auto",
                        "log_level": "info",
                        "auto_update": True,
                        "show_welcome": True
                    },
                    "Trading": {
                        "default_exchange": "binance",
                        "trade_confirmation": True,
                        "max_leverage": 5,
                        "default_position_size": 1.0
                    },
                    "Mining": {
                        "auto_start": False,
                        "use_gpu": True,
                        "power_limit": 80,
                        "mining_pool": "auto"
                    },
                    "Wallet": {
                        "auto_backup": True,
                        "backup_frequency": "daily",
                        "show_balances": True,
                        "default_currency": "USD"
                    },
                    "API Keys": {
                        "key_encryption": True,
                        "key_validation": True
                    },
                    "Advanced": {
                        "debug_mode": False,
                        "redis_port": 6380,  # Redis Quantum Nexus
                        "thread_limit": 16,
                        "memory_limit": 4096
                    },
                    "Appearance": {
                        "theme": "dark",
                        "animation_speed": 1.0,
                        "font_size": "medium",
                        "compact_mode": False
                    },
                    "Network": {
                        "connection_timeout": 30,
                        "retry_attempts": 3,
                        "proxy_enabled": False,
                        "proxy_address": ""
                    },
                    "Storage": {
                        "data_directory": "data",
                        "auto_cleanup": True,
                        "retention_days": 30,
                        "compression": True
                    },
                    "Updates": {
                        "check_frequency": "daily",
                        "auto_download": True,
                        "install_beta": False,
                        "update_channel": "stable"
                    }
                }
                
                # Reset settings for this category
                if category in default_settings:
                    self.settings[category] = default_settings[category].copy()
                    
                    # Create new widgets
                    self._create_settings_for_category(category, self.settings[category], self.settings_frames[category])
                    
                    # Show the updated frame
                    self.settings_frames[category].pack(fill=tk.BOTH, expand=True)
                    
                    # Update status
                    self.update_status(f"Reset {category} settings to defaults", 100)
                
        except Exception as e:
            self.logger.error(f"Error resetting settings: {e}")
            self.show_error(f"Error resetting settings: {e}")
    
    def _handle_settings_update(self, event_data):
        """Handle settings update events.
        
        Args:
            event_data: The event data containing settings updates
        """
        try:
            if not isinstance(event_data, dict):
                return
                
            # Update settings from event data
            for category, category_settings in event_data.items():
                if category in self.settings and isinstance(category_settings, dict):
                    # Update settings dictionary
                    self.settings[category].update(category_settings)
                    
                    # Update UI controls if they exist
                    if category in self.settings_widgets:
                        for setting_name, setting_value in category_settings.items():
                            if setting_name in self.settings_widgets[category]:
                                widget_dict = self.settings_widgets[category][setting_name]
                                if "variable" in widget_dict:
                                    widget_dict["variable"].set(setting_value)
            
            # Update status
            self.update_status("Settings updated from external source", 100)
            
        except Exception as e:
            self.logger.error(f"Error handling settings update: {e}")
    
    def _handle_settings_reset(self, event_data):
        """Handle settings reset events.
        
        Args:
            event_data: The event data
        """
        try:
            # Call reset method
            self._reset_settings()
            
        except Exception as e:
            self.logger.error(f"Error handling settings reset: {e}")
    
    def _handle_settings_save(self, event_data):
        """Handle settings save events.
        
        Args:
            event_data: The event data
        """
        try:
            # Call save method
            self._save_settings()
            
        except Exception as e:
            self.logger.error(f"Error handling settings save: {e}")
    
    async def _handle_settings_load(self, event_data):
        """Handle settings load events.
        
        Args:
            event_data: The event data
        """
        try:
            # Reload settings and update UI
            await self._load_settings()
            
            # Refresh UI with new settings
            self._create_category_frames()
            
            # Show currently selected category
            self._on_category_select(None)
            
            # Update status
            self.update_status("Settings reloaded", 100)
            
        except Exception as e:
            self.logger.error(f"Error handling settings load: {e}")
