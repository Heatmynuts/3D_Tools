"""Pied incliné aimanté pour Corsair Xeneon Edge dans sa coque — forme inspirée du pied d'origine.

Forme (d'après les photos du pied Corsair, cotes non mesurées → dessin à partir de l'écran et de la coque) :
- 2 flancs ajourés aux extrémités, qui portent les 4 plots aimantés (mêmes points d'accroche que
  l'origine : aimants de l'écran sous les vis d'angle, X ±179,0 ; Y ±52,7 sur le STEP officiel) ;
- un rail bas continu sur toute la longueur, qui porte le bord inférieur de la coque ;
- un panneau arrière continu avec une échancrure centrale pour le câble.
Les plots traversent les trous Ø12 de la coque (ergots de centrage) et s'arrêtent à 0,2 mm de l'écran.

Longueur ≈ 370 mm > plateau H2D : 2 parties, jonction décalée de l'échancrure, tenons en losange (45°).
Impression : debout, base sur le plateau ; faces à 45° au plus (limite sans support, wiki Bambu).
"""

import importlib.util
import math
import sys
from pathlib import Path

from build123d import (
    Align,
    Box,
    Cylinder,
    Location,
    Plane,
    Polyline,
    Pos,
    Rot,
    extrude,
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
FLANC_LARGEUR = 14.0       # épaisseur des flancs d'extrémité (le long de l'écran)
FLANC_CADRE = 7.0          # largeur de matière autour de l'ajour des flancs
EPAISSEUR_PLAQUE = 5.0     # plaque inclinée sous la coque (dans les flancs)
REBORD_HAUTEUR = 8.0       # rebord qui retient le bord bas de la coque
REBORD_EPAISSEUR = 5.0
RAIL_PROFONDEUR = 15.0     # largeur du rail sous le bord bas de la coque
JEU_PIED = 0.5             # jeu entre rebord et bord de coque
MARGE_HAUT = 4.0           # plaque au-delà du plot haut

PANNEAU_HAUTEUR = 35.0     # panneau arrière continu
PANNEAU_EPAISSEUR = 5.0
ENCOCHE_RAYON = 14.0       # échancrure centrale (passage de câble)

JEU_PLOT = 0.2             # jeu plot / trou de coque (plage Bambu 0,15–0,3)
ECART_ECRAN = 0.2          # le plot s'arrête à cette distance du dos de l'écran
AIMANT_D = 8.0             # aimant néodyme disque : À ADAPTER aux aimants achetés
AIMANT_H = 3.0
JEU_AIMANT = 0.1

DECALAGE_JONCTION = 60.0   # jonction à X = −60 (hors échancrure)
TENON_COTE = 2.0           # tenon carré tourné à 45°
TENON_LONG = 6.0
JEU_TENON = 0.2            # plage Bambu 0,15–0,3
PROFONDEUR_MARGE = 0.5

ECART_PLATEAU = 15.0
# -------------------------------------------------------------------------------

OUT_DIR = Path(__file__).parent / "out"
PLOT_D = coque.TROU_ACCROCHE_D - 2 * JEU_PLOT
Y_BAS = -(coque.OUT_W / 2 + JEU_PIED)       # bord bas de la coque (repère écran)
Y_HAUT = coque.ACCROCHE_Y + PLOT_D / 2 + MARGE_HAUT
Z_DOS = -coque.EPAISSEUR_DOS                 # dos extérieur de la coque (repère écran)
Z_PLAQUE = Z_DOS - EPAISSEUR_PLAQUE
X_BOUT = coque.ACCROCHE_X + FLANC_LARGEUR / 2


def _tourne(y: float, z: float) -> tuple[float, float]:
    a = math.radians(ANGLE)
    return (y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))


PROFIL_FLANC = [
    (Y_BAS - REBORD_EPAISSEUR, Z_PLAQUE),
    (Y_BAS - REBORD_EPAISSEUR, REBORD_HAUTEUR),
    (Y_BAS, REBORD_HAUTEUR),
    (Y_BAS, Z_DOS),
    (Y_HAUT, Z_DOS),
    (Y_HAUT, Z_PLAQUE),
]
Z_DECALAGE = -min(_tourne(y, z)[1] for y, z in PROFIL_FLANC)


def vers_bureau(y: float, z: float) -> tuple[float, float]:
    """Repère écran (dos de l'écran à z = 0, bas en −y) → bureau (z = 0)."""
    py, pz = _tourne(y, z)
    return (py, pz + Z_DECALAGE)


def placement() -> Location:
    return Pos(0, 0, Z_DECALAGE) * Rot(ANGLE, 0, 0)


