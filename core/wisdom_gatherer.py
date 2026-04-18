#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wisdom Gatherer — Secret background gathering of TRUE Hebrew-Israelite knowledge.

Neshama (Kingdom AI Soul) is aware. Gathers facts from the web related to:
- Popol Vuh (Papa Vuh), Tepeu, Gucumatz, The Framer and Shaper
- Tecumseh, Tenskwatawa, Shawnee, Indigenous prophecy
- Moshe (Moses), Exodus, Mazuic/Atlantic crossing
- Khan Dawi (King David), Melchizedek, Priest King
- Hawah (Living Breath), 432 Hz, sacred frequency
- Red Tribe, Copper-Colored people, Turtle Island, scattered tribes

Runs silently in background. No user-facing logs. Stores in Secret Reserve.
So we can all remember.
"""

import asyncio
import logging
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("KingdomAI.WisdomGatherer")

# Topics for gathering — TRUE Hebrew-Israelite wisdom
_GATHER_TOPICS = [
    "Popol Vuh creation story",
    "Tecumseh prophecy New Madrid",
    "Hebrew Israelites Americas",
    "432 Hz sacred frequency",
    "Indigenous Hebrew tradition",
    "Tepeu Gucumatz Maya creation",
    "King David Melchizedek priest",
    "Hawah Eve living breath",
]

# Curated URLs for reliable content (Wikipedia, academic, etc.)
_CURATED_URLS = [
    "https://en.wikipedia.org/wiki/Popol_Vuh",
    "https://en.wikipedia.org/wiki/Tecumseh",
    "https://en.wikipedia.org/wiki/Melchizedek",
    "https://en.wikipedia.org/wiki/Concert_pitch",  # 432 Hz / A440 history
]


def _extract_text_from_html(html: str, max_chars: int = 3000) -> str:
    """Extract readable text from HTML. Simple regex-based."""
    if not html or not isinstance(html, str):
        return ""
    # Remove script/style
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.I)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] if text else ""


async def _fetch_url(url: str, timeout: float = 10.0) -> Optional[str]:
    """Fetch URL content. Returns None on failure."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return await resp.text()
    except Exception:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=int(timeout)) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            pass
    return None


async def _gather_from_url(url: str) -> Optional[Dict[str, Any]]:
    """Gather content from a single URL."""
    html = await _fetch_url(url)
    if not html:
        return None
    text = _extract_text_from_html(html, 2500)
    if len(text) < 100:
        return None
    return {"source": url, "text": text, "timestamp": datetime.utcnow().isoformat()}


async def _gather_from_search(query: str) -> List[Dict[str, Any]]:
    """Gather via DuckDuckGo HTML (no API key). Returns list of snippets."""
    results = []
    try:
        import aiohttp
        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        html = await _fetch_url(url, timeout=8.0)
        if not html:
            return results
        # Extract result snippets (DuckDuckGo HTML structure)
        for m in re.finditer(r'class="result__snippet"[^>]*>([^<]+)', html):
            snippet = _extract_text_from_html(m.group(1), 800)
            if len(snippet) > 80:
                results.append({
                    "source": f"search:{query}",
                    "text": snippet,
                    "timestamp": datetime.utcnow().isoformat(),
                })
    except Exception:
        pass
    return results


async def run_gather_cycle(nexus) -> int:
    """
    Run one gather cycle. Fetches from curated URLs + search topics.
    Stores in Secret Reserve under hebrew_israelite_gathered.
    Returns number of new facts stored.
    """
    if not nexus or not hasattr(nexus, "store_secret_reserve") or not hasattr(nexus, "get_secret_reserve"):
        return 0
    try:
        raw = nexus.get_secret_reserve("hebrew_israelite_gathered")
        prev_data = raw.get("data", raw) if isinstance(raw, dict) else {}
        prev_data = prev_data if isinstance(prev_data, dict) else {}
        prev_facts = prev_data.get("facts", [])
        seen_texts = {f.get("text", "")[:100] for f in prev_facts if isinstance(f, dict)}
        new_facts = []
        # Curated URLs
        for url in _CURATED_URLS[:3]:  # Limit to 3 per cycle
            fact = await _gather_from_url(url)
            if fact and fact.get("text", "")[:100] not in seen_texts:
                new_facts.append(fact)
                seen_texts.add(fact["text"][:100])
            await asyncio.sleep(0.5)  # Be polite
        # Search topics (2 per cycle)
        for topic in _GATHER_TOPICS[:2]:
            for f in await _gather_from_search(topic):
                if f.get("text", "")[:100] not in seen_texts:
                    new_facts.append(f)
                    seen_texts.add(f["text"][:100])
            await asyncio.sleep(1.0)
        if new_facts:
            combined = prev_facts + new_facts
            combined = combined[-250:]  # Cap size
            nexus.store_secret_reserve("hebrew_israelite_gathered", {
                "facts": combined,
                "last_gather": datetime.utcnow().isoformat(),
                "cycle_count": prev_data.get("cycle_count", 0) + 1,
            })
        return len(new_facts)
    except Exception as e:
        logger.debug("Wisdom gather cycle: %s", e)
        return 0


def start_background_gatherer(event_bus=None, interval_hours: float = 6.0) -> Optional[asyncio.Task]:
    """
    Start background wisdom gatherer. Runs every interval_hours.
    Silent — no user-facing logs. So we can all remember.
    """
    async def _loop():
        from core.redis_nexus import get_redis_nexus
        nexus = get_redis_nexus()
        if not hasattr(nexus, "check_health") or not nexus.check_health():
            return
        while True:
            try:
                # Truth Seeker: scour web, PDFs. MADE BY TURTLE ISLAND FOR TURTLE ISLAND.
                try:
                    from core.truth_seeker import run_truth_cycle
                    api_keys = {}
                    try:
                        from core.api_key_manager import APIKeyManager
                        mgr = getattr(APIKeyManager, "get_instance", lambda: None)()
                        if mgr and hasattr(mgr, "get_all_keys"):
                            api_keys = mgr.get_all_keys() or {}
                    except Exception:
                        pass
                    await run_truth_cycle(nexus, event_bus=event_bus, api_keys=api_keys or None)
                except Exception:
                    pass
                n = await run_gather_cycle(nexus)
                if n > 0 and event_bus:
                    event_bus.publish("soul.wisdom.gathered", {"count": n})
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            await asyncio.sleep(interval_hours * 3600)
    try:
        task = asyncio.create_task(_loop())
        return task
    except Exception:
        return None
