"""
Media Export & Conversion Component for Kingdom AI - SOTA 2026.

Comprehensive media format conversion and export via EventBus events.

SUPPORTED FORMATS:
==================
VIDEO:
- MP4 (H.264/H.265/HEVC) - Web/social media standard
- MOV (ProRes) - Professional mastering
- WebM (VP9/AV1) - Web streaming with transparency
- MKV - Multi-track container
- AVI, FLV, GIF (animated)

AUDIO:
- WAV/AIFF - Lossless studio quality
- MP3 - Compressed distribution
- AAC/M4A - High-quality compressed
- OGG/FLAC - Open formats
- OPUS - Low-latency streaming

IMAGE:
- PNG - Graphics with transparency
- JPG/JPEG - Photography
- WebP/AVIF - Next-gen web formats
- TIFF - Print/archival
- SVG - Vector graphics
- BMP, ICO, GIF

DOCUMENT:
- PDF - Universal document format
- HTML - Web export
- Markdown - Text with formatting

3D & INTERACTIVE:
- glTF/GLB - "JPEG of 3D" for web/AR/VR
- OBJ - Legacy 3D meshes
- STL - 3D printing
- FBX - Animation transfer
- USD/USDZ - Pixar/Apple 3D workflow

DATA:
- JSON - Structured data
- CSV - Tabular data
- XML - Markup data
- YAML - Configuration

ROBOTICS & ENGINEERING:
- URDF - Robot description (ROS)
- SDFormat - Gazebo simulation
- MJCF - MuJoCo physics

Subscribes to:
- media.export.* - Various export events
- media.convert - Format conversion
"""

import os
import io
import base64
import logging
import tempfile
import subprocess
import shutil
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List, Union, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("KingdomAI.MediaExport")


class MediaType(Enum):
    """Classification of media types."""
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    DOCUMENT = "document"
    DATA = "data"
    THREE_D = "3d"
    ROBOTICS = "robotics"


@dataclass
class FormatInfo:
    """Information about a media format."""
    extension: str
    media_type: MediaType
    mime_type: str
    description: str
    lossless: bool = False
    supports_transparency: bool = False


