#!/usr/bin/env python3

"""Stratum client implementation for Kingdom AI Mining System.

This module provides an asyncio-based Stratum v1 client that connects to
Bitcoin-style mining pools over TCP, performs JSON-RPC 2.0 messaging, and
emits jobs and difficulty updates to the rest of the mining system.

The design is intentionally general so it can later be reused for GPU miners
and multi-coin setups.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("KingdomAI.StratumClient")


@dataclass
class StratumJob:
    """Represents a Stratum mining job from mining.notify.

    This structure is sufficient for building a coinbase transaction and
    block header for double-SHA256 proof-of-work.
    """

    job_id: str
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branches: List[str]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool


class StratumClient:
    """Async Stratum v1 client with basic reconnection logic.

    This class is responsible only for protocol handling and connection
    management. Actual hashing is delegated to a miner implementation.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str = "x",
        *,
        reconnect: bool = True,
        max_backoff: int = 60,
        client_name: str = "KingdomAI/1.0.0",
        on_job: Optional[Callable[[StratumJob], None]] = None,
        on_difficulty: Optional[Callable[[float], None]] = None,
        on_state: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.reconnect = reconnect
        self.max_backoff = max_backoff
        self.client_name = client_name

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._next_id: int = 1

        self._running: bool = False
        self._read_task: Optional[asyncio.Task] = None
        # Map JSON-RPC request ids to Futures for responses
        self._pending: Dict[int, asyncio.Future] = {}

        self.extranonce1: Optional[str] = None
        self.extranonce2_size: int = 4
        self.current_difficulty: float = 1.0
        self.last_job: Optional[StratumJob] = None

        self._on_job = on_job
        self._on_difficulty = on_difficulty
        self._on_state = on_state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the Stratum client and maintain the connection.

        This method will loop with backoff and attempt to reconnect if
        the connection drops, until :meth:`stop` is called.
        """

        if self._running:
            return

        self._running = True
        backoff = 1

        while self._running:
            try:
                await self._connect_once()
                backoff = 1  # Reset backoff after successful connect

                # Wait for the read loop to finish (until error or stop)
                if self._read_task:
                    await self._read_task
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Stratum connection error: %s", exc)
                self._emit_state("error", {"error": str(exc)})

            # Clean up writer
            try:
                if self._writer is not None:
                    self._writer.close()
                    await self._writer.wait_closed()
            except Exception:
                pass

            self._reader = None
            self._writer = None

            if not self._running or not self.reconnect:
                break

            # Backoff before reconnect
            delay = min(backoff, self.max_backoff)
            self._emit_state("reconnecting", {"delay": delay})
            await asyncio.sleep(delay)
            backoff = min(backoff * 2, self.max_backoff)

        self._running = False
        self._emit_state("stopped", {})

    async def stop(self) -> None:
        """Stop the client and close the connection."""

        self._running = False
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

        self._reader = None
        self._writer = None

    async def submit_share(
        self,
        job_id: str,
        extranonce2: str,
        ntime: str,
        nonce_hex: str,
    ) -> bool:
        """Submit a share using mining.submit.

        Returns True if the pool accepted the share (result==True), False
        otherwise.
        """

        req_id = self._next_request_id()
        params = [self.username, job_id, extranonce2, ntime, nonce_hex]
        request = {
            "id": req_id,
            "method": "mining.submit",
            "params": params,
        }
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        await self._send(request)

        try:
            result = await asyncio.wait_for(fut, timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("Stratum share submission timed out")
            return False
        finally:
            self._pending.pop(req_id, None)

        if isinstance(result, bool):
            return result
        return False

    # ------------------------------------------------------------------
    # Internal connection / protocol handling
    # ------------------------------------------------------------------

    async def _connect_once(self) -> None:
        """Open a TCP connection and perform subscribe/authorize."""

        self._emit_state("connecting", {"host": self.host, "port": self.port})
        self._reader, self._writer = await asyncio.open_connection(
            self.host, self.port
        )
        self._emit_state("connected", {"host": self.host, "port": self.port})

        # Initialize per-connection state
        self._pending.clear()

        # Perform subscribe and authorize
        await self._subscribe_and_authorize()

        # Start read loop
        self._read_task = asyncio.create_task(self._read_loop())

    async def _subscribe_and_authorize(self) -> None:
        """Issue mining.subscribe and mining.authorize requests."""

        # mining.subscribe
        sub_id = self._next_request_id()
        sub_req = {
            "id": sub_id,
            "method": "mining.subscribe",
            "params": [self.client_name],
        }
        sub_future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[sub_id] = sub_future
        await self._send(sub_req)

        try:
            sub_result = await asyncio.wait_for(sub_future, timeout=30.0)
        finally:
            self._pending.pop(sub_id, None)

        try:
            # Expected: [[["mining.set_difficulty", id1], ["mining.notify", id2]], extranonce1, extranonce2_size]
            if (
                isinstance(sub_result, list)
                and len(sub_result) >= 3
            ):
                self.extranonce1 = sub_result[1]
                self.extranonce2_size = int(sub_result[2])
                logger.info(
                    "Stratum subscribed: extranonce1=%s extranonce2_size=%s",
                    self.extranonce1,
                    self.extranonce2_size,
                )
        except Exception as exc:
            logger.warning("Failed to parse subscribe result: %s", exc)

        # mining.authorize
        auth_id = self._next_request_id()
        auth_req = {
            "id": auth_id,
            "method": "mining.authorize",
            "params": [self.username, self.password],
        }
        auth_future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[auth_id] = auth_future
        await self._send(auth_req)

        try:
            auth_result = await asyncio.wait_for(auth_future, timeout=30.0)
        finally:
            self._pending.pop(auth_id, None)

        if auth_result is not True:
            raise RuntimeError(f"Stratum authorization failed: {auth_result}")

        self._emit_state("authorized", {"username": self.username})

    async def _read_loop(self) -> None:
        """Continuously read JSON-RPC messages from the pool."""

        assert self._reader is not None
        reader = self._reader

        while self._running:
            line = await reader.readline()
            if not line:
                # Connection closed
                raise ConnectionError("Stratum connection closed by remote host")

            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line.decode("utf-8"))
            except Exception as exc:
                logger.warning("Failed to decode Stratum message: %s", exc)
                continue

            # Distinguish between response and notification
            if "id" in msg and msg.get("method") is None:
                await self._handle_response(msg)
            else:
                await self._handle_notification(msg)

    async def _handle_response(self, msg: Dict[str, Any]) -> None:
        """Handle JSON-RPC response messages."""

        msg_id = msg.get("id")
        if not isinstance(msg_id, int):
            return
        future = self._pending.get(msg_id)
        if not future:
            return

        if msg.get("error") is not None:
            future.set_result(False)
            return

        future.set_result(msg.get("result"))

    async def _handle_notification(self, msg: Dict[str, Any]) -> None:
        """Handle Stratum notifications (server-to-client methods)."""

        method = msg.get("method")
        params = msg.get("params", [])

        if method == "mining.notify":
            await self._handle_mining_notify(params)
        elif method == "mining.set_difficulty":
            await self._handle_set_difficulty(params)
        elif method == "mining.set_extranonce":
            await self._handle_set_extranonce(params)
        elif method == "client.reconnect":
            await self._handle_client_reconnect(params)
        elif method == "client.show_message":
            await self._handle_client_show_message(params)
        else:
            # Unknown/unused method; ignore
            logger.debug("Unhandled Stratum method: %s", method)

    async def _handle_mining_notify(self, params: List[Any]) -> None:
        """Handle mining.notify job notifications."""

        try:
            job = StratumJob(
                job_id=str(params[0]),
                prevhash=str(params[1]),
                coinb1=str(params[2]),
                coinb2=str(params[3]),
                merkle_branches=[str(x) for x in params[4]],
                version=str(params[5]),
                nbits=str(params[6]),
                ntime=str(params[7]),
                clean_jobs=bool(params[8]),
            )
            self.last_job = job
            logger.debug("Received Stratum job %s", job.job_id)
            if self._on_job:
                self._on_job(job)
        except Exception as exc:
            logger.error("Failed to parse mining.notify: %s", exc)

    async def _handle_set_difficulty(self, params: List[Any]) -> None:
        try:
            difficulty = float(params[0]) if params else 1.0
            self.current_difficulty = difficulty
            logger.info("Stratum difficulty set to %s", difficulty)
            if self._on_difficulty:
                self._on_difficulty(difficulty)
        except Exception as exc:
            logger.error("Failed to handle set_difficulty: %s", exc)

    async def _handle_set_extranonce(self, params: List[Any]) -> None:
        try:
            if len(params) >= 2:
                self.extranonce1 = str(params[0])
                self.extranonce2_size = int(params[1])
                logger.info(
                    "Stratum extranonce updated: extranonce1=%s extranonce2_size=%s",
                    self.extranonce1,
                    self.extranonce2_size,
                )
        except Exception as exc:
            logger.error("Failed to handle set_extranonce: %s", exc)

    async def _handle_client_reconnect(self, params: List[Any]) -> None:
        """Handle client.reconnect(server_host, port, waittime)."""

        try:
            host = params[0] if len(params) > 0 else self.host
            port = int(params[1]) if len(params) > 1 else self.port
            wait = int(params[2]) if len(params) > 2 else 0
        except Exception:
            host, port, wait = self.host, self.port, 0

        # For safety we only obey if host/port match original pool
        if host != self.host or port != self.port:
            logger.warning("Ignoring client.reconnect to different host %s:%s", host, port)
            return

        self._emit_state("reconnect_requested", {"wait": wait})
        await asyncio.sleep(max(wait, 0))
        # Force reconnect by breaking read loop
        raise ConnectionError("client.reconnect requested")

    async def _handle_client_show_message(self, params: List[Any]) -> None:
        try:
            message = str(params[0]) if params else ""
            logger.info("Stratum message: %s", message)
            self._emit_state("message", {"message": message})
        except Exception:
            pass

    async def _send(self, payload: Dict[str, Any]) -> None:
        """Send a JSON-RPC message followed by a newline."""

        if self._writer is None:
            raise ConnectionError("Stratum writer is not available")

        data = json.dumps(payload, separators=(",", ":")) + "\n"
        self._writer.write(data.encode("utf-8"))
        await self._writer.drain()

    def _next_request_id(self) -> int:
        req_id = self._next_id
        self._next_id += 1
        return req_id

    def _emit_state(self, state: str, info: Dict[str, Any]) -> None:
        if self._on_state:
            try:
                data = dict(info)
                data["state"] = state
                data["timestamp"] = time.time()
                self._on_state(state, data)
            except Exception:
                logger.exception("Error in StratumClient state callback")
