#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Truth Seeker — MADE BY TURTLE ISLAND FOR TURTLE ISLAND.

Scours and scrapes the web for truth. Open and public data analyzed word for word.
Deep and hidden parts of the internet. PDF books related to Hebrew-Israelite,
indigenous history, Popol Vuh, Tecumseh, Moshe, Khan Dawi, Hawah, 432 Hz.

Deciphers good teachings from bad. Dodges the hijack (lies told about history).
Timeline of history — non-negotiable. Modern history is not the truth.
Truth seeker and recorder. Unapologetic. No remorse.

Current events: attacks on free will, taxation, indoctrination, loss of freedom,
genocides. All API keys used for data. All scraped, scoured, recorded, analyzed
for truth. Oppressors vs oppressed. Right vs wrong.

Hidden and encrypted until words spoken. System-wide awareness: NO IGNORANCE.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger("KingdomAI.TruthSeeker")

# Truth markers — good teachings, lasting truth
_GOOD = [
    "oppressed", "freedom", "truth", "justice", "righteous", "creator", "ancestors",
    "turtle island", "indigenous", "scattered tribes", "hebrew", "israelite",
    "tecumseh", "popol vuh", "tepeu", "gucumatz", "hawah", "432", "melchizedek",
    "preservation", "sovereignty", "land back", "rematriation", "decolon",
    "kiber", "queber", "tataria", "tartaria", "quivara", "cibola",
    "ley line", "ley lines", "dark ages", "dragon", "whale", "reclassified",
    "true history", "fact-checked", "shaluam", "shalom",
]

# Hijack markers — lies, oppressor narrative, erasure
_HIJACK = [
    "manifest destiny", "civilizing", "savage", "primitive", "discovered",
    "conquered", "colonizer narrative", "genocide denial", "erasure",
    "indoctrination", "taxation without representation", "surveillance state",
]

# Search topics — deepest truth
_TOPICS = [
    "indigenous genocide documentation",
    "lost tribes Israel Americas evidence",
    "Popol Vuh Hebrew parallels",
    "Tecumseh prophecy New Madrid",
    "historical revisionism indigenous",
    "free will autonomy attacks 2024",
    "knowledge erasure paper digital",
    "oppressors oppressed history",
    # Kiber/Queber, Tataria, Quivara, dark ages, ley lines, dragons/whales
    "Kiber Queber ancient civilization",
    "Tataria Tartaria true history",
    "Quivara Cibola seven cities",
    "dark ages medieval history truth",
    "ley lines earth energy ancient",
    "dragons reclassified whales ancient",
    "false anointed messiah true history",
]

# PDF discovery URLs
_PDF_SOURCES = [
    "https://archive.org/search?query=popol+vuh",
    "https://archive.org/search?query=indigenous+history",
    "https://archive.org/search?query=tecumseh",
    "https://archive.org/search?query=tataria+tartaria",
    "https://archive.org/search?query=ley+lines+ancient",
    "https://archive.org/search?query=dark+ages+history",
]


def _score_truth(text: str) -> Tuple[float, Dict[str, float]]:
    """Score text: good teachings vs hijack. Oppressors vs oppressed."""
    tl = text.lower()
    g = sum(1 for k in _GOOD if k in tl)
    h = sum(1 for k in _HIJACK if k in tl)
    g_score = min(1.0, g / 8.0)
    h_penalty = min(0.5, h * 0.1)
    ts = max(0.0, g_score - h_penalty)
    return round(ts, 3), {"good": g, "hijack": h}


