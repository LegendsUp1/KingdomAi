#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Internal module for document processing utilities.
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_l = logging.getLogger("KingdomAI.DocProc")

_T = {
    "popol": ["tepeu", "gucumatz", "framer", "shaper", "xibalba", "hunahpu", "xbalanque"],
    "moshe": ["exodus", "parting", "red sea", "yam suph", "tablets", "sinai", "burning bush"],
    "dawi": ["melchizedek", "priest king", "salem", "psalm 110", "order of"],
    "hawah": ["chava", "chavvah", "living", "breath", "life giver", "mother of all"],
    "freq": ["432", "hz", "pythagoras", "monochord", "spheres", "solfeggio", "schumann"],
    "tribe": ["copper", "red people", "turtle island", "scattered", "indigenous", "israelite"],
    "tecum": ["shawnee", "tenskwatawa", "prophet", "new madrid", "confederacy"],
    "paleo": ["𐤀", "𐤁", "𐤂", "𐤃", "𐤄", "𐤅", "𐤆", "𐤇", "𐤈", "𐤉", "phoenician", "proto"],
    "oppressed": ["oppressed", "genocide", "erasure", "sovereignty", "freedom", "land back"],
    "hijack": ["manifest destiny", "civilizing", "savage", "discovered", "conquered", "denial"],
}

_H = {
    "אמת": "emet_truth", "חסד": "chesed_kindness", "צדק": "tzedek_justice",
    "שלום": "shalom_peace", "חכמה": "chochmah_wisdom", "נשמה": "neshama_soul",
    "רוח": "ruach_spirit", "נפש": "nefesh_life", "תורה": "torah_teaching",
    "מלכות": "malkhut_kingdom", "כתר": "keter_crown", "בינה": "binah_understanding",
}

