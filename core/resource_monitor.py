"""
Resource Monitor
---------------
Monitors system resources (CPU, memory, disk, network) and provides notifications
when thresholds are exceeded. Integrates with the event bus for system-wide alerts.
"""

import time
import psutil
import threading
import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ResourceMonitor")

class ResourceMonitor:
    """
    Monitors system resources and sends alerts when thresholds are exceeded.
    
    Features:
    - Real-time monitoring of CPU, memory, disk, and network usage
    - Configurable thresholds for alerts
    - Event bus integration for system-wide notifications
    - Historical tracking for trend analysis
    - Self-optimization based on system capabilities
    """
    
    def __init__(self, event_bus=None, config: Dict[str, Any] = None):
        """
        Initialize the resource monitor.
        
        Args:
            event_bus: The event bus for publishing resource alerts
            config: Configuration settings for the resource monitor
        """
        self.event_bus = event_bus
        self.config = config or {}
        
        # Set default thresholds
        self.thresholds = {
            "cpu_percent": self.config.get("cpu_threshold", 80),  # 80% CPU usage
            "memory_percent": self.config.get("memory_threshold", 85),  # 85% memory usage
            "disk_percent": self.config.get("disk_threshold", 90),  # 90% disk usage
            "network_error_rate": self.config.get("network_error_threshold", 0.05),  # 5% error rate
            "battery_percent": self.config.get("battery_threshold", 15)  # 15% battery remaining
        }
        
        # Resource tracking history (last 60 minutes, 1 sample per minute)
        self.history = {
            "cpu": [],
            "memory": [],
            "disk": [],
            "network": [],
            "battery": []
        }
        
        # Set history retention period (in minutes)
        self.history_minutes = self.config.get("history_minutes", 60)
        
        # Monitoring interval (in seconds)
        self.interval = self.config.get("monitoring_interval", 30)
        
        # Timestamps for rate limiting alerts
        self.last_alert = {resource: datetime.min for resource in self.thresholds}
        self.alert_cooldown = timedelta(minutes=self.config.get("alert_cooldown_minutes", 5))
        
        # Flag to control the monitoring thread
        self.running = False
        self.monitor_thread = None
        
        # Track the start time for uptime calculation
        self.start_time = datetime.now()
        
        # Performance optimization settings
        self.adaptive_monitoring = self.config.get("adaptive_monitoring", True)
        self.min_interval = 10  # Minimum 10 seconds between checks
        self.max_interval = 120  # Maximum 2 minutes between checks
        
        # Calculate optimal interval based on system specs
        if self.adaptive_monitoring:
            self._optimize_monitoring_interval()
            
        logger.info(f"Resource Monitor initialized with {self.interval}s monitoring interval")
    
    def _optimize_monitoring_interval(self):
        """
        Optimize the monitoring interval based on system specifications.
        Faster systems can handle more frequent monitoring.
        """
        try:
            # Check CPU count and speed
            cpu_count = psutil.cpu_count(logical=True)
            
            # Get memory info
            memory_gb = psutil.virtual_memory().total / (1024 * 1024 * 1024)
            
            # Calculate optimal interval: less powerful systems get longer intervals
            # to reduce monitoring overhead
            if cpu_count >= 8 and memory_gb >= 16:
                # High-end system
                self.interval = max(self.min_interval, min(20, self.interval))
            elif cpu_count >= 4 and memory_gb >= 8:
                # Mid-range system
                self.interval = max(self.min_interval, min(30, self.interval))
            else:
                # Lower-end system - be conservative with resources
                self.interval = max(self.min_interval, min(45, self.interval))
                
            logger.info(f"Adaptive monitoring: optimized interval to {self.interval}s "
                       f"based on {cpu_count} CPUs and {memory_gb:.1f}GB RAM")
        except Exception as e:
            logger.warning(f"Failed to optimize monitoring interval: {e}. Using default.")
    
    def start(self):
        """Start the resource monitoring thread."""
        if self.running:
            logger.warning("Resource Monitor is already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="ResourceMonitorThread",
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Resource Monitor started")
    
    def stop(self):
        """Stop the resource monitoring thread."""
        if not self.running:
            logger.warning("Resource Monitor is not running")
            return
        
        self.running = False
        if self.monitor_thread:
            # Give thread time to complete current iteration
            if self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=self.interval + 5)
            self.monitor_thread = None
        logger.info("Resource Monitor stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop that runs in a separate thread."""
        while self.running:
            try:
                # Collect resource metrics
                metrics = self._collect_metrics()
                
                # Check for threshold breaches
                self._check_thresholds(metrics)
                
                # Update history
                self._update_history(metrics)
                
                # Sleep until next check
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Don't crash the thread, just log the error and continue
                time.sleep(self.interval)
    
    def _collect_metrics(self) -> Dict[str, Any]:
        """
        Collect current resource metrics.
        
        Returns:
            Dict of current resource metrics
        """
        metrics = {}
        
        try:
            # CPU metrics
            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.5)
            metrics["cpu_count"] = psutil.cpu_count(logical=True)
            metrics["cpu_freq"] = psutil.cpu_freq().current if psutil.cpu_freq() else None
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics["memory_percent"] = memory.percent
            metrics["memory_available"] = memory.available
            metrics["memory_total"] = memory.total
            
            # Disk metrics - check all mounted disks
            disk_metrics = {}
            for partition in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_metrics[partition.mountpoint] = {
                        "percent": usage.percent,
                        "used": usage.used,
                        "total": usage.total,
                        "free": usage.free
                    }
                except (PermissionError, FileNotFoundError):
                    # Skip inaccessible disks
                    continue
            
            metrics["disk"] = disk_metrics
            
            # Get the max disk usage across all partitions
            if disk_metrics:
                metrics["disk_percent"] = max(
                    info["percent"] for info in disk_metrics.values()
                )
            else:
                metrics["disk_percent"] = 0
            
            # Network metrics - collect data from all interfaces
            net_io_counters = psutil.net_io_counters(pernic=True)
            metrics["network"] = {
                iface: {
                    "bytes_sent": counters.bytes_sent,
                    "bytes_recv": counters.bytes_recv,
                    "packets_sent": counters.packets_sent,
                    "packets_recv": counters.packets_recv,
                    "errin": counters.errin,
                    "errout": counters.errout,
                    "dropin": counters.dropin,
                    "dropout": counters.dropout
                } for iface, counters in net_io_counters.items()
            }
            
            # Calculate network error rate (if packets were sent/received)
            total_packets_in = sum(nic["packets_recv"] for nic in metrics["network"].values())
            total_packets_out = sum(nic["packets_sent"] for nic in metrics["network"].values())
            total_errors = sum(nic["errin"] + nic["errout"] for nic in metrics["network"].values())
            total_drops = sum(nic["dropin"] + nic["dropout"] for nic in metrics["network"].values())
            
            total_packets = total_packets_in + total_packets_out
            if total_packets > 0:
                metrics["network_error_rate"] = (total_errors + total_drops) / total_packets
            else:
                metrics["network_error_rate"] = 0
            
            # Battery metrics (for laptops/mobile devices)
            try:
                battery = psutil.sensors_battery()
                if battery:
                    metrics["battery_percent"] = battery.percent
                    metrics["battery_plugged"] = battery.power_plugged
                    metrics["battery_time_left"] = battery.secsleft
                else:
                    metrics["battery_percent"] = 100  # No battery = desktop = always powered
                    metrics["battery_plugged"] = True
            except (AttributeError, NotImplementedError):
                # Battery metrics not available on this platform
                metrics["battery_percent"] = 100
                metrics["battery_plugged"] = True
            
            # Get process info for the current process
            process = psutil.Process()
            metrics["process"] = {
                "cpu_percent": process.cpu_percent(interval=0.1),
                "memory_percent": process.memory_percent(),
                "memory_rss": process.memory_info().rss,
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections())
            }
            
            # System uptime
            metrics["system_uptime"] = time.time() - psutil.boot_time()
            metrics["app_uptime"] = (datetime.now() - self.start_time).total_seconds()
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
        
        return metrics
    
    def _check_thresholds(self, metrics: Dict[str, Any]):
        """
        Check if any resource metrics exceed thresholds.
        
        Args:
            metrics: Current resource metrics
        """
        now = datetime.now()
        
        # Check CPU usage
        if metrics.get("cpu_percent", 0) > self.thresholds["cpu_percent"]:
            if now - self.last_alert["cpu_percent"] > self.alert_cooldown:
                self._publish_alert("resource.cpu.high", {
                    "current": metrics["cpu_percent"],
                    "threshold": self.thresholds["cpu_percent"],
                    "message": f"High CPU usage detected: {metrics['cpu_percent']}% (threshold: {self.thresholds['cpu_percent']}%)"
                })
                self.last_alert["cpu_percent"] = now
        
        # Check memory usage
        if metrics.get("memory_percent", 0) > self.thresholds["memory_percent"]:
            if now - self.last_alert["memory_percent"] > self.alert_cooldown:
                # Convert bytes to MB for readability
                available_mb = metrics["memory_available"] / (1024 * 1024)
                total_mb = metrics["memory_total"] / (1024 * 1024)
                
                self._publish_alert("resource.memory.high", {
                    "current": metrics["memory_percent"],
                    "threshold": self.thresholds["memory_percent"],
                    "available_mb": available_mb,
                    "total_mb": total_mb,
                    "message": f"High memory usage detected: {metrics['memory_percent']}% "
                              f"({available_mb:.0f}MB available of {total_mb:.0f}MB)"
                })
                self.last_alert["memory_percent"] = now
        
        # Check disk usage
        if metrics.get("disk_percent", 0) > self.thresholds["disk_percent"]:
            if now - self.last_alert["disk_percent"] > self.alert_cooldown:
                # Find the partition with the highest usage
                if metrics.get("disk"):
                    max_usage_partition = max(
                        metrics["disk"].items(),
                        key=lambda x: x[1]["percent"]
                    )
                    mount_point, disk_info = max_usage_partition
                    free_gb = disk_info["free"] / (1024 * 1024 * 1024)
                    total_gb = disk_info["total"] / (1024 * 1024 * 1024)
                    
                    self._publish_alert("resource.disk.high", {
                        "current": disk_info["percent"],
                        "threshold": self.thresholds["disk_percent"],
                        "partition": mount_point,
                        "free_gb": free_gb,
                        "total_gb": total_gb,
                        "message": f"High disk usage on {mount_point}: {disk_info['percent']}% "
                                  f"({free_gb:.1f}GB free of {total_gb:.1f}GB)"
                    })
                else:
                    self._publish_alert("resource.disk.high", {
                        "current": metrics["disk_percent"],
                        "threshold": self.thresholds["disk_percent"],
                        "message": f"High disk usage detected: {metrics['disk_percent']}%"
                    })
                self.last_alert["disk_percent"] = now
        
        # Check network error rate
        if metrics.get("network_error_rate", 0) > self.thresholds["network_error_rate"]:
            if now - self.last_alert["network_error_rate"] > self.alert_cooldown:
                self._publish_alert("resource.network.errors", {
                    "current": metrics["network_error_rate"],
                    "threshold": self.thresholds["network_error_rate"],
                    "message": f"High network error rate: {metrics['network_error_rate']*100:.2f}% "
                              f"(threshold: {self.thresholds['network_error_rate']*100:.2f}%)"
                })
                self.last_alert["network_error_rate"] = now
        
        # Check battery level (only if not plugged in)
        battery_percent = metrics.get("battery_percent", 100)
        battery_plugged = metrics.get("battery_plugged", True)
        
        if battery_percent < self.thresholds["battery_percent"] and not battery_plugged:
            if now - self.last_alert["battery_percent"] > self.alert_cooldown:
                time_left = metrics.get("battery_time_left", -1)
                time_str = f"{time_left // 60} minutes" if time_left > 0 else "unknown"
                
                self._publish_alert("resource.battery.low", {
                    "current": battery_percent,
                    "threshold": self.thresholds["battery_percent"],
                    "time_remaining": time_left,
                    "message": f"Low battery: {battery_percent}% remaining ({time_str} left)"
                })
                self.last_alert["battery_percent"] = now
    
    def _publish_alert(self, event_type: str, data: Dict[str, Any]):
        """
        Publish a resource alert to the event bus.
        
        Args:
            event_type: The type of event to publish
            data: The event data
        """
        # Log the alert
        logger.warning(data.get("message", f"Resource alert: {event_type}"))
        
        # Publish to event bus if available
        if self.event_bus:
            try:
                self.event_bus.publish(event_type, data)
            except Exception as e:
                logger.error(f"Failed to publish resource alert to event bus: {e}")
    
    def _update_history(self, metrics: Dict[str, Any]):
        """
        Update the resource history with current metrics.
        
        Args:
            metrics: Current resource metrics
        """
        timestamp = datetime.now()
        
        # Add current metrics to history
        self.history["cpu"].append((timestamp, metrics.get("cpu_percent", 0)))
        self.history["memory"].append((timestamp, metrics.get("memory_percent", 0)))
        self.history["disk"].append((timestamp, metrics.get("disk_percent", 0)))
        self.history["network"].append((timestamp, metrics.get("network_error_rate", 0)))
        self.history["battery"].append((timestamp, metrics.get("battery_percent", 100)))
        
        # Trim history to keep only the last X minutes of data
        cutoff_time = timestamp - timedelta(minutes=self.history_minutes)
        for resource in self.history:
            self.history[resource] = [
                (ts, value) for ts, value in self.history[resource]
                if ts > cutoff_time
            ]
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get the current resource metrics.
        
        Returns:
            Dict of current resource metrics
        """
        return self._collect_metrics()
    
    def get_resource_history(self, resource_type: str = None) -> Dict[str, List[Tuple[datetime, float]]]:
        """
        Get historical resource data.
        
        Args:
            resource_type: The specific resource to get history for (optional)
            
        Returns:
            Dict or List of historical metrics
        """
        if resource_type and resource_type in self.history:
            return self.history[resource_type]
        return self.history
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current resource usage.
        
        Returns:
            Dict containing a summary of resource usage
        """
        metrics = self._collect_metrics()
        
        return {
            "cpu": {
                "current": metrics.get("cpu_percent", 0),
                "status": "high" if metrics.get("cpu_percent", 0) > self.thresholds["cpu_percent"] else "normal"
            },
            "memory": {
                "current": metrics.get("memory_percent", 0),
                "available_mb": metrics.get("memory_available", 0) / (1024 * 1024),
                "total_mb": metrics.get("memory_total", 0) / (1024 * 1024),
                "status": "high" if metrics.get("memory_percent", 0) > self.thresholds["memory_percent"] else "normal"
            },
            "disk": {
                "current": metrics.get("disk_percent", 0),
                "status": "high" if metrics.get("disk_percent", 0) > self.thresholds["disk_percent"] else "normal"
            },
            "network": {
                "error_rate": metrics.get("network_error_rate", 0),
                "status": "degraded" if metrics.get("network_error_rate", 0) > self.thresholds["network_error_rate"] else "normal"
            },
            "battery": {
                "current": metrics.get("battery_percent", 100),
                "plugged_in": metrics.get("battery_plugged", True),
                "status": "low" if metrics.get("battery_percent", 0) < self.thresholds["battery_percent"] and not metrics.get("battery_plugged", True) else "normal"
            },
            "uptime": {
                "system_hours": metrics.get("system_uptime", 0) / 3600,
                "app_hours": metrics.get("app_uptime", 0) / 3600
            },
            "process": metrics.get("process", {})
        }
    
    def update_thresholds(self, new_thresholds: Dict[str, float]):
        """
        Update resource monitoring thresholds.
        
        Args:
            new_thresholds: Dict of new threshold values
        """
        for key, value in new_thresholds.items():
            if key in self.thresholds:
                self.thresholds[key] = value
        logger.info(f"Resource thresholds updated: {self.thresholds}")
    
    def set_monitoring_interval(self, seconds: int):
        """
        Set the monitoring interval.
        
        Args:
            seconds: New interval in seconds
        """
        self.interval = max(self.min_interval, min(seconds, self.max_interval))
        logger.info(f"Monitoring interval updated to {self.interval}s")


