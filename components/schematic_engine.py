"""Generates ASCII/SVG schematic diagrams for chemical processes."""

from __future__ import annotations

import logging
import textwrap
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.schematic_engine")

SCHEMATIC_REQUEST = "chemistry.schematic.request"
SCHEMATIC_RESULT = "chemistry.schematic.result"


class SchematicEngine:
    """Renders reaction equations, process-flow diagrams, and apparatus layouts
    as ASCII art or minimal SVG."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._default_style = "ascii"
        logger.info("SchematicEngine initialised")

        if event_bus:
            event_bus.subscribe(SCHEMATIC_REQUEST, self._on_request)
            logger.debug("Subscribed to %s", SCHEMATIC_REQUEST)

    # ── public API ───────────────────────────────────────────────────────────

    def render_reaction(
        self,
        reactants: List[str],
        products: List[str],
        catalyst: Optional[str] = None,
        style: str = "ascii",
    ) -> str:
        """Return a schematic string for a chemical reaction.

        Example output (ASCII)::

            H2 + O2  ──[ Pt ]──▶  H2O
        """
        lhs = " + ".join(reactants)
        rhs = " + ".join(products)

        if style == "svg":
            return self._reaction_svg(lhs, rhs, catalyst)

        arrow_label = f"[ {catalyst} ]" if catalyst else ""
        arrow = f"──{arrow_label}──▶"
        line = f"  {lhs}  {arrow}  {rhs}"

        top_border = "┌" + "─" * (len(line) + 2) + "┐"
        bot_border = "└" + "─" * (len(line) + 2) + "┘"
        schematic = "\n".join([top_border, f"│ {line} │", bot_border])
        logger.debug("render_reaction: %d chars", len(schematic))
        return schematic

    def render_process_flow(self, steps: List[str], style: str = "ascii") -> str:
        """Render a linear process-flow diagram.

        Each element in *steps* is a stage label.  Output example::

            [Mixing] ──▶ [Heating] ──▶ [Distillation] ──▶ [Collection]
        """
        if not steps:
            return "(empty process)"

        if style == "svg":
            return self._process_flow_svg(steps)

        boxes = [f"[{s}]" for s in steps]
        flow_line = " ──▶ ".join(boxes)

        separator = "═" * (len(flow_line) + 4)
        schematic = "\n".join([separator, f"  {flow_line}", separator])
        logger.debug("render_process_flow: %d steps", len(steps))
        return schematic

    def render_apparatus(self, equipment_list: List[str], style: str = "ascii") -> str:
        """Render an ASCII depiction of laboratory/industrial apparatus.

        Each item gets its own box; items are connected vertically.
        """
        if not equipment_list:
            return "(no equipment)"

        if style == "svg":
            return self._apparatus_svg(equipment_list)

        lines: List[str] = []
        max_width = max(len(e) for e in equipment_list)
        for idx, equip in enumerate(equipment_list):
            padded = equip.center(max_width)
            border = "─" * (max_width + 2)
            lines.append(f"┌{border}┐")
            lines.append(f"│ {padded} │")
            lines.append(f"└{border}┘")
            if idx < len(equipment_list) - 1:
                lines.append(" " * ((max_width + 4) // 2) + "│")
                lines.append(" " * ((max_width + 4) // 2) + "▼")

        schematic = "\n".join(lines)
        logger.debug("render_apparatus: %d items", len(equipment_list))
        return schematic

    # ── SVG helpers ──────────────────────────────────────────────────────────

    def _reaction_svg(self, lhs: str, rhs: str, catalyst: Optional[str]) -> str:
        cat_text = f'<text x="250" y="35" text-anchor="middle" font-size="11">{catalyst}</text>' if catalyst else ""
        return textwrap.dedent(f"""\
            <svg xmlns="http://www.w3.org/2000/svg" width="500" height="60">
              <text x="10" y="40" font-family="monospace" font-size="14">{lhs}</text>
              <line x1="160" y1="35" x2="340" y2="35" stroke="black" stroke-width="2"
                    marker-end="url(#arrow)"/>
              {cat_text}
              <text x="360" y="40" font-family="monospace" font-size="14">{rhs}</text>
              <defs><marker id="arrow" markerWidth="10" markerHeight="7"
                refX="10" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="black"/></marker></defs>
            </svg>""")

    def _process_flow_svg(self, steps: List[str]) -> str:
        box_w, box_h, gap = 120, 40, 30
        total_w = len(steps) * box_w + (len(steps) - 1) * gap + 20
        parts: List[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="80">']
        for i, step in enumerate(steps):
            x = 10 + i * (box_w + gap)
            parts.append(f'<rect x="{x}" y="20" width="{box_w}" height="{box_h}" '
                         f'fill="#e0e7ff" stroke="#4f46e5" rx="6"/>')
            parts.append(f'<text x="{x + box_w // 2}" y="45" text-anchor="middle" '
                         f'font-size="12" font-family="sans-serif">{step}</text>')
            if i < len(steps) - 1:
                ax = x + box_w
                parts.append(f'<line x1="{ax}" y1="40" x2="{ax + gap}" y2="40" '
                             f'stroke="#4f46e5" stroke-width="2" marker-end="url(#arr)"/>')
        parts.append('<defs><marker id="arr" markerWidth="8" markerHeight="6" '
                     'refX="8" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" '
                     'fill="#4f46e5"/></marker></defs>')
        parts.append("</svg>")
        return "\n".join(parts)

    def _apparatus_svg(self, equipment_list: List[str]) -> str:
        box_w, box_h, gap = 160, 40, 25
        total_h = len(equipment_list) * (box_h + gap) + 20
        parts: List[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="{total_h}">']
        for i, equip in enumerate(equipment_list):
            y = 10 + i * (box_h + gap)
            parts.append(f'<rect x="20" y="{y}" width="{box_w}" height="{box_h}" '
                         f'fill="#fef9c3" stroke="#ca8a04" rx="4"/>')
            parts.append(f'<text x="100" y="{y + 25}" text-anchor="middle" '
                         f'font-size="12" font-family="sans-serif">{equip}</text>')
            if i < len(equipment_list) - 1:
                ly = y + box_h
                parts.append(f'<line x1="100" y1="{ly}" x2="100" y2="{ly + gap}" '
                             f'stroke="#ca8a04" stroke-width="2" marker-end="url(#darr)"/>')
        parts.append('<defs><marker id="darr" markerWidth="8" markerHeight="6" '
                     'refX="4" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" '
                     'fill="#ca8a04"/></marker></defs>')
        parts.append("</svg>")
        return "\n".join(parts)

    # ── event bus handler ────────────────────────────────────────────────────

    def _on_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("_on_request: expected dict, got %s", type(data).__name__)
            return

        action = data.get("action", "reaction")
        style = data.get("style", self._default_style)
        result: str

        if action == "reaction":
            result = self.render_reaction(
                reactants=data.get("reactants", []),
                products=data.get("products", []),
                catalyst=data.get("catalyst"),
                style=style,
            )
        elif action == "process_flow":
            result = self.render_process_flow(steps=data.get("steps", []), style=style)
        elif action == "apparatus":
            result = self.render_apparatus(equipment_list=data.get("equipment", []), style=style)
        else:
            result = f"Unknown schematic action: {action}"

        if self.event_bus:
            self.event_bus.publish(SCHEMATIC_RESULT, {"action": action, "style": style, "schematic": result})
            logger.debug("Published %s for action=%s", SCHEMATIC_RESULT, action)
