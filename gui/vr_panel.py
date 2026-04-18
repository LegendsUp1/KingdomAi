#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - VR Panel
Provides GUI interface for the VR component of Kingdom AI.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import asyncio
import threading
import json
from typing import Dict, Any, Optional, List, Callable
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

logger = logging.getLogger("KingdomAI.VRPanel")

class VRPanel(ttk.Frame):
    """VR interface panel for Kingdom AI."""
    
    def __init__(self, parent, event_bus=None):
        """Initialize the VR panel."""
        super().__init__(parent)
        self.parent = parent
        self.event_bus = event_bus
        
        # VR system state
        self.hardware_connected = False
        self.simulation_mode = False
        self.active_components = {}
        self.environment = "default"
        
        # GUI elements
        self.hardware_status_var = tk.StringVar(value="Checking...")
        self.simulation_status_var = tk.StringVar(value="Disabled")
        self.component_count_var = tk.IntVar(value=0)
        self.environment_var = tk.StringVar(value="Default")
        
        # Create GUI components
        self._create_widgets()
        
        # Set up event listeners
        self._setup_event_listeners()

    def _create_widgets(self):
        """Create the GUI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self, padding="10", style="VR.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="VR System Status")
        status_frame.pack(fill=tk.X, pady=5)
        
        # Hardware status
        ttk.Label(status_frame, text="Hardware:", style="VR.TLabel").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        hardware_status_label = ttk.Label(status_frame, textvariable=self.hardware_status_var, style="VR.TLabel")
        hardware_status_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Simulation status
        ttk.Label(status_frame, text="Simulation:", style="VR.TLabel").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        simulation_status_label = ttk.Label(status_frame, textvariable=self.simulation_status_var, style="VR.TLabel")
        simulation_status_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Environment
        ttk.Label(status_frame, text="Environment:", style="VR.TLabel").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        environment_label = ttk.Label(status_frame, textvariable=self.environment_var, style="VR.TLabel")
        environment_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Active components
        ttk.Label(status_frame, text="Active Components:", style="VR.TLabel").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        component_count_label = ttk.Label(status_frame, textvariable=self.component_count_var, style="VR.TLabel")
        component_count_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Control section
        control_frame = ttk.LabelFrame(main_frame, text="VR Controls")
        control_frame.pack(fill=tk.X, pady=5)
        
        # Environment selection
        ttk.Label(control_frame, text="Select Environment:", style="VR.TLabel").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        environment_combo = ttk.Combobox(control_frame, values=["Default", "Trading Floor", "Cosmic", "Ocean"])
        environment_combo.current(0)
        environment_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        environment_combo.bind("<<ComboboxSelected>>", self._on_environment_changed)
        
        # Toggle simulation button
        self.toggle_simulation_btn = ttk.Button(
            control_frame, 
            text="Enable Simulation",
            command=self._toggle_simulation
        )
        self.toggle_simulation_btn.grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Reset view button
        reset_view_btn = ttk.Button(
            control_frame, 
            text="Reset View",
            command=self._reset_view
        )
        reset_view_btn.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Visualization section
        viz_frame = ttk.LabelFrame(main_frame, text="VR Visualization")
        viz_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create a figure for the visualization
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax.set_xlabel('X axis')
        self.ax.set_ylabel('Y axis')
        self.ax.set_zlabel('Z axis')
        self.ax.set_title('VR Environment Visualization')
        
        # Create a canvas for the figure
        self.canvas = FigureCanvasTkAgg(self.figure, viz_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Component list
        component_frame = ttk.LabelFrame(main_frame, text="Active Components")
        component_frame.pack(fill=tk.X, pady=5)
        
        self.component_tree = ttk.Treeview(
            component_frame, 
            columns=("Type", "Position"),
            show="headings",
            height=5
        )
        self.component_tree.heading("Type", text="Type")
        self.component_tree.heading("Position", text="Position")
        self.component_tree.column("Type", width=100)
        self.component_tree.column("Position", width=200)
        self.component_tree.pack(fill=tk.X, expand=True)
        
        # Add context menu to component list
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Toggle Visibility", command=self._toggle_component_visibility)
        self.context_menu.add_command(label="Highlight", command=self._highlight_component)
        self.context_menu.add_command(label="Delete", command=self._delete_component)
        
        self.component_tree.bind("<Button-3>", self._show_context_menu)
        
    def _setup_event_listeners(self):
        """Set up event listeners for the VR system."""
        if self.event_bus:
            # Run these in the next event loop iteration to ensure they're registered after component initialization
            self.after(100, self._register_event_listeners)
    
    def _register_event_listeners(self):
        """Register event listeners with the event bus using synchronous methods."""
        # First make sure we actually have an event bus
        if self.event_bus is None:
            logging.error("Cannot register event listeners: event_bus is None")
            return
            
        # Use synchronous subscribe_sync method to prevent coroutine warnings
        subscribe_sync_method = getattr(self.event_bus, 'subscribe_sync', None)
        if subscribe_sync_method and callable(subscribe_sync_method):
            # Use synchronous methods directly
            try:
                subscribe_sync_method("vr.status_update", self._handle_status_update)
                subscribe_sync_method("vr.component_update", self._handle_component_update)
                subscribe_sync_method("vr.environment_changed", self._handle_environment_change)
                logging.info("VR panel registered event listeners using subscribe_sync")
                
                # Request initial status update with sync method
                publish_sync_method = getattr(self.event_bus, 'publish_sync', None)
                if publish_sync_method and callable(publish_sync_method):
                    publish_sync_method("vr.request_status", {})
                else:
                    # Fallback if publish_sync doesn't exist
                    logging.warning("publish_sync not available in event_bus, cannot request VR status")
            except Exception as e:
                logging.error(f"Error registering event listeners with subscribe_sync: {e}")
        else:
            # Fallback to async methods with proper handling if sync methods aren't available
            logging.warning("subscribe_sync not available in event_bus, falling back to async methods")
            
            # Helper to properly handle async event bus methods
            def safe_async_call(coro):
                if coro and asyncio.iscoroutine(coro):
                    try:
                        asyncio.run_coroutine_threadsafe(coro, asyncio.get_event_loop())
                    except Exception as e:
                        logging.error(f"Error in async event bus call: {e}")
                        
            # Subscribe to events using async method with proper handling
            subscribe_method = getattr(self.event_bus, 'subscribe', None)
            if subscribe_method and callable(subscribe_method):
                try:
                    safe_async_call(subscribe_method("vr.status_update", self._handle_status_update))
                    safe_async_call(subscribe_method("vr.component_update", self._handle_component_update))
                    safe_async_call(subscribe_method("vr.environment_changed", self._handle_environment_change))
                    logging.info("VR panel registered event listeners using async subscribe")
                    
                    # Request initial status update
                    publish_method = getattr(self.event_bus, 'publish', None)
                    if publish_method and callable(publish_method):
                        safe_async_call(publish_method("vr.request_status", {}))
                except Exception as e:
                    logging.error(f"Error registering event listeners with async subscribe: {e}")
            else:
                logging.error("No event subscription methods available on event_bus")

        
    def _handle_status_update(self, event_data: Dict[str, Any]):
        """Handle VR status update events."""
        # Update in the GUI thread to avoid threading issues
        self.after(0, lambda: self._update_status_display(event_data))
        
    def _update_status_display(self, event_data: Dict[str, Any]):
        """Update the status display with new VR system status."""
        self.hardware_connected = event_data.get("hardware_connected", False)
        self.simulation_mode = event_data.get("simulation_mode", False)
        
        # Update status labels
        if self.hardware_connected:
            self.hardware_status_var.set("Connected")
        else:
            self.hardware_status_var.set("Disconnected")
            
        if self.simulation_mode:
            self.simulation_status_var.set("Enabled")
            self.toggle_simulation_btn.config(text="Disable Simulation")
        else:
            self.simulation_status_var.set("Disabled")
            self.toggle_simulation_btn.config(text="Enable Simulation")
            
        self.environment_var.set(event_data.get("environment", "Default").capitalize())
        
        # Update the component count
        component_count = len(event_data.get("active_components", {}))
        self.component_count_var.set(component_count)
        
        # Update the 3D visualization
        self._update_visualization(event_data.get("active_components", {}))
        
    def _handle_component_update(self, event_data: Dict[str, Any]):
        """Handle component update events."""
        # Update in the GUI thread
        self.after(0, lambda: self._update_component_display(event_data))
        
    def _update_component_display(self, event_data: Dict[str, Any]):
        """Update the component display with new component data."""
        component_id = event_data.get("component_id", "")
        component_type = event_data.get("component_type", "Unknown")
        position = event_data.get("position", {})
        pos_str = f"X: {position.get('x', 0):.1f}, Y: {position.get('y', 0):.1f}, Z: {position.get('z', 0):.1f}"
        
        # Update the component tree
        # Check if the item already exists
        for item_id in self.component_tree.get_children():
            if self.component_tree.item(item_id, "text") == component_id:
                self.component_tree.item(item_id, values=(component_type, pos_str))
                break
        else:
            # Item doesn't exist, add it
            self.component_tree.insert("", "end", text=component_id, values=(component_type, pos_str))
            
        # Update active components dictionary
        self.active_components[component_id] = event_data
        
        # Update count
        self.component_count_var.set(len(self.active_components))
        
        # Update visualization
        self._update_visualization(self.active_components)
        
    def _handle_environment_change(self, event_data: Dict[str, Any]):
        """Handle environment change events."""
        # Update in the GUI thread
        self.after(0, lambda: self._update_environment_display(event_data))
        
    def _update_environment_display(self, event_data: Dict[str, Any]):
        """Update the environment display with new environment data."""
        environment = event_data.get("environment", "default")
        self.environment_var.set(environment.capitalize())
        self.environment = environment
        
    def _update_visualization(self, components: Dict[str, Any]):
        """Update the 3D visualization with component positions."""
        # Clear the current plot
        self.ax.clear()
        
        # Set up the axes
        self.ax.set_xlabel('X axis')
        self.ax.set_ylabel('Y axis')
        self.ax.set_zlabel('Z axis')
        self.ax.set_title(f'VR Environment: {self.environment.capitalize()}')
        
        # Set fixed limits for consistent view
        self.ax.set_xlim(-5, 5)
        self.ax.set_ylim(-5, 5)
        self.ax.set_zlim(-5, 5)
        
        # Plot each component
        for component_id, component in components.items():
            position = component.get("position", {})
            x = position.get("x", 0)
            y = position.get("y", 0)
            z = position.get("z", 0)
            
            component_type = component.get("component_type", "")
            
            # Different marker styles and colors for different component types
            marker = 'o'  # default
            color = 'blue'  # default
            
            if "chart" in component_type.lower():
                marker = 's'
                color = 'red'
            elif "trading" in component_type.lower():
                marker = '^'
                color = 'green'
            elif "wallet" in component_type.lower():
                marker = 'D'
                color = 'purple'
            
            self.ax.scatter(x, y, z, marker=marker, color=color, s=50, label=component_id)
            self.ax.text(x, y, z, component_id, fontsize=8)
            
        # Redraw the canvas
        self.canvas.draw()
        
    def _on_environment_changed(self, event):
        """Handle environment combobox selection."""
        selected_env = event.widget.get().lower()
        if self.event_bus:
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("vr.change_environment", {"environment": selected_env}),
                asyncio.get_event_loop()
            )
        
    def _toggle_simulation(self):
        """Toggle VR simulation mode."""
        if self.event_bus:
            # Toggle the current state
            new_state = not self.simulation_mode
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("vr.toggle_simulation", {"enabled": new_state}),
                asyncio.get_event_loop()
            )
        
    def _reset_view(self):
        """Reset the VR view to default position."""
        if self.event_bus:
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("vr.reset_view", {}),
                asyncio.get_event_loop()
            )
            
    def _show_context_menu(self, event):
        """Show context menu for component tree."""
        # Identify the component under cursor
        item_id = self.component_tree.identify_row(event.y)
        if item_id:
            self.component_tree.selection_set(item_id)
            self.context_menu.post(event.x_root, event.y_root)
            
    def _toggle_component_visibility(self):
        """Toggle visibility of selected component."""
        selected_items = self.component_tree.selection()
        if selected_items and self.event_bus:
            component_id = self.component_tree.item(selected_items[0], "text")
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("vr.toggle_component", {"component_id": component_id}),
                asyncio.get_event_loop()
            )
            
    def _highlight_component(self):
        """Highlight selected component."""
        selected_items = self.component_tree.selection()
        if selected_items and self.event_bus:
            component_id = self.component_tree.item(selected_items[0], "text")
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("vr.highlight_object", {
                    "object_id": component_id,
                    "highlight": True,
                    "intensity": 1.0
                }),
                asyncio.get_event_loop()
            )
            
    def _delete_component(self):
        """Delete selected component."""
        selected_items = self.component_tree.selection()
        if selected_items and self.event_bus:
            component_id = self.component_tree.item(selected_items[0], "text")
            if messagebox.askyesno("Confirm Delete", f"Delete component '{component_id}'?"):
                asyncio.run_coroutine_threadsafe(
                    self.event_bus.publish("vr.delete_component", {"component_id": component_id}),
                    asyncio.get_event_loop()
                )
                # Remove from tree
                self.component_tree.delete(selected_items[0])
                # Remove from active components
                if component_id in self.active_components:
                    del self.active_components[component_id]
                # Update count
                self.component_count_var.set(len(self.active_components))
