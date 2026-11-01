"""Manufacturing reference values, read from the official Bambu Studio profiles
installed on this machine (never hard-coded guesses). Profiles use `inherits`
chains; values are resolved by walking the chain."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

BUNDLED_BAMBU = Path(__file__).resolve().parents[3] / "tools" / "BambuStudio.app"
DEFAULT_BAMBU = BUNDLED_BAMBU if BUNDLED_BAMBU.is_dir() else Path("/Applications/BambuStudio.app")

PROFILES_DIR = Path(os.getenv(
    "BAMBU_PROFILES_DIR", str(DEFAULT_BAMBU / "Contents/Resources/profiles/BBL")
))
PROCESS_PROFILE = os.getenv("BAMBU_PROCESS_PROFILE", "0.20mm Standard @BBL H2D")

KEYS = (
    "line_width", "outer_wall_line_width", "inner_wall_line_width", "wall_loops", "layer_height",
    "support_threshold_angle", "top_shell_layers", "bottom_shell_layers",
)


def _num(v: object) -> float | None:
    try:
        return float(str(v).rstrip("%"))
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def process_profile() -> dict:
    """Resolved values of the reference process profile, with provenance."""
    folder = PROFILES_DIR / "process"
    out: dict = {"name": PROCESS_PROFILE, "source": None, "values": {}}
    name: str | None = PROCESS_PROFILE
    seen: set[str] = set()
    while name and name not in seen:
        seen.add(name)
        path = folder / f"{name}.json"
        if not path.exists():
            break
        data = json.loads(path.read_text(encoding="utf-8"))
        out["source"] = out["source"] or str(path)
        for key in KEYS:
            if key not in out["values"] and key in data:
                out["values"][key] = _num(data[key])
        name = data.get("inherits")
    v = out["values"]
    if v.get("outer_wall_line_width") and v.get("inner_wall_line_width"):
        # Thinnest wall the slicer fills solidly with its default two perimeters.
        out["two_perimeters_mm"] = round(v["outer_wall_line_width"] + v["inner_wall_line_width"], 2)
    out["available"] = bool(v)
    return out


def profile_for_prompt() -> str:
    p = process_profile()
    if not p["available"]:
        return "Profil Bambu H2D introuvable sur cette machine : aucune valeur de référence d'impression."
    v = p["values"]
    return (
        f"Profil de référence : « {p['name']} » (profil officiel Bambu Studio installé). "
        f"Largeur de ligne paroi extérieure {v.get('outer_wall_line_width')} mm, intérieure "
        f"{v.get('inner_wall_line_width')} mm, {int(v.get('wall_loops') or 0)} parois par défaut "
        f"(≈ {p.get('two_perimeters_mm')} mm pour deux lignes), hauteur de couche {v.get('layer_height')} mm, "
        f"seuil de génération de supports {v.get('support_threshold_angle')}° (surfaces en surplomb "
        f"moins inclinées que ce seuil par rapport à l'horizontale)."
    )