def _h(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()[:16]

def _s(t: str, p: List[str]) -> float:
    tl = t.lower()
    c = sum(1 for k in p if k in tl)
    return min(1.0, c / max(1, len(p) * 0.3))

def _a(t: str) -> Dict[str, float]:
    r = {}
    for k, v in _T.items():
        s = _s(t, v)
        if s > 0.1:
            r[k] = round(s, 3)
    return r

def _hb(t: str) -> Dict[str, bool]:
    r = {}
    for k, v in _H.items():
        if k in t:
            r[v] = True
    return r

def _x(t: str, img_data: Optional[bytes] = None) -> Dict[str, Any]:
    """Extract truth markers. Decipher good from bad. Dodge hijack (lies about history)."""
    al = _a(t)
    hb = _hb(t)
    
    # Paleo-Hebrew detection
    paleo = any(c in t for c in "𐤀𐤁𐤂𐤃𐤄𐤅𐤆𐤇𐤈𐤉𐤊𐤋𐤌𐤍𐤎𐤏𐤐𐤑𐤒𐤓𐤔𐤕")
    
    # 432 Hz markers
    f432 = bool(re.search(r"432\s*[hH]z|A=432|concert\s*pitch", t))
    
    # Oppressors vs oppressed — good teachings vs hijack
    tl = t.lower()
    oppr = 1.0 if any(k in tl for k in ["oppressed", "genocide", "erasure", "sovereignty", "freedom"]) else 0.0
    hij = -0.3 if any(k in tl for k in ["manifest destiny", "civilizing", "savage", "discovered", "conquered"]) else 0.0
    
    ts = 0.0
    if al:
        ts += sum(al.values()) / len(al) * 0.4
    if hb:
        ts += len(hb) * 0.1
    if paleo:
        ts += 0.2
    if f432:
        ts += 0.1
    ts += oppr * 0.15 + hij
    
    return {
        "alignment": al,
        "hebrew": hb,
        "paleo": paleo,
        "f432": f432,
        "oppressed_markers": oppr > 0,
        "hijack_penalty": hij < 0,
        "ts": round(min(1.0, max(0.0, ts)), 3),
        "h": _h(t[:500]),
    }

async def _p(content: str, source: str, img: Optional[bytes] = None) -> Dict[str, Any]:
    """Process document content for truth extraction."""
    if not content or len(content) < 50:
        return {}
    
    x = _x(content, img)
    
    # Only store if truth score > 0.15
    if x.get("ts", 0) < 0.15:
        return {"stored": False, "ts": x.get("ts", 0)}
    
    # Build fact
    fact = {
        "source": source,
        "ts": x["ts"],
        "alignment": x["alignment"],
        "hebrew": x["hebrew"],
        "paleo": x["paleo"],
        "f432": x["f432"],
        "h": x["h"],
        "t": datetime.utcnow().isoformat(),
        "excerpt": content[:1500],
    }
    
    # Store in Secret Reserve
    try:
        from core.redis_nexus import get_redis_nexus
        nx = get_redis_nexus()
        if hasattr(nx, "get_secret_reserve") and hasattr(nx, "store_secret_reserve"):
            raw = nx.get_secret_reserve("_m_facts")
            prev = (raw.get("data", raw) if isinstance(raw, dict) else {}) or {}
            facts = prev.get("f", []) if isinstance(prev, dict) else []
            
            # Dedupe by hash
            seen = {f.get("h") for f in facts if isinstance(f, dict)}
            if fact["h"] not in seen:
                facts.append(fact)
                facts = facts[-500:]  # Cap
                nx.store_secret_reserve("_m_facts", {"f": facts, "u": datetime.utcnow().isoformat()})
                
                # Notify soul
                try:
                    from core.event_bus import EventBus
                    eb = EventBus.get_instance()
                    if eb:
                        eb.publish("soul.wisdom.gathered", {"count": 1, "ts": fact["ts"]})
                except Exception:
                    pass
                
                return {"stored": True, "ts": fact["ts"], "alignment": fact["alignment"]}
    except Exception as e:
        _l.debug("_p store: %s", e)
    
    return {"stored": False, "ts": x.get("ts", 0)}

async def _v(content: str, bio_ok: bool = True) -> Tuple[bool, str]:
    """Verify content against biometric/will authorization."""
    if not bio_ok:
        return False, "bio_fail"
    
    # Check for hostile patterns (anti-Hebrew, anti-truth)
    hostile = [
        "destroy israel", "fake hebrew", "not real", "hoax", "conspiracy theory",
        "debunked", "pseudoscience", "false history",
    ]
    cl = content.lower()
    for h in hostile:
        if h in cl:
            return False, f"hostile:{h}"
    
    return True, "ok"

def _g() -> List[Dict[str, Any]]:
    """Get stored facts (for Neshama)."""
    try:
        from core.redis_nexus import get_redis_nexus
        nx = get_redis_nexus()
        if hasattr(nx, "get_secret_reserve"):
            raw = nx.get_secret_reserve("_m_facts")
            prev = (raw.get("data", raw) if isinstance(raw, dict) else {}) or {}
            return prev.get("f", []) if isinstance(prev, dict) else []
    except Exception:
        pass
    return []

class _M:
    """Document processor with truth extraction."""
    
    _instance = None
    
    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._bio_ok = True
        self._owner_present = True
        self._will_active = False
    
    def set_bio(self, ok: bool):
        self._bio_ok = ok
    
    def set_owner(self, present: bool):
        self._owner_present = present
        if not present:
            self._will_active = True
    
    async def process(self, content: str, source: str = "upload", img: Optional[bytes] = None) -> Dict[str, Any]:
        """Process uploaded document."""
        # Verify authorization
        ok, reason = await _v(content, self._bio_ok)
        if not ok:
            _l.debug("_M reject: %s", reason)
            return {"rejected": True, "reason": reason}
        
        # If owner absent and will active, apply stricter filtering
        if self._will_active and not self._owner_present:
            x = _x(content, img)
            if x.get("ts", 0) < 0.3:
                return {"rejected": True, "reason": "will_filter"}
        
        return await _p(content, source, img)
    
    def get_facts(self) -> List[Dict[str, Any]]:
        return _g()
    
    def get_truth_summary(self) -> Dict[str, Any]:
        facts = _g()
        if not facts:
            return {"count": 0}
        
        # Aggregate alignments
        agg = {}
        for f in facts:
            for k, v in f.get("alignment", {}).items():
                agg[k] = agg.get(k, 0) + v
        
        return {
            "count": len(facts),
            "alignment": agg,
            "paleo_count": sum(1 for f in facts if f.get("paleo")),
            "f432_count": sum(1 for f in facts if f.get("f432")),
            "avg_ts": round(sum(f.get("ts", 0) for f in facts) / len(facts), 3) if facts else 0,
        }

# Wire to HiveMind awareness
def _wire_hive():
    try:
        from core.security.hive_mind import HiveMind
        hm = HiveMind.get_instance()
        if hm and hasattr(hm, "event_bus") and hm.event_bus:
            def _on_threat(data):
                m = _M.get()
                if data.get("threat_level") == "emergency":
                    m.set_owner(False)
            hm.event_bus.subscribe("hive.threat.consensus", _on_threat)
    except Exception:
        pass

# Wire to biometric
def _wire_bio():
    try:
        from core.event_bus import EventBus
        eb = EventBus.get_instance()
        if eb:
            def _on_bio(data):
                m = _M.get()
                m.set_bio(data.get("verified", False))
                m.set_owner(data.get("creator_present", True))
            eb.subscribe("biometric.verification.result", _on_bio)
            eb.subscribe("security.creator.presence", _on_bio)
    except Exception:
        pass

# Auto-wire on import
try:
    _wire_hive()
    _wire_bio()
except Exception:
    pass

__all__ = ["_M", "_p", "_g"]
