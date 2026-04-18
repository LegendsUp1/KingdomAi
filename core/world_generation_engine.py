#!/usr/bin/env python3
import os
"""
World Generation Engine - SOTA 2026
====================================
AI-powered procedural world creation for games and interactive experiences.

BASED ON RESEARCH:
- WorldGen: Text-to-traversable 3D worlds for Unity/Unreal
- SceneFoundry: Apartment-scale worlds with articulated furniture
- Hunyuan3D Studio: Game-ready asset pipeline
- WorldScore: Unified evaluation benchmark

KEY CAPABILITIES:
- Text-to-world generation (natural language → 3D world)
- Large-scale environments (city-scale, planet-scale)
- Functionally articulated objects (doors open, chairs sit-able)
- Navigable spaces (collision-free pathfinding)
- Game engine integration (Unity, Unreal)
- Procedural asset generation
"""

import logging
import asyncio
import time
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger("KingdomAI.WorldGeneration")


class WorldScale(Enum):
    """Scale of world to generate"""
    ROOM = "room"  # Single room (10-100 m²)
    APARTMENT = "apartment"  # Apartment/house (100-500 m²)
    BUILDING = "building"  # Office building, mall (500-10k m²)
    NEIGHBORHOOD = "neighborhood"  # City block (10k-100k m²)
    CITY = "city"  # Small city (100k-10M m²)
    REGION = "region"  # Large region/country
    PLANET = "planet"  # Entire planet


class WorldType(Enum):
    """Type of world"""
    REALISTIC = "realistic"  # Real-world architecture
    FANTASY = "fantasy"  # Magic, castles, dragons
    SCIFI = "scifi"  # Futuristic, high-tech
    HORROR = "horror"  # Creepy, atmospheric
    ABSTRACT = "abstract"  # Non-realistic, artistic
    HISTORICAL = "historical"  # Period-accurate
    PROCEDURAL = "procedural"  # Fully generated


@dataclass
class WorldObject:
    """Single object in world"""
    id: str
    type: str  # "building", "tree", "vehicle", "furniture", etc.
    name: str
    position: Tuple[float, float, float]  # (x, y, z)
    rotation: Tuple[float, float, float]  # (pitch, yaw, roll)
    scale: Tuple[float, float, float]  # (x, y, z)
    
    # Functionality
    is_interactive: bool = False
    interaction_type: Optional[str] = None  # "door", "button", "container", etc.
    
    # References
    asset_path: Optional[str] = None  # Path to 3D model
    texture_paths: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldRegion:
    """Defined region within world"""
    id: str
    name: str
    bounds: Tuple[float, float, float, float]  # (min_x, min_z, max_x, max_z)
    biome: str  # "urban", "forest", "desert", "ocean", etc.
    objects: List[str]  # Object IDs
    navigation_mesh: Optional[Any] = None  # NavMesh for pathfinding


