#!/usr/bin/env python3
"""
GPU Scheduler - SOTA 2026 Dual GPU Workload Manager
====================================================
Manages concurrent GPU operations across dual RTX 4060 GPUs.
Prevents VRAM exhaustion, thermal overload, and resource conflicts.

ARCHITECTURE:
- GPU 0 (cuda:0): Image Generation (8GB VRAM), Video Generation (fallback)
- GPU 1 (cuda:1): Trading AI (2GB), Thoth Inference (3GB), spare capacity

FEATURES:
- Automatic device assignment based on component type
- VRAM monitoring and overflow prevention
- Thermal monitoring with auto-throttling
- Request queuing when GPU is busy
- Priority-based GPU access (trading > inference > creation)
"""
import os
import threading
import time
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger("KingdomAI.GPUScheduler")


class GPUPriority(Enum):
    """GPU task priority levels."""
    CRITICAL = 1    # Trading AI, real-time inference
    HIGH = 2        # Image generation, video generation
    NORMAL = 3      # Background inference, medical reconstruction
    LOW = 4         # Batch processing, analytics


@dataclass
class GPURequest:
    """GPU computation request."""
    component: str
    priority: GPUPriority
    estimated_vram_gb: float
    estimated_duration_sec: float
    callback: Any = None
    request_id: str = ""


