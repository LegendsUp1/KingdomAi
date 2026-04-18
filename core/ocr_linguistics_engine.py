#!/usr/bin/env python3
"""
KINGDOM AI - SOTA 2026 OCR & Advanced Linguistics Engine
=========================================================

Comprehensive OCR (Optical Character Recognition) and NLP capabilities:

OCR BACKENDS (priority order):
1. RapidOCR (ONNX-based, fastest, no GPU required)
2. PaddleOCR (PP-OCRv5, highest accuracy for documents)
3. Tesseract (classic, wide language support)
4. Ollama Vision (deepseek-ocr, llava, gemma3 - VLM-based OCR)
5. EasyOCR (GPU-accelerated, 80+ languages)
6. docTR (deep learning, PDF/document focused)

ANCIENT SCRIPTS & PICTOGRAPHY (SOTA 2026):
- Egyptian Hieroglyphs (Glyphnet-style recognition)
- Mesopotamian Cuneiform (wedge-based detection)
- Mayan Hieroglyphs (logographic recognition)
- Chinese Oracle Bone Script (甲骨文)
- Dongba Pictographs (Naxi script)
- Proto-Elamite Scripts
- Runes (Elder/Younger Futhark)
- Phoenician/Proto-Sinaitic
- Linear A/B (Minoan/Mycenaean)
- Indus Valley Script

LINGUISTICS CAPABILITIES:
- Named Entity Recognition (NER)
- Part-of-Speech (POS) Tagging
- Dependency Parsing
- Sentiment Analysis
- Text Classification
- Summarization
- Translation
- Semantic Similarity
- Keyword Extraction
- Language Detection
- Morphological Analysis
- Coreference Resolution

Works in WSL2 with full GPU support when available.
"""

import os
import sys
import json
import base64
import logging
import asyncio
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO

logger = logging.getLogger("KingdomOCRLinguistics")

# Import Kingdom AI base component for Redis Quantum Nexus integration
try:
    from core.base_component_v2 import BaseComponentV2
    BASE_COMPONENT_AVAILABLE = True
except ImportError:
    BASE_COMPONENT_AVAILABLE = False
    logger.debug("BaseComponentV2 not available - running standalone")

# ============================================================================
# OCR BACKEND AVAILABILITY FLAGS
# ============================================================================

RAPIDOCR_AVAILABLE = False
PADDLEOCR_AVAILABLE = False
TESSERACT_AVAILABLE = False
EASYOCR_AVAILABLE = False
DOCTR_AVAILABLE = False
SPACY_AVAILABLE = False
TRANSFORMERS_AVAILABLE = False
NLTK_AVAILABLE = False

# Try imports
try:
    from rapidocr_onnxruntime import RapidOCR
    RAPIDOCR_AVAILABLE = True
    logger.info("✅ RapidOCR available")
except ImportError:
    logger.debug("RapidOCR not installed - pip install rapidocr-onnxruntime")

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
    logger.info("✅ PaddleOCR available")
except ImportError:
    logger.debug("PaddleOCR not installed - pip install paddleocr")

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
    logger.info("✅ Tesseract available")
except ImportError:
    logger.debug("pytesseract not installed - pip install pytesseract")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
    logger.info("✅ EasyOCR available")
except ImportError:
    logger.debug("EasyOCR not installed - pip install easyocr")

try:
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    DOCTR_AVAILABLE = True
    logger.info("✅ docTR available")
except ImportError:
    logger.debug("docTR not installed - pip install python-doctr[torch]")

try:
    import spacy
    SPACY_AVAILABLE = True
    logger.info("✅ spaCy available")
except ImportError:
    logger.debug("spaCy not installed - pip install spacy")

try:
    import transformers
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
    logger.info("✅ Transformers available")
except ImportError:
    logger.debug("transformers not installed - pip install transformers")

try:
    import nltk
    NLTK_AVAILABLE = True
    logger.info("✅ NLTK available")
except ImportError:
    logger.debug("NLTK not installed - pip install nltk")

# PIL for image handling
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL not available - pip install pillow")

# Redis for Quantum Nexus connection
REDIS_AVAILABLE = False
try:
    import redis
    REDIS_AVAILABLE = True
    logger.info("✅ Redis available for Quantum Nexus")
except ImportError:
    logger.debug("Redis not installed - pip install redis")


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class OCRResult:
    """OCR extraction result."""
    text: str
    confidence: float = 0.0
    bounding_boxes: List[Dict[str, Any]] = field(default_factory=list)
    backend: str = "unknown"
    language: str = "en"
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LinguisticsResult:
    """Linguistics analysis result."""
    text: str
    analysis_type: str
    result: Any
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# MAIN OCR & LINGUISTICS ENGINE
# ============================================================================

