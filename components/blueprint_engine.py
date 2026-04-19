"""Generates manufacturing blueprints with dimensions, materials, and tolerances."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.blueprint_engine")

BLUEPRINT_REQUEST = "manufacturing.blueprint.request"
BLUEPRINT_RESULT = "manufacturing.blueprint.result"


class Dimension:
    """A single linear, angular, or radial dimension."""

    def __init__(
        self,
        label: str,
        value: float,
        unit: str = "mm",
        tolerance_plus: float = 0.0,
        tolerance_minus: float = 0.0,
    ) -> None:
        self.label = label
        self.value = value
        self.unit = unit
        self.tolerance_plus = tolerance_plus
        self.tolerance_minus = tolerance_minus

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "tolerance": f"+{self.tolerance_plus}/-{self.tolerance_minus} {self.unit}",
        }


class MaterialSpec:
    """Material specification for a blueprint layer."""

    def __init__(
        self,
        name: str,
        grade: str = "",
        finish: str = "",
        hardness: str = "",
        notes: str = "",
    ) -> None:
        self.name = name
        self.grade = grade
        self.finish = finish
        self.hardness = hardness
        self.notes = notes

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in {
            "name": self.name, "grade": self.grade,
            "finish": self.finish, "hardness": self.hardness,
            "notes": self.notes,
        }.items() if v}


class BlueprintEngine:
    """Creates and manages manufacturing blueprint specifications."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._blueprints: Dict[str, Dict[str, Any]] = {}
        logger.info("BlueprintEngine initialised")

        if event_bus:
            event_bus.subscribe(BLUEPRINT_REQUEST, self._on_request)
            logger.debug("Subscribed to %s", BLUEPRINT_REQUEST)

    # ── public API ───────────────────────────────────────────────────────────

    def create_blueprint(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new blueprint from *spec*.

        *spec* may include: title, description, scale, units, layers (list of
        layer dicts).  Returns the full blueprint dict including generated id.
        """
        bp_id = str(uuid.uuid4())[:8]
        blueprint: Dict[str, Any] = {
            "id": bp_id,
            "title": spec.get("title", "Untitled Blueprint"),
            "description": spec.get("description", ""),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "scale": spec.get("scale", "1:1"),
            "units": spec.get("units", "mm"),
            "dimensions": [],
            "materials": [],
            "layers": [],
            "notes": spec.get("notes", ""),
        }

        for layer_spec in spec.get("layers", []):
            blueprint["layers"].append({
                "name": layer_spec.get("name", "default"),
                "geometry": layer_spec.get("geometry", []),
                "visible": layer_spec.get("visible", True),
            })

        if not blueprint["layers"]:
            blueprint["layers"].append({"name": "default", "geometry": [], "visible": True})

        self._blueprints[bp_id] = blueprint
        logger.info("create_blueprint: id=%s title=%r", bp_id, blueprint["title"])
        return blueprint

    def add_dimension(self, blueprint_id: str, dimension: Dict[str, Any]) -> Dict[str, Any]:
        """Add a ``Dimension`` to an existing blueprint.

        *dimension* keys: label, value, unit, tolerance_plus, tolerance_minus.
        """
        bp = self._blueprints.get(blueprint_id)
        if bp is None:
            logger.warning("add_dimension: blueprint %s not found", blueprint_id)
            return {"error": f"Blueprint {blueprint_id} not found"}

        dim = Dimension(
            label=dimension.get("label", "D"),
            value=float(dimension.get("value", 0)),
            unit=dimension.get("unit", bp["units"]),
            tolerance_plus=float(dimension.get("tolerance_plus", 0)),
            tolerance_minus=float(dimension.get("tolerance_minus", 0)),
        )
        bp["dimensions"].append(dim.to_dict())
        logger.debug("add_dimension: %s to bp %s", dim.label, blueprint_id)
        return dim.to_dict()

    def add_material_spec(self, blueprint_id: str, material: Dict[str, Any]) -> Dict[str, Any]:
        """Attach a ``MaterialSpec`` to an existing blueprint."""
        bp = self._blueprints.get(blueprint_id)
        if bp is None:
            logger.warning("add_material_spec: blueprint %s not found", blueprint_id)
            return {"error": f"Blueprint {blueprint_id} not found"}

        mat = MaterialSpec(
            name=material.get("name", "Unknown"),
            grade=material.get("grade", ""),
            finish=material.get("finish", ""),
            hardness=material.get("hardness", ""),
            notes=material.get("notes", ""),
        )
        bp["materials"].append(mat.to_dict())
        logger.debug("add_material_spec: %s to bp %s", mat.name, blueprint_id)
        return mat.to_dict()

    def export_blueprint(self, blueprint_id: str, fmt: str = "text") -> str:
        """Export the blueprint as a human-readable representation.

        Supported *fmt*: ``text``, ``json``, ``ascii``.
        """
        bp = self._blueprints.get(blueprint_id)
        if bp is None:
            return f"[Error] Blueprint {blueprint_id} not found."

        if fmt == "json":
            import json
            return json.dumps(bp, indent=2)

        if fmt == "ascii":
            return self._ascii_export(bp)

        return self._text_export(bp)

    def get_blueprint(self, blueprint_id: str) -> Optional[Dict[str, Any]]:
        return self._blueprints.get(blueprint_id)

    # ── export helpers ───────────────────────────────────────────────────────

    def _text_export(self, bp: Dict[str, Any]) -> str:
        lines = [
            f"BLUEPRINT: {bp['title']}  (id: {bp['id']})",
            f"Description: {bp['description']}",
            f"Scale: {bp['scale']}   Units: {bp['units']}",
            f"Created: {bp['created_at']}",
            "",
            "── Dimensions ──",
        ]
        for d in bp["dimensions"]:
            lines.append(f"  {d['label']}: {d['value']} {d.get('unit', '')}  tol {d.get('tolerance', '')}")
        if not bp["dimensions"]:
            lines.append("  (none)")

        lines.append("")
        lines.append("── Materials ──")
        for m in bp["materials"]:
            lines.append(f"  {m['name']}  grade={m.get('grade', '-')}  finish={m.get('finish', '-')}")
        if not bp["materials"]:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"── Layers ({len(bp['layers'])}) ──")
        for layer in bp["layers"]:
            vis = "visible" if layer["visible"] else "hidden"
            lines.append(f"  [{vis}] {layer['name']}  ({len(layer['geometry'])} geometry items)")

        if bp.get("notes"):
            lines.extend(["", f"Notes: {bp['notes']}"])
        return "\n".join(lines)

    def _ascii_export(self, bp: Dict[str, Any]) -> str:
        width = 60
        border = "+" + "-" * (width - 2) + "+"
        title_line = f"| {bp['title'].center(width - 4)} |"
        scale_line = f"| Scale: {bp['scale']}  Units: {bp['units']}".ljust(width - 1) + "|"
        lines = [border, title_line, border, scale_line]
        for d in bp["dimensions"]:
            dl = f"| DIM {d['label']}: {d['value']} {d.get('tolerance', '')}".ljust(width - 1) + "|"
            lines.append(dl)
        for m in bp["materials"]:
            ml = f"| MAT {m['name']} [{m.get('grade', '')}]".ljust(width - 1) + "|"
            lines.append(ml)
        lines.append(border)
        return "\n".join(lines)

    # ── event bus handler ────────────────────────────────────────────────────

    def _on_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("_on_request: expected dict, got %s", type(data).__name__)
            return

        action = data.get("action", "create")
        result: Any

        if action == "create":
            result = self.create_blueprint(data.get("spec", {}))
        elif action == "add_dimension":
            result = self.add_dimension(data.get("blueprint_id", ""), data.get("dimension", {}))
        elif action == "add_material":
            result = self.add_material_spec(data.get("blueprint_id", ""), data.get("material", {}))
        elif action == "export":
            result = self.export_blueprint(data.get("blueprint_id", ""), data.get("format", "text"))
        else:
            result = {"error": f"Unknown blueprint action: {action}"}

        if self.event_bus:
            self.event_bus.publish(BLUEPRINT_RESULT, {"action": action, "result": result})
            logger.debug("Published %s for action=%s", BLUEPRINT_RESULT, action)
