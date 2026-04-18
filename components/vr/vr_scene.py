#!/usr/bin/env python3
# VRScene for Kingdom AI

import logging
import asyncio
import json
from core.base_component import BaseComponent

class VRScene(BaseComponent):
    """
    VRScene handles VR scene management for the Kingdom AI system.
    This component manages the creation, loading, and manipulation of virtual environments.
    """
    
    def __new__(cls, event_bus=None, *args, **kwargs):
        return super().__new__(cls)
    
    def __init__(self, event_bus=None):
        super().__init__("VRScene", event_bus)
        self.logger = logging.getLogger("KingdomAI.VRScene")
        self.scenes = {}
        self.active_scene_id = None
        self.scene_objects = {}
        self.scene_metadata = {}
        self.logger.info("VRScene initialized")
    
    async def initialize(self):
        """Initialize the VRScene component."""
        self.logger.info("Initializing VRScene...")
        
        # Set up event subscriptions if event_bus is available
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            try:
                self.event_bus.subscribe_sync("vr.scene.create", self._handle_scene_create)
                self.event_bus.subscribe_sync("vr.scene.delete", self._handle_scene_delete)
                self.event_bus.subscribe_sync("vr.scene.activate", self._handle_scene_activate)
                self.event_bus.subscribe_sync("vr.scene.add_object", self._handle_add_object)
                self.event_bus.subscribe_sync("vr.scene.remove_object", self._handle_remove_object)
                self.event_bus.subscribe_sync("vr.scene.update", self._handle_scene_update)
                self.logger.info("VRScene event subscriptions initialized successfully")
            except Exception as e:
                self.logger.error(f"Error setting up VRScene event subscriptions: {e}")
        else:
            self.logger.warning("VRScene initialized without event bus. Event subscriptions skipped.")
        
        # Initialize default scenes
        await self._initialize_default_scenes()
        
        self.logger.info("VRScene initialization completed")
        return True
    
    async def _initialize_default_scenes(self):
        """Initialize default VR scenes."""
        try:
            # Create a default trading environment scene
            trading_scene = {
                "id": "trading_environment",
                "name": "Kingdom AI Trading Room",
                "description": "Virtual trading floor for cryptocurrency and stock market visualization",
                "environment": {
                    "skybox": "trading_floor",
                    "lighting": "office",
                    "ambient_sound": "trading_ambience"
                },
                "objects": {}
            }
            
            # Create a default mining environment scene
            mining_scene = {
                "id": "mining_environment",
                "name": "Cryptocurrency Mining Facility",
                "description": "Virtual mining facility with real-time blockchain visualization",
                "environment": {
                    "skybox": "mining_facility",
                    "lighting": "industrial",
                    "ambient_sound": "server_hum"
                },
                "objects": {}
            }
            
            # Add scenes to the scenes dictionary
            self.scenes["trading_environment"] = trading_scene
            self.scenes["mining_environment"] = mining_scene
            
            self.logger.info("Default scenes initialized")
            
            # Publish scenes initialized event
            if hasattr(self, 'event_bus') and self.event_bus is not None:
                await self.event_bus.emit("vr.scene.initialized", {
                    "available_scenes": list(self.scenes.keys()),
                    "default_scenes": ["trading_environment", "mining_environment"]
                })
                
        except Exception as e:
            self.logger.error(f"Error initializing default scenes: {e}")
    
    async def _handle_scene_create(self, event_data):
        """Handle vr.scene.create event."""
        self.logger.info(f"Received vr.scene.create event: {event_data}")
        
        scene_id = event_data.get('id')
        scene_name = event_data.get('name', 'Unnamed Scene')
        scene_data = event_data.get('data', {})
        
        if not scene_id:
            self.logger.error("Cannot create scene: Missing scene ID")
            
            # Emit error event
            if hasattr(self, 'event_bus') and self.event_bus is not None:
                await self.event_bus.emit("vr.scene.error", {
                    "error": "missing_id",
                    "message": "Scene ID is required"
                })
            return
            
        if scene_id in self.scenes:
            self.logger.warning(f"Scene ID {scene_id} already exists. Overwriting.")
        
        # Create the new scene
        self.scenes[scene_id] = {
            "id": scene_id,
            "name": scene_name,
            "description": event_data.get('description', ''),
            "environment": event_data.get('environment', {}),
            "objects": {}
        }
        
        # Merge any additional data
        self.scenes[scene_id].update(scene_data)
        
        self.logger.info(f"Created scene: {scene_id} - {scene_name}")
        
        # Emit scene created event
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            await self.event_bus.emit("vr.scene.created", {
                "scene_id": scene_id,
                "name": scene_name,
                "status": "created"
            })
    
    async def _handle_scene_delete(self, event_data):
        """Handle vr.scene.delete event."""
        self.logger.info(f"Received vr.scene.delete event: {event_data}")
        
        scene_id = event_data.get('scene_id')
        
        if not scene_id:
            self.logger.error("Cannot delete scene: Missing scene ID")
            return
            
        if scene_id not in self.scenes:
            self.logger.error(f"Cannot delete scene: Scene {scene_id} not found")
            return
            
        # If deleting the active scene, clear the active scene ID
        if scene_id == self.active_scene_id:
            self.active_scene_id = None
            
        # Delete the scene
        scene_name = self.scenes[scene_id].get('name', 'Unnamed Scene')
        del self.scenes[scene_id]
        
        self.logger.info(f"Deleted scene: {scene_id} - {scene_name}")
        
        # Emit scene deleted event
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            await self.event_bus.emit("vr.scene.deleted", {
                "scene_id": scene_id,
                "name": scene_name,
                "status": "deleted"
            })
    
    async def _handle_scene_activate(self, event_data):
        """Handle vr.scene.activate event."""
        self.logger.info(f"Received vr.scene.activate event: {event_data}")
        
        scene_id = event_data.get('scene_id')
        
        if not scene_id:
            self.logger.error("Cannot activate scene: Missing scene ID")
            return
            
        if scene_id not in self.scenes:
            self.logger.error(f"Cannot activate scene: Scene {scene_id} not found")
            
            # Emit error event
            if hasattr(self, 'event_bus') and self.event_bus is not None:
                await self.event_bus.emit("vr.scene.error", {
                    "error": "scene_not_found",
                    "scene_id": scene_id,
                    "message": f"Scene {scene_id} not found"
                })
            return
            
        # Set the active scene
        self.active_scene_id = scene_id
        scene_name = self.scenes[scene_id].get('name', 'Unnamed Scene')
        
        self.logger.info(f"Activated scene: {scene_id} - {scene_name}")
        
        # Emit scene activated event
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            await self.event_bus.emit("vr.scene.activated", {
                "scene_id": scene_id,
                "name": scene_name,
                "status": "activated",
                "scene_data": self.scenes[scene_id]
            })
            
            # Also emit a load event for the renderer
            await self.event_bus.emit("vr.scene.load", {
                "scene_id": scene_id,
                "scene_data": self.scenes[scene_id]
            })
    
    async def _handle_add_object(self, event_data):
        """Handle vr.scene.add_object event."""
        self.logger.info(f"Received vr.scene.add_object event: {event_data}")
        
        scene_id = event_data.get('scene_id', self.active_scene_id)
        object_id = event_data.get('object_id')
        object_data = event_data.get('object_data', {})
        
        if not scene_id:
            self.logger.error("Cannot add object: No scene specified and no active scene")
            return
            
        if scene_id not in self.scenes:
            self.logger.error(f"Cannot add object: Scene {scene_id} not found")
            return
            
        if not object_id:
            self.logger.error("Cannot add object: Missing object ID")
            return
            
        # Add the object to the scene
        self.scenes[scene_id]["objects"][object_id] = object_data
        
        self.logger.info(f"Added object {object_id} to scene {scene_id}")
        
        # Emit object added event
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            await self.event_bus.emit("vr.scene.object.added", {
                "scene_id": scene_id,
                "object_id": object_id,
                "status": "added"
            })
    
    async def _handle_remove_object(self, event_data):
        """Handle vr.scene.remove_object event."""
        self.logger.info(f"Received vr.scene.remove_object event: {event_data}")
        
        scene_id = event_data.get('scene_id', self.active_scene_id)
        object_id = event_data.get('object_id')
        
        if not scene_id:
            self.logger.error("Cannot remove object: No scene specified and no active scene")
            return
            
        if scene_id not in self.scenes:
            self.logger.error(f"Cannot remove object: Scene {scene_id} not found")
            return
            
        if not object_id:
            self.logger.error("Cannot remove object: Missing object ID")
            return
            
        if object_id not in self.scenes[scene_id]["objects"]:
            self.logger.error(f"Cannot remove object: Object {object_id} not found in scene {scene_id}")
            return
            
        # Remove the object from the scene
        del self.scenes[scene_id]["objects"][object_id]
        
        self.logger.info(f"Removed object {object_id} from scene {scene_id}")
        
        # Emit object removed event
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            await self.event_bus.emit("vr.scene.object.removed", {
                "scene_id": scene_id,
                "object_id": object_id,
                "status": "removed"
            })
    
    async def _handle_scene_update(self, event_data):
        """Handle vr.scene.update event."""
        self.logger.info(f"Received vr.scene.update event: {event_data}")
        
        scene_id = event_data.get('scene_id')
        scene_updates = event_data.get('updates', {})
        
        if not scene_id:
            self.logger.error("Cannot update scene: Missing scene ID")
            return
            
        if scene_id not in self.scenes:
            self.logger.error(f"Cannot update scene: Scene {scene_id} not found")
            return
            
        # Update scene properties
        if 'name' in scene_updates:
            self.scenes[scene_id]['name'] = scene_updates['name']
            
        if 'description' in scene_updates:
            self.scenes[scene_id]['description'] = scene_updates['description']
            
        if 'environment' in scene_updates:
            self.scenes[scene_id]['environment'].update(scene_updates['environment'])
            
        self.logger.info(f"Updated scene: {scene_id}")
        
        # Emit scene updated event
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            await self.event_bus.emit("vr.scene.updated", {
                "scene_id": scene_id,
                "status": "updated",
                "updates": scene_updates
            })
    
    async def get_scene(self, scene_id):
        """Get a scene by ID."""
        if scene_id not in self.scenes:
            self.logger.error(f"Scene {scene_id} not found")
            return None
            
        return self.scenes[scene_id]
    
    async def get_active_scene(self):
        """Get the active scene."""
        if not self.active_scene_id:
            self.logger.warning("No active scene")
            return None
            
        return self.scenes.get(self.active_scene_id)
    
    async def export_scene(self, scene_id, format="json"):
        """Export a scene to the specified format."""
        if scene_id not in self.scenes:
            self.logger.error(f"Cannot export scene: Scene {scene_id} not found")
            return None
            
        scene = self.scenes[scene_id]
        
        if format.lower() == "json":
            return json.dumps(scene, indent=2)
        else:
            self.logger.error(f"Unsupported export format: {format}")
            return None