class OCRLinguisticsEngine:
    """
    SOTA 2026 OCR and Advanced Linguistics Engine.
    
    Provides unified interface for:
    - Multi-backend OCR with automatic fallback
    - Advanced NLP/linguistics analysis
    - Ollama vision model integration
    - Event bus integration for Kingdom AI
    - Redis Quantum Nexus integration (via BaseComponentV2)
    """
    
    # Component name for registration
    COMPONENT_NAME = "ocr_linguistics_engine"
    
    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None):
        """Initialize the OCR & Linguistics Engine.
        
        Args:
            event_bus: Kingdom AI event bus for publishing results
            config: Configuration dictionary
        """
        self.event_bus = event_bus
        self.config = config or {}
        self.initialized = False
        
        # Redis Quantum Nexus - use existing connector
        self.redis = None
        if REDIS_AVAILABLE:
            try:
                from core.redis_connector import RedisQuantumNexusConnector
                self.redis = RedisQuantumNexusConnector()
                logger.info("✅ OCR Engine connected to Redis Quantum Nexus")
            except Exception as e:
                logger.warning(f"Redis Quantum Nexus not available: {e}")
        
        # OCR backends (lazy loaded)
        self._rapidocr = None
        self._paddleocr = None
        self._easyocr = None
        self._doctr = None
        
        # NLP models (lazy loaded)
        self._spacy_model = None
        self._sentiment_pipeline = None
        self._ner_pipeline = None
        self._summarization_pipeline = None
        self._translation_pipelines = {}
        self._zero_shot_pipeline = None
        
        # Ollama config
        self.ollama_url = self.config.get("ollama_url", "http://localhost:11434")
        self.ollama_vision_model = self.config.get("ollama_vision_model", "deepseek-ocr")
        
        # Preferred backends (order of priority)
        self.ocr_priority = self.config.get("ocr_priority", [
            "rapidocr", "paddleocr", "tesseract", "ollama", "easyocr", "doctr"
        ])
        
        logger.info("OCR & Linguistics Engine created")
    
    async def initialize(self) -> bool:
        """Initialize the engine and load models."""
        try:
            logger.info("Initializing OCR & Linguistics Engine...")
            
            # Subscribe to events if event bus available
            if self.event_bus:
                try:
                    await self._subscribe_events()
                except Exception as e:
                    logger.warning(f"Could not subscribe to events: {e}")
            
            # Pre-load preferred OCR backend
            await self._init_primary_ocr()
            
            # Pre-load spaCy if available
            if SPACY_AVAILABLE:
                await self._init_spacy()
            
            self.initialized = True
            logger.info("✅ OCR & Linguistics Engine initialized")
            
            # Publish status
            if self.event_bus:
                await self.event_bus.publish("ocr_linguistics.status", {
                    "status": "initialized",
                    "ocr_backends": self.get_available_backends(),
                    "linguistics_available": SPACY_AVAILABLE or TRANSFORMERS_AVAILABLE,
                    "timestamp": datetime.now().isoformat()
                })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OCR & Linguistics Engine: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _subscribe_events(self):
        """Subscribe to event bus topics."""
        events = [
            ("ocr.extract", self._handle_ocr_extract),
            ("ocr.extract_from_base64", self._handle_ocr_base64),
            ("linguistics.analyze", self._handle_linguistics_analyze),
            ("linguistics.ner", self._handle_ner),
            ("linguistics.sentiment", self._handle_sentiment),
            ("linguistics.summarize", self._handle_summarize),
            ("linguistics.translate", self._handle_translate),
            ("linguistics.classify", self._handle_classify),
        ]
        
        for event, handler in events:
            if hasattr(self.event_bus, 'subscribe'):
                await self.event_bus.subscribe(event, handler)
            elif hasattr(self.event_bus, 'subscribe_sync'):
                self.event_bus.subscribe_sync(event, handler)
    
    async def _init_primary_ocr(self):
        """Initialize primary OCR backend."""
        for backend in self.ocr_priority:
            if backend == "rapidocr" and RAPIDOCR_AVAILABLE:
                self._rapidocr = RapidOCR()
                logger.info("Primary OCR: RapidOCR")
                return
            elif backend == "paddleocr" and PADDLEOCR_AVAILABLE:
                self._paddleocr = PaddleOCR(
                    use_angle_cls=True,
                    lang='en',
                    use_gpu=False,  # WSL2 compatible
                    show_log=False
                )
                logger.info("Primary OCR: PaddleOCR")
                return
        
        logger.warning("No primary OCR backend available - will use Ollama vision fallback")
    
    async def _init_spacy(self):
        """Initialize spaCy model."""
        try:
            # Try to load English model
            models_to_try = ["en_core_web_trf", "en_core_web_lg", "en_core_web_md", "en_core_web_sm"]
            
            for model_name in models_to_try:
                try:
                    self._spacy_model = spacy.load(model_name)
                    logger.info(f"Loaded spaCy model: {model_name}")
                    return
                except OSError:
                    continue
            
            # Download small model if none available
            logger.info("Downloading spaCy en_core_web_sm model...")
            import subprocess
            subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], 
                         capture_output=True)
            self._spacy_model = spacy.load("en_core_web_sm")
            logger.info("Downloaded and loaded spaCy en_core_web_sm")
            
        except Exception as e:
            logger.warning(f"Could not initialize spaCy: {e}")
    
    def get_available_backends(self) -> List[str]:
        """Get list of available OCR backends."""
        backends = []
        if RAPIDOCR_AVAILABLE:
            backends.append("rapidocr")
        if PADDLEOCR_AVAILABLE:
            backends.append("paddleocr")
        if TESSERACT_AVAILABLE:
            backends.append("tesseract")
        if EASYOCR_AVAILABLE:
            backends.append("easyocr")
        if DOCTR_AVAILABLE:
            backends.append("doctr")
        backends.append("ollama")  # Always available if Ollama running
        return backends
    
    # ========================================================================
    # OCR METHODS
    # ========================================================================
    
    async def extract_text(
        self,
        image: Union[str, bytes, "Image.Image"],
        backend: Optional[str] = None,
        language: str = "en",
        return_boxes: bool = False
    ) -> OCRResult:
        """
        Extract text from image using OCR.
        
        Args:
            image: Image path, bytes, or PIL Image
            backend: Specific backend to use (None = auto-select)
            language: Language code for OCR
            return_boxes: Whether to return bounding boxes
            
        Returns:
            OCRResult with extracted text and metadata
        """
        import time
        start_time = time.time()
        
        # Convert to PIL Image if needed
        pil_image = await self._to_pil_image(image)
        if pil_image is None:
            return OCRResult(text="", confidence=0.0, backend="error", 
                           metadata={"error": "Could not load image"})
        
        # Select backend
        if backend:
            backends_to_try = [backend]
        else:
            backends_to_try = self.ocr_priority
        
        # Try backends in order
        for backend_name in backends_to_try:
            try:
                result = await self._run_ocr_backend(pil_image, backend_name, language, return_boxes)
                if result and result.text.strip():
                    result.processing_time_ms = (time.time() - start_time) * 1000
                    return result
            except Exception as e:
                logger.warning(f"OCR backend {backend_name} failed: {e}")
                continue
        
        # All backends failed
        return OCRResult(
            text="",
            confidence=0.0,
            backend="none",
            processing_time_ms=(time.time() - start_time) * 1000,
            metadata={"error": "All OCR backends failed"}
        )
    
    async def _run_ocr_backend(
        self,
        image: "Image.Image",
        backend: str,
        language: str,
        return_boxes: bool
    ) -> Optional[OCRResult]:
        """Run OCR using specific backend."""
        
        if backend == "rapidocr" and RAPIDOCR_AVAILABLE:
            return await self._ocr_rapidocr(image, return_boxes)
        
        elif backend == "paddleocr" and PADDLEOCR_AVAILABLE:
            return await self._ocr_paddleocr(image, language, return_boxes)
        
        elif backend == "tesseract" and TESSERACT_AVAILABLE:
            return await self._ocr_tesseract(image, language, return_boxes)
        
        elif backend == "easyocr" and EASYOCR_AVAILABLE:
            return await self._ocr_easyocr(image, language, return_boxes)
        
        elif backend == "doctr" and DOCTR_AVAILABLE:
            return await self._ocr_doctr(image, return_boxes)
        
        elif backend == "ollama":
            return await self._ocr_ollama_vision(image)
        
        return None
    
    async def _ocr_rapidocr(self, image: "Image.Image", return_boxes: bool) -> OCRResult:
        """RapidOCR extraction."""
        import numpy as np
        
        if self._rapidocr is None:
            self._rapidocr = RapidOCR()
        
        # Convert to numpy array
        img_array = np.array(image)
        
        # Run OCR
        result, elapse = self._rapidocr(img_array)
        
        if result is None:
            return OCRResult(text="", confidence=0.0, backend="rapidocr")
        
        # Parse results
        texts = []
        boxes = []
        confidences = []
        
        for item in result:
            box, text, conf = item
            texts.append(text)
            confidences.append(conf)
            if return_boxes:
                boxes.append({"box": box, "text": text, "confidence": conf})
        
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        return OCRResult(
            text="\n".join(texts),
            confidence=avg_conf,
            bounding_boxes=boxes if return_boxes else [],
            backend="rapidocr",
            metadata={"elapse": elapse}
        )
    
    async def _ocr_paddleocr(self, image: "Image.Image", language: str, return_boxes: bool) -> OCRResult:
        """PaddleOCR extraction."""
        import numpy as np
        
        if self._paddleocr is None:
            self._paddleocr = PaddleOCR(
                use_angle_cls=True,
                lang=language[:2] if len(language) > 2 else language,
                use_gpu=False,
                show_log=False
            )
        
        img_array = np.array(image)
        result = self._paddleocr.ocr(img_array, cls=True)
        
        if result is None or len(result) == 0:
            return OCRResult(text="", confidence=0.0, backend="paddleocr")
        
        texts = []
        boxes = []
        confidences = []
        
        for line in result:
            if line:
                for item in line:
                    box, (text, conf) = item
                    texts.append(text)
                    confidences.append(conf)
                    if return_boxes:
                        boxes.append({"box": box, "text": text, "confidence": conf})
        
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        return OCRResult(
            text="\n".join(texts),
            confidence=avg_conf,
            bounding_boxes=boxes if return_boxes else [],
            backend="paddleocr",
            language=language
        )
    
    async def _ocr_tesseract(self, image: "Image.Image", language: str, return_boxes: bool) -> OCRResult:
        """Tesseract OCR extraction."""
        # Map common language codes
        lang_map = {"en": "eng", "zh": "chi_sim", "ja": "jpn", "ko": "kor", "de": "deu", "fr": "fra"}
        tess_lang = lang_map.get(language, language)
        
        # Get text
        text = pytesseract.image_to_string(image, lang=tess_lang)
        
        # Get confidence and boxes if requested
        boxes = []
        confidences = []
        
        if return_boxes:
            data = pytesseract.image_to_data(image, lang=tess_lang, output_type=pytesseract.Output.DICT)
            
            for i, word in enumerate(data['text']):
                if word.strip():
                    conf = float(data['conf'][i]) / 100.0 if data['conf'][i] != -1 else 0.0
                    confidences.append(conf)
                    boxes.append({
                        "box": [data['left'][i], data['top'][i], 
                               data['left'][i] + data['width'][i],
                               data['top'][i] + data['height'][i]],
                        "text": word,
                        "confidence": conf
                    })
        
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.8  # Default confidence
        
        return OCRResult(
            text=text.strip(),
            confidence=avg_conf,
            bounding_boxes=boxes,
            backend="tesseract",
            language=language
        )
    
    async def _ocr_easyocr(self, image: "Image.Image", language: str, return_boxes: bool) -> OCRResult:
        """EasyOCR extraction."""
        import numpy as np
        
        if self._easyocr is None:
            # Map language codes
            lang_list = [language] if language != "en" else ["en"]
            self._easyocr = easyocr.Reader(lang_list, gpu=False)  # WSL2 compatible
        
        img_array = np.array(image)
        result = self._easyocr.readtext(img_array)
        
        texts = []
        boxes = []
        confidences = []
        
        for item in result:
            box, text, conf = item
            texts.append(text)
            confidences.append(conf)
            if return_boxes:
                boxes.append({"box": box, "text": text, "confidence": conf})
        
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        return OCRResult(
            text="\n".join(texts),
            confidence=avg_conf,
            bounding_boxes=boxes if return_boxes else [],
            backend="easyocr",
            language=language
        )
    
    async def _ocr_doctr(self, image: "Image.Image", return_boxes: bool) -> OCRResult:
        """docTR extraction."""
        if self._doctr is None:
            self._doctr = ocr_predictor(pretrained=True)
        
        # Save image temporarily
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image.save(tmp.name)
            doc = DocumentFile.from_images(tmp.name)
        
        result = self._doctr(doc)
        
        # Extract text
        texts = []
        boxes = []
        
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    line_text = " ".join([word.value for word in line.words])
                    texts.append(line_text)
                    
                    if return_boxes:
                        for word in line.words:
                            boxes.append({
                                "box": word.geometry,
                                "text": word.value,
                                "confidence": word.confidence
                            })
        
        # Cleanup temp file
        try:
            os.unlink(tmp.name)
        except:
            pass
        
        return OCRResult(
            text="\n".join(texts),
            confidence=0.9,  # docTR doesn't provide overall confidence
            bounding_boxes=boxes if return_boxes else [],
            backend="doctr"
        )
    
    async def _ocr_ollama_vision(self, image: "Image.Image") -> OCRResult:
        """Ollama Vision model OCR (deepseek-ocr, llava, gemma3)."""
        try:
            import aiohttp
            
            # Convert image to base64
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Try vision models in order
            try:
                from core.ollama_gateway import orchestrator
                _ocr_model = orchestrator.get_model_for_task("ocr")
            except ImportError:
                _ocr_model = "deepseek-ocr:latest"

            ocr_prompt = "Extract all text from this image. Output only the extracted text."
            
            async with aiohttp.ClientSession() as session:
                try:
                    payload = {
                        "model": _ocr_model,
                        "messages": [{
                            "role": "user",
                            "content": ocr_prompt,
                            "images": [img_base64]
                        }],
                        "stream": False,
                        "keep_alive": -1,
                        "options": {"num_gpu": 999},
                    }
                    
                    async with session.post(
                        f"{self.ollama_url}/api/chat",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=None, sock_read=300)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            text = data.get("message", {}).get("content", "")
                            
                            if text.strip():
                                return OCRResult(
                                    text=text.strip(),
                                    confidence=0.85,
                                    backend=f"ollama:{_ocr_model}",
                                    metadata={"model": _ocr_model}
                                )
                except Exception as e:
                    logger.debug(f"Ollama OCR model {_ocr_model} failed: {e}")
            
            return OCRResult(text="", confidence=0.0, backend="ollama", 
                           metadata={"error": "No Ollama vision model available"})
            
        except Exception as e:
            logger.error(f"Ollama vision OCR failed: {e}")
            return OCRResult(text="", confidence=0.0, backend="ollama",
                           metadata={"error": str(e)})
    
    # ========================================================================
    # SOTA 2026 ANCIENT SCRIPTS & PICTOGRAPHY RECOGNITION
    # ========================================================================
    
    async def recognize_ancient_script(
        self,
        image: Union[str, bytes, "Image.Image"],
        script_type: str = "auto",
        return_analysis: bool = True
    ) -> OCRResult:
        """
        Recognize and interpret ancient scripts and pictography.
        
        SOTA 2026 - Uses VLM (Vision Language Models) for:
        - Egyptian Hieroglyphs
        - Mesopotamian Cuneiform
        - Mayan Hieroglyphs
        - Chinese Oracle Bone Script
        - Dongba Pictographs
        - Runes (Elder/Younger Futhark)
        - Linear A/B
        - Proto-Sinaitic/Phoenician
        - Indus Valley Script
        - Generic Pictographs
        
        Args:
            image: Image containing ancient script
            script_type: Type of script ("auto", "hieroglyph", "cuneiform", "maya",
                        "oracle_bone", "dongba", "runes", "linear_a", "linear_b",
                        "phoenician", "indus", "pictograph")
            return_analysis: Whether to include interpretation/translation
            
        Returns:
            OCRResult with recognized symbols and interpretation
        """
        import time
        start_time = time.time()
        
        pil_image = await self._to_pil_image(image)
        if pil_image is None:
            return OCRResult(text="", confidence=0.0, backend="error",
                           metadata={"error": "Could not load image"})
        
        # Build specialized prompt based on script type
        prompt = self._build_ancient_script_prompt(script_type, return_analysis)
        
        # Use Ollama vision for recognition
        result = await self._query_ollama_ancient_script(pil_image, prompt, script_type)
        result.processing_time_ms = (time.time() - start_time) * 1000
        
        return result
    
    def _build_ancient_script_prompt(self, script_type: str, return_analysis: bool) -> str:
        """Build specialized prompt for ancient script recognition."""
        
        prompts = {
            "auto": """Analyze this image for any ancient writing system or pictographic script.
Identify the script type (hieroglyphs, cuneiform, runes, pictographs, etc.).
List each symbol/glyph you can identify.
If possible, provide the phonetic value or meaning of recognized symbols.
Format: [Symbol description] - [Phonetic/Meaning if known]""",
            
            "hieroglyph": """This image contains Egyptian hieroglyphs.
Identify and catalog each hieroglyphic symbol using the Gardiner Sign List classification where possible.
For each glyph provide:
1. Visual description
2. Gardiner code (if identifiable, e.g., A1, G17, N35)
3. Phonetic value (uniliteral, biliteral, or triliteral)
4. Logographic meaning if applicable
5. Reading direction indicators

List symbols in reading order (typically right-to-left, top-to-bottom).""",
            
            "cuneiform": """This image contains Mesopotamian cuneiform script.
Analyze the wedge-shaped impressions and identify:
1. Individual cuneiform signs
2. Sign type (logogram, syllabogram, determinative)
3. Transliteration in standard Assyriological notation
4. Approximate period/style (Sumerian, Akkadian, Old Persian, etc.)
5. Any recognizable words or phrases

Note the wedge orientations: horizontal, vertical, diagonal, and Winkelhaken.""",
            
            "maya": """This image contains Mayan hieroglyphic script.
Identify the glyphs and provide:
1. Glyph block analysis (main sign + affixes)
2. Thompson (T-number) classification if identifiable
3. Phonetic reading (syllabic values)
4. Logographic meanings
5. Potential historical or calendrical significance

Note: Mayan glyphs are read in paired columns, left-to-right, top-to-bottom.""",
            
            "oracle_bone": """This image contains Chinese Oracle Bone Script (甲骨文).
Identify the archaic Chinese characters and provide:
1. Oracle bone form description
2. Modern Chinese character equivalent (if evolved)
3. Pinyin pronunciation
4. Original divinatory meaning
5. Pictographic origin explanation""",
            
            "dongba": """This image contains Dongba pictographic script (Naxi).
This is the only living pictographic writing system. Identify:
1. Each pictograph's visual elements
2. The object or concept depicted
3. Phonetic reading in Naxi language
4. Semantic meaning
5. Any compound symbols""",
            
            "runes": """This image contains runic script.
Identify the runes and provide:
1. Rune name (Proto-Germanic or Old Norse)
2. Phonetic value
3. Elder Futhark / Younger Futhark / Anglo-Saxon classification
4. Associated meaning or symbolism
5. Transcription into Latin alphabet

Reading direction (left-to-right or boustrophedon if applicable).""",
            
            "linear_a": """This image contains Linear A script (Minoan).
Note: Linear A is undeciphered. Provide:
1. Sign identification using standard Linear A notation
2. Comparison to similar Linear B signs if applicable
3. Frequency/context analysis
4. Any numerical notations
5. Structural analysis of the inscription""",
            
            "linear_b": """This image contains Linear B script (Mycenaean Greek).
Identify the syllabic signs and provide:
1. Sign number (standard Linear B notation)
2. Phonetic value (syllable)
3. Word boundaries
4. Transcription into Greek
5. Translation if text is complete""",
            
            "phoenician": """This image contains Phoenician or Proto-Sinaitic script.
Identify the consonantal alphabet signs:
1. Letter name (Aleph, Beth, Gimel, etc.)
2. Phonetic value
3. Pictographic origin
4. Direction of writing
5. Any connections to later alphabets (Greek, Hebrew, Arabic)""",
            
            "indus": """This image contains Indus Valley Script (Harappan).
Note: This script is undeciphered. Provide:
1. Sign identification using Mahadevan concordance numbers
2. Visual description of each symbol
3. Frequency analysis
4. Directional analysis (likely right-to-left)
5. Any repeated sequences or patterns""",
            
            "pictograph": """This image contains pictographic writing or symbols.
Analyze the pictographs and provide:
1. Visual description of each symbol
2. Likely real-world referent (what it depicts)
3. Potential meaning or concept
4. Cultural/historical context if identifiable
5. Any patterns or sequences"""
        }
        
        base_prompt = prompts.get(script_type, prompts["auto"])
        
        if return_analysis:
            base_prompt += "\n\nAlso provide an overall interpretation or translation if possible."
        
        return base_prompt
    
    async def _query_ollama_ancient_script(
        self, 
        image: "Image.Image", 
        prompt: str,
        script_type: str
    ) -> OCRResult:
        """Query Ollama vision model for ancient script recognition."""
        try:
            import aiohttp
            
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            try:
                from core.ollama_gateway import orchestrator
                _vision_model = orchestrator.get_model_for_task("vision")
            except ImportError:
                _vision_model = "llava:latest"
            
            async with aiohttp.ClientSession() as session:
                try:
                    payload = {
                        "model": _vision_model,
                        "messages": [{
                            "role": "user",
                            "content": prompt,
                            "images": [img_base64]
                        }],
                        "stream": False,
                        "keep_alive": -1,
                        "options": {"num_gpu": 999},
                    }
                    
                    async with session.post(
                        f"{self.ollama_url}/api/chat",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=None, sock_read=300)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            text = data.get("message", {}).get("content", "")
                            
                            if text.strip():
                                return OCRResult(
                                    text=text.strip(),
                                    confidence=0.75,
                                    backend=f"ollama:{_vision_model}",
                                    metadata={
                                        "model": _vision_model,
                                        "script_type": script_type,
                                        "analysis_type": "ancient_script"
                                    }
                                )
                except Exception as e:
                    logger.debug(f"Ollama vision model {_vision_model} failed for ancient script: {e}")
            
            return OCRResult(
                text="",
                confidence=0.0,
                backend="ollama",
                metadata={"error": "No Ollama vision model available for ancient script recognition"}
            )
            
        except Exception as e:
            logger.error(f"Ancient script recognition failed: {e}")
            return OCRResult(text="", confidence=0.0, backend="error",
                           metadata={"error": str(e)})
    
    async def recognize_hieroglyphs(self, image: Union[str, bytes, "Image.Image"]) -> OCRResult:
        """Specialized Egyptian hieroglyph recognition."""
        return await self.recognize_ancient_script(image, script_type="hieroglyph")
    
    async def recognize_cuneiform(self, image: Union[str, bytes, "Image.Image"]) -> OCRResult:
        """Specialized Mesopotamian cuneiform recognition."""
        return await self.recognize_ancient_script(image, script_type="cuneiform")
    
    async def recognize_mayan(self, image: Union[str, bytes, "Image.Image"]) -> OCRResult:
        """Specialized Mayan hieroglyph recognition."""
        return await self.recognize_ancient_script(image, script_type="maya")
    
    async def recognize_pictographs(self, image: Union[str, bytes, "Image.Image"]) -> OCRResult:
        """General pictograph and symbol recognition."""
        return await self.recognize_ancient_script(image, script_type="pictograph")
    
    async def recognize_runes(self, image: Union[str, bytes, "Image.Image"]) -> OCRResult:
        """Runic script recognition (Elder/Younger Futhark)."""
        return await self.recognize_ancient_script(image, script_type="runes")
    
    async def recognize_oracle_bone(self, image: Union[str, bytes, "Image.Image"]) -> OCRResult:
        """Chinese Oracle Bone Script (甲骨文) recognition."""
        return await self.recognize_ancient_script(image, script_type="oracle_bone")
    
    async def _to_pil_image(self, image: Union[str, bytes, "Image.Image"]) -> Optional["Image.Image"]:
        """Convert various image formats to PIL Image."""
        if not PIL_AVAILABLE:
            logger.error("PIL not available")
            return None
        
        try:
            if isinstance(image, Image.Image):
                return image
            elif isinstance(image, bytes):
                return Image.open(BytesIO(image))
            elif isinstance(image, str):
                # Check if base64
                if image.startswith("data:image"):
                    # Data URL
                    header, data = image.split(",", 1)
                    return Image.open(BytesIO(base64.b64decode(data)))
                elif len(image) > 500 and not os.path.exists(image):
                    # Likely base64 without header
                    return Image.open(BytesIO(base64.b64decode(image)))
                else:
                    # File path
                    return Image.open(image)
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
        
        return None
    
    # ========================================================================
    # LINGUISTICS METHODS
    # ========================================================================
    
    async def analyze_text(
        self,
        text: str,
        analyses: Optional[List[str]] = None
    ) -> Dict[str, LinguisticsResult]:
        """
        Perform comprehensive linguistic analysis.
        
        Args:
            text: Text to analyze
            analyses: List of analyses to perform. Options:
                - ner: Named Entity Recognition
                - pos: Part-of-Speech tagging
                - sentiment: Sentiment analysis
                - summary: Text summarization
                - keywords: Keyword extraction
                - language: Language detection
                - dependencies: Dependency parsing
                
        Returns:
            Dictionary of analysis results
        """
        if analyses is None:
            analyses = ["ner", "pos", "sentiment", "keywords", "language"]
        
        results = {}
        
        for analysis in analyses:
            try:
                if analysis == "ner":
                    results["ner"] = await self.extract_entities(text)
                elif analysis == "pos":
                    results["pos"] = await self.pos_tagging(text)
                elif analysis == "sentiment":
                    results["sentiment"] = await self.analyze_sentiment(text)
                elif analysis == "summary":
                    results["summary"] = await self.summarize(text)
                elif analysis == "keywords":
                    results["keywords"] = await self.extract_keywords(text)
                elif analysis == "language":
                    results["language"] = await self.detect_language(text)
                elif analysis == "dependencies":
                    results["dependencies"] = await self.parse_dependencies(text)
            except Exception as e:
                logger.warning(f"Analysis {analysis} failed: {e}")
                results[analysis] = LinguisticsResult(
                    text=text,
                    analysis_type=analysis,
                    result=None,
                    metadata={"error": str(e)}
                )
        
        return results
    
    async def extract_entities(self, text: str) -> LinguisticsResult:
        """Extract named entities from text."""
        import time
        start = time.time()
        
        entities = []
        
        # Try spaCy first
        if SPACY_AVAILABLE and self._spacy_model:
            doc = self._spacy_model(text)
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "description": spacy.explain(ent.label_) or ent.label_
                })
        
        # Fallback to transformers NER
        elif TRANSFORMERS_AVAILABLE:
            if self._ner_pipeline is None:
                self._ner_pipeline = pipeline("ner", aggregation_strategy="simple")  # type: ignore
            
            results = self._ner_pipeline(text)
            for item in results:
                entities.append({
                    "text": item["word"],
                    "label": item["entity_group"],
                    "start": item["start"],
                    "end": item["end"],
                    "score": item["score"]
                })
        
        return LinguisticsResult(
            text=text,
            analysis_type="ner",
            result=entities,
            confidence=0.9 if entities else 0.0,
            processing_time_ms=(time.time() - start) * 1000
        )
    
    async def pos_tagging(self, text: str) -> LinguisticsResult:
        """Part-of-speech tagging."""
        import time
        start = time.time()
        
        tags = []
        
        if SPACY_AVAILABLE and self._spacy_model:
            doc = self._spacy_model(text)
            for token in doc:
                tags.append({
                    "text": token.text,
                    "pos": token.pos_,
                    "tag": token.tag_,
                    "description": spacy.explain(token.tag_) or token.tag_,
                    "lemma": token.lemma_
                })
        
        elif NLTK_AVAILABLE:
            from nltk import word_tokenize, pos_tag
            tokens = word_tokenize(text)
            nltk_tags = pos_tag(tokens)
            for word, tag in nltk_tags:
                tags.append({"text": word, "pos": tag})
        
        return LinguisticsResult(
            text=text,
            analysis_type="pos",
            result=tags,
            confidence=0.95,
            processing_time_ms=(time.time() - start) * 1000
        )
    
    async def analyze_sentiment(self, text: str) -> LinguisticsResult:
        """Analyze sentiment of text."""
        import time
        start = time.time()
        
        result = {"label": "neutral", "score": 0.5, "details": {}}
        
        # Try transformers sentiment pipeline
        if TRANSFORMERS_AVAILABLE:
            try:
                if self._sentiment_pipeline is None:
                    self._sentiment_pipeline = pipeline(
                        "sentiment-analysis",  # type: ignore[arg-type]
                        model="distilbert-base-uncased-finetuned-sst-2-english"
                    )
                
                output = self._sentiment_pipeline(text[:512])[0]  # Truncate for model
                result = {
                    "label": output["label"].lower(),
                    "score": output["score"],
                    "details": {"model": "distilbert-sst2"}
                }
            except Exception as e:
                logger.warning(f"Transformers sentiment failed: {e}")
        
        # Fallback: simple lexicon-based
        if result["label"] == "neutral" and NLTK_AVAILABLE:
            try:
                from nltk.sentiment import SentimentIntensityAnalyzer
                nltk.download('vader_lexicon', quiet=True)
                sia = SentimentIntensityAnalyzer()
                scores = sia.polarity_scores(text)
                
                if scores["compound"] >= 0.05:
                    result = {"label": "positive", "score": scores["compound"], "details": scores}
                elif scores["compound"] <= -0.05:
                    result = {"label": "negative", "score": abs(scores["compound"]), "details": scores}
                else:
                    result = {"label": "neutral", "score": 0.5, "details": scores}
            except:
                pass
        
        return LinguisticsResult(
            text=text,
            analysis_type="sentiment",
            result=result,
            confidence=result["score"],
            processing_time_ms=(time.time() - start) * 1000
        )
    
    async def summarize(self, text: str, max_length: int = 150, min_length: int = 30) -> LinguisticsResult:
        """Summarize text."""
        import time
        start = time.time()
        
        summary = ""
        
        if TRANSFORMERS_AVAILABLE and len(text) > 100:
            try:
                if self._summarization_pipeline is None:
                    self._summarization_pipeline = pipeline(
                        "summarization",
                        model="facebook/bart-large-cnn"
                    )
                
                output = self._summarization_pipeline(
                    text[:1024],  # Truncate
                    max_length=max_length,
                    min_length=min_length,
                    do_sample=False
                )
                summary = output[0]["summary_text"]
            except Exception as e:
                logger.warning(f"Summarization failed: {e}")
        
        # Fallback: extractive summary using spaCy
        if not summary and SPACY_AVAILABLE and self._spacy_model:
            doc = self._spacy_model(text)
            sentences = list(doc.sents)
            if len(sentences) > 3:
                # Take first and most important sentences
                summary = " ".join([str(s) for s in sentences[:3]])
            else:
                summary = text
        
        if not summary:
            summary = text[:max_length] + "..." if len(text) > max_length else text
        
        return LinguisticsResult(
            text=text,
            analysis_type="summary",
            result=summary,
            confidence=0.8,
            processing_time_ms=(time.time() - start) * 1000
        )
    
    async def translate(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> LinguisticsResult:
        """Translate text."""
        import time
        start = time.time()
        
        translated = text  # Default: return original
        
        if TRANSFORMERS_AVAILABLE:
            try:
                # Use appropriate translation model
                model_name = f"Helsinki-NLP/opus-mt-{source_lang}-{target_lang}"
                
                if model_name not in self._translation_pipelines:
                    self._translation_pipelines[model_name] = pipeline(
                        "translation",
                        model=model_name
                    )
                
                output = self._translation_pipelines[model_name](text[:512])
                translated = output[0]["translation_text"]
            except Exception as e:
                logger.warning(f"Translation failed: {e}")
        
        return LinguisticsResult(
            text=text,
            analysis_type="translation",
            result={"original": text, "translated": translated, "source": source_lang, "target": target_lang},
            confidence=0.85,
            processing_time_ms=(time.time() - start) * 1000
        )
    
    async def extract_keywords(self, text: str, top_k: int = 10) -> LinguisticsResult:
        """Extract keywords from text."""
        import time
        start = time.time()
        
        keywords = []
        
        if SPACY_AVAILABLE and self._spacy_model:
            doc = self._spacy_model(text)
            
            # Get noun chunks and named entities as keywords
            seen = set()
            
            for chunk in doc.noun_chunks:
                if chunk.text.lower() not in seen:
                    keywords.append({"text": chunk.text, "type": "noun_chunk"})
                    seen.add(chunk.text.lower())
            
            for ent in doc.ents:
                if ent.text.lower() not in seen:
                    keywords.append({"text": ent.text, "type": "entity", "label": ent.label_})
                    seen.add(ent.text.lower())
            
            keywords = keywords[:top_k]
        
        elif NLTK_AVAILABLE:
            from nltk import word_tokenize, pos_tag
            from nltk.corpus import stopwords
            
            try:
                nltk.download('stopwords', quiet=True)
                nltk.download('punkt', quiet=True)
                nltk.download('averaged_perceptron_tagger', quiet=True)
                
                stop_words = set(stopwords.words('english'))
                tokens = word_tokenize(text.lower())
                tags = pos_tag(tokens)
                
                # Extract nouns and proper nouns
                for word, tag in tags:
                    if tag.startswith(('NN', 'NNP')) and word not in stop_words and len(word) > 2:
                        keywords.append({"text": word, "type": tag})
                
                keywords = keywords[:top_k]
            except:
                pass
        
        return LinguisticsResult(
            text=text,
            analysis_type="keywords",
            result=keywords,
            confidence=0.8,
            processing_time_ms=(time.time() - start) * 1000
        )
    
    async def detect_language(self, text: str) -> LinguisticsResult:
        """Detect language of text."""
        import time
        start = time.time()
        
        detected = {"language": "en", "confidence": 0.5}
        
        # Try langdetect
        try:
            from langdetect import detect, detect_langs
            lang = detect(text)
            probs = detect_langs(text)
            detected = {
                "language": lang,
                "confidence": probs[0].prob if probs else 0.8,
                "alternatives": [{"lang": p.lang, "prob": p.prob} for p in probs[:3]]
            }
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Language detection failed: {e}")
        
        return LinguisticsResult(
            text=text,
            analysis_type="language",
            result=detected,
            confidence=detected["confidence"],
            processing_time_ms=(time.time() - start) * 1000
        )
    
    async def parse_dependencies(self, text: str) -> LinguisticsResult:
        """Parse syntactic dependencies."""
        import time
        start = time.time()
        
        dependencies = []
        
        if SPACY_AVAILABLE and self._spacy_model:
            doc = self._spacy_model(text)
            
            for token in doc:
                dependencies.append({
                    "text": token.text,
                    "dep": token.dep_,
                    "head": token.head.text,
                    "children": [child.text for child in token.children]
                })
        
        return LinguisticsResult(
            text=text,
            analysis_type="dependencies",
            result=dependencies,
            confidence=0.95,
            processing_time_ms=(time.time() - start) * 1000
        )
    
    async def classify_text(self, text: str, labels: List[str]) -> LinguisticsResult:
        """Zero-shot text classification."""
        import time
        start = time.time()
        
        result = {"labels": labels, "scores": [1.0/len(labels)] * len(labels)}
        
        if TRANSFORMERS_AVAILABLE:
            try:
                if self._zero_shot_pipeline is None:
                    self._zero_shot_pipeline = pipeline(
                        "zero-shot-classification",
                        model="facebook/bart-large-mnli"
                    )
                
                output = self._zero_shot_pipeline(text[:512], labels)  # type: ignore
                # Extract results from pipeline output
                labels_out = output.get("labels", []) if isinstance(output, dict) else []  # type: ignore
                scores_out = output.get("scores", []) if isinstance(output, dict) else []  # type: ignore
                result = {
                    "labels": labels_out,
                    "scores": scores_out,
                    "best_label": labels_out[0] if labels_out else "",
                    "best_score": scores_out[0] if scores_out else 0.0
                }
            except Exception as e:
                logger.warning(f"Zero-shot classification failed: {e}")
        
        return LinguisticsResult(
            text=text,
            analysis_type="classification",
            result=result,
            confidence=result.get("best_score", 0.5),
            processing_time_ms=(time.time() - start) * 1000
        )
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    async def _handle_ocr_extract(self, data: Dict[str, Any]):
        """Handle OCR extraction request."""
        image_path = data.get("image_path") or data.get("path")
        if not image_path:
            logger.warning("OCR extract request missing image_path")
            return
        backend = data.get("backend")
        language = data.get("language", "en")
        
        result = await self.extract_text(image_path, backend=backend, language=language, return_boxes=True)
        
        if self.event_bus:
            await self.event_bus.publish("ocr.result", {
                "text": result.text,
                "confidence": result.confidence,
                "backend": result.backend,
                "boxes": result.bounding_boxes,
                "request_id": data.get("request_id")
            })
    
    async def _handle_ocr_base64(self, data: Dict[str, Any]):
        """Handle OCR from base64 image."""
        image_data = data.get("image") or data.get("base64")
        if not image_data:
            logger.warning("OCR base64 request missing image data")
            return
        
        result = await self.extract_text(image_data, return_boxes=data.get("return_boxes", False))
        
        if self.event_bus:
            await self.event_bus.publish("ocr.result", {
                "text": result.text,
                "confidence": result.confidence,
                "backend": result.backend,
                "request_id": data.get("request_id")
            })
    
    async def _handle_linguistics_analyze(self, data: Dict[str, Any]):
        """Handle comprehensive linguistics analysis."""
        text = data.get("text", "")
        analyses = data.get("analyses")
        
        results = await self.analyze_text(text, analyses)
        
        if self.event_bus:
            await self.event_bus.publish("linguistics.result", {
                "results": {k: {"result": v.result, "confidence": v.confidence} for k, v in results.items()},
                "request_id": data.get("request_id")
            })
    
    async def _handle_ner(self, data: Dict[str, Any]):
        """Handle NER request."""
        result = await self.extract_entities(data.get("text", ""))
        
        if self.event_bus:
            await self.event_bus.publish("linguistics.ner.result", {
                "entities": result.result,
                "request_id": data.get("request_id")
            })
    
    async def _handle_sentiment(self, data: Dict[str, Any]):
        """Handle sentiment analysis request."""
        result = await self.analyze_sentiment(data.get("text", ""))
        
        if self.event_bus:
            await self.event_bus.publish("linguistics.sentiment.result", {
                "sentiment": result.result,
                "request_id": data.get("request_id")
            })
    
    async def _handle_summarize(self, data: Dict[str, Any]):
        """Handle summarization request."""
        result = await self.summarize(
            data.get("text", ""),
            max_length=data.get("max_length", 150),
            min_length=data.get("min_length", 30)
        )
        
        if self.event_bus:
            await self.event_bus.publish("linguistics.summary.result", {
                "summary": result.result,
                "request_id": data.get("request_id")
            })
    
    async def _handle_translate(self, data: Dict[str, Any]):
        """Handle translation request."""
        result = await self.translate(
            data.get("text", ""),
            source_lang=data.get("source", "auto"),
            target_lang=data.get("target", "en")
        )
        
        if self.event_bus:
            await self.event_bus.publish("linguistics.translation.result", {
                "translation": result.result,
                "request_id": data.get("request_id")
            })
    
    async def _handle_classify(self, data: Dict[str, Any]):
        """Handle classification request."""
        result = await self.classify_text(
            data.get("text", ""),
            labels=data.get("labels", [])
        )
        
        if self.event_bus:
            await self.event_bus.publish("linguistics.classification.result", {
                "classification": result.result,
                "request_id": data.get("request_id")
            })


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_engine_instance: Optional[OCRLinguisticsEngine] = None


def get_ocr_linguistics_engine(event_bus=None) -> OCRLinguisticsEngine:
    """Get or create the OCR & Linguistics engine singleton."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OCRLinguisticsEngine(event_bus=event_bus)
    return _engine_instance


async def extract_text_from_image(image: Union[str, bytes], backend: str = None) -> str:
    """Quick function to extract text from image."""
    engine = get_ocr_linguistics_engine()
    if not engine.initialized:
        await engine.initialize()
    result = await engine.extract_text(image, backend=backend)
    return result.text


async def analyze_text(text: str) -> Dict[str, Any]:
    """Quick function to analyze text."""
    engine = get_ocr_linguistics_engine()
    if not engine.initialized:
        await engine.initialize()
    results = await engine.analyze_text(text)
    return {k: v.result for k, v in results.items()}


# ============================================================================
# CLI / TESTING
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    parser = argparse.ArgumentParser(description="Kingdom AI OCR & Linguistics Engine")
    parser.add_argument("--ocr", type=str, help="Image path for OCR")
    parser.add_argument("--analyze", type=str, help="Text to analyze")
    parser.add_argument("--backend", type=str, help="OCR backend to use")
    
    args = parser.parse_args()
    
    async def main():
        engine = OCRLinguisticsEngine()
        await engine.initialize()
        
        print(f"\n📚 Available OCR backends: {engine.get_available_backends()}")
        print(f"📖 spaCy available: {SPACY_AVAILABLE}")
        print(f"🤖 Transformers available: {TRANSFORMERS_AVAILABLE}")
        
        if args.ocr:
            print(f"\n🔍 Running OCR on: {args.ocr}")
            result = await engine.extract_text(args.ocr, backend=args.backend, return_boxes=True)
            print(f"Backend: {result.backend}")
            print(f"Confidence: {result.confidence:.2f}")
            print(f"Text:\n{result.text}")
        
        if args.analyze:
            print(f"\n📝 Analyzing text: {args.analyze[:50]}...")
            results = await engine.analyze_text(args.analyze)
            for name, result in results.items():
                print(f"\n{name.upper()}:")
                print(f"  Result: {result.result}")
        
        if not args.ocr and not args.analyze:
            # Demo
            print("\n--- DEMO ---")
            
            # Test linguistics
            test_text = "Apple Inc. announced that CEO Tim Cook will visit Paris next week to discuss AI partnerships with European companies."
            print(f"\nAnalyzing: '{test_text}'")
            
            results = await engine.analyze_text(test_text, ["ner", "sentiment", "keywords"])
            
            print("\nNamed Entities:")
            for ent in results["ner"].result:
                print(f"  - {ent['text']} ({ent['label']})")
            
            print(f"\nSentiment: {results['sentiment'].result}")
            
            print("\nKeywords:")
            for kw in results["keywords"].result[:5]:
                print(f"  - {kw['text']}")
    
    asyncio.run(main())
