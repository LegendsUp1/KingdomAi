# GUI package for Kingdom AI

# Import required modules
import sys
import logging
import os
import types
import importlib

# Ensure correct environment path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
# Add project root to path to ensure modules are found
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Configure root logger if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Logger for GUI module
logger = logging.getLogger('KingdomAI.GUI')

# Initialize styles modules with comprehensive error handling

# Function to create a fallback styles module with basic styling properties
def create_fallback_styles():
    """Create a fallback styles module with basic styling properties"""
    fallback = types.ModuleType('gui.styles')
    setattr(fallback, '__name__', 'gui.styles')
    setattr(fallback, '__file__', os.path.join(current_dir, 'styles.py'))
    
    # Basic styles using setattr to avoid IDE warnings
    setattr(fallback, 'MAIN_BG_COLOR', '#212121')
    setattr(fallback, 'TEXT_COLOR', '#FFFFFF')
    setattr(fallback, 'ACCENT_COLOR', '#1976D2')
    setattr(fallback, 'BUTTON_COLOR', '#2196F3')
    setattr(fallback, 'FONT_FAMILY', 'Arial')
    setattr(fallback, 'LABEL_STYLE', {'color': '#FFFFFF', 'font': ('Arial', 10)})
    setattr(fallback, 'BUTTON_STYLE', {'bg': '#2196F3', 'fg': '#FFFFFF'})
    setattr(fallback, 'FRAME_STYLE', {'bg': '#212121'})
    
    # Add __all__ using setattr
    setattr(fallback, '__all__', [
        'MAIN_BG_COLOR', 'TEXT_COLOR', 'ACCENT_COLOR', 'BUTTON_COLOR',
        'FONT_FAMILY', 'LABEL_STYLE', 'BUTTON_STYLE', 'FRAME_STYLE',
        'GlowButton', 'rgb_animation_manager'
    ])
    
    # Ensure GlowButton and rgb_animation_manager are available
    class GlowButton:
        """SOTA 2026: Fallback GlowButton implementation.
        
        Provides basic button functionality when main implementation unavailable.
        """
        def __init__(self, parent=None, text="", command=None, *args, **kwargs):
            logger.warning("Using fallback GlowButton implementation")
            self.parent = parent
            self.text = text
            self.command = command
            self._enabled = True
            self._glow_color = "#00ffff"
            self._glow_intensity = 0.5
        
        def setText(self, text):
            """Set button text."""
            self.text = text
        
        def setEnabled(self, enabled):
            """Set enabled state."""
            self._enabled = enabled
        
        def click(self):
            """Simulate button click."""
            if self._enabled and self.command:
                self.command()
        
        def setGlowColor(self, color):
            """Set glow effect color."""
            self._glow_color = color
        
        def setGlowIntensity(self, intensity):
            """Set glow intensity (0.0 - 1.0)."""
            self._glow_intensity = max(0.0, min(1.0, intensity))
    
    class RGBAnimationManager:
        """SOTA 2026: Fallback RGB Animation Manager.
        
        Provides animation timing and color cycling when main implementation unavailable.
        """
        def __init__(self):
            logger.warning("Using fallback RGBAnimationManager implementation")
            self._running = False
            self._widgets = []
            self._current_hue = 0.0
            self._animation_speed = 0.01
            self._timer = None
        
        def start(self):
            """Start RGB animation cycle."""
            self._running = True
            logger.info("RGB animation started (fallback mode)")
        
        def stop(self):
            """Stop RGB animation cycle."""
            self._running = False
            logger.info("RGB animation stopped (fallback mode)")
        
        def register_widget(self, widget):
            """Register a widget for RGB animation."""
            if widget not in self._widgets:
                self._widgets.append(widget)
        
        def unregister_widget(self, widget):
            """Unregister a widget from RGB animation."""
            if widget in self._widgets:
                self._widgets.remove(widget)
        
        def is_running(self):
            """Check if animation is running."""
            return self._running
        
        def set_speed(self, speed):
            """Set animation speed."""
            self._animation_speed = max(0.001, min(0.1, speed))
        
        def get_current_color(self):
            """Get current RGB color in animation cycle."""
            import colorsys
            r, g, b = colorsys.hsv_to_rgb(self._current_hue, 1.0, 1.0)
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    
    setattr(fallback, 'GlowButton', GlowButton)
    setattr(fallback, 'rgb_animation_manager', RGBAnimationManager())
    
    return fallback

