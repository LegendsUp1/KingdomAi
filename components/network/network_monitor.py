"""Network Monitor"""
import logging
import time

logger = logging.getLogger(__name__)


class NetworkMonitor:
    def __init__(self):
        self.logger = logger
        self.connections = {}
        self.bandwidth_stats = {"upload": 0.0, "download": 0.0}
        self.latency_history = []
        self.is_monitoring = False
        self.check_interval = 30
        self.alert_threshold_ms = 500
        self.last_check_time = None
        self.logger.info("NetworkMonitor initialized")
