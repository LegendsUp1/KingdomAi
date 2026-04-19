"""Model Context Protocol server exposing MemPalace as external tools."""

from __future__ import annotations

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.mempalace_mcp_server")


class _MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler that dispatches JSON-RPC style MCP tool calls."""

    server: "_MCPHTTPServer"

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug(fmt, *args)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._reply(400, {"error": "Invalid JSON"})
            return
        tool_name = payload.get("tool")
        params = payload.get("params", {})
        mcp = self.server.mcp_server
        result = mcp.handle_tool_call(tool_name, params)
        self._reply(200, result)

    def do_GET(self) -> None:
        mcp = self.server.mcp_server
        self._reply(200, {"tools": mcp.list_tools()})

    def _reply(self, code: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _MCPHTTPServer(HTTPServer):
    mcp_server: "MemPalaceMCPServer"


class MemPalaceMCPServer:
    """Exposes MemPalace read/write/search as MCP-compatible tools."""

    def __init__(self, event_bus: Any = None, palace: Any = None, persistence: Any = None) -> None:
        self.event_bus = event_bus
        self.palace = palace
        self.persistence = persistence
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, Callable[..., Any]] = {}
        self._http_server: Optional[_MCPHTTPServer] = None
        self.register_tools()
        if event_bus:
            event_bus.subscribe("mempalace.mcp.request", self._on_mcp_request)
        logger.info("MemPalaceMCPServer initialised with %d tools", len(self._tools))

    def register_tools(self) -> None:
        self._register("mempalace_write", {
            "name": "mempalace_write",
            "description": "Write a memory to the MemPalace",
            "parameters": {"key": "string", "value": "string", "metadata": "object (optional)"},
        }, self._tool_write)

        self._register("mempalace_read", {
            "name": "mempalace_read",
            "description": "Read memories matching a query",
            "parameters": {"query": "string", "top_k": "integer (optional, default 5)"},
        }, self._tool_read)

        self._register("mempalace_search", {
            "name": "mempalace_search",
            "description": "Search the palace structure across all wings",
            "parameters": {"query": "string"},
        }, self._tool_search)

        self._register("mempalace_structure", {
            "name": "mempalace_structure",
            "description": "Return the current palace wing/hall structure",
            "parameters": {},
        }, self._tool_structure)

    def _register(self, name: str, definition: Dict[str, Any], handler: Callable[..., Any]) -> None:
        self._tools[name] = definition
        self._handlers[name] = handler

    def handle_tool_call(self, tool_name: Optional[str], params: Dict[str, Any]) -> Dict[str, Any]:
        if not tool_name or tool_name not in self._handlers:
            available = list(self._tools.keys())
            return {"success": False, "error": f"Unknown tool '{tool_name}'. Available: {available}"}
        try:
            result = self._handlers[tool_name](params)
            return {"success": True, "tool": tool_name, "result": result}
        except Exception as exc:
            logger.exception("Tool call '%s' failed", tool_name)
            return {"success": False, "tool": tool_name, "error": str(exc)}

    def list_tools(self) -> List[Dict[str, Any]]:
        return list(self._tools.values())

    def start_server(self, host: str = "127.0.0.1", port: int = 8781) -> None:
        server = _MCPHTTPServer((host, port), _MCPRequestHandler)
        server.mcp_server = self
        self._http_server = server
        thread = threading.Thread(target=server.serve_forever, daemon=True, name="mcp-mempalace")
        thread.start()
        logger.info("MCP HTTP server listening on %s:%d", host, port)

    def stop_server(self) -> None:
        if self._http_server:
            self._http_server.shutdown()
            self._http_server = None
            logger.info("MCP HTTP server stopped")

    def _tool_write(self, params: Dict[str, Any]) -> Any:
        if not self.persistence:
            return {"error": "No persistence layer configured"}
        key = str(params.get("key", ""))
        value = str(params.get("value", ""))
        metadata = params.get("metadata")
        mid = self.persistence.write_memory(key, value, metadata)
        return {"memory_id": mid, "key": key}

    def _tool_read(self, params: Dict[str, Any]) -> Any:
        if not self.persistence:
            return {"error": "No persistence layer configured"}
        query = str(params.get("query", ""))
        top_k = int(params.get("top_k", 5))
        return self.persistence.read_memory(query, top_k)

    def _tool_search(self, params: Dict[str, Any]) -> Any:
        if not self.palace:
            return {"error": "No palace manager configured"}
        query = str(params.get("query", ""))
        return self.palace.search_palace(query)

    def _tool_structure(self, params: Dict[str, Any]) -> Any:
        if not self.palace:
            return {"error": "No palace manager configured"}
        return self.palace.get_palace_structure()

    def _on_mcp_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("MCP request ignored — expected dict")
            return
        tool_name = data.get("tool")
        params = data.get("params", {})
        result = self.handle_tool_call(tool_name, params)
        if self.event_bus:
            self.event_bus.publish("mempalace.mcp.response", result)
