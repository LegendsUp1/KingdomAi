"""
SOTA 2026: Fallback implementations for GUI components.

Provides full functionality fallbacks when primary implementations unavailable.
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional, Callable


class FallbackStatusBar:
    """Fallback status bar with message queue and timed updates."""
    
    def __init__(self, parent):
        self.logger = logging.getLogger("FallbackStatusBar")
        self.logger.warning("Using fallback StatusBar")
        self.parent = parent
        self.label = ttk.Label(parent, text="Status: Ready")
        self.label.pack(side=tk.BOTTOM, fill=tk.X)
        self._message_queue = []
        self._current_message = "Status: Ready"
        self._timeout_id = None
    
    def config(self, **kwargs):
        """Configure status bar."""
        text = kwargs.get("text", self._current_message)
        self._current_message = text
        self.label.config(text=text)
    
    def update(self):
        """Process update cycle."""
        if self._message_queue:
            msg, duration = self._message_queue.pop(0)
            self.show_message(msg, duration)
        if hasattr(self.label, 'update'):
            self.label.update()
    
    def show_message(self, message: str, duration_ms: int = 3000):
        """Show a message for a specified duration."""
        self._current_message = message
        self.label.config(text=message)
        
        # Clear previous timeout
        if self._timeout_id:
            try:
                self.parent.after_cancel(self._timeout_id)
            except Exception:
                pass
        
        # Set timeout to clear message
        if duration_ms > 0:
            self._timeout_id = self.parent.after(duration_ms, self._clear_message)
    
    def _clear_message(self):
        """Clear temporary message."""
        self.label.config(text="Status: Ready")
    
    def queue_message(self, message: str, duration_ms: int = 3000):
        """Queue a message to be shown."""
        self._message_queue.append((message, duration_ms))


class FallbackToolTip:
    """Fallback tooltip with proper show/hide functionality."""
    
    def __init__(self, widget, text: str):
        self.logger = logging.getLogger("FallbackToolTip")
        self.logger.warning("Using fallback ToolTip")
        self.widget = widget
        self.text = text
        self.tip_window = None
        self._bind_events()
    
    def _bind_events(self):
        """Bind mouse events for tooltip."""
        if self.widget:
            self.widget.bind("<Enter>", lambda e: self.showtip())
            self.widget.bind("<Leave>", lambda e: self.hidetip())
    
    def showtip(self):
        """Show the tooltip."""
        if self.tip_window or not self.text:
            return
        
        try:
            x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
            x += self.widget.winfo_rootx() + 25
            y += self.widget.winfo_rooty() + 25
            
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            
            label = ttk.Label(tw, text=self.text, justify=tk.LEFT,
                             background="#ffffe0", relief=tk.SOLID, borderwidth=1)
            label.pack(ipadx=5, ipady=2)
        except Exception as e:
            self.logger.debug(f"Tooltip show error: {e}")
    
    def hidetip(self):
        """Hide the tooltip."""
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None
    
    def set_text(self, text: str):
        """Update tooltip text."""
        self.text = text


class FallbackThemeManager:
    """Fallback theme manager with theme switching support."""
    
    THEMES = {
        "dark": {
            "bg": "#1a1a2e",
            "fg": "#eaeaea",
            "accent": "#00d4ff",
            "button_bg": "#16213e",
            "button_fg": "#00d4ff"
        },
        "light": {
            "bg": "#f5f5f5",
            "fg": "#333333",
            "accent": "#2196f3",
            "button_bg": "#ffffff",
            "button_fg": "#2196f3"
        },
        "cyberpunk": {
            "bg": "#0a0a14",
            "fg": "#00ffff",
            "accent": "#ff00ff",
            "button_bg": "#1a1a2e",
            "button_fg": "#00ffff"
        }
    }
    
    def __init__(self):
        self.logger = logging.getLogger("FallbackThemeManager")
        self.logger.warning("Using fallback ThemeManager")
        self._current_theme = "dark"
        self._widgets = []
    
    def apply_theme(self, theme_name: str):
        """Apply a theme to all registered widgets."""
        if theme_name not in self.THEMES:
            self.logger.warning(f"Theme '{theme_name}' not found, using dark")
            theme_name = "dark"
        
        self._current_theme = theme_name
        theme = self.THEMES[theme_name]
        
        for widget in self._widgets:
            try:
                if hasattr(widget, 'configure'):
                    widget.configure(bg=theme["bg"], fg=theme["fg"])
            except Exception as e:
                self.logger.debug(f"Failed to apply theme to widget: {e}")
        
        self.logger.info(f"Applied theme: {theme_name}")
    
    def register_widget(self, widget):
        """Register a widget for theme updates."""
        if widget not in self._widgets:
            self._widgets.append(widget)
    
    def get_current_theme(self) -> str:
        """Get current theme name."""
        return self._current_theme
    
    def get_theme_colors(self) -> Dict[str, str]:
        """Get current theme colors."""
        return self.THEMES.get(self._current_theme, self.THEMES["dark"]).copy()


class FallbackTabManager:
    """Fallback tab manager with data routing support."""
    
    def __init__(self):
        self.logger = logging.getLogger("FallbackTabManager")
        self.logger.warning("Using fallback TabManager")
        self._tabs: Dict[str, Any] = {}
        self._data_cache: Dict[str, Any] = {}
        self._update_callbacks: Dict[str, Callable] = {}
    
    def register_tab(self, name: str, frame):
        """Register a tab with the manager."""
        self._tabs[name] = frame
        self.logger.info(f"Registered tab: {name}")
    
    def unregister_tab(self, name: str):
        """Unregister a tab."""
        if name in self._tabs:
            del self._tabs[name]
    
    def get_tab(self, name: str) -> Optional[Any]:
        """Get a registered tab by name."""
        return self._tabs.get(name)
    
    def update_data(self, data: Dict[str, Any]):
        """Update all tabs with new data."""
        self._data_cache.update(data)
        
        for name, tab in self._tabs.items():
            if hasattr(tab, 'update_data'):
                try:
                    tab.update_data(data)
                except Exception as e:
                    self.logger.error(f"Error updating tab {name}: {e}")
    
    def update_redis_data(self, data: Dict[str, Any]):
        """Update tabs with Redis data."""
        self._data_cache['redis'] = data
        
        for name, tab in self._tabs.items():
            if hasattr(tab, 'update_redis_data'):
                try:
                    tab.update_redis_data(data)
                except Exception as e:
                    self.logger.error(f"Error updating tab {name} with Redis data: {e}")
    
    def update_api_data(self, data: Dict[str, Any]):
        """Update tabs with API data."""
        self._data_cache['api'] = data
        
        for name, tab in self._tabs.items():
            if hasattr(tab, 'update_api_data'):
                try:
                    tab.update_api_data(data)
                except Exception as e:
                    self.logger.error(f"Error updating tab {name} with API data: {e}")
    
    def set_update_callback(self, name: str, callback: Callable):
        """Set update callback for a tab."""
        self._update_callbacks[name] = callback
    
    def get_cached_data(self) -> Dict[str, Any]:
        """Get all cached data."""
        return self._data_cache.copy()


class FallbackBaseFrame:
    """Fallback base frame with common functionality."""
    
    def __init__(self, parent, event_bus=None):
        self.logger = logging.getLogger("FallbackBaseFrame")
        self.logger.warning("Using fallback BaseFrame")
        self.parent = parent
        self.event_bus = event_bus
        self.frame = ttk.Frame(parent)
        self._initialized = False
    
    def pack(self, **kwargs):
        """Pack the frame."""
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """Grid the frame."""
        self.frame.grid(**kwargs)
    
    def place(self, **kwargs):
        """Place the frame."""
        self.frame.place(**kwargs)
    
    def destroy(self):
        """Destroy the frame."""
        self.frame.destroy()
    
    def update(self):
        """Update the frame."""
        if hasattr(self.frame, 'update'):
            self.frame.update()
    
    def update_data(self, data: Dict[str, Any]):
        """Update frame with data."""
        pass  # Override in subclasses


class FallbackDashboardFrame(FallbackBaseFrame):
    """Fallback dashboard frame with basic metrics display."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus)
        self.logger = logging.getLogger("FallbackDashboardFrame")
        
        # Create dashboard layout
        ttk.Label(self.frame, text="Dashboard (Fallback Mode)", 
                 font=('Helvetica', 14, 'bold')).pack(pady=10)
        
        self.metrics_frame = ttk.Frame(self.frame)
        self.metrics_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.metric_labels = {}
        metrics = ["CPU Usage", "Memory", "Network", "Disk"]
        for i, metric in enumerate(metrics):
            label = ttk.Label(self.metrics_frame, text=f"{metric}: --")
            label.grid(row=i//2, column=i%2, padx=10, pady=5)
            self.metric_labels[metric] = label
    
    def update_data(self, data: Dict[str, Any]):
        """Update dashboard metrics."""
        for metric, label in self.metric_labels.items():
            value = data.get(metric.lower().replace(" ", "_"), "--")
            label.config(text=f"{metric}: {value}")


class FallbackMiningFrame(FallbackBaseFrame):
    """Fallback mining frame with basic status display."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus)
        self.logger = logging.getLogger("FallbackMiningFrame")
        
        ttk.Label(self.frame, text="Mining (Fallback Mode)",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)
        
        self.status_label = ttk.Label(self.frame, text="Status: Stopped")
        self.status_label.pack(pady=5)
        
        self.hashrate_label = ttk.Label(self.frame, text="Hashrate: 0 H/s")
        self.hashrate_label.pack(pady=5)
    
    def update_data(self, data: Dict[str, Any]):
        """Update mining status."""
        status = data.get("mining_status", "Stopped")
        hashrate = data.get("hashrate", 0)
        self.status_label.config(text=f"Status: {status}")
        self.hashrate_label.config(text=f"Hashrate: {hashrate} H/s")


class FallbackTradingFrame(FallbackBaseFrame):
    """Fallback trading frame with basic controls."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus)
        self.logger = logging.getLogger("FallbackTradingFrame")
        
        ttk.Label(self.frame, text="Trading (Fallback Mode)",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)
        
        self.price_label = ttk.Label(self.frame, text="Price: $0.00")
        self.price_label.pack(pady=5)
        
        self.balance_label = ttk.Label(self.frame, text="Balance: $0.00")
        self.balance_label.pack(pady=5)
    
    def update_data(self, data: Dict[str, Any]):
        """Update trading info."""
        price = data.get("price", 0)
        balance = data.get("balance", 0)
        self.price_label.config(text=f"Price: ${price:,.2f}")
        self.balance_label.config(text=f"Balance: ${balance:,.2f}")


class FallbackSettingsFrame(FallbackBaseFrame):
    """Fallback settings frame."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus)
        self.logger = logging.getLogger("FallbackSettingsFrame")
        
        ttk.Label(self.frame, text="Settings (Fallback Mode)",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)
        
        ttk.Label(self.frame, text="Settings are limited in fallback mode").pack(pady=20)


class FallbackLogFrame(FallbackBaseFrame):
    """Fallback log frame with text display."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus)
        self.logger = logging.getLogger("FallbackLogFrame")
        
        ttk.Label(self.frame, text="Logs (Fallback Mode)",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)
        
        self.log_text = tk.Text(self.frame, height=20, width=80)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def add_log(self, message: str):
        """Add a log message."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
    
    def clear_logs(self):
        """Clear all logs."""
        self.log_text.delete(1.0, tk.END)


class FallbackApiKeyFrame(FallbackBaseFrame):
    """Fallback API key management frame."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus)
        self.logger = logging.getLogger("FallbackApiKeyFrame")
        
        ttk.Label(self.frame, text="API Keys (Fallback Mode)",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)
        
        ttk.Label(self.frame, text="API key management limited in fallback mode").pack(pady=20)