class GPUScheduler:
    """
    SOTA 2026 GPU Scheduler for Dual RTX 4060 System.
    
    Manages concurrent GPU operations to prevent:
    - VRAM exhaustion (10.6GB demand > 8GB available)
    - Thermal overload (both GPUs at 100% → 85°C+)
    - Resource conflicts (2 models loading to same device)
    """
    
    def __init__(self):
        """Initialize GPU scheduler with dual GPU support."""
        self._lock = threading.RLock()
        self._gpu_available = self._detect_gpus()
        self._device_map = self._create_device_map()
        self._active_tasks: Dict[str, GPURequest] = {}
        self._queue: deque = deque()  # Priority queue
        
        # VRAM tracking (RTX 4060 = 8GB each)
        self._vram_capacity_gb = {0: 8.0, 1: 8.0}
        self._vram_used_gb = {0: 0.0, 1: 0.0}
        
        # Thermal tracking
        self._gpu_temps = {0: 0.0, 1: 0.0}
        self._thermal_throttle_threshold = 80.0  # °C
        self._thermal_throttle_active = {0: False, 1: False}
        
        # Monitoring
        self._monitoring_thread = None
        self._shutdown = False
        
        logger.info(f"✅ GPU Scheduler initialized - Detected {len(self._gpu_available)} GPU(s)")
        for gpu_id in self._gpu_available:
            logger.info(f"   GPU {gpu_id}: {self._vram_capacity_gb[gpu_id]:.1f}GB VRAM")
    
    def _detect_gpus(self) -> List[int]:
        """Detect available CUDA GPUs."""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                logger.info(f"🔍 Detected {gpu_count} CUDA GPU(s)")
                return list(range(gpu_count))
            else:
                logger.warning("⚠️ No CUDA GPUs detected - falling back to CPU")
                return []
        except ImportError:
            logger.warning("⚠️ PyTorch not available - GPU scheduler disabled")
            return []
    
    def _create_device_map(self) -> Dict[str, int]:
        """Create optimal device assignment map for components.
        
        Returns:
            Dict mapping component names to GPU IDs (0 or 1)
        """
        if len(self._gpu_available) == 0:
            return {}
        elif len(self._gpu_available) == 1:
            # Single GPU - all workloads share cuda:0
            return {
                'image_generation': 0,
                'video_generation': 0,
                'trading_ai': 0,
                'thoth_inference': 0,
                'medical_reconstruction': 0,
                'cinema_engine': 0,
            }
        else:
            # Dual GPU - optimal distribution
            return {
                'image_generation': 0,      # 8.6GB model → GPU 0
                'video_generation': 0,      # Fallback to GPU 0 (Redis service)
                'cinema_engine': 0,         # Will GPU-accelerate → GPU 0
                'trading_ai': 1,            # 2GB model → GPU 1
                'thoth_inference': 1,       # 2-3GB models → GPU 1
                'medical_reconstruction': 1, # Will GPU-accelerate → GPU 1
                'background_inference': 1,  # GPU 1 has spare capacity
            }
    
    def get_device(self, component: str) -> str:
        """Get optimal device for component.
        
        Args:
            component: Component name (e.g., 'image_generation', 'trading_ai')
            
        Returns:
            Device string (e.g., 'cuda:0', 'cuda:1', 'cpu')
        """
        with self._lock:
            if len(self._gpu_available) == 0:
                return 'cpu'
            
            gpu_id = self._device_map.get(component, 0)  # Default to GPU 0
            
            # Check if thermal throttle is active
            if self._thermal_throttle_active.get(gpu_id, False):
                # Try alternate GPU
                alternate = 1 - gpu_id if len(self._gpu_available) > 1 else gpu_id
                if not self._thermal_throttle_active.get(alternate, False):
                    logger.warning(f"🌡️ GPU {gpu_id} throttled, redirecting {component} to GPU {alternate}")
                    return f'cuda:{alternate}'
                else:
                    logger.warning(f"🌡️ All GPUs throttled, using CPU for {component}")
                    return 'cpu'
            
            return f'cuda:{gpu_id}'
    
    def request_gpu(self, request: GPURequest) -> Optional[str]:
        """Request GPU access for a component.
        
        Args:
            request: GPURequest with component, priority, VRAM estimate
            
        Returns:
            Device string if granted, None if queued
        """
        with self._lock:
            device_str = self.get_device(request.component)
            
            if device_str == 'cpu':
                return device_str
            
            gpu_id = int(device_str.split(':')[1])
            required_vram = request.estimated_vram_gb
            available_vram = self._vram_capacity_gb[gpu_id] - self._vram_used_gb[gpu_id]
            
            if available_vram >= required_vram:
                # Grant access
                self._vram_used_gb[gpu_id] += required_vram
                self._active_tasks[request.request_id] = request
                logger.info(f"✅ GPU {gpu_id} granted to {request.component} ({required_vram:.1f}GB, {available_vram:.1f}GB remaining)")
                return device_str
            else:
                # Queue request
                self._queue.append(request)
                logger.warning(f"⏳ GPU {gpu_id} busy - queued {request.component} (need {required_vram:.1f}GB, have {available_vram:.1f}GB)")
                return None
    
    def release_gpu(self, request_id: str):
        """Release GPU after task completes."""
        with self._lock:
            if request_id not in self._active_tasks:
                return
            
            request = self._active_tasks.pop(request_id)
            device_str = self.get_device(request.component)
            
            if device_str.startswith('cuda'):
                gpu_id = int(device_str.split(':')[1])
                self._vram_used_gb[gpu_id] -= request.estimated_vram_gb
                self._vram_used_gb[gpu_id] = max(0, self._vram_used_gb[gpu_id])  # Clamp to 0
                logger.info(f"✅ Released {request.component} from GPU {gpu_id} ({request.estimated_vram_gb:.1f}GB freed)")
            
            # Process queued requests
            self._process_queue()
    
    def _process_queue(self):
        """Process queued GPU requests (called with lock held)."""
        if not self._queue:
            return
        
        # Sort by priority
        sorted_queue = sorted(self._queue, key=lambda r: r.priority.value)
        self._queue.clear()
        
        for req in sorted_queue:
            device = self.request_gpu(req)
            if device:
                # Grant succeeded - notify callback
                if req.callback:
                    req.callback(device)
            else:
                # Still no capacity - re-queue
                self._queue.append(req)
    
    def update_thermal_status(self):
        """Update GPU temperatures and throttle state.
        
        Uses torch.cuda.temperature() or nvidia-ml-py.
        """
        if len(self._gpu_available) == 0:
            return
        
        try:
            import torch
            
            for gpu_id in self._gpu_available:
                try:
                    # Try torch.cuda.temperature() (PyTorch 2.10+)
                    if hasattr(torch.cuda, 'temperature'):
                        temp = torch.cuda.temperature(gpu_id)
                        self._gpu_temps[gpu_id] = temp
                    else:
                        # Fallback to pynvml
                        import pynvml
                        if not hasattr(self, '_nvml_initialized'):
                            pynvml.nvmlInit()
                            self._nvml_initialized = True
                        
                        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
                        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                        self._gpu_temps[gpu_id] = temp
                    
                    # Check throttle threshold
                    was_throttled = self._thermal_throttle_active[gpu_id]
                    is_throttled = temp >= self._thermal_throttle_threshold
                    
                    if is_throttled and not was_throttled:
                        logger.warning(f"🌡️ GPU {gpu_id} THERMAL THROTTLE ACTIVATED ({temp}°C ≥ {self._thermal_throttle_threshold}°C)")
                        self._thermal_throttle_active[gpu_id] = True
                    elif not is_throttled and was_throttled:
                        logger.info(f"🌡️ GPU {gpu_id} thermal throttle RELEASED ({temp}°C)")
                        self._thermal_throttle_active[gpu_id] = False
                    
                except Exception as e:
                    logger.debug(f"GPU {gpu_id} temp read error: {e}")
        
        except ImportError:
            pass  # PyTorch or pynvml not available
    
    def start_monitoring(self, interval_sec: float = 5.0):
        """Start thermal monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
        
        def _monitor_loop():
            logger.info(f"🌡️ GPU thermal monitoring started (interval: {interval_sec}s)")
            while not self._shutdown:
                self.update_thermal_status()
                time.sleep(interval_sec)
            logger.info("🌡️ GPU thermal monitoring stopped")
        
        self._monitoring_thread = threading.Thread(target=_monitor_loop, daemon=True, name="GPUThermalMonitor")
        self._monitoring_thread.start()
    
    def shutdown(self):
        """Shutdown scheduler and monitoring."""
        self._shutdown = True
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=2)
        logger.info("✅ GPU Scheduler shutdown complete")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current GPU scheduler status."""
        with self._lock:
            return {
                'gpus': len(self._gpu_available),
                'vram_used': self._vram_used_gb.copy(),
                'vram_capacity': self._vram_capacity_gb.copy(),
                'temperatures': self._gpu_temps.copy(),
                'throttled': self._thermal_throttle_active.copy(),
                'active_tasks': len(self._active_tasks),
                'queued_tasks': len(self._queue),
            }


# Global singleton
_gpu_scheduler = None
_gpu_scheduler_lock = threading.Lock()


def get_gpu_scheduler() -> GPUScheduler:
    """Get or create global GPU scheduler singleton."""
    global _gpu_scheduler
    with _gpu_scheduler_lock:
        if _gpu_scheduler is None:
            _gpu_scheduler = GPUScheduler()
            _gpu_scheduler.start_monitoring(interval_sec=5.0)
        return _gpu_scheduler
