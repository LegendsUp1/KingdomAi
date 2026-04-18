#!/usr/bin/env python3
"""
Brain Runtime Controller - Ollama AI Control Interface for Runtime Orchestrator

Allows the Ollama brain to monitor and dynamically adjust runtime resource allocation.
The AI can:
- Monitor real-time resource usage across all subsystems
- Adjust priority and quotas for subsystems based on current needs
- Pause/resume heavy workloads when real-time systems need resources
- Receive alerts when system is under stress
- Make intelligent decisions about resource allocation

This ensures the AI brain has full control over the entire system during runtime.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SystemHealthReport:
    """Real-time system health metrics."""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    gpu_memory_percent: float
    active_jobs: Dict[str, int]
    queue_size: int
    subsystem_status: Dict[str, str]
    recommendations: List[str]


class BrainRuntimeController:
    """
    Interface between Ollama AI brain and RuntimeResourceOrchestrator.
    
    Allows the AI to monitor and control runtime resource allocation.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._orchestrator = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._last_health_report: Optional[SystemHealthReport] = None
        
        # Subscribe to orchestrator metrics
        if self.event_bus:
            try:
                self.event_bus.subscribe("runtime.orchestrator.metrics", self._on_metrics_update)
                logger.info("✅ BrainRuntimeController subscribed to orchestrator metrics")
            except Exception as e:
                logger.warning(f"Failed to subscribe to orchestrator metrics: {e}")
        
        logger.info("BrainRuntimeController initialized")
    
    def set_orchestrator(self, orchestrator):
        """Set the runtime orchestrator instance to control."""
        self._orchestrator = orchestrator
        logger.info("✅ BrainRuntimeController connected to RuntimeResourceOrchestrator")
    
    async def start_monitoring(self):
        """Start continuous monitoring and publish health reports."""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Monitoring already running")
            return
        
        # CRITICAL FIX: Use ensure_future instead of create_task
        self._monitoring_task = asyncio.ensure_future(self._monitoring_loop())
        logger.info("✅ BrainRuntimeController monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        logger.info("BrainRuntimeController monitoring stopped")
    
    async def _monitoring_loop(self):
        """Continuous monitoring loop."""
        while True:
            try:
                # Generate health report
                report = await self.get_health_report()
                
                # Publish to event bus for AI brain consumption
                if self.event_bus and report:
                    try:
                        self.event_bus.publish("brain.runtime.health_report", {
                            "timestamp": report.timestamp,
                            "cpu_percent": report.cpu_percent,
                            "memory_percent": report.memory_percent,
                            "gpu_memory_percent": report.gpu_memory_percent,
                            "active_jobs": report.active_jobs,
                            "queue_size": report.queue_size,
                            "subsystem_status": report.subsystem_status,
                            "recommendations": report.recommendations
                        })
                    except:
                        pass
                
                # Check for critical conditions and alert AI
                if report and (report.cpu_percent > 90 or report.memory_percent > 90):
                    await self._alert_brain_critical_load(report)
                
                await asyncio.sleep(15.0)  # Report every 15 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(15.0)
    
    def _on_metrics_update(self, metrics: Dict[str, Any]):
        """Handle metrics updates from orchestrator."""
        # Store latest metrics for health report generation
        self._last_metrics = metrics
    
    async def get_health_report(self) -> Optional[SystemHealthReport]:
        """Generate current system health report."""
        try:
            import psutil
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # Try to get GPU memory
            gpu_memory_percent = 0.0
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_mem_used = torch.cuda.memory_allocated(0)
                    gpu_mem_total = torch.cuda.get_device_properties(0).total_memory
                    gpu_memory_percent = (gpu_mem_used / gpu_mem_total) * 100
            except:
                pass
            
            # Get orchestrator stats
            active_jobs = {}
            queue_size = 0
            if self._orchestrator:
                stats = self._orchestrator.get_stats()
                active_jobs = stats.get("active_jobs", {})
                queue_size = stats.get("queue_size", 0)
            
            # Determine subsystem status
            subsystem_status = {}
            for subsystem, count in active_jobs.items():
                if count > 0:
                    subsystem_status[subsystem] = "active"
                else:
                    subsystem_status[subsystem] = "idle"
            
            # Generate recommendations
            recommendations = []
            if cpu_percent > 85:
                recommendations.append("HIGH_CPU: Consider pausing low-priority jobs")
            if memory.percent > 85:
                recommendations.append("HIGH_MEMORY: Reduce concurrent heavy workloads")
            if gpu_memory_percent > 85:
                recommendations.append("HIGH_GPU_MEMORY: Limit Diffusers/video generation")
            if queue_size > 10:
                recommendations.append("LARGE_QUEUE: System may be overloaded")
            
            report = SystemHealthReport(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                gpu_memory_percent=gpu_memory_percent,
                active_jobs=active_jobs,
                queue_size=queue_size,
                subsystem_status=subsystem_status,
                recommendations=recommendations
            )
            
            self._last_health_report = report
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate health report: {e}")
            return None
    
    async def _alert_brain_critical_load(self, report: SystemHealthReport):
        """Alert AI brain about critical system load."""
        if self.event_bus:
            try:
                self.event_bus.publish("brain.runtime.critical_alert", {
                    "severity": "critical",
                    "message": f"System under heavy load: CPU {report.cpu_percent:.1f}%, RAM {report.memory_percent:.1f}%",
                    "cpu_percent": report.cpu_percent,
                    "memory_percent": report.memory_percent,
                    "recommendations": report.recommendations,
                    "timestamp": report.timestamp
                })
                logger.warning(f"⚠️ Critical load alert sent to AI brain: CPU {report.cpu_percent:.1f}%, RAM {report.memory_percent:.1f}%")
            except:
                pass
    
    async def adjust_subsystem_priority(self, subsystem: str, new_priority: str) -> bool:
        """
        Allow AI brain to adjust subsystem priority dynamically.
        
        Args:
            subsystem: Subsystem name (e.g., "diffusers", "trading")
            new_priority: New priority level ("CRITICAL", "HIGH", "NORMAL", "LOW")
            
        Returns:
            True if adjustment successful
        """
        if not self._orchestrator:
            logger.warning("Cannot adjust priority: orchestrator not set")
            return False
        
        try:
            from core.runtime_resource_orchestrator import SubsystemType, Priority
            
            # Map string to enum
            subsystem_enum = SubsystemType(subsystem)
            priority_enum = Priority[new_priority]
            
            # Update quota
            quota = self._orchestrator._quotas.get(subsystem_enum)
            if quota:
                quota.priority = priority_enum
                logger.info(f"✅ AI brain adjusted {subsystem} priority to {new_priority}")
                
                # Publish event
                if self.event_bus:
                    try:
                        self.event_bus.publish("brain.runtime.priority_adjusted", {
                            "subsystem": subsystem,
                            "new_priority": new_priority,
                            "timestamp": datetime.now().isoformat()
                        })
                    except:
                        pass
                
                return True
            else:
                logger.warning(f"Subsystem {subsystem} not found in quotas")
                return False
                
        except Exception as e:
            logger.error(f"Failed to adjust priority: {e}")
            return False
    
    async def pause_heavy_workloads(self) -> bool:
        """
        Pause all heavy ML workloads (Diffusers, video gen, TTS).
        
        Returns:
            True if successful
        """
        try:
            from core.runtime_resource_orchestrator import SubsystemType
            
            heavy_subsystems = [
                SubsystemType.DIFFUSERS,
                SubsystemType.VIDEO_GEN,
                SubsystemType.TTS
            ]
            
            for subsystem in heavy_subsystems:
                quota = self._orchestrator._quotas.get(subsystem)
                if quota:
                    # Set max concurrent jobs to 0 to pause
                    quota.max_concurrent_jobs = 0
            
            logger.info("✅ AI brain paused all heavy ML workloads")
            
            if self.event_bus:
                try:
                    self.event_bus.publish("brain.runtime.heavy_workloads_paused", {
                        "timestamp": datetime.now().isoformat()
                    })
                except:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause heavy workloads: {e}")
            return False
    
    async def resume_heavy_workloads(self) -> bool:
        """
        Resume heavy ML workloads.
        
        Returns:
            True if successful
        """
        try:
            from core.runtime_resource_orchestrator import SubsystemType
            
            # Restore default concurrent job limits
            heavy_subsystems = {
                SubsystemType.DIFFUSERS: 1,
                SubsystemType.VIDEO_GEN: 1,
                SubsystemType.TTS: 1
            }
            
            for subsystem, default_limit in heavy_subsystems.items():
                quota = self._orchestrator._quotas.get(subsystem)
                if quota:
                    quota.max_concurrent_jobs = default_limit
            
            logger.info("✅ AI brain resumed heavy ML workloads")
            
            if self.event_bus:
                try:
                    self.event_bus.publish("brain.runtime.heavy_workloads_resumed", {
                        "timestamp": datetime.now().isoformat()
                    })
                except:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to resume heavy workloads: {e}")
            return False
    
    async def get_subsystem_stats(self, subsystem: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed stats for a specific subsystem.
        
        Args:
            subsystem: Subsystem name
            
        Returns:
            Dict with subsystem stats or None
        """
        if not self._orchestrator:
            return None
        
        try:
            from core.runtime_resource_orchestrator import SubsystemType
            
            subsystem_enum = SubsystemType(subsystem)
            quota = self._orchestrator._quotas.get(subsystem_enum)
            active_jobs = self._orchestrator._active_jobs.get(subsystem_enum, set())
            
            if quota:
                return {
                    "subsystem": subsystem,
                    "priority": quota.priority.name,
                    "max_cpu_threads": quota.max_cpu_threads,
                    "max_ram_mb": quota.max_ram_mb,
                    "max_gpu_memory_mb": quota.max_gpu_memory_mb,
                    "max_concurrent_jobs": quota.max_concurrent_jobs,
                    "active_jobs": len(active_jobs),
                    "status": "active" if active_jobs else "idle"
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get subsystem stats: {e}")
            return None


# Global singleton
_brain_controller: Optional[BrainRuntimeController] = None


def get_brain_runtime_controller(event_bus=None) -> BrainRuntimeController:
    """Get or create the global brain runtime controller."""
    global _brain_controller
    if _brain_controller is None:
        _brain_controller = BrainRuntimeController(event_bus=event_bus)
    return _brain_controller
