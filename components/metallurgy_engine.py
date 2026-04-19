"""Materials science analysis — alloy composition, heat treatment, hardness."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kingdom_ai.metallurgy_engine")

METALLURGY_REQUEST = "metallurgy.analyze.request"
METALLURGY_RESULT = "metallurgy.analyze.result"


def _seed_alloy_db() -> Dict[str, Dict[str, Any]]:
    """Pre-loaded database of common alloys and their properties."""
    return {
        "1018 steel": {
            "category": "carbon steel",
            "composition": {"Fe": 98.8, "C": 0.18, "Mn": 0.75, "P": 0.04, "S": 0.05},
            "tensile_strength_mpa": 440, "yield_strength_mpa": 370,
            "hardness_hrc": 15, "density_gcc": 7.87, "melting_range_c": (1450, 1510),
            "heat_treatments": ["annealing", "normalizing", "case_hardening"],
        },
        "4140 steel": {
            "category": "alloy steel",
            "composition": {"Fe": 96.8, "C": 0.40, "Cr": 0.95, "Mn": 0.88, "Mo": 0.20, "Si": 0.25},
            "tensile_strength_mpa": 655, "yield_strength_mpa": 415,
            "hardness_hrc": 28, "density_gcc": 7.85, "melting_range_c": (1416, 1460),
            "heat_treatments": ["quench_and_temper", "normalizing", "annealing"],
        },
        "304 stainless": {
            "category": "austenitic stainless steel",
            "composition": {"Fe": 67.0, "Cr": 18.5, "Ni": 9.25, "Mn": 2.0, "C": 0.08},
            "tensile_strength_mpa": 515, "yield_strength_mpa": 205,
            "hardness_hrc": 20, "density_gcc": 8.0, "melting_range_c": (1400, 1450),
            "heat_treatments": ["solution_annealing"],
        },
        "316 stainless": {
            "category": "austenitic stainless steel",
            "composition": {"Fe": 63.0, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 2.0, "C": 0.08},
            "tensile_strength_mpa": 515, "yield_strength_mpa": 205,
            "hardness_hrc": 20, "density_gcc": 8.0, "melting_range_c": (1390, 1440),
            "heat_treatments": ["solution_annealing"],
        },
        "6061 aluminum": {
            "category": "aluminum alloy",
            "composition": {"Al": 97.3, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2},
            "tensile_strength_mpa": 310, "yield_strength_mpa": 276,
            "hardness_hrc": None, "hardness_hb": 95, "density_gcc": 2.7,
            "melting_range_c": (582, 652),
            "heat_treatments": ["T6_precipitation_hardening", "annealing"],
        },
        "7075 aluminum": {
            "category": "aluminum alloy",
            "composition": {"Al": 89.7, "Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Cr": 0.23},
            "tensile_strength_mpa": 572, "yield_strength_mpa": 503,
            "hardness_hrc": None, "hardness_hb": 150, "density_gcc": 2.81,
            "melting_range_c": (477, 635),
            "heat_treatments": ["T6_precipitation_hardening", "annealing"],
        },
        "ti-6al-4v": {
            "category": "titanium alloy",
            "composition": {"Ti": 89.6, "Al": 6.0, "V": 4.0, "Fe": 0.25, "O": 0.13},
            "tensile_strength_mpa": 950, "yield_strength_mpa": 880,
            "hardness_hrc": 36, "density_gcc": 4.43, "melting_range_c": (1604, 1660),
            "heat_treatments": ["solution_treat_and_age", "stress_relief", "annealing"],
        },
        "c11000 copper": {
            "category": "copper",
            "composition": {"Cu": 99.9, "O": 0.04},
            "tensile_strength_mpa": 220, "yield_strength_mpa": 69,
            "hardness_hrc": None, "hardness_hb": 45, "density_gcc": 8.94,
            "melting_range_c": (1065, 1083),
            "heat_treatments": ["annealing"],
        },
        "c36000 brass": {
            "category": "brass",
            "composition": {"Cu": 61.5, "Zn": 35.5, "Pb": 3.0},
            "tensile_strength_mpa": 340, "yield_strength_mpa": 125,
            "hardness_hrc": None, "hardness_hb": 78, "density_gcc": 8.5,
            "melting_range_c": (885, 900),
            "heat_treatments": ["stress_relief_annealing"],
        },
        "inconel 718": {
            "category": "nickel superalloy",
            "composition": {"Ni": 52.5, "Cr": 19.0, "Fe": 18.5, "Nb": 5.1, "Mo": 3.0, "Ti": 0.9, "Al": 0.5},
            "tensile_strength_mpa": 1240, "yield_strength_mpa": 1036,
            "hardness_hrc": 44, "density_gcc": 8.19, "melting_range_c": (1260, 1336),
            "heat_treatments": ["solution_treat_and_age", "stress_relief"],
        },
    }


# Galvanic series index (lower = more anodic/active)
_GALVANIC_INDEX: Dict[str, int] = {
    "magnesium": 1, "zinc": 2, "aluminum": 3, "carbon steel": 4,
    "alloy steel": 4, "cast iron": 5, "stainless steel": 6,
    "austenitic stainless steel": 6, "nickel superalloy": 7,
    "copper": 8, "brass": 8, "bronze": 8, "titanium alloy": 9,
    "gold": 10, "platinum": 10,
}


class MetallurgyEngine:
    """Alloy database, heat-treatment advisor, compatibility checker, stress calculator."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._alloys = _seed_alloy_db()
        logger.info("MetallurgyEngine initialised with %d alloys", len(self._alloys))

        if event_bus:
            event_bus.subscribe(METALLURGY_REQUEST, self._on_request)
            logger.debug("Subscribed to %s", METALLURGY_REQUEST)

    # ── public API ───────────────────────────────────────────────────────────

    def analyze_alloy(self, composition: Dict[str, float]) -> Dict[str, Any]:
        """Predict properties from a percentage composition dict like ``{"Fe": 96, "C": 0.4, ...}``."""
        best_match: Optional[str] = None
        best_score = -1.0

        for name, info in self._alloys.items():
            score = self._composition_similarity(composition, info["composition"])
            if score > best_score:
                best_score = score
                best_match = name

        if best_match is None or best_score < 0.3:
            estimated = self._estimate_from_composition(composition)
            logger.debug("analyze_alloy: no close match (best=%.2f), returning estimate", best_score)
            return {"match": None, "match_score": round(best_score, 3), "estimated_properties": estimated}

        alloy = self._alloys[best_match]
        logger.debug("analyze_alloy: best match=%s score=%.3f", best_match, best_score)
        return {
            "match": best_match,
            "match_score": round(best_score, 3),
            "category": alloy["category"],
            "tensile_strength_mpa": alloy["tensile_strength_mpa"],
            "yield_strength_mpa": alloy["yield_strength_mpa"],
            "hardness_hrc": alloy.get("hardness_hrc"),
            "hardness_hb": alloy.get("hardness_hb"),
            "density_gcc": alloy["density_gcc"],
            "melting_range_c": alloy["melting_range_c"],
            "available_heat_treatments": alloy["heat_treatments"],
        }

    def recommend_heat_treatment(self, alloy_name: str, desired_hardness: float) -> Dict[str, Any]:
        """Recommend a heat treatment plan for *alloy_name* targeting *desired_hardness* HRC."""
        key = alloy_name.strip().lower()
        alloy = self._alloys.get(key)
        if alloy is None:
            for k, v in self._alloys.items():
                if alloy_name.lower() in k:
                    alloy = v
                    key = k
                    break

        if alloy is None:
            logger.warning("recommend_heat_treatment: alloy %r not found", alloy_name)
            return {"error": f"Alloy '{alloy_name}' not in database", "available": list(self._alloys.keys())}

        current = alloy.get("hardness_hrc") or 0
        treatments = alloy["heat_treatments"]
        plan: Dict[str, Any] = {
            "alloy": key,
            "current_hardness_hrc": current,
            "desired_hardness_hrc": desired_hardness,
            "steps": [],
        }

        if desired_hardness <= current:
            plan["steps"].append({
                "treatment": "annealing" if "annealing" in treatments else treatments[0],
                "temperature_c": alloy["melting_range_c"][0] * 0.55,
                "hold_time_min": 60,
                "cooling": "furnace cool",
                "expected_hardness_hrc": max(desired_hardness, current * 0.5),
            })
        else:
            if "quench_and_temper" in treatments:
                austenitize_temp = alloy["melting_range_c"][0] * 0.58
                temper_temp = 200 + (alloy["melting_range_c"][0] * 0.4 - 200) * (1 - desired_hardness / 65)
                plan["steps"].append({
                    "treatment": "austenitize_and_quench",
                    "temperature_c": round(austenitize_temp),
                    "hold_time_min": 45,
                    "cooling": "oil quench",
                    "expected_hardness_hrc": min(desired_hardness + 8, 65),
                })
                plan["steps"].append({
                    "treatment": "temper",
                    "temperature_c": round(temper_temp),
                    "hold_time_min": 120,
                    "cooling": "air cool",
                    "expected_hardness_hrc": round(desired_hardness, 1),
                })
            elif "T6_precipitation_hardening" in treatments:
                plan["steps"].append({
                    "treatment": "solution_heat_treat",
                    "temperature_c": round(alloy["melting_range_c"][0] * 0.85),
                    "hold_time_min": 60,
                    "cooling": "water quench",
                })
                plan["steps"].append({
                    "treatment": "artificial_aging",
                    "temperature_c": 175,
                    "hold_time_min": 480,
                    "cooling": "air cool",
                    "expected_hardness_hb": 150,
                })
            elif "solution_treat_and_age" in treatments:
                plan["steps"].append({
                    "treatment": "solution_treat",
                    "temperature_c": round(alloy["melting_range_c"][0] * 0.6),
                    "hold_time_min": 60,
                    "cooling": "water quench",
                })
                plan["steps"].append({
                    "treatment": "age_harden",
                    "temperature_c": 720,
                    "hold_time_min": 480,
                    "cooling": "air cool",
                    "expected_hardness_hrc": round(desired_hardness, 1),
                })
            else:
                plan["steps"].append({
                    "treatment": treatments[0] if treatments else "unknown",
                    "notes": "Consult materials engineer for specifics.",
                })

        logger.info("recommend_heat_treatment: %s -> %d HRC, %d steps",
                     key, desired_hardness, len(plan["steps"]))
        return plan

    def check_compatibility(self, material_a: str, material_b: str) -> Dict[str, Any]:
        """Check galvanic and thermal compatibility between two materials."""
        cat_a = self._category_for(material_a)
        cat_b = self._category_for(material_b)

        idx_a = _GALVANIC_INDEX.get(cat_a, 5)
        idx_b = _GALVANIC_INDEX.get(cat_b, 5)
        galvanic_diff = abs(idx_a - idx_b)

        if galvanic_diff <= 1:
            galvanic_risk = "low"
        elif galvanic_diff <= 3:
            galvanic_risk = "moderate"
        else:
            galvanic_risk = "high"

        melt_a = self._melting_range(material_a)
        melt_b = self._melting_range(material_b)
        thermal_compat = "compatible"
        if melt_a and melt_b:
            if abs(melt_a[0] - melt_b[0]) > 600:
                thermal_compat = "significant difference — joining may be difficult"

        report = {
            "material_a": material_a,
            "material_b": material_b,
            "category_a": cat_a,
            "category_b": cat_b,
            "galvanic_risk": galvanic_risk,
            "galvanic_index_diff": galvanic_diff,
            "thermal_compatibility": thermal_compat,
            "recommendation": "Use insulating barrier" if galvanic_risk == "high" else "Generally acceptable",
        }
        logger.debug("check_compatibility: %s vs %s -> galvanic=%s", material_a, material_b, galvanic_risk)
        return report

    def calculate_stress(self, material: str, load_n: float, area_mm2: float) -> Dict[str, Any]:
        """Basic stress analysis: σ = F/A, compared to yield/tensile of material."""
        if area_mm2 <= 0:
            return {"error": "Area must be positive"}

        stress_mpa = load_n / area_mm2
        key = material.strip().lower()
        alloy = self._alloys.get(key)
        if alloy is None:
            for k in self._alloys:
                if material.lower() in k:
                    alloy = self._alloys[k]
                    break

        result: Dict[str, Any] = {
            "material": material,
            "applied_load_n": load_n,
            "cross_section_area_mm2": area_mm2,
            "stress_mpa": round(stress_mpa, 3),
        }

        if alloy:
            ys = alloy["yield_strength_mpa"]
            ts = alloy["tensile_strength_mpa"]
            result["yield_strength_mpa"] = ys
            result["tensile_strength_mpa"] = ts
            result["safety_factor_yield"] = round(ys / stress_mpa, 2) if stress_mpa > 0 else float("inf")
            result["safety_factor_ultimate"] = round(ts / stress_mpa, 2) if stress_mpa > 0 else float("inf")
            if stress_mpa > ts:
                result["verdict"] = "FAILURE — stress exceeds ultimate tensile strength"
            elif stress_mpa > ys:
                result["verdict"] = "WARNING — stress exceeds yield (plastic deformation)"
            else:
                result["verdict"] = "OK — within elastic region"
        else:
            result["note"] = f"Material '{material}' not in database; showing raw stress only"

        logger.debug("calculate_stress: %s @ %.1f MPa", material, stress_mpa)
        return result

    def list_alloys(self) -> List[str]:
        return sorted(self._alloys.keys())

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _composition_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
        all_elements = set(a) | set(b)
        if not all_elements:
            return 0.0
        diffs = sum(abs(a.get(e, 0) - b.get(e, 0)) for e in all_elements)
        return max(0.0, 1.0 - diffs / 200.0)

    def _category_for(self, material: str) -> str:
        key = material.strip().lower()
        alloy = self._alloys.get(key)
        if alloy:
            return alloy["category"]
        for k, v in self._alloys.items():
            if material.lower() in k:
                return v["category"]
        return material.lower()

    def _melting_range(self, material: str) -> Optional[Tuple[int, int]]:
        key = material.strip().lower()
        alloy = self._alloys.get(key)
        if alloy:
            return alloy["melting_range_c"]
        for k, v in self._alloys.items():
            if material.lower() in k:
                return v["melting_range_c"]
        return None

    def _estimate_from_composition(self, composition: Dict[str, float]) -> Dict[str, Any]:
        fe = composition.get("Fe", 0)
        al = composition.get("Al", 0)
        ti = composition.get("Ti", 0)
        cu = composition.get("Cu", 0)
        density = 7.87 * (fe / 100) + 2.7 * (al / 100) + 4.43 * (ti / 100) + 8.94 * (cu / 100)
        remaining = 100 - fe - al - ti - cu
        if remaining > 0:
            density += 7.0 * (remaining / 100)
        return {"estimated_density_gcc": round(density, 2), "note": "Rough rule-of-mixtures estimate"}

    # ── event bus handler ────────────────────────────────────────────────────

    def _on_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("_on_request: expected dict, got %s", type(data).__name__)
            return

        action = data.get("action", "analyze")
        result: Any

        if action == "analyze":
            result = self.analyze_alloy(data.get("composition", {}))
        elif action == "heat_treatment":
            result = self.recommend_heat_treatment(
                data.get("alloy", ""), float(data.get("desired_hardness", 40)))
        elif action == "compatibility":
            result = self.check_compatibility(data.get("material_a", ""), data.get("material_b", ""))
        elif action == "stress":
            result = self.calculate_stress(
                data.get("material", ""), float(data.get("load_n", 0)), float(data.get("area_mm2", 1)))
        elif action == "list":
            result = self.list_alloys()
        else:
            result = {"error": f"Unknown metallurgy action: {action}"}

        if self.event_bus:
            self.event_bus.publish(METALLURGY_RESULT, {"action": action, "result": result})
            logger.debug("Published %s for action=%s", METALLURGY_RESULT, action)