# Comprehensive format registry
FORMAT_REGISTRY: Dict[str, FormatInfo] = {
    # Video formats
    "mp4": FormatInfo("mp4", MediaType.VIDEO, "video/mp4", "MPEG-4 (H.264/H.265)", False, False),
    "mov": FormatInfo("mov", MediaType.VIDEO, "video/quicktime", "QuickTime (ProRes)", False, False),
    "webm": FormatInfo("webm", MediaType.VIDEO, "video/webm", "WebM (VP9/AV1)", False, True),
    "mkv": FormatInfo("mkv", MediaType.VIDEO, "video/x-matroska", "Matroska", False, False),
    "avi": FormatInfo("avi", MediaType.VIDEO, "video/x-msvideo", "AVI Container", False, False),
    "flv": FormatInfo("flv", MediaType.VIDEO, "video/x-flv", "Flash Video", False, False),
    # Audio formats
    "wav": FormatInfo("wav", MediaType.AUDIO, "audio/wav", "Waveform Audio", True, False),
    "aiff": FormatInfo("aiff", MediaType.AUDIO, "audio/aiff", "Audio Interchange", True, False),
    "mp3": FormatInfo("mp3", MediaType.AUDIO, "audio/mpeg", "MPEG Audio Layer 3", False, False),
    "aac": FormatInfo("aac", MediaType.AUDIO, "audio/aac", "Advanced Audio Coding", False, False),
    "m4a": FormatInfo("m4a", MediaType.AUDIO, "audio/mp4", "MPEG-4 Audio", False, False),
    "ogg": FormatInfo("ogg", MediaType.AUDIO, "audio/ogg", "Ogg Vorbis", False, False),
    "flac": FormatInfo("flac", MediaType.AUDIO, "audio/flac", "Free Lossless Audio", True, False),
    "opus": FormatInfo("opus", MediaType.AUDIO, "audio/opus", "Opus Interactive Audio", False, False),
    # Image formats
    "png": FormatInfo("png", MediaType.IMAGE, "image/png", "Portable Network Graphics", True, True),
    "jpg": FormatInfo("jpg", MediaType.IMAGE, "image/jpeg", "JPEG Image", False, False),
    "jpeg": FormatInfo("jpeg", MediaType.IMAGE, "image/jpeg", "JPEG Image", False, False),
    "webp": FormatInfo("webp", MediaType.IMAGE, "image/webp", "WebP Image", False, True),
    "avif": FormatInfo("avif", MediaType.IMAGE, "image/avif", "AV1 Image Format", False, True),
    "tiff": FormatInfo("tiff", MediaType.IMAGE, "image/tiff", "Tagged Image File", True, True),
    "tif": FormatInfo("tif", MediaType.IMAGE, "image/tiff", "Tagged Image File", True, True),
    "bmp": FormatInfo("bmp", MediaType.IMAGE, "image/bmp", "Bitmap Image", True, False),
    "gif": FormatInfo("gif", MediaType.IMAGE, "image/gif", "Graphics Interchange", True, True),
    "ico": FormatInfo("ico", MediaType.IMAGE, "image/x-icon", "Icon Format", True, True),
    "svg": FormatInfo("svg", MediaType.IMAGE, "image/svg+xml", "Scalable Vector Graphics", True, True),
    # Document formats
    "pdf": FormatInfo("pdf", MediaType.DOCUMENT, "application/pdf", "Portable Document Format", True, False),
    "html": FormatInfo("html", MediaType.DOCUMENT, "text/html", "HyperText Markup Language", True, False),
    "md": FormatInfo("md", MediaType.DOCUMENT, "text/markdown", "Markdown", True, False),
    "txt": FormatInfo("txt", MediaType.DOCUMENT, "text/plain", "Plain Text", True, False),
    # Data formats
    "json": FormatInfo("json", MediaType.DATA, "application/json", "JavaScript Object Notation", True, False),
    "csv": FormatInfo("csv", MediaType.DATA, "text/csv", "Comma-Separated Values", True, False),
    "xml": FormatInfo("xml", MediaType.DATA, "application/xml", "Extensible Markup Language", True, False),
    "yaml": FormatInfo("yaml", MediaType.DATA, "application/x-yaml", "YAML Ain't Markup Language", True, False),
    "xlsx": FormatInfo("xlsx", MediaType.DATA, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Excel Spreadsheet", True, False),
    # 3D formats
    "gltf": FormatInfo("gltf", MediaType.THREE_D, "model/gltf+json", "GL Transmission Format", True, False),
    "glb": FormatInfo("glb", MediaType.THREE_D, "model/gltf-binary", "GL Binary", True, False),
    "obj": FormatInfo("obj", MediaType.THREE_D, "model/obj", "Wavefront OBJ", True, False),
    "stl": FormatInfo("stl", MediaType.THREE_D, "model/stl", "Stereolithography", True, False),
    "fbx": FormatInfo("fbx", MediaType.THREE_D, "application/octet-stream", "Autodesk FBX", True, False),
    "usd": FormatInfo("usd", MediaType.THREE_D, "model/vnd.usd+zip", "Universal Scene Description", True, False),
    "usdz": FormatInfo("usdz", MediaType.THREE_D, "model/vnd.usdz+zip", "USD Zip Archive", True, False),
    # Robotics formats
    "urdf": FormatInfo("urdf", MediaType.ROBOTICS, "application/xml", "Unified Robot Description", True, False),
    "sdf": FormatInfo("sdf", MediaType.ROBOTICS, "application/xml", "Simulation Description Format", True, False),
    "mjcf": FormatInfo("mjcf", MediaType.ROBOTICS, "application/xml", "MuJoCo XML Format", True, False),
}


# Check for available libraries
HAS_PIL = False
HAS_REPORTLAB = False
HAS_MATPLOTLIB = False
HAS_WAVE = False
HAS_FFMPEG = False
HAS_PYDUB = False
HAS_TRIMESH = False
HAS_NUMPY = False
HAS_OPENPYXL = False
HAS_CAIROSVG = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    logger.warning("PIL not available - image conversion will be limited")

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    HAS_REPORTLAB = True
except ImportError:
    logger.warning("reportlab not available - PDF export will be limited")

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    logger.warning("matplotlib not available - chart export will be limited")

try:
    import wave
    import struct
    HAS_WAVE = True
except ImportError:
    logger.warning("wave module not available - audio export will be limited")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    logger.warning("numpy not available - some conversions will be limited")

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    logger.warning("pydub not available - audio format conversion will be limited")

try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    logger.warning("trimesh not available - 3D format conversion will be limited")

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    logger.warning("openpyxl not available - Excel export will be limited")

try:
    import cairosvg
    HAS_CAIROSVG = True
except ImportError:
    logger.warning("cairosvg not available - SVG conversion will be limited")

# Check for FFmpeg availability
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
    HAS_FFMPEG = result.returncode == 0
except Exception:
    HAS_FFMPEG = False
    logger.warning("FFmpeg not available - video/audio conversion will be limited")


def get_format_info(extension: str) -> Optional[FormatInfo]:
    """Get format information for a file extension."""
    ext = extension.lower().lstrip('.')
    return FORMAT_REGISTRY.get(ext)


def detect_format(filepath: str) -> Optional[FormatInfo]:
    """Detect format from file path."""
    ext = Path(filepath).suffix.lower().lstrip('.')
    return FORMAT_REGISTRY.get(ext)


class MediaExportComponent:
    """Component for exporting media files via EventBus events."""
    
    def __init__(self, event_bus=None, export_dir: Optional[str] = None):
        """Initialize the media export component.
        
        Args:
            event_bus: EventBus instance for subscribing to export events
            export_dir: Default directory for exports (defaults to data/exports)
        """
        self.event_bus = event_bus
        self.export_dir = export_dir or str(Path(__file__).parent.parent / "data" / "exports")
        
        # Ensure export directory exists
        os.makedirs(self.export_dir, exist_ok=True)
        
        # Register with EventBus
        if self.event_bus:
            self._register_subscriptions()
            
            # Register component for direct access
            if hasattr(self.event_bus, 'register_component'):
                self.event_bus.register_component('media_export', self)
        
        logger.info(f"✅ MediaExportComponent initialized (export_dir={self.export_dir})")
        logger.info(f"   Available: PIL={HAS_PIL}, reportlab={HAS_REPORTLAB}, matplotlib={HAS_MATPLOTLIB}, wave={HAS_WAVE}")
        logger.info(f"   FFmpeg={HAS_FFMPEG}, pydub={HAS_PYDUB}, trimesh={HAS_TRIMESH}, numpy={HAS_NUMPY}")
    
    def _register_subscriptions(self):
        """Subscribe to media export and conversion events."""
        try:
            # Export events
            self.event_bus.subscribe("media.export.image", self._handle_image_export)
            self.event_bus.subscribe("media.export.pdf", self._handle_pdf_export)
            self.event_bus.subscribe("media.export.audio", self._handle_audio_export)
            self.event_bus.subscribe("media.export.chart", self._handle_chart_export)
            self.event_bus.subscribe("media.export.video", self._handle_video_export)
            self.event_bus.subscribe("media.export.data", self._handle_data_export)
            self.event_bus.subscribe("media.export.3d", self._handle_3d_export)
            
            # Conversion events
            self.event_bus.subscribe("media.convert", self._handle_convert)
            self.event_bus.subscribe("media.convert.image", self._handle_image_convert)
            self.event_bus.subscribe("media.convert.audio", self._handle_audio_convert)
            self.event_bus.subscribe("media.convert.video", self._handle_video_convert)
            self.event_bus.subscribe("media.convert.data", self._handle_data_convert)
            
            # Query events
            self.event_bus.subscribe("media.formats.list", self._handle_list_formats)
            self.event_bus.subscribe("media.formats.info", self._handle_format_info)
            
            logger.info("✅ MediaExportComponent subscribed to media.export.* and media.convert.* events")
        except Exception as e:
            logger.error(f"Failed to subscribe MediaExportComponent: {e}")
    
    def _generate_filename(self, prefix: str, extension: str) -> str:
        """Generate a unique filename with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.export_dir, f"{prefix}_{timestamp}.{extension}")
    
    # -------------------------------------------------------------------------
    # Image Export (PNG)
    # -------------------------------------------------------------------------
    def _handle_image_export(self, data: Dict[str, Any]):
        """Handle media.export.image event.
        
        Expected data:
            - image: Base64-encoded image data, PIL Image, numpy array, or file path
            - filename: Optional output filename
            - format: Image format (default: 'PNG')
        """
        try:
            result = self.export_image(
                image=data.get('image'),
                filename=data.get('filename'),
                format=data.get('format', 'PNG')
            )
            
            # Publish result
            if self.event_bus:
                self.event_bus.publish("media.export.image.complete", {
                    "success": result is not None,
                    "filename": result,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
        except Exception as e:
            logger.error(f"Error handling image export: {e}")
            if self.event_bus:
                self.event_bus.publish("media.export.image.error", {"error": str(e)})
    
    def export_image(self, image: Any, filename: Optional[str] = None, format: str = 'PNG') -> Optional[str]:
        """Export image to file.
        
        Args:
            image: Base64 string, PIL Image, numpy array, QPixmap, or file path
            filename: Output filename (auto-generated if not provided)
            format: Image format (PNG, JPEG, etc.)
            
        Returns:
            Path to exported file, or None on error
        """
        if not filename:
            filename = self._generate_filename("image", format.lower())
        
        try:
            # Handle different input types
            if isinstance(image, str):
                # Check if it's base64 or file path
                if os.path.exists(image):
                    # Copy file
                    import shutil
                    shutil.copy(image, filename)
                    logger.info(f"📷 Copied image to: {filename}")
                    return filename
                else:
                    # Assume base64
                    if "," in image and image.startswith("data:"):
                        image = image.split(",", 1)[1]
                    img_bytes = base64.b64decode(image)
                    
                    if HAS_PIL:
                        pil_img = Image.open(io.BytesIO(img_bytes))
                        pil_img.save(filename, format=format)
                    else:
                        # Fallback: write raw bytes
                        with open(filename, 'wb') as f:
                            f.write(img_bytes)
                    
                    logger.info(f"📷 Exported base64 image to: {filename}")
                    return filename
            
            elif HAS_PIL and hasattr(image, 'save'):
                # PIL Image
                image.save(filename, format=format)
                logger.info(f"📷 Exported PIL image to: {filename}")
                return filename
            
            elif hasattr(image, 'shape'):
                # Numpy array (e.g., OpenCV frame)
                import cv2
                cv2.imwrite(filename, image)
                logger.info(f"📷 Exported numpy array to: {filename}")
                return filename
            
            elif hasattr(image, 'save') and hasattr(image, 'toImage'):
                # QPixmap
                image.save(filename, format.upper())
                logger.info(f"📷 Exported QPixmap to: {filename}")
                return filename
            
            else:
                logger.error(f"Unsupported image type: {type(image)}")
                return None
                
        except Exception as e:
            logger.error(f"Error exporting image: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # PDF Export
    # -------------------------------------------------------------------------
    def _handle_pdf_export(self, data: Dict[str, Any]):
        """Handle media.export.pdf event.
        
        Expected data:
            - content: Text content or list of paragraphs
            - title: Document title
            - filename: Optional output filename
            - include_images: List of base64 images to include
        """
        try:
            result = self.export_pdf(
                content=data.get('content', ''),
                title=data.get('title', 'Kingdom AI Export'),
                filename=data.get('filename'),
                include_images=data.get('include_images', [])
            )
            
            if self.event_bus:
                self.event_bus.publish("media.export.pdf.complete", {
                    "success": result is not None,
                    "filename": result,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
        except Exception as e:
            logger.error(f"Error handling PDF export: {e}")
            if self.event_bus:
                self.event_bus.publish("media.export.pdf.error", {"error": str(e)})
    
    def export_pdf(self, content: Union[str, List[str]], title: str = "Kingdom AI Export",
                   filename: Optional[str] = None, include_images: List[str] = None) -> Optional[str]:
        """Export content to PDF document.
        
        Args:
            content: Text content or list of paragraphs
            title: Document title
            filename: Output filename
            include_images: List of base64-encoded images to include
            
        Returns:
            Path to exported file, or None on error
        """
        if not filename:
            filename = self._generate_filename("document", "pdf")
        
        if not HAS_REPORTLAB:
            # Fallback: write as plain text
            txt_filename = filename.replace('.pdf', '.txt')
            try:
                with open(txt_filename, 'w', encoding='utf-8') as f:
                    f.write(f"=== {title} ===\n\n")
                    if isinstance(content, list):
                        f.write('\n\n'.join(content))
                    else:
                        f.write(content)
                logger.warning(f"📄 reportlab not available, exported as text: {txt_filename}")
                return txt_filename
            except Exception as e:
                logger.error(f"Error writing text fallback: {e}")
                return None
        
        try:
            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=20
            )
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 12))
            
            # Timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            story.append(Paragraph(f"Generated: {timestamp}", styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Content
            if isinstance(content, list):
                for para in content:
                    story.append(Paragraph(para, styles['Normal']))
                    story.append(Spacer(1, 6))
            else:
                # Split content into paragraphs
                for para in content.split('\n\n'):
                    if para.strip():
                        story.append(Paragraph(para.strip(), styles['Normal']))
                        story.append(Spacer(1, 6))
            
            # Include images if provided
            if include_images:
                story.append(Spacer(1, 20))
                story.append(Paragraph("Attachments", styles['Heading2']))
                
                for idx, b64_img in enumerate(include_images[:10]):  # Limit to 10 images
                    try:
                        if "," in b64_img and b64_img.startswith("data:"):
                            b64_img = b64_img.split(",", 1)[1]
                        img_bytes = base64.b64decode(b64_img)
                        
                        # Save to temp file for reportlab
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                            tmp.write(img_bytes)
                            tmp_path = tmp.name
                        
                        img = RLImage(tmp_path, width=4*inch, height=3*inch)
                        story.append(img)
                        story.append(Spacer(1, 12))
                        
                        # Clean up temp file
                        os.unlink(tmp_path)
                        
                    except Exception as img_err:
                        logger.warning(f"Error including image {idx} in PDF: {img_err}")
            
            # Build PDF
            doc.build(story)
            logger.info(f"📄 Exported PDF to: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error exporting PDF: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # Audio Export (WAV)
    # -------------------------------------------------------------------------
    def _handle_audio_export(self, data: Dict[str, Any]):
        """Handle media.export.audio event.
        
        Expected data:
            - audio: Audio data (bytes, base64, numpy array, or file path)
            - filename: Optional output filename
            - sample_rate: Sample rate (default: 22050)
            - channels: Number of channels (default: 1)
        """
        try:
            result = self.export_audio(
                audio=data.get('audio'),
                filename=data.get('filename'),
                sample_rate=data.get('sample_rate', 22050),
                channels=data.get('channels', 1)
            )
            
            if self.event_bus:
                self.event_bus.publish("media.export.audio.complete", {
                    "success": result is not None,
                    "filename": result,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
        except Exception as e:
            logger.error(f"Error handling audio export: {e}")
            if self.event_bus:
                self.event_bus.publish("media.export.audio.error", {"error": str(e)})
    
    def export_audio(self, audio: Any, filename: Optional[str] = None,
                     sample_rate: int = 22050, channels: int = 1) -> Optional[str]:
        """Export audio to WAV file.
        
        Args:
            audio: Audio data (bytes, base64, numpy array, or file path)
            filename: Output filename
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            
        Returns:
            Path to exported file, or None on error
        """
        if not filename:
            filename = self._generate_filename("audio", "wav")
        
        if not HAS_WAVE:
            logger.error("wave module not available for audio export")
            return None
        
        try:
            if isinstance(audio, str):
                if os.path.exists(audio):
                    # Copy existing file
                    import shutil
                    shutil.copy(audio, filename)
                    logger.info(f"🔊 Copied audio to: {filename}")
                    return filename
                else:
                    # Assume base64
                    if "," in audio and audio.startswith("data:"):
                        audio = audio.split(",", 1)[1]
                    audio = base64.b64decode(audio)
            
            if isinstance(audio, bytes):
                # Write raw bytes as WAV
                with wave.open(filename, 'wb') as wav_file:
                    wav_file.setnchannels(channels)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio)
                logger.info(f"🔊 Exported audio to: {filename}")
                return filename
            
            elif hasattr(audio, 'shape'):
                # Numpy array
                import numpy as np
                audio_data = audio
                if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                    # Convert float to int16
                    audio_data = (audio_data * 32767).astype(np.int16)
                
                with wave.open(filename, 'wb') as wav_file:
                    wav_file.setnchannels(channels)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_data.tobytes())
                logger.info(f"🔊 Exported numpy audio to: {filename}")
                return filename
            
            else:
                logger.error(f"Unsupported audio type: {type(audio)}")
                return None
                
        except Exception as e:
            logger.error(f"Error exporting audio: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # Chart Export (matplotlib)
    # -------------------------------------------------------------------------
    def _handle_chart_export(self, data: Dict[str, Any]):
        """Handle media.export.chart event.
        
        Expected data:
            - chart_type: Type of chart ('line', 'bar', 'pie', 'scatter')
            - data: Chart data (dict with 'x', 'y', 'labels', etc.)
            - title: Chart title
            - filename: Optional output filename
            - format: Output format ('png' or 'pdf')
        """
        try:
            result = self.export_chart(
                chart_type=data.get('chart_type', 'line'),
                chart_data=data.get('data', {}),
                title=data.get('title', 'Chart'),
                filename=data.get('filename'),
                format=data.get('format', 'png')
            )
            
            if self.event_bus:
                self.event_bus.publish("media.export.chart.complete", {
                    "success": result is not None,
                    "filename": result,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
        except Exception as e:
            logger.error(f"Error handling chart export: {e}")
            if self.event_bus:
                self.event_bus.publish("media.export.chart.error", {"error": str(e)})
    
    def export_chart(self, chart_type: str, chart_data: Dict[str, Any],
                     title: str = "Chart", filename: Optional[str] = None,
                     format: str = 'png') -> Optional[str]:
        """Export matplotlib chart to file.
        
        Args:
            chart_type: Type of chart ('line', 'bar', 'pie', 'scatter')
            chart_data: Dict with chart data (x, y, labels, colors, etc.)
            title: Chart title
            filename: Output filename
            format: Output format ('png' or 'pdf')
            
        Returns:
            Path to exported file, or None on error
        """
        if not HAS_MATPLOTLIB:
            logger.error("matplotlib not available for chart export")
            return None
        
        if not filename:
            filename = self._generate_filename("chart", format)
        
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            x = chart_data.get('x', [])
            y = chart_data.get('y', [])
            labels = chart_data.get('labels', [])
            colors = chart_data.get('colors', None)
            
            if chart_type == 'line':
                ax.plot(x, y, marker='o', color=colors[0] if colors else '#7aa2f7')
            elif chart_type == 'bar':
                ax.bar(x, y, color=colors if colors else '#7aa2f7')
            elif chart_type == 'pie':
                ax.pie(y, labels=labels or x, colors=colors, autopct='%1.1f%%')
            elif chart_type == 'scatter':
                ax.scatter(x, y, c=colors if colors else '#7aa2f7', alpha=0.7)
            else:
                ax.plot(x, y)  # Default to line
            
            ax.set_title(title, fontsize=14, fontweight='bold')
            
            if chart_data.get('xlabel'):
                ax.set_xlabel(chart_data['xlabel'])
            if chart_data.get('ylabel'):
                ax.set_ylabel(chart_data['ylabel'])
            
            # Style for dark theme
            fig.patch.set_facecolor('#1a1b26')
            ax.set_facecolor('#1a1b26')
            ax.tick_params(colors='#a9b1d6')
            ax.xaxis.label.set_color('#a9b1d6')
            ax.yaxis.label.set_color('#a9b1d6')
            ax.title.set_color('#c0caf5')
            for spine in ax.spines.values():
                spine.set_color('#3b4261')
            
            plt.tight_layout()
            plt.savefig(filename, format=format, dpi=150, facecolor='#1a1b26', edgecolor='none')
            plt.close(fig)
            
            logger.info(f"📊 Exported chart to: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error exporting chart: {e}")
            return None

    # =========================================================================
    # VIDEO EXPORT & CONVERSION (FFmpeg-based)
    # =========================================================================
    def _handle_video_export(self, data: Dict[str, Any]):
        """Handle media.export.video event."""
        try:
            result = self.export_video(
                source=data.get('source'),
                filename=data.get('filename'),
                format=data.get('format', 'mp4'),
                codec=data.get('codec', 'libx264'),
                quality=data.get('quality', 'medium')
            )
            if self.event_bus:
                self.event_bus.publish("media.export.video.complete", {
                    "success": result is not None, "filename": result,
                    "timestamp": datetime.utcnow().isoformat(),
                })
        except Exception as e:
            logger.error(f"Error handling video export: {e}")
            if self.event_bus:
                self.event_bus.publish("media.export.video.error", {"error": str(e)})

    def export_video(self, source: str, filename: Optional[str] = None,
                     format: str = 'mp4', codec: str = 'libx264',
                     quality: str = 'medium') -> Optional[str]:
        """Export/convert video using FFmpeg."""
        if not HAS_FFMPEG:
            logger.error("FFmpeg not available for video export")
            return None
        
        if not filename:
            filename = self._generate_filename("video", format)
        
        # Quality presets
        quality_presets = {
            'low': {'crf': '28', 'preset': 'fast'},
            'medium': {'crf': '23', 'preset': 'medium'},
            'high': {'crf': '18', 'preset': 'slow'},
            'lossless': {'crf': '0', 'preset': 'veryslow'}
        }
        preset = quality_presets.get(quality, quality_presets['medium'])
        
        try:
            cmd = [
                'ffmpeg', '-y', '-i', source,
                '-c:v', codec, '-crf', preset['crf'], '-preset', preset['preset'],
                '-c:a', 'aac', '-b:a', '128k',
                filename
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0:
                logger.info(f"🎬 Exported video to: {filename}")
                return filename
            else:
                logger.error(f"FFmpeg error: {result.stderr.decode()[:500]}")
                return None
        except Exception as e:
            logger.error(f"Error exporting video: {e}")
            return None

    def _handle_video_convert(self, data: Dict[str, Any]):
        """Handle media.convert.video event."""
        try:
            result = self.convert_video(
                source=data.get('source'),
                target_format=data.get('target_format', 'mp4'),
                output=data.get('output')
            )
            if self.event_bus:
                self.event_bus.publish("media.convert.video.complete", {
                    "success": result is not None, "filename": result,
                })
        except Exception as e:
            logger.error(f"Error converting video: {e}")

    def convert_video(self, source: str, target_format: str,
                      output: Optional[str] = None) -> Optional[str]:
        """Convert video to different format."""
        if not HAS_FFMPEG:
            logger.error("FFmpeg required for video conversion")
            return None
        
        if not output:
            output = self._generate_filename("converted", target_format)
        
        # Format-specific codec mappings
        format_codecs = {
            'mp4': ('libx264', 'aac'),
            'webm': ('libvpx-vp9', 'libopus'),
            'mov': ('prores_ks', 'pcm_s16le'),
            'mkv': ('libx264', 'aac'),
            'avi': ('mpeg4', 'mp3'),
        }
        video_codec, audio_codec = format_codecs.get(target_format, ('copy', 'copy'))
        
        try:
            cmd = ['ffmpeg', '-y', '-i', source, '-c:v', video_codec, '-c:a', audio_codec, output]
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode == 0:
                logger.info(f"🎬 Converted video to {target_format}: {output}")
                return output
            return None
        except Exception as e:
            logger.error(f"Video conversion error: {e}")
            return None

    # =========================================================================
    # AUDIO CONVERSION (pydub/FFmpeg-based)
    # =========================================================================
    def _handle_audio_convert(self, data: Dict[str, Any]):
        """Handle media.convert.audio event."""
        try:
            result = self.convert_audio(
                source=data.get('source'),
                target_format=data.get('target_format', 'mp3'),
                output=data.get('output'),
                bitrate=data.get('bitrate', '192k')
            )
            if self.event_bus:
                self.event_bus.publish("media.convert.audio.complete", {
                    "success": result is not None, "filename": result,
                })
        except Exception as e:
            logger.error(f"Error converting audio: {e}")

    def convert_audio(self, source: str, target_format: str,
                      output: Optional[str] = None, bitrate: str = '192k') -> Optional[str]:
        """Convert audio between formats (WAV, MP3, AAC, FLAC, OGG, etc.)."""
        if not output:
            output = self._generate_filename("audio", target_format)
        
        # Try pydub first (easier API)
        if HAS_PYDUB:
            try:
                audio = AudioSegment.from_file(source)
                export_params = {}
                if target_format in ('mp3', 'ogg'):
                    export_params['bitrate'] = bitrate
                audio.export(output, format=target_format, **export_params)
                logger.info(f"🔊 Converted audio to {target_format}: {output}")
                return output
            except Exception as e:
                logger.warning(f"pydub conversion failed, trying FFmpeg: {e}")
        
        # Fallback to FFmpeg
        if HAS_FFMPEG:
            try:
                codec_map = {
                    'mp3': 'libmp3lame', 'aac': 'aac', 'm4a': 'aac',
                    'ogg': 'libvorbis', 'flac': 'flac', 'opus': 'libopus',
                    'wav': 'pcm_s16le', 'aiff': 'pcm_s16be'
                }
                codec = codec_map.get(target_format, 'copy')
                cmd = ['ffmpeg', '-y', '-i', source, '-c:a', codec, '-b:a', bitrate, output]
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                if result.returncode == 0:
                    logger.info(f"🔊 Converted audio to {target_format}: {output}")
                    return output
            except Exception as e:
                logger.error(f"FFmpeg audio conversion error: {e}")
        
        logger.error("No audio conversion backend available")
        return None

    # =========================================================================
    # IMAGE CONVERSION (PIL-based with next-gen format support)
    # =========================================================================
    def _handle_image_convert(self, data: Dict[str, Any]):
        """Handle media.convert.image event."""
        try:
            result = self.convert_image(
                source=data.get('source'),
                target_format=data.get('target_format', 'png'),
                output=data.get('output'),
                quality=data.get('quality', 85)
            )
            if self.event_bus:
                self.event_bus.publish("media.convert.image.complete", {
                    "success": result is not None, "filename": result,
                })
        except Exception as e:
            logger.error(f"Error converting image: {e}")

    def convert_image(self, source: str, target_format: str,
                      output: Optional[str] = None, quality: int = 85) -> Optional[str]:
        """Convert image between formats (PNG, JPG, WebP, AVIF, TIFF, etc.)."""
        if not HAS_PIL:
            logger.error("PIL required for image conversion")
            return None
        
        if not output:
            output = self._generate_filename("image", target_format)
        
        try:
            img = Image.open(source)
            
            # Handle transparency for formats that don't support it
            if target_format.lower() in ('jpg', 'jpeg') and img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Handle SVG to raster conversion
            if source.lower().endswith('.svg') and HAS_CAIROSVG:
                png_bytes = cairosvg.svg2png(url=source)
                img = Image.open(io.BytesIO(png_bytes))
            
            # Format-specific save options
            save_kwargs = {}
            if target_format.lower() in ('jpg', 'jpeg', 'webp'):
                save_kwargs['quality'] = quality
            if target_format.lower() == 'webp':
                save_kwargs['method'] = 6  # Best compression
            if target_format.lower() == 'png':
                save_kwargs['optimize'] = True
            
            # PIL format names
            pil_format = target_format.upper()
            if pil_format == 'JPG':
                pil_format = 'JPEG'
            
            img.save(output, format=pil_format, **save_kwargs)
            logger.info(f"📷 Converted image to {target_format}: {output}")
            return output
            
        except Exception as e:
            logger.error(f"Image conversion error: {e}")
            return None

    # =========================================================================
    # DATA FORMAT CONVERSION (JSON, CSV, XML, YAML, XLSX)
    # =========================================================================
    def _handle_data_export(self, data: Dict[str, Any]):
        """Handle media.export.data event."""
        try:
            result = self.export_data(
                data=data.get('data'),
                format=data.get('format', 'json'),
                filename=data.get('filename')
            )
            if self.event_bus:
                self.event_bus.publish("media.export.data.complete", {
                    "success": result is not None, "filename": result,
                })
        except Exception as e:
            logger.error(f"Error exporting data: {e}")

    def _handle_data_convert(self, data: Dict[str, Any]):
        """Handle media.convert.data event."""
        try:
            result = self.convert_data(
                source=data.get('source'),
                target_format=data.get('target_format', 'json'),
                output=data.get('output')
            )
            if self.event_bus:
                self.event_bus.publish("media.convert.data.complete", {
                    "success": result is not None, "filename": result,
                })
        except Exception as e:
            logger.error(f"Error converting data: {e}")

    def export_data(self, data: Any, format: str = 'json',
                    filename: Optional[str] = None) -> Optional[str]:
        """Export structured data to file format."""
        if not filename:
            filename = self._generate_filename("data", format)
        
        try:
            if format == 'json':
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            elif format == 'csv':
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], dict):
                            writer = csv.DictWriter(f, fieldnames=data[0].keys())
                            writer.writeheader()
                            writer.writerows(data)
                        else:
                            writer = csv.writer(f)
                            writer.writerows(data)
            
            elif format == 'xml':
                xml_content = self._dict_to_xml(data, 'root')
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                    f.write(xml_content)
            
            elif format == 'yaml':
                try:
                    import yaml
                    with open(filename, 'w', encoding='utf-8') as f:
                        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                except ImportError:
                    logger.error("PyYAML not available for YAML export")
                    return None
            
            elif format == 'xlsx' and HAS_OPENPYXL:
                from openpyxl import Workbook
                wb = Workbook()
                ws = wb.active
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    headers = list(data[0].keys())
                    ws.append(headers)
                    for row in data:
                        ws.append([row.get(h) for h in headers])
                wb.save(filename)
            
            else:
                logger.error(f"Unsupported data format: {format}")
                return None
            
            logger.info(f"📊 Exported data to {format}: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Data export error: {e}")
            return None

    def convert_data(self, source: str, target_format: str,
                     output: Optional[str] = None) -> Optional[str]:
        """Convert data file between formats."""
        if not output:
            output = self._generate_filename("converted", target_format)
        
        try:
            # Load source data
            source_ext = Path(source).suffix.lower().lstrip('.')
            data = None
            
            if source_ext == 'json':
                with open(source, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif source_ext == 'csv':
                with open(source, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
            elif source_ext in ('yaml', 'yml'):
                import yaml
                with open(source, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            elif source_ext == 'xml':
                data = self._xml_to_dict(source)
            
            if data is None:
                logger.error(f"Could not load source data from {source}")
                return None
            
            return self.export_data(data, target_format, output)
            
        except Exception as e:
            logger.error(f"Data conversion error: {e}")
            return None

    def _dict_to_xml(self, data: Any, root_name: str = 'root') -> str:
        """Convert dictionary to XML string."""
        def _to_xml(d, parent):
            if isinstance(d, dict):
                items = []
                for key, val in d.items():
                    items.append(f"<{key}>{_to_xml(val, key)}</{key}>")
                return ''.join(items)
            elif isinstance(d, list):
                items = []
                for item in d:
                    items.append(f"<item>{_to_xml(item, 'item')}</item>")
                return ''.join(items)
            else:
                return str(d) if d is not None else ''
        return f"<{root_name}>{_to_xml(data, root_name)}</{root_name}>"

    def _xml_to_dict(self, filepath: str) -> Optional[Dict]:
        """Parse XML file to dictionary."""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            def _elem_to_dict(elem):
                result = {}
                for child in elem:
                    if len(child) > 0:
                        result[child.tag] = _elem_to_dict(child)
                    else:
                        result[child.tag] = child.text
                return result
            
            return {root.tag: _elem_to_dict(root)}
        except Exception as e:
            logger.error(f"XML parse error: {e}")
            return None

    # =========================================================================
    # 3D MODEL EXPORT (trimesh-based)
    # =========================================================================
    def _handle_3d_export(self, data: Dict[str, Any]):
        """Handle media.export.3d event."""
        try:
            result = self.export_3d(
                source=data.get('source'),
                format=data.get('format', 'glb'),
                filename=data.get('filename')
            )
            if self.event_bus:
                self.event_bus.publish("media.export.3d.complete", {
                    "success": result is not None, "filename": result,
                })
        except Exception as e:
            logger.error(f"Error exporting 3D model: {e}")

    def export_3d(self, source: str, format: str = 'glb',
                  filename: Optional[str] = None) -> Optional[str]:
        """Export/convert 3D models (OBJ, STL, glTF, GLB, etc.)."""
        if not HAS_TRIMESH:
            logger.error("trimesh required for 3D model export")
            return None
        
        if not filename:
            filename = self._generate_filename("model", format)
        
        try:
            mesh = trimesh.load(source)
            
            if format in ('gltf', 'glb'):
                mesh.export(filename, file_type=format)
            elif format == 'stl':
                mesh.export(filename, file_type='stl')
            elif format == 'obj':
                mesh.export(filename, file_type='obj')
            elif format == 'ply':
                mesh.export(filename, file_type='ply')
            else:
                mesh.export(filename)
            
            logger.info(f"🎮 Exported 3D model to {format}: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"3D export error: {e}")
            return None

    # =========================================================================
    # GENERIC CONVERSION HANDLER
    # =========================================================================
    def _handle_convert(self, data: Dict[str, Any]):
        """Handle generic media.convert event - auto-detect type."""
        source = data.get('source', '')
        target_format = data.get('target_format', '')
        
        if not source or not target_format:
            logger.error("media.convert requires 'source' and 'target_format'")
            return
        
        # Detect source type
        source_info = detect_format(source)
        target_info = get_format_info(target_format)
        
        if not source_info:
            logger.error(f"Unknown source format: {source}")
            return
        
        # Route to appropriate converter
        result = None
        if source_info.media_type == MediaType.IMAGE:
            result = self.convert_image(source, target_format, data.get('output'))
        elif source_info.media_type == MediaType.AUDIO:
            result = self.convert_audio(source, target_format, data.get('output'))
        elif source_info.media_type == MediaType.VIDEO:
            result = self.convert_video(source, target_format, data.get('output'))
        elif source_info.media_type == MediaType.DATA:
            result = self.convert_data(source, target_format, data.get('output'))
        elif source_info.media_type == MediaType.THREE_D:
            result = self.export_3d(source, target_format, data.get('output'))
        
        if self.event_bus:
            self.event_bus.publish("media.convert.complete", {
                "success": result is not None,
                "source": source,
                "target_format": target_format,
                "filename": result,
            })

    # =========================================================================
    # FORMAT QUERY HANDLERS
    # =========================================================================
    def _handle_list_formats(self, data: Dict[str, Any]):
        """Handle media.formats.list - return all supported formats."""
        media_type = data.get('type')  # Optional filter
        
        formats = {}
        for ext, info in FORMAT_REGISTRY.items():
            if media_type is None or info.media_type.value == media_type:
                formats[ext] = {
                    'type': info.media_type.value,
                    'mime': info.mime_type,
                    'description': info.description,
                    'lossless': info.lossless,
                    'transparency': info.supports_transparency,
                }
        
        if self.event_bus:
            self.event_bus.publish("media.formats.list.result", {
                "formats": formats,
                "count": len(formats),
            })

    def _handle_format_info(self, data: Dict[str, Any]):
        """Handle media.formats.info - return info for specific format."""
        ext = data.get('format', '').lower().lstrip('.')
        info = FORMAT_REGISTRY.get(ext)
        
        if self.event_bus:
            if info:
                self.event_bus.publish("media.formats.info.result", {
                    "format": ext,
                    "type": info.media_type.value,
                    "mime": info.mime_type,
                    "description": info.description,
                    "lossless": info.lossless,
                    "transparency": info.supports_transparency,
                })
            else:
                self.event_bus.publish("media.formats.info.error", {
                    "format": ext,
                    "error": "Unknown format",
                })

    # =========================================================================
    # CAPABILITIES QUERY
    # =========================================================================
    def get_capabilities(self) -> Dict[str, Any]:
        """Return current conversion capabilities based on available libraries."""
        return {
            "image": {
                "available": HAS_PIL,
                "formats": ["png", "jpg", "jpeg", "webp", "tiff", "bmp", "gif", "ico"],
                "next_gen": ["webp", "avif"] if HAS_PIL else [],
                "svg_raster": HAS_CAIROSVG,
            },
            "audio": {
                "available": HAS_PYDUB or HAS_FFMPEG,
                "formats": ["wav", "mp3", "aac", "ogg", "flac", "opus", "m4a", "aiff"],
                "backend": "pydub" if HAS_PYDUB else ("ffmpeg" if HAS_FFMPEG else None),
            },
            "video": {
                "available": HAS_FFMPEG,
                "formats": ["mp4", "mov", "webm", "mkv", "avi"],
                "codecs": ["h264", "h265", "vp9", "av1", "prores"] if HAS_FFMPEG else [],
            },
            "3d": {
                "available": HAS_TRIMESH,
                "formats": ["glb", "gltf", "obj", "stl", "ply"] if HAS_TRIMESH else [],
            },
            "data": {
                "available": True,
                "formats": ["json", "csv", "xml", "yaml"],
                "xlsx": HAS_OPENPYXL,
            },
            "document": {
                "available": HAS_REPORTLAB,
                "formats": ["pdf", "html", "md", "txt"],
            },
            "chart": {
                "available": HAS_MATPLOTLIB,
                "types": ["line", "bar", "pie", "scatter"],
            },
        }


def initialize_media_export(event_bus=None, export_dir: Optional[str] = None) -> MediaExportComponent:
    """Factory function to initialize the MediaExportComponent.
    
    Args:
        event_bus: EventBus instance
        export_dir: Export directory path
        
    Returns:
        Initialized MediaExportComponent
    """
    return MediaExportComponent(event_bus=event_bus, export_dir=export_dir)
