#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Model Manager GUI Component

This module provides a GUI interface for managing the models in ThothAI.
It allows users to add, discover, and configure model capabilities at runtime.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
import json
import asyncio
import uuid
from datetime import datetime

logger = logging.getLogger('KingdomAI.GUI.ModelManager')

class ModelManagerTab:
    """GUI tab for managing models in ThothAI."""
    
    def __init__(self, parent, event_bus=None):
        """Initialize the model manager tab."""
        self.parent = parent
        self.event_bus = event_bus
        self.frame = ttk.Frame(parent)
        self.discovered_models = []
        self.brain_models = {}
        self.model_capabilities = {}
        self.model_metadata = {}
        self.last_request_id = None
        self.pull_in_progress = False
        
        # Create and layout widgets
        self._create_widgets()
        self._layout_widgets()
        
        # Subscribe to events
        self._subscribe_to_events()
        
    def _create_widgets(self):
        """Create the widgets for the tab."""
        # Top frame for model discovery
        self.discovery_frame = ttk.LabelFrame(self.frame, text="Model Discovery")
        self.discover_button = ttk.Button(self.discovery_frame, text="Discover Models", 
                                        command=self._handle_discover_models_click)
        
        # Models list frame
        self.models_frame = ttk.LabelFrame(self.frame, text="Available Models")
        self.models_tree = ttk.Treeview(self.models_frame, columns=("Model", "Type", "Status"), 
                                        show="headings", selectmode="browse")
        self.models_tree.heading("Model", text="Model")
        self.models_tree.heading("Type", text="Type")
        self.models_tree.heading("Status", text="Status")
        self.models_tree.column("Model", width=200)
        self.models_tree.column("Type", width=100)
        self.models_tree.column("Status", width=100)
        
        self.models_scrollbar = ttk.Scrollbar(self.models_frame, orient="vertical", 
                                             command=self.models_tree.yview)
        self.models_tree.configure(yscrollcommand=self.models_scrollbar.set)
        
        # Add model frame
        self.add_model_frame = ttk.LabelFrame(self.frame, text="Add New Model")
        
        self.add_model_label = ttk.Label(self.add_model_frame, text="Model Name:")
        self.add_model_entry = ttk.Entry(self.add_model_frame, width=30)
        
        self.provider_label = ttk.Label(self.add_model_frame, text="Provider:")
        self.provider_combo = ttk.Combobox(self.add_model_frame, values=["ollama"], state="readonly")
        self.provider_combo.set("ollama")
        
        self.add_model_button = ttk.Button(self.add_model_frame, text="Add/Pull Model", 
                                         command=self._handle_add_model_click)
        
        # Model capabilities frame
        self.capabilities_frame = ttk.LabelFrame(self.frame, text="Model Capabilities")
        
        self.capabilities_chat_var = tk.BooleanVar(value=True)
        self.capabilities_code_var = tk.BooleanVar(value=False)
        self.capabilities_reasoning_var = tk.BooleanVar(value=False)
        self.capabilities_research_var = tk.BooleanVar(value=False)
        self.capabilities_assistant_var = tk.BooleanVar(value=True)
        
        self.capabilities_chat_check = ttk.Checkbutton(self.capabilities_frame, text="Chat", 
                                                     variable=self.capabilities_chat_var)
        self.capabilities_code_check = ttk.Checkbutton(self.capabilities_frame, text="Code", 
                                                     variable=self.capabilities_code_var)
        self.capabilities_reasoning_check = ttk.Checkbutton(self.capabilities_frame, text="Reasoning", 
                                                          variable=self.capabilities_reasoning_var)
        self.capabilities_research_check = ttk.Checkbutton(self.capabilities_frame, text="Research", 
                                                         variable=self.capabilities_research_var)
        self.capabilities_assistant_check = ttk.Checkbutton(self.capabilities_frame, text="Assistant", 
                                                          variable=self.capabilities_assistant_var)
        
        # Priority setting frame (for each capability)
        self.priority_frame = ttk.LabelFrame(self.frame, text="Priority Settings")
        
        self.priority_labels = {
            "chat": ttk.Label(self.priority_frame, text="Chat Priority:"),
            "code": ttk.Label(self.priority_frame, text="Code Priority:"),
            "reasoning": ttk.Label(self.priority_frame, text="Reasoning Priority:"),
            "research": ttk.Label(self.priority_frame, text="Research Priority:"),
            "assistant": ttk.Label(self.priority_frame, text="Assistant Priority:")
        }
        
        self.priority_values = {
            "chat": ttk.Spinbox(self.priority_frame, from_=1, to=5, width=5),
            "code": ttk.Spinbox(self.priority_frame, from_=1, to=5, width=5),
            "reasoning": ttk.Spinbox(self.priority_frame, from_=1, to=5, width=5),
            "research": ttk.Spinbox(self.priority_frame, from_=1, to=5, width=5),
            "assistant": ttk.Spinbox(self.priority_frame, from_=1, to=5, width=5)
        }
        
        # Set default values
        for spin in self.priority_values.values():
            spin.set(3)  # Default priority
        
        # Update capabilities button
        self.update_capabilities_button = ttk.Button(self.capabilities_frame, 
                                                   text="Update Capabilities", 
                                                   command=self._handle_update_capabilities_click,
                                                   state="disabled")
        
        # Status and log frame
        self.status_frame = ttk.LabelFrame(self.frame, text="Status")
        self.status_label = ttk.Label(self.status_frame, text="Ready")
        self.log_text = scrolledtext.ScrolledText(self.status_frame, height=5, width=50)
        self.log_text.config(state="disabled")
        
        # Brain Models frame to show current assignments
        self.brain_frame = ttk.LabelFrame(self.frame, text="Current Brain Models")
        self.brain_text = scrolledtext.ScrolledText(self.brain_frame, height=6, width=50)
        self.brain_text.config(state="disabled")
        
    def _layout_widgets(self):
        """Layout the widgets in the tab."""
        # Discovery frame
        self.discovery_frame.pack(fill="x", padx=5, pady=5)
        self.discover_button.pack(padx=5, pady=5)
        
        # Models list frame
        self.models_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.models_tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.models_scrollbar.pack(side="right", fill="y")
        
        # Model selectors and add model frame
        self.add_model_frame.pack(fill="x", padx=5, pady=5)
        
        self.add_model_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.add_model_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.provider_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.provider_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        self.add_model_button.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Capabilities frame
        self.capabilities_frame.pack(fill="x", padx=5, pady=5)
        
        self.capabilities_chat_check.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.capabilities_code_check.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.capabilities_reasoning_check.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.capabilities_research_check.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.capabilities_assistant_check.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        
        self.update_capabilities_button.grid(row=2, column=1, padx=5, pady=5, sticky="e")
        
        # Priority frame
        self.priority_frame.pack(fill="x", padx=5, pady=5)
        
        row = 0
        for capability, label in self.priority_labels.items():
            label.grid(row=row, column=0, padx=5, pady=2, sticky="w")
            self.priority_values[capability].grid(row=row, column=1, padx=5, pady=2, sticky="w")
            row += 1
        
        # Brain Models frame
        self.brain_frame.pack(fill="x", padx=5, pady=5)
        self.brain_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Status frame
        self.status_frame.pack(fill="x", padx=5, pady=5)
        self.status_label.pack(padx=5, pady=2, anchor="w")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Configure the models tree for selection
        self.models_tree.bind("<<TreeviewSelect>>", self._on_model_select)
        
    def _subscribe_to_events(self):
        """Subscribe to relevant events from the event bus."""
        if self.event_bus:
            asyncio.create_task(self.event_bus.subscribe("ai.model.auto.discover.response", 
                                                        self._handle_discover_response))
            asyncio.create_task(self.event_bus.subscribe("ai.model.auto.discover.progress", 
                                                        self._handle_discover_progress))
            asyncio.create_task(self.event_bus.subscribe("ai.model.add.response", 
                                                        self._handle_add_response))
            asyncio.create_task(self.event_bus.subscribe("ai.model.add.progress", 
                                                        self._handle_add_progress))
            asyncio.create_task(self.event_bus.subscribe("ai.model.update.capabilities.response", 
                                                        self._handle_update_capabilities_response))
            asyncio.create_task(self.event_bus.subscribe("gui.update", 
                                                        self._handle_gui_update))
            
    def _handle_discover_models_click(self):
        """Handle the discover models button click."""
        if self.event_bus:
            # Disable the button while discovery is in progress
            self.discover_button.config(state="disabled")
            self.status_label.config(text="Discovering models...")
            self._add_log("Discovering models...")
            
            # Generate a unique request ID
            self.last_request_id = str(uuid.uuid4())
            
            # Publish the discover event
            asyncio.create_task(self.event_bus.publish("ai.model.auto.discover", {
                "request_id": self.last_request_id,
                "timestamp": datetime.now().isoformat()
            }))
            
    async def _handle_discover_response(self, data):
        """Handle the discover models response."""
        status = data.get("status")
        request_id = data.get("request_id")
        
        # Only process if it's our request
        if request_id != self.last_request_id:
            return
            
        # Re-enable the discover button
        self.discover_button.config(state="normal")
        
        if status == "success":
            # Update the discovered models
            self.discovered_models = data.get("discovered_models", [])
            self.brain_models = data.get("brain_models", {})
            new_models = data.get("new_models", [])
            
            # Update the status
            self.status_label.config(text=f"Discovered {len(self.discovered_models)} models")
            self._add_log(f"Discovered {len(self.discovered_models)} models, {len(new_models)} new")
            
            # Update the models tree
            self._update_models_tree()
            
            # Update the brain models display
            self._update_brain_models_display()
        else:
            # Show error
            error_msg = data.get("message", "Unknown error")
            self.status_label.config(text=f"Error: {error_msg}")
            self._add_log(f"Error discovering models: {error_msg}")
            messagebox.showerror("Error", f"Failed to discover models: {error_msg}")
            
    async def _handle_discover_progress(self, data):
        """Handle the discover models progress updates."""
        status = data.get("status")
        message = data.get("message")
        request_id = data.get("request_id")
        
        # Only process if it's our request
        if request_id != self.last_request_id:
            return
            
        # Update the status
        self.status_label.config(text=message)
        self._add_log(message)
            
    def _handle_add_model_click(self):
        """Handle the add model button click."""
        model_name = self.add_model_entry.get().strip()
        provider = self.provider_combo.get()
        
        if not model_name:
            messagebox.showerror("Error", "Please enter a model name")
            return
            
        if self.event_bus:
            # Disable the button while adding is in progress
            self.add_model_button.config(state="disabled")
            self.status_label.config(text=f"Adding model {model_name}...")
            self._add_log(f"Adding model {model_name} from {provider}...")
            
            # Set pull in progress flag
            self.pull_in_progress = True
            
            # Generate a unique request ID
            self.last_request_id = str(uuid.uuid4())
            
            # Get capabilities from checkboxes
            capabilities = []
            priorities = {}
            
            if self.capabilities_chat_var.get():
                capabilities.append("chat")
                priorities["chat"] = int(self.priority_values["chat"].get())
                
            if self.capabilities_code_var.get():
                capabilities.append("code")
                priorities["code"] = int(self.priority_values["code"].get())
                
            if self.capabilities_reasoning_var.get():
                capabilities.append("reasoning")
                priorities["reasoning"] = int(self.priority_values["reasoning"].get())
                
            if self.capabilities_research_var.get():
                capabilities.append("research")
                priorities["research"] = int(self.priority_values["research"].get())
                
            if self.capabilities_assistant_var.get():
                capabilities.append("assistant")
                priorities["assistant"] = int(self.priority_values["assistant"].get())
            
            # Publish the add model event
            asyncio.create_task(self.event_bus.publish("ai.model.add", {
                "model": model_name,
                "provider": provider,
                "capabilities": capabilities,
                "priorities": priorities,
                "request_id": self.last_request_id,
                "timestamp": datetime.now().isoformat()
            }))
            
    async def _handle_add_response(self, data):
        """Handle the add model response."""
        status = data.get("status")
        request_id = data.get("request_id")
        
        # Only process if it's our request
        if request_id != self.last_request_id:
            return
            
        # Reset pull in progress flag
        self.pull_in_progress = False
        
        # Re-enable the add button
        self.add_model_button.config(state="normal")
        
        if status == "success":
            # Get model details
            model = data.get("model")
            capabilities = data.get("capabilities", [])
            self.brain_models = data.get("brain_models", {})
            
            # Update the status
            self.status_label.config(text=f"Added model {model}")
            self._add_log(f"Successfully added model {model} with capabilities: {', '.join(capabilities)}")
            
            # Clear the entry
            self.add_model_entry.delete(0, tk.END)
            
            # Update the models tree and refresh the discovered models
            self._handle_discover_models_click()
            
            # Update the brain models display
            self._update_brain_models_display()
        else:
            # Show error
            error_msg = data.get("message", "Unknown error")
            self.status_label.config(text=f"Error: {error_msg}")
            self._add_log(f"Error adding model: {error_msg}")
            messagebox.showerror("Error", f"Failed to add model: {error_msg}")
            
    async def _handle_add_progress(self, data):
        """Handle the add model progress updates."""
        status = data.get("status")
        message = data.get("message")
        request_id = data.get("request_id")
        
        # Only process if it's our request
        if request_id != self.last_request_id:
            return
            
        # Update the status
        self.status_label.config(text=message)
        self._add_log(message)
            
    def _on_model_select(self, event):
        """Handle model selection in the treeview."""
        selection = self.models_tree.selection()
        if selection:
            item = self.models_tree.item(selection[0])
            model = item['values'][0]
            
            # Get the model capabilities if available
            if model in self.model_metadata:
                capabilities = self.model_metadata[model].get("capabilities", [])
                priorities = self.model_metadata[model].get("priority", {})
                
                # Update checkboxes
                self.capabilities_chat_var.set("chat" in capabilities)
                self.capabilities_code_var.set("code" in capabilities)
                self.capabilities_reasoning_var.set("reasoning" in capabilities)
                self.capabilities_research_var.set("research" in capabilities)
                self.capabilities_assistant_var.set("assistant" in capabilities)
                
                # Update priorities
                for capability, spin in self.priority_values.items():
                    spin.set(priorities.get(capability, 3))
                
                # Enable the update button
                self.update_capabilities_button.config(state="normal")
            else:
                # Reset checkboxes
                self.capabilities_chat_var.set(True)
                self.capabilities_code_var.set(False)
                self.capabilities_reasoning_var.set(False)
                self.capabilities_research_var.set(False)
                self.capabilities_assistant_var.set(True)
                
                # Reset priorities
                for spin in self.priority_values.values():
                    spin.set(3)
                
                # Disable the update button
                self.update_capabilities_button.config(state="disabled")
        else:
            # Disable the update button
            self.update_capabilities_button.config(state="disabled")
            
    def _handle_update_capabilities_click(self):
        """Handle the update capabilities button click."""
        selection = self.models_tree.selection()
        if not selection:
            return
            
        item = self.models_tree.item(selection[0])
        model = item['values'][0]
        
        # Get capabilities from checkboxes
        capabilities = []
        priorities = {}
        
        if self.capabilities_chat_var.get():
            capabilities.append("chat")
            priorities["chat"] = int(self.priority_values["chat"].get())
            
        if self.capabilities_code_var.get():
            capabilities.append("code")
            priorities["code"] = int(self.priority_values["code"].get())
            
        if self.capabilities_reasoning_var.get():
            capabilities.append("reasoning")
            priorities["reasoning"] = int(self.priority_values["reasoning"].get())
            
        if self.capabilities_research_var.get():
            capabilities.append("research")
            priorities["research"] = int(self.priority_values["research"].get())
            
        if self.capabilities_assistant_var.get():
            capabilities.append("assistant")
            priorities["assistant"] = int(self.priority_values["assistant"].get())
        
        if not capabilities:
            messagebox.showerror("Error", "Please select at least one capability")
            return
            
        if self.event_bus:
            # Disable the button while updating
            self.update_capabilities_button.config(state="disabled")
            self.status_label.config(text=f"Updating capabilities for {model}...")
            self._add_log(f"Updating capabilities for {model}: {', '.join(capabilities)}")
            
            # Generate a unique request ID
            self.last_request_id = str(uuid.uuid4())
            
            # Publish the update capabilities event
            asyncio.create_task(self.event_bus.publish("ai.model.update.capabilities", {
                "model": model,
                "capabilities": capabilities,
                "priorities": priorities,
                "request_id": self.last_request_id,
                "timestamp": datetime.now().isoformat()
            }))
            
    async def _handle_update_capabilities_response(self, data):
        """Handle the update capabilities response."""
        status = data.get("status")
        request_id = data.get("request_id")
        
        # Only process if it's our request
        if request_id != self.last_request_id:
            return
            
        # Re-enable the update button
        self.update_capabilities_button.config(state="normal")
        
        if status == "success":
            # Get model details
            model = data.get("model")
            capabilities = data.get("capabilities", [])
            self.brain_models = data.get("brain_models", {})
            
            # Update the status
            self.status_label.config(text=f"Updated capabilities for {model}")
            self._add_log(f"Successfully updated capabilities for {model}: {', '.join(capabilities)}")
            
            # Update the brain models display
            self._update_brain_models_display()
        else:
            # Show error
            error_msg = data.get("message", "Unknown error")
            self.status_label.config(text=f"Error: {error_msg}")
            self._add_log(f"Error updating capabilities: {error_msg}")
            messagebox.showerror("Error", f"Failed to update capabilities: {error_msg}")
            
    async def _handle_gui_update(self, data):
        """Handle GUI update events."""
        component = data.get("component")
        
        if component == "thoth":
            # Update brain models if available
            brain_models = data.get("brain_models")
            if brain_models:
                self.brain_models = brain_models
                self._update_brain_models_display()
                
            # Update model capabilities if available
            model_capabilities = data.get("model_capabilities")
            if model_capabilities:
                self.model_capabilities = model_capabilities
                
            # Update available models if available
            available_models = data.get("available_models")
            if available_models:
                self.discovered_models = available_models.get("ollama", [])
                self._update_models_tree()
                
    def _update_models_tree(self):
        """Update the models tree with the current discovered models."""
        # Clear the tree
        for item in self.models_tree.get_children():
            self.models_tree.delete(item)
            
        # Add discovered models
        for model in self.discovered_models:
            # Determine type and status
            model_type = "Unknown"
            if model in self.model_metadata:
                capabilities = self.model_metadata[model].get("capabilities", [])
                if "code" in capabilities:
                    model_type = "Code"
                elif "research" in capabilities:
                    model_type = "Research"
                elif "reasoning" in capabilities:
                    model_type = "Reasoning"
                elif "chat" in capabilities:
                    model_type = "Chat"
                elif "assistant" in capabilities:
                    model_type = "Assistant"
                    
            # Determine status
            status = "Available"
            for capability, assigned_model in self.brain_models.items():
                if model == assigned_model:
                    status = f"Active ({capability})"
                    break
                    
            self.models_tree.insert("", "end", values=(model, model_type, status))
            
    def _update_brain_models_display(self):
        """Update the brain models display."""
        # Clear the text
        self.brain_text.config(state="normal")
        self.brain_text.delete(1.0, tk.END)
        
        # Add brain models
        self.brain_text.insert(tk.END, "Current Brain Model Assignments:\n")
        for capability, model in self.brain_models.items():
            self.brain_text.insert(tk.END, f"{capability.capitalize()}: {model}\n")
            
        self.brain_text.config(state="disabled")
        
    def _add_log(self, message):
        """Add a message to the log."""
        # Get current time
        now = datetime.now().strftime("%H:%M:%S")
        
        # Add message to log
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{now}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
