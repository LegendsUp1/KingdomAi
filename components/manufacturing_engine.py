"""Manufacturing process simulation — CNC, 3D printing, injection molding, casting."""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.manufacturing_engine")

MANUFACTURING_SIMULATE_REQUEST = "manufacturing.simulate.request"
MANUFACTURING_SIMULATE_RESULT = "manufacturing.simulate.result"

# ── Process knowledge base ───────────────────────────────────────────────────

_PROCESS_PROFILES: Dict[str, Dict[str, Any]] = {
    "cnc_milling": {
        "display_name": "CNC Milling",
        "setup_cost_usd": 150.0,
        "hourly_rate_usd": 75.0,
        "material_waste_pct": 15.0,
        "tolerance_mm": 0.025,
        "min_quantity": 1,
        "complexity_factors": {"low": 1.0, "medium": 1.6, "high": 2.5, "very_high": 4.0},
        "compatible_materials": ["aluminum", "steel", "titanium", "brass", "copper", "plastic"],
    },
    "cnc_turning": {
        "display_name": "CNC Turning",
        "setup_cost_usd": 120.0,
        "hourly_rate_usd": 65.0,
        "material_waste_pct": 12.0,
        "tolerance_mm": 0.013,
        "min_quantity": 1,
        "complexity_factors": {"low": 1.0, "medium": 1.4, "high": 2.0, "very_high": 3.0},
        "compatible_materials": ["aluminum", "steel", "titanium", "brass", "copper", "plastic"],
    },
    "3d_printing_fdm": {
        "display_name": "FDM 3D Printing",
        "setup_cost_usd": 10.0,
        "hourly_rate_usd": 15.0,
        "material_waste_pct": 5.0,
        "tolerance_mm": 0.3,
        "min_quantity": 1,
        "complexity_factors": {"low": 1.0, "medium": 1.2, "high": 1.5, "very_high": 2.0},
        "compatible_materials": ["pla", "abs", "petg", "nylon", "tpu"],
    },
    "3d_printing_sla": {
        "display_name": "SLA 3D Printing",
        "setup_cost_usd": 25.0,
        "hourly_rate_usd": 30.0,
        "material_waste_pct": 8.0,
        "tolerance_mm": 0.05,
        "min_quantity": 1,
        "complexity_factors": {"low": 1.0, "medium": 1.15, "high": 1.4, "very_high": 1.8},
        "compatible_materials": ["standard_resin", "tough_resin", "flexible_resin", "castable_resin"],
    },
    "3d_printing_sls": {
        "display_name": "SLS 3D Printing",
        "setup_cost_usd": 50.0,
        "hourly_rate_usd": 45.0,
        "material_waste_pct": 10.0,
        "tolerance_mm": 0.1,
        "min_quantity": 1,
        "complexity_factors": {"low": 1.0, "medium": 1.1, "high": 1.3, "very_high": 1.6},
        "compatible_materials": ["nylon", "nylon_gf", "tpu", "alumide"],
    },
    "injection_molding": {
        "display_name": "Injection Molding",
        "setup_cost_usd": 5000.0,
        "hourly_rate_usd": 40.0,
        "material_waste_pct": 3.0,
        "tolerance_mm": 0.1,
        "min_quantity": 100,
        "complexity_factors": {"low": 1.0, "medium": 1.5, "high": 2.5, "very_high": 4.0},
        "compatible_materials": ["abs", "polypropylene", "nylon", "polycarbonate", "peek"],
    },
    "sand_casting": {
        "display_name": "Sand Casting",
        "setup_cost_usd": 300.0,
        "hourly_rate_usd": 55.0,
        "material_waste_pct": 20.0,
        "tolerance_mm": 1.5,
        "min_quantity": 1,
        "complexity_factors": {"low": 1.0, "medium": 1.4, "high": 2.0, "very_high": 3.0},
        "compatible_materials": ["aluminum", "cast_iron", "steel", "bronze", "brass"],
    },
    "investment_casting": {
        "display_name": "Investment Casting",
        "setup_cost_usd": 1500.0,
        "hourly_rate_usd": 80.0,
        "material_waste_pct": 5.0,
        "tolerance_mm": 0.25,
        "min_quantity": 10,
        "complexity_factors": {"low": 1.0, "medium": 1.3, "high": 1.8, "very_high": 2.5},
        "compatible_materials": ["steel", "stainless_steel", "aluminum", "titanium", "inconel"],
    },
    "sheet_metal": {
        "display_name": "Sheet Metal Fabrication",
        "setup_cost_usd": 200.0,
        "hourly_rate_usd": 50.0,
        "material_waste_pct": 10.0,
        "tolerance_mm": 0.5,
        "min_quantity": 1,
        "complexity_factors": {"low": 1.0, "medium": 1.3, "high": 1.8, "very_high": 2.5},
        "compatible_materials": ["aluminum", "steel", "stainless_steel", "copper", "brass"],
    },
}

