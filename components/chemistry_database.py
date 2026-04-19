"""In-memory chemical compound database with SMILES notation support."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.chemistry_database")

# ── Event names ──────────────────────────────────────────────────────────────
CHEMISTRY_DB_QUERY = "chemistry.database.query"
CHEMISTRY_DB_RESULT = "chemistry.database.result"


class Compound:
    """A single chemical compound record."""

    __slots__ = ("name", "formula", "smiles", "molecular_weight", "boiling_point",
                 "melting_point", "density", "hazard_class", "extra")

    def __init__(
        self,
        name: str,
        formula: str,
        smiles: str = "",
        molecular_weight: float = 0.0,
        boiling_point: Optional[float] = None,
        melting_point: Optional[float] = None,
        density: Optional[float] = None,
        hazard_class: str = "none",
        **extra: Any,
    ) -> None:
        self.name = name
        self.formula = formula
        self.smiles = smiles
        self.molecular_weight = molecular_weight
        self.boiling_point = boiling_point
        self.melting_point = melting_point
        self.density = density
        self.hazard_class = hazard_class
        self.extra = extra

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "formula": self.formula,
            "smiles": self.smiles,
            "molecular_weight": self.molecular_weight,
            "boiling_point": self.boiling_point,
            "melting_point": self.melting_point,
            "density": self.density,
            "hazard_class": self.hazard_class,
            **self.extra,
        }


def _seed_compounds() -> Dict[str, Compound]:
    """Return a dict of ~20 common compounds keyed by lower-case name."""
    raw: List[Dict[str, Any]] = [
        dict(name="Water", formula="H2O", smiles="O", molecular_weight=18.015,
             boiling_point=100.0, melting_point=0.0, density=1.0, hazard_class="none"),
        dict(name="Ethanol", formula="C2H5OH", smiles="CCO", molecular_weight=46.07,
             boiling_point=78.37, melting_point=-114.1, density=0.789, hazard_class="flammable"),
        dict(name="Acetone", formula="C3H6O", smiles="CC(=O)C", molecular_weight=58.08,
             boiling_point=56.05, melting_point=-94.7, density=0.784, hazard_class="flammable"),
        dict(name="Sodium Chloride", formula="NaCl", smiles="[Na+].[Cl-]", molecular_weight=58.44,
             boiling_point=1413.0, melting_point=801.0, density=2.165, hazard_class="none"),
        dict(name="Hydrochloric Acid", formula="HCl", smiles="Cl", molecular_weight=36.46,
             boiling_point=-85.05, melting_point=-114.2, density=1.49, hazard_class="corrosive"),
        dict(name="Sodium Hydroxide", formula="NaOH", smiles="[Na+].[OH-]", molecular_weight=40.0,
             boiling_point=1388.0, melting_point=323.0, density=2.13, hazard_class="corrosive"),
        dict(name="Sulfuric Acid", formula="H2SO4", smiles="OS(=O)(=O)O", molecular_weight=98.079,
             boiling_point=337.0, melting_point=10.31, density=1.84, hazard_class="corrosive"),
        dict(name="Methanol", formula="CH3OH", smiles="CO", molecular_weight=32.04,
             boiling_point=64.7, melting_point=-97.6, density=0.792, hazard_class="flammable/toxic"),
        dict(name="Benzene", formula="C6H6", smiles="c1ccccc1", molecular_weight=78.11,
             boiling_point=80.1, melting_point=5.5, density=0.879, hazard_class="flammable/carcinogen"),
        dict(name="Acetic Acid", formula="CH3COOH", smiles="CC(=O)O", molecular_weight=60.052,
             boiling_point=118.1, melting_point=16.6, density=1.049, hazard_class="corrosive/flammable"),
        dict(name="Ammonia", formula="NH3", smiles="N", molecular_weight=17.031,
             boiling_point=-33.34, melting_point=-77.73, density=0.73, hazard_class="toxic/corrosive"),
        dict(name="Glucose", formula="C6H12O6", smiles="OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
             molecular_weight=180.16, boiling_point=None, melting_point=146.0, density=1.54, hazard_class="none"),
        dict(name="Carbon Dioxide", formula="CO2", smiles="O=C=O", molecular_weight=44.01,
             boiling_point=-78.46, melting_point=-56.56, density=1.98, hazard_class="asphyxiant"),
        dict(name="Hydrogen Peroxide", formula="H2O2", smiles="OO", molecular_weight=34.014,
             boiling_point=150.2, melting_point=-0.43, density=1.45, hazard_class="oxidizer/corrosive"),
        dict(name="Toluene", formula="C7H8", smiles="Cc1ccccc1", molecular_weight=92.14,
             boiling_point=110.6, melting_point=-95.0, density=0.87, hazard_class="flammable"),
        dict(name="Nitric Acid", formula="HNO3", smiles="[O-][N+](=O)O", molecular_weight=63.01,
             boiling_point=83.0, melting_point=-42.0, density=1.51, hazard_class="corrosive/oxidizer"),
        dict(name="Calcium Carbonate", formula="CaCO3", smiles="[Ca+2].[O-]C([O-])=O",
             molecular_weight=100.09, boiling_point=None, melting_point=825.0, density=2.71, hazard_class="none"),
        dict(name="Isopropanol", formula="C3H8O", smiles="CC(O)C", molecular_weight=60.1,
             boiling_point=82.6, melting_point=-89.0, density=0.786, hazard_class="flammable"),
        dict(name="Phosphoric Acid", formula="H3PO4", smiles="OP(=O)(O)O", molecular_weight=97.994,
             boiling_point=158.0, melting_point=42.35, density=1.885, hazard_class="corrosive"),
        dict(name="Potassium Permanganate", formula="KMnO4", smiles="[K+].[O-][Mn](=O)(=O)=O",
             molecular_weight=158.034, boiling_point=None, melting_point=240.0, density=2.7, hazard_class="oxidizer"),
    ]
    db: Dict[str, Compound] = {}
    for entry in raw:
        db[entry["name"].lower()] = Compound(**entry)
    return db


class ChemistryDatabase:
    """In-memory chemical compound database with SMILES, formula, and name lookup."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._compounds: Dict[str, Compound] = _seed_compounds()
        logger.info("ChemistryDatabase initialised with %d compounds", len(self._compounds))

        if event_bus:
            event_bus.subscribe(CHEMISTRY_DB_QUERY, self._on_query)
            logger.debug("Subscribed to %s", CHEMISTRY_DB_QUERY)

    # ── public API ───────────────────────────────────────────────────────────

    def search_compounds(self, query: str) -> List[Dict[str, Any]]:
        """Search by partial name, formula, or SMILES.  Case-insensitive."""
        query_lower = query.strip().lower()
        results: List[Dict[str, Any]] = []
        for compound in self._compounds.values():
            if (query_lower in compound.name.lower()
                    or query_lower in compound.formula.lower()
                    or query_lower in compound.smiles.lower()):
                results.append(compound.to_dict())
        logger.debug("search_compounds(%r) -> %d hits", query, len(results))
        return results

    def get_properties(self, compound_name: str) -> Optional[Dict[str, Any]]:
        """Return full property dict for *compound_name*, or ``None``."""
        compound = self._compounds.get(compound_name.strip().lower())
        if compound is None:
            logger.debug("get_properties(%r): not found", compound_name)
            return None
        return compound.to_dict()

    def add_compound(self, name: str, formula: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add or update a compound.  *properties* feeds extra keyword args."""
        props = properties or {}
        compound = Compound(name=name, formula=formula, **props)
        self._compounds[name.strip().lower()] = compound
        logger.info("add_compound: stored %r (%s)", name, formula)
        return compound.to_dict()

    def list_all(self) -> List[str]:
        """Return a sorted list of all compound names."""
        return sorted(c.name for c in self._compounds.values())

    def get_by_formula(self, formula: str) -> List[Dict[str, Any]]:
        """Find all compounds matching an exact formula (case-insensitive)."""
        formula_lower = formula.strip().lower()
        return [c.to_dict() for c in self._compounds.values() if c.formula.lower() == formula_lower]

    def get_by_smiles(self, smiles: str) -> Optional[Dict[str, Any]]:
        """Lookup compound by exact SMILES string."""
        for c in self._compounds.values():
            if c.smiles == smiles:
                return c.to_dict()
        return None

    # ── event bus handler ────────────────────────────────────────────────────

    def _on_query(self, data: Any) -> None:
        """Handle ``chemistry.database.query`` events.

        Expected *data* keys:
            action: "search" | "get" | "add" | "list" | "formula" | "smiles"
            query / name / formula / smiles / properties: depends on action
        """
        if not isinstance(data, dict):
            logger.warning("_on_query: expected dict, got %s", type(data).__name__)
            return

        action = data.get("action", "search")
        result: Any = None

        if action == "search":
            result = self.search_compounds(data.get("query", ""))
        elif action == "get":
            result = self.get_properties(data.get("name", ""))
        elif action == "add":
            result = self.add_compound(
                name=data.get("name", "Unknown"),
                formula=data.get("formula", ""),
                properties=data.get("properties"),
            )
        elif action == "list":
            result = self.list_all()
        elif action == "formula":
            result = self.get_by_formula(data.get("formula", ""))
        elif action == "smiles":
            result = self.get_by_smiles(data.get("smiles", ""))
        else:
            result = {"error": f"Unknown action: {action}"}

        if self.event_bus:
            self.event_bus.publish(CHEMISTRY_DB_RESULT, {"action": action, "result": result})
            logger.debug("Published %s for action=%s", CHEMISTRY_DB_RESULT, action)
