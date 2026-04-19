"""Models biological processes — enzyme kinetics, metabolic pathways, cell modelling."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("kingdom_ai.biological_system")

BIOLOGY_MODEL_REQUEST = "biology.model.request"
BIOLOGY_MODEL_RESULT = "biology.model.result"

_CODON_TABLE: Dict[str, str] = {
    "TTT": "Phe", "TTC": "Phe", "TTA": "Leu", "TTG": "Leu",
    "CTT": "Leu", "CTC": "Leu", "CTA": "Leu", "CTG": "Leu",
    "ATT": "Ile", "ATC": "Ile", "ATA": "Ile", "ATG": "Met",
    "GTT": "Val", "GTC": "Val", "GTA": "Val", "GTG": "Val",
    "TCT": "Ser", "TCC": "Ser", "TCA": "Ser", "TCG": "Ser",
    "CCT": "Pro", "CCC": "Pro", "CCA": "Pro", "CCG": "Pro",
    "ACT": "Thr", "ACC": "Thr", "ACA": "Thr", "ACG": "Thr",
    "GCT": "Ala", "GCC": "Ala", "GCA": "Ala", "GCG": "Ala",
    "TAT": "Tyr", "TAC": "Tyr", "TAA": "Stop", "TAG": "Stop",
    "CAT": "His", "CAC": "His", "CAA": "Gln", "CAG": "Gln",
    "AAT": "Asn", "AAC": "Asn", "AAA": "Lys", "AAG": "Lys",
    "GAT": "Asp", "GAC": "Asp", "GAA": "Glu", "GAG": "Glu",
    "TGT": "Cys", "TGC": "Cys", "TGA": "Stop", "TGG": "Trp",
    "CGT": "Arg", "CGC": "Arg", "CGA": "Arg", "CGG": "Arg",
    "AGT": "Ser", "AGC": "Ser", "AGA": "Arg", "AGG": "Arg",
    "GGT": "Gly", "GGC": "Gly", "GGA": "Gly", "GGG": "Gly",
}


class BiologicalSystem:
    """Enzyme kinetics, pathway simulation, population modelling, DNA analysis."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        logger.info("BiologicalSystem initialised")

        if event_bus:
            event_bus.subscribe(BIOLOGY_MODEL_REQUEST, self._on_request)
            logger.debug("Subscribed to %s", BIOLOGY_MODEL_REQUEST)

    # ── Enzyme kinetics ──────────────────────────────────────────────────────

    def model_enzyme_kinetics(
        self,
        substrate_conc: float,
        vmax: float,
        km: float,
        inhibitor_conc: float = 0.0,
        ki: float = 0.0,
        inhibition_type: str = "none",
    ) -> Dict[str, Any]:
        """Michaelis-Menten kinetics with optional inhibition.

        *inhibition_type*: ``"none"``, ``"competitive"``, ``"uncompetitive"``,
        ``"noncompetitive"``.
        """
        if km <= 0 or vmax <= 0:
            return {"error": "Vmax and Km must be positive"}

        effective_km = km
        effective_vmax = vmax

        if inhibitor_conc > 0 and ki > 0:
            alpha = 1 + inhibitor_conc / ki
            if inhibition_type == "competitive":
                effective_km = km * alpha
            elif inhibition_type == "uncompetitive":
                effective_vmax = vmax / alpha
                effective_km = km / alpha
            elif inhibition_type == "noncompetitive":
                effective_vmax = vmax / alpha

        velocity = (effective_vmax * substrate_conc) / (effective_km + substrate_conc)

        result = {
            "substrate_conc": substrate_conc,
            "vmax": vmax,
            "km": km,
            "velocity": round(velocity, 6),
            "fraction_vmax": round(velocity / vmax, 4),
            "inhibition_type": inhibition_type,
        }
        if inhibitor_conc > 0:
            result["effective_km"] = round(effective_km, 4)
            result["effective_vmax"] = round(effective_vmax, 4)

        logger.debug("model_enzyme_kinetics: v=%.4f at [S]=%.4f", velocity, substrate_conc)
        return result

    def michaelis_menten_curve(
        self, vmax: float, km: float, points: int = 20, s_max: float = 0.0
    ) -> List[Dict[str, float]]:
        """Return [S] vs v data points for plotting."""
        if s_max <= 0:
            s_max = km * 10
        step = s_max / points
        curve = []
        for i in range(points + 1):
            s = step * i
            v = (vmax * s) / (km + s) if (km + s) > 0 else 0
            curve.append({"substrate_conc": round(s, 4), "velocity": round(v, 6)})
        return curve

    # ── Pathway simulation ───────────────────────────────────────────────────

    def simulate_pathway(self, pathway_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simulate a linear metabolic pathway.

        Each step dict: ``{"name": ..., "rate": ..., "substrate": ..., "product": ...}``.
        Returns concentrations over discrete time steps.
        """
        if not pathway_steps:
            return {"error": "No pathway steps provided"}

        metabolites: Dict[str, float] = {}
        for step in pathway_steps:
            for key in ("substrate", "product"):
                met = step.get(key, "")
                if met and met not in metabolites:
                    metabolites[met] = 1.0 if key == "substrate" and step is pathway_steps[0] else 0.0

        if pathway_steps[0].get("substrate"):
            metabolites[pathway_steps[0]["substrate"]] = 1.0

        time_points = 50
        dt = 0.1
        history: List[Dict[str, float]] = []

        for t_idx in range(time_points):
            snapshot = {"time": round(t_idx * dt, 2), **{k: round(v, 6) for k, v in metabolites.items()}}
            history.append(snapshot)
            for step in pathway_steps:
                sub = step.get("substrate", "")
                prod = step.get("product", "")
                rate = float(step.get("rate", 0.1))
                if sub and sub in metabolites:
                    flux = rate * metabolites[sub] * dt
                    flux = min(flux, metabolites[sub])
                    metabolites[sub] -= flux
                    if prod:
                        metabolites[prod] = metabolites.get(prod, 0) + flux

        logger.debug("simulate_pathway: %d steps, %d time points", len(pathway_steps), time_points)
        return {
            "steps": [s.get("name", "step") for s in pathway_steps],
            "time_points": len(history),
            "final_concentrations": {k: round(v, 6) for k, v in metabolites.items()},
            "history": history,
        }

    # ── Population growth ────────────────────────────────────────────────────

    def model_population_growth(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Model population growth (logistic by default).

        *params*: model ("logistic"|"exponential"), initial_population, growth_rate,
        carrying_capacity (logistic only), time_steps, dt.
        """
        model = params.get("model", "logistic")
        n0 = float(params.get("initial_population", 100))
        r = float(params.get("growth_rate", 0.1))
        k = float(params.get("carrying_capacity", 10000))
        steps = int(params.get("time_steps", 100))
        dt = float(params.get("dt", 1.0))

        curve: List[Dict[str, float]] = []
        n = n0
        for t in range(steps):
            curve.append({"time": round(t * dt, 2), "population": round(n, 2)})
            if model == "exponential":
                n += r * n * dt
            else:
                n += r * n * (1 - n / k) * dt if k > 0 else 0
            n = max(0, n)

        logger.debug("model_population_growth: model=%s, final N=%.1f", model, n)
        return {
            "model": model,
            "initial_population": n0,
            "growth_rate": r,
            "carrying_capacity": k if model == "logistic" else None,
            "final_population": round(n, 2),
            "curve": curve,
        }

    # ── DNA sequence analysis ────────────────────────────────────────────────

    def analyze_dna_sequence(self, sequence: str) -> Dict[str, Any]:
        """Analyse a DNA sequence for GC content, codons, length, and more."""
        seq = sequence.upper().replace(" ", "").replace("\n", "")
        valid = set("ATGC")
        clean = "".join(c for c in seq if c in valid)

        if not clean:
            return {"error": "No valid nucleotides found in sequence"}

        length = len(clean)
        gc = clean.count("G") + clean.count("C")
        gc_content = gc / length if length > 0 else 0

        counts = {base: clean.count(base) for base in "ATGC"}

        codons: List[str] = [clean[i:i + 3] for i in range(0, length - 2, 3)]
        amino_acids = [_CODON_TABLE.get(c, "?") for c in codons if len(c) == 3]

        has_start = "ATG" in codons
        stop_codons = [c for c in codons if _CODON_TABLE.get(c) == "Stop"]

        complement = clean.translate(str.maketrans("ATGC", "TACG"))
        reverse_complement = complement[::-1]

        molecular_weight_da = length * 330

        result = {
            "length_bp": length,
            "gc_content": round(gc_content, 4),
            "gc_percent": round(gc_content * 100, 2),
            "base_counts": counts,
            "codon_count": len(codons),
            "amino_acid_sequence": amino_acids,
            "has_start_codon": has_start,
            "stop_codons_found": len(stop_codons),
            "complement": complement,
            "reverse_complement": reverse_complement,
            "estimated_mw_da": molecular_weight_da,
        }
        logger.debug("analyze_dna_sequence: %d bp, GC=%.1f%%", length, gc_content * 100)
        return result

    # ── event bus handler ────────────────────────────────────────────────────

    def _on_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("_on_request: expected dict, got %s", type(data).__name__)
            return

        action = data.get("action", "kinetics")
        result: Any

        if action == "kinetics":
            result = self.model_enzyme_kinetics(
                substrate_conc=float(data.get("substrate_conc", 1)),
                vmax=float(data.get("vmax", 10)),
                km=float(data.get("km", 5)),
                inhibitor_conc=float(data.get("inhibitor_conc", 0)),
                ki=float(data.get("ki", 0)),
                inhibition_type=data.get("inhibition_type", "none"),
            )
        elif action == "kinetics_curve":
            result = self.michaelis_menten_curve(
                vmax=float(data.get("vmax", 10)),
                km=float(data.get("km", 5)),
                points=int(data.get("points", 20)),
            )
        elif action == "pathway":
            result = self.simulate_pathway(data.get("pathway_steps", []))
        elif action == "population":
            result = self.model_population_growth(data.get("params", {}))
        elif action == "dna":
            result = self.analyze_dna_sequence(data.get("sequence", ""))
        else:
            result = {"error": f"Unknown biology action: {action}"}

        if self.event_bus:
            self.event_bus.publish(BIOLOGY_MODEL_RESULT, {"action": action, "result": result})
            logger.debug("Published %s for action=%s", BIOLOGY_MODEL_RESULT, action)