# Try to import real style modules first
try:
    # First attempt to import modules directly
    logger.info("Attempting to import styles modules...")
    
    # Force a reload to ensure fresh imports
    if 'gui.styles' in sys.modules:
        del sys.modules['gui.styles']
    if 'gui.kingdom_style' in sys.modules:
        del sys.modules['gui.kingdom_style']
        
    # Import both style modules
    from . import styles
    from . import kingdom_style
    
    # Register both modules in sys.modules to ensure they're available by name
    sys.modules['gui.styles'] = styles
    sys.modules['gui.kingdom_style'] = kingdom_style
    
    logger.info('Styles modules registered successfully')
    
    # Verify that required components are available in styles
    if not hasattr(styles, 'GlowButton') or not hasattr(styles, 'rgb_animation_manager'):
        # Components are missing, but use PyQt6 implementations from styles.py instead
        logger.info("Ensuring all style components are available from PyQt6 implementation")
        # No need to re-export from kingdom_style since styles.py has native PyQt6 versions

except (ImportError, AttributeError) as e:
    logger.warning(f'Could not import styles modules: {e}')
    
    # Create fallback module
    fallback_styles = create_fallback_styles()
    
    # Register fallback in sys.modules
    sys.modules['gui.styles'] = fallback_styles
    
    # Log warning about fallback
    logger.warning("gui.styles module not available. Using fallback styles.")

# Ensure main components are importable
try:
    from .main_window import MainWindow
    from .tab_manager import TabManager
    __all__ = ['MainWindow', 'TabManager']
except Exception as e:
    logger.error(f"Could not import main components: {e}")
    __all__ = []

# We've already attempted to import the style modules above, so only create fallbacks
# if they're not already in sys.modules. This prevents duplicate warnings.

# Verify the styles modules are properly registered and have required components
if 'gui.styles' in sys.modules:
    styles_module = sys.modules['gui.styles']
    
    # Check for essential attributes and log that we're using the real module
    if hasattr(styles_module, 'ACCENT_COLOR'):
        logger.info('Using real gui.styles module with accent color: %s', 
                   getattr(styles_module, 'ACCENT_COLOR'))
        
    # Add any missing essential attributes
    if not hasattr(styles_module, 'ACCENT_COLOR'):
        setattr(styles_module, 'ACCENT_COLOR', '#007BFF')
        
    # No warning needed here since we have the real module
else:
    # This condition should rarely be hit due to the try/except above
    # But we keep it as a final fallback
    styles_module = types.ModuleType('styles')
    setattr(styles_module, 'ACCENT_COLOR', '#007BFF')
    sys.modules['gui.styles'] = styles_module
    logger.warning('gui.styles module not available. Creating empty fallback module.')

# Same checks for kingdom_style
if 'gui.kingdom_style' in sys.modules:
    kingdom_module = sys.modules['gui.kingdom_style']
    logger.info('Using real gui.kingdom_style module')
else:
    kingdom_module = types.ModuleType('kingdom_style')
    setattr(kingdom_module, 'MAIN_BG_COLOR', '#212121')
    setattr(kingdom_module, 'TEXT_COLOR', '#FFFFFF')
    setattr(kingdom_module, 'ACCENT_COLOR', '#007BFF')
    sys.modules['gui.kingdom_style'] = kingdom_module
    logger.warning('gui.kingdom_style module not available. Creating empty fallback module.')

# Import main window classes
try:
    from .main_window import MainWindow, KingdomMainWindow
except Exception as e:
    logger.error(f"Could not import main window classes: {e}")
    MainWindow = None  # type: ignore[assignment]
    KingdomMainWindow = None  # type: ignore[assignment]

# Ensure frames directory is in path
frames_dir = os.path.join(current_dir, 'frames')
if frames_dir not in sys.path:
    sys.path.insert(0, frames_dir)

# Export frames for direct import
try:
    from .frames import *
    # Explicitly import link_frame to ensure it's available
    from .frames.link_frame import LinkFrame
except Exception as e:
    logging.getLogger('KingdomAI.GUI').warning(f'Could not import frames: {e}')

# Define __all__ to export public API
__all__ = [
    'MainWindow',
    'KingdomMainWindow',
    'LinkFrame',
    # Add other important exports here
]
