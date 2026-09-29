"""Coque de protection (bumper) PETG pour Corsair Xeneon Edge 14,5″, en 2 moitiés.

- L'écran reste visible et tactile : lèvre avant qui recouvre seulement le cadre (bezel).
- Dos ouvert, sauf un rebord sur lequel repose la face arrière plane de l'écran.
- Coupe au plan X = 0 (écran 372 mm > plateau H2D 325 mm) ; ceinture épaissie à la jonction
  qui porte 4 tenons en losange (faces à 45° → sans support, wiki Bambu « surplombs »).
- Impression : dos sur le plateau. La lèvre avant (surplomb horizontal) demande des supports.

Cotes de l'écran relevées sur le STEP officiel Corsair (voir parts/xeneon_edge/SOURCE.md).
"""

import importlib.util
import sys
from pathlib import Path

from build123d import (
    Align,
    Box,
    BuildPart,
    BuildSketch,
    Location,
    Locations,
    Mode,
    Plane,
    Pos,
    Rectangle,
    RectangleRounded,
    Rot,
    extrude,
)

ROOT = Path(__file__).resolve().parents[2]

# Réutilise l'import + recentrage du STEP officiel (parts/xeneon_edge/part.py).
_spec = importlib.util.spec_from_file_location("xeneon_edge", ROOT / "parts" / "xeneon_edge" / "part.py")
_xeneon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_xeneon)
build_ecran = _xeneon.build_ecran

# ------------------------------------------------ COTES ÉCRAN (relevées sur le STEP, mm)
ECRAN_L = 372.1            # X
ECRAN_W = 119.5            # Y
ECRAN_H = 19.75            # Z (face arrière à Z = 0, vitre en haut)
ECRAN_RAYON = 7.0          # rayon d'angle en plan
DOS_PLAT_X = 174.7         # demi-étendue de la face arrière plane
DOS_PLAT_Y = 48.4
POCHE_X_MIN = 27.1         # zone arrière sans face plane (poche 11,6 mm de profondeur)
POCHE_X_MAX = 114.0

# ---------------------------------------------------------------- PARAMÈTRES (mm)
JEU_ECRAN = 0.3            # jeu coque/écran (plage Bambu 0,15–0,3 pour assemblages, par analogie)
EPAISSEUR_PAROI = 2.0
EPAISSEUR_DOS = 2.0
EPAISSEUR_LEVRE = 2.0
LEVRE_AVANT = 3.0          # recouvrement du cadre avant ; cadre le plus étroit = 5,2 mm
RECOUVREMENT_DOS = 2.0     # le rebord arrière dépasse sous la face plane de cette valeur

BANDE_LARGEUR = 20.0       # ceinture de jonction (le long de X)
BANDE_SURPLUS = 4.0        # épaisseur ajoutée sur les flancs à la jonction
TENON_COTE = 2.5           # tenon carré tourné à 45° (losange)
TENON_LONG = 6.0
JEU_TENON = 0.2            # plage Bambu 0,15–0,3 mm
PROFONDEUR_MARGE = 0.5     # logement plus profond que le tenon

ECART_PLATEAU = 10.0       # espace entre les deux moitiés sur le plateau (3MF)
# -------------------------------------------------------------------------------

OUT_DIR = Path(__file__).parent / "out"

IN_L = ECRAN_L + 2 * JEU_ECRAN
IN_W = ECRAN_W + 2 * JEU_ECRAN
IN_R = ECRAN_RAYON + JEU_ECRAN
OUT_L = IN_L + 2 * EPAISSEUR_PAROI
OUT_W = IN_W + 2 * EPAISSEUR_PAROI
Z_CAVITE = EPAISSEUR_DOS
H_CAVITE = ECRAN_H + JEU_ECRAN
H_TOTAL = EPAISSEUR_DOS + H_CAVITE + EPAISSEUR_LEVRE

