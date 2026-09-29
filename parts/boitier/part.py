"""Boîtier paramétrique avec couvercle à lèvre emboîtée (pièce de démonstration).

Les deux pièces sont modélisées dans leur position d'impression, côte à côte sur le plateau :
- boîtier : ouverture vers le haut ;
- couvercle : face extérieure sur le plateau, lèvre vers le haut.
"""

import sys
from pathlib import Path

from build123d import (
    Axis,
    BuildPart,
    BuildSketch,
    Locations,
    Mode,
    Plane,
    RectangleRounded,
    extrude,
    fillet,
)

# ---------------------------------------------------------------- PARAMÈTRES (mm)
LONGUEUR = 80.0            # extérieur, axe X
LARGEUR = 60.0             # extérieur, axe Y
HAUTEUR = 40.0             # extérieur du boîtier seul, axe Z
EPAISSEUR_PAROI = 2.0
EPAISSEUR_FOND = 2.0
RAYON_ANGLES = 4.0         # arrondi vertical des angles extérieurs
CONGE_INTERIEUR = 1.5      # congé fond/paroi (wiki Bambu : supprime les lignes de changement de section)

EPAISSEUR_COUVERCLE = 2.0
HAUTEUR_LEVRE = 4.0
EPAISSEUR_LEVRE = 1.6
JEU = 0.2                  # jeu lèvre/paroi, plage Bambu 0,15–0,3 mm

ECART_PLATEAU = 10.0       # espace entre les deux pièces sur le plateau
# -------------------------------------------------------------------------------

OUT_DIR = Path(__file__).parent / "out"


def cavite_dims() -> tuple[float, float, float]:
    """Longueur, largeur et rayon d'angle de la cavité intérieure."""
    return (
        LONGUEUR - 2 * EPAISSEUR_PAROI,
        LARGEUR - 2 * EPAISSEUR_PAROI,
        RAYON_ANGLES - EPAISSEUR_PAROI,
    )


def build_boitier():
    cav_l, cav_w, cav_r = cavite_dims()
    with BuildPart() as boitier:
        with BuildSketch():
            RectangleRounded(LONGUEUR, LARGEUR, RAYON_ANGLES)
        extrude(amount=HAUTEUR)

        with BuildPart(Plane.XY.offset(EPAISSEUR_FOND), mode=Mode.PRIVATE) as cavite:
            with BuildSketch():
                RectangleRounded(cav_l, cav_w, cav_r)
            extrude(amount=HAUTEUR)
            fillet(cavite.edges().group_by(Axis.Z)[0], radius=CONGE_INTERIEUR)
        boitier.part -= cavite.part
    return boitier.part


def build_couvercle():
    cav_l, cav_w, cav_r = cavite_dims()
    levre_l = cav_l - 2 * JEU
    levre_w = cav_w - 2 * JEU
    levre_r = cav_r - JEU
    x = LONGUEUR + ECART_PLATEAU
    with BuildPart() as couvercle:
        with Locations((x, 0, 0)):
            with BuildSketch():
                RectangleRounded(LONGUEUR, LARGEUR, RAYON_ANGLES)
            extrude(amount=EPAISSEUR_COUVERCLE)
        with BuildSketch(Plane.XY.offset(EPAISSEUR_COUVERCLE)) as levre:
            with Locations((x, 0)):
                RectangleRounded(levre_l, levre_w, levre_r)
                RectangleRounded(
                    levre_l - 2 * EPAISSEUR_LEVRE,
                    levre_w - 2 * EPAISSEUR_LEVRE,
                    max(levre_r - EPAISSEUR_LEVRE, 0.5),
                    mode=Mode.SUBTRACT,
                )
        extrude(levre.sketch, amount=HAUTEUR_LEVRE)
    return couvercle.part


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from export import export_all

    params = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float))}
    export_all(
        {"boitier": build_boitier(), "couvercle": build_couvercle()},
        "boitier",
        OUT_DIR,
        params,
    )
