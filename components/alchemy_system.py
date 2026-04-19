"""Creative transmutation / transformation system for Kingdom AI."""

from __future__ import annotations

import itertools
import logging
import math
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("kingdom_ai.alchemy_system")

ALCHEMY_TRANSMUTE_REQUEST = "alchemy.transmute.request"
ALCHEMY_TRANSMUTE_RESULT = "alchemy.transmute.result"

# ── Elemental data ───────────────────────────────────────────────────────────
# Simplified periodic-table-inspired element map with "alchemical energy" values.
# Energy increases roughly with atomic number and rarity.

_ELEMENTS: Dict[str, Dict[str, Any]] = {
    "hydrogen":  {"symbol": "H",  "atomic_number": 1,  "energy": 1,   "class": "nonmetal",       "phase": "gas"},
    "carbon":    {"symbol": "C",  "atomic_number": 6,  "energy": 6,   "class": "nonmetal",       "phase": "solid"},
    "nitrogen":  {"symbol": "N",  "atomic_number": 7,  "energy": 7,   "class": "nonmetal",       "phase": "gas"},
    "oxygen":    {"symbol": "O",  "atomic_number": 8,  "energy": 8,   "class": "nonmetal",       "phase": "gas"},
    "sodium":    {"symbol": "Na", "atomic_number": 11, "energy": 12,  "class": "alkali_metal",   "phase": "solid"},
    "aluminum":  {"symbol": "Al", "atomic_number": 13, "energy": 15,  "class": "metal",          "phase": "solid"},
    "silicon":   {"symbol": "Si", "atomic_number": 14, "energy": 16,  "class": "metalloid",      "phase": "solid"},
    "iron":      {"symbol": "Fe", "atomic_number": 26, "energy": 30,  "class": "transition_metal", "phase": "solid"},
    "copper":    {"symbol": "Cu", "atomic_number": 29, "energy": 35,  "class": "transition_metal", "phase": "solid"},
    "zinc":      {"symbol": "Zn", "atomic_number": 30, "energy": 36,  "class": "transition_metal", "phase": "solid"},
    "silver":    {"symbol": "Ag", "atomic_number": 47, "energy": 55,  "class": "transition_metal", "phase": "solid"},
    "tin":       {"symbol": "Sn", "atomic_number": 50, "energy": 58,  "class": "metal",          "phase": "solid"},
    "tungsten":  {"symbol": "W",  "atomic_number": 74, "energy": 80,  "class": "transition_metal", "phase": "solid"},
    "platinum":  {"symbol": "Pt", "atomic_number": 78, "energy": 90,  "class": "transition_metal", "phase": "solid"},
    "gold":      {"symbol": "Au", "atomic_number": 79, "energy": 95,  "class": "transition_metal", "phase": "solid"},
    "mercury":   {"symbol": "Hg", "atomic_number": 80, "energy": 85,  "class": "transition_metal", "phase": "liquid"},
    "lead":      {"symbol": "Pb", "atomic_number": 82, "energy": 60,  "class": "metal",          "phase": "solid"},
    "uranium":   {"symbol": "U",  "atomic_number": 92, "energy": 150, "class": "actinide",       "phase": "solid"},
}

# Transformation rules: (input, output) -> special cost modifier (1.0 = normal).
_TRANSFORM_RULES: Dict[Tuple[str, str], float] = {
    ("lead", "gold"):     3.0,
    ("iron", "gold"):     2.5,
    ("copper", "silver"): 1.2,
    ("copper", "gold"):   2.8,
    ("mercury", "gold"):  1.5,
    ("iron", "copper"):   0.8,
    ("carbon", "silicon"): 1.1,
    ("tin", "silver"):    1.4,
    ("aluminum", "iron"): 0.9,
    ("silver", "gold"):   1.3,
}

# Known combination recipes: frozenset of inputs -> product name
_COMBINATION_RECIPES: Dict[frozenset, str] = {
    frozenset(["iron", "carbon"]): "steel",
    frozenset(["copper", "tin"]): "bronze",
    frozenset(["copper", "zinc"]): "brass",
    frozenset(["hydrogen", "oxygen"]): "water",
    frozenset(["sodium", "oxygen"]): "sodium_oxide",
    frozenset(["iron", "oxygen"]): "rust",
    frozenset(["carbon", "oxygen"]): "carbon_dioxide",
    frozenset(["nitrogen", "hydrogen"]): "ammonia",
    frozenset(["silicon", "oxygen"]): "quartz",
    frozenset(["gold", "silver"]): "electrum",
    frozenset(["copper", "gold"]): "rose_gold",
}


