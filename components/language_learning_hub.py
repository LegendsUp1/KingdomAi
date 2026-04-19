"""Multi-language learning system with vocabulary, grammar, and translation."""

from __future__ import annotations

import json
import logging
import random
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.language_learning_hub")

SUPPORTED_LANGUAGES = ("spanish", "french", "german", "japanese", "mandarin")

PHRASE_BOOK: Dict[str, Dict[str, str]] = {
    "spanish": {
        "hello": "hola", "goodbye": "adiós", "thank you": "gracias",
        "please": "por favor", "yes": "sí", "no": "no",
        "good morning": "buenos días", "good night": "buenas noches",
        "how are you": "¿cómo estás?", "water": "agua",
        "food": "comida", "friend": "amigo", "house": "casa",
        "book": "libro", "love": "amor",
    },
    "french": {
        "hello": "bonjour", "goodbye": "au revoir", "thank you": "merci",
        "please": "s'il vous plaît", "yes": "oui", "no": "non",
        "good morning": "bonjour", "good night": "bonne nuit",
        "how are you": "comment allez-vous?", "water": "eau",
        "food": "nourriture", "friend": "ami", "house": "maison",
        "book": "livre", "love": "amour",
    },
    "german": {
        "hello": "hallo", "goodbye": "auf wiedersehen", "thank you": "danke",
        "please": "bitte", "yes": "ja", "no": "nein",
        "good morning": "guten morgen", "good night": "gute nacht",
        "how are you": "wie geht es Ihnen?", "water": "wasser",
        "food": "essen", "friend": "freund", "house": "haus",
        "book": "buch", "love": "liebe",
    },
    "japanese": {
        "hello": "こんにちは", "goodbye": "さようなら", "thank you": "ありがとう",
        "please": "お願いします", "yes": "はい", "no": "いいえ",
        "good morning": "おはようございます", "good night": "おやすみなさい",
        "how are you": "お元気ですか？", "water": "水",
        "food": "食べ物", "friend": "友達", "house": "家",
        "book": "本", "love": "愛",
    },
    "mandarin": {
        "hello": "你好", "goodbye": "再见", "thank you": "谢谢",
        "please": "请", "yes": "是", "no": "不",
        "good morning": "早上好", "good night": "晚安",
        "how are you": "你好吗？", "water": "水",
        "food": "食物", "friend": "朋友", "house": "房子",
        "book": "书", "love": "爱",
    },
}

GRAMMAR_NOTES: Dict[str, Dict[str, str]] = {
    "spanish": {"word_order": "SVO", "gendered_nouns": "yes (masculine/feminine)", "verb_conjugation": "6 persons"},
    "french": {"word_order": "SVO", "gendered_nouns": "yes (masculine/feminine)", "verb_conjugation": "6 persons"},
    "german": {"word_order": "SOV in subordinate", "gendered_nouns": "yes (m/f/n)", "cases": "4 (nom/acc/dat/gen)"},
    "japanese": {"word_order": "SOV", "particles": "postpositional", "politeness_levels": "3+"},
    "mandarin": {"word_order": "SVO", "tones": "4 + neutral", "measure_words": "required for counting"},
}


