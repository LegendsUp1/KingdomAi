#!/usr/bin/env python3
"""
Code Generator Application with MCP Integration

This module implements a standalone Code Generator application with full MCP (Model Context Protocol)
integration for AI-powered code generation, execution, and injection.
"""

import os
import sys
import json
import logging
import asyncio
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import core components
try:
    from core.mcp_connector import MCPConnector
    from core.event_bus import EventBus
except ImportError as e:
    print(f"Error importing core modules: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('code_generator.log')
    ]
)
logger = logging.getLogger(__name__)

class CodeGeneratorApp:
    """Main application class for the Code Generator with MCP integration."""
    
    def __init__(self, root):
        """Initialize the application.
        
        Args:
            root: The root Tkinter window
        """
        self.root = root
        self.root.title("Kingdom AI - Code Generator")
        self.root.geometry("1200x800")
        
        # Initialize event bus
        self.event_bus = EventBus()
        
        # Initialize MCP connector
        self.mcp_connector = MCPConnector(event_bus=self.event_bus)
        
        # Initialize UI
        self._setup_ui()
        
        # Connect to MCP
        self._connect_to_mcp()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def _setup_ui(self):
        """Set up the user interface."""
        # Configure styles
        self._configure_styles()
        
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        self._create_header()
        
        # Content area
        self._create_content_area()
        
        # Status bar
        self._create_status_bar()
    
    def _configure_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        
        # Configure main window background
        style.configure('TFrame', background='#2E3440')
        style.configure('TLabel', background='#2E3440', foreground='#E5E9F0')
        style.configure('TButton', font=('Segoe UI', 9))
        
        # Configure notebook style
        style.configure('TNotebook', background='#2E3440')
        style.configure('TNotebook.Tab', 
                       padding=[10, 5],
                       background='#3B4252',
                       foreground='#E5E9F0',
                       font=('Segoe UI', 9, 'bold'))
        style.map('TNotebook.Tab',
                 background=[('selected', '#4C566A')],
                 foreground=[('selected', '#88C0D0')])
    
    def _create_header(self):
        """Create the header section."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        title_label = ttk.Label(
            header_frame,
            text="Code Generator",
            font=('Segoe UI', 16, 'bold'),
            foreground='#88C0D0'
        )
        title_label.pack(side=tk.LEFT)
        
        # Model selection
        model_frame = ttk.Frame(header_frame)
        model_frame.pack(side=tk.RIGHT, padx=10)
        
        ttk.Label(model_frame, text="Model:").pack(side=tk.LEFT, padx=5)
        
        self.model_var = tk.StringVar(value="deepseek-coder-v2")
        self.model_dropdown = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=["deepseek-coder-v2", "llama2", "codegemma-2", "gpt-4"],
            state='readonly',
            width=20
        )
        self.model_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Connect button
        self.connect_button = ttk.Button(
            model_frame,
            text="Connect",
            command=self._connect_to_mcp
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)
    
    def _create_content_area(self):
        """Create the main content area."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Code Generation Tab
        self._create_code_generation_tab()
        
        # Settings Tab
        self._create_settings_tab()
    
    def _create_code_generation_tab(self):
        """Create the code generation tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Code Generation")
        
        # Input area
        input_frame = ttk.LabelFrame(tab, text="Input Prompt")
        input_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5, ipadx=5, ipady=5)
        
        self.input_text = scrolledtext.ScrolledText(
            input_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            bg='#3B4252',
            fg='#E5E9F0',
            insertbackground='white',
            padx=10,
            pady=10
        )
        self.input_text.pack(fill=tk.BOTH, expand=True)
        
        # Button frame
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Buttons
        self.generate_button = ttk.Button(
            button_frame,
            text="Generate Code",
            command=self._on_generate_code,
            style='Accent.TButton'
        )
        self.generate_button.pack(side=tk.LEFT, padx=5)
        
        self.execute_button = ttk.Button(
            button_frame,
            text="Execute",
            command=self._on_execute_code,
            state=tk.DISABLED
        )
        self.execute_button.pack(side=tk.LEFT, padx=5)
        
        self.inject_button = ttk.Button(
            button_frame,
            text="Inject to System",
            command=self._on_inject_code,
            state=tk.DISABLED
        )
        self.inject_button.pack(side=tk.LEFT, padx=5)
        
        # Output area
        output_frame = ttk.LabelFrame(tab, text="Generated Code")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5, ipadx=5, ipady=5)
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            bg='#3B4252',
            fg='#E5E9F0',
            insertbackground='white',
            padx=10,
            pady=10,
            state=tk.DISABLED
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Console output
        console_frame = ttk.LabelFrame(tab, text="Console Output")
        console_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5, ipadx=5, ipady=5, height=150)
        
        self.console_text = scrolledtext.ScrolledText(
            console_frame,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg='#2E3440',
            fg='#D8DEE9',
            insertbackground='white',
            padx=10,
            pady=10,
            state=tk.DISABLED
        )
        self.console_text.pack(fill=tk.BOTH, expand=True)
    
    def _create_settings_tab(self):
        """Create the settings tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Settings")
        
        # Settings container
        settings_frame = ttk.LabelFrame(tab, text="Code Generation Settings")
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10, ipadx=5, ipady=5)
        
        # Model settings
        ttk.Label(settings_frame, text="Default Model:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        
        self.default_model_var = tk.StringVar(value="deepseek-coder-v2")
        model_dropdown = ttk.Combobox(
            settings_frame,
            textvariable=self.default_model_var,
            values=["deepseek-coder-v2", "llama2", "codegemma-2", "gpt-4"],
            state='readonly',
            width=20
        )
        model_dropdown.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        
        # Temperature setting
        ttk.Label(settings_frame, text="Temperature:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        
        self.temp_var = tk.DoubleVar(value=0.7)
        temp_scale = ttk.Scale(
            settings_frame,
            from_=0.1,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.temp_var
        )
        temp_scale.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        
        # Max tokens
        ttk.Label(settings_frame, text="Max Tokens:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        
        self.max_tokens_var = tk.IntVar(value=2000)
        ttk.Spinbox(
            settings_frame,
            from_=100,
            to=8000,
            textvariable=self.max_tokens_var,
            width=10
        ).grid(row=2, column=1, sticky='w', padx=5, pady=5)
        
        # Save button
        save_button = ttk.Button(
            settings_frame,
            text="Save Settings",
            command=self._save_settings
        )
        save_button.grid(row=3, column=0, columnspan=2, pady=10)
    
    def _create_status_bar(self):
        """Create the status bar."""
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
        self.status_bar = ttk.Label(
            self.main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(5, 2)
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))
        
        # MCP status indicator
        self.mcp_status_var = tk.StringVar()
        self.mcp_status_var.set("MCP: Not Connected")
        
        self.mcp_status = ttk.Label(
            self.status_bar,
            textvariable=self.mcp_status_var,
            foreground='red',
            padding=(0, 0, 10, 0)
        )
        self.mcp_status.pack(side=tk.RIGHT)
    
    async def _connect_to_mcp_async(self):
        """Connect to MCP asynchronously."""
        try:
            self._update_status("Connecting to MCP...")
            await self.mcp_connector.initialize()
            await self.mcp_connector.connect()
            
            # Update UI
            self.mcp_status_var.set(f"MCP: Connected ({self.mcp_connector.current_model})")
            self.mcp_status.configure(foreground='green')
            self._update_status("Connected to MCP")
            
            # Enable generate button
            self.generate_button.config(state=tk.NORMAL)
            
        except Exception as e:
            self._update_status(f"Failed to connect to MCP: {str(e)}", error=True)
            self.mcp_status_var.set("MCP: Connection Failed")
            self.mcp_status.configure(foreground='red')
    
    def _connect_to_mcp(self):
        """Connect to MCP (wrapper for async)."""
        asyncio.create_task(self._connect_to_mcp_async())
    
    async def _generate_code_async(self):
        """Generate code asynchronously."""
        try:
            # Get input prompt
            prompt = self.input_text.get("1.0", tk.END).strip()
            if not prompt:
                self._update_status("Please enter a prompt", error=True)
                return
            
            # Update UI
            self._update_status("Generating code...")
            self.generate_button.config(state=tk.DISABLED)
            self.root.update()
            
            # Call MCP connector
            model = self.model_var.get()
            temperature = self.temp_var.get()
            max_tokens = self.max_tokens_var.get()
            
            result = await self.mcp_connector.generate_code(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if result.get('success', False):
                # Display generated code
                code = result.get('code', '')
                language = result.get('language', 'python')
                
                self.output_text.config(state=tk.NORMAL)
                self.output_text.delete("1.0", tk.END)
                self.output_text.insert(tk.END, code)
                self.output_text.config(state=tk.DISABLED)
                
                # Enable execute and inject buttons
                self.execute_button.config(state=tk.NORMAL)
                self.inject_button.config(state=tk.NORMAL)
                
                self._update_status("Code generated successfully")
                self._log_to_console("Code generation completed successfully.")
            else:
                error = result.get('error', 'Unknown error')
                self._update_status(f"Error generating code: {error}", error=True)
                self._log_to_console(f"Error: {error}", error=True)
                
        except Exception as e:
            self._update_status(f"Error: {str(e)}", error=True)
            self._log_to_console(f"Error: {str(e)}", error=True)
            
        finally:
            self.generate_button.config(state=tk.NORMAL)
    
    def _on_generate_code(self):
        """Handle generate code button click."""
        asyncio.create_task(self._generate_code_async())
    
    async def _execute_code_async(self):
        """Execute the generated code asynchronously."""
        try:
            # Get code to execute
            code = self.output_text.get("1.0", tk.END).strip()
            if not code:
                self._update_status("No code to execute", error=True)
                return
            
            # Update UI
            self._update_status("Executing code...")
            self.execute_button.config(state=tk.DISABLED)
            self._log_to_console("Executing code...")
            self.root.update()
            
            # Call MCP connector to execute code
            result = await self.mcp_connector.execute_code(
                code=code,
                language='python'  # Default to Python for now
            )
            
            if result.get('success', False):
                output = result.get('output', '')
                self._log_to_console(f"Execution result:\n{output}")
                self._update_status("Code executed successfully")
            else:
                error = result.get('error', 'Unknown error')
                self._log_to_console(f"Execution error: {error}", error=True)
                self._update_status(f"Execution error: {error}", error=True)
                
        except Exception as e:
            self._update_status(f"Error executing code: {str(e)}", error=True)
            self._log_to_console(f"Error: {str(e)}", error=True)
            
        finally:
            self.execute_button.config(state=tk.NORMAL)
    
    def _on_execute_code(self):
        """Handle execute code button click."""
        asyncio.create_task(self._execute_code_async())
    
    async def _inject_code_async(self):
        """Inject code into the system asynchronously."""
        try:
            # Get code to inject
            code = self.output_text.get("1.0", tk.END).strip()
            if not code:
                self._update_status("No code to inject", error=True)
                return
            
            # Ask for confirmation
            if not messagebox.askyesno(
                "Confirm Injection",
                "Are you sure you want to inject this code into the system?\n\n"
                "This operation cannot be undone."
            ):
                self._update_status("Injection cancelled")
                return
            
            # Update UI
            self._update_status("Injecting code...")
            self.inject_button.config(state=tk.DISABLED)
            self._log_to_console("Injecting code into system...")
            self.root.update()
            
            # Call MCP connector to inject code
            result = await self.mcp_connector.inject_code(
                code=code,
                target_module="user_modules"
            )
            
            if result.get('success', False):
                message = result.get('message', 'Code injected successfully')
                self._log_to_console(message)
                self._update_status("Code injected successfully")
                messagebox.showinfo("Success", message)
            else:
                error = result.get('error', 'Unknown error')
                self._log_to_console(f"Injection failed: {error}", error=True)
                self._update_status(f"Injection failed: {error}", error=True)
                messagebox.showerror("Error", f"Failed to inject code: {error}")
                
        except Exception as e:
            self._update_status(f"Error injecting code: {str(e)}", error=True)
            self._log_to_console(f"Error: {str(e)}", error=True)
            messagebox.showerror("Error", f"Failed to inject code: {str(e)}")
            
        finally:
            self.inject_button.config(state=tk.NORMAL)
    
    def _on_inject_code(self):
        """Handle inject code button click."""
        asyncio.create_task(self._inject_code_async())
    
    def _save_settings(self):
        """Save application settings."""
        try:
            settings = {
                'default_model': self.default_model_var.get(),
                'temperature': self.temp_var.get(),
                'max_tokens': self.max_tokens_var.get()
            }
            
            # Save to file
            config_dir = os.path.expanduser("~/.kingdom_ai")
            os.makedirs(config_dir, exist_ok=True)
            
            config_file = os.path.join(config_dir, 'code_generator_config.json')
            with open(config_file, 'w') as f:
                json.dump(settings, f, indent=2)
            
            self._update_status("Settings saved successfully")
            
        except Exception as e:
            self._update_status(f"Error saving settings: {str(e)}", error=True)
    
    def _load_settings(self):
        """Load application settings."""
        try:
            config_file = os.path.expanduser("~/.kingdom_ai/code_generator_config.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    settings = json.load(f)
                
                # Apply settings
                self.default_model_var.set(settings.get('default_model', 'deepseek-coder-v2'))
                self.temp_var.set(float(settings.get('temperature', 0.7)))
                self.max_tokens_var.set(int(settings.get('max_tokens', 2000)))
                
                # Update model dropdown
                self.model_var.set(self.default_model_var.get())
                
        except Exception as e:
            logger.warning(f"Failed to load settings: {str(e)}")
    
    def _update_status(self, message: str, error: bool = False):
        """Update the status bar.
        
        Args:
            message: Status message
            error: Whether this is an error message
        """
        self.status_var.set(message)
        if error:
            self.status_bar.configure(foreground='red')
        else:
            self.status_bar.configure(foreground='black')
    
    def _log_to_console(self, message: str, error: bool = False):
        """Log a message to the console output.
        
        Args:
            message: Message to log
            error: Whether this is an error message
        """
        self.console_text.config(state=tk.NORMAL)
        
        # Add timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}] ERROR: " if error else f"[{timestamp}] "
        
        # Insert message
        self.console_text.insert(tk.END, prefix + message + "\n")
        
        # Scroll to end
        self.console_text.see(tk.END)
        self.console_text.config(state=tk.DISABLED)
    
    def on_close(self):
        """Handle application close event."""
        # Clean up resources
        if hasattr(self, 'mcp_connector'):
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_until_complete(self.mcp_connector.close())
        
        # Close the application
        self.root.destroy()
        
        # Exit the application
        sys.exit(0)

def main():
    """Main entry point for the application."""
    # Create root window
    root = tk.Tk()
    
    # Set application icon if available
    try:
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'icon.ico')
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        logger.warning(f"Failed to set application icon: {str(e)}")
    
    # Create and run the application
    app = CodeGeneratorApp(root)
    
    # Load settings
    app._load_settings()
    
    # Start the main event loop
    root.mainloop()

if __name__ == "__main__":
    main()