# Tenons : au milieu de l'épaisseur des flancs à la jonction, à 1/3 et 2/3 de la hauteur.
TENON_Y = IN_W / 2 + (EPAISSEUR_PAROI + BANDE_SURPLUS) / 2
TENON_Z = (H_TOTAL / 3, 2 * H_TOTAL / 3)


def build_coque():
    """Coque complète (avant découpe), dos sur le plateau."""
    with BuildPart() as coque:
        with BuildSketch():
            RectangleRounded(OUT_L, OUT_W, IN_R + EPAISSEUR_PAROI)
        extrude(amount=H_TOTAL)
        Box(BANDE_LARGEUR, OUT_W + 2 * BANDE_SURPLUS, H_TOTAL, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Logement de l'écran
        with BuildSketch(Plane.XY.offset(Z_CAVITE)):
            RectangleRounded(IN_L, IN_W, IN_R)
        extrude(amount=H_CAVITE, mode=Mode.SUBTRACT)

        # Ouverture avant (vitre + tactile)
        with BuildSketch(Plane.XY.offset(Z_CAVITE + H_CAVITE)):
            RectangleRounded(IN_L - 2 * LEVRE_AVANT, IN_W - 2 * LEVRE_AVANT, IN_R - LEVRE_AVANT)
        extrude(amount=EPAISSEUR_LEVRE, mode=Mode.SUBTRACT)

        # Ouverture arrière : rebord sous la face plane uniquement
        dos_l = 2 * (DOS_PLAT_X - RECOUVREMENT_DOS)
        dos_w = 2 * (DOS_PLAT_Y - RECOUVREMENT_DOS)
        with BuildSketch():
            RectangleRounded(dos_l, dos_w, IN_R)
            # Poche arrière de l'écran laissée accessible (pas de face plane à cet endroit)
            with Locations((POCHE_X_MIN, 0)):
                Rectangle(POCHE_X_MAX - POCHE_X_MIN, IN_W, align=(Align.MIN, Align.CENTER))
        extrude(amount=EPAISSEUR_DOS, mode=Mode.SUBTRACT)
    return coque.part


def _losange(cote: float, longueur: float, y: float, z: float):
    """Prisme à section carrée tournée de 45° (losange), axe le long de +X depuis X = 0."""
    return Pos(0, y, z) * Rot(45, 0, 0) * Box(longueur, cote, cote, align=(Align.MIN, Align.CENTER, Align.CENTER))


def build_moities():
    coque = build_coque()
    gauche = coque & Box(OUT_L, OUT_W + 2 * BANDE_SURPLUS, H_TOTAL, align=(Align.MAX, Align.CENTER, Align.MIN))
    droite = coque & Box(OUT_L, OUT_W + 2 * BANDE_SURPLUS, H_TOTAL, align=(Align.MIN, Align.CENTER, Align.MIN))
    for y in (-TENON_Y, TENON_Y):
        for z in TENON_Z:
            gauche += _losange(TENON_COTE, TENON_LONG, y, z)
            droite -= _losange(TENON_COTE + 2 * JEU_TENON, TENON_LONG + PROFONDEUR_MARGE, y, z)
    return gauche, droite


def ecran_en_place():
    return Pos(0, 0, Z_CAVITE) * build_ecran()


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tools"))
    from export import export_all

    gauche, droite = build_moities()
    ecran = ecran_en_place()

    for nom, piece in (("gauche", gauche), ("droite", droite)):
        inter = (piece & ecran).volume
        print(f"  contrôle interférence {nom}/écran : {inter:.3f} mm³")

    # Plateau : les deux moitiés l'une derrière l'autre, centrées en X.
    dy = (OUT_W + 2 * BANDE_SURPLUS + ECART_PLATEAU) / 2
    disposition = {
        "coque_gauche": Location((OUT_L / 4, dy, 0)),
        "coque_droite": Location((-OUT_L / 4, -dy, 0)),
    }
    params = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float))}
    export_all(
        {"coque_gauche": gauche, "coque_droite": droite},
        "coque_xeneon",
        OUT_DIR,
        params,
        contexte={"ecran": ecran},
        disposition=disposition,
    )