class LanguageLearningHub:
    """Multi-language learning hub with vocabulary, grammar, and practice."""

    def __init__(
        self,
        event_bus: Any = None,
        ollama_url: str = "http://localhost:11434",
        dictionary_brain: Any = None,
    ) -> None:
        self.event_bus = event_bus
        self._ollama_url = ollama_url
        self._session_history: List[Dict[str, Any]] = []
        self._dictionary_brain = dictionary_brain
        if event_bus:
            event_bus.subscribe("language.learn.request", self._on_learn_request)
        logger.info(
            "LanguageLearningHub initialised (%d languages, dictionary_brain=%s)",
            len(SUPPORTED_LANGUAGES),
            dictionary_brain is not None,
        )

    def set_dictionary_brain(self, dictionary_brain: Any) -> None:
        """Attach a DictionaryBrain after construction (used by the bootstrapper)."""
        self._dictionary_brain = dictionary_brain
        logger.info("LanguageLearningHub: dictionary_brain attached")

    def enrich_with_english_definition(self, english_word: str) -> Optional[Dict[str, Any]]:
        """Pull multi-era English context for a vocabulary word.

        Returns ``None`` if no DictionaryBrain is attached. Safe to call in
        practice sessions — non-blocking and swallows any lookup error.
        """
        if self._dictionary_brain is None or not english_word:
            return None
        try:
            return self._dictionary_brain.get_definition(english_word, source="auto")
        except Exception as exc:
            logger.debug("DictionaryBrain enrichment skipped: %s", exc)
            return None

    def translate(self, text: str, source_lang: str, target_lang: str) -> Dict[str, Any]:
        source_lang = source_lang.lower()
        target_lang = target_lang.lower()
        lower_text = text.lower().strip()
        if source_lang == "english" and target_lang in PHRASE_BOOK:
            match = PHRASE_BOOK[target_lang].get(lower_text)
            if match:
                return {"original": text, "translation": match, "source": source_lang, "target": target_lang, "method": "dictionary"}
        if target_lang == "english":
            for lang, phrases in PHRASE_BOOK.items():
                if lang == source_lang or source_lang == "auto":
                    for eng, foreign in phrases.items():
                        if foreign.lower() == lower_text:
                            return {"original": text, "translation": eng, "source": lang, "target": "english", "method": "dictionary"}
        ai_result = self._try_ollama_translate(text, source_lang, target_lang)
        if ai_result:
            return {"original": text, "translation": ai_result, "source": source_lang, "target": target_lang, "method": "ollama"}
        return {"original": text, "translation": f"[{target_lang}] {text}", "source": source_lang, "target": target_lang, "method": "passthrough"}

    def get_vocabulary(
        self,
        language: str,
        category: Optional[str] = None,
        enrich: bool = False,
    ) -> List[Dict[str, Any]]:
        language = language.lower()
        phrases = PHRASE_BOOK.get(language, {})
        vocab: List[Dict[str, Any]] = [
            {"english": eng, language: foreign} for eng, foreign in sorted(phrases.items())
        ]
        if category:
            cat = category.lower()
            vocab = [v for v in vocab if cat in v["english"]]
        if enrich and self._dictionary_brain is not None:
            for card in vocab:
                enrichment = self.enrich_with_english_definition(card["english"])
                if enrichment and enrichment.get("available"):
                    card["english_1828"] = enrichment.get("1828_webster")
                    card["english_etymology"] = self._safe_etymology(card["english"])
        return vocab

    def _safe_etymology(self, word: str) -> Optional[str]:
        if self._dictionary_brain is None:
            return None
        try:
            etym = self._dictionary_brain.get_etymology(word)
            return etym.get("full_etymology") if etym else None
        except Exception:
            return None

    def practice_session(self, language: str, difficulty: str = "beginner") -> List[Dict[str, Any]]:
        language = language.lower()
        phrases = PHRASE_BOOK.get(language, {})
        if not phrases:
            return [{"error": f"Unsupported language: {language}"}]
        items = list(phrases.items())
        count = {"beginner": 3, "intermediate": 5, "advanced": 8}.get(difficulty, 3)
        selected = random.sample(items, min(count, len(items)))
        exercises: List[Dict[str, Any]] = []
        for eng, foreign in selected:
            ex_type = random.choice(["translate_to_target", "translate_to_english", "fill_blank"])
            exercise: Dict[str, Any] = {"type": ex_type, "difficulty": difficulty, "language": language}
            if ex_type == "translate_to_target":
                exercise["prompt"] = f"Translate to {language}: '{eng}'"
                exercise["answer"] = foreign
            elif ex_type == "translate_to_english":
                exercise["prompt"] = f"Translate to English: '{foreign}'"
                exercise["answer"] = eng
            else:
                blanked = foreign[0] + "_" * (len(foreign) - 1) if len(foreign) > 1 else "_"
                exercise["prompt"] = f"Fill in the blank ({language} for '{eng}'): {blanked}"
                exercise["answer"] = foreign
            exercises.append(exercise)
        return exercises

    def analyze_grammar(self, text: str, language: str) -> Dict[str, Any]:
        language = language.lower()
        notes = GRAMMAR_NOTES.get(language, {})
        word_count = len(text.split())
        char_count = len(text)
        analysis: Dict[str, Any] = {
            "language": language,
            "text": text,
            "word_count": word_count,
            "char_count": char_count,
            "grammar_notes": notes if notes else {"info": "Grammar data not available for this language"},
            "sentence_count": text.count(".") + text.count("!") + text.count("?") + (1 if text and text[-1] not in ".!?" else 0),
        }
        return analysis

    def _try_ollama_translate(self, text: str, source: str, target: str) -> Optional[str]:
        try:
            payload = json.dumps({
                "model": "llama3",
                "prompt": f"Translate from {source} to {target}. Reply ONLY with the translation:\n{text}",
                "stream": False,
            }).encode()
            req = urllib.request.Request(f"{self._ollama_url}/api/generate", data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            return data.get("response", "").strip() or None
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None

    def _on_learn_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("learn request ignored — expected dict")
            return
        action = data.get("action", "translate")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            if action == "translate":
                result["data"] = self.translate(data.get("text", ""), data.get("source", "english"), data.get("target", "spanish"))
            elif action == "vocabulary":
                result["data"] = self.get_vocabulary(data.get("language", "spanish"), data.get("category"))
            elif action == "practice":
                result["data"] = self.practice_session(data.get("language", "spanish"), data.get("difficulty", "beginner"))
            elif action == "grammar":
                result["data"] = self.analyze_grammar(data.get("text", ""), data.get("language", "spanish"))
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("Language learning request failed")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("language.learn.result", result)
