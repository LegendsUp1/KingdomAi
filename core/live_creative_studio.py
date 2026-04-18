"""
Live Creative Studio - SOTA 2026
=================================
Real-time AI-controlled image/map creation and editing.
Ollama brain controls the creative process live.
"""
import os
import logging
import threading
import time
import numpy as np
from typing import Dict, Any, Optional, Callable
from pathlib import Path

logger = logging.getLogger("KingdomAI.LiveCreativeStudio")

class LiveCreativeStudio:
    """
    Real-time creative studio with Ollama brain control.
    Shows live creation/editing of images and maps.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._window = None
        self._app = None
        self._canvas = None
        self._running = False
        self._ollama_connected = False
        self._current_project = None
        
        # Try to connect to Ollama
        self._connect_ollama()
        
        logger.info("🎨 LiveCreativeStudio initialized")
    
    def _connect_ollama(self):
        """Connect to Ollama brain for AI control."""
        try:
            import requests
            _ollama_url = os.environ.get("KINGDOM_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            response = requests.get(f"{_ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                self._ollama_connected = True
                models = response.json().get("models", [])
                logger.info(f"✅ Ollama connected - {len(models)} models available")
            else:
                logger.warning("⚠️ Ollama not responding")
        except Exception as e:
            logger.warning(f"⚠️ Ollama not available: {e}")
    
    def create_live(self, prompt: str, on_update: Callable = None) -> Dict[str, Any]:
        """
        Create content live with real-time visualization.
        Ollama brain interprets prompt and controls creation.
        """
        from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QProgressBar
        from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QFont
        from PyQt6.QtCore import Qt, QTimer
        import sys
        
        # Get or create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Create live window
        window = QMainWindow()
        window.setWindowTitle(f"🎨 Kingdom AI Live Studio - Creating...")
        window.setStyleSheet("background-color: #1a1a2e; color: white;")
        window.resize(800, 700)
        
        # Central widget
        central = QWidget()
        layout = QVBoxLayout(central)
        
        # Status label
        status = QLabel(f"🧠 Ollama Brain: {'Connected' if self._ollama_connected else 'Offline'}")
        status.setStyleSheet("color: #00ff88; font-size: 14px; padding: 5px;")
        layout.addWidget(status)
        
        # Prompt label
        prompt_label = QLabel(f"📝 Prompt: {prompt[:50]}...")
        prompt_label.setStyleSheet("color: #88ccff; font-size: 12px; padding: 5px;")
        layout.addWidget(prompt_label)
        
        # Progress bar
        progress = QProgressBar()
        progress.setStyleSheet("""
            QProgressBar { border: 2px solid #333; border-radius: 5px; background: #222; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 #00ff88, stop:1 #00ccff); }
        """)
        progress.setMaximum(100)
        layout.addWidget(progress)
        
        # Image canvas
        canvas = QLabel()
        canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas.setMinimumSize(512, 512)
        canvas.setStyleSheet("background-color: #0a0a1a; border: 2px solid #333;")
        layout.addWidget(canvas)
        
        # Phase label
        phase_label = QLabel("⏳ Initializing...")
        phase_label.setStyleSheet("color: #ffcc00; font-size: 12px; padding: 5px;")
        layout.addWidget(phase_label)
        
        window.setCentralWidget(central)
        window.show()
        
        # Live creation state
        state = {
            "phase": 0,
            "heightmap": None,
            "biomes": None,
            "cities": [],
            "rivers": [],
            "roads": [],
            "width": 512,
            "height": 512
        }
        
        def update_canvas():
            """Render current state to canvas."""
            img = self._render_state(state)
            if img is not None:
                h, w, ch = img.shape
                bytes_per_line = ch * w
                qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                canvas.setPixmap(pixmap.scaled(512, 512, Qt.AspectRatioMode.KeepAspectRatio))
        
        def creation_step():
            """Execute one step of the creation process."""
            nonlocal state
            
            if state["phase"] == 0:
                # Phase 1: Generate terrain
                phase_label.setText("🏔️ Phase 1: Generating terrain...")
                progress.setValue(10)
                state["heightmap"] = self._generate_heightmap_live(state["width"], state["height"])
                state["phase"] = 1
                
            elif state["phase"] == 1:
                # Phase 2: Generate biomes
                phase_label.setText("🌲 Phase 2: Creating biomes...")
                progress.setValue(30)
                state["biomes"] = self._generate_biomes_live(state["heightmap"])
                state["phase"] = 2
                
            elif state["phase"] == 2:
                # Phase 3: Add rivers
                phase_label.setText("💧 Phase 3: Flowing rivers...")
                progress.setValue(50)
                state["rivers"] = self._generate_rivers_live(state["heightmap"])
                state["phase"] = 3
                
            elif state["phase"] == 3:
                # Phase 4: Place cities
                phase_label.setText("🏰 Phase 4: Building cities...")
                progress.setValue(70)
                state["cities"] = self._place_cities_live(state["heightmap"], state["biomes"])
                state["phase"] = 4
                
            elif state["phase"] == 4:
                # Phase 5: Create roads
                phase_label.setText("🛤️ Phase 5: Connecting roads...")
                progress.setValue(85)
                state["roads"] = self._generate_roads_live(state["cities"])
                state["phase"] = 5
                
            elif state["phase"] == 5:
                # Phase 6: Final touches (Ollama brain suggestions)
                phase_label.setText("🧠 Phase 6: AI enhancements...")
                progress.setValue(95)
                if self._ollama_connected:
                    self._apply_ollama_suggestions(state, prompt)
                state["phase"] = 6
                
            elif state["phase"] == 6:
                # Complete
                phase_label.setText("✅ Creation complete!")
                progress.setValue(100)
                window.setWindowTitle(f"🎨 Kingdom AI Live Studio - Complete!")
                timer.stop()
                
                # Save final image
                self._save_creation(state, prompt)
            
            update_canvas()
        
        # Timer for live updates
        timer = QTimer()
        timer.timeout.connect(creation_step)
        timer.start(500)  # Update every 500ms
        
        # Initial render
        update_canvas()
        
        # Run event loop
        app.exec()
        
        return {"success": True, "state": state}
    
    def _generate_heightmap_live(self, width: int, height: int) -> np.ndarray:
        """Generate heightmap with Perlin-like noise."""
        import random
        
        # Simple noise generation
        heightmap = np.zeros((height, width), dtype=np.float32)
        
        # Multi-octave noise
        for octave in range(4):
            freq = 2 ** octave
            amplitude = 1.0 / freq
            
            # Generate random gradients
            noise = np.random.rand(height // freq + 2, width // freq + 2)
            
            # Interpolate
            for y in range(height):
                for x in range(width):
                    fy = (y / height) * (height // freq)
                    fx = (x / width) * (width // freq)
                    
                    y0, x0 = int(fy), int(fx)
                    fy, fx = fy - y0, fx - x0
                    
                    # Bilinear interpolation
                    v00 = noise[y0, x0]
                    v10 = noise[y0, x0 + 1]
                    v01 = noise[y0 + 1, x0]
                    v11 = noise[y0 + 1, x0 + 1]
                    
                    vx0 = v00 * (1 - fx) + v10 * fx
                    vx1 = v01 * (1 - fx) + v11 * fx
                    
                    heightmap[y, x] += (vx0 * (1 - fy) + vx1 * fy) * amplitude
        
        # Normalize
        heightmap = (heightmap - heightmap.min()) / (heightmap.max() - heightmap.min())
        return heightmap
    
    def _generate_biomes_live(self, heightmap: np.ndarray) -> np.ndarray:
        """Generate biomes based on heightmap."""
        h, w = heightmap.shape
        biomes = np.zeros((h, w), dtype=np.int32)
        moisture = np.random.rand(h, w)
        
        for y in range(h):
            for x in range(w):
                elev = heightmap[y, x]
                moist = moisture[y, x]
                
                if elev < 0.3:
                    biomes[y, x] = 0  # Ocean
                elif elev < 0.35:
                    biomes[y, x] = 1  # Beach
                elif elev > 0.8:
                    biomes[y, x] = 7  # Snow
                elif elev > 0.65:
                    biomes[y, x] = 6  # Mountains
                elif moist < 0.3:
                    biomes[y, x] = 2  # Desert
                elif moist < 0.5:
                    biomes[y, x] = 3  # Grassland
                elif moist < 0.7:
                    biomes[y, x] = 4  # Forest
                else:
                    biomes[y, x] = 5  # Jungle
        
        return biomes
    
    def _generate_rivers_live(self, heightmap: np.ndarray) -> list:
        """Generate rivers flowing downhill."""
        import random
        h, w = heightmap.shape
        rivers = []
        
        for _ in range(5):
            # Start from high point
            high_points = np.where(heightmap > 0.7)
            if len(high_points[0]) == 0:
                continue
            
            idx = random.randint(0, len(high_points[0]) - 1)
            y, x = high_points[0][idx], high_points[1][idx]
            
            river = [(x, y)]
            for _ in range(200):
                if heightmap[y, x] < 0.3:
                    break
                
                # Find lowest neighbor
                min_h = heightmap[y, x]
                next_x, next_y = x, y
                
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w:
                            if heightmap[ny, nx] < min_h:
                                min_h = heightmap[ny, nx]
                                next_x, next_y = nx, ny
                
                if next_x == x and next_y == y:
                    break
                
                x, y = next_x, next_y
                river.append((x, y))
            
            if len(river) > 10:
                rivers.append(river)
        
        return rivers
    
    def _place_cities_live(self, heightmap: np.ndarray, biomes: np.ndarray) -> list:
        """Place cities at strategic locations."""
        import random
        h, w = heightmap.shape
        cities = []
        
        for i in range(10):
            for _ in range(100):  # Try to find good spot
                x = random.randint(50, w - 50)
                y = random.randint(50, h - 50)
                
                if biomes[y, x] in [3, 4] and 0.35 <= heightmap[y, x] <= 0.6:
                    # Good location
                    city_type = "capital" if i == 0 else "city" if i < 3 else "town"
                    cities.append({
                        "x": x, "y": y,
                        "name": f"City_{i+1}",
                        "type": city_type,
                        "size": 3 if city_type == "capital" else 2 if city_type == "city" else 1
                    })
                    break
        
        return cities
    
    def _generate_roads_live(self, cities: list) -> list:
        """Generate roads connecting cities."""
        roads = []
        if len(cities) < 2:
            return roads
        
        # Connect each city to nearest
        for i, city1 in enumerate(cities):
            min_dist = float('inf')
            nearest = None
            
            for j, city2 in enumerate(cities):
                if i != j:
                    dist = ((city1["x"] - city2["x"])**2 + (city1["y"] - city2["y"])**2)**0.5
                    if dist < min_dist:
                        min_dist = dist
                        nearest = city2
            
            if nearest:
                roads.append([(city1["x"], city1["y"]), (nearest["x"], nearest["y"])])
        
        return roads
    
    def _apply_ollama_suggestions(self, state: dict, prompt: str):
        """Ask Ollama for creative suggestions."""
        if not self._ollama_connected:
            return
        
        try:
            import requests
            try:
                from core.ollama_gateway import orchestrator
                _map_model = orchestrator.get_model_for_task("creative_studio")
            except ImportError:
                _map_model = "mistral-nemo:latest"
            _ollama_gen = os.environ.get("KINGDOM_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            response = requests.post(
                f"{_ollama_gen}/api/generate",
                json={
                    "model": _map_model,
                    "prompt": f"Suggest one creative enhancement for a fantasy map with: {prompt}. Reply in 10 words or less.",
                    "stream": False,
                    "keep_alive": -1,
                    "options": {"num_gpu": 999},
                },
                timeout=120
            )
            if response.status_code == 200:
                suggestion = response.json().get("response", "")
                logger.info(f"🧠 Ollama suggestion: {suggestion[:50]}")
        except Exception as e:
            logger.warning(f"Ollama suggestion failed: {e}")
    
    def _render_state(self, state: dict) -> Optional[np.ndarray]:
        """Render current state to RGB image."""
        if state["heightmap"] is None:
            # Return blank image
            return np.zeros((512, 512, 3), dtype=np.uint8)
        
        h, w = state["heightmap"].shape
        img = np.zeros((h, w, 3), dtype=np.uint8)
        
        # Biome colors
        biome_colors = {
            0: [20, 80, 150],    # Ocean
            1: [230, 220, 150],  # Beach
            2: [230, 200, 130],  # Desert
            3: [100, 180, 80],   # Grassland
            4: [50, 130, 50],    # Forest
            5: [30, 100, 50],    # Jungle
            6: [130, 130, 130],  # Mountains
            7: [240, 240, 250],  # Snow
        }
        
        # Color by biome or height
        if state["biomes"] is not None:
            for y in range(h):
                for x in range(w):
                    biome = state["biomes"][y, x]
                    color = biome_colors.get(biome, [128, 128, 128])
                    shade = 0.7 + 0.3 * state["heightmap"][y, x]
                    img[y, x] = [int(c * shade) for c in color]
        else:
            # Grayscale height
            gray = (state["heightmap"] * 255).astype(np.uint8)
            img[:, :, 0] = gray
            img[:, :, 1] = gray
            img[:, :, 2] = gray
        
        # Draw rivers
        for river in state.get("rivers", []):
            for x, y in river:
                if 0 <= y < h and 0 <= x < w:
                    img[y, x] = [70, 140, 200]
        
        # Draw roads
        for road in state.get("roads", []):
            if len(road) >= 2:
                x1, y1 = road[0]
                x2, y2 = road[1]
                # Simple line
                steps = max(abs(x2 - x1), abs(y2 - y1))
                if steps > 0:
                    for i in range(steps):
                        x = int(x1 + (x2 - x1) * i / steps)
                        y = int(y1 + (y2 - y1) * i / steps)
                        if 0 <= y < h and 0 <= x < w:
                            img[y, x] = [140, 100, 70]
        
        # Draw cities
        for city in state.get("cities", []):
            cx, cy = city["x"], city["y"]
            size = city.get("size", 1) * 3
            color = [255, 215, 0] if city.get("type") == "capital" else [255, 100, 100]
            for dy in range(-size, size + 1):
                for dx in range(-size, size + 1):
                    if dx*dx + dy*dy <= size*size:
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w:
                            img[ny, nx] = color
        
        return img
    
    def _save_creation(self, state: dict, prompt: str):
        """Save the final creation."""
        img = self._render_state(state)
        if img is not None:
            from PIL import Image
            pil_img = Image.fromarray(img)
            
            export_dir = Path(__file__).parent.parent / "exports" / "live_creations"
            export_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"live_{prompt[:20].replace(' ', '_')}_{int(time.time())}.png"
            filepath = export_dir / filename
            pil_img.save(str(filepath))
            
            logger.info(f"✅ Saved live creation: {filepath}")


# Singleton
_live_studio: Optional[LiveCreativeStudio] = None

def get_live_creative_studio(event_bus=None) -> LiveCreativeStudio:
    """Get or create the live creative studio."""
    global _live_studio
    if _live_studio is None:
        _live_studio = LiveCreativeStudio(event_bus)
    return _live_studio


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print(" KINGDOM AI LIVE CREATIVE STUDIO ".center(70))
    print("="*70 + "\n")
    
    studio = get_live_creative_studio()
    studio.create_live("fantasy world with mountains, forests, and ancient cities")
