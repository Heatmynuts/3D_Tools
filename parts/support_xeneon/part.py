"""Pied incliné aimanté pour Corsair Xeneon Edge dans sa coque — berceau continu.

Design (cohérent avec la coque, même langage de formes) :
- Berceau : plaque inclinée sous toute la coque + rebord périphérique qui l'entoure, au même
  contour que la coque (mêmes rayons d'angle + jeu + épaisseur), dessus affleurant la face avant.
- 2 flancs triangulaires aux extrémités, découpés au contour du berceau (aucun angle qui dépasse).
- 4 plots aimantés aux points d'accroche d'origine (aimants de l'écran sous les vis d'angle,
  X ±179,0 ; Y ±52,7 sur le STEP officiel) : ils traversent les trous Ø12 de la coque.
- Fenêtre dans la plaque face à la poche arrière de l'écran (X 27,1…114).
- Arêtes extérieures arrondies au même rayon que la coque.
- 2 parties : jonction à X = 0 (alignée sur celle de la coque), languette / rainure intérieures.
- Impression : debout, base sur le plateau ; faces inclinées à 45° (limite sans support, wiki Bambu).
Cotes du pied d'origine non mesurées : proportions dérivées de l'écran et de la coque.
"""

import importlib.util
import math
import sys
from pathlib import Path

from build123d import (
    Align,
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    Location,
    Locations,
    Mode,
    Plane,
    Polyline,
    Pos,
    Rectangle,
    RectangleRounded,
    Rot,
    extrude,
    fillet,
    make_face,
    offset,
)

ROOT = Path(__file__).resolve().parents[2]


def _charger(nom: str, chemin: Path):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coque = _charger("coque_xeneon", ROOT / "parts" / "coque_xeneon" / "part.py")

# ---------------------------------------------------------------- PARAMÈTRES (mm, °)
ANGLE = 45.0               # inclinaison de l'écran par rapport au bureau (origine : 45°, Corsair)
EPAISSEUR_PLAQUE = 4.0     # plaque inclinée sous la coque
REBORD_EPAISSEUR = 3.2     # rebord périphérique (0,9 + 1,4 + 0,9 pour la rainure)
JEU_PIED = 0.5             # jeu coque / berceau
FLANC_LARGEUR = 18.0       # flancs d'extrémité (le long de l'écran)
RECOUVREMENT_FLANC = 1.0   # pénétration du flanc dans la plaque (fusion)
ASSISE = 2.0               # hauteur rabotée sous l'arête avant → semelle plate (adhérence, stabilité)

JEU_PLOT = 0.2             # jeu plot / trou de coque (plage Bambu 0,15–0,3)
ECART_ECRAN = 0.2          # le plot s'arrête à cette distance du dos de l'écran
AIMANT_D = 8.0             # aimant néodyme disque : À ADAPTER aux aimants achetés
AIMANT_H = 3.0
JEU_AIMANT = 0.1

ECART_PLATEAU = 15.0
# -------------------------------------------------------------------------------

OUT_DIR = Path(__file__).parent / "out"
PLOT_D = coque.TROU_ACCROCHE_D - 2 * JEU_PLOT
Z_DOS = -coque.Z_CAVITE                          # dos extérieur de la coque (repère écran)
Z_AVANT = coque.H_TOTAL - coque.Z_CAVITE         # face avant de la coque (repère écran)
Z_PLAQUE = Z_DOS - EPAISSEUR_PLAQUE
POCHE_L = coque.OUT_L + 2 * JEU_PIED
POCHE_W = coque.OUT_W + 2 * JEU_PIED
POCHE_R = coque.OUT_R + JEU_PIED
B_L = POCHE_L + 2 * REBORD_EPAISSEUR
B_W = POCHE_W + 2 * REBORD_EPAISSEUR
B_R = POCHE_R + REBORD_EPAISSEUR


def _tourne(y: float, z: float) -> tuple[float, float]:
    a = math.radians(ANGLE)
    return (y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))


# Point le plus bas : arête avant-basse du berceau → posée sur le bureau
Z_DECALAGE = -_tourne(-B_W / 2, Z_PLAQUE)[1] - ASSISE


def placement() -> Location:
    """Repère écran (dos de l'écran à z = 0, bas en −y) → bureau (z = 0)."""
    return Pos(0, 0, Z_DECALAGE) * Rot(ANGLE, 0, 0)


def vers_bureau(y: float, z: float) -> tuple[float, float]:
    py, pz = _tourne(y, z)
    return (py, pz + Z_DECALAGE)


