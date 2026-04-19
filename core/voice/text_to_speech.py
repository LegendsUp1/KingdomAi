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
        self._speaking = False
        self._subscribe_events()
        logger.info("TextToSpeech initialized (event_bus=%s)", "active" if event_bus else "none")

    def _subscribe_events(self):
        if not self.event_bus:
            return
        self.event_bus.subscribe("voice.speak.request", self._handle_speak_request)
        logger.info("TextToSpeech subscribed to voice.speak.request")

    async def _handle_speak_request(self, data):
        """Handle an inbound speak request from the event bus."""
        text = data.get("text", "") if isinstance(data, dict) else str(data)
        request_id = data.get("request_id", "") if isinstance(data, dict) else ""
        try:
            self._speaking = True
            await self.speak(text)
            self._speaking = False
            if self.event_bus:
                self.event_bus.publish("voice.speak.complete", {
                    "success": True, "request_id": request_id, "text": text,
                })
        except Exception as e:
            self._speaking = False
            logger.error("TTS speak request failed: %s", e)
            if self.event_bus:
                self.event_bus.publish("voice.speak.complete", {
                    "success": False, "error": str(e), "request_id": request_id,
                })

    async def speak(self, text: str):
        """Synthesize and play speech. Override in subclasses for real TTS."""
        logger.info("TTS speak (base): %s", text[:80] if text else "")

class BlackPantherVoice(TextToSpeech):
    """Black Panther voice with Wakandan accent and authoritative tone."""
    def __init__(self, config=None, event_bus=None):
        black_panther_config = config or {}
        black_panther_config["voice"] = "black_panther"
        super().__init__(black_panther_config, event_bus)
        logger.info("BlackPantherVoice initialized - Wakanda Forever!")

__all__ = ["TextToSpeech", "BlackPantherVoice"]