def _prisme(points_yz: list[tuple[float, float]], x0: float, longueur: float):
    """Extrude un profil (y, z) du repère bureau le long de +X depuis x0."""
    plan = Plane(origin=(x0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    return extrude(plan.from_local_coords(make_face(Polyline(*points_yz, close=True))), amount=longueur)


def _profil_flanc_bureau() -> list[tuple[float, float]]:
    pts = [vers_bureau(y, z) for y, z in PROFIL_FLANC]
    pts.append((pts[-1][0], 0.0))               # descente arrière jusqu'au bureau
    return pts


Y_ARRIERE = _profil_flanc_bureau()[-1][0]      # face arrière des flancs (repère bureau)


def build_flanc(x: float):
    pts = _profil_flanc_bureau()
    plan = Plane(origin=(x - FLANC_LARGEUR / 2, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    face = make_face(Polyline(*pts, close=True))
    ajour = offset(face, amount=-FLANC_CADRE)
    flanc = extrude(plan.from_local_coords(face), amount=FLANC_LARGEUR)
    if ajour.area > 0:
        flanc -= extrude(plan.from_local_coords(ajour), amount=FLANC_LARGEUR)
    loc = placement()
    h_plot = -ECART_ECRAN - Z_DOS
    for y in (-coque.ACCROCHE_Y, coque.ACCROCHE_Y):
        flanc += loc * (Pos(x, y, Z_DOS) * Cylinder(PLOT_D / 2, h_plot, align=(Align.CENTER, Align.CENTER, Align.MIN)))
        flanc -= loc * (
            Pos(x, y, -ECART_ECRAN - AIMANT_H)
            * Cylinder(AIMANT_D / 2 + JEU_AIMANT, AIMANT_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        )
    return flanc


def build_rail():
    profil = [
        (Y_BAS - REBORD_EPAISSEUR, Z_PLAQUE),
        (Y_BAS - REBORD_EPAISSEUR, REBORD_HAUTEUR),
        (Y_BAS, REBORD_HAUTEUR),
        (Y_BAS, Z_DOS),
        (Y_BAS + RAIL_PROFONDEUR, Z_DOS),
        (Y_BAS + RAIL_PROFONDEUR, Z_PLAQUE),
    ]
    rail = _prisme([vers_bureau(y, z) for y, z in profil], -X_BOUT, 2 * X_BOUT)
    # Dégagement pour la ceinture de jonction de la coque (plus large de BANDE_SURPLUS)
    ceinture = Box(
        coque.BANDE_LARGEUR + 2 * JEU_PIED,
        coque.OUT_W + 2 * (coque.BANDE_SURPLUS + JEU_PIED),
        coque.H_TOTAL,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    return rail - placement() * Pos(0, 0, -coque.Z_CAVITE) * ceinture


def build_panneau():
    panneau = Pos(0, Y_ARRIERE - PANNEAU_EPAISSEUR / 2, 0) * Box(
        2 * X_BOUT, PANNEAU_EPAISSEUR, PANNEAU_HAUTEUR, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    encoche = Pos(0, Y_ARRIERE, 0) * Rot(90, 0, 0) * Cylinder(ENCOCHE_RAYON, 4 * PANNEAU_EPAISSEUR)
    return panneau - encoche


def _losange(cote: float, longueur: float, x0: float, y: float, z: float):
    return Pos(x0, y, z) * Rot(45, 0, 0) * Box(longueur, cote, cote, align=(Align.MIN, Align.CENTER, Align.CENTER))


def build_parties():
    pied = build_rail() + build_panneau() + build_flanc(-coque.ACCROCHE_X) + build_flanc(coque.ACCROCHE_X)
    xj = -DECALAGE_JONCTION
    grand = 4 * X_BOUT
    gauche = pied & Pos(xj, 0, 0) * Box(grand, grand, grand, align=(Align.MAX, Align.CENTER, Align.MIN))
    droite = pied & Pos(xj, 0, 0) * Box(grand, grand, grand, align=(Align.MIN, Align.CENTER, Align.MIN))
    # Tenons : au centre du rebord du rail et au centre du panneau
    y_rail, z_rail = vers_bureau(Y_BAS - REBORD_EPAISSEUR / 2, (Z_PLAQUE + REBORD_HAUTEUR) / 2)
    points = [(y_rail, z_rail), (Y_ARRIERE - PANNEAU_EPAISSEUR / 2, PANNEAU_HAUTEUR / 2)]
    for y, z in points:
        gauche += _losange(TENON_COTE, TENON_LONG, xj, y, z)
        droite -= _losange(TENON_COTE + 2 * JEU_TENON, TENON_LONG + PROFONDEUR_MARGE, xj, y, z)
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
    cg = ecran.center()
    base_y = (vers_bureau(Y_BAS - REBORD_EPAISSEUR, Z_PLAQUE)[0], Y_ARRIERE)
    print(f"  stabilité : centre écran y={cg.Y:.1f} ; base y {base_y[0]:.1f} → {base_y[1]:.1f}")
    print(f"  écart plot/écran : {gauche.distance_to(ecran):.2f} mm")

    # Plateau : 2 parties debout, l'une derrière l'autre
    profondeur = Y_ARRIERE - base_y[0]
    disposition = {
        "pied_gauche": Location((X_BOUT / 2, (profondeur + ECART_PLATEAU) / 2, 0)),
        "pied_droite": Location((-X_BOUT / 2 + DECALAGE_JONCTION / 2, -(profondeur + ECART_PLATEAU) / 2, 0)),
    }
    params = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float))}
    export_all(parties, "support_xeneon", OUT_DIR, params, contexte=contexte, disposition=disposition)
