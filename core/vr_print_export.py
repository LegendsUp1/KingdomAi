import os
import json
import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DESIGN_DIR = os.path.join(BASE_DIR, "vr_designs")


def _ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _slugify(name: str) -> str:
    value = "".join(c if c.isalnum() else "_" for c in str(name).strip().lower())
    while "__" in value:
        value = value.replace("__", "_")
    return value.strip("_") or "vr_design"


def export_design_spec(design_spec: Dict[str, Any]) -> Dict[str, str]:
    _ensure_dir(DESIGN_DIR)
    name = design_spec.get("name", "vr_design")
    slug = _slugify(name)
    timestamp = int(time.time())
    base = f"{slug}_{timestamp}"

    json_path = os.path.join(DESIGN_DIR, f"{base}.design.json")
    scad_path = os.path.join(DESIGN_DIR, f"{base}.scad")

    try:
        with open(json_path, "w", encoding="utf-8") as f_json:
            json.dump(design_spec, f_json, indent=2)
    except Exception as e:
        logger.error(f"Failed to write design JSON: {e}")

    try:
        components = design_spec.get("components") or []
        lines = []
        lines.append("// Auto-generated from Kingdom AI design spec")
        lines.append(f"// Source JSON: {os.path.basename(json_path)}")
        lines.append("")
        lines.append("module generated_design() {")
        for comp in components:
            shape = str(comp.get("shape", "")).lower()
            dims = comp.get("dimensions", {})
            pos = comp.get("position", {})
            rot = comp.get("rotation", {})
            tx = float(pos.get("x", 0.0))
            ty = float(pos.get("y", 0.0))
            tz = float(pos.get("z", 0.0))
            rx = float(rot.get("x", 0.0))
            ry = float(rot.get("y", 0.0))
            rz = float(rot.get("z", 0.0))
            lines.append("    translate([%.3f, %.3f, %.3f])" % (tx, ty, tz))
            lines.append("    rotate([%.3f, %.3f, %.3f])" % (rx, ry, rz))
            if shape == "cube":
                sx = float(dims.get("x", 1.0))
                sy = float(dims.get("y", 1.0))
                sz = float(dims.get("z", 1.0))
                lines.append("    cube([%.3f, %.3f, %.3f], center=false);" % (sx, sy, sz))
            elif shape == "cylinder":
                r = float(dims.get("r", dims.get("radius", 1.0)))
                h = float(dims.get("h", dims.get("height", 1.0)))
                lines.append("    cylinder(h=%.3f, r=%.3f, center=false);" % (h, r))
            elif shape == "sphere":
                r = float(dims.get("r", dims.get("radius", 1.0)))
                lines.append("    sphere(r=%.3f);" % r)
            else:
                lines.append("    // Unsupported shape: %s" % shape)
            lines.append("")
        lines.append("}")
        lines.append("")
        lines.append("generated_design();")

        with open(scad_path, "w", encoding="utf-8") as f_scad:
            f_scad.write("\n".join(lines))
    except Exception as e:
        logger.error(f"Failed to write SCAD file: {e}")

    return {"json": json_path, "scad": scad_path}