class AlchemySystem:
    """Elemental transmutation engine with energy-cost modelling and combination discovery."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._elements = dict(_ELEMENTS)
        self._transform_rules = dict(_TRANSFORM_RULES)
        self._recipes = dict(_COMBINATION_RECIPES)
        self._discovery_log: List[Dict[str, Any]] = []
        logger.info("AlchemySystem initialised with %d elements, %d rules, %d recipes",
                     len(self._elements), len(self._transform_rules), len(self._recipes))

        if event_bus:
            event_bus.subscribe(ALCHEMY_TRANSMUTE_REQUEST, self._on_request)
            logger.debug("Subscribed to %s", ALCHEMY_TRANSMUTE_REQUEST)

    # ── public API ───────────────────────────────────────────────────────────

    def transmute(self, input_element: str, target_element: str) -> Dict[str, Any]:
        """Calculate a transmutation path from *input_element* to *target_element*.

        Returns the path (list of intermediate elements), total energy cost,
        and whether a direct rule exists.
        """
        src = input_element.strip().lower()
        dst = target_element.strip().lower()

        if src not in self._elements:
            return {"error": f"Unknown element: {input_element}", "known": list(self._elements.keys())}
        if dst not in self._elements:
            return {"error": f"Unknown element: {target_element}", "known": list(self._elements.keys())}
        if src == dst:
            return {"path": [src], "energy_cost": 0, "direct_rule": True, "note": "No transmutation needed"}

        direct_key = (src, dst)
        if direct_key in self._transform_rules:
            cost = self._direct_cost(src, dst) * self._transform_rules[direct_key]
            path = [src, dst]
            logger.info("transmute: direct %s -> %s, cost=%.1f", src, dst, cost)
            return {"path": path, "energy_cost": round(cost, 2), "direct_rule": True}

        path, cost = self._find_path(src, dst)
        logger.info("transmute: %s -> %s via %d steps, cost=%.1f", src, dst, len(path), cost)
        return {"path": path, "energy_cost": round(cost, 2), "direct_rule": False}

    def calculate_energy_cost(self, transmutation: Dict[str, Any]) -> Dict[str, Any]:
        """Given a transmutation result dict, return a detailed energy breakdown."""
        path: List[str] = transmutation.get("path", [])
        if len(path) < 2:
            return {"total_energy": 0, "steps": [], "note": "No transformation"}

        steps: List[Dict[str, Any]] = []
        total = 0.0
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            modifier = self._transform_rules.get((a, b), 1.0)
            step_cost = self._direct_cost(a, b) * modifier
            steps.append({
                "from": a, "to": b,
                "base_cost": round(self._direct_cost(a, b), 2),
                "modifier": modifier,
                "step_cost": round(step_cost, 2),
            })
            total += step_cost

        return {"total_energy": round(total, 2), "steps": steps}

    def discover_combinations(self, elements: List[str]) -> List[Dict[str, Any]]:
        """Given a list of elements, return all known products from pairwise combinations."""
        normalised = [e.strip().lower() for e in elements if e.strip().lower() in self._elements]
        discoveries: List[Dict[str, Any]] = []

        for combo in itertools.combinations(set(normalised), 2):
            key = frozenset(combo)
            product = self._recipes.get(key)
            if product:
                cost = self._combination_cost(list(combo))
                entry = {"inputs": sorted(combo), "product": product, "energy_cost": round(cost, 2)}
                discoveries.append(entry)
                self._discovery_log.append(entry)

        if not discoveries:
            possible_products: List[str] = []
            for recipe_key, prod in self._recipes.items():
                if recipe_key & set(normalised):
                    missing = recipe_key - set(normalised)
                    possible_products.append(f"{prod} (need: {', '.join(missing)})")
            return [{"inputs": normalised, "product": None, "hint": possible_products or "no known recipes"}]

        logger.info("discover_combinations: %d products from %d elements", len(discoveries), len(normalised))
        return discoveries

    def list_elements(self) -> List[Dict[str, Any]]:
        return [{"name": k, **v} for k, v in sorted(self._elements.items(), key=lambda x: x[1]["atomic_number"])]

    def get_discovery_log(self) -> List[Dict[str, Any]]:
        return list(self._discovery_log)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _direct_cost(self, a: str, b: str) -> float:
        e_a = self._elements[a]["energy"]
        e_b = self._elements[b]["energy"]
        return abs(e_b - e_a) + math.log1p(e_a + e_b)

    def _combination_cost(self, elements: List[str]) -> float:
        return sum(self._elements[e]["energy"] for e in elements) * 0.5

    def _find_path(self, src: str, dst: str) -> Tuple[List[str], float]:
        """BFS over known transform rules to find a multi-hop path."""
        from collections import deque

        adjacency: Dict[str, List[str]] = {}
        for (a, b) in self._transform_rules:
            adjacency.setdefault(a, []).append(b)

        visited: Set[str] = {src}
        queue: deque[Tuple[List[str], float]] = deque([([src], 0.0)])

        while queue:
            path, cost = queue.popleft()
            current = path[-1]
            if current == dst:
                return path, cost

            for neighbour in adjacency.get(current, []):
                if neighbour not in visited:
                    visited.add(neighbour)
                    step_cost = self._direct_cost(current, neighbour) * self._transform_rules.get((current, neighbour), 1.0)
                    queue.append((path + [neighbour], cost + step_cost))

        fallback_cost = self._direct_cost(src, dst) * 5.0
        return [src, dst], fallback_cost

    # ── event bus handler ────────────────────────────────────────────────────

    def _on_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("_on_request: expected dict, got %s", type(data).__name__)
            return

        action = data.get("action", "transmute")
        result: Any

        if action == "transmute":
            result = self.transmute(data.get("input_element", ""), data.get("target_element", ""))
        elif action == "energy_cost":
            result = self.calculate_energy_cost(data.get("transmutation", {}))
        elif action == "discover":
            result = self.discover_combinations(data.get("elements", []))
        elif action == "list_elements":
            result = self.list_elements()
        elif action == "discovery_log":
            result = self.get_discovery_log()
        else:
            result = {"error": f"Unknown alchemy action: {action}"}

        if self.event_bus:
            self.event_bus.publish(ALCHEMY_TRANSMUTE_RESULT, {"action": action, "result": result})
            logger.debug("Published %s for action=%s", ALCHEMY_TRANSMUTE_RESULT, action)
