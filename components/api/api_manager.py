#!/usr/bin/env python3
# APIManager for Kingdom AI

import logging
import asyncio
import time
from typing import Any, Dict, Optional
from core.base_component import BaseComponent

class APIManager(BaseComponent):
    """
    APIManager handles API key storage, validation, and proxied request
    dispatch for the Kingdom AI system.
    """
    
    def __new__(cls, event_bus=None, *args, **kwargs):
        return super().__new__(cls)
    
    def __init__(self, event_bus=None):
        super().__init__("APIManager", event_bus or None)
        self.logger = logging.getLogger("KingdomAI.APIManager")
        self._api_keys: Dict[str, Dict[str, Any]] = {}
        self._request_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self.logger.info("APIManager initialized")
    
    async def _initialize_impl(self) -> bool:
        try:
            if self.event_bus is None:
                self.logger.warning("APIManager: no event_bus, skipping subscriptions")
                return True
            self.event_bus.subscribe_sync('api.key.add', self._handle_api_key_add)
            self.event_bus.subscribe_sync('api.key.remove', self._handle_api_key_remove)
            self.event_bus.subscribe_sync('api.key.validate', self._handle_api_key_validate)
            self.event_bus.subscribe_sync('api.request', self._handle_api_request)
            self.logger.info("APIManager subscriptions initialized")
            return True
        except Exception as e:
            self.logger.error(f"APIManager _initialize_impl failed: {e}")
            return False
    
    async def _start_impl(self) -> bool:
        self._worker_task = asyncio.create_task(self._request_worker())
        self.is_running = True
        if self.event_bus:
            await self.publish_event("component.apimanager.started", {
                "status": "running",
                "keys_loaded": len(self._api_keys),
            })
        self.logger.info("APIManager started (request worker active)")
        return True
    
    async def _stop_impl(self) -> bool:
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        self.is_running = False
        if self.event_bus:
            await self.publish_event("component.apimanager.stopped", {"status": "stopped"})
        self.logger.info("APIManager stopped")
        return True
    
    async def _request_worker(self) -> None:
        while True:
            try:
                event_data = await asyncio.wait_for(self._request_queue.get(), timeout=1.0)
                await self._dispatch_request(event_data)
                self._request_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.error("Request worker error: %s", exc, exc_info=True)

    async def _dispatch_request(self, event_data: Dict[str, Any]) -> None:
        service = event_data.get("service", "")
        key_entry = self._api_keys.get(service)
        if not key_entry:
            self.logger.warning("No API key registered for service '%s'", service)
            if self.event_bus:
                await self.publish_event("api.request.error", {
                    "service": service,
                    "error": "no_key",
                    "request_id": event_data.get("request_id"),
                })
            return

        result: Dict[str, Any] = {
            "service": service,
            "request_id": event_data.get("request_id"),
            "key_alias": key_entry.get("alias", service),
            "endpoint": event_data.get("endpoint"),
            "params": event_data.get("params"),
            "dispatched_at": time.time(),
        }
        if self.event_bus:
            await self.publish_event("api.request.dispatched", result)
        self.logger.debug("Dispatched request for service=%s endpoint=%s", service, event_data.get("endpoint"))

    async def initialize(self):
        if self._initialized:
            return True
        ok = await super().initialize()
        if not ok:
            return False
        ok = await self._initialize_impl()
        return ok
    
    async def _handle_api_key_add(self, event_data):
        service = event_data.get("service")
        if not service:
            self.logger.warning("api.key.add missing 'service' field")
            return
        self._api_keys[service] = {
            "key": event_data.get("key"),
            "alias": event_data.get("alias", service),
            "added_at": time.time(),
            "valid": True,
        }
        self.logger.info("API key added for service '%s'", service)
        if self.event_bus:
            await self.publish_event("api.key.added", {"service": service, "status": "stored"})
        
    async def _handle_api_key_remove(self, event_data):
        service = event_data.get("service")
        if not service:
            return
        removed = self._api_keys.pop(service, None)
        if removed:
            self.logger.info("API key removed for service '%s'", service)
        else:
            self.logger.debug("No API key found for service '%s' to remove", service)
        if self.event_bus:
            await self.publish_event("api.key.removed", {
                "service": service,
                "existed": removed is not None,
            })
        
    async def _handle_api_key_validate(self, event_data):
        service = event_data.get("service")
        entry = self._api_keys.get(service) if service else None
        valid = entry is not None and bool(entry.get("key"))
        if entry:
            entry["valid"] = valid
        self.logger.info("API key validation for '%s': %s", service, "valid" if valid else "invalid")
        if self.event_bus:
            await self.publish_event("api.key.validated", {"service": service, "valid": valid})
        
    async def _handle_api_request(self, event_data):
        if not self.is_running:
            self.logger.warning("APIManager not running, dropping request: %s", event_data.get("service"))
            return
        await self._request_queue.put(event_data)

