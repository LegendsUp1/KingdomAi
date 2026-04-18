from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

import json

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
except Exception:  # pragma: no cover - torch may not be installed in some envs
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    optim = None  # type: ignore[assignment]

from core.base_component_v2 import BaseComponentV2


@dataclass
class Transition:
    """Simple transition tuple for online RL updates."""

    state: np.ndarray
    action: np.ndarray
    reward: float
    next_state: np.ndarray
    done: bool


class SmallQNetwork(nn.Module):  # type: ignore[misc]
    """Tiny MLP Q-network for streaming updates.

    Input is a concatenated [state, action] vector. The architecture is kept
    deliberately small so that incremental gradient steps can run in the
    background without blocking the main event loop.
    """

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 64) -> None:
        super().__init__()
        in_dim = state_dim + action_dim
        self.net = nn.Sequential(  # type: ignore[arg-type]
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        return self.net(x)


class QEstimatorAdapter:
    """Adapter exposing OnlineRLTrainer.q_net as predict(np.ndarray) -> np.ndarray.

    This matches the expectation of ConservativeSizingPolicy.load_q_estimator
    so that sizing decisions can be informed by the streaming RL Q-function
    without coupling callers to PyTorch.
    """

    def __init__(self, trainer: "OnlineRLTrainer") -> None:
        self._trainer = trainer

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Return Q-value estimates for given state-action vectors.

        Args:
            x: np.ndarray of shape (N, D) with D == state_dim + action_dim.
        Returns:
            np.ndarray of shape (N, 1) with scalar Q-values.
        """

        import numpy as _np

        if not self._trainer._torch_available or self._trainer.q_net is None or self._trainer.device is None:
            return _np.zeros((x.shape[0], 1), dtype=float)

        if x.ndim == 1:
            x = x.reshape(1, -1)

        with torch.no_grad():  # type: ignore[union-attr]
            t = torch.from_numpy(_np.asarray(x, dtype=_np.float32)).to(self._trainer.device)  # type: ignore[arg-type]
            out = self._trainer.q_net(t)  # type: ignore[union-attr]
            return out.detach().cpu().numpy()


class OnlineRLTrainer(BaseComponentV2):
    """Background online RL trainer over paper + live trading telemetry.

    This component is intentionally lightweight and runs entirely in the
    backend. It:

    - Listens to ``autotrade.paper.trade_closed`` events to build a small
      replay buffer of trade-level transitions.
    - Performs incremental Q-learning style gradient steps in a background
      loop using ``asyncio.to_thread`` so the GUI and event loop remain
      responsive.
    - Emits high-level training telemetry on
      ``learning.rl_online.metrics`` for Thoth/Ollama and observability
      tools.

    The current implementation treats each closed trade as a transition with
    reward equal to realized PnL and features derived from the global paper
    account metrics at the time of close. It is designed as a SOTA 2025-26
    scaffold: you can extend the feature set, reward shaping, or even swap
    in a more advanced actor-critic algorithm without touching the rest of
    the system.
    """

    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(name="OnlineRLTrainer", event_bus=event_bus, config=config or {})
        self.logger = logging.getLogger("kingdom_ai.OnlineRLTrainer")

        # RL configuration (kept modest to avoid heavy resource usage).
        # State features are aligned with ConservativeSizingPolicy expectations
        # so a single Q-function can be used for both offline/online sizing:
        #   - recent_volatility
        #   - recent_drawdown_pct
        #   - win_rate
        #   - edge_estimate (avg trade return / edge proxy)
        self.state_dim: int = int(self.config.get("state_dim", 4))
        self.action_dim: int = int(self.config.get("action_dim", 1))
        self.gamma: float = float(self.config.get("gamma", 0.99))
        self.lr: float = float(self.config.get("lr", 3e-4))
        self.batch_size: int = int(self.config.get("batch_size", 64))
        self.max_buffer_size: int = int(self.config.get("max_buffer_size", 50_000))
        self.train_interval_seconds: float = float(self.config.get("train_interval_seconds", 2.0))
        self.metrics_emit_interval: float = float(self.config.get("metrics_emit_interval", 30.0))
        self.min_updates_for_ready: int = int(self.config.get("min_updates_for_ready", 200))
        self.min_transitions_for_ready: int = int(self.config.get("min_transitions_for_ready", 1_000))

        # Checkpoint configuration – where to store online Q-network weights so
        # the learned policy survives restarts. Defaults to a local
        # "checkpoints/online_rl" folder if not provided.
        self.checkpoint_dir: str = str(self.config.get("checkpoint_dir", "checkpoints/online_rl"))
        self.checkpoint_path: str = str(
            self.config.get(
                "checkpoint_path",
                os.path.join(self.checkpoint_dir, "online_rl_trainer_latest.pth"),
            )
        )

        # Replay buffer and training state.
        self._buffer: Deque[Transition] = deque(maxlen=self.max_buffer_size)
        self._last_state: Optional[np.ndarray] = None
        self._last_metrics_emit_ts: float = 0.0

        self._torch_available: bool = torch is not None and nn is not None and optim is not None
        if not self._torch_available:
            self.logger.warning("Torch not available – OnlineRLTrainer will run in telemetry-only mode")

        self.device = torch.device("cuda" if self._torch_available and torch.cuda.is_available() else "cpu") if self._torch_available else None  # type: ignore[arg-type]

        self.q_net: Optional[SmallQNetwork] = None
        self.target_q: Optional[SmallQNetwork] = None
        self.optimizer: Optional[optim.Optimizer] = None  # type: ignore[type-arg]

        self._total_updates: int = 0
        self._total_transitions: int = 0
        self._loss_ema: float = 0.0
        self._reward_ema: float = 0.0
        self._ema_alpha: float = 0.05

        self._ready: bool = False
        self._ready_reason: str = "WARMUP – insufficient data for online RL"

        # Last successful weight checkpoint wall-clock timestamp (seconds).
        self._last_checkpoint_ts: float = 0.0

        self._train_task: Optional[asyncio.Task] = None
        self._train_start_handle: Optional[asyncio.Handle] = None

        if self._torch_available:
            self._build_models()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _build_models(self) -> None:
        assert self._torch_available
        self.q_net = SmallQNetwork(self.state_dim, self.action_dim).to(self.device)  # type: ignore[arg-type]
        self.target_q = SmallQNetwork(self.state_dim, self.action_dim).to(self.device)  # type: ignore[arg-type]
        self.target_q.load_state_dict(self.q_net.state_dict())  # type: ignore[union-attr]
        self.optimizer = optim.Adam(self.q_net.parameters(), lr=self.lr)  # type: ignore[arg-type,union-attr]

    async def _initialize(self) -> None:
        self.logger.info(
            "OnlineRLTrainer initialized – state_dim=%d, action_dim=%d, buffer=%d",
            self.state_dim,
            self.action_dim,
            self.max_buffer_size,
        )
        # Best-effort restore of prior scalar state and Q-network weights so
        # learning continues across restarts instead of always starting from
        # scratch.
        try:
            await self._load_state_from_redis()
        except Exception as e:  # noqa: BLE001
            self._handle_error("Failed to load OnlineRLTrainer state from Redis", e)

    def _save_weights_checkpoint(self) -> None:
        """Save Q-network, target network, and optimizer state to disk.

        This uses a small single-file checkpoint so the online Q-function can
        be restored across restarts. It is best-effort and should not raise
        exceptions up the call stack.
        """

        if not self._torch_available or self.q_net is None or self.target_q is None or self.optimizer is None:
            return

        ck_path = self.checkpoint_path
        try:
            ck_dir = os.path.dirname(ck_path)
            if ck_dir and not os.path.exists(ck_dir):
                os.makedirs(ck_dir, exist_ok=True)
        except Exception:
            # Directory creation failures are non-fatal; checkpoint may fail.
            pass

        try:
            ck = {
                "state_dict": self.q_net.state_dict(),
                "target_state_dict": self.target_q.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "total_updates": self._total_updates,
                "total_transitions": self._total_transitions,
            }
            torch.save(ck, ck_path)
        except Exception as e:  # noqa: BLE001
            self._handle_error("Failed to save OnlineRLTrainer weights checkpoint", e)

    def _load_weights_checkpoint(self) -> None:
        """Load Q-network, target network, and optimizer state from disk.

        If no checkpoint exists or torch is unavailable, this is a no-op.
        """

        if not self._torch_available or self.q_net is None or self.target_q is None or self.optimizer is None:
            return

        ck_path = self.checkpoint_path
        if not ck_path or not os.path.exists(ck_path):
            return

        try:
            try:
                ck = torch.load(ck_path, map_location=self.device, weights_only=True)
            except TypeError:
                ck = torch.load(ck_path, map_location=self.device)
            state_dict = ck.get("state_dict")
            target_state_dict = ck.get("target_state_dict")
            optimizer_state = ck.get("optimizer")
            if state_dict:
                self.q_net.load_state_dict(state_dict)
            if target_state_dict:
                self.target_q.load_state_dict(target_state_dict)
            if optimizer_state:
                self.optimizer.load_state_dict(optimizer_state)

            try:
                self._total_updates = int(ck.get("total_updates", self._total_updates) or self._total_updates)
                self._total_transitions = int(ck.get("total_transitions", self._total_transitions) or self._total_transitions)
            except Exception:
                pass

            self.logger.info(
                "Loaded OnlineRLTrainer weights checkpoint from %s – transitions=%d, updates=%d",
                ck_path,
                self._total_transitions,
                self._total_updates,
            )
        except Exception as e:  # noqa: BLE001
            self._handle_error("Failed to load OnlineRLTrainer weights checkpoint", e)

    async def _register_event_handlers(self) -> None:
        # Trade-level events from PaperAutotradeOrchestrator.
        await self.subscribe("autotrade.paper.trade_closed", self._on_trade_closed)

    async def _start(self) -> None:
        if not self._torch_available:
            self.logger.info("OnlineRLTrainer running without torch – telemetry only, no gradient updates")
            return

        # qasync safety: defer task creation until after the current startup task yields.
        # Creating/awakening background tasks too early can trigger qasync reentrancy errors
        # ("Cannot enter into task ... while another task ... is being executed").
        if self._train_task is None or self._train_task.done():
            loop = asyncio.get_running_loop()

            def _start_training_loop() -> None:
                if self._train_task is None or self._train_task.done():
                    self._train_task = loop.create_task(
                        self._training_loop(),
                        name="online_rl_training_loop",
                    )
                self._train_start_handle = None

            if self._train_start_handle is None:
                self._train_start_handle = loop.call_soon(_start_training_loop)

    async def _stop(self) -> None:
        if self._train_start_handle is not None:
            self._train_start_handle.cancel()
            self._train_start_handle = None

        if self._train_task is not None:
            self._train_task.cancel()
            try:
                await self._train_task
            except asyncio.CancelledError:  # pragma: no cover - normal shutdown
                pass
            self._train_task = None

        # Persist final state on clean shutdown so we can resume on restart.
        try:
            await self._persist_state_to_redis()
        except Exception as e:  # noqa: BLE001
            self._handle_error("Failed to persist OnlineRLTrainer state to Redis on stop", e)

        # Best-effort weight checkpoint on stop.
        try:
            self._save_weights_checkpoint()
        except Exception as e:  # noqa: BLE001
            self._handle_error("Failed to save OnlineRLTrainer weights checkpoint on stop", e)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_trade_closed(self, payload: Dict[str, Any]) -> None:
        """Ingest a closed paper trade and enqueue a transition."""

        try:
            state = self._extract_state(payload)
            reward = float(payload.get("pnl", 0.0) or 0.0)
            done = False

            if self._last_state is None:
                prev_state = state
            else:
                prev_state = self._last_state
            self._last_state = state

            # For now we use a dummy scalar action; future versions can feed
            # actual size-fraction or strategy decisions here.
            action = np.asarray([1.0], dtype=float)

            self._buffer.append(
                Transition(
                    state=prev_state,
                    action=action,
                    reward=reward,
                    next_state=state,
                    done=done,
                )
            )
            self._total_transitions += 1

        except Exception as e:  # noqa: BLE001
            self._handle_error("Error handling autotrade.paper.trade_closed", e)

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def _extract_state(self, payload: Dict[str, Any]) -> np.ndarray:
        """Build a compact state vector from a trade_closed payload.

        We use global paper account metrics at the time of close as a coarse
        summary of regime and recent performance. Features are intentionally
        aligned with ConservativeSizingPolicy._state_action_vector so the
        same Q-function can inform position sizing:

            - recent_volatility      ~ scale of recent returns
            - recent_drawdown_pct    ~ max drawdown in percent
            - win_rate               ~ wins / (wins + losses)
            - edge_estimate          ~ avg trade return
        """

        metrics = payload.get("metrics_snapshot") or {}
        try:
            equity = float(metrics.get("equity", 0.0) or 0.0)
            peak = float(metrics.get("equity_peak", equity) or equity)
            min_eq = float(metrics.get("equity_min", equity) or equity)
            wins = int(metrics.get("wins", 0) or 0)
            losses = int(metrics.get("losses", 0) or 0)
            trade_count = int(metrics.get("trade_count", 0) or 0)
            gross_profit = float(metrics.get("gross_profit", 0.0) or 0.0)
            gross_loss = float(metrics.get("gross_loss", 0.0) or 0.0)
        except Exception:  # noqa: BLE001
            equity = peak = min_eq = 0.0
            wins = losses = trade_count = 0
            gross_profit = gross_loss = 0.0

        total = max(1, wins + losses)
        win_rate = wins / float(total)

        dd_pct = 0.0
        if peak > 0.0:
            dd_pct = (peak - min_eq) / peak * 100.0

        avg_trade_return = 0.0
        if trade_count > 0:
            avg_trade_return = (gross_profit - gross_loss) / float(trade_count)

        # Map into the canonical sizing feature space expected by
        # ConservativeSizingPolicy: recent_volatility, recent_drawdown_pct,
        # win_rate, edge_estimate.
        last_pnl = float(payload.get("pnl", 0.0) or 0.0)
        recent_volatility = float(metrics.get("recent_volatility", None) or 0.0)
        if recent_volatility <= 0.0:
            # Fallback proxy when no explicit volatility metric is available.
            recent_volatility = max(1e-6, abs(last_pnl) or abs(avg_trade_return))

        state_vec = np.asarray(
            [
                recent_volatility,
                dd_pct,
                win_rate,
                avg_trade_return,
            ],
            dtype=float,
        )

        if state_vec.shape[0] != self.state_dim:
            # Pad or truncate to match configured state_dim.
            if state_vec.shape[0] < self.state_dim:
                pad = np.zeros(self.state_dim - state_vec.shape[0], dtype=float)
                state_vec = np.concatenate([state_vec, pad], axis=0)
            else:
                state_vec = state_vec[: self.state_dim]
        return state_vec.astype(float)

    # ------------------------------------------------------------------
    # Training loop
    # ------------------------------------------------------------------

    async def _training_loop(self) -> None:
        """Background loop that periodically performs gradient steps."""

        assert self._torch_available
        while not self._shutdown_requested:
            try:
                if len(self._buffer) >= max(self.batch_size, 1):
                    loss, avg_reward = await asyncio.to_thread(self._train_step_batch)
                    self._update_emas(loss, avg_reward)
                    self._update_readiness()
                    await self._maybe_emit_metrics()
                    # Persist slowly-changing scalar state so restarts resume
                    # near the prior point. This is best-effort and should
                    # never block the training loop.
                    try:
                        await self._persist_state_to_redis()
                    except Exception as e:  # noqa: BLE001
                        self._handle_error("Failed to persist OnlineRLTrainer state to Redis", e)

                    # Best-effort periodic weight checkpoint. We keep this
                    # lightweight by saving at most once every
                    # metrics_emit_interval seconds.
                    try:
                        now_ck = time.time()
                        if (
                            self._last_checkpoint_ts <= 0.0
                            or now_ck - self._last_checkpoint_ts >= max(self.metrics_emit_interval, 10.0)
                        ):
                            self._save_weights_checkpoint()
                            self._last_checkpoint_ts = now_ck
                    except Exception as e:  # noqa: BLE001
                        self._handle_error("Failed to save OnlineRLTrainer weights checkpoint", e)
            except Exception as e:  # noqa: BLE001
                self._handle_error("Error in OnlineRLTrainer training loop", e)

            await asyncio.sleep(self.train_interval_seconds)

    def _train_step_batch(self) -> tuple[float, float]:
        """Run a single Q-learning style update on a random mini-batch."""

        assert self._torch_available and self.q_net is not None and self.target_q is not None and self.optimizer is not None

        batch_size = min(self.batch_size, len(self._buffer))
        idxs = np.random.choice(len(self._buffer), size=batch_size, replace=False)
        transitions = [list(self._buffer)[i] for i in idxs]

        states = np.stack([t.state for t in transitions], axis=0)
        actions = np.stack([t.action for t in transitions], axis=0)
        rewards = np.asarray([t.reward for t in transitions], dtype=float)
        next_states = np.stack([t.next_state for t in transitions], axis=0)
        dones = np.asarray([t.done for t in transitions], dtype=float)

        s = torch.from_numpy(states).float().to(self.device)
        a = torch.from_numpy(actions).float().to(self.device)
        r = torch.from_numpy(rewards).float().unsqueeze(-1).to(self.device)
        ns = torch.from_numpy(next_states).float().to(self.device)
        d = torch.from_numpy(dones).float().unsqueeze(-1).to(self.device)

        sa = torch.cat([s, a], dim=-1)
        with torch.no_grad():
            na = a  # placeholder: same action space; future versions can sample
            nsa = torch.cat([ns, na], dim=-1)
            q_next = self.target_q(nsa)
            q_target = r + self.gamma * (1.0 - d) * q_next

        q_values = self.q_net(sa)
        loss = torch.nn.functional.mse_loss(q_values, q_target)

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q_net.parameters(), 5.0)
        self.optimizer.step()

        # Soft update target network
        with torch.no_grad():
            tau = 0.01
            for p, tp in zip(self.q_net.parameters(), self.target_q.parameters()):
                tp.data.mul_(1.0 - tau)
                tp.data.add_(tau * p.data)

        self._total_updates += 1
        avg_reward = float(rewards.mean()) if rewards.size > 0 else 0.0
        return float(loss.detach().cpu().item()), avg_reward

    def _update_emas(self, loss: float, reward: float) -> None:
        alpha = self._ema_alpha
        if self._total_updates == 1:
            self._loss_ema = loss
            self._reward_ema = reward
            return
        self._loss_ema = (1.0 - alpha) * self._loss_ema + alpha * loss
        self._reward_ema = (1.0 - alpha) * self._reward_ema + alpha * reward

    def _update_readiness(self) -> None:
        if self._total_transitions < self.min_transitions_for_ready:
            self._ready = False
            self._ready_reason = (
                f"WARMUP – transitions={self._total_transitions}/{self.min_transitions_for_ready}"
            )
            return
        if self._total_updates < self.min_updates_for_ready:
            self._ready = False
            self._ready_reason = (
                f"LEARNING – updates={self._total_updates}/{self.min_updates_for_ready}"
            )
            return
        self._ready = True
        self._ready_reason = (
            f"READY – online RL trained with transitions={self._total_transitions}, updates={self._total_updates}"
        )

    async def _maybe_emit_metrics(self) -> None:
        now = time.time()
        if now - self._last_metrics_emit_ts < self.metrics_emit_interval:
            return

        payload: Dict[str, Any] = {
            "timestamp": now,
            "total_transitions": self._total_transitions,
            "total_updates": self._total_updates,
            "buffer_size": len(self._buffer),
            "loss_ema": self._loss_ema,
            "avg_reward_ema": self._reward_ema,
            "ready": self._ready,
            "reason": self._ready_reason,
            "last_checkpoint_ts": self._last_checkpoint_ts,
        }

        try:
            await self.publish_event("learning.rl_online.metrics", payload)
        except Exception as e:  # noqa: BLE001
            self._handle_error("Failed to publish learning.rl_online.metrics", e)

        self._last_metrics_emit_ts = now

    # ------------------------------------------------------------------
    # Q-estimator adapter for downstream sizing policies
    # ------------------------------------------------------------------

    def get_q_estimator_adapter(self) -> Optional[QEstimatorAdapter]:
        """Return a QEstimatorAdapter for this trainer's Q-network.

        Callers (e.g. ConservativeSizingPolicy) can use this to obtain a
        predict(np.ndarray) -> np.ndarray interface without depending on
        PyTorch or internal trainer details.
        """

        if not self._torch_available or self.q_net is None or self.device is None:
            return None
        return QEstimatorAdapter(self)

    # ------------------------------------------------------------------
    # Persistence helpers – keep online RL state across restarts
    # ------------------------------------------------------------------

    async def _persist_state_to_redis(self) -> None:
        """Persist coarse OnlineRLTrainer state so learning is not lost.

        This writes small scalar summaries only (no replay buffer) to keep
        Redis usage minimal while still allowing the trainer to resume with
        realistic counters/EMAs after a restart.
        """

        if not getattr(self, "redis_connected", False) or getattr(self, "redis", None) is None:
            return

        try:
            state: Dict[str, Any] = {
                "total_transitions": self._total_transitions,
                "total_updates": self._total_updates,
                "loss_ema": self._loss_ema,
                "reward_ema": self._reward_ema,
                "ready": self._ready,
                "ready_reason": self._ready_reason,
                "state_dim": self.state_dim,
                "action_dim": self.action_dim,
            }
            payload = json.dumps(state)
            await asyncio.to_thread(self.redis.set, "online_rl_trainer:state", payload)
        except Exception as e:  # noqa: BLE001
            self._handle_error("Failed to persist OnlineRLTrainer state to Redis", e)

    async def _load_state_from_redis(self) -> None:
        """Restore OnlineRLTrainer state from Redis if present."""

        if not getattr(self, "redis_connected", False) or getattr(self, "redis", None) is None:
            return

        try:
            raw = await asyncio.to_thread(self.redis.get, "online_rl_trainer:state")
            if not raw:
                return
            data = json.loads(raw)
            if not isinstance(data, dict):
                return

            self._total_transitions = int(data.get("total_transitions", self._total_transitions) or self._total_transitions)
            self._total_updates = int(data.get("total_updates", self._total_updates) or self._total_updates)
            self._loss_ema = float(data.get("loss_ema", self._loss_ema) or self._loss_ema)
            self._reward_ema = float(data.get("reward_ema", self._reward_ema) or self._reward_ema)
            self._ready = bool(data.get("ready", self._ready))
            self._ready_reason = str(data.get("ready_reason", self._ready_reason) or self._ready_reason)

            self.logger.info(
                "Restored OnlineRLTrainer state from Redis – transitions=%d, updates=%d, ready=%s",
                self._total_transitions,
                self._total_updates,
                self._ready,
            )
        except Exception as e:  # noqa: BLE001
            self._handle_error("Failed to load OnlineRLTrainer state from Redis", e)
