#!/usr/bin/env python3
"""
Kingdom AI - SOTA 2026 Enhanced Learning System
================================================

Advanced learning system with fact correlation, knowledge synthesis,
and multimodal data integration for Ollama brain.

Features:
- Fact correlation across all data types (text, images, videos, audio)
- Knowledge graph construction from learned data
- Memory persistence and recall
- Image composition from learned visual concepts
- Cross-domain knowledge transfer
- Temporal learning patterns
"""

import os
import json
import logging
import asyncio
import hashlib
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np

logger = logging.getLogger("KingdomAI.EnhancedLearning")

# Check dependencies
HAS_NETWORKX = False
HAS_SKLEARN = False
HAS_TORCH = False

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    logger.warning("networkx not available - knowledge graph disabled")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    logger.warning("sklearn not available - similarity computation limited")

try:
    import torch
    HAS_TORCH = True
except ImportError:
    logger.warning("torch not available - embedding operations limited")


@dataclass
class Fact:
    """A learned fact with metadata."""
    content: str
    source: str  # url, file, interaction
    source_type: str  # text, image, video, audio
    timestamp: str
    confidence: float = 1.0
    related_facts: List[str] = field(default_factory=list)
    embeddings: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    fact_id: str = ""
    
    def __post_init__(self):
        if not self.fact_id:
            self.fact_id = hashlib.sha256(
                f"{self.content}{self.source}{self.timestamp}".encode()
            ).hexdigest()[:16]


@dataclass
class VisualConcept:
    """A learned visual concept for image composition."""
    name: str
    description: str
    source_images: List[str] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    concept_id: str = ""
    
    def __post_init__(self):
        if not self.concept_id:
            self.concept_id = hashlib.sha256(
                f"{self.name}{self.description}".encode()
            ).hexdigest()[:16]


