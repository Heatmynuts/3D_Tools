"""Corsair XENEON EDGE 14.5" — modèle de référence (gabarit pour concevoir supports et accessoires).

Source : modèle officiel publié par Corsair sur Printables, licence CC-BY (voir SOURCE.md).
Le STEP d'origine est conservé tel quel dans source/ ; ici il est seulement recentré :
centre en X/Y, face la plus basse à Z = 0. Orientation d'origine conservée.
"""

import sys
from pathlib import Path

from build123d import Pos, import_step

SOURCE_STEP = Path(__file__).parent / "source" / "corsair-xeneon-edge.step"
OUT_DIR = Path(__file__).parent / "out"
ATTRIBUTION = (
    "Modèle officiel « CORSAIR Xeneon EDGE 14.5 touchscreen model » par Corsair, "
    "licence CC-BY : https://www.printables.com/model/1651858"
)


def build_ecran():
    ecran = import_step(SOURCE_STEP)
    bb = ecran.bounding_box()
    return Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * ecran


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from export import export_all

    export_all({"ecran": build_ecran()}, "xeneon_edge", OUT_DIR, reference=True, source=ATTRIBUTION)
