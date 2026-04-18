#!/usr/bin/env python3

"""
Kingdom AI GUI Demo
Demonstrates the AI-powered GUI with color-changing abilities
Works with both standard Tkinter and CustomTkinter
"""

import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("KingdomAI.GUIDemo")

# Try to import tkinter
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False
    logger.warning("Tkinter not available - GUI will not function")

# Try to import customtkinter
try:
    import customtkinter as ctk
    HAS_CUSTOMTKINTER = True
    # Set customtkinter appearance
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
except ImportError:
    HAS_CUSTOMTKINTER = False
    logger.info("CustomTkinter not available - falling back to standard Tkinter")

# Import the AI GUI integration
try:
    from core.gui_ai_integration import GUIAIIntegration
except ImportError:
    logger.error("Could not import GUIAIIntegration - AI features unavailable")
    GUIAIIntegration = None


class NeonFrame(tk.Frame):
    """Custom frame with neon border effect that changes colors"""
    
    def __init__(self, master, **kwargs):
        self.border_width = kwargs.pop('border_width', 2)
        self.border_color = kwargs.pop('border_color', '#3498db')
        self.colors = ['#ff4500', '#ffd700', '#32cd32', '#00bfff', '#8a2be2']  # Orange, Yellow, Green, Blue, Purple
        self.color_index = 0
        
        kwargs['highlightbackground'] = self.border_color
        kwargs['highlightcolor'] = self.border_color
        kwargs['highlightthickness'] = self.border_width
        
        super().__init__(master, **kwargs)
        
        # Start color cycling if enabled
        self.color_cycling = kwargs.pop('color_cycling', True)
        if self.color_cycling:
            self.cycle_colors()
    
    def cycle_colors(self):
        """Cycle through neon border colors"""
        if not self.color_cycling:
            return
            
        self.color_index = (self.color_index + 1) % len(self.colors)
        self.border_color = self.colors[self.color_index]
        
        self.config(highlightbackground=self.border_color, 
                   highlightcolor=self.border_color)
        
        # Schedule the next color change
        self.after(500, self.cycle_colors)
    
    def set_color(self, color):
        """Set the border color"""
        self.border_color = color
        self.config(highlightbackground=color, highlightcolor=color)
    
    def toggle_cycling(self):
        """Toggle color cycling on/off"""
        self.color_cycling = not self.color_cycling
        if self.color_cycling:
            self.cycle_colors()


