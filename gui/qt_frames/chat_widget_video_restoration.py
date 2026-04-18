"""
Video Restoration Command Handler for ChatWidget
Add this method to ChatWidget class to enable video restoration commands.
"""

def _check_video_restoration_command(self, message: str) -> bool:
    """Check if message is a video restoration command and handle it.
    
    Commands:
    - "restore" / "restore video" - Full restoration pipeline
    - "colorize" / "colorize video" - Colorization only
    - "upscale" / "upscale video" - 4K upscaling only
    - "enhance faces" - Face enhancement only
    - "detect players" - Player detection only
    
    Returns True if command was handled, False otherwise.
    """
    from pathlib import Path
    import logging
    logger = logging.getLogger("KingdomAI.ChatWidget")
    
    # Check if Visual Canvas is available
    try:
        from gui.widgets.visual_creation_canvas import VisualCreationCanvas
        VISUAL_CANVAS_AVAILABLE = True
    except:
        VISUAL_CANVAS_AVAILABLE = False
    
    if not VISUAL_CANVAS_AVAILABLE:
        return False
    
    message_lower = message.lower().strip()
    
    # Check for restoration commands
    restoration_keywords = [
        'restore', 'colorize', 'upscale', 'enhance', 'detect players',
        'restore video', 'colorize video', 'upscale video', 'enhance faces'
    ]
    
    is_restoration_cmd = any(keyword in message_lower for keyword in restoration_keywords)
    if not is_restoration_cmd:
        return False
    
    # Check if Visual Creation Canvas is available
    if not hasattr(self, '_visual_canvas') or self._visual_canvas is None:
        self.add_message("System", "❌ Visual Creation Canvas not available. Please open the Visual Creation tab first.", is_ai=True)
        return True
    
    # Check if there's an uploaded video
    if not hasattr(self._visual_canvas, '_last_uploaded_video') or not self._visual_canvas._last_uploaded_video:
        self.add_message("System", "❌ No video uploaded. Please upload a video first using the Visual Creation Canvas.", is_ai=True)
        return True
    
    video_path = self._visual_canvas._last_uploaded_video
    
    # Determine restoration config based on command
    config = {
        'colorize_method': 'ddcolor',
        'colorize_strength': 1.0,
        'enable_colorize': True,
        'upscale_factor': 4,
        'enable_upscale': True,
        'enable_face_enhance': True,
        'enable_detect': True,
        'target_width': 3840,
        'target_height': 2160
    }
    
    # Adjust config based on specific command
    if 'colorize' in message_lower and 'upscale' not in message_lower:
        config['enable_upscale'] = False
        config['enable_face_enhance'] = False
        config['enable_detect'] = False
        mode = "Colorization"
    elif 'upscale' in message_lower and 'colorize' not in message_lower:
        config['enable_colorize'] = False
        config['enable_detect'] = False
        mode = "4K Upscaling"
    elif 'enhance' in message_lower and 'face' in message_lower:
        config['enable_colorize'] = False
        config['enable_upscale'] = False
        config['enable_detect'] = False
        mode = "Face Enhancement"
    elif 'detect' in message_lower and 'player' in message_lower:
        config['enable_colorize'] = False
        config['enable_upscale'] = False
        config['enable_face_enhance'] = False
        mode = "Player Detection"
    else:
        mode = "Full Restoration"
    
    # Show confirmation message
    self.add_message("You", message, is_ai=False)
    self.message_input.clear()
    
    self.add_message("System", f"🎬 Starting {mode}...\n\nVideo: {Path(video_path).name}\n\nThis may take several minutes.", is_ai=True)
    
    # Trigger restoration
    try:
        self._visual_canvas.upload_and_restore_video(video_path, config)
        logger.info(f"✅ Video restoration triggered: {mode}")
    except Exception as e:
        logger.error(f"❌ Video restoration failed: {e}")
        self.add_message("System", f"❌ Restoration failed: {e}", is_ai=True)
    
    return True
