"""Assemblage de contrôle : écran Xeneon Edge + coque (2 moitiés) + pied (2 parties), à 45°.

Vue uniquement (rien à imprimer ici) : reprend les pièces de parts/coque_xeneon et
parts/support_xeneon dans leur position d'usage. Exporte aussi un STEP d'assemblage.
"""

import importlib.util
import sys
from pathlib import Path

from build123d import Compound, Pos, export_step

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).parent / "out"


def _charger(nom: str, chemin: Path):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tools"))
    from export import export_all

    pied = _charger("support_xeneon", ROOT / "parts" / "support_xeneon" / "part.py")
    coque = pied.coque

    vers_coque = pied.placement() * Pos(0, 0, -coque.Z_CAVITE)
    c_gauche, c_droite = coque.build_moities()
    p_gauche, p_centre, p_droite = pied.build_parties()
    pieces = {
        "coque_gauche": vers_coque * c_gauche,
        "coque_droite": vers_coque * c_droite,
        "pied_gauche": p_gauche,
        "pied_centre": p_centre,
        "pied_droite": p_droite,
    }
    ecran = vers_coque * coque.ecran_en_place()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for nom, p in pieces.items():
        p.label = nom
    ecran.label = "ecran"
    export_step(Compound(children=[*[p.moved(Pos()) for p in pieces.values()], ecran.moved(Pos())], label="xeneon_assemblage"),
                OUT_DIR / "xeneon_assemblage.step")

    export_all(
        pieces,
        "assemblage_xeneon",
        OUT_DIR,
        reference=True,
        source="Assemblage de contrôle (non imprimé). Écran : modèle officiel Corsair, CC-BY : "
        "https://www.printables.com/model/1651858",
        contexte={"ecran": ecran},
        couches=pied.couches_impression(),
    )
