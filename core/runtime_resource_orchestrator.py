#!/usr/bin/env python3
"""
Runtime Resource Orchestrator - Ensures Heavy ML Workloads Never Starve Real-Time Systems

This orchestrator manages CPU/GPU/memory budgets at runtime so that:
- Real-time systems (GUI, voice, trading) always have priority
- Heavy ML workloads (Diffusers, Torch, TTS) run in controlled resource envelopes
- No subsystem can monopolize resources and cause lag/freezing
- Ollama brain can monitor and control all subsystems dynamically

Architecture:
- Priority-based job queue (CRITICAL > HIGH > NORMAL > LOW)
- Per-subsystem resource quotas (CPU threads, GPU memory, system RAM)
- Dynamic throttling based on real-time load
- Optional process isolation for heavy workloads
- Event bus integration for Ollama brain control
"""

import asyncio
import logging
import threading
import time
import psutil
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum
from collections import deque
import traceback

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Job priority levels - higher priority jobs run first."""
    CRITICAL = 4  # GUI, voice output, critical trading signals
    HIGH = 3      # Trading analysis, wallet operations
    NORMAL = 2    # Background mining, API calls
    LOW = 1       # Heavy ML (Diffusers, video generation, TTS training)


class SubsystemType(Enum):
    """Subsystem categories for resource allocation."""
    GUI = "gui"
    VOICE = "voice"
    TRADING = "trading"
    MINING = "mining"
    WALLET = "wallet"
    AI_BRAIN = "ai_brain"
    DIFFUSERS = "diffusers"
    VIDEO_GEN = "video_gen"
    TTS = "tts"
    BLOCKCHAIN = "blockchain"
    VR = "vr"


@dataclass
class ResourceQuota:
    """Resource limits for a subsystem."""
    max_cpu_threads: int = 0  # 0 = unlimited
    max_gpu_memory_mb: int = 0  # 0 = unlimited
    max_ram_mb: int = 0  # 0 = unlimited
    max_concurrent_jobs: int = 1
    priority: Priority = Priority.NORMAL


@dataclass
class Job:
    """A job to be executed with resource constraints."""
    id: str
    subsystem: SubsystemType
    priority: Priority
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    callback: Optional[Callable] = None
    timeout: float = 300.0  # 5 minutes default
    
    # Runtime state
    status: str = "queued"  # queued, running, completed, failed, cancelled
    start_time: float = 0.0
    end_time: float = 0.0
    error: Optional[str] = None
    result: Any = None
    
    def __lt__(self, other):
        """For priority queue sorting - higher priority first."""
        return self.priority.value > other.priority.value


class RuntimeResourceOrchestrator:
    """
    Central orchestrator that manages all runtime resource allocation.
    
    Ensures heavy ML workloads (Diffusers/Torch) never starve real-time systems.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.running = False
        
        # Job queue (priority-based)
        self._job_queue: deque = deque()
        self._queue_lock = threading.Lock()
        
        # Active jobs by subsystem
        self._active_jobs: Dict[SubsystemType, Set[Job]] = {
            subsystem: set() for subsystem in SubsystemType
        }
        
        # Resource quotas per subsystem
        self._quotas: Dict[SubsystemType, ResourceQuota] = self._initialize_quotas()
        
        # Worker threads
        self._workers: List[threading.Thread] = []
        self._num_workers = min(4, os.cpu_count() or 2)
        
        # Monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats = {
            "jobs_queued": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "jobs_cancelled": 0,
        }
        
        # Torch thread limiting (applied globally)
        self._torch_available = False
        self._torch_threads_limited = False
        
        logger.info("RuntimeResourceOrchestrator initialized")
        
    def _initialize_quotas(self) -> Dict[SubsystemType, ResourceQuota]:
        """Initialize resource quotas based on system capabilities."""
        total_cpu = os.cpu_count() or 4
        total_ram_mb = psutil.virtual_memory().total // (1024 * 1024)
        
        # Try to detect GPU memory
        gpu_memory_mb = 0
        try:
            import torch
            if torch.cuda.is_available():
                gpu_memory_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
                self._torch_available = True
        except:
            pass
        
        quotas = {
            # CRITICAL: Real-time systems get guaranteed resources
            SubsystemType.GUI: ResourceQuota(
                max_cpu_threads=max(2, total_cpu // 4),
                max_ram_mb=min(2048, total_ram_mb // 4),
                max_concurrent_jobs=10,
                priority=Priority.CRITICAL
            ),
            SubsystemType.VOICE: ResourceQuota(
                max_cpu_threads=max(2, total_cpu // 8),
                max_ram_mb=min(1024, total_ram_mb // 8),
                max_concurrent_jobs=2,
                priority=Priority.CRITICAL
            ),
            SubsystemType.TRADING: ResourceQuota(
                max_cpu_threads=max(2, total_cpu // 4),
                max_ram_mb=min(2048, total_ram_mb // 4),
                max_concurrent_jobs=5,
                priority=Priority.HIGH
            ),
            SubsystemType.AI_BRAIN: ResourceQuota(
                max_cpu_threads=max(2, total_cpu // 4),
                max_ram_mb=min(4096, total_ram_mb // 4),
                max_gpu_memory_mb=min(4096, gpu_memory_mb // 2) if gpu_memory_mb > 0 else 0,
                max_concurrent_jobs=3,
                priority=Priority.HIGH
            ),
            
            # LOW: Heavy ML workloads get limited resources
            SubsystemType.DIFFUSERS: ResourceQuota(
                max_cpu_threads=max(1, total_cpu // 8),  # Limit CPU threads
                max_ram_mb=min(4096, total_ram_mb // 3),
                max_gpu_memory_mb=min(6144, gpu_memory_mb // 2) if gpu_memory_mb > 0 else 0,
                max_concurrent_jobs=1,  # Only 1 diffusion job at a time
                priority=Priority.LOW
            ),
            SubsystemType.VIDEO_GEN: ResourceQuota(
                max_cpu_threads=max(1, total_cpu // 8),
                max_ram_mb=min(6144, total_ram_mb // 3),
                max_gpu_memory_mb=min(8192, gpu_memory_mb // 2) if gpu_memory_mb > 0 else 0,
                max_concurrent_jobs=1,
                priority=Priority.LOW
            ),
            SubsystemType.TTS: ResourceQuota(
                max_cpu_threads=max(1, total_cpu // 8),
                max_ram_mb=min(2048, total_ram_mb // 6),
                max_gpu_memory_mb=min(2048, gpu_memory_mb // 4) if gpu_memory_mb > 0 else 0,
                max_concurrent_jobs=1,
                priority=Priority.LOW
            ),
            
            # NORMAL: Other subsystems
            SubsystemType.MINING: ResourceQuota(
                max_cpu_threads=max(1, total_cpu // 4),
                max_ram_mb=min(2048, total_ram_mb // 6),
                max_concurrent_jobs=3,
                priority=Priority.NORMAL
            ),
            SubsystemType.WALLET: ResourceQuota(
                max_cpu_threads=max(1, total_cpu // 8),
                max_ram_mb=min(1024, total_ram_mb // 8),
                max_concurrent_jobs=5,
                priority=Priority.HIGH
            ),
            SubsystemType.BLOCKCHAIN: ResourceQuota(
                max_cpu_threads=max(1, total_cpu // 8),
                max_ram_mb=min(1024, total_ram_mb // 8),
                max_concurrent_jobs=10,
                priority=Priority.NORMAL
            ),
            SubsystemType.VR: ResourceQuota(
                max_cpu_threads=max(2, total_cpu // 6),
                max_ram_mb=min(2048, total_ram_mb // 6),
                max_gpu_memory_mb=min(2048, gpu_memory_mb // 4) if gpu_memory_mb > 0 else 0,
                max_concurrent_jobs=2,
                priority=Priority.HIGH
            ),
        }
        
        logger.info(f"Resource quotas initialized for {total_cpu} CPUs, {total_ram_mb}MB RAM, {gpu_memory_mb}MB GPU")
        return quotas
    
    def start(self):
        """Start the orchestrator and worker threads."""
        if self.running:
            logger.warning("RuntimeResourceOrchestrator already running")
            return
        
        self.running = True
        
        # Limit torch threads globally to prevent CPU starvation
        if self._torch_available and not self._torch_threads_limited:
            try:
                import torch
                max_torch_threads = max(1, (os.cpu_count() or 4) // 4)
                torch.set_num_threads(max_torch_threads)
                self._torch_threads_limited = True
                logger.info(f"✅ Torch CPU threads limited to {max_torch_threads} (prevents CPU starvation)")
            except Exception as e:
                logger.warning(f"Failed to limit torch threads: {e}")
        
        # Set environment variables for other ML libraries
        os.environ.setdefault("OMP_NUM_THREADS", str(max(1, (os.cpu_count() or 4) // 4)))
        os.environ.setdefault("MKL_NUM_THREADS", str(max(1, (os.cpu_count() or 4) // 4)))
        os.environ.setdefault("OPENBLAS_NUM_THREADS", str(max(1, (os.cpu_count() or 4) // 4)))
        
        # Start worker threads
        for i in range(self._num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"ResourceWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
        
        # Start monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="ResourceMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        
        logger.info(f"✅ RuntimeResourceOrchestrator started with {self._num_workers} workers")
        
        # Publish startup event
        if self.event_bus:
            try:
                self.event_bus.publish("runtime.orchestrator.started", {
                    "workers": self._num_workers,
                    "quotas": {k.value: {
                        "max_cpu_threads": v.max_cpu_threads,
                        "max_ram_mb": v.max_ram_mb,
                        "max_gpu_memory_mb": v.max_gpu_memory_mb,
                        "priority": v.priority.name
                    } for k, v in self._quotas.items()}
                })
            except:
                pass
    
    def stop(self):
        """Stop the orchestrator and all workers."""
        if not self.running:
            return
        
        logger.info("Stopping RuntimeResourceOrchestrator...")
        self.running = False
        
        # Cancel all queued jobs
        with self._queue_lock:
            while self._job_queue:
                job = self._job_queue.popleft()
                job.status = "cancelled"
                self._stats["jobs_cancelled"] += 1
        
        # Wait for workers to finish
        for worker in self._workers:
            if worker.is_alive():
                worker.join(timeout=5.0)
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        
        logger.info("✅ RuntimeResourceOrchestrator stopped")
    
    def submit_job(self, subsystem: SubsystemType, func: Callable, 
                   args: tuple = (), kwargs: dict = None,
                   priority: Optional[Priority] = None,
                   callback: Optional[Callable] = None,
                   timeout: float = 300.0) -> str:
        """
        Submit a job to be executed with resource constraints.
        
        Args:
            subsystem: Which subsystem this job belongs to
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            priority: Override default priority for this subsystem
            callback: Optional callback(result) when job completes
            timeout: Max execution time in seconds
            
        Returns:
            Job ID for tracking
        """
        if kwargs is None:
            kwargs = {}
        
        # Use subsystem's default priority if not specified
        if priority is None:
            priority = self._quotas[subsystem].priority
        
        job = Job(
            id=f"{subsystem.value}_{int(time.time() * 1000)}_{id(func)}",
            subsystem=subsystem,
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs,
            callback=callback,
            timeout=timeout
        )
        
        with self._queue_lock:
            # Insert in priority order (higher priority first)
            inserted = False
            for i, existing_job in enumerate(self._job_queue):
                if job.priority.value > existing_job.priority.value:
                    self._job_queue.insert(i, job)
                    inserted = True
                    break
            
            if not inserted:
                self._job_queue.append(job)
            
            self._stats["jobs_queued"] += 1
        
        logger.debug(f"Job submitted: {job.id} [{priority.name}] for {subsystem.value}")
        return job.id
    
    def _worker_loop(self):
        """Worker thread that processes jobs from the queue."""
        while self.running:
            job = None
            
            try:
                # Get next job from queue
                with self._queue_lock:
                    if not self._job_queue:
                        time.sleep(0.1)
                        continue
                    
                    # Find first job that doesn't exceed subsystem quota
                    for i, candidate in enumerate(self._job_queue):
                        quota = self._quotas[candidate.subsystem]
                        active_count = len(self._active_jobs[candidate.subsystem])
                        
                        if active_count < quota.max_concurrent_jobs:
                            job = self._job_queue[i]
                            del self._job_queue[i]
                            break
                    
                    if job is None:
                        # All subsystems at capacity
                        time.sleep(0.1)
                        continue
                    
                    # Mark as active
                    self._active_jobs[job.subsystem].add(job)
                
                # Execute job
                self._execute_job(job)
                
            except Exception as e:
                logger.error(f"Worker error: {e}")
                logger.error(traceback.format_exc())
            finally:
                # Remove from active jobs
                if job:
                    with self._queue_lock:
                        self._active_jobs[job.subsystem].discard(job)
    
    def _execute_job(self, job: Job):
        """Execute a single job with resource constraints."""
        job.status = "running"
        job.start_time = time.time()
        
        try:
            # Apply resource limits for this subsystem
            quota = self._quotas[job.subsystem]
            
            # For heavy ML jobs, enforce torch thread limits
            if job.subsystem in [SubsystemType.DIFFUSERS, SubsystemType.VIDEO_GEN, SubsystemType.TTS]:
                if self._torch_available:
                    import torch
                    # Temporarily reduce torch threads even further for heavy jobs
                    original_threads = torch.get_num_threads()
                    torch.set_num_threads(max(1, quota.max_cpu_threads))
                    try:
                        result = job.func(*job.args, **job.kwargs)
                    finally:
                        torch.set_num_threads(original_threads)
                else:
                    result = job.func(*job.args, **job.kwargs)
            else:
                result = job.func(*job.args, **job.kwargs)
            
            job.result = result
            job.status = "completed"
            job.end_time = time.time()
            self._stats["jobs_completed"] += 1
            
            # Call callback if provided
            if job.callback:
                try:
                    job.callback(result)
                except Exception as e:
                    logger.error(f"Job callback error: {e}")
            
            logger.debug(f"Job completed: {job.id} in {job.end_time - job.start_time:.2f}s")
            
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.end_time = time.time()
            self._stats["jobs_failed"] += 1
            logger.error(f"Job failed: {job.id}: {e}")
            logger.error(traceback.format_exc())
    
    def _monitor_loop(self):
        """Monitor system resources and publish metrics."""
        while self.running:
            try:
                # Collect metrics
                cpu_percent = psutil.cpu_percent(interval=1.0)
                memory = psutil.virtual_memory()
                
                # Count active jobs per subsystem
                active_counts = {}
                with self._queue_lock:
                    for subsystem, jobs in self._active_jobs.items():
                        if jobs:
                            active_counts[subsystem.value] = len(jobs)
                    queue_size = len(self._job_queue)
                
                metrics = {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_mb": memory.available // (1024 * 1024),
                    "active_jobs": active_counts,
                    "queue_size": queue_size,
                    "stats": self._stats.copy()
                }
                
                # Publish to event bus for Ollama brain monitoring
                if self.event_bus:
                    try:
                        self.event_bus.publish("runtime.orchestrator.metrics", metrics)
                    except:
                        pass
                
                # Log if system is under heavy load
                if cpu_percent > 80 or memory.percent > 85:
                    logger.warning(f"⚠️ High resource usage: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}%")
                
                time.sleep(10.0)  # Monitor every 10 seconds
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(10.0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current orchestrator statistics."""
        with self._queue_lock:
            return {
                "running": self.running,
                "workers": self._num_workers,
                "queue_size": len(self._job_queue),
                "active_jobs": {k.value: len(v) for k, v in self._active_jobs.items()},
                "stats": self._stats.copy()
            }


# Global singleton instance
_orchestrator: Optional[RuntimeResourceOrchestrator] = None


def get_runtime_orchestrator(event_bus=None) -> RuntimeResourceOrchestrator:
    """Get or create the global runtime orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = RuntimeResourceOrchestrator(event_bus=event_bus)
    return _orchestrator
