#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-

import logging

logger = logging.getLogger("KingdomAI.TextToSpeech")

class TextToSpeech:
    """State-of-the-art text-to-speech system with Black Panther voice."""
    def __init__(self, config=None, event_bus=None):
        self.config = config or {}
        self.event_bus = event_bus
        logger.info("TextToSpeech initialized")

class BlackPantherVoice(TextToSpeech):
    """Black Panther voice with Wakandan accent and authoritative tone."""
    def __init__(self, config=None, event_bus=None):
        black_panther_config = config or {}
        black_panther_config["voice"] = "black_panther"
        super().__init__(black_panther_config, event_bus)
        logger.info("BlackPantherVoice initialized - Wakanda Forever!")

__all__ = ["TextToSpeech", "BlackPantherVoice"]