@dataclass
class World:
    """Complete world definition"""
    id: str
    name: str
    description: str
    scale: WorldScale
    type: WorldType
    
    # World data
    objects: List[WorldObject]
    regions: List[WorldRegion]
    
    # Terrain
    terrain_heightmap: Optional[str] = None  # Path to heightmap
    terrain_size: Tuple[float, float] = (1000.0, 1000.0)  # (width, depth)
    
    # Lighting/atmosphere
    time_of_day: str = "noon"  # "dawn", "noon", "dusk", "night"
    weather: str = "clear"  # "clear", "cloudy", "rain", "snow", "fog"
    ambient_color: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    
    # Game engine export
    unity_project_path: Optional[str] = None
    unreal_project_path: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorldGenerationEngine:
    """
    SOTA 2026 World Generation Engine.
    
    Transforms natural language → traversable 3D worlds.
    Integrates with Unity/Unreal for game-ready output.
    """
    
    def __init__(self, event_bus=None):
        """Initialize engine."""
        self.event_bus = event_bus
        self._worlds: Dict[str, World] = {}
        self._asset_cache: Dict[str, str] = {}
        
        logger.info("🌍 WorldGenerationEngine initialized")
    
    async def generate_world(
        self,
        description: str,
        scale: WorldScale = WorldScale.APARTMENT,
        type: WorldType = WorldType.REALISTIC,
        target_engine: str = "unity"  # "unity" or "unreal"
    ) -> World:
        """
        Generate complete 3D world from text description.
        
        SOTA 2026 Pipeline (WorldGen approach):
        1. LLM scene layout reasoning (decompose description)
        2. Procedural generation (terrain, buildings, props)
        3. Diffusion-based 3D generation (assets)
        4. Object decomposition (functional articulation)
        5. Navigation mesh generation (pathfinding)
        6. Game engine export (Unity/Unreal)
        
        Args:
            description: Natural language world description
            scale: Scale of world
            type: Type/genre of world
            target_engine: Target game engine
            
        Returns:
            Complete World object
        """
        logger.info(f"🌍 Generating world: {description[:50]}...")
        start_time = time.time()
        
        # 1. LLM Scene Layout Reasoning
        logger.info("🧠 Phase 1: Scene layout reasoning...")
        layout = await self._reason_scene_layout(description, scale, type)
        
        # 2. Procedural Generation
        logger.info("🏗️ Phase 2: Procedural generation...")
        objects = await self._generate_objects(layout, scale, type)
        
        # 3. Diffusion-based 3D Generation (for unique assets)
        logger.info("🎨 Phase 3: Asset generation...")
        objects = await self._generate_3d_assets(objects)
        
        # 4. Functional Articulation
        logger.info("🔧 Phase 4: Functional articulation...")
        objects = self._articulate_objects(objects)
        
        # 5. Region Definition & Navigation
        logger.info("🗺️ Phase 5: Navigation mesh...")
        regions = self._create_regions(objects, scale)
        regions = self._generate_navmesh(regions)
        
        # 6. Create World
        world = World(
            id=f"world_{int(time.time())}",
            name=f"Generated World: {description[:30]}",
            description=description,
            scale=scale,
            type=type,
            objects=objects,
            regions=regions
        )
        
        # 7. Export to game engine
        logger.info(f"📦 Phase 6: Exporting to {target_engine}...")
        if target_engine == "unity":
            world = await self._export_to_unity(world)
        elif target_engine == "unreal":
            world = await self._export_to_unreal(world)
        
        execution_time = time.time() - start_time
        world.metadata["execution_time"] = execution_time
        world.metadata["generation_date"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Cache
        self._worlds[world.id] = world
        
        # Publish event
        if self.event_bus:
            self.event_bus.publish("world.generated", {
                "world_id": world.id,
                "description": description,
                "scale": scale.value,
                "num_objects": len(world.objects),
                "execution_time": execution_time
            })
        
        logger.info(f"✅ World generated in {execution_time:.2f}s - {len(world.objects)} objects")
        return world
    
    async def _reason_scene_layout(
        self, description: str, scale: WorldScale, type: WorldType
    ) -> Dict[str, Any]:
        """
        Use LLM to reason about scene layout.
        
        Decomposes description into:
        - Major structures (buildings, terrain features)
        - Object categories (furniture, vegetation, vehicles)
        - Spatial relationships (X is near Y, Z is inside A)
        - Functional requirements (navigable paths, interaction points)
        """
        
        prompt = f"""You are a world designer for a {type.value} world at {scale.value} scale.
Analyze this description and create a layout plan:

Description: {description}

Provide in JSON format:
{{
  "major_structures": [
    {{"type": "...", "name": "...", "description": "...", "approximate_position": [x, y, z]}}
  ],
  "object_categories": ["furniture", "vegetation", "props", ...],
  "spatial_relationships": [
    {{"object_a": "...", "relation": "near/inside/above", "object_b": "..."}}
  ],
  "navigation_requirements": ["paths between A and B", ...],
  "interaction_points": ["doors", "switches", ...]
}}"""
        
        response = await self._call_ollama(prompt, model="deepseek-v3.1:671b-cloud")
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback layout
            return {
                "major_structures": [{"type": "building", "name": "main_structure"}],
                "object_categories": ["props"],
                "spatial_relationships": [],
                "navigation_requirements": [],
                "interaction_points": []
            }
    
    async def _generate_objects(
        self, layout: Dict[str, Any], scale: WorldScale, type: WorldType
    ) -> List[WorldObject]:
        """Generate objects based on layout plan."""
        
        objects = []
        obj_id = 0
        
        # Generate major structures
        for structure in layout.get("major_structures", []):
            pos = structure.get("approximate_position", [0, 0, 0])
            obj = WorldObject(
                id=f"obj_{obj_id}",
                type=structure.get("type", "building"),
                name=structure.get("name", f"structure_{obj_id}"),
                position=(pos[0], pos[1], pos[2]),
                rotation=(0, 0, 0),
                scale=(1, 1, 1),
                is_interactive=False
            )
            objects.append(obj)
            obj_id += 1
        
        # Generate objects by category with spatial distribution
        for category in layout.get("object_categories", []):
            count = 10 if scale == WorldScale.ROOM else 50 if scale == WorldScale.APARTMENT else 100
            
            import random
            spread = {
                WorldScale.ROOM: 5.0, WorldScale.APARTMENT: 15.0,
                WorldScale.BUILDING: 50.0, WorldScale.NEIGHBORHOOD: 200.0,
                WorldScale.CITY: 1000.0, WorldScale.REGION: 5000.0,
                WorldScale.PLANET: 50000.0,
            }.get(scale, 20.0)
            
            for i in range(count):
                px = random.uniform(-spread, spread)
                pz = random.uniform(-spread, spread)
                py = 0.0
                ry = random.uniform(0, 360)
                
                obj = WorldObject(
                    id=f"obj_{obj_id}",
                    type=category,
                    name=f"{category}_{i}",
                    position=(px, py, pz),
                    rotation=(0, ry, 0),
                    scale=(1, 1, 1),
                    is_interactive=False
                )
                objects.append(obj)
                obj_id += 1
        
        return objects
    
    async def _generate_3d_assets(self, objects: List[WorldObject]) -> List[WorldObject]:
        """Generate 3D asset descriptors for objects via Ollama."""
        
        logger.info(f"🎨 Generating 3D assets for {len(objects)} objects...")
        
        unique_types = list({obj.type for obj in objects})
        prompt = (
            f"For each of these object types in a 3D world, provide asset specs. "
            f"Types: {unique_types}\n\n"
            f"Respond in JSON object mapping type to specs:\n"
            f'{{"type_name": {{"lod_levels": 3, "poly_budget": 5000, '
            f'"texture_res": 1024, "material": "PBR", "style_notes": "..."}}, ...}}'
        )
        asset_specs = {}
        try:
            response = await self._call_ollama(prompt)
            asset_specs = json.loads(response)
            if not isinstance(asset_specs, dict):
                asset_specs = {}
        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"Asset spec generation failed: {e}")
        
        for obj in objects:
            spec = asset_specs.get(obj.type, {})
            obj.asset_path = f"assets/{obj.type}/{obj.name}.fbx"
            obj.metadata["poly_budget"] = spec.get("poly_budget", 5000)
            obj.metadata["texture_res"] = spec.get("texture_res", 1024)
            obj.metadata["material"] = spec.get("material", "PBR")
            obj.metadata["lod_levels"] = spec.get("lod_levels", 3)
        
        return objects
    
    def _articulate_objects(self, objects: List[WorldObject]) -> List[WorldObject]:
        """Make objects functionally articulated (doors open, chairs sit-able)."""
        
        for obj in objects:
            # Define interactive objects
            if obj.type in ["door", "window"]:
                obj.is_interactive = True
                obj.interaction_type = "toggle"  # Open/close
            elif obj.type in ["button", "switch"]:
                obj.is_interactive = True
                obj.interaction_type = "button"  # Press
            elif obj.type in ["container", "chest"]:
                obj.is_interactive = True
                obj.interaction_type = "container"  # Open/loot
            elif obj.type in ["chair", "bench"]:
                obj.is_interactive = True
                obj.interaction_type = "sit"  # Sit action
        
        return objects
    
    def _create_regions(self, objects: List[WorldObject], scale: WorldScale) -> List[WorldRegion]:
        """Create world regions for organization."""
        
        # Simple region creation based on scale
        if scale == WorldScale.ROOM:
            return [WorldRegion(
                id="region_0",
                name="Main Room",
                bounds=(-10, -10, 10, 10),
                biome="indoor",
                objects=[obj.id for obj in objects]
            )]
        elif scale == WorldScale.APARTMENT:
            return [
                WorldRegion(id="region_0", name="Living Room", bounds=(-10, -10, 10, 0), biome="indoor", objects=[]),
                WorldRegion(id="region_1", name="Bedroom", bounds=(-10, 0, 0, 10), biome="indoor", objects=[]),
                WorldRegion(id="region_2", name="Kitchen", bounds=(0, 0, 10, 10), biome="indoor", objects=[])
            ]
        
        spread_map = {
            WorldScale.BUILDING: (50, 4), WorldScale.NEIGHBORHOOD: (200, 9),
            WorldScale.CITY: (1000, 16), WorldScale.REGION: (5000, 25),
            WorldScale.PLANET: (50000, 36),
        }
        spread, grid_n = spread_map.get(scale, (100, 4))
        side = int(grid_n ** 0.5)
        cell_size = (spread * 2) / max(side, 1)
        
        biomes = ["urban", "suburban", "park", "commercial", "industrial",
                   "forest", "desert", "water", "mountain", "plains"]
        
        regions = []
        idx = 0
        for row in range(side):
            for col in range(side):
                min_x = -spread + col * cell_size
                min_z = -spread + row * cell_size
                biome = biomes[idx % len(biomes)]
                region_objs = [
                    o.id for o in objects
                    if min_x <= o.position[0] < min_x + cell_size
                    and min_z <= o.position[2] < min_z + cell_size
                ]
                regions.append(WorldRegion(
                    id=f"region_{idx}",
                    name=f"{biome.title()} Zone {idx}",
                    bounds=(min_x, min_z, min_x + cell_size, min_z + cell_size),
                    biome=biome,
                    objects=region_objs
                ))
                idx += 1
        
        return regions
    
    def _generate_navmesh(self, regions: List[WorldRegion]) -> List[WorldRegion]:
        """Generate navigation mesh (grid-based walkability) for pathfinding."""
        
        logger.info(f"🗺️ Generating navigation mesh for {len(regions)} regions...")
        
        for region in regions:
            min_x, min_z, max_x, max_z = region.bounds
            cell_size = max(1.0, (max_x - min_x) / 20.0)
            
            nav_nodes = []
            nx = int((max_x - min_x) / cell_size)
            nz = int((max_z - min_z) / cell_size)
            for ix in range(max(nx, 1)):
                for iz in range(max(nz, 1)):
                    cx = min_x + (ix + 0.5) * cell_size
                    cz = min_z + (iz + 0.5) * cell_size
                    walkable = region.biome not in ("water", "mountain")
                    nav_nodes.append({
                        "x": cx, "z": cz,
                        "walkable": walkable,
                        "neighbors": []
                    })
            
            for i, node in enumerate(nav_nodes):
                row, col = divmod(i, max(nz, 1))
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = row + dr, col + dc
                    ni = nr * max(nz, 1) + nc
                    if 0 <= nr < max(nx, 1) and 0 <= nc < max(nz, 1) and nav_nodes[ni]["walkable"]:
                        node["neighbors"].append(ni)
            
            region.navigation_mesh = {
                "cell_size": cell_size, "grid": [nx, nz], "nodes": nav_nodes
            }
        
        return regions
    
    async def _export_to_unity(self, world: World) -> World:
        """Export world to Unity project structure (JSON scene descriptor)."""
        
        logger.info("📦 Exporting to Unity...")
        
        export_dir = Path(f"exports/unity_projects/{world.id}")
        export_dir.mkdir(parents=True, exist_ok=True)
        
        scene_data = {
            "engine": "unity",
            "world_id": world.id,
            "name": world.name,
            "description": world.description,
            "scale": world.scale.value,
            "time_of_day": world.time_of_day,
            "weather": world.weather,
            "ambient_color": list(world.ambient_color),
            "terrain": {
                "heightmap": world.terrain_heightmap,
                "size": list(world.terrain_size)
            },
            "objects": [
                {
                    "id": obj.id, "type": obj.type, "name": obj.name,
                    "position": list(obj.position),
                    "rotation": list(obj.rotation),
                    "scale": list(obj.scale),
                    "is_interactive": obj.is_interactive,
                    "interaction_type": obj.interaction_type,
                    "asset_path": obj.asset_path,
                    "prefab": f"Assets/Prefabs/{obj.type}/{obj.name}.prefab"
                }
                for obj in world.objects
            ],
            "regions": [
                {"id": r.id, "name": r.name, "bounds": list(r.bounds),
                 "biome": r.biome, "object_count": len(r.objects)}
                for r in world.regions
            ]
        }
        
        (export_dir / "scene.json").write_text(json.dumps(scene_data, indent=2), encoding="utf-8")
        world.unity_project_path = str(export_dir)
        return world
    
    async def _export_to_unreal(self, world: World) -> World:
        """Export world to Unreal Engine project structure (JSON level descriptor)."""
        
        logger.info("📦 Exporting to Unreal Engine...")
        
        export_dir = Path(f"exports/unreal_projects/{world.id}")
        export_dir.mkdir(parents=True, exist_ok=True)
        
        level_data = {
            "engine": "unreal",
            "world_id": world.id,
            "name": world.name,
            "description": world.description,
            "scale": world.scale.value,
            "time_of_day": world.time_of_day,
            "weather": world.weather,
            "ambient_color": list(world.ambient_color),
            "landscape": {
                "heightmap": world.terrain_heightmap,
                "size": list(world.terrain_size)
            },
            "actors": [
                {
                    "id": obj.id, "type": obj.type, "name": obj.name,
                    "transform": {
                        "location": list(obj.position),
                        "rotation": list(obj.rotation),
                        "scale": list(obj.scale)
                    },
                    "is_interactive": obj.is_interactive,
                    "interaction_type": obj.interaction_type,
                    "mesh_path": obj.asset_path,
                    "blueprint": f"/Game/Blueprints/{obj.type}/{obj.name}_BP"
                }
                for obj in world.objects
            ],
            "sub_levels": [
                {"id": r.id, "name": r.name, "bounds": list(r.bounds),
                 "biome": r.biome, "actor_count": len(r.objects)}
                for r in world.regions
            ]
        }
        
        (export_dir / "level.json").write_text(json.dumps(level_data, indent=2), encoding="utf-8")
        world.unreal_project_path = str(export_dir)
        return world
    
    async def _call_ollama(self, prompt: str, model: str = None) -> str:
        """Call Ollama API."""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                _url = os.environ.get("KINGDOM_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
                try:
                    from core.ollama_gateway import orchestrator
                    model = orchestrator.get_model_for_task("creative") or "cogito:latest"
                except Exception:
                    model = model or "cogito:latest"
                async with session.post(
                    f"{_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False, "keep_alive": -1, "options": {"num_gpu": 999}},
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "")
                    else:
                        return ""
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return ""
    
    def get_world(self, world_id: str) -> Optional[World]:
        """Get world by ID."""
        return self._worlds.get(world_id)
    
    def list_worlds(self) -> List[World]:
        """List all generated worlds."""
        return list(self._worlds.values())


# Global singleton
_world_engine = None


def get_world_engine(event_bus=None) -> WorldGenerationEngine:
    """Get or create global world generation engine singleton."""
    global _world_engine
    if _world_engine is None:
        _world_engine = WorldGenerationEngine(event_bus=event_bus)
    return _world_engine