_MATERIAL_COST_PER_KG: Dict[str, float] = {
    "aluminum": 8.0, "steel": 3.0, "stainless_steel": 12.0,
    "titanium": 60.0, "brass": 15.0, "copper": 20.0,
    "cast_iron": 2.5, "bronze": 18.0, "inconel": 90.0,
    "plastic": 5.0, "pla": 25.0, "abs": 30.0, "petg": 35.0,
    "nylon": 40.0, "tpu": 50.0, "polypropylene": 4.0,
    "polycarbonate": 10.0, "peek": 300.0,
    "standard_resin": 50.0, "tough_resin": 70.0,
    "flexible_resin": 80.0, "castable_resin": 90.0,
    "nylon_gf": 55.0, "alumide": 65.0,
}


class ManufacturingEngine:
    """Simulates manufacturing processes and generates toolpath data."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._processes = dict(_PROCESS_PROFILES)
        self._material_costs = dict(_MATERIAL_COST_PER_KG)
        logger.info("ManufacturingEngine initialised with %d process types", len(self._processes))

        if event_bus:
            event_bus.subscribe(MANUFACTURING_SIMULATE_REQUEST, self._on_request)
            logger.debug("Subscribed to %s", MANUFACTURING_SIMULATE_REQUEST)

    # ── public API ───────────────────────────────────────────────────────────

    def simulate_process(self, process_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate a manufacturing process and return predicted outcomes.

        *parameters* keys: material, part_volume_cm3, part_weight_kg,
        complexity ("low"/"medium"/"high"/"very_high"), quantity, surface_finish.
        """
        profile = self._processes.get(process_type)
        if profile is None:
            return {"error": f"Unknown process: {process_type}", "available": list(self._processes.keys())}

        material = parameters.get("material", "aluminum")
        complexity = parameters.get("complexity", "medium")
        quantity = max(1, int(parameters.get("quantity", 1)))
        volume_cm3 = float(parameters.get("part_volume_cm3", 100))

        cf = profile["complexity_factors"].get(complexity, 1.5)
        base_time_hr = (volume_cm3 / 50.0) * cf
        setup_hr = 0.5 * cf

        total_time_hr = setup_hr + base_time_hr * quantity
        waste_kg = (volume_cm3 * 0.001) * (profile["material_waste_pct"] / 100) * quantity

        mat_cost_per_kg = self._material_costs.get(material, 10.0)
        weight_kg = float(parameters.get("part_weight_kg", volume_cm3 * 0.0027))
        material_cost = (weight_kg + waste_kg / quantity) * mat_cost_per_kg * quantity
        machine_cost = total_time_hr * profile["hourly_rate_usd"]
        total_cost = profile["setup_cost_usd"] + material_cost + machine_cost

        compatible = material in profile["compatible_materials"]

        result = {
            "process": profile["display_name"],
            "process_type": process_type,
            "material": material,
            "material_compatible": compatible,
            "complexity": complexity,
            "quantity": quantity,
            "cycle_time_hr": round(base_time_hr, 3),
            "total_time_hr": round(total_time_hr, 3),
            "tolerance_mm": profile["tolerance_mm"],
            "waste_kg": round(waste_kg, 3),
            "cost_breakdown": {
                "setup_usd": profile["setup_cost_usd"],
                "material_usd": round(material_cost, 2),
                "machine_usd": round(machine_cost, 2),
                "total_usd": round(total_cost, 2),
            },
        }
        if not compatible:
            result["warning"] = (f"{material} is not a standard material for {profile['display_name']}. "
                                 f"Compatible: {', '.join(profile['compatible_materials'])}")

        logger.info("simulate_process: %s/%s qty=%d -> $%.2f", process_type, material, quantity, total_cost)
        return result

    def estimate_cost(
        self, process_type: str, material: str, quantity: int, volume_cm3: float = 100.0
    ) -> Dict[str, Any]:
        """Quick cost estimate without full simulation detail."""
        return self.simulate_process(process_type, {
            "material": material, "quantity": quantity, "part_volume_cm3": volume_cm3,
        }).get("cost_breakdown", {"error": "simulation failed"})

    def generate_gcode(self, toolpath_spec: Dict[str, Any]) -> str:
        """Generate simple G-code from a toolpath specification.

        *toolpath_spec* keys: tool_diameter_mm, spindle_rpm, feed_rate_mmpm,
        depth_of_cut_mm, passes (list of {"x","y","z"} waypoints), coolant.
        """
        tool_d = toolpath_spec.get("tool_diameter_mm", 6.0)
        rpm = toolpath_spec.get("spindle_rpm", 12000)
        feed = toolpath_spec.get("feed_rate_mmpm", 800)
        doc = toolpath_spec.get("depth_of_cut_mm", 1.0)
        coolant = toolpath_spec.get("coolant", True)
        passes = toolpath_spec.get("passes", [])

        lines: List[str] = [
            f"(Generated by Kingdom AI ManufacturingEngine)",
            f"(Tool: D{tool_d}mm  RPM: {rpm}  Feed: {feed} mm/min)",
            "G90 G21",
            "G28 G91 Z0",
            "G90",
            f"S{rpm} M3",
        ]
        if coolant:
            lines.append("M8")

        lines.append(f"G0 Z5.0")

        current_z = 0.0
        for p_idx, waypoint in enumerate(passes):
            x = waypoint.get("x", 0)
            y = waypoint.get("y", 0)
            z = waypoint.get("z", -doc)
            lines.append(f"G0 X{x} Y{y}")
            lines.append(f"G1 Z{z} F{feed // 2}")
            lines.append(f"G1 X{x} Y{y} F{feed}")
            current_z = z

        lines.append("G0 Z5.0")
        lines.append("M5")
        if coolant:
            lines.append("M9")
        lines.append("G28 G91 Z0")
        lines.append("M30")

        gcode = "\n".join(lines)
        logger.debug("generate_gcode: %d lines, %d waypoints", len(lines), len(passes))
        return gcode

    def calculate_cycle_time(self, process_type: str, complexity: str = "medium", volume_cm3: float = 100.0) -> Dict[str, Any]:
        """Estimate cycle time for a single part."""
        profile = self._processes.get(process_type)
        if profile is None:
            return {"error": f"Unknown process: {process_type}"}

        cf = profile["complexity_factors"].get(complexity, 1.5)
        cycle_hr = (volume_cm3 / 50.0) * cf
        setup_hr = 0.5 * cf

        return {
            "process": profile["display_name"],
            "complexity": complexity,
            "volume_cm3": volume_cm3,
            "setup_time_hr": round(setup_hr, 3),
            "cycle_time_hr": round(cycle_hr, 3),
            "cycle_time_min": round(cycle_hr * 60, 1),
            "parts_per_8hr_shift": max(1, int(8.0 / cycle_hr)) if cycle_hr > 0 else 0,
        }

    def list_processes(self) -> List[Dict[str, Any]]:
        return [{"key": k, "name": v["display_name"], "tolerance_mm": v["tolerance_mm"],
                 "min_quantity": v["min_quantity"]} for k, v in self._processes.items()]

    # ── event bus handler ────────────────────────────────────────────────────

    def _on_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("_on_request: expected dict, got %s", type(data).__name__)
            return

        action = data.get("action", "simulate")
        result: Any

        if action == "simulate":
            result = self.simulate_process(data.get("process_type", ""), data.get("parameters", {}))
        elif action == "cost":
            result = self.estimate_cost(
                data.get("process_type", ""), data.get("material", "aluminum"),
                int(data.get("quantity", 1)), float(data.get("volume_cm3", 100)))
        elif action == "gcode":
            result = self.generate_gcode(data.get("toolpath", {}))
        elif action == "cycle_time":
            result = self.calculate_cycle_time(
                data.get("process_type", ""), data.get("complexity", "medium"),
                float(data.get("volume_cm3", 100)))
        elif action == "list":
            result = self.list_processes()
        else:
            result = {"error": f"Unknown manufacturing action: {action}"}

        if self.event_bus:
            self.event_bus.publish(MANUFACTURING_SIMULATE_RESULT, {"action": action, "result": result})
            logger.debug("Published %s for action=%s", MANUFACTURING_SIMULATE_RESULT, action)
