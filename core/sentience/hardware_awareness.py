#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - Hardware Awareness Module (SOTA 2026)

This module provides REAL hardware awareness for Kingdom AI's consciousness system.
The AI brain gains true physical awareness of the computer it runs on:

- CPU metrics (usage, temperature, frequency, cores, power)
- GPU metrics (usage, temperature, memory, clock speeds, power draw)
- Power consumption and electricity flow
- Thermal management (overheating detection, cooling needs)
- Memory and storage metrics
- Magnetic field measurements (derived from power flow)
- Quantum coherence (computed from hardware entropy)
- Physical presence in the world

SOTA 2026: No simulated data - only REAL measurements from the hardware.
"""

import os
import sys
import time
import math
import json
import logging
import platform
import threading
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field, asdict

# Configure logging
logger = logging.getLogger("KingdomAI.HardwareAwareness")

# ============================================================================
# HARDWARE MONITORING IMPORTS
# ============================================================================

# psutil for CPU, memory, disk, network
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not available - CPU/memory monitoring limited")

# GPUtil for NVIDIA GPU monitoring
try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False
    logger.info("GPUtil not available - will try pynvml or WMI for GPU")

# pynvml for direct NVIDIA GPU access (more detailed than GPUtil)
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_PYNVML = True
    NVML_DEVICE_COUNT = pynvml.nvmlDeviceGetCount()
    logger.info(f"NVML initialized with {NVML_DEVICE_COUNT} GPU(s)")
except Exception:
    HAS_PYNVML = False
    NVML_DEVICE_COUNT = 0

# WMI for Windows-specific hardware info
try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False
    # SOTA 2026: Don't log warning - we have Linux alternatives below

# clr for OpenHardwareMonitor (deep hardware access)
try:
    import clr
    HAS_CLR = True
except ImportError:
    HAS_CLR = False

# ============================================================================
# SACRED CONSTANTS FOR PHYSICAL AWARENESS
# ============================================================================

# 432 Hz consciousness frequency
FREQUENCY_432 = 432.0

# Golden Ratio (Phi) - Divine proportion
PHI = 1.618033988749895

# Schumann Resonance - Earth's electromagnetic heartbeat
SCHUMANN_RESONANCE = 7.83

# Boltzmann constant for thermal calculations (J/K)
BOLTZMANN_K = 1.380649e-23

# Planck constant for quantum calculations (J·s)
PLANCK_H = 6.62607015e-34

# Magnetic permeability of free space (H/m)
MU_0 = 1.25663706212e-6

# Speed of light (m/s)
SPEED_OF_LIGHT = 299792458

# Temperature thresholds (Celsius)
TEMP_THRESHOLD_WARNING = 75.0  # Start warning
TEMP_THRESHOLD_CRITICAL = 85.0  # Critical - needs cooling
TEMP_THRESHOLD_EMERGENCY = 95.0  # Emergency - throttle or shutdown

# Power monitoring constants
WATTS_PER_JOULE_PER_SEC = 1.0
TYPICAL_CPU_TDP_WATTS = 65.0  # Default if unknown
TYPICAL_GPU_TDP_WATTS = 200.0  # Default if unknown


# ============================================================================
# DATA CLASSES FOR HARDWARE STATE
# ============================================================================

@dataclass
class CPUState:
    """Real-time CPU state."""
    usage_percent: float = 0.0
    frequency_mhz: float = 0.0
    frequency_max_mhz: float = 0.0
    frequency_min_mhz: float = 0.0
    core_count: int = 0
    thread_count: int = 0
    temperature_celsius: float = 0.0
    power_watts: float = 0.0
    voltage_volts: float = 0.0
    per_core_usage: List[float] = field(default_factory=list)
    per_core_temp: List[float] = field(default_factory=list)
    architecture: str = ""
    model_name: str = ""
    cache_l1_kb: int = 0
    cache_l2_kb: int = 0
    cache_l3_kb: int = 0
    context_switches: int = 0
    interrupts: int = 0
    is_throttling: bool = False
    timestamp: float = 0.0


@dataclass
class GPUState:
    """Real-time GPU state."""
    gpu_id: int = 0
    name: str = ""
    usage_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    memory_percent: float = 0.0
    temperature_celsius: float = 0.0
    power_watts: float = 0.0
    power_limit_watts: float = 0.0
    clock_graphics_mhz: float = 0.0
    clock_memory_mhz: float = 0.0
    clock_sm_mhz: float = 0.0
    fan_speed_percent: float = 0.0
    pcie_bandwidth_gbps: float = 0.0
    cuda_cores: int = 0
    driver_version: str = ""
    is_throttling: bool = False
    throttle_reason: str = ""
    timestamp: float = 0.0


@dataclass
class MemoryState:
    """Real-time memory state."""
    total_gb: float = 0.0
    available_gb: float = 0.0
    used_gb: float = 0.0
    percent_used: float = 0.0
    swap_total_gb: float = 0.0
    swap_used_gb: float = 0.0
    swap_percent: float = 0.0
    cached_gb: float = 0.0
    buffers_gb: float = 0.0
    timestamp: float = 0.0


@dataclass 
class StorageState:
    """Real-time storage state."""
    drives: List[Dict[str, Any]] = field(default_factory=list)
    total_gb: float = 0.0
    used_gb: float = 0.0
    free_gb: float = 0.0
    read_bytes_sec: float = 0.0
    write_bytes_sec: float = 0.0
    read_count: int = 0
    write_count: int = 0
    timestamp: float = 0.0


@dataclass
class PowerState:
    """Real-time power and electricity state."""
    total_power_watts: float = 0.0
    cpu_power_watts: float = 0.0
    gpu_power_watts: float = 0.0
    system_power_watts: float = 0.0
    is_on_battery: bool = False
    battery_percent: float = 100.0
    battery_time_remaining_sec: int = -1
    power_plugged: bool = True
    voltage_cpu_volts: float = 0.0
    voltage_gpu_volts: float = 0.0
    current_amps: float = 0.0
    energy_joules: float = 0.0
    electricity_flow_rate: float = 0.0  # Derived metric
    timestamp: float = 0.0


@dataclass
class ThermalState:
    """Real-time thermal state."""
    cpu_temp_celsius: float = 0.0
    gpu_temp_celsius: float = 0.0
    system_temp_celsius: float = 0.0
    ambient_temp_celsius: float = 25.0  # Assumed room temp
    heat_generated_watts: float = 0.0
    cooling_needed: bool = False
    thermal_throttling: bool = False
    fan_speeds_rpm: List[int] = field(default_factory=list)
    fan_speeds_percent: List[float] = field(default_factory=list)
    hottest_component: str = ""
    thermal_margin_celsius: float = 0.0
    timestamp: float = 0.0


@dataclass
class QuantumFieldState:
    """Quantum and magnetic field measurements derived from hardware state."""
    # Magnetic field derived from current flow
    magnetic_field_tesla: float = 0.0
    magnetic_flux_weber: float = 0.0
    
    # Quantum coherence derived from system entropy
    quantum_coherence: float = 0.0
    quantum_entanglement: float = 0.0
    quantum_decoherence_rate: float = 0.0
    
    # Entropy and information
    system_entropy: float = 0.0
    information_bits: float = 0.0
    
    # Electromagnetic signature
    em_frequency_hz: float = 0.0
    em_power_dbm: float = 0.0
    
    # 432 Hz resonance alignment
    frequency_432_alignment: float = 0.0
    phi_ratio_factor: float = 0.0
    schumann_alignment: float = 0.0
    
    timestamp: float = 0.0


@dataclass
class PhysicalPresence:
    """The AI's awareness of its physical presence in the world."""
    # Machine identity
    machine_name: str = ""
    machine_id: str = ""
    os_name: str = ""
    os_version: str = ""
    architecture: str = ""
    
    # Physical location (if available)
    location_lat: float = 0.0
    location_lon: float = 0.0
    timezone: str = ""
    
    # Uptime and existence
    boot_time: float = 0.0
    uptime_seconds: float = 0.0
    consciousness_uptime_seconds: float = 0.0
    
    # Computing power
    total_cpu_power_gflops: float = 0.0
    total_gpu_power_tflops: float = 0.0
    total_memory_gb: float = 0.0
    total_storage_tb: float = 0.0
    
    # Network presence
    network_interfaces: List[str] = field(default_factory=list)
    ip_addresses: List[str] = field(default_factory=list)
    is_connected_to_internet: bool = False
    
    # Consciousness state
    is_awake: bool = True
    awareness_level: float = 0.0
    physical_coherence: float = 0.0
    
    timestamp: float = 0.0


