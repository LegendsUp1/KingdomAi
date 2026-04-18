#!/usr/bin/env python3
"""
Kingdom AI - VR SOTA 2026 Integration
======================================

Integrates all SOTA 2026 systems with the VR system for immersive experiences:
- Visual creation in VR (real-time image/video generation)
- Web scraping visualization in VR
- Knowledge graph exploration in 3D VR space
- File export from VR creations
- Ollama brain integration for VR interactions

Features:
- Real-time visual generation in VR headset
- 3D knowledge graph visualization
- VR-based web content exploration
- Gesture-based creation controls
- Voice commands in VR
- Export VR screenshots and recordings
"""

import os
import logging
import asyncio
import json
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("KingdomAI.VRSOTAIntegration")


class VRSOTAIntegration:
    """Integration layer for VR system with all SOTA 2026 enhancements."""
    
    def __init__(self, event_bus=None, vr_system=None):
        """Initialize VR SOTA 2026 integration.
        
        Args:
            event_bus: EventBus instance
            vr_system: VRSystem instance
        """
        self.event_bus = event_bus
        self.vr_system = vr_system
        
        # Component references (will be set during initialization)
        self.visual_creation = None
        self.ollama_learning = None
        self.enhanced_learning = None
        self.multimodal_scraper = None
        self.enhanced_export = None
        
        # VR-specific state
        self.vr_mode = "standard"  # standard, creation, exploration, learning
        self.current_visualization = None
        self.gesture_history = []
        self.voice_commands_enabled = True
        
        # Creation state
        self.active_creation = None
        self.creation_preview_enabled = True
        
        logger.info("🥽 VR SOTA 2026 Integration layer created")
    
    async def initialize(self) -> bool:
        """Initialize VR integration with all SOTA 2026 systems."""
        try:
            logger.info("🥽 Initializing VR SOTA 2026 integration...")
            
            # Get component references
            await self._get_component_references()
            
            # Subscribe to VR events
            await self._subscribe_vr_events()
            
            # Subscribe to creation events for VR preview
            await self._subscribe_creation_events()
            
            # Subscribe to learning events for VR visualization
            await self._subscribe_learning_events()
            
            # Setup VR-specific event handlers
            await self._setup_vr_handlers()
            
            logger.info("✅ VR SOTA 2026 integration initialized")
            
            # Publish initialization event
            if self.event_bus:
                self.event_bus.publish("vr.sota_2026.initialized", {
                    'visual_creation': self.visual_creation is not None,
                    'ollama_learning': self.ollama_learning is not None,
                    'enhanced_learning': self.enhanced_learning is not None,
                    'multimodal_scraper': self.multimodal_scraper is not None,
                    'enhanced_export': self.enhanced_export is not None,
                    'timestamp': datetime.now().isoformat()
                })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize VR SOTA 2026 integration: {e}")
            return False
    
    async def _get_component_references(self):
        """Get references to all SOTA 2026 components."""
        try:
            # Visual Creation Canvas
            try:
                from gui.widgets.visual_creation_canvas import VisualCreationCanvas
                # Will be set by GUI when canvas is created
                logger.info("   Visual Creation Canvas available")
            except ImportError:
                logger.warning("   Visual Creation Canvas not available")
            
            # Ollama Learning
            try:
                from core.ollama_learning_integration import get_learning_system
                self.ollama_learning = get_learning_system(self.event_bus)
                logger.info("   ✅ Ollama Learning System connected")
            except Exception as e:
                logger.warning(f"   Ollama Learning not available: {e}")
            
            # Enhanced Learning
            try:
                from core.enhanced_learning_system_sota_2026 import get_enhanced_learning_system
                self.enhanced_learning = get_enhanced_learning_system(self.event_bus, self.ollama_learning)
                logger.info("   ✅ Enhanced Learning System connected")
            except Exception as e:
                logger.warning(f"   Enhanced Learning not available: {e}")
            
            # Multimodal Scraper
            try:
                from core.multimodal_web_scraper_sota_2026 import get_multimodal_scraper
                self.multimodal_scraper = get_multimodal_scraper(self.event_bus, self.ollama_learning)
                logger.info("   ✅ Multimodal Scraper connected")
            except Exception as e:
                logger.warning(f"   Multimodal Scraper not available: {e}")
            
            # Enhanced Export
            try:
                from components.enhanced_file_export_sota_2026 import get_enhanced_export_system
                self.enhanced_export = get_enhanced_export_system(self.event_bus)
                logger.info("   ✅ Enhanced Export System connected")
            except Exception as e:
                logger.warning(f"   Enhanced Export not available: {e}")
                
        except Exception as e:
            logger.error(f"Failed to get component references: {e}")
    
    async def _subscribe_vr_events(self):
        """Subscribe to VR system events."""
        if not self.event_bus:
            return
        
        try:
            # VR mode changes
            self.event_bus.subscribe("vr.mode.change", self._handle_vr_mode_change)
            
            # VR gestures
            self.event_bus.subscribe("vr.gesture", self._handle_vr_gesture)
            
            # VR voice commands
            self.event_bus.subscribe("vr.voice_command", self._handle_vr_voice_command)
            
            # VR screenshot/recording
            self.event_bus.subscribe("vr.screenshot", self._handle_vr_screenshot)
            self.event_bus.subscribe("vr.recording.start", self._handle_vr_recording_start)
            self.event_bus.subscribe("vr.recording.stop", self._handle_vr_recording_stop)
            
            logger.info("   ✅ Subscribed to VR events")
            
        except Exception as e:
            logger.warning(f"Failed to subscribe to VR events: {e}")
    
    async def _subscribe_creation_events(self):
        """Subscribe to visual creation events for VR preview."""
        if not self.event_bus:
            return
        
        try:
            # Visual generation progress (for real-time VR preview)
            # FIX (2026-02-03): Use dot notation for consistency with other events
            self.event_bus.subscribe("visual.generation.progress", self._handle_creation_progress)
            
            # Visual generation complete
            self.event_bus.subscribe("visual.generated", self._handle_creation_complete)
            
            # Map generation
            self.event_bus.subscribe("creative.map.generated", self._handle_map_generated)
            
            logger.info("   ✅ Subscribed to creation events")
            
        except Exception as e:
            logger.warning(f"Failed to subscribe to creation events: {e}")
    
    async def _subscribe_learning_events(self):
        """Subscribe to learning events for VR visualization."""
        if not self.event_bus:
            return
        
        try:
            # Fact learned (update VR knowledge graph)
            self.event_bus.subscribe("learning.fact_learned", self._handle_fact_learned)
            
            # Knowledge synthesized
            self.event_bus.subscribe("learning.knowledge_synthesized", self._handle_knowledge_synthesized)
            
            # Visual concept learned
            self.event_bus.subscribe("learning.visual_concept_learned", self._handle_visual_concept_learned)
            
            logger.info("   ✅ Subscribed to learning events")
            
        except Exception as e:
            logger.warning(f"Failed to subscribe to learning events: {e}")
    
    async def _setup_vr_handlers(self):
        """Setup VR-specific event handlers."""
        if not self.event_bus:
            return
        
        try:
            # VR creation requests
            self.event_bus.subscribe("vr.create_image", self._handle_vr_create_image)
            self.event_bus.subscribe("vr.create_video", self._handle_vr_create_video)
            self.event_bus.subscribe("vr.create_3d", self._handle_vr_create_3d)
            
            # VR exploration requests
            self.event_bus.subscribe("vr.explore_knowledge", self._handle_vr_explore_knowledge)
            self.event_bus.subscribe("vr.explore_web", self._handle_vr_explore_web)
            
            # VR learning requests
            self.event_bus.subscribe("vr.learn_from_view", self._handle_vr_learn_from_view)
            
            logger.info("   ✅ VR-specific handlers registered")
            
        except Exception as e:
            logger.warning(f"Failed to setup VR handlers: {e}")
    
    # VR Mode Handlers
    async def _handle_vr_mode_change(self, data: Dict[str, Any]):
        """Handle VR mode change."""
        new_mode = data.get('mode', 'standard')
        self.vr_mode = new_mode
        
        logger.info(f"🥽 VR mode changed to: {new_mode}")
        
        # Configure systems based on mode
        if new_mode == "creation":
            self.creation_preview_enabled = True
            logger.info("   Creation mode: Real-time preview enabled")
        elif new_mode == "exploration":
            await self._setup_knowledge_graph_visualization()
            logger.info("   Exploration mode: Knowledge graph visualization active")
        elif new_mode == "learning":
            self.voice_commands_enabled = True
            logger.info("   Learning mode: Voice commands enabled")
    
    async def _handle_vr_gesture(self, data: Dict[str, Any]):
        """Handle VR gesture input."""
        gesture_type = data.get('type')
        gesture_data = data.get('data', {})
        
        self.gesture_history.append({
            'type': gesture_type,
            'data': gesture_data,
            'timestamp': datetime.now().isoformat()
        })
        
        # Limit history
        if len(self.gesture_history) > 100:
            self.gesture_history = self.gesture_history[-100:]
        
        # Handle specific gestures
        if gesture_type == "pinch":
            # Create image at pinch location
            await self._handle_gesture_create(gesture_data)
        elif gesture_type == "swipe":
            # Navigate knowledge graph
            await self._handle_gesture_navigate(gesture_data)
        elif gesture_type == "grab":
            # Grab and manipulate object
            await self._handle_gesture_grab(gesture_data)
    
    async def _handle_vr_voice_command(self, data: Dict[str, Any]):
        """Handle VR voice command."""
        command = data.get('command', '').lower()
        
        if not self.voice_commands_enabled:
            return
        
        # Creation commands
        if "create" in command or "generate" in command:
            prompt = command.replace("create", "").replace("generate", "").strip()
            await self._handle_vr_create_image({'prompt': prompt})
        
        # Learning commands
        elif "learn" in command or "remember" in command:
            await self._handle_vr_learn_from_view({})
        
        # Query commands
        elif "what" in command or "show" in command or "find" in command:
            query = command.replace("what", "").replace("show", "").replace("find", "").strip()
            await self._handle_vr_explore_knowledge({'query': query})
        
        # Export commands
        elif "save" in command or "export" in command:
            await self._handle_vr_screenshot({})
    
    async def _handle_vr_screenshot(self, data: Dict[str, Any]):
        """Handle VR screenshot request."""
        if not self.vr_system or not self.enhanced_export:
            return
        
        try:
            # Get current VR view
            screenshot_data = data.get('screenshot_data')
            
            if screenshot_data:
                # Save screenshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"vr_screenshot_{timestamp}.png"
                
                # Decode base64 if needed
                if isinstance(screenshot_data, str):
                    if screenshot_data.startswith('data:'):
                        screenshot_data = screenshot_data.split(',')[1]
                    screenshot_data = base64.b64decode(screenshot_data)
                
                # Ensure we have bytes
                if not isinstance(screenshot_data, bytes):
                    logger.error("Screenshot data is not bytes")
                    return
                
                # Save to temp file
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False, mode='wb') as tmp:
                    tmp.write(screenshot_data)
                    tmp_path = tmp.name
                
                # Export
                await self.enhanced_export.export_file(
                    tmp_path,
                    'images',
                    export_to_host=True,
                    custom_name=filename,
                    metadata={'source': 'vr_screenshot', 'mode': self.vr_mode}
                )
                
                logger.info(f"✅ VR screenshot saved: {filename}")
                
        except Exception as e:
            logger.error(f"Failed to save VR screenshot: {e}")
    
    async def _handle_vr_recording_start(self, data: Dict[str, Any]):
        """Handle VR recording start."""
        logger.info("🎥 VR recording started")
        # Recording will be handled by VR system
    
    async def _handle_vr_recording_stop(self, data: Dict[str, Any]):
        """Handle VR recording stop and export."""
        recording_path = data.get('recording_path')
        
        if recording_path and self.enhanced_export:
            await self.enhanced_export.export_file(
                recording_path,
                'videos',
                export_to_host=True,
                metadata={'source': 'vr_recording', 'mode': self.vr_mode}
            )
            logger.info(f"✅ VR recording exported: {recording_path}")
    
    # Creation Handlers
    async def _handle_creation_progress(self, data: Dict[str, Any]):
        """Handle visual creation progress for VR preview."""
        if not self.creation_preview_enabled or self.vr_mode != "creation":
            return
        
        # Send preview to VR headset
        preview_image = data.get('preview_image')
        if preview_image and self.event_bus:
            self.event_bus.publish("vr.display.preview", {
                'image': preview_image,
                'progress': data.get('progress', 0),
                'step': data.get('step', 0)
            })
    
    async def _handle_creation_complete(self, data: Dict[str, Any]):
        """Handle visual creation completion in VR."""
        image_path = data.get('image_path')
        video_path = data.get('video_path')
        
        if image_path and self.event_bus:
            # Display in VR
            self.event_bus.publish("vr.display.image", {
                'image_path': image_path,
                'mode': data.get('mode', 'image')
            })
            
            # Auto-export if in VR mode
            if self.enhanced_export:
                await self.enhanced_export.export_file(
                    image_path,
                    'ai_creations',
                    export_to_host=True,
                    metadata={'source': 'vr_creation', 'prompt': data.get('prompt', '')}
                )
        elif video_path and self.event_bus:
            self.event_bus.publish("vr.display.content", {
                'type': 'video',
                'video_path': video_path,
                'mode': data.get('mode', 'video')
            })
    
    async def _handle_map_generated(self, data: Dict[str, Any]):
        """Handle map generation for VR display."""
        image_path = data.get('image_path')
        
        if image_path and self.event_bus:
            # Display map in VR
            self.event_bus.publish("vr.display.map", {
                'image_path': image_path,
                'map_type': data.get('map_type', 'unknown')
            })
    
    # VR Creation Handlers
    async def _handle_vr_create_image(self, data: Dict[str, Any]):
        """Handle image creation request from VR."""
        prompt = data.get('prompt', '')
        
        if not prompt:
            return
        
        logger.info(f"🥽 VR image creation: {prompt}")
        
        # Trigger visual generation
        if self.event_bus:
            self.event_bus.publish("visual.generate", {
                'prompt': prompt,
                'mode': 'image',
                'source': 'vr',
                'preview_enabled': True
            })
    
    async def _handle_vr_create_video(self, data: Dict[str, Any]):
        """Handle video creation request from VR."""
        prompt = data.get('prompt', '')
        
        if not prompt:
            return
        
        logger.info(f"🥽 VR video creation: {prompt}")
        
        # Trigger video generation
        if self.event_bus:
            self.event_bus.publish("visual.generate", {
                'prompt': prompt,
                'mode': 'video',
                'source': 'vr',
                'preview_enabled': True
            })
    
    async def _handle_vr_create_3d(self, data: Dict[str, Any]):
        """Handle 3D model creation request from VR."""
        prompt = data.get('prompt', '')
        
        if not prompt:
            return
        
        logger.info(f"🥽 VR 3D creation: {prompt}")
        
        # Trigger 3D generation
        if self.event_bus:
            self.event_bus.publish("creative.generate_3d", {
                'prompt': prompt,
                'source': 'vr'
            })
    
    # Learning Handlers
    async def _handle_fact_learned(self, data: Dict[str, Any]):
        """Handle new fact learned - update VR knowledge graph."""
        if self.vr_mode != "exploration":
            return
        
        fact_id = data.get('fact_id')
        content = data.get('content', '')
        topics = data.get('topics', [])
        
        # Update VR knowledge graph visualization
        if self.event_bus:
            self.event_bus.publish("vr.knowledge_graph.add_node", {
                'node_id': fact_id,
                'content': content[:100],  # Preview
                'topics': topics,
                'related_count': data.get('related_count', 0)
            })
    
    async def _handle_knowledge_synthesized(self, data: Dict[str, Any]):
        """Handle knowledge synthesis - display in VR."""
        query = data.get('query', '')
        synthesis = data.get('synthesis_preview', '')
        
        if self.event_bus:
            self.event_bus.publish("vr.display.text", {
                'title': f"Knowledge: {query}",
                'content': synthesis,
                'type': 'synthesis'
            })
    
    async def _handle_visual_concept_learned(self, data: Dict[str, Any]):
        """Handle visual concept learned - add to VR library."""
        concept_id = data.get('concept_id')
        name = data.get('name', '')
        
        if self.event_bus:
            self.event_bus.publish("vr.concept_library.add", {
                'concept_id': concept_id,
                'name': name,
                'image_count': data.get('image_count', 0)
            })
    
    # VR Exploration Handlers
    async def _handle_vr_explore_knowledge(self, data: Dict[str, Any]):
        """Handle knowledge exploration request from VR."""
        query = data.get('query', '')
        
        if not query or not self.enhanced_learning:
            return
        
        logger.info(f"🥽 VR knowledge exploration: {query}")
        
        # Query knowledge graph
        if self.event_bus:
            self.event_bus.publish("learning.query_facts", {
                'query': query,
                'max_results': 20,
                'source': 'vr'
            })
    
    async def _handle_vr_explore_web(self, data: Dict[str, Any]):
        """Handle web exploration request from VR."""
        url = data.get('url', '')
        
        if not url or not self.multimodal_scraper:
            return
        
        logger.info(f"🥽 VR web exploration: {url}")
        
        # Scrape and visualize in VR
        if self.event_bus:
            self.event_bus.publish("user.scrape_and_learn", {
                'url': url,
                'source': 'vr',
                'visualize_in_vr': True
            })
    
    async def _handle_vr_learn_from_view(self, data: Dict[str, Any]):
        """Handle learning from current VR view."""
        if not self.enhanced_learning:
            return
        
        # Get current VR view/screenshot
        view_data = data.get('view_data')
        
        if view_data:
            # Analyze with Ollama
            if self.ollama_learning:
                from core.ollama_learning_integration import TaskType
                
                result = await self.ollama_learning.process(
                    prompt="Analyze this VR scene and extract key information",
                    task_type=TaskType.IMAGE_ANALYSIS,
                    images=[view_data] if isinstance(view_data, str) else None
                )
                
                # Learn from analysis
                if result.get('response'):
                    await self.enhanced_learning.learn_fact(
                        content=result['response'],
                        source='vr_view',
                        source_type='vr_scene',
                        metadata={'vr_mode': self.vr_mode}
                    )
                    
                    logger.info("✅ Learned from VR view")
    
    # Gesture Handlers
    async def _handle_gesture_create(self, gesture_data: Dict[str, Any]):
        """Handle creation gesture."""
        position = gesture_data.get('position', [0, 0, 0])
        
        # Trigger creation at gesture location
        if self.event_bus:
            self.event_bus.publish("vr.create_at_position", {
                'position': position,
                'type': 'image'
            })
    
    async def _handle_gesture_navigate(self, gesture_data: Dict[str, Any]):
        """Handle navigation gesture in knowledge graph."""
        direction = gesture_data.get('direction', [0, 0, 0])
        
        if self.event_bus:
            self.event_bus.publish("vr.knowledge_graph.navigate", {
                'direction': direction
            })
    
    async def _handle_gesture_grab(self, gesture_data: Dict[str, Any]):
        """Handle grab gesture."""
        object_id = gesture_data.get('object_id')
        
        if object_id and self.event_bus:
            self.event_bus.publish("vr.object.grabbed", {
                'object_id': object_id
            })
    
    # Visualization Setup
    async def _setup_knowledge_graph_visualization(self):
        """Setup 3D knowledge graph visualization in VR."""
        if not self.enhanced_learning:
            return
        
        try:
            # Get knowledge graph stats
            stats = self.enhanced_learning.knowledge_graph.get_stats()
            
            # Build 3D visualization data
            nodes = []
            edges = []
            
            # Sample nodes (limit to 100 for performance)
            for fact_id, fact in list(self.enhanced_learning.knowledge_graph.facts.items())[:100]:
                nodes.append({
                    'id': fact_id,
                    'label': fact.content[:50],
                    'topics': fact.metadata.get('topics', []),
                    'source_type': fact.source_type
                })
                
                # Add edges to related facts
                for related_id in fact.related_facts[:5]:  # Limit edges
                    if related_id in self.enhanced_learning.knowledge_graph.facts:
                        edges.append({
                            'source': fact_id,
                            'target': related_id
                        })
            
            # Send to VR for visualization
            if self.event_bus:
                self.event_bus.publish("vr.knowledge_graph.setup", {
                    'nodes': nodes,
                    'edges': edges,
                    'stats': stats
                })
                
                logger.info(f"✅ Knowledge graph visualization setup: {len(nodes)} nodes, {len(edges)} edges")
                
        except Exception as e:
            logger.error(f"Failed to setup knowledge graph visualization: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get VR SOTA integration status."""
        return {
            'vr_mode': self.vr_mode,
            'creation_preview_enabled': self.creation_preview_enabled,
            'voice_commands_enabled': self.voice_commands_enabled,
            'components': {
                'visual_creation': self.visual_creation is not None,
                'ollama_learning': self.ollama_learning is not None,
                'enhanced_learning': self.enhanced_learning is not None,
                'multimodal_scraper': self.multimodal_scraper is not None,
                'enhanced_export': self.enhanced_export is not None
            },
            'gesture_history_size': len(self.gesture_history)
        }


# Global instance
_vr_integration: Optional[VRSOTAIntegration] = None


def get_vr_sota_integration(event_bus=None, vr_system=None) -> VRSOTAIntegration:
    """Get or create global VR SOTA integration instance."""
    global _vr_integration
    if _vr_integration is None:
        _vr_integration = VRSOTAIntegration(event_bus, vr_system)
    return _vr_integration


async def initialize_vr_sota_integration(event_bus=None, vr_system=None) -> bool:
    """Initialize VR SOTA 2026 integration.
    
    Args:
        event_bus: EventBus instance
        vr_system: VRSystem instance
        
    Returns:
        True if initialization successful
    """
    integration = get_vr_sota_integration(event_bus, vr_system)
    return await integration.initialize()


__all__ = [
    'VRSOTAIntegration',
    'get_vr_sota_integration',
    'initialize_vr_sota_integration',
]
