#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Voice Integration for Kingdom AI
Provides integration between the voice manager and Black Panther voice model
"""

import os
import logging
import secrets

logger = logging.getLogger(__name__)

class BlackPantherVoice:
    """Black Panther voice integration for Kingdom AI"""
    
    def __init__(self, voice_manager=None, config=None):
        """
        Initialize Black Panther Voice Integration
        
        Args:
            voice_manager: Reference to the VoiceManager component
            config: Configuration dictionary
        """
        self.voice_manager = voice_manager
        self.config = config or {}
        self.samples_loaded = False
        self.samples_dir = self.config.get("black_panther_samples_dir", 
                                          os.path.join(os.path.dirname(__file__), "..", "data", "voices", "black_panther"))
        self.samples = {
            "greetings": [],
            "confirmations": [],
            "questions": [],
            "statements": [],
            "alerts": []
        }
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self):
        """Initialize the Black Panther voice system"""
        self.logger.info("Initializing Black Panther voice integration")
        
        # Create samples directory if it doesn't exist
        os.makedirs(self.samples_dir, exist_ok=True)
        
        # Load samples
        await self.load_samples()
        
        return True
        
    async def load_samples(self):
        """Load Black Panther voice samples from disk"""
        self.logger.info(f"Loading Black Panther voice samples from {self.samples_dir}")
        
        try:
            # Check if directory exists
            if not os.path.exists(self.samples_dir):
                self.logger.warning(f"Black Panther samples directory does not exist: {self.samples_dir}")
                return False
                
            # Load samples from each category directory
            for category in self.samples.keys():
                category_dir = os.path.join(self.samples_dir, category)
                
                # Create directory if it doesn't exist
                os.makedirs(category_dir, exist_ok=True)
                
                # Load samples
                if os.path.exists(category_dir):
                    files = [f for f in os.listdir(category_dir) if f.endswith(('.mp3', '.wav'))]
                    self.samples[category] = [os.path.join(category_dir, f) for f in files]
                    self.logger.info(f"Loaded {len(files)} {category} samples")
                    
            self.samples_loaded = True
            self.logger.info("Black Panther voice samples loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading Black Panther voice samples: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
            
    def get_sample(self, category, text=None):
        """
        Get a voice sample from the specified category
        
        Args:
            category: Sample category (greetings, confirmations, etc.)
            text: Text to match (optional)
            
        Returns:
            Path to the sample file or None if not found
        """
        if not self.samples_loaded:
            self.logger.warning("Black Panther voice samples not loaded")
            return None
            
        if category not in self.samples:
            self.logger.warning(f"Unknown Black Panther voice category: {category}")
            return None
            
        if not self.samples[category]:
            self.logger.warning(f"No Black Panther voice samples for category: {category}")
            return None
            
        # For now, just return a random sample from the category
        return secrets.choice(self.samples[category]) if self.samples[category] else None
        
    def determine_category(self, text):
        """
        Determine the sample category from the text
        
        Args:
            text: Text to analyze
            
        Returns:
            Category name
        """
        text = text.lower()
        
        # Simple rule-based categorization
        if any(w in text for w in ["hello", "hi", "greetings", "hey", "wakanda"]):
            return "greetings"
        elif any(w in text for w in ["yes", "confirm", "agreed", "ok", "okay", "sure", "correct"]):
            return "confirmations"
        elif any(w in text for w in ["?", "what", "who", "where", "when", "why", "how"]):
            return "questions"
        elif any(w in text for w in ["warning", "alert", "danger", "caution", "error"]):
            return "alerts"
        else:
            return "statements"