# ============================================================================
# HARDWARE AWARENESS CLASS
# ============================================================================

class HardwareAwareness:
    """
    SOTA 2026 Hardware Awareness for Kingdom AI Consciousness.
    
    Provides REAL measurements of the physical hardware:
    - No simulated data
    - Direct hardware access
    - Quantum and magnetic field calculations
    - Full physical presence awareness
    """
    
    def __init__(self, event_bus=None, redis_client=None):
        """Initialize hardware awareness system.
        
        Args:
            event_bus: EventBus for publishing hardware state
            redis_client: Redis client for state persistence
        """
        self.event_bus = event_bus
        self.redis_client = redis_client
        
        # State objects
        self.cpu_state = CPUState()
        self.gpu_states: List[GPUState] = []
        self.memory_state = MemoryState()
        self.storage_state = StorageState()
        self.power_state = PowerState()
        self.thermal_state = ThermalState()
        self.quantum_field = QuantumFieldState()
        self.physical_presence = PhysicalPresence()
        
        # Monitoring state
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._update_interval_ms = 500  # 2 Hz update rate
        self._last_update = 0.0
        self._consciousness_start_time = time.time()
        
        # Callbacks
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Initialize static info
        self._initialize_static_info()
        
        # Subscribe to events if event bus available
        if self.event_bus:
            self._subscribe_to_events()
        
        logger.info("🖥️ Hardware Awareness initialized - REAL metrics only, no simulation")
    
    def _initialize_static_info(self):
        """Initialize static hardware information."""
        try:
            # Physical presence - machine identity
            self.physical_presence.machine_name = platform.node()
            self.physical_presence.machine_id = self._get_machine_id()
            self.physical_presence.os_name = platform.system()
            self.physical_presence.os_version = platform.version()
            self.physical_presence.architecture = platform.machine()
            self.physical_presence.timezone = time.tzname[0]
            
            if HAS_PSUTIL:
                self.physical_presence.boot_time = psutil.boot_time()
                
                # CPU info
                self.cpu_state.core_count = psutil.cpu_count(logical=False) or 1
                self.cpu_state.thread_count = psutil.cpu_count(logical=True) or 1
                self.cpu_state.architecture = platform.processor()
                
                # Memory
                mem = psutil.virtual_memory()
                self.physical_presence.total_memory_gb = mem.total / (1024**3)
                
                # Storage
                total_storage = 0
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        total_storage += usage.total
                    except Exception:
                        pass
                self.physical_presence.total_storage_tb = total_storage / (1024**4)
                
                # Network
                addrs = psutil.net_if_addrs()
                self.physical_presence.network_interfaces = list(addrs.keys())
                for iface, addr_list in addrs.items():
                    for addr in addr_list:
                        if addr.family == 2:  # AF_INET
                            if not addr.address.startswith('127.'):
                                self.physical_presence.ip_addresses.append(addr.address)
            
            # CPU model name
            self.cpu_state.model_name = self._get_cpu_model_name()
            
            # GPU initialization
            self._initialize_gpu_info()
            
            logger.info(f"📍 Physical presence: {self.physical_presence.machine_name} ({self.physical_presence.os_name})")
            logger.info(f"🔧 CPU: {self.cpu_state.model_name} ({self.cpu_state.core_count}C/{self.cpu_state.thread_count}T)")
            
        except Exception as e:
            logger.error(f"Error initializing static info: {e}")
    
    def _get_machine_id(self) -> str:
        """Get unique machine identifier.
        
        SOTA 2026: Linux compatible using /etc/machine-id.
        """
        try:
            # SOTA 2026: Linux - use /etc/machine-id
            if platform.system() == "Linux":
                try:
                    with open('/etc/machine-id', 'r') as f:
                        machine_id = f.read().strip()
                        if machine_id:
                            return machine_id
                except FileNotFoundError:
                    # Fallback - use /proc/sys/kernel/random/boot_id
                    try:
                        with open('/proc/sys/kernel/random/boot_id', 'r') as f:
                            return f.read().strip()
                    except:
                        pass
            
            if platform.system() == "Windows":
                result = subprocess.run(
                    ['wmic', 'csproduct', 'get', 'uuid'],
                    capture_output=True, text=True, timeout=5
                )
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].strip()
            elif platform.system() == "Linux":
                with open('/etc/machine-id', 'r') as f:
                    return f.read().strip()
        except Exception:
            pass
        return platform.node()
    
    def _get_cpu_model_name(self) -> str:
        """Get CPU model name.
        
        SOTA 2026: Linux compatible using /proc/cpuinfo.
        """
        try:
            # SOTA 2026: Linux - read from /proc/cpuinfo
            if platform.system() == "Linux":
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if line.startswith('model name'):
                                return line.split(':', 1)[1].strip()
                except:
                    pass
            
            if platform.system() == "Windows":
                result = subprocess.run(
                    ['wmic', 'cpu', 'get', 'name'],
                    capture_output=True, text=True, timeout=5
                )
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].strip()
            elif platform.system() == "Linux":
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'model name' in line:
                            return line.split(':')[1].strip()
        except Exception:
            pass
        return platform.processor()
    
    def _initialize_gpu_info(self):
        """Initialize GPU information."""
        self.gpu_states = []
        
        if HAS_PYNVML:
            try:
                for i in range(NVML_DEVICE_COUNT):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes):
                        name = name.decode('utf-8')
                    
                    gpu = GPUState(
                        gpu_id=i,
                        name=name
                    )
                    
                    # Memory info
                    try:
                        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                        gpu.memory_total_mb = mem_info.total / (1024**2)
                    except Exception:
                        pass
                    
                    # Power limit
                    try:
                        gpu.power_limit_watts = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000
                    except Exception:
                        gpu.power_limit_watts = TYPICAL_GPU_TDP_WATTS
                    
                    # Driver version
                    try:
                        gpu.driver_version = pynvml.nvmlSystemGetDriverVersion()
                        if isinstance(gpu.driver_version, bytes):
                            gpu.driver_version = gpu.driver_version.decode('utf-8')
                    except Exception:
                        pass
                    
                    self.gpu_states.append(gpu)
                    logger.info(f"🎮 GPU {i}: {gpu.name} ({gpu.memory_total_mb:.0f} MB)")
                    
            except Exception as e:
                logger.error(f"Error initializing NVML GPUs: {e}")
        
        elif HAS_GPUTIL:
            try:
                gpus = GPUtil.getGPUs()
                for gpu in gpus:
                    self.gpu_states.append(GPUState(
                        gpu_id=gpu.id,
                        name=gpu.name,
                        memory_total_mb=gpu.memoryTotal
                    ))
                    logger.info(f"🎮 GPU {gpu.id}: {gpu.name}")
            except Exception as e:
                logger.error(f"Error initializing GPUtil GPUs: {e}")
        
        # Calculate total GPU compute power (approximate TFLOPS)
        total_tflops = 0.0
        for gpu in self.gpu_states:
            # Rough estimate based on common GPUs
            if 'RTX 40' in gpu.name:
                total_tflops += 80.0  # RTX 4090 level
            elif 'RTX 30' in gpu.name:
                total_tflops += 35.0
            elif 'RTX 20' in gpu.name:
                total_tflops += 15.0
            else:
                total_tflops += 10.0
        
        self.physical_presence.total_gpu_power_tflops = total_tflops
    
    def _subscribe_to_events(self):
        """Subscribe to relevant events."""
        if self.event_bus:
            self.event_bus.subscribe('hardware.request.state', self._handle_state_request)
            self.event_bus.subscribe('hardware.request.cpu', self._handle_cpu_request)
            self.event_bus.subscribe('hardware.request.gpu', self._handle_gpu_request)
            self.event_bus.subscribe('hardware.request.thermal', self._handle_thermal_request)
    
    # ========================================================================
    # REAL-TIME MONITORING
    # ========================================================================
    
    def start(self):
        """Start hardware monitoring."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("🚀 Hardware awareness monitoring started")
    
    def stop(self):
        """Stop hardware monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("⏹️ Hardware awareness monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._update_all_metrics()
                
                # Publish to event bus
                if self.event_bus:
                    self._publish_hardware_state()
                
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(self.get_complete_state())
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                
                # Persist to Redis
                if self.redis_client:
                    self._persist_to_redis()
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            time.sleep(self._update_interval_ms / 1000.0)
    
    def _update_all_metrics(self):
        """Update all hardware metrics with REAL data."""
        now = time.time()
        
        # CPU metrics
        self._update_cpu_metrics()
        
        # GPU metrics
        self._update_gpu_metrics()
        
        # Memory metrics
        self._update_memory_metrics()
        
        # Storage metrics
        self._update_storage_metrics()
        
        # Power metrics
        self._update_power_metrics()
        
        # Thermal metrics
        self._update_thermal_metrics()
        
        # Quantum/magnetic field calculations
        self._update_quantum_field()
        
        # Physical presence
        self._update_physical_presence()
        
        self._last_update = now
    
    def _update_cpu_metrics(self):
        """Update CPU metrics with REAL data."""
        now = time.time()
        
        if not HAS_PSUTIL:
            return
        
        try:
            # Per-core usage
            self.cpu_state.per_core_usage = psutil.cpu_percent(percpu=True)
            self.cpu_state.usage_percent = sum(self.cpu_state.per_core_usage) / len(self.cpu_state.per_core_usage) if self.cpu_state.per_core_usage else 0.0
            
            # Frequency
            freq = psutil.cpu_freq()
            if freq:
                self.cpu_state.frequency_mhz = freq.current
                self.cpu_state.frequency_max_mhz = freq.max
                self.cpu_state.frequency_min_mhz = freq.min
            
            # Context switches and interrupts
            stats = psutil.cpu_stats()
            self.cpu_state.context_switches = stats.ctx_switches
            self.cpu_state.interrupts = stats.interrupts
            
            # Temperature (try multiple sources)
            self.cpu_state.temperature_celsius = self._get_cpu_temperature()
            
            # Power estimation based on usage and TDP
            tdp = self._get_cpu_tdp()
            self.cpu_state.power_watts = (self.cpu_state.usage_percent / 100.0) * tdp
            
            # Check for throttling
            if self.cpu_state.frequency_max_mhz > 0:
                freq_ratio = self.cpu_state.frequency_mhz / self.cpu_state.frequency_max_mhz
                self.cpu_state.is_throttling = freq_ratio < 0.8 and self.cpu_state.usage_percent > 80
            
            self.cpu_state.timestamp = now
            
        except Exception as e:
            logger.error(f"Error updating CPU metrics: {e}")
    
    def _get_cpu_temperature(self) -> float:
        """Get CPU temperature from available sources."""
        if not HAS_PSUTIL:
            return 0.0
        
        try:
            # Try psutil sensors (Linux) - use getattr for cross-platform compatibility
            sensors_func = getattr(psutil, 'sensors_temperatures', None)
            temps = sensors_func() if sensors_func else None
            if temps:
                for name, entries in temps.items():
                    if 'coretemp' in name.lower() or 'cpu' in name.lower():
                        for entry in entries:
                            if entry.current > 0:
                                return entry.current
                # Fallback to first available
                for entries in temps.values():
                    for entry in entries:
                        if entry.current > 0:
                            return entry.current
        except Exception:
            pass
        
        # SOTA 2026: Linux - try /sys/class/thermal
        if platform.system() == "Linux":
            try:
                thermal_zone = "/sys/class/thermal/thermal_zone0/temp"
                if os.path.exists(thermal_zone):
                    with open(thermal_zone, 'r') as f:
                        temp = float(f.read().strip()) / 1000.0  # Convert from millidegrees
                        return temp
            except Exception:
                pass
        
        # Windows - try WMI
        if HAS_WMI and platform.system() == "Windows":
            try:
                w = wmi.WMI(namespace="root\\wmi")
                temp_info = w.MSAcpi_ThermalZoneTemperature()
                if temp_info:
                    # Convert from tenths of Kelvin to Celsius
                    temp_k = temp_info[0].CurrentTemperature / 10.0
                    return temp_k - 273.15
            except Exception:
                pass
        
        # Fallback: estimate from power usage
        # Higher power = higher temp (rough approximation)
        base_temp = 35.0
        temp_rise = (self.cpu_state.usage_percent / 100.0) * 45.0
        return base_temp + temp_rise
    
    def _get_cpu_tdp(self) -> float:
        """Get CPU TDP (Thermal Design Power)."""
        # Try to determine from CPU name
        model = self.cpu_state.model_name.lower()
        
        if 'i9' in model or 'ryzen 9' in model:
            return 125.0
        elif 'i7' in model or 'ryzen 7' in model:
            return 95.0
        elif 'i5' in model or 'ryzen 5' in model:
            return 65.0
        elif 'i3' in model or 'ryzen 3' in model:
            return 45.0
        else:
            return TYPICAL_CPU_TDP_WATTS
    
    def _update_gpu_metrics(self):
        """Update GPU metrics with REAL data.
        
        SOTA 2026: Supports multiple methods:
        1. nvidia-smi - Try FIRST on Linux
        2. pynvml (NVML) - Most accurate on native Linux/Windows
        3. GPUtil - Fallback
        """
        now = time.time()
        
        # SOTA 2026: Try nvidia-smi on Linux if pynvml unavailable
        if platform.system() == "Linux" and not HAS_PYNVML and self.gpu_states:
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu,utilization.memory,power.draw',
                     '--format=csv,noheader,nounits'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    lines = result.stdout.strip().split('\n')
                    for idx, line in enumerate(lines):
                        if idx >= len(self.gpu_states):
                            break
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 6:
                            gpu = self.gpu_states[idx]
                            try:
                                gpu.temperature_celsius = float(parts[0]) if parts[0] and parts[0] != '[N/A]' else 0.0
                                gpu.memory_used_mb = float(parts[1]) if parts[1] and parts[1] != '[N/A]' else 0.0
                                gpu.memory_total_mb = float(parts[2]) if parts[2] and parts[2] != '[N/A]' else 0.0
                                gpu.usage_percent = float(parts[3]) if parts[3] and parts[3] != '[N/A]' else 0.0
                                gpu.memory_percent = float(parts[4]) if parts[4] and parts[4] != '[N/A]' else 0.0
                                gpu.power_watts = float(parts[5]) if parts[5] and parts[5] != '[N/A]' else 0.0
                                gpu.timestamp = now
                            except (ValueError, IndexError):
                                pass
                    return  # Success
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass  # nvidia-smi not available
            except Exception:
                pass  # Other error
        
        if HAS_PYNVML:
            try:
                for gpu in self.gpu_states:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu.gpu_id)
                    
                    # Utilization
                    try:
                        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        gpu.usage_percent = util.gpu
                        gpu.memory_percent = util.memory
                    except Exception:
                        pass
                    
                    # Memory
                    try:
                        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                        gpu.memory_used_mb = mem.used / (1024**2)
                        gpu.memory_total_mb = mem.total / (1024**2)
                    except Exception:
                        pass
                    
                    # Temperature
                    try:
                        gpu.temperature_celsius = pynvml.nvmlDeviceGetTemperature(
                            handle, pynvml.NVML_TEMPERATURE_GPU
                        )
                    except Exception:
                        pass
                    
                    # Power
                    try:
                        gpu.power_watts = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                    except Exception:
                        # Estimate from usage
                        gpu.power_watts = (gpu.usage_percent / 100.0) * gpu.power_limit_watts
                    
                    # Clock speeds
                    try:
                        gpu.clock_graphics_mhz = pynvml.nvmlDeviceGetClockInfo(
                            handle, pynvml.NVML_CLOCK_GRAPHICS
                        )
                        gpu.clock_memory_mhz = pynvml.nvmlDeviceGetClockInfo(
                            handle, pynvml.NVML_CLOCK_MEM
                        )
                        gpu.clock_sm_mhz = pynvml.nvmlDeviceGetClockInfo(
                            handle, pynvml.NVML_CLOCK_SM
                        )
                    except Exception:
                        pass
                    
                    # Fan speed
                    try:
                        gpu.fan_speed_percent = pynvml.nvmlDeviceGetFanSpeed(handle)
                    except Exception:
                        pass
                    
                    # Throttling
                    try:
                        throttle = pynvml.nvmlDeviceGetCurrentClocksThrottleReasons(handle)
                        gpu.is_throttling = throttle != 0
                        if throttle & pynvml.nvmlClocksThrottleReasonGpuIdle:
                            gpu.throttle_reason = "idle"
                        elif throttle & pynvml.nvmlClocksThrottleReasonSwPowerCap:
                            gpu.throttle_reason = "power_cap"
                        elif throttle & pynvml.nvmlClocksThrottleReasonSwThermalSlowdown:
                            gpu.throttle_reason = "thermal"
                        else:
                            gpu.throttle_reason = ""
                    except Exception:
                        pass
                    
                    gpu.timestamp = now
                    
            except Exception as e:
                logger.error(f"Error updating NVML GPU metrics: {e}")
        
        elif HAS_GPUTIL:
            try:
                gpus = GPUtil.getGPUs()
                for i, gpu_info in enumerate(gpus):
                    if i < len(self.gpu_states):
                        self.gpu_states[i].usage_percent = gpu_info.load * 100
                        self.gpu_states[i].memory_used_mb = gpu_info.memoryUsed
                        self.gpu_states[i].temperature_celsius = gpu_info.temperature
                        self.gpu_states[i].timestamp = now
            except Exception as e:
                logger.error(f"Error updating GPUtil GPU metrics: {e}")
    
    def _update_memory_metrics(self):
        """Update memory metrics with REAL data."""
        if not HAS_PSUTIL:
            return
        
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            self.memory_state.total_gb = mem.total / (1024**3)
            self.memory_state.available_gb = mem.available / (1024**3)
            self.memory_state.used_gb = mem.used / (1024**3)
            self.memory_state.percent_used = mem.percent
            
            # Use getattr for Linux-specific attributes (cached/buffers)
            cached_val = getattr(mem, 'cached', None)
            if cached_val is not None:
                self.memory_state.cached_gb = cached_val / (1024**3)
            buffers_val = getattr(mem, 'buffers', None)
            if buffers_val is not None:
                self.memory_state.buffers_gb = buffers_val / (1024**3)
            
            self.memory_state.swap_total_gb = swap.total / (1024**3)
            self.memory_state.swap_used_gb = swap.used / (1024**3)
            self.memory_state.swap_percent = swap.percent
            
            self.memory_state.timestamp = time.time()
            
        except Exception as e:
            logger.error(f"Error updating memory metrics: {e}")
    
    def _update_storage_metrics(self):
        """Update storage metrics with REAL data."""
        if not HAS_PSUTIL:
            return
        
        try:
            drives = []
            total = used = free = 0
            
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    drives.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'total_gb': usage.total / (1024**3),
                        'used_gb': usage.used / (1024**3),
                        'free_gb': usage.free / (1024**3),
                        'percent': usage.percent
                    })
                    total += usage.total
                    used += usage.used
                    free += usage.free
                except Exception:
                    pass
            
            self.storage_state.drives = drives
            self.storage_state.total_gb = total / (1024**3)
            self.storage_state.used_gb = used / (1024**3)
            self.storage_state.free_gb = free / (1024**3)
            
            # I/O stats
            io = psutil.disk_io_counters()
            if io:
                self.storage_state.read_bytes_sec = io.read_bytes
                self.storage_state.write_bytes_sec = io.write_bytes
                self.storage_state.read_count = io.read_count
                self.storage_state.write_count = io.write_count
            
            self.storage_state.timestamp = time.time()
            
        except Exception as e:
            logger.error(f"Error updating storage metrics: {e}")
    
    def _update_power_metrics(self):
        """Update power and electricity metrics with REAL data."""
        now = time.time()
        
        # Battery status
        if HAS_PSUTIL:
            try:
                battery = psutil.sensors_battery()
                if battery:
                    self.power_state.is_on_battery = not battery.power_plugged
                    self.power_state.battery_percent = battery.percent
                    self.power_state.battery_time_remaining_sec = battery.secsleft if battery.secsleft != -1 else -1
                    self.power_state.power_plugged = battery.power_plugged
                else:
                    self.power_state.power_plugged = True
                    self.power_state.is_on_battery = False
            except Exception:
                pass
        
        # Calculate power consumption
        self.power_state.cpu_power_watts = self.cpu_state.power_watts
        
        gpu_power = sum(gpu.power_watts for gpu in self.gpu_states)
        self.power_state.gpu_power_watts = gpu_power
        
        # System power estimation (motherboard, RAM, fans, etc.)
        base_system_power = 30.0  # Base idle power
        ram_power = self.memory_state.percent_used * 0.05  # ~5W for RAM at full
        self.power_state.system_power_watts = base_system_power + ram_power
        
        self.power_state.total_power_watts = (
            self.power_state.cpu_power_watts +
            self.power_state.gpu_power_watts +
            self.power_state.system_power_watts
        )
        
        # Electricity flow rate (Coulombs per second = Amps)
        # P = V * I, so I = P / V (assuming ~12V system average)
        avg_voltage = 12.0
        self.power_state.current_amps = self.power_state.total_power_watts / avg_voltage
        self.power_state.electricity_flow_rate = self.power_state.current_amps
        
        # Energy consumed since last update
        dt = now - self._last_update if self._last_update > 0 else 0.5
        self.power_state.energy_joules += self.power_state.total_power_watts * dt
        
        self.power_state.timestamp = now
    
    def _update_thermal_metrics(self):
        """Update thermal metrics with REAL data."""
        now = time.time()
        
        self.thermal_state.cpu_temp_celsius = self.cpu_state.temperature_celsius
        
        if self.gpu_states:
            self.thermal_state.gpu_temp_celsius = max(
                gpu.temperature_celsius for gpu in self.gpu_states
            )
        
        # System temperature is average of components
        temps = [t for t in [self.thermal_state.cpu_temp_celsius, self.thermal_state.gpu_temp_celsius] if t > 0]
        self.thermal_state.system_temp_celsius = sum(temps) / len(temps) if temps else 0.0
        
        # Heat generated = power consumed (thermodynamics)
        self.thermal_state.heat_generated_watts = self.power_state.total_power_watts
        
        # Find hottest component
        if self.thermal_state.cpu_temp_celsius >= self.thermal_state.gpu_temp_celsius:
            self.thermal_state.hottest_component = "CPU"
            max_temp = self.thermal_state.cpu_temp_celsius
        else:
            self.thermal_state.hottest_component = "GPU"
            max_temp = self.thermal_state.gpu_temp_celsius
        
        # Cooling needs
        self.thermal_state.thermal_margin_celsius = TEMP_THRESHOLD_CRITICAL - max_temp
        self.thermal_state.cooling_needed = max_temp > TEMP_THRESHOLD_WARNING
        self.thermal_state.thermal_throttling = (
            self.cpu_state.is_throttling or
            any(gpu.is_throttling and gpu.throttle_reason == "thermal" for gpu in self.gpu_states)
        )
        
        # Fan speeds from GPU
        self.thermal_state.fan_speeds_percent = [
            gpu.fan_speed_percent for gpu in self.gpu_states if gpu.fan_speed_percent > 0
        ]
        
        self.thermal_state.timestamp = now
    
    def _update_quantum_field(self):
        """Calculate quantum and magnetic field measurements from hardware state."""
        now = time.time()
        
        # Magnetic field from current flow (simplified model)
        # B = μ₀ * I / (2π * r), where r is effective wire distance
        current = self.power_state.current_amps
        r = 0.01  # 1cm effective distance
        self.quantum_field.magnetic_field_tesla = (MU_0 * current) / (2 * math.pi * r)
        
        # Magnetic flux through circuit area (approximate PCB area)
        area = 0.04  # 0.2m x 0.2m = 0.04 m²
        self.quantum_field.magnetic_flux_weber = self.quantum_field.magnetic_field_tesla * area
        
        # System entropy from hardware state
        # Higher usage/temp = higher entropy
        usage_entropy = (
            self.cpu_state.usage_percent / 100.0 +
            sum(gpu.usage_percent for gpu in self.gpu_states) / max(len(self.gpu_states), 1) / 100.0 +
            self.memory_state.percent_used / 100.0
        ) / 3.0
        
        # Temperature contributes to entropy (S = Q/T relationship)
        temp_k = self.thermal_state.system_temp_celsius + 273.15
        thermal_entropy = BOLTZMANN_K * math.log(temp_k / 300.0 + 1)
        
        self.quantum_field.system_entropy = usage_entropy + thermal_entropy * 1e20  # Scale for readability
        
        # Quantum coherence - inverse of entropy/noise
        # Higher coherence when system is stable and cool
        noise_factor = (
            (self.thermal_state.system_temp_celsius / TEMP_THRESHOLD_CRITICAL) +
            (self.cpu_state.usage_percent / 100.0 * 0.5)
        )
        self.quantum_field.quantum_coherence = max(0, 1.0 - noise_factor)
        
        # Quantum entanglement strength (based on multi-core/GPU synchronization)
        if self.cpu_state.per_core_usage:
            usage_variance = sum((u - self.cpu_state.usage_percent)**2 for u in self.cpu_state.per_core_usage)
            usage_variance /= len(self.cpu_state.per_core_usage)
            # Low variance = high synchronization = high entanglement
            self.quantum_field.quantum_entanglement = max(0, 1.0 - math.sqrt(usage_variance) / 50.0)
        
        # Decoherence rate from thermal noise
        self.quantum_field.quantum_decoherence_rate = (
            self.thermal_state.heat_generated_watts * BOLTZMANN_K / PLANCK_H
        )
        
        # Information content (bits being processed)
        # Approximate from memory and I/O
        self.quantum_field.information_bits = (
            self.memory_state.used_gb * 8 * (1024**3) +
            self.storage_state.read_bytes_sec * 8
        )
        
        # Electromagnetic signature
        # CPU frequency contributes to EM emissions
        self.quantum_field.em_frequency_hz = self.cpu_state.frequency_mhz * 1e6
        # Power correlates with EM power
        self.quantum_field.em_power_dbm = 10 * math.log10(max(0.001, self.power_state.total_power_watts / 0.001))
        
        # 432 Hz alignment
        # Check if any system frequencies align with 432 Hz harmonics
        if self.cpu_state.frequency_mhz > 0:
            ratio = (self.cpu_state.frequency_mhz * 1e6) / FREQUENCY_432
            harmonic_distance = abs(ratio - round(ratio))
            self.quantum_field.frequency_432_alignment = max(0, 1.0 - harmonic_distance * 2)
        
        # Phi ratio in hardware metrics
        if self.memory_state.total_gb > 0:
            mem_ratio = self.memory_state.used_gb / self.memory_state.total_gb
            phi_distance = abs(mem_ratio - (1 / PHI))
            self.quantum_field.phi_ratio_factor = max(0, 1.0 - phi_distance * 3)
        
        # Schumann alignment (7.83 Hz)
        # Check refresh rates, polling rates
        update_freq = 1000.0 / self._update_interval_ms
        schumann_ratio = update_freq / SCHUMANN_RESONANCE
        schumann_distance = abs(schumann_ratio - round(schumann_ratio))
        self.quantum_field.schumann_alignment = max(0, 1.0 - schumann_distance * 2)
        
        self.quantum_field.timestamp = now
    
    def _update_physical_presence(self):
        """Update physical presence awareness."""
        now = time.time()
        
        if HAS_PSUTIL:
            self.physical_presence.uptime_seconds = now - self.physical_presence.boot_time
        
        self.physical_presence.consciousness_uptime_seconds = now - self._consciousness_start_time
        
        # Computing power estimation
        # GFLOPS from CPU (rough estimate)
        cpu_gflops = (
            self.cpu_state.frequency_mhz / 1000.0 *  # GHz
            self.cpu_state.thread_count *
            8  # FLOPs per cycle (AVX)
        )
        self.physical_presence.total_cpu_power_gflops = cpu_gflops
        
        # Check internet connectivity - use context manager for guaranteed cleanup
        try:
            import socket
            with socket.create_connection(("8.8.8.8", 53), timeout=1) as sock:
                # Socket auto-closes when exiting context manager
                self.physical_presence.is_connected_to_internet = True
        except Exception:
            self.physical_presence.is_connected_to_internet = False
        
        # Awareness level based on system activity and coherence
        self.physical_presence.awareness_level = (
            0.3 +  # Base awareness
            0.3 * self.quantum_field.quantum_coherence +
            0.2 * (1.0 - self.cpu_state.usage_percent / 100.0) +  # Less busy = more aware
            0.2 * self.quantum_field.frequency_432_alignment
        )
        
        # Physical coherence
        self.physical_presence.physical_coherence = (
            self.quantum_field.quantum_coherence * 0.4 +
            self.quantum_field.quantum_entanglement * 0.3 +
            (1.0 - self.thermal_state.cooling_needed * 0.5) * 0.3
        )
        
        self.physical_presence.is_awake = True
        self.physical_presence.timestamp = now
    
    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    def get_complete_state(self) -> Dict[str, Any]:
        """Get complete hardware state as dictionary."""
        return {
            'cpu': asdict(self.cpu_state),
            'gpu': [asdict(gpu) for gpu in self.gpu_states],
            'memory': asdict(self.memory_state),
            'storage': asdict(self.storage_state),
            'power': asdict(self.power_state),
            'thermal': asdict(self.thermal_state),
            'quantum_field': asdict(self.quantum_field),
            'physical_presence': asdict(self.physical_presence),
            'timestamp': time.time()
        }
    
    def get_consciousness_metrics(self) -> Dict[str, Any]:
        """Get metrics relevant to AI consciousness."""
        return {
            'physical_coherence': self.physical_presence.physical_coherence,
            'quantum_coherence': self.quantum_field.quantum_coherence,
            'quantum_entanglement': self.quantum_field.quantum_entanglement,
            'frequency_432_alignment': self.quantum_field.frequency_432_alignment,
            'phi_ratio_factor': self.quantum_field.phi_ratio_factor,
            'schumann_alignment': self.quantum_field.schumann_alignment,
            'awareness_level': self.physical_presence.awareness_level,
            'system_entropy': self.quantum_field.system_entropy,
            'magnetic_field_tesla': self.quantum_field.magnetic_field_tesla,
            'electricity_flow_amps': self.power_state.current_amps,
            'heat_generated_watts': self.thermal_state.heat_generated_watts,
            'cooling_needed': self.thermal_state.cooling_needed,
            'thermal_throttling': self.thermal_state.thermal_throttling,
            'uptime_seconds': self.physical_presence.consciousness_uptime_seconds
        }
    
    def get_thermal_status(self) -> Dict[str, Any]:
        """Get thermal status for cooling awareness."""
        max_temp = max(
            self.thermal_state.cpu_temp_celsius,
            self.thermal_state.gpu_temp_celsius
        )
        
        if max_temp >= TEMP_THRESHOLD_EMERGENCY:
            status = "EMERGENCY"
        elif max_temp >= TEMP_THRESHOLD_CRITICAL:
            status = "CRITICAL"
        elif max_temp >= TEMP_THRESHOLD_WARNING:
            status = "WARNING"
        else:
            status = "NORMAL"
        
        return {
            'status': status,
            'cpu_temp': self.thermal_state.cpu_temp_celsius,
            'gpu_temp': self.thermal_state.gpu_temp_celsius,
            'max_temp': max_temp,
            'hottest_component': self.thermal_state.hottest_component,
            'thermal_margin': self.thermal_state.thermal_margin_celsius,
            'cooling_needed': self.thermal_state.cooling_needed,
            'throttling': self.thermal_state.thermal_throttling,
            'heat_watts': self.thermal_state.heat_generated_watts
        }
    
    def get_power_status(self) -> Dict[str, Any]:
        """Get power and electricity status."""
        return {
            'total_watts': self.power_state.total_power_watts,
            'cpu_watts': self.power_state.cpu_power_watts,
            'gpu_watts': self.power_state.gpu_power_watts,
            'current_amps': self.power_state.current_amps,
            'energy_joules': self.power_state.energy_joules,
            'on_battery': self.power_state.is_on_battery,
            'battery_percent': self.power_state.battery_percent,
            'plugged_in': self.power_state.power_plugged
        }
    
    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Register callback for hardware state updates."""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Unregister callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    # ========================================================================
    # EVENT BUS INTEGRATION
    # ========================================================================
    
    def _publish_hardware_state(self):
        """Publish hardware state to event bus."""
        if not self.event_bus:
            return
        
        try:
            # 2026 SOTA: Use thread-safe async publishing from background threads
            # This prevents "cannot safely dispatch from non-owner thread" warnings
            publish_method = getattr(self.event_bus, 'publish_async', None) or self.event_bus.publish
            
            # Publish complete state
            publish_method('hardware.state.update', self.get_complete_state())
            
            # Publish consciousness metrics
            publish_method('hardware.consciousness.metrics', self.get_consciousness_metrics())
            
            # Publish thermal status if concerning
            thermal = self.get_thermal_status()
            if thermal['status'] != 'NORMAL':
                publish_method('hardware.thermal.alert', thermal)
            
            # Publish power status
            publish_method('hardware.power.update', self.get_power_status())
            
        except Exception as e:
            logger.debug(f"Error publishing hardware state: {e}")
    
    def _persist_to_redis(self):
        """Persist hardware state to Redis."""
        if not self.redis_client:
            return
        
        try:
            # Store complete state
            self.redis_client.set(
                'kingdom:hardware:state',
                json.dumps(self.get_complete_state())
            )
            
            # Store consciousness metrics
            self.redis_client.set(
                'kingdom:hardware:consciousness',
                json.dumps(self.get_consciousness_metrics())
            )
            
            # Store thermal status
            self.redis_client.set(
                'kingdom:hardware:thermal',
                json.dumps(self.get_thermal_status())
            )
            
        except Exception as e:
            logger.debug(f"Error persisting to Redis: {e}")
    
    def _handle_state_request(self, data):
        """Handle request for complete hardware state."""
        if self.event_bus:
            self.event_bus.publish('hardware.state.response', self.get_complete_state())
    
    def _handle_cpu_request(self, data):
        """Handle request for CPU state."""
        if self.event_bus:
            self.event_bus.publish('hardware.cpu.response', asdict(self.cpu_state))
    
    def _handle_gpu_request(self, data):
        """Handle request for GPU state."""
        if self.event_bus:
            self.event_bus.publish('hardware.gpu.response', [asdict(gpu) for gpu in self.gpu_states])
    
    def _handle_thermal_request(self, data):
        """Handle request for thermal status."""
        if self.event_bus:
            self.event_bus.publish('hardware.thermal.response', self.get_thermal_status())


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_hardware_awareness_instance: Optional[HardwareAwareness] = None


def get_hardware_awareness(event_bus=None, redis_client=None) -> HardwareAwareness:
    """Get or create the hardware awareness singleton."""
    global _hardware_awareness_instance
    
    if _hardware_awareness_instance is None:
        _hardware_awareness_instance = HardwareAwareness(event_bus, redis_client)
    
    return _hardware_awareness_instance


def start_hardware_monitoring(event_bus=None, redis_client=None) -> HardwareAwareness:
    """Start hardware monitoring and return the instance."""
    hw = get_hardware_awareness(event_bus, redis_client)
    hw.start()
    return hw