class KnowledgeGraph:
    """Knowledge graph for fact correlation."""
    
    def __init__(self):
        self.graph = nx.DiGraph() if HAS_NETWORKX else None
        self.facts: Dict[str, Fact] = {}
        self.topics: Dict[str, Set[str]] = defaultdict(set)  # topic -> fact_ids
        
    def add_fact(self, fact: Fact):
        """Add a fact to the knowledge graph."""
        self.facts[fact.fact_id] = fact
        
        if self.graph is not None:
            self.graph.add_node(fact.fact_id, fact=fact)
            
            # Connect to related facts
            for related_id in fact.related_facts:
                if related_id in self.facts:
                    self.graph.add_edge(fact.fact_id, related_id, weight=0.8)
    
    def find_related_facts(self, fact_id: str, max_depth: int = 2) -> List[Fact]:
        """Find facts related to a given fact."""
        if not self.graph or fact_id not in self.facts:
            return []
        
        related_ids = set()
        
        # BFS to find related facts
        visited = {fact_id}
        queue = [(fact_id, 0)]
        
        while queue:
            current_id, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            for neighbor in self.graph.neighbors(current_id):
                if neighbor not in visited:
                    visited.add(neighbor)
                    related_ids.add(neighbor)
                    queue.append((neighbor, depth + 1))
        
        return [self.facts[fid] for fid in related_ids if fid in self.facts]
    
    def find_facts_by_topic(self, topic: str) -> List[Fact]:
        """Find all facts related to a topic."""
        fact_ids = self.topics.get(topic.lower(), set())
        return [self.facts[fid] for fid in fact_ids if fid in self.facts]
    
    def correlate_facts(self, query: str, top_k: int = 10) -> List[Tuple[Fact, float]]:
        """Find facts most relevant to a query using embeddings."""
        if not HAS_SKLEARN or not self.facts:
            return []
        
        try:
            # Get all fact contents
            fact_ids = list(self.facts.keys())
            fact_contents = [self.facts[fid].content for fid in fact_ids]
            
            # Compute TF-IDF vectors
            vectorizer = TfidfVectorizer(max_features=1000)
            tfidf_matrix = vectorizer.fit_transform(fact_contents + [query])
            
            # Compute similarity
            query_vector = tfidf_matrix[-1]
            fact_vectors = tfidf_matrix[:-1]
            similarities = cosine_similarity(query_vector, fact_vectors)[0]
            
            # Get top-k
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    results.append((self.facts[fact_ids[idx]], float(similarities[idx])))
            
            return results
            
        except Exception as e:
            logger.warning(f"Failed to correlate facts: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge graph statistics."""
        return {
            'total_facts': len(self.facts),
            'total_topics': len(self.topics),
            'graph_nodes': self.graph.number_of_nodes() if self.graph else 0,
            'graph_edges': self.graph.number_of_edges() if self.graph else 0,
        }


class EnhancedLearningSystemSOTA2026:
    """SOTA 2026 Enhanced Learning System with fact correlation and knowledge synthesis."""
    
    def __init__(self, event_bus=None, ollama_learning=None, storage_dir: Optional[str] = None):
        """Initialize the enhanced learning system.
        
        Args:
            event_bus: EventBus for learning events
            ollama_learning: OllamaLearningSystem for AI processing
            storage_dir: Directory for storing learned knowledge
        """
        self.event_bus = event_bus
        self.ollama_learning = ollama_learning
        self.storage_dir = storage_dir or str(Path(__file__).parent.parent / "data" / "learned_knowledge")
        
        # Create storage directories
        os.makedirs(self.storage_dir, exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "facts"), exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "visual_concepts"), exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "knowledge_graphs"), exist_ok=True)
        
        # Knowledge structures
        self.knowledge_graph = KnowledgeGraph()
        self.visual_concepts: Dict[str, VisualConcept] = {}
        self.learning_history: List[Dict[str, Any]] = []
        
        # Learning parameters
        self.max_history = 10000
        self.fact_confidence_threshold = 0.5
        self.correlation_threshold = 0.3
        
        logger.info(f"✅ SOTA 2026 Enhanced Learning System initialized (storage={self.storage_dir})")
        logger.info(f"   Available: networkx={HAS_NETWORKX}, sklearn={HAS_SKLEARN}, torch={HAS_TORCH}")
    
    async def initialize(self) -> bool:
        """Initialize the learning system."""
        try:
            # Load existing knowledge
            await self._load_knowledge()
            
            # Subscribe to learning events
            if self.event_bus:
                # Multimodal learning events
                self.event_bus.subscribe("learning.web_content", self._learn_from_web_content)
                self.event_bus.subscribe("learning.image", self._learn_from_image)
                self.event_bus.subscribe("learning.video", self._learn_from_video)
                self.event_bus.subscribe("learning.audio", self._learn_from_audio)
                self.event_bus.subscribe("learning.text", self._learn_from_text)
                
                # Query events
                self.event_bus.subscribe("learning.query_facts", self._handle_fact_query)
                self.event_bus.subscribe("learning.correlate", self._handle_correlation_request)
                self.event_bus.subscribe("learning.synthesize", self._handle_synthesis_request)
                
                # Visual composition events
                self.event_bus.subscribe("learning.compose_image", self._handle_image_composition)
                
                logger.info("✅ Subscribed to learning events")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced learning system: {e}")
            return False
    
    async def learn_fact(self, content: str, source: str, source_type: str,
                        metadata: Optional[Dict] = None) -> Fact:
        """Learn a new fact and integrate into knowledge graph.
        
        Args:
            content: The fact content
            source: Source of the fact (URL, file, etc.)
            source_type: Type of source (text, image, video, audio)
            metadata: Additional metadata
            
        Returns:
            The created Fact object
        """
        # Create fact
        fact = Fact(
            content=content,
            source=source,
            source_type=source_type,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        
        # Extract topics using Ollama
        if self.ollama_learning:
            topics = await self._extract_topics(content)
            fact.metadata['topics'] = topics
            
            # Add to topic index
            for topic in topics:
                self.knowledge_graph.topics[topic.lower()].add(fact.fact_id)
        
        # Find related facts
        related_facts = await self._find_related_facts(fact)
        fact.related_facts = [f.fact_id for f in related_facts]
        
        # Add to knowledge graph
        self.knowledge_graph.add_fact(fact)
        
        # Store fact
        await self._store_fact(fact)
        
        # Add to history
        self.learning_history.append({
            'type': 'fact_learned',
            'fact_id': fact.fact_id,
            'content_preview': content[:100],
            'source_type': source_type,
            'timestamp': fact.timestamp
        })
        
        # Limit history size
        if len(self.learning_history) > self.max_history:
            self.learning_history = self.learning_history[-self.max_history:]
        
        # Publish event
        if self.event_bus:
            self.event_bus.publish("learning.fact_learned", {
                'fact_id': fact.fact_id,
                'content': content,
                'source_type': source_type,
                'topics': fact.metadata.get('topics', []),
                'related_count': len(fact.related_facts)
            })
        
        logger.info(f"✅ Learned fact: {content[:50]}... (related to {len(fact.related_facts)} facts)")
        return fact
    
    async def _extract_topics(self, content: str) -> List[str]:
        """Extract topics from content using Ollama."""
        if not self.ollama_learning:
            return []
        
        try:
            from core.ollama_learning_integration import TaskType
            
            result = await self.ollama_learning.process(
                prompt=f"Extract 3-5 key topics or keywords from this text. Return only the topics as a comma-separated list:\n\n{content[:1000]}",
                task_type=TaskType.SUMMARIZATION,
                prefer_speed=True
            )
            
            response = result.get('response', '')
            topics = [t.strip() for t in response.split(',') if t.strip()]
            return topics[:5]  # Limit to 5 topics
            
        except Exception as e:
            logger.warning(f"Failed to extract topics: {e}")
            return []
    
    async def _find_related_facts(self, fact: Fact) -> List[Fact]:
        """Find facts related to a new fact."""
        if not self.knowledge_graph.facts:
            return []
        
        # Use knowledge graph correlation
        related = self.knowledge_graph.correlate_facts(fact.content, top_k=5)
        return [f for f, score in related if score > self.correlation_threshold]
    
    async def learn_visual_concept(self, name: str, description: str,
                                   image_paths: List[str],
                                   tags: Optional[List[str]] = None) -> VisualConcept:
        """Learn a visual concept from images.
        
        Args:
            name: Name of the concept
            description: Description of the concept
            image_paths: Paths to example images
            tags: Optional tags for categorization
            
        Returns:
            The created VisualConcept object
        """
        concept = VisualConcept(
            name=name,
            description=description,
            source_images=image_paths,
            tags=tags or []
        )
        
        # Analyze images with Ollama if available
        if self.ollama_learning and image_paths:
            try:
                from core.ollama_learning_integration import TaskType
                
                # Analyze first image to extract features
                result = await self.ollama_learning.process(
                    prompt=f"Analyze this image representing '{name}'. Describe key visual features, colors, shapes, and patterns.",
                    task_type=TaskType.IMAGE_ANALYSIS,
                    images=[image_paths[0]],
                    prefer_quality=True
                )
                
                concept.features['analysis'] = result.get('response', '')
                
            except Exception as e:
                logger.warning(f"Failed to analyze visual concept: {e}")
        
        # Store concept
        self.visual_concepts[concept.concept_id] = concept
        await self._store_visual_concept(concept)
        
        # Publish event
        if self.event_bus:
            self.event_bus.publish("learning.visual_concept_learned", {
                'concept_id': concept.concept_id,
                'name': name,
                'image_count': len(image_paths),
                'tags': tags
            })
        
        logger.info(f"✅ Learned visual concept: {name} ({len(image_paths)} images)")
        return concept
    
    async def correlate_facts_by_topic(self, topic: str) -> List[Fact]:
        """Find all facts related to a topic."""
        facts = self.knowledge_graph.find_facts_by_topic(topic)
        
        # Publish event
        if self.event_bus:
            self.event_bus.publish("learning.facts_correlated", {
                'topic': topic,
                'fact_count': len(facts),
                'facts': [{'id': f.fact_id, 'content': f.content[:100]} for f in facts[:10]]
            })
        
        return facts
    
    async def synthesize_knowledge(self, query: str, max_facts: int = 20) -> str:
        """Synthesize knowledge from learned facts to answer a query.
        
        Args:
            query: The query to answer
            max_facts: Maximum number of facts to use
            
        Returns:
            Synthesized answer
        """
        # Find relevant facts
        relevant_facts = self.knowledge_graph.correlate_facts(query, top_k=max_facts)
        
        if not relevant_facts:
            return "No relevant knowledge found."
        
        # Build context from facts
        context = "\n\n".join([
            f"Fact {i+1} (confidence {score:.2f}): {fact.content}"
            for i, (fact, score) in enumerate(relevant_facts[:10])
        ])
        
        # Use Ollama to synthesize answer
        if self.ollama_learning:
            try:
                from core.ollama_learning_integration import TaskType
                
                result = await self.ollama_learning.process(
                    prompt=f"Based on the following learned facts, answer this question: {query}\n\nLearned Facts:\n{context}",
                    task_type=TaskType.KNOWLEDGE_SYNTHESIS,
                    prefer_quality=True
                )
                
                synthesis = result.get('response', '')
                
                # Publish event
                if self.event_bus:
                    self.event_bus.publish("learning.knowledge_synthesized", {
                        'query': query,
                        'facts_used': len(relevant_facts),
                        'synthesis_preview': synthesis[:200]
                    })
                
                return synthesis
                
            except Exception as e:
                logger.error(f"Failed to synthesize knowledge: {e}")
                return f"Error synthesizing knowledge: {e}"
        
        return context
    
    async def compose_image_from_concepts(self, concept_names: List[str],
                                         composition_prompt: str) -> Optional[str]:
        """Compose a new image from learned visual concepts.
        
        Args:
            concept_names: Names of visual concepts to combine
            composition_prompt: How to combine the concepts
            
        Returns:
            Path to generated image, or None on error
        """
        # Find concepts
        concepts = []
        for name in concept_names:
            for concept in self.visual_concepts.values():
                if concept.name.lower() == name.lower():
                    concepts.append(concept)
                    break
        
        if not concepts:
            logger.warning(f"No visual concepts found for: {concept_names}")
            return None
        
        # Build detailed prompt from concepts
        concept_descriptions = []
        for concept in concepts:
            desc = f"{concept.name}: {concept.description}"
            if concept.features.get('analysis'):
                desc += f" ({concept.features['analysis'][:100]})"
            concept_descriptions.append(desc)
        
        full_prompt = f"{composition_prompt}\n\nVisual Concepts:\n" + "\n".join(concept_descriptions)
        
        # Generate image using visual creation system
        if self.event_bus:
            self.event_bus.publish("visual.generate", {
                'prompt': full_prompt,
                'mode': 'image',
                'source': 'learned_concepts',
                'concepts_used': [c.name for c in concepts]
            })
        
        logger.info(f"✅ Requested image composition from concepts: {concept_names}")
        return None  # Actual path will come from visual.generated event
    
    # Event handlers
    async def _learn_from_web_content(self, data: Dict[str, Any]):
        """Learn from scraped web content."""
        url = data.get('url', '')
        text = data.get('text_preview', '')
        analysis = data.get('analysis', '')
        
        if text:
            await self.learn_fact(
                content=text,
                source=url,
                source_type='web_text',
                metadata={'analysis': analysis}
            )
        
        # Learn from images
        for img_data in data.get('images', [])[:5]:
            if img_data.get('analysis'):
                await self.learn_fact(
                    content=img_data['analysis'],
                    source=img_data.get('url', url),
                    source_type='web_image',
                    metadata={'image_url': img_data.get('url')}
                )
    
    async def _learn_from_image(self, data: Dict[str, Any]):
        """Learn from image analysis."""
        analysis = data.get('analysis', '')
        image_path = data.get('image_path', '')
        
        if analysis:
            await self.learn_fact(
                content=analysis,
                source=image_path,
                source_type='image',
                metadata=data.get('metadata', {})
            )
    
    async def _learn_from_video(self, data: Dict[str, Any]):
        """Learn from video analysis."""
        analysis = data.get('analysis', {})
        video_path = data.get('video_path', '')
        
        # Learn from frame analyses
        for frame_analysis in analysis.get('frame_analyses', []):
            if frame_analysis:
                await self.learn_fact(
                    content=frame_analysis,
                    source=video_path,
                    source_type='video',
                    metadata={'video_path': video_path}
                )
    
    async def _learn_from_audio(self, data: Dict[str, Any]):
        """Learn from audio transcription."""
        transcription = data.get('transcription', '')
        audio_path = data.get('audio_path', '')
        
        if transcription:
            await self.learn_fact(
                content=transcription,
                source=audio_path,
                source_type='audio',
                metadata={'audio_path': audio_path}
            )
    
    async def _learn_from_text(self, data: Dict[str, Any]):
        """Learn from text content."""
        text = data.get('text', '')
        source = data.get('source', 'unknown')
        
        if text:
            await self.learn_fact(
                content=text,
                source=source,
                source_type='text',
                metadata=data.get('metadata', {})
            )
    
    async def _handle_fact_query(self, data: Dict[str, Any]):
        """Handle learning.query_facts event."""
        query = data.get('query', '')
        max_results = data.get('max_results', 10)
        
        facts = self.knowledge_graph.correlate_facts(query, top_k=max_results)
        
        if self.event_bus:
            self.event_bus.publish("learning.query_facts.result", {
                'query': query,
                'facts': [
                    {'content': f.content, 'source': f.source, 'score': score}
                    for f, score in facts
                ]
            })
    
    async def _handle_correlation_request(self, data: Dict[str, Any]):
        """Handle learning.correlate event."""
        topic = data.get('topic', '')
        
        facts = await self.correlate_facts_by_topic(topic)
        
        if self.event_bus:
            self.event_bus.publish("learning.correlate.result", {
                'topic': topic,
                'facts': [
                    {'id': f.fact_id, 'content': f.content, 'source': f.source}
                    for f in facts
                ]
            })
    
    async def _handle_synthesis_request(self, data: Dict[str, Any]):
        """Handle learning.synthesize event."""
        query = data.get('query', '')
        
        synthesis = await self.synthesize_knowledge(query)
        
        if self.event_bus:
            self.event_bus.publish("learning.synthesize.result", {
                'query': query,
                'synthesis': synthesis
            })
    
    async def _handle_image_composition(self, data: Dict[str, Any]):
        """Handle learning.compose_image event."""
        concepts = data.get('concepts', [])
        prompt = data.get('prompt', '')
        
        await self.compose_image_from_concepts(concepts, prompt)
    
    # Storage methods
    async def _store_fact(self, fact: Fact):
        """Store a fact to disk."""
        try:
            fact_file = os.path.join(self.storage_dir, "facts", f"{fact.fact_id}.json")
            
            fact_dict = {
                'content': fact.content,
                'source': fact.source,
                'source_type': fact.source_type,
                'timestamp': fact.timestamp,
                'confidence': fact.confidence,
                'related_facts': fact.related_facts,
                'metadata': fact.metadata,
                'fact_id': fact.fact_id
            }
            
            with open(fact_file, 'w', encoding='utf-8') as f:
                json.dump(fact_dict, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"Failed to store fact: {e}")
    
    async def _store_visual_concept(self, concept: VisualConcept):
        """Store a visual concept to disk."""
        try:
            concept_file = os.path.join(
                self.storage_dir, "visual_concepts",
                f"{concept.concept_id}.json"
            )
            
            concept_dict = {
                'name': concept.name,
                'description': concept.description,
                'source_images': concept.source_images,
                'features': concept.features,
                'tags': concept.tags,
                'concept_id': concept.concept_id
            }
            
            with open(concept_file, 'w', encoding='utf-8') as f:
                json.dump(concept_dict, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"Failed to store visual concept: {e}")
    
    async def _load_knowledge(self):
        """Load existing knowledge from disk."""
        try:
            # Load facts
            facts_dir = os.path.join(self.storage_dir, "facts")
            if os.path.exists(facts_dir):
                for fact_file in Path(facts_dir).glob("*.json"):
                    try:
                        with open(fact_file, 'r', encoding='utf-8') as f:
                            fact_dict = json.load(f)
                        
                        fact = Fact(**fact_dict)
                        self.knowledge_graph.add_fact(fact)
                        
                        # Rebuild topic index
                        for topic in fact.metadata.get('topics', []):
                            self.knowledge_graph.topics[topic.lower()].add(fact.fact_id)
                            
                    except Exception as e:
                        logger.warning(f"Failed to load fact {fact_file}: {e}")
            
            # Load visual concepts
            concepts_dir = os.path.join(self.storage_dir, "visual_concepts")
            if os.path.exists(concepts_dir):
                for concept_file in Path(concepts_dir).glob("*.json"):
                    try:
                        with open(concept_file, 'r', encoding='utf-8') as f:
                            concept_dict = json.load(f)
                        
                        concept = VisualConcept(**concept_dict)
                        self.visual_concepts[concept.concept_id] = concept
                        
                    except Exception as e:
                        logger.warning(f"Failed to load visual concept {concept_file}: {e}")
            
            logger.info(f"✅ Loaded {len(self.knowledge_graph.facts)} facts and {len(self.visual_concepts)} visual concepts")
            
        except Exception as e:
            logger.error(f"Failed to load knowledge: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get learning system statistics."""
        return {
            'knowledge_graph': self.knowledge_graph.get_stats(),
            'visual_concepts': len(self.visual_concepts),
            'learning_history_size': len(self.learning_history),
            'storage_dir': self.storage_dir
        }


# Global instance
_learning_system: Optional[EnhancedLearningSystemSOTA2026] = None


def get_enhanced_learning_system(event_bus=None, ollama_learning=None) -> EnhancedLearningSystemSOTA2026:
    """Get or create global learning system instance."""
    global _learning_system
    if _learning_system is None:
        _learning_system = EnhancedLearningSystemSOTA2026(event_bus, ollama_learning)
    return _learning_system


__all__ = [
    'EnhancedLearningSystemSOTA2026',
    'Fact',
    'VisualConcept',
    'KnowledgeGraph',
    'get_enhanced_learning_system',
]
