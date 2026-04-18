"""
SOTA 2026 UI Event Handlers for Visual Creation Canvas
Backend and Quality preset change handlers
"""

from enum import Enum


def _on_backend_changed(self, index: int):
    """Handle video backend selection change - SOTA 2026."""
    backends = [
        VideoBackend.AUTO,
        VideoBackend.ANIMATELCM,
        VideoBackend.MOCHI1,
        VideoBackend.SVD_XT,
        VideoBackend.HUNYUAN,
        VideoBackend.LTXVIDEO
    ]
    
    if 0 <= index < len(backends):
        self._generation_config.video_backend = backends[index]
        
        # Update status label with backend info
        backend_names = {
            VideoBackend.AUTO: "Auto-select based on quality",
            VideoBackend.ANIMATELCM: "AnimateLCM - Fast (6-8 steps, 768x512)",
            VideoBackend.MOCHI1: "Mochi 1 - Production (64 steps, 848x480, 10B params)",
            VideoBackend.SVD_XT: "SVD-XT - Image-to-Video (25 frames, 1024x576)",
            VideoBackend.HUNYUAN: "HunyuanVideo - Cinematic (50 steps, 1080p, 13B params)",
            VideoBackend.LTXVIDEO: "LTXVideo - Real-time (8-12 steps, 768x512)"
        }
        
        backend_name = backend_names.get(backends[index], "Unknown")
        if hasattr(self, 'status_label') and self.status_label is not None:
            self.status_label.setText(f"Backend: {backend_name}")
        
        logger.info(f"Video backend changed to: {backends[index].value}")


def _on_quality_changed(self, index: int):
    """Handle quality preset selection change - SOTA 2026."""
    presets = [
        QualityPreset.DRAFT,
        QualityPreset.STANDARD,
        QualityPreset.PRODUCTION,
        QualityPreset.CINEMATIC
    ]
    
    if 0 <= index < len(presets):
        preset = presets[index]
        self._generation_config.quality_preset = preset
        
        # Apply preset settings to config
        preset_settings = {
            QualityPreset.DRAFT: {
                'steps': 6,
                'width': 512,
                'height': 512,
                'guidance_scale': 2.0,
                'num_frames': 16
            },
            QualityPreset.STANDARD: {
                'steps': 12,
                'width': 768,
                'height': 512,
                'guidance_scale': 7.5,
                'num_frames': 24
            },
            QualityPreset.PRODUCTION: {
                'steps': 30,
                'width': 1024,
                'height': 576,
                'guidance_scale': 8.0,
                'num_frames': 48
            },
            QualityPreset.CINEMATIC: {
                'steps': 64,
                'width': 1280,
                'height': 720,
                'guidance_scale': 6.0,
                'num_frames': 129
            }
        }
        
        if preset in preset_settings:
            settings = preset_settings[preset]
            
            # Update UI controls
            if hasattr(self, 'steps_slider') and self.steps_slider is not None:
                self.steps_slider.blockSignals(True)
                self.steps_slider.setValue(settings['steps'])
                self.steps_slider.blockSignals(False)
                if hasattr(self, 'steps_value_label'):
                    self.steps_value_label.setText(str(settings['steps']))
            
            if hasattr(self, 'width_spin') and self.width_spin is not None:
                self.width_spin.blockSignals(True)
                self.width_spin.setValue(settings['width'])
                self.width_spin.blockSignals(False)
            
            if hasattr(self, 'height_spin') and self.height_spin is not None:
                self.height_spin.blockSignals(True)
                self.height_spin.setValue(settings['height'])
                self.height_spin.blockSignals(False)
            
            # Update config
            self._generation_config.steps = settings['steps']
            self._generation_config.width = settings['width']
            self._generation_config.height = settings['height']
            self._generation_config.guidance_scale = settings['guidance_scale']
            self._generation_config.num_frames = settings['num_frames']
            
            if hasattr(self, 'status_label') and self.status_label is not None:
                self.status_label.setText(f"Quality: {preset.value.upper()} - {settings['width']}x{settings['height']}, {settings['steps']} steps")
            
            logger.info(f"Quality preset changed to: {preset.value} ({settings['width']}x{settings['height']}, {settings['steps']} steps)")


# Import for type hints
import logging
logger = logging.getLogger("KingdomAI.VisualCreationCanvas")

# Import enums
from gui.widgets.visual_creation_canvas import VideoBackend, QualityPreset