def build_berceau():
    """Berceau dans le repère écran."""
    with BuildPart() as b:
        with BuildSketch(Plane.XY.offset(Z_PLAQUE)):
            RectangleRounded(B_L, B_W, B_R)
        extrude(amount=Z_AVANT - Z_PLAQUE)
        aretes = b.edges().group_by(Axis.Z)
        fillet(aretes[0] + aretes[-1], radius=coque.RAYON_ARETE)
        # Logement de la coque
        with BuildSketch(Plane.XY.offset(Z_DOS)):
            RectangleRounded(POCHE_L, POCHE_W, POCHE_R)
        extrude(amount=Z_AVANT - Z_DOS, mode=Mode.SUBTRACT)
        # Fenêtre face à la poche arrière de l'écran
        with BuildSketch(Plane.XY.offset(Z_PLAQUE)):
            with Locations((coque.POCHE_X_MIN, 0)):
                Rectangle(
                    coque.POCHE_X_MAX - coque.POCHE_X_MIN,
                    2 * coque.DOS_PLAT_Y,
                    align=(Align.MIN, Align.CENTER),
                )
        extrude(amount=EPAISSEUR_PLAQUE, mode=Mode.SUBTRACT)
        # Plots aimantés
        with BuildSketch(Plane.XY.offset(Z_DOS)):
            with Locations(*[(sx * coque.ACCROCHE_X, sy * coque.ACCROCHE_Y) for sx in (-1, 1) for sy in (-1, 1)]):
                RectangleRounded(PLOT_D, PLOT_D, PLOT_D / 2 - 0.01)
        extrude(amount=-ECART_ECRAN - Z_DOS)
        with BuildSketch(Plane.XY.offset(-ECART_ECRAN - AIMANT_H)):
            with Locations(*[(sx * coque.ACCROCHE_X, sy * coque.ACCROCHE_Y) for sx in (-1, 1) for sy in (-1, 1)]):
                RectangleRounded(AIMANT_D + 2 * JEU_AIMANT, AIMANT_D + 2 * JEU_AIMANT, AIMANT_D / 2 + JEU_AIMANT - 0.01)
        extrude(amount=AIMANT_H, mode=Mode.SUBTRACT)
    return b.part


def build_flancs():
    """Flancs triangulaires (repère bureau), découpés au contour du berceau."""
    y_av, z_av = vers_bureau(-B_W / 2, Z_PLAQUE + RECOUVREMENT_FLANC)
    y_ar, z_ar = vers_bureau(B_W / 2, Z_PLAQUE + RECOUVREMENT_FLANC)
    z_bas = min(0.0, z_av) - 1.0          # sous le bureau ; rogné ensuite à z = 0
    profil = [(y_av, z_bas), (y_av, z_av), (y_ar, z_ar), (y_ar, z_bas)]
    flancs = []
    # Contour du berceau prolongé perpendiculairement à la plaque (repère écran), puis placé
    gabarit = placement() * (
        Pos(0, 0, Z_PLAQUE - 300) * extrude(RectangleRounded(B_L, B_W, B_R), amount=300 + RECOUVREMENT_FLANC)
    )
    for sx in (-1, 1):
        x0 = sx * B_L / 2 - (FLANC_LARGEUR if sx > 0 else 0)
        plan = Plane(origin=(x0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
        prisme = extrude(plan.from_local_coords(make_face(Polyline(*profil, close=True))), amount=FLANC_LARGEUR)
        flanc = prisme & gabarit
        if flanc.volume < 1:
            raise ValueError("flanc vide : profil invalide (vérifier ANGLE / ASSISE)")
        flancs.append(flanc)
    return flancs


def _joint(piece, peau: float, longueur: float):
    solides = []
    for f in piece.intersect(Plane.YZ).faces():
        for g in offset(f, amount=-peau).faces():
            if g.area > 1:
                solides.append(extrude(g, amount=longueur, dir=(1, 0, 0)))
    return solides


def build_parties():
    pied = placement() * build_berceau()
    for f in build_flancs():
        pied += f
    grand = 4 * B_L
    pied = pied & Box(grand, grand, grand, align=(Align.CENTER, Align.CENTER, Align.MIN))  # semelle z = 0
    gauche = pied & Box(grand, grand, grand, align=(Align.MAX, Align.CENTER, Align.CENTER))
    droite = pied & Box(grand, grand, grand, align=(Align.MIN, Align.CENTER, Align.CENTER))
    for languette in _joint(pied, coque.LANGUETTE_PEAU + coque.JEU_LANGUETTE, coque.LANGUETTE_PROF):
        gauche += languette
    for rainure in _joint(pied, coque.LANGUETTE_PEAU, coque.LANGUETTE_PROF + coque.PROFONDEUR_MARGE):
        droite -= rainure
    return gauche, droite


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tools"))
    from export import export_all

    vers_coque = placement() * Pos(0, 0, -coque.Z_CAVITE)   # repère coque → bureau
    c_gauche, c_droite = coque.build_moities()
    contexte = {
        "coque_gauche": vers_coque * c_gauche,
        "coque_droite": vers_coque * c_droite,
        "ecran": vers_coque * coque.ecran_en_place(),
    }

    gauche, droite = build_parties()
    parties = {"pied_gauche": gauche, "pied_droite": droite}
    for nom, p in parties.items():
        print(f"  {nom} : valide={p.is_valid}, solides={len(p.solids())}")
        for c_nom, c in contexte.items():
            v = (p & c).volume
            if v > 1e-3:
                print(f"    ⚠ interférence {nom}/{c_nom} : {v:.3f} mm³")
    ecran = contexte["ecran"]
    base = [b.bounding_box() for b in parties.values()]
    print(
        f"  stabilité : centre écran y={ecran.center().Y:.1f} ; base y "
        f"{min(b.min.Y for b in base):.1f} → {max(b.max.Y for b in base):.1f}"
    )
    print(f"  écart plot/écran : {min(p.distance_to(ecran) for p in parties.values()):.2f} mm")

    profondeur = max(b.size.Y for b in base)
    disposition = {
        "pied_gauche": Location((B_L / 4, (profondeur + ECART_PLATEAU) / 2, 0)),
        "pied_droite": Location((-B_L / 4, -(profondeur + ECART_PLATEAU) / 2, 0)),
    }
    params = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float))}
    export_all(parties, "support_xeneon", OUT_DIR, params, contexte=contexte, disposition=disposition)
