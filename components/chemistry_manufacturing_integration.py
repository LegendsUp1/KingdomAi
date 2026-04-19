"""Chemistry / manufacturing orchestration (creator events).

Wires all nine sub-engines to the shared event bus and exposes a unified
``run_pipeline`` entry point.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.kingdom_event_names import CREATOR_CHEMISTRY_ANALYZE, CREATOR_CHEMISTRY_VISUALIZE

from components.chemistry_database import ChemistryDatabase
from components.schematic_engine import SchematicEngine
from components.blueprint_engine import BlueprintEngine
from components.exploded_view_engine import ExplodedViewEngine
from components.metallurgy_engine import MetallurgyEngine
from components.biological_system import BiologicalSystem
from components.alchemy_system import AlchemySystem
from components.manufacturing_engine import ManufacturingEngine
from components.visualization_dashboard import VisualizationDashboard

logger = logging.getLogger("kingdom_ai.chemistry_manufacturing")


class ChemistryManufacturingOrchestrator:
    """Central orchestrator that owns and wires all chemistry/manufacturing sub-engines."""

    def __init__(self, event_bus: Any) -> None:
        self.event_bus = event_bus

        # ── Instantiate sub-engines (each subscribes to its own events) ──────
        self.chemistry_db = ChemistryDatabase(event_bus)
        self.schematic = SchematicEngine(event_bus)
        self.blueprint = BlueprintEngine(event_bus)
        self.exploded_view = ExplodedViewEngine(event_bus)
        self.metallurgy = MetallurgyEngine(event_bus)
        self.biology = BiologicalSystem(event_bus)
        self.alchemy = AlchemySystem(event_bus)
        self.manufacturing = ManufacturingEngine(event_bus)
        self.dashboard = VisualizationDashboard(event_bus)

        # ── Register all engines as dashboard data sources ───────────────────
        self.dashboard.register_data_source("chemistry_database", self.chemistry_db)
        self.dashboard.register_data_source("schematic_engine", self.schematic)
        self.dashboard.register_data_source("blueprint_engine", self.blueprint)
        self.dashboard.register_data_source("exploded_view_engine", self.exploded_view)
        self.dashboard.register_data_source("metallurgy_engine", self.metallurgy)
        self.dashboard.register_data_source("biological_system", self.biology)
        self.dashboard.register_data_source("alchemy_system", self.alchemy)
        self.dashboard.register_data_source("manufacturing_engine", self.manufacturing)

        # ── Subscribe to top-level creator events ────────────────────────────
        if event_bus:
            event_bus.subscribe(CREATOR_CHEMISTRY_ANALYZE, self._on_analyze)
            event_bus.subscribe(CREATOR_CHEMISTRY_VISUALIZE, self._on_visualize)

        logger.info("ChemistryManufacturingOrchestrator initialised — all 9 sub-engines wired")

    # ── Creator-event handlers ───────────────────────────────────────────────

    def _on_analyze(self, data: Any) -> None:
        """Route a creator-level analysis request to the appropriate sub-engine."""
        logger.debug("Chemistry analyze: %s", str(data)[:200])
        if not isinstance(data, dict):
            return

        target = data.get("target", "chemistry")

        if target == "chemistry":
            result = self.chemistry_db.search_compounds(data.get("query", ""))
        elif target == "metallurgy":
            result = self.metallurgy.analyze_alloy(data.get("composition", {}))
        elif target == "biology":
            result = self.biology.analyze_dna_sequence(data.get("sequence", ""))
        elif target == "alchemy":
            result = self.alchemy.transmute(
                data.get("input_element", ""), data.get("target_element", ""))
        elif target == "manufacturing":
            result = self.manufacturing.simulate_process(
                data.get("process_type", "cnc_milling"), data.get("parameters", {}))
        else:
            result = {"error": f"Unknown analysis target: {target}"}

        if self.event_bus:
            self.event_bus.publish("creator_chemistry_analyze.result", {
                "target": target, "result": result,
            })

    def _on_visualize(self, data: Any) -> None:
        """Route a creator-level visualization request to the appropriate renderer."""
        logger.debug("Chemistry visualize: %s", str(data)[:200])
        if not isinstance(data, dict):
            return

        viz_type = data.get("type", "reaction")

        if viz_type == "reaction":
            result = self.schematic.render_reaction(
                reactants=data.get("reactants", []),
                products=data.get("products", []),
                catalyst=data.get("catalyst"),
                style=data.get("style", "ascii"),
            )
        elif viz_type == "process_flow":
            result = self.schematic.render_process_flow(
                steps=data.get("steps", []),
                style=data.get("style", "ascii"),
            )
        elif viz_type == "apparatus":
            result = self.schematic.render_apparatus(
                equipment_list=data.get("equipment", []),
                style=data.get("style", "ascii"),
            )
        elif viz_type == "blueprint":
            result = self.blueprint.create_blueprint(data.get("spec", {}))
        elif viz_type == "exploded_view":
            result = self.exploded_view.create_exploded_view(data.get("assembly", {}))
        elif viz_type == "dashboard":
            result = self.dashboard.format_for_gui()
        else:
            result = {"error": f"Unknown visualization type: {viz_type}"}

        if self.event_bus:
            self.event_bus.publish("creator_chemistry_visualize.result", {
                "type": viz_type, "result": result,
            })

    # ── Unified pipeline ─────────────────────────────────────────────────────

    def run_pipeline(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an end-to-end pipeline described by *spec*.

        *spec* can contain any combination of:
          - ``analyze``: dict passed to ``_on_analyze``
          - ``visualize``: dict passed to ``_on_visualize``
          - ``blueprint``: spec dict for ``BlueprintEngine.create_blueprint``
          - ``manufacturing``: params for ``ManufacturingEngine.simulate_process``
          - ``metallurgy``: composition dict for ``MetallurgyEngine.analyze_alloy``
          - ``biology``: params for ``BiologicalSystem`` (action key selects method)
          - ``alchemy``: params for ``AlchemySystem.transmute``
        """
        results: Dict[str, Any] = {"ok": True, "spec_keys": list(spec.keys())}

        if "analyze" in spec:
            self._on_analyze(spec["analyze"])
            results["analyze"] = "dispatched"

        if "visualize" in spec:
            self._on_visualize(spec["visualize"])
            results["visualize"] = "dispatched"

        if "blueprint" in spec:
            results["blueprint"] = self.blueprint.create_blueprint(spec["blueprint"])

        if "manufacturing" in spec:
            mfg = spec["manufacturing"]
            results["manufacturing"] = self.manufacturing.simulate_process(
                mfg.get("process_type", "cnc_milling"), mfg.get("parameters", {}))

        if "metallurgy" in spec:
            results["metallurgy"] = self.metallurgy.analyze_alloy(spec["metallurgy"])

        if "biology" in spec:
            bio = spec["biology"]
            action = bio.get("action", "dna")
            if action == "dna":
                results["biology"] = self.biology.analyze_dna_sequence(bio.get("sequence", ""))
            elif action == "kinetics":
                results["biology"] = self.biology.model_enzyme_kinetics(
                    substrate_conc=float(bio.get("substrate_conc", 1)),
                    vmax=float(bio.get("vmax", 10)),
                    km=float(bio.get("km", 5)),
                )
            elif action == "population":
                results["biology"] = self.biology.model_population_growth(bio.get("params", {}))
            elif action == "pathway":
                results["biology"] = self.biology.simulate_pathway(bio.get("pathway_steps", []))

        if "alchemy" in spec:
            alc = spec["alchemy"]
            results["alchemy"] = self.alchemy.transmute(
                alc.get("input_element", ""), alc.get("target_element", ""))

        if "dashboard" in spec:
            results["dashboard"] = self.dashboard.format_for_gui()

        logger.info("run_pipeline: processed %d sections", len(results) - 2)
        return results

    # ── Convenience accessors ────────────────────────────────────────────────

    def get_dashboard(self) -> Dict[str, Any]:
        return self.dashboard.format_for_gui()

    def get_engine(self, name: str) -> Optional[Any]:
        """Return a sub-engine by short name."""
        return {
            "chemistry_db": self.chemistry_db,
            "schematic": self.schematic,
            "blueprint": self.blueprint,
            "exploded_view": self.exploded_view,
            "metallurgy": self.metallurgy,
            "biology": self.biology,
            "alchemy": self.alchemy,
            "manufacturing": self.manufacturing,
            "dashboard": self.dashboard,
        }.get(name)