class GUIDemo:
    """Demo class for the Kingdom AI GUI with AI features"""
    
    def __init__(self, use_custom_tk=False):
        """Initialize the GUI demo
        
        Args:
            use_custom_tk: Whether to use CustomTkinter if available
        """
        self.logger = logging.getLogger("KingdomAI.GUIDemo")
        
        # Determine which UI toolkit to use
        self.use_custom_tk = use_custom_tk and HAS_CUSTOMTKINTER
        
        # Setup UI variables
        self.root = None
        self.frames = {}
        self.buttons = {}
        self.labels = {}
        self.tabs = {}
        
        # Counters for interaction tracking
        self.click_counts = {}
        
        # Initialize UI
        self.setup_ui()
        
        # Initialize AI integration
        self.setup_ai()
        
        self.logger.info(f"GUI Demo initialized with {'CustomTkinter' if self.use_custom_tk else 'Tkinter'}")
    
    def setup_ui(self):
        """Set up the UI components"""
        # Create the root window
        if self.use_custom_tk:
            self.root = ctk.CTk()
            self.root.title("Kingdom AI GUI Demo (CustomTkinter)")
        else:
            self.root = tk.Tk()
            self.root.title("Kingdom AI GUI Demo (Tkinter)")
        
        self.root.geometry("800x600")
        
        # Create main frames
        self.create_header_frame()
        self.create_content_frame()
        self.create_status_frame()
    
    def create_header_frame(self):
        """Create the header frame with title and controls"""
        if self.use_custom_tk:
            header = ctk.CTkFrame(self.root)
            header.pack(fill="x", padx=10, pady=10)
            
            title = ctk.CTkLabel(header, text="Kingdom AI Smart GUI", 
                               font=ctk.CTkFont(size=20, weight="bold"))
            title.pack(side="left", padx=10)
            
            theme_btn = ctk.CTkButton(header, text="Toggle Theme", 
                                    command=self.toggle_theme)
            theme_btn.pack(side="right", padx=10)
            
            self.ai_toggle_btn = ctk.CTkButton(header, text="AI: ON", 
                                             command=self.toggle_ai)
            self.ai_toggle_btn.pack(side="right", padx=10)
        else:
            header = NeonFrame(self.root, bg="#2c3e50")
            header.pack(fill="x", padx=10, pady=10)
            
            title = tk.Label(header, text="Kingdom AI Smart GUI", 
                           font=("Arial", 20, "bold"), bg="#2c3e50", fg="white")
            title.pack(side="left", padx=10)
            
            theme_btn = tk.Button(header, text="Toggle Theme", 
                               command=self.toggle_theme)
            theme_btn.pack(side="right", padx=10)
            
            self.ai_toggle_btn = tk.Button(header, text="AI: ON", 
                                        command=self.toggle_ai)
            self.ai_toggle_btn.pack(side="right", padx=10)
        
        # Store references
        self.frames['header'] = header
        self.buttons['theme'] = theme_btn
        self.buttons['ai_toggle'] = self.ai_toggle_btn
    
    def create_content_frame(self):
        """Create the main content frame with tabs"""
        if self.use_custom_tk:
            # Create tabview
            tabview = ctk.CTkTabview(self.root)
            tabview.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create dashboard tab
            dashboard_tab = tabview.add("Dashboard")
            self.create_dashboard_content(dashboard_tab)
            
            # Create settings tab
            settings_tab = tabview.add("Settings")
            self.create_settings_content(settings_tab)
            
            # Create about tab
            about_tab = tabview.add("About")
            self.create_about_content(about_tab)
            
            # Store references
            self.tabs['tabview'] = tabview
            self.tabs['dashboard'] = dashboard_tab
            self.tabs['settings'] = settings_tab
            self.tabs['about'] = about_tab
        else:
            # Create content frame
            content = NeonFrame(self.root, bg="#34495e")
            content.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create notebook for tabs
            notebook = ttk.Notebook(content)
            notebook.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Create dashboard tab
            dashboard_tab = ttk.Frame(notebook)
            notebook.add(dashboard_tab, text="Dashboard")
            self.create_dashboard_content(dashboard_tab)
            
            # Create settings tab
            settings_tab = ttk.Frame(notebook)
            notebook.add(settings_tab, text="Settings")
            self.create_settings_content(settings_tab)
            
            # Create about tab
            about_tab = ttk.Frame(notebook)
            notebook.add(about_tab, text="About")
            self.create_about_content(about_tab)
            
            # Store references
            self.frames['content'] = content
            self.tabs['notebook'] = notebook
            self.tabs['dashboard'] = dashboard_tab
            self.tabs['settings'] = settings_tab
            self.tabs['about'] = about_tab
    
    def create_dashboard_content(self, parent):
        """Create content for the dashboard tab"""
        if self.use_custom_tk:
            # Create two columns
            left_col = ctk.CTkFrame(parent)
            left_col.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            
            right_col = ctk.CTkFrame(parent)
            right_col.pack(side="right", fill="both", expand=True, padx=5, pady=5)
            
            # System status section
            status_frame = ctk.CTkFrame(left_col)
            status_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(status_frame, text="System Status", 
                       font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
            
            for i, status in enumerate(["AI System: Online", "Trading: Active", 
                                      "Security: Secure", "Network: Connected"]):
                ctk.CTkLabel(status_frame, text=status).pack(anchor="w", padx=20, pady=2)
            
            # Quick actions section
            actions_frame = ctk.CTkFrame(right_col)
            actions_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(actions_frame, text="Quick Actions", 
                       font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
            
            for i, action in enumerate(["Run Analysis", "Generate Report", 
                                       "Backup System", "Check Updates"]):
                btn = ctk.CTkButton(actions_frame, text=action, 
                                  command=lambda a=action: self.handle_action(a))
                btn.pack(anchor="w", padx=20, pady=5, fill="x")
                self.buttons[f"action_{i}"] = btn
        else:
            # Create two columns
            left_col = tk.Frame(parent, bg="#34495e")
            left_col.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            
            right_col = tk.Frame(parent, bg="#34495e")
            right_col.pack(side="right", fill="both", expand=True, padx=5, pady=5)
            
            # System status section
            status_frame = NeonFrame(left_col, bg="#3d556c")
            status_frame.pack(fill="x", padx=10, pady=10)
            
            tk.Label(status_frame, text="System Status", font=("Arial", 12, "bold"),
                   bg="#3d556c", fg="white").pack(anchor="w", padx=10, pady=5)
            
            for i, status in enumerate(["AI System: Online", "Trading: Active", 
                                      "Security: Secure", "Network: Connected"]):
                tk.Label(status_frame, text=status, bg="#3d556c", fg="white").pack(
                    anchor="w", padx=20, pady=2)
            
            # Quick actions section
            actions_frame = NeonFrame(right_col, bg="#3d556c")
            actions_frame.pack(fill="x", padx=10, pady=10)
            
            tk.Label(actions_frame, text="Quick Actions", font=("Arial", 12, "bold"),
                   bg="#3d556c", fg="white").pack(anchor="w", padx=10, pady=5)
            
            for i, action in enumerate(["Run Analysis", "Generate Report", 
                                       "Backup System", "Check Updates"]):
                btn = tk.Button(actions_frame, text=action, 
                             command=lambda a=action: self.handle_action(a))
                btn.pack(anchor="w", padx=20, pady=5, fill="x")
                self.buttons[f"action_{i}"] = btn
    
    def create_settings_content(self, parent):
        """Create content for the settings tab"""
        if self.use_custom_tk:
            # System settings section
            settings_frame = ctk.CTkFrame(parent)
            settings_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            ctk.CTkLabel(settings_frame, text="System Settings", 
                       font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
            
            # Create settings controls
            for i, setting in enumerate([
                ("Enable AI Features", True),
                ("Dark Mode", True),
                ("Auto Updates", False),
                ("Notifications", True)
            ]):
                name, default = setting
                row = ctk.CTkFrame(settings_frame)
                row.pack(fill="x", padx=10, pady=5)
                
                ctk.CTkLabel(row, text=name).pack(side="left", padx=10)
                var = tk.BooleanVar(value=default)
                switch = ctk.CTkSwitch(row, text="", variable=var, 
                                     command=lambda n=name: self.handle_setting_change(n))
                switch.pack(side="right", padx=10)
                
                self.buttons[f"setting_{i}"] = switch
        else:
            # System settings section
            settings_frame = NeonFrame(parent, bg="#3d556c")
            settings_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            tk.Label(settings_frame, text="System Settings", 
                   font=("Arial", 12, "bold"), bg="#3d556c", fg="white").pack(
                       anchor="w", padx=10, pady=5)
            
            # Create settings controls
            for i, setting in enumerate([
                ("Enable AI Features", True),
                ("Dark Mode", True),
                ("Auto Updates", False),
                ("Notifications", True)
            ]):
                name, default = setting
                row = tk.Frame(settings_frame, bg="#3d556c")
                row.pack(fill="x", padx=10, pady=5)
                
                tk.Label(row, text=name, bg="#3d556c", fg="white").pack(side="left", padx=10)
                var = tk.BooleanVar(value=default)
                chk = tk.Checkbutton(row, variable=var, bg="#3d556c", fg="white",
                                   command=lambda n=name: self.handle_setting_change(n))
                chk.pack(side="right", padx=10)
                
                self.buttons[f"setting_{i}"] = chk
    
    def create_about_content(self, parent):
        """Create content for the about tab"""
        if self.use_custom_tk:
            about_frame = ctk.CTkFrame(parent)
            about_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            ctk.CTkLabel(about_frame, text="Kingdom AI Smart GUI", 
                       font=ctk.CTkFont(size=18, weight="bold")).pack(padx=10, pady=10)
            
            about_text = """This demo showcases the AI-powered smart GUI for Kingdom AI.
Features:
- Adaptive UI based on user interactions
- Predictive suggestions for next actions
- Color-changing neon elements
- Compatible with both Tkinter and CustomTkinter
            """
            
            ctk.CTkLabel(about_frame, text=about_text, justify="left").pack(
                padx=20, pady=10, anchor="w")
            
            btn = ctk.CTkButton(about_frame, text="Visit Website", 
                              command=lambda: self.handle_action("Visit Website"))
            btn.pack(pady=10)
            self.buttons["about_button"] = btn
        else:
            about_frame = NeonFrame(parent, bg="#3d556c")
            about_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            tk.Label(about_frame, text="Kingdom AI Smart GUI", 
                   font=("Arial", 18, "bold"), bg="#3d556c", fg="white").pack(
                       padx=10, pady=10)
            
            about_text = """This demo showcases the AI-powered smart GUI for Kingdom AI.
Features:
- Adaptive UI based on user interactions
- Predictive suggestions for next actions
- Color-changing neon elements
- Compatible with both Tkinter and CustomTkinter
            """
            
            tk.Label(about_frame, text=about_text, justify="left", 
                   bg="#3d556c", fg="white").pack(padx=20, pady=10, anchor="w")
            
            btn = tk.Button(about_frame, text="Visit Website", 
                         command=lambda: self.handle_action("Visit Website"))
            btn.pack(pady=10)
            self.buttons["about_button"] = btn
    
    def create_status_frame(self):
        """Create the status frame with AI suggestions"""
        if self.use_custom_tk:
            status = ctk.CTkFrame(self.root)
            status.pack(fill="x", padx=10, pady=10)
            
            # Add counters
            counter_frame = ctk.CTkFrame(status)
            counter_frame.pack(side="left", fill="y", padx=10)
            
            ctk.CTkLabel(counter_frame, text="Interactions:").pack(side="left", padx=5)
            self.counter_label = ctk.CTkLabel(counter_frame, text="0")
            self.counter_label.pack(side="left", padx=5)
            
            # Add AI suggestion label
            suggestion_frame = ctk.CTkFrame(status)
            suggestion_frame.pack(side="right", fill="y", expand=True, padx=10)
            
            ctk.CTkLabel(suggestion_frame, text="AI Suggestion:").pack(side="left", padx=5)
            self.suggestion_label = ctk.CTkLabel(suggestion_frame, text="No suggestions yet")
            self.suggestion_label.pack(side="left", padx=5)
            
            # Store references
            self.frames['status'] = status
            self.labels['counter'] = self.counter_label
            self.labels['suggestion'] = self.suggestion_label
        else:
            status = NeonFrame(self.root, bg="#2c3e50")
            status.pack(fill="x", padx=10, pady=10)
            
            # Add counters
            counter_frame = tk.Frame(status, bg="#2c3e50")
            counter_frame.pack(side="left", fill="y", padx=10)
            
            tk.Label(counter_frame, text="Interactions:", bg="#2c3e50", fg="white").pack(
                side="left", padx=5)
            self.counter_label = tk.Label(counter_frame, text="0", bg="#2c3e50", fg="white")
            self.counter_label.pack(side="left", padx=5)
            
            # Add AI suggestion label
            suggestion_frame = tk.Frame(status, bg="#2c3e50")
            suggestion_frame.pack(side="right", fill="y", expand=True, padx=10)
            
            tk.Label(suggestion_frame, text="AI Suggestion:", bg="#2c3e50", fg="white").pack(
                side="left", padx=5)
            self.suggestion_label = tk.Label(suggestion_frame, text="No suggestions yet", 
                                          bg="#2c3e50", fg="white")
            self.suggestion_label.pack(side="left", padx=5)
            
            # Store references
            self.frames['status'] = status
            self.labels['counter'] = self.counter_label
            self.labels['suggestion'] = self.suggestion_label
    
    def setup_ai(self):
        """Set up the AI integration"""
        if GUIAIIntegration is None:
            self.logger.warning("GUIAIIntegration not available - AI features disabled")
            self.ai_manager = None
            return
        
        try:
            # Create AI manager
            self.ai_manager = GUIAIIntegration()
            
            # Set suggestion widget
            self.ai_manager.set_suggestion_widget(self.suggestion_label)
            
            # Register all buttons
            for button_id, button in self.buttons.items():
                self.ai_manager.register_widget(button, name=button_id)
            
            # Initialize AI
            self.ai_manager.initialize_sync()
            
            self.logger.info("AI integration set up successfully")
        except Exception as e:
            self.logger.error(f"Error setting up AI integration: {e}")
            self.ai_manager = None
    
    def handle_action(self, action):
        """Handle a button click action
        
        Args:
            action: The action name
        """
        self.logger.info(f"Action triggered: {action}")
        
        # Update interaction counters
        if action not in self.click_counts:
            self.click_counts[action] = 0
        self.click_counts[action] += 1
        
        total_clicks = sum(self.click_counts.values())
        self.counter_label.config(text=str(total_clicks)) if hasattr(self.counter_label, 'config') else None
        
        # Show message
        if self.use_custom_tk:
            ctk.CTkMessagebox(title="Action", message=f"Executing action: {action}")
        else:
            messagebox.showinfo("Action", f"Executing action: {action}")
    
    def handle_setting_change(self, setting):
        """Handle a setting change
        
        Args:
            setting: The setting name
        """
        self.logger.info(f"Setting changed: {setting}")
        
        # Show message
        if self.use_custom_tk:
            ctk.CTkMessagebox(title="Setting Changed", message=f"Setting changed: {setting}")
        else:
            messagebox.showinfo("Setting Changed", f"Setting changed: {setting}")
    
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        if self.use_custom_tk:
            current = ctk.get_appearance_mode()
            new_mode = "Light" if current == "Dark" else "Dark"
            ctk.set_appearance_mode(new_mode)
        else:
            # For standard tkinter, toggle the color cycling on neon frames
            for frame_name, frame in self.frames.items():
                if isinstance(frame, NeonFrame):
                    frame.toggle_cycling()
    
    def toggle_ai(self):
        """Toggle AI features on/off"""
        if self.ai_manager:
            self.ai_manager.toggle_ai()
            is_enabled = getattr(self.ai_manager, 'ai_enabled', False)
            
            # Update button text
            if self.use_custom_tk:
                self.ai_toggle_btn.configure(text=f"AI: {'ON' if is_enabled else 'OFF'}")
            else:
                self.ai_toggle_btn.config(text=f"AI: {'ON' if is_enabled else 'OFF'}")
    
    def run(self):
        """Run the GUI demo"""
        if not self.root:
            self.logger.error("Cannot run demo - UI not initialized")
            return False
        
        try:
            self.root.mainloop()
            return True
        except Exception as e:
            self.logger.error(f"Error running demo: {e}")
            return False


def main():
    """Main entry point"""
    # Check if CustomTkinter should be used
    use_custom_tk = "--custom" in sys.argv
    
    demo = GUIDemo(use_custom_tk=use_custom_tk)
    demo.run()


if __name__ == "__main__":
    main()
