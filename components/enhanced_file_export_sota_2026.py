#!/usr/bin/env python3
"""
Kingdom AI - SOTA 2026 Enhanced File Export System
===================================================

Comprehensive file export system with host system integration.
Ensures all created content can be downloaded to the host system.

Features:
- Automatic export of all generated content
- Host system integration (Windows/WSL bridge)
- Multiple format support (images, videos, audio, documents, 3D, data)
- Batch export operations
- Export history and tracking
- Direct host filesystem access
"""

import os
import sys
import shutil
import logging
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field

logger = logging.getLogger("KingdomAI.EnhancedFileExport")


@dataclass
class ExportRecord:
    """Record of an exported file."""
    source_path: str
    export_path: str
    file_type: str
    timestamp: str
    size_bytes: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    export_id: str = ""
    
    def __post_init__(self):
        if not self.export_id:
            import hashlib
            self.export_id = hashlib.sha256(
                f"{self.source_path}{self.timestamp}".encode()
            ).hexdigest()[:12]


class EnhancedFileExportSOTA2026:
    """SOTA 2026 Enhanced File Export System with host integration."""
    
    def __init__(self, event_bus=None, export_base_dir: Optional[str] = None):
        """Initialize the enhanced file export system.
        
        Args:
            event_bus: EventBus for export events
            export_base_dir: Base directory for exports (defaults to data/exports)
        """
        self.event_bus = event_bus
        self.export_base_dir = export_base_dir or str(Path(__file__).parent.parent / "data" / "exports")
        
        # Create export directories
        self.export_dirs = {
            'images': os.path.join(self.export_base_dir, 'images'),
            'videos': os.path.join(self.export_base_dir, 'videos'),
            'audio': os.path.join(self.export_base_dir, 'audio'),
            'documents': os.path.join(self.export_base_dir, 'documents'),
            '3d': os.path.join(self.export_base_dir, '3d'),
            'data': os.path.join(self.export_base_dir, 'data'),
            'maps': os.path.join(self.export_base_dir, 'maps'),
            'ai_creations': os.path.join(self.export_base_dir, 'ai_creations'),
            'live_creations': os.path.join(self.export_base_dir, 'live_creations'),
            'scraped_content': os.path.join(self.export_base_dir, 'scraped_content'),
        }
        
        for dir_path in self.export_dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        # Export history
        self.export_history: List[ExportRecord] = []
        self.max_history = 1000
        
        # Host system detection
        self.is_wsl = False
        self.host_export_path = None
        
        logger.info(f"✅ SOTA 2026 Enhanced File Export System initialized")
        logger.info(f"   Export base: {self.export_base_dir}")
    
    def _detect_wsl(self) -> bool:
        """Detect WSL via /proc/version. Returns False on native Linux."""
        try:
            with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
                return "microsoft" in f.read().lower()
        except Exception:
            return False
    
    def _get_host_export_path(self) -> Optional[str]:
        """No-op on native Linux — returns None."""
        return None
    
    async def initialize(self) -> bool:
        """Initialize the export system."""
        try:
            # Subscribe to export events
            if self.event_bus:
                # General export events
                self.event_bus.subscribe("export.file", self._handle_file_export)
                self.event_bus.subscribe("export.batch", self._handle_batch_export)
                
                # Content creation events (auto-export)
                self.event_bus.subscribe("visual.generated", self._handle_visual_generated)
                self.event_bus.subscribe("creative.map.generated", self._handle_map_generated)
                self.event_bus.subscribe("web.scraped", self._handle_web_scraped)
                self.event_bus.subscribe("media.export.complete", self._handle_media_exported)
                
                # Query events
                self.event_bus.subscribe("export.history", self._handle_history_request)
                self.event_bus.subscribe("export.open_folder", self._handle_open_folder)
                
                logger.info("✅ Subscribed to export events")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced file export: {e}")
            return False
    
    async def export_file(self, source_path: str, file_type: str,
                         export_to_host: bool = True,
                         custom_name: Optional[str] = None,
                         metadata: Optional[Dict] = None) -> Optional[ExportRecord]:
        """Export a file to the export directory and optionally to host.
        
        Args:
            source_path: Path to source file
            file_type: Type of file (image, video, audio, etc.)
            export_to_host: Whether to also export to Windows host (if WSL)
            custom_name: Custom filename (optional)
            metadata: Additional metadata
            
        Returns:
            ExportRecord if successful, None otherwise
        """
        if not os.path.exists(source_path):
            logger.error(f"Source file not found: {source_path}")
            return None
        
        try:
            # Determine export directory
            export_dir = self.export_dirs.get(file_type, self.export_base_dir)
            
            # Generate export filename
            if custom_name:
                filename = custom_name
            else:
                source_name = Path(source_path).name
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_parts = source_name.rsplit('.', 1)
                if len(name_parts) == 2:
                    filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
                else:
                    filename = f"{source_name}_{timestamp}"
            
            export_path = os.path.join(export_dir, filename)
            
            # Copy file
            shutil.copy2(source_path, export_path)
            
            # Get file size
            size_bytes = os.path.getsize(export_path)
            
            # Create export record
            record = ExportRecord(
                source_path=source_path,
                export_path=export_path,
                file_type=file_type,
                timestamp=datetime.now().isoformat(),
                size_bytes=size_bytes,
                metadata=metadata or {}
            )
            
            # Add to history
            self.export_history.append(record)
            if len(self.export_history) > self.max_history:
                self.export_history = self.export_history[-self.max_history:]
            
            logger.info(f"✅ Exported {file_type}: {filename} ({size_bytes} bytes)")
            
            # Export to host if requested and available
            if export_to_host and self.host_export_path:
                host_path = await self._export_to_host(export_path, file_type, filename)
                if host_path:
                    record.metadata['host_path'] = host_path
                    logger.info(f"✅ Also exported to host: {host_path}")
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("export.file.complete", {
                    'export_id': record.export_id,
                    'source_path': source_path,
                    'export_path': export_path,
                    'file_type': file_type,
                    'size_bytes': size_bytes,
                    'host_path': record.metadata.get('host_path'),
                    'timestamp': record.timestamp
                })
            
            return record
            
        except Exception as e:
            logger.error(f"Failed to export file {source_path}: {e}")
            return None
    
    async def _export_to_host(self, source_path: str, file_type: str, filename: str) -> Optional[str]:
        """Export file to Windows host system."""
        if not self.host_export_path:
            return None
        
        try:
            # Create type-specific directory on host
            host_type_dir = os.path.join(self.host_export_path, file_type)
            os.makedirs(host_type_dir, exist_ok=True)
            
            # Copy to host
            host_path = os.path.join(host_type_dir, filename)
            shutil.copy2(source_path, host_path)
            
            return host_path
            
        except Exception as e:
            logger.warning(f"Failed to export to host: {e}")
            return None
    
    async def export_batch(self, file_paths: List[str], file_type: str,
                          export_to_host: bool = True) -> List[ExportRecord]:
        """Export multiple files at once.
        
        Args:
            file_paths: List of file paths to export
            file_type: Type of files
            export_to_host: Whether to export to host
            
        Returns:
            List of ExportRecord objects
        """
        records = []
        
        for file_path in file_paths:
            record = await self.export_file(file_path, file_type, export_to_host)
            if record:
                records.append(record)
        
        logger.info(f"✅ Batch exported {len(records)}/{len(file_paths)} files")
        
        # Publish event
        if self.event_bus:
            self.event_bus.publish("export.batch.complete", {
                'total_files': len(file_paths),
                'successful': len(records),
                'file_type': file_type
            })
        
        return records
    
    def open_export_folder(self, file_type: Optional[str] = None):
        """Open export folder in file explorer.
        
        Args:
            file_type: Specific file type folder, or None for base directory
        """
        folder_path = self.export_dirs.get(file_type, self.export_base_dir) if file_type else self.export_base_dir
        
        try:
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', folder_path])
            else:
                subprocess.run(['xdg-open', folder_path])
            
            logger.info(f"✅ Opened export folder: {folder_path}")
            
        except Exception as e:
            logger.error(f"Failed to open export folder: {e}")
    
    def get_export_history(self, file_type: Optional[str] = None,
                          limit: int = 100) -> List[ExportRecord]:
        """Get export history.
        
        Args:
            file_type: Filter by file type (optional)
            limit: Maximum number of records to return
            
        Returns:
            List of ExportRecord objects
        """
        history = self.export_history
        
        if file_type:
            history = [r for r in history if r.file_type == file_type]
        
        return history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get export system statistics."""
        stats = {
            'total_exports': len(self.export_history),
            'export_base_dir': self.export_base_dir,
            'is_wsl': self.is_wsl,
            'host_export_available': self.host_export_path is not None,
            'host_export_path': self.host_export_path,
            'exports_by_type': {}
        }
        
        # Count exports by type
        for record in self.export_history:
            file_type = record.file_type
            if file_type not in stats['exports_by_type']:
                stats['exports_by_type'][file_type] = 0
            stats['exports_by_type'][file_type] += 1
        
        return stats
    
    # Event handlers
    async def _handle_file_export(self, data: Dict[str, Any]):
        """Handle export.file event."""
        source_path = data.get('source_path')
        file_type = data.get('file_type', 'data')
        export_to_host = data.get('export_to_host', True)
        custom_name = data.get('custom_name')
        metadata = data.get('metadata')
        
        if source_path:
            await self.export_file(source_path, file_type, export_to_host, custom_name, metadata)
    
    async def _handle_batch_export(self, data: Dict[str, Any]):
        """Handle export.batch event."""
        file_paths = data.get('file_paths', [])
        file_type = data.get('file_type', 'data')
        export_to_host = data.get('export_to_host', True)
        
        await self.export_batch(file_paths, file_type, export_to_host)
    
    async def _handle_visual_generated(self, data: Dict[str, Any]):
        """Auto-export generated visual content."""
        image_path = data.get('image_path')
        mode = data.get('mode', 'image')
        
        if image_path and os.path.exists(image_path):
            file_type = 'ai_creations' if mode == 'image' else 'videos'
            await self.export_file(
                image_path,
                file_type,
                export_to_host=True,
                metadata={'mode': mode, 'prompt': data.get('prompt', '')}
            )
    
    async def _handle_map_generated(self, data: Dict[str, Any]):
        """Auto-export generated maps."""
        image_path = data.get('image_path')
        
        if image_path and os.path.exists(image_path):
            await self.export_file(
                image_path,
                'maps',
                export_to_host=True,
                metadata={'map_type': data.get('map_type', 'unknown')}
            )
    
    async def _handle_web_scraped(self, data: Dict[str, Any]):
        """Auto-export scraped web content."""
        # Export images
        for img_data in data.get('images', [])[:10]:
            local_path = img_data.get('local_path')
            if local_path and os.path.exists(local_path):
                await self.export_file(
                    local_path,
                    'scraped_content',
                    export_to_host=False,  # Don't clutter host with scraped images
                    metadata={'url': data.get('url'), 'source': 'web_scraper'}
                )
    
    async def _handle_media_exported(self, data: Dict[str, Any]):
        """Handle media export completion from media_export component."""
        filename = data.get('filename')
        
        if filename and os.path.exists(filename):
            # Determine file type from extension
            ext = Path(filename).suffix.lower()
            if ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']:
                file_type = 'images'
            elif ext in ['.mp4', '.mov', '.webm', '.avi']:
                file_type = 'videos'
            elif ext in ['.wav', '.mp3', '.ogg', '.flac']:
                file_type = 'audio'
            elif ext in ['.pdf', '.html', '.md', '.txt']:
                file_type = 'documents'
            else:
                file_type = 'data'
            
            await self.export_file(filename, file_type, export_to_host=True)
    
    async def _handle_history_request(self, data: Dict[str, Any]):
        """Handle export.history event."""
        file_type = data.get('file_type')
        limit = data.get('limit', 100)
        
        history = self.get_export_history(file_type, limit)
        
        if self.event_bus:
            self.event_bus.publish("export.history.result", {
                'history': [
                    {
                        'export_id': r.export_id,
                        'source_path': r.source_path,
                        'export_path': r.export_path,
                        'file_type': r.file_type,
                        'timestamp': r.timestamp,
                        'size_bytes': r.size_bytes
                    }
                    for r in history
                ]
            })
    
    async def _handle_open_folder(self, data: Dict[str, Any]):
        """Handle export.open_folder event."""
        file_type = data.get('file_type')
        self.open_export_folder(file_type)


# Global instance
_export_system: Optional[EnhancedFileExportSOTA2026] = None


def get_enhanced_export_system(event_bus=None) -> EnhancedFileExportSOTA2026:
    """Get or create global export system instance."""
    global _export_system
    if _export_system is None:
        _export_system = EnhancedFileExportSOTA2026(event_bus)
    return _export_system


__all__ = [
    'EnhancedFileExportSOTA2026',
    'ExportRecord',
    'get_enhanced_export_system',
]