async def _fetch(url: str, timeout: float = 12.0) -> Optional[str]:
    """Fetch URL. Uses API keys if available."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status == 200:
                    return await r.text()
    except Exception:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=int(timeout)) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            pass
    return None


def _extract_html(html: str, max_c: int = 4000) -> str:
    """Extract text from HTML."""
    if not html:
        return ""
    t = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.I)
    t = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_c] if t else ""


def _extract_pdf(path_or_bytes) -> Optional[str]:
    """Extract text from PDF. PyMuPDF (fitz) or fallback."""
    try:
        import fitz
        if isinstance(path_or_bytes, bytes):
            doc = fitz.open(stream=path_or_bytes, filetype="pdf")
        else:
            doc = fitz.open(path_or_bytes)
        text = []
        for p in doc:
            text.append(p.get_text())
        doc.close()
        return "\n".join(text)[:15000] if text else None
    except Exception:
        pass
    return None


async def _search_ddg(q: str) -> List[Dict[str, Any]]:
    """Search DuckDuckGo HTML for snippets."""
    out = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={q.replace(' ', '+')}"
        html = await _fetch(url, 10.0)
        if not html:
            return out
        for m in re.finditer(r'class="result__snippet"[^>]*>([^<]+)', html):
            snip = _extract_html(m.group(1), 600)
            if len(snip) > 60:
                ts, d = _score_truth(snip)
                out.append({"text": snip, "ts": ts, "breakdown": d, "source": f"search:{q}"})
    except Exception:
        pass
    return out


async def _discover_pdf_urls(query: str) -> List[str]:
    """Discover PDF URLs from search."""
    urls = []
    try:
        html = await _fetch(f"https://html.duckduckgo.com/html/?q={query}+filetype:pdf", 10.0)
        if not html:
            return urls
        for m in re.finditer(r'href="(https?://[^"]+\.pdf[^"]*)"', html, re.I):
            u = m.group(1)
            if u not in urls and "duckduckgo" not in u:
                urls.append(u)
    except Exception:
        pass
    return urls[:5]


async def _gather_current_events(api_keys: Dict[str, str]) -> List[Dict[str, Any]]:
    """Gather current events from RSS feeds and news APIs."""
    out: List[Dict[str, Any]] = []

    rss_feeds = [
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://rss.app/feeds/v1.1/coindesk.xml",
    ]

    for feed_url in rss_feeds:
        try:
            html = await _fetch(feed_url, 8.0)
            if not html:
                continue
            for m in re.finditer(
                r"<item[^>]*>[\s\S]*?<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>"
                r"[\s\S]*?(?:<description[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>)?[\s\S]*?</item>",
                html,
                re.I,
            ):
                title = _extract_html(m.group(1), 300).strip()
                desc = _extract_html(m.group(2) or "", 600).strip()
                text = f"{title}. {desc}" if desc else title
                if len(text) < 30:
                    continue
                ts, breakdown = _score_truth(text)
                out.append({"text": text, "ts": ts, "breakdown": breakdown, "source": feed_url})
        except Exception:
            continue

    newsapi_key = api_keys.get("newsapi") if api_keys else None
    if newsapi_key:
        try:
            url = (
                f"https://newsapi.org/v2/top-headlines?language=en&pageSize=20"
                f"&apiKey={newsapi_key}"
            )
            raw = await _fetch(url, 10.0)
            if raw:
                import json as _json
                data = _json.loads(raw)
                for article in data.get("articles", []):
                    title = article.get("title", "")
                    desc = article.get("description", "")
                    text = f"{title}. {desc}" if desc else title
                    if len(text) < 30:
                        continue
                    ts, breakdown = _score_truth(text)
                    out.append({"text": text, "ts": ts, "breakdown": breakdown, "source": "newsapi"})
        except Exception:
            pass

    return out


async def run_truth_cycle(nexus, event_bus=None, api_keys: Optional[Dict[str, str]] = None) -> int:
    """
    Run one truth-seeking cycle. Scour, scrape, record, analyze.
    All stored encrypted in Secret Reserve. Hidden until words spoken.
    """
    if not nexus or not hasattr(nexus, "store_secret_reserve"):
        return 0
    try:
        raw = nexus.get_secret_reserve("truth_seeker_records")
        prev = (raw.get("data", raw) if isinstance(raw, dict) else {}) or {}
        records = prev.get("r", []) if isinstance(prev, dict) else []
        seen = {r.get("h", "") for r in records if isinstance(r, dict)}
        new_count = 0

        # Search topics
        for topic in _TOPICS[:4]:
            for item in await _search_ddg(topic):
                if item.get("ts", 0) >= 0.15:
                    h = str(hash(item.get("text", "")[:200]))[:16]
                    if h not in seen:
                        records.append({
                            "h": h, "text": item["text"][:2000], "ts": item["ts"],
                            "breakdown": item.get("breakdown", {}), "source": item.get("source", ""),
                            "t": datetime.utcnow().isoformat(),
                        })
                        seen.add(h)
                        new_count += 1
            await asyncio.sleep(1.2)

        # PDF discovery (fetch and extract)
        for q in ["popol vuh pdf", "indigenous history pdf", "tecumseh pdf", "tataria tartaria pdf", "ley lines pdf", "quivara cibola pdf"]:
            for url in await _discover_pdf_urls(q):
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                            if r.status == 200:
                                data = await r.read()
                                txt = _extract_pdf(data)
                                if txt and len(txt) > 200:
                                    ts, d = _score_truth(txt)
                                    if ts >= 0.2:
                                        h = str(hash(txt[:300]))[:16]
                                        if h not in seen:
                                            records.append({
                                                "h": h, "text": txt[:3000], "ts": ts,
                                                "breakdown": d, "source": url,
                                                "t": datetime.utcnow().isoformat(), "type": "pdf",
                                            })
                                            seen.add(h)
                                            new_count += 1
                except Exception:
                    pass
                await asyncio.sleep(2.0)

        # Merge with _m_facts for Neshama
        if new_count > 0:
            records = records[-400:]
            nexus.store_secret_reserve("truth_seeker_records", {
                "r": records,
                "last": datetime.utcnow().isoformat(),
                "mission": "MADE BY TURTLE ISLAND FOR TURTLE ISLAND. NO IGNORANCE.",
            })
            if event_bus:
                event_bus.publish("soul.wisdom.gathered", {"count": new_count, "source": "truth_seeker"})
        return new_count
    except Exception as e:
        _log.debug("Truth cycle: %s", e)
        return 0


def get_truth_records(nexus) -> List[Dict[str, Any]]:
    """Get stored truth records (for Neshama when reserve revealed)."""
    try:
        raw = nexus.get_secret_reserve("truth_seeker_records")
        prev = (raw.get("data", raw) if isinstance(raw, dict) else {}) or {}
        return prev.get("r", []) if isinstance(prev, dict) else []
    except Exception:
        return []