def initialize_resource_monitor(event_bus=None, config: Dict[str, Any] = None) -> ResourceMonitor:
    """
    Initialize and start the resource monitor.
    
    Args:
        event_bus: Event bus for publishing alerts
        config: Configuration for the resource monitor
        
    Returns:
        Initialized and running ResourceMonitor instance
    """
    logger.info("Initializing Resource Monitor...")
    
    # Create default config if none provided
    if config is None:
        config = {
            "cpu_threshold": 80,
            "memory_threshold": 85,
            "disk_threshold": 90,
            "network_error_threshold": 0.05,
            "battery_threshold": 15,
            "monitoring_interval": 30,
            "history_minutes": 60,
            "alert_cooldown_minutes": 5,
            "adaptive_monitoring": True
        }
    
    # Create and start the resource monitor
    monitor = ResourceMonitor(event_bus=event_bus, config=config)
    monitor.start()
    
    # Register resource monitor with event bus
    if event_bus:
        def handle_get_metrics(event_type, data):
            resource_type = data.get("resource_type") if data else None
            if resource_type == "summary":
                return monitor.get_summary()
            elif resource_type == "current":
                return monitor.get_current_metrics()
            elif resource_type == "history":
                specific_resource = data.get("specific_resource")
                return monitor.get_resource_history(specific_resource)
            # Default to summary if not specified
            return monitor.get_summary()
        
        def handle_update_thresholds(event_type, data):
            if data and isinstance(data, dict):
                monitor.update_thresholds(data)
                return {"success": True, "message": "Thresholds updated"}
            return {"success": False, "message": "Invalid threshold data"}
        
        def handle_set_interval(event_type, data):
            if data and "interval" in data:
                try:
                    interval = int(data["interval"])
                    monitor.set_monitoring_interval(interval)
                    return {"success": True, "message": f"Interval updated to {monitor.interval}s"}
                except (ValueError, TypeError):
                    return {"success": False, "message": "Invalid interval value"}
            return {"success": False, "message": "Missing interval parameter"}
        
        # Subscribe to resource monitoring events
        event_bus.subscribe_sync("resource.get_metrics", handle_get_metrics)
        event_bus.subscribe_sync("resource.update_thresholds", handle_update_thresholds)
        event_bus.subscribe_sync("resource.set_interval", handle_set_interval)
        
        logger.info("Resource Monitor registered with event bus")
    
    return monitor


if __name__ == "__main__":
    # Simple standalone test
    print("Testing Resource Monitor...")
    monitor = ResourceMonitor()
    monitor.start()
    
    try:
        # Monitor for a while and print summaries
        for _ in range(5):
            time.sleep(5)
            summary = monitor.get_summary()
            print("\nResource Summary:")
            print(f"CPU: {summary['cpu']['current']}% ({summary['cpu']['status']})")
            print(f"Memory: {summary['memory']['current']}% ({summary['memory']['status']})")
            print(f"Disk: {summary['disk']['current']}% ({summary['disk']['status']})")
            print(f"Network error rate: {summary['network']['error_rate']*100:.2f}% ({summary['network']['status']})")
            print(f"Battery: {summary['battery']['current']}% ({'Plugged In' if summary['battery']['plugged_in'] else 'Unplugged'})")
            print(f"System uptime: {summary['uptime']['system_hours']:.1f} hours")
    finally:
        monitor.stop()
        print("Resource Monitor stopped")
