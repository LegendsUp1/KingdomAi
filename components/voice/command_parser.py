"""Voice Command Parser"""
import logging
import re

logger = logging.getLogger(__name__)


class CommandParser:
    def __init__(self):
        self.logger = logger
        self.commands = {}
        self.aliases = {}
        self.command_history = []
        self.max_history = 100
        self.confidence_threshold = 0.6
        self.logger.info("CommandParser initialized")
