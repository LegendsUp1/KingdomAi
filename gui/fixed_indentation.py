# Fixed version of the methods with proper indentation

def init_component_frames(self):
    """Initialize component frames and tabs in the main window.

    This method sets up the notebook widget and creates all necessary tabs for the
    various components of the Kingdom AI system.

    Returns:
        bool: True if initialization succeeds, False otherwise
    """
    try:
        # Configure notebook if it doesn't exist
        if 'main' not in self._notebooks:
            self.logger.info("Initializing component frames")
            
            # Reapply dark theme to ensure styling is correct
            self._set_dark_theme()
            
            # Make sure the notebook exists and is visible with proper typing
            notebook = self._get_widget("notebook")
            
            if not notebook:
                self.logger.error("Notebook widget not found")
                # Try getting it as a widget if not found as a notebook
                notebook_widget = self._get_widget("notebook")
                
                if notebook_widget and isinstance(notebook_widget, ttk.Notebook):
                    # Cast to ttk.Notebook type and register in notebooks dictionary
                    notebook = notebook_widget
                    self._notebooks["notebook"] = notebook
                else:
                    self.logger.error("Failed to find notebook widget in any registry")
                    return False
            
            # Continue only if we have a valid notebook
            if not notebook or not isinstance(notebook, ttk.Notebook):
                self.logger.error("Valid notebook not found or not a ttk.Notebook")
                return False
                
            # Use grid instead of pack to avoid geometry manager conflicts
            notebook.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
            
            # Ensure all tabs are created and added to the notebook
            # First check if tabs already exist
            existing_tabs = notebook.tabs()
            
            # Only create tabs if none exist
            if not existing_tabs:
                self.logger.info("No existing tabs found, creating component tabs")
                
                # Create all the tab frames for all components
                chat_tab = self._create_chat_tab()
                notebook.add(chat_tab, text="Chat")
                
                code_tab = self._create_code_tab()
                notebook.add(code_tab, text="Code Generator")
                
                trading_tab = self._create_trading_tab()
                notebook.add(trading_tab, text="Trading")
                
                mining_tab = self._create_mining_tab()
                notebook.add(mining_tab, text="Mining")
                
                wallet_tab = self._create_wallet_tab()
                notebook.add(wallet_tab, text="Wallet")
                
                voice_tab = self._create_voice_tab()
                notebook.add(voice_tab, text="Voice")
                
                vr_tab = self._create_vr_tab()
                notebook.add(vr_tab, text="VR")
                
                api_keys_tab = self._create_api_keys_tab()
                notebook.add(api_keys_tab, text="API Keys")
                
                meta_tab = self._create_meta_tab()
                notebook.add(meta_tab, text="Meta Learning")
                
                settings_tab = self._create_settings_tab()
                notebook.add(settings_tab, text="Settings")
                
                self.logger.info(f"Created {len(notebook.tabs())} component tabs")
            else:
                self.logger.info(f"Using existing tabs: {len(existing_tabs)}")
            
            self.logger.info("Component frames initialized successfully")
            return True
        return False  # Return False if notebook already exists
    except Exception as e:
        self.logger.error(f"Error initializing component frames: {e}")
        self.logger.error(traceback.format_exc())
        return False

def _post_show_callback(self):
    """Perform final actions after the main window is fully displayed.

    This method is called after a short delay following the initial window display
    to ensure the window has been properly rendered and is fully visible to the user.
    """
    try:
        # Ensure window is fully active and ready for user interaction
        self.lift()
        self.focus_force()
        
        # Trigger any post-initialization events
        if self.event_bus:
            self.event_bus.trigger('gui.main_window.ready', {})
            
        # Log successful completion
        self.logger.info("Main window fully initialized and ready for interaction")
        
        # Refresh the window to ensure all components are properly displayed
        self.update()
        return True
    except Exception as e:
        self.logger.error(f"Error in post-show callback: {e}")
        # Continue anyway - window should still be usable
        self.logger.error(traceback.format_exc())
        return False
