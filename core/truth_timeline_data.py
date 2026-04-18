#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Truth Timeline Data — shared loader for desktop GUI and mobile.

No PyQt dependency. Used by:
  - gui/widgets/truth_timeline_window.py (desktop popup)
  - core/mobile_sync_server.py (mobile get_truth_timeline)
"""

from typing import Any, Dict


def load_all_facts(nexus) -> Dict[str, Any]:
    """Load all facts from Secret Reserve. Timeline + sources."""
    out = {"foundation": "", "gathered": [], "documents": [], "truth_records": [], "timeline": []}
    if not nexus or not hasattr(nexus, "get_secret_reserve"):
        return out
    try:
        raw = nexus.get_secret_reserve("hebrew_israelite_wisdom")
        if isinstance(raw, dict):
            d = raw.get("data", raw)
            if isinstance(d, dict) and d.get("content"):
                out["foundation"] = d["content"]
        g = nexus.get_secret_reserve("hebrew_israelite_gathered")
        if isinstance(g, dict):
            gd = g.get("data", g)
            if isinstance(gd, dict) and gd.get("facts"):
                out["gathered"] = gd["facts"]
        m = nexus.get_secret_reserve("_m_facts")
        if isinstance(m, dict):
            md = m.get("data", m)
            if isinstance(md, dict) and md.get("f"):
                out["documents"] = md["f"]
        tr = nexus.get_secret_reserve("truth_seeker_records")
        if isinstance(tr, dict):
            trd = tr.get("data", tr)
            if isinstance(trd, dict) and trd.get("r"):
                out["truth_records"] = trd["r"]
        for f in out["gathered"]:
            if isinstance(f, dict):
                ts = f.get("timestamp", "")
                out["timeline"].append({"t": ts, "source": "gathered", "text": f.get("text", "")[:500]})
        for f in out["documents"]:
            if isinstance(f, dict):
                ts = f.get("t", "")
                out["timeline"].append({"t": ts, "source": "document", "text": f.get("excerpt", "")[:500], "ts": f.get("ts")})
        for f in out["truth_records"]:
            if isinstance(f, dict):
                ts = f.get("t", "")
                out["timeline"].append({"t": ts, "source": "truth_seeker", "text": f.get("text", "")[:500], "ts": f.get("ts")})
        out["timeline"].sort(key=lambda x: x.get("t", ""), reverse=True)
    except Exception:
        pass
    return out
