#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web MCP Integration — SOTA 2026.

Model Context Protocol (MCP) web tools for Kingdom AI.
Exposes web_fetch and web_search to AI agents (Thoth, Truth Seeker, Cursor).

WebMCP (W3C 2026): Browser-native AI agent interaction.
This module provides backend MCP tools for web research, Truth Seeker, and
knowledge gathering. Compatible with MCP Python SDK and FastMCP.

Usage:
  - As component: event_bus.get_component('web_mcp_tools')
  - Standalone MCP server: python -m core.web_mcp_integration
  - Thoth/Truth Seeker call tools directly for web research
"""

import asyncio
import logging
import re
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("KingdomAI.WebMCP")

# Optional MCP SDK (mcp or fastmcp package)
HAS_MCP_SDK = False
FastMCP = None
try:
    from mcp.server.fastmcp import FastMCP
    HAS_MCP_SDK = True
except ImportError:
    try:
        from fastmcp import FastMCP
        HAS_MCP_SDK = True
    except ImportError:
        pass


def _fetch_url_sync(url: str, timeout: float = 12.0) -> Optional[str]:
    """Fetch URL synchronously."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KingdomAI-WebMCP/1.0"})
        with urllib.request.urlopen(req, timeout=int(timeout)) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("web_fetch %s: %s", url[:50], e)
    return None


async def _fetch_url_async(url: str, timeout: float = 12.0) -> Optional[str]:
    """Fetch URL asynchronously."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status == 200:
                    return await r.text()
    except Exception:
        try:
            return _fetch_url_sync(url, timeout)
        except Exception:
            pass
    return None


def _extract_text(html: str, max_chars: int = 4000) -> str:
    """Extract readable text from HTML."""
    if not html:
        return ""
    t = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.I)
    t = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_chars] if t else ""


def web_fetch(url: str, extract_text: bool = True, max_chars: int = 4000) -> Dict[str, Any]:
    """
    Fetch a URL and return content. For Truth Seeker, research, knowledge gathering.

    Args:
        url: Full URL to fetch
        extract_text: If True, strip HTML and return plain text
        max_chars: Max chars to return when extracting text

    Returns:
        {"ok": bool, "url": str, "content": str, "error": str|None}
    """
    try:
        html = _fetch_url_sync(url)
        if not html:
            return {"ok": False, "url": url, "content": "", "error": "fetch_failed"}
        content = _extract_text(html, max_chars) if extract_text else html[:max_chars]
        return {"ok": True, "url": url, "content": content, "error": None}
    except Exception as e:
        return {"ok": False, "url": url, "content": "", "error": str(e)}


async def web_fetch_async(url: str, extract_text: bool = True, max_chars: int = 4000) -> Dict[str, Any]:
    """Async web_fetch."""
    try:
        html = await _fetch_url_async(url)
        if not html:
            return {"ok": False, "url": url, "content": "", "error": "fetch_failed"}
        content = _extract_text(html, max_chars) if extract_text else html[:max_chars]
        return {"ok": True, "url": url, "content": content, "error": None}
    except Exception as e:
        return {"ok": False, "url": url, "content": "", "error": str(e)}


def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the web via DuckDuckGo HTML. For Truth Seeker, research.

    Args:
        query: Search query
        max_results: Max snippets to return

    Returns:
        {"ok": bool, "query": str, "results": [{"text": str, "source": str}], "error": str|None}
    """
    try:
        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        html = _fetch_url_sync(url, 10.0)
        if not html:
            return {"ok": False, "query": query, "results": [], "error": "fetch_failed"}
        results = []
        for m in re.finditer(r'class="result__snippet"[^>]*>([^<]+)', html):
            snip = _extract_text(m.group(1), 600)
            if len(snip) > 60:
                results.append({"text": snip, "source": f"search:{query}"})
                if len(results) >= max_results:
                    break
        return {"ok": True, "query": query, "results": results, "error": None}
    except Exception as e:
        return {"ok": False, "query": query, "results": [], "error": str(e)}


def get_web_mcp_tools() -> Dict[str, Any]:
    """Return callable web tools for Thoth/Truth Seeker. Owner/Consumer desktop + mobile."""
    return {
        "web_fetch": web_fetch,
        "web_search": web_search,
        "web_fetch_async": web_fetch_async,
    }


class WebMCPTools:
    """Web MCP tools component. Registers with event bus."""

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._mcp_server = None

    def web_fetch(self, url: str, **kwargs) -> Dict[str, Any]:
        return web_fetch(url, **kwargs)

    def web_search(self, query: str, **kwargs) -> Dict[str, Any]:
        return web_search(query, **kwargs)

    def get_tools(self) -> Dict[str, Any]:
        return get_web_mcp_tools()


def get_web_mcp_tools_component(event_bus=None) -> WebMCPTools:
    """Get or create WebMCPTools component."""
    return WebMCPTools(event_bus=event_bus)


# ─── MCP Server (for external clients: Cursor, Claude Desktop) ───

def _create_mcp_server() -> Optional[Any]:
    """Create MCP server with web tools if SDK available."""
    if not HAS_MCP_SDK or FastMCP is None:
        return None
    try:
        mcp = FastMCP("KingdomAI-WebMCP", json_response=True)

        @mcp.tool()
        def web_fetch_tool(url: str, extract_text: bool = True, max_chars: int = 4000) -> dict:
            """Fetch a URL and return content. For research and Truth Seeker."""
            return web_fetch(url, extract_text=extract_text, max_chars=max_chars)

        @mcp.tool()
        def web_search_tool(query: str, max_results: int = 5) -> dict:
            """Search the web. For Truth Seeker, research, knowledge gathering."""
            return web_search(query, max_results=max_results)

        return mcp
    except Exception as e:
        logger.debug("MCP server create: %s", e)
    return None


def run_mcp_server(transport: str = "stdio") -> None:
    """Run Web MCP server. Use streamable-http for remote, stdio for local."""
    mcp = _create_mcp_server()
    if mcp:
        mcp.run(transport=transport)
    else:
        logger.warning("MCP SDK not installed. pip install mcp[cli] httpx")


if __name__ == "__main__":
    run_mcp_server()
