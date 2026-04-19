"""Creates exploded assembly views showing component relationships."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kingdom_ai.exploded_view_engine")

EXPLODED_VIEW_REQUEST = "manufacturing.exploded_view.request"
EXPLODED_VIEW_RESULT = "manufacturing.exploded_view.result"


class Part:
    """A single part in an exploded assembly view."""

    def __init__(
        self,
        name: str,
        part_number: str = "",
        material: str = "",
        quantity: int = 1,
        position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        parent: Optional[str] = None,
        weight_kg: float = 0.0,
        notes: str = "",
    ) -> None:
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.part_number = part_number or f"P-{self.id}"
        self.material = material
        self.quantity = quantity
        self.position = position
        self.offset = offset
        self.parent = parent
        self.weight_kg = weight_kg
        self.notes = notes

    def exploded_position(self, factor: float) -> Tuple[float, float, float]:
        """Return position with offset scaled by *factor*."""
        return (
            self.position[0] + self.offset[0] * factor,
            self.position[1] + self.offset[1] * factor,
            self.position[2] + self.offset[2] * factor,
        )

    def to_dict(self, factor: float = 1.0) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "part_number": self.part_number,
            "material": self.material,
            "quantity": self.quantity,
            "position": list(self.position),
            "offset": list(self.offset),
            "exploded_position": list(self.exploded_position(factor)),
            "parent": self.parent,
            "weight_kg": self.weight_kg,
            "notes": self.notes,
        }


class ExplodedViewEngine:
    """Manages exploded assembly views and generates bills of materials."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._views: Dict[str, Dict[str, Any]] = {}
        logger.info("ExplodedViewEngine initialised")

        if event_bus:
            event_bus.subscribe(EXPLODED_VIEW_REQUEST, self._on_request)
            logger.debug("Subscribed to %s", EXPLODED_VIEW_REQUEST)

    # ── public API ───────────────────────────────────────────────────────────

    def create_exploded_view(self, assembly: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new exploded view from an assembly spec.

        *assembly* keys: name, description, parts (list of part dicts).
        Each part dict: name, material, quantity, position, offset, parent, weight_kg.
        """
        view_id = str(uuid.uuid4())[:8]
        view: Dict[str, Any] = {
            "id": view_id,
            "name": assembly.get("name", "Assembly"),
            "description": assembly.get("description", ""),
            "explosion_factor": assembly.get("explosion_factor", 1.5),
            "parts": [],
        }

        for p_spec in assembly.get("parts", []):
            part = self._make_part(p_spec)
            view["parts"].append(part)

        self._views[view_id] = view
        logger.info("create_exploded_view: id=%s, %d parts", view_id, len(view["parts"]))
        return self._view_to_dict(view)

    def add_part(self, view_id: str, part_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Add a part to an existing view."""
        view = self._views.get(view_id)
        if view is None:
            logger.warning("add_part: view %s not found", view_id)
            return {"error": f"View {view_id} not found"}

        part = self._make_part(part_spec)
        view["parts"].append(part)
        logger.debug("add_part: %s to view %s", part.name, view_id)
        return part.to_dict(view["explosion_factor"])

    def set_explosion_factor(self, view_id: str, factor: float) -> Dict[str, Any]:
        """Set the explosion separation factor (1.0 = assembled, higher = more separated)."""
        view = self._views.get(view_id)
        if view is None:
            return {"error": f"View {view_id} not found"}

        factor = max(0.0, factor)
        view["explosion_factor"] = factor
        logger.debug("set_explosion_factor: view %s -> %.2f", view_id, factor)
        return self._view_to_dict(view)

    def get_bill_of_materials(self, view_id: str) -> List[Dict[str, Any]]:
        """Return a bill-of-materials for the view."""
        view = self._views.get(view_id)
        if view is None:
            logger.warning("get_bill_of_materials: view %s not found", view_id)
            return []

        bom: List[Dict[str, Any]] = []
        total_weight = 0.0
        for idx, part in enumerate(view["parts"], start=1):
            entry = {
                "item": idx,
                "part_number": part.part_number,
                "name": part.name,
                "material": part.material,
                "quantity": part.quantity,
                "unit_weight_kg": part.weight_kg,
                "total_weight_kg": round(part.weight_kg * part.quantity, 4),
            }
            total_weight += entry["total_weight_kg"]
            bom.append(entry)

        bom.append({
            "item": "TOTAL",
            "part_number": "",
            "name": f"{len(view['parts'])} unique parts",
            "material": "",
            "quantity": sum(p.quantity for p in view["parts"]),
            "unit_weight_kg": "",
            "total_weight_kg": round(total_weight, 4),
        })
        logger.debug("get_bill_of_materials: %d line items for view %s", len(bom), view_id)
        return bom

    def render_ascii(self, view_id: str) -> str:
        """Render a simple ASCII representation of the exploded view."""
        view = self._views.get(view_id)
        if view is None:
            return f"[Error] View {view_id} not found."

        factor = view["explosion_factor"]
        lines = [f"EXPLODED VIEW: {view['name']}  (factor={factor})", ""]
        for i, part in enumerate(view["parts"]):
            ep = part.exploded_position(factor)
            indent = "  " * i
            connector = "│" if i < len(view["parts"]) - 1 else "└"
            lines.append(f"{indent}{connector}── [{part.part_number}] {part.name}  "
                         f"@ ({ep[0]:.1f}, {ep[1]:.1f}, {ep[2]:.1f})")

        return "\n".join(lines)

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _make_part(spec: Dict[str, Any]) -> Part:
        pos = spec.get("position", (0, 0, 0))
        off = spec.get("offset", (0, 0, 0))
        return Part(
            name=spec.get("name", "Part"),
            part_number=spec.get("part_number", ""),
            material=spec.get("material", ""),
            quantity=int(spec.get("quantity", 1)),
            position=tuple(float(v) for v in pos),  # type: ignore[arg-type]
            offset=tuple(float(v) for v in off),  # type: ignore[arg-type]
            parent=spec.get("parent"),
            weight_kg=float(spec.get("weight_kg", 0)),
            notes=spec.get("notes", ""),
        )

    def _view_to_dict(self, view: Dict[str, Any]) -> Dict[str, Any]:
        factor = view["explosion_factor"]
        return {
            "id": view["id"],
            "name": view["name"],
            "description": view["description"],
            "explosion_factor": factor,
            "parts": [p.to_dict(factor) for p in view["parts"]],
            "total_parts": len(view["parts"]),
        }

    # ── event bus handler ────────────────────────────────────────────────────

    def _on_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("_on_request: expected dict, got %s", type(data).__name__)
            return

        action = data.get("action", "create")
        result: Any

        if action == "create":
            result = self.create_exploded_view(data.get("assembly", {}))
        elif action == "add_part":
            result = self.add_part(data.get("view_id", ""), data.get("part", {}))
        elif action == "set_factor":
            result = self.set_explosion_factor(data.get("view_id", ""), float(data.get("factor", 1.5)))
        elif action == "bom":
            result = self.get_bill_of_materials(data.get("view_id", ""))
        elif action == "render":
            result = self.render_ascii(data.get("view_id", ""))
        else:
            result = {"error": f"Unknown exploded-view action: {action}"}

        if self.event_bus:
            self.event_bus.publish(EXPLODED_VIEW_RESULT, {"action": action, "result": result})
            logger.debug("Published %s for action=%s", EXPLODED_VIEW_RESULT, action)
