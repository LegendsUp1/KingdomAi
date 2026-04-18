"""
Optional bridge to a local claw-code style workflow.
Set claw_repo_path in config; clone https://github.com/instructkr/claw-code if desired.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from core.kingdom_event_names import REQUEST_CLAW_CODING_TASK

logger = logging.getLogger("kingdom_ai.claw_code_bridge")


class ClawCodeBridge:
    def __init__(self, event_bus: Any, claw_repo_path: str = "~/claw-code"):
        self.event_bus = event_bus
        self.claw_path = Path(claw_repo_path).expanduser()
        if event_bus:
            event_bus.subscribe(REQUEST_CLAW_CODING_TASK, self._on_task)

    def _on_task(self, data: Any) -> None:
        task = data if isinstance(data, str) else (data or {}).get("task", "")
        if not task:
            return
        logger.info("ClawCodeBridge received task: %s", task[:120])
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._execute_and_publish(task))
            else:
                loop.run_until_complete(self._execute_and_publish(task))
        except RuntimeError:
            logger.warning("No event loop available for ClawCodeBridge task")

    async def _execute_and_publish(self, task: str) -> None:
        result = await self.execute_claw_task(task)
        if self.event_bus and hasattr(self.event_bus, "publish"):
            self.event_bus.publish("claw.task.result", result)
        if not result.get("success"):
            logger.warning("Claw task failed: %s", result.get("error", "unknown"))

    async def execute_claw_task(self, task: str, project_dir: Optional[str] = None) -> Dict[str, Any]:
        if not self.claw_path.exists():
            return {"success": False, "error": f"Clone claw-code to {self.claw_path}", "task": task}
        cargo = self.claw_path / "Cargo.toml"
        if not cargo.exists():
            return {"success": False, "error": "Cargo.toml not found in claw repo", "task": task}
        try:
            proc = subprocess.run(
                ["cargo", "run", "--release", "--manifest-path", str(cargo), "--", "--task", task],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.claw_path),
            )
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout[:2000],
                "stderr": proc.stderr[:2000],
                "task": task,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "task": task}
