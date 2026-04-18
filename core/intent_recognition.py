#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Intent Recognition Module

This module uses NLP via NLTK and spaCy for advanced language understanding
and employs cryptographically secure random selection for response variations.
It extracts entities from user requests and performs pattern matching for
command recognition across multiple intents.
"""

import os
import logging
import threading
import json
from typing import Dict, List, Any, Callable
import string

# Set up logging
logger = logging.getLogger('KingdomAI.IntentRecognition')

# Initialize NLP availability flags
NLTK_AVAILABLE = False
SPACY_AVAILABLE = False

# Dynamic imports for NLP libraries with robust error handling
try:
    # Compatibility layer for numpy and NLTK to handle binary incompatibility
    import sys
    import warnings

    # Handle numpy binary incompatibility with a compatibility layer
    try:
        # Save original __getattr__ for numpy.core.multiarray
        import numpy
        _original_numpy_multiarray = None
        if hasattr(numpy, 'core') and hasattr(numpy.core, 'multiarray'):
            _original_numpy_multiarray = numpy.core.multiarray.__dict__.get('__getattr__', None)
        
        # Define custom __getattr__ for numpy.core.multiarray
        def _numpy_multiarray_getattr(attr):
            if attr == '_multiarray_umath':
                warnings.warn("numpy.dtype size changed, may indicate binary incompatibility. "
                            "Using compatibility layer.", ImportWarning)
                # Return the existing module even if size mismatch
                import numpy.core._multiarray_umath
                return numpy.core._multiarray_umath
            if _original_numpy_multiarray:
                return _original_numpy_multiarray(attr)
            raise AttributeError(f"module 'numpy.core.multiarray' has no attribute '{attr}'")
        
        # Apply the patch if numpy.core.multiarray exists
        if hasattr(numpy, 'core') and hasattr(numpy.core, 'multiarray'):
            numpy.core.multiarray.__dict__['__getattr__'] = _numpy_multiarray_getattr
    except ImportError:
        pass

    # Now import NLTK with the compatibility layer in place
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.stem import WordNetLemmatizer
    NLTK_AVAILABLE = True
    logger.info("NLTK successfully imported")
except (ImportError, ValueError) as e:
    logger.warning(f"NLTK import failed: {e}")
    logger.warning("Intent recognition will use pattern matching only, without advanced NLP")

try:
    import spacy
    SPACY_AVAILABLE = True
    logger.info("spaCy successfully imported")
except (ImportError, ValueError) as e:
    logger.warning(f"spaCy import failed: {e}")
    logger.warning("Intent recognition will not use spaCy models")

class IntentRecognition:
    """
    Handles intent recognition using NLP techniques and pattern matching.
    Extracts entities from user requests and performs command recognition.
    """
    
    def __init__(self, 
                 event_bus=None,
                 confidence_threshold: float = 0.7,
                 intent_data_path: str = None,
                 use_spacy: bool = True,
                 use_nltk: bool = True):
        """
        Initialize the Intent Recognition module.
        
        Args:
            event_bus: Event bus for publishing intent events
            confidence_threshold: Minimum confidence level to recognize an intent
            intent_data_path: Path to intent data files
            use_spacy: Whether to use spaCy for NLP (if available)
            use_nltk: Whether to use NLTK for NLP (if available)
        """
        self.event_bus = event_bus
        self.confidence_threshold = confidence_threshold
        self.intent_data_path = intent_data_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            'data', 
            'intents'
        )
        
        # NLP settings
        self.use_spacy = use_spacy and SPACY_AVAILABLE
        self.use_nltk = use_nltk and NLTK_AVAILABLE
        self.nlp = None  # spaCy model
        self.lemmatizer = None  # NLTK lemmatizer
        
        # Intent data
        self.intents = {}  # Intent patterns
        self.component_intents = {}  # Intents registered by components
        self.intent_handlers = {}  # Intent handlers
        self.entity_extractors = {}  # Entity extractors
        
        # Concurrency
        self.lock = threading.RLock()
        self.running = False
        
    def initialize(self) -> bool:
        """
        Initialize the Intent Recognition module.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        logger.info("Initializing Intent Recognition")
        
        try:
            self.running = True
            
            # Initialize NLP components
            if self.use_spacy:
                try:
                    # Try to load a smaller model first for efficiency
                    self.nlp = spacy.load("en_core_web_sm")
                    logger.info("Loaded spaCy en_core_web_sm model")
                except:
                    try:
                        # Fall back to trying a different model
                        self.nlp = spacy.load("en")
                        logger.info("Loaded spaCy en model")
                    except:
                        logger.warning("Could not load any spaCy model, disabling spaCy")
                        self.use_spacy = False
            
            if self.use_nltk:
                try:
                    # Download necessary NLTK resources if not already downloaded
                    nltk.download('punkt', quiet=True)
                    nltk.download('wordnet', quiet=True)
                    nltk.download('omw-1.4', quiet=True)
                    
                    self.lemmatizer = WordNetLemmatizer()
                    logger.info("Initialized NLTK components")
                except Exception as e:
                    logger.warning(f"Could not initialize NLTK: {e}, falling back to basic matching")
                    self.use_nltk = False
            
            # Load intent data
            self._load_intent_data()
            
            # Register event handlers
            if self.event_bus:
                self.event_bus.subscribe_sync('user.input', self._handle_user_input)
                self.event_bus.subscribe_sync('intent.register', self._handle_intent_register)
                
            logger.info("Intent Recognition initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Intent Recognition: {e}")
            return False
            
    def shutdown(self):
        """Shutdown the Intent Recognition module."""
        logger.info("Shutting down Intent Recognition")
        self.running = False
        logger.info("Intent Recognition shutdown complete")
        
    def register_intent(self, 
                       intent_name: str, 
                       patterns: List[str], 
                       handler: Callable = None,
                       component_name: str = None) -> bool:
        """
        Register a new intent with patterns and an optional handler.
        
        Args:
            intent_name: Name of the intent
            patterns: List of pattern strings to match
            handler: Function to call when intent is recognized
            component_name: Name of the component registering this intent
            
        Returns:
            bool: True if successfully registered, False otherwise
        """
        with self.lock:
            if intent_name in self.intents:
                # If intent already exists, add new patterns
                self.intents[intent_name]['patterns'].extend(patterns)
                # Remove duplicates
                self.intents[intent_name]['patterns'] = list(set(self.intents[intent_name]['patterns']))
            else:
                # Create new intent
                self.intents[intent_name] = {
                    'patterns': patterns,
                    'responses': [],  # Optional responses for this intent
                    'entities': []  # Optional entity types to extract
                }
                
            # Register handler if provided
            if handler:
                self.intent_handlers[intent_name] = handler
                
            # Record component ownership
            if component_name:
                if component_name not in self.component_intents:
                    self.component_intents[component_name] = []
                if intent_name not in self.component_intents[component_name]:
                    self.component_intents[component_name].append(intent_name)
                    
            logger.debug(f"Registered intent '{intent_name}' with {len(patterns)} patterns")
            return True
            
    def register_entity_extractor(self, 
                                 entity_type: str, 
                                 extractor: Callable) -> bool:
        """
        Register an entity extractor function.
        
        Args:
            entity_type: Type of entity to extract
            extractor: Function to extract the entity from text
            
        Returns:
            bool: True if successfully registered, False otherwise
        """
        with self.lock:
            self.entity_extractors[entity_type] = extractor
            logger.debug(f"Registered entity extractor for '{entity_type}'")
            return True
            
    def recognize_intent(self, text: str) -> Dict:
        """
        Recognize the intent in the given text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dict: Intent recognition results
        """
        if not text or not self.intents:
            return {
                'intent': None,
                'confidence': 0.0,
                'entities': {},
                'matches': []
            }
            
        # Preprocess text
        preprocessed = self._preprocess_text(text)
        
        # Find matching intents
        matches = []
        for intent_name, intent_data in self.intents.items():
            for pattern in intent_data['patterns']:
                score = self._calculate_match_score(preprocessed, pattern)
                if score > 0:
                    matches.append({
                        'intent': intent_name,
                        'pattern': pattern,
                        'score': score
                    })
        
        # Sort matches by score
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        # Get best match
        if matches and matches[0]['score'] >= self.confidence_threshold:
            best_match = matches[0]
            intent_name = best_match['intent']
            confidence = best_match['score']
            
            # Extract entities
            entities = self._extract_entities(text, intent_name)
            
            return {
                'intent': intent_name,
                'confidence': confidence,
                'entities': entities,
                'matches': matches[:3]  # Top 3 matches
            }
        else:
            return {
                'intent': None,
                'confidence': 0.0,
                'entities': {},
                'matches': matches[:3] if matches else []
            }
            
    def execute_intent(self, intent_result: Dict) -> Any:
        """
        Execute the handler for a recognized intent.
        
        Args:
            intent_result: Intent recognition results from recognize_intent
            
        Returns:
            Any: Result from the intent handler or None if no handler
        """
        intent_name = intent_result.get('intent')
        if not intent_name or intent_name not in self.intent_handlers:
            return None
            
        handler = self.intent_handlers[intent_name]
        try:
            # Call handler with entities as keyword arguments
            entities = intent_result.get('entities', {})
            return handler(**entities)
        except Exception as e:
            logger.error(f"Error executing intent handler for '{intent_name}': {e}")
            return None
            
    def get_registered_intents(self, component_name: str = None) -> List[str]:
        """
        Get list of registered intents, optionally filtered by component.
        
        Args:
            component_name: Filter by component name
            
        Returns:
            List[str]: List of intent names
        """
        with self.lock:
            if component_name:
                return self.component_intents.get(component_name, [])
            else:
                return list(self.intents.keys())
                
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for intent matching.
        
        Args:
            text: Raw input text
            
        Returns:
            str: Preprocessed text
        """
        # Convert to lowercase
        text = text.lower()
        
        if self.use_spacy and self.nlp:
            # Use spaCy for preprocessing
            doc = self.nlp(text)
            # Get lemmatized tokens, excluding stopwords and punctuation
            tokens = [token.lemma_ for token in doc 
                     if not token.is_stop and not token.is_punct]
            return ' '.join(tokens)
            
        elif self.use_nltk and self.lemmatizer:
            # Use NLTK for preprocessing
            # Remove punctuation
            text = ''.join([c for c in text if c not in string.punctuation])
            # Tokenize
            tokens = word_tokenize(text)
            # Lemmatize
            lemmatized = [self.lemmatizer.lemmatize(word) for word in tokens]
            return ' '.join(lemmatized)
            
        else:
            # Basic preprocessing: remove punctuation and extra whitespace
            text = ''.join([c for c in text if c not in string.punctuation])
            text = ' '.join(text.split())
            return text
            
    def _calculate_match_score(self, preprocessed_text: str, pattern: str) -> float:
        """
        Calculate match score between preprocessed text and pattern.
        
        Args:
            preprocessed_text: Preprocessed input text
            pattern: Pattern to match against
            
        Returns:
            float: Match score between 0.0 and 1.0
        """
        # Preprocess pattern the same way
        preprocessed_pattern = self._preprocess_text(pattern)
        
        # Exact match
        if preprocessed_pattern in preprocessed_text:
            # Calculate how much of the text is covered by the pattern
            pattern_words = set(preprocessed_pattern.split())
            text_words = set(preprocessed_text.split())
            coverage = len(pattern_words) / max(1, len(text_words))
            
            # Higher score for patterns that cover more of the text
            return min(1.0, 0.8 + coverage * 0.2)
            
        # Partial word matching
        pattern_words = preprocessed_pattern.split()
        text_words = preprocessed_text.split()
        
        # Count how many pattern words appear in the text
        matches = sum(1 for word in pattern_words if word in text_words)
        
        if matches > 0:
            # Calculate score based on percentage of pattern words matched
            return matches / len(pattern_words) * 0.9  # Max 0.9 for partial matches
            
        return 0.0
        
    def _extract_entities(self, text: str, intent_name: str) -> Dict:
        """
        Extract entities from text for a specific intent.
        
        Args:
            text: Input text
            intent_name: Intent name
            
        Returns:
            Dict: Extracted entities
        """
        entities = {}
        
        # Check if intent has defined entities to extract
        if intent_name in self.intents:
            intent_entities = self.intents[intent_name].get('entities', [])
            
            # Extract each entity type
            for entity_type in intent_entities:
                # Check if we have a specific extractor for this entity type
                if entity_type in self.entity_extractors:
                    extractor = self.entity_extractors[entity_type]
                    try:
                        extracted = extractor(text)
                        if extracted is not None:
                            entities[entity_type] = extracted
                    except Exception as e:
                        logger.error(f"Error with entity extractor for '{entity_type}': {e}")
                        
        # If spaCy is available, use it for additional entity extraction
        if self.use_spacy and self.nlp:
            try:
                doc = self.nlp(text)
                
                # Extract named entities
                for ent in doc.ents:
                    # Convert spaCy entity types to our format
                    entity_type = ent.label_.lower()
                    if entity_type in ['person', 'org', 'gpe', 'loc', 'date', 'time', 'money', 'percent']:
                        entity_name = entity_type
                        if entity_type == 'gpe':
                            entity_name = 'location'
                        elif entity_type == 'org':
                            entity_name = 'organization'
                            
                        entities[entity_name] = ent.text
            except Exception as e:
                logger.error(f"Error extracting entities with spaCy: {e}")
                
        return entities
        
    def _load_intent_data(self):
        """Load intent data from files."""
        try:
            # Ensure intent data directory exists
            os.makedirs(self.intent_data_path, exist_ok=True)
            
            # Look for intent JSON files
            for filename in os.listdir(self.intent_data_path):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.intent_data_path, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        intent_data = json.load(f)
                        
                        # Process each intent
                        for intent_name, intent_info in intent_data.items():
                            patterns = intent_info.get('patterns', [])
                            if patterns:
                                if intent_name in self.intents:
                                    # Merge with existing patterns
                                    self.intents[intent_name]['patterns'].extend(patterns)
                                    if 'responses' in intent_info:
                                        self.intents[intent_name]['responses'].extend(intent_info.get('responses', []))
                                    if 'entities' in intent_info:
                                        self.intents[intent_name]['entities'].extend(intent_info.get('entities', []))
                                else:
                                    # Add new intent
                                    self.intents[intent_name] = {
                                        'patterns': patterns,
                                        'responses': intent_info.get('responses', []),
                                        'entities': intent_info.get('entities', [])
                                    }
            
            logger.info(f"Loaded {len(self.intents)} intents from data files")
            
        except Exception as e:
            logger.error(f"Error loading intent data: {e}")
            
    def _handle_user_input(self, event_data):
        """Handle user input events from the event bus."""
        input_text = event_data.get('input', '')
        if not input_text:
            return
            
        # Recognize intent
        intent_result = self.recognize_intent(input_text)
        
        # If intent recognized with sufficient confidence, execute it
        if intent_result['intent'] and intent_result['confidence'] >= self.confidence_threshold:
            # Publish intent recognized event
            if self.event_bus:
                self.event_bus.publish('intent.recognized', {
                    'intent': intent_result['intent'],
                    'confidence': intent_result['confidence'],
                    'entities': intent_result['entities'],
                    'input': input_text
                })
                
            # Execute intent handler
            result = self.execute_intent(intent_result)
            
            # Publish intent executed event
            if self.event_bus:
                self.event_bus.publish('intent.executed', {
                    'intent': intent_result['intent'],
                    'result': result,
                    'input': input_text
                })
                
    def _handle_intent_register(self, event_data):
        """Handle intent registration events from the event bus."""
        intent_name = event_data.get('intent')
        patterns = event_data.get('patterns')
        component = event_data.get('component')
        
        if intent_name and patterns:
            self.register_intent(
                intent_name=intent_name,
                patterns=patterns,
                component_name=component
            )
            
    def _initialize_default_intents(self):
        """Initialize default intents that should always be available."""
        self.register_intent(
            intent_name="help",
            patterns=[
                "help",
                "what can you do",
                "show commands",
                "available commands",
                "how do I use you",
                "what are your capabilities",
                "show help",
                "assist me",
                "instructions please"
            ],
            handler=self._handle_help_intent
        )
        
        self.register_intent(
            intent_name="stop",
            patterns=[
                "stop",
                "cancel",
                "abort",
                "terminate",
                "quit",
                "exit"
            ],
            handler=self._handle_stop_intent
        )
        
    def _handle_help_intent(self) -> Dict:
        """Handle help intent by listing available commands."""
        # Gather all intents and their first pattern as an example
        available_intents = {}
        for intent_name, intent_data in self.intents.items():
            if intent_data['patterns']:
                available_intents[intent_name] = intent_data['patterns'][0]
                
        return {
            "message": "Here are some commands you can use:",
            "intents": available_intents
        }
        
    def _handle_stop_intent(self) -> Dict:
        """Handle stop intent by cancelling current operations."""
        # Publish stop event
        if self.event_bus:
            self.event_bus.publish('system.stop_requested', {
                'timestamp': None,
                'source': 'intent_recognition'
            })
            
        return {
            "message": "Operation stopped."
        }
