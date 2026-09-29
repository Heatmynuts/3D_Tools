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
CONGE_ARRIERE = 20.0       # congé du coin arrière-bas des flancs
COUPE_X = 142.0            # coupes du pied à X = ±142 (loin de la jonction coque à X = 0)

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
    if z_av < 0:  # l'hypoténuse coupe le bureau : triangle posé à z = 0
        y0 = y_av + (0 - z_av) * (y_ar - y_av) / (z_ar - z_av)
        profil = [(y0, 0.0), (y_ar, z_ar), (y_ar, 0.0)]
    else:
        profil = [(y_av, 0.0), (y_av, z_av), (y_ar, z_ar), (y_ar, 0.0)]
    face = make_face(Polyline(*profil, close=True)).faces()[0]
    coin = [v for v in face.vertices() if abs(v.X - y_ar) < 1e-6 and abs(v.Y) < 1e-6]
    face = face.fillet_2d(CONGE_ARRIERE, coin)      # congé généreux du coin arrière-bas
    flancs = []
    # Contour du berceau prolongé perpendiculairement à la plaque (repère écran), puis placé
    gabarit = placement() * (
        Pos(0, 0, Z_PLAQUE - 300) * extrude(RectangleRounded(B_L, B_W, B_R), amount=300 + RECOUVREMENT_FLANC)
    )
    for sx in (-1, 1):
        x0 = sx * B_L / 2 - (FLANC_LARGEUR if sx > 0 else 0)
        plan = Plane(origin=(x0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
        prisme = extrude(plan.from_local_coords(face), amount=FLANC_LARGEUR)
        flanc = prisme & gabarit
        if flanc.volume < 1:
            raise ValueError("flanc vide : profil invalide (vérifier ANGLE / ASSISE)")
        flancs.append(flanc)
    return flancs


def _joint(piece, x0: float, sens: float, peau: float, longueur: float):
    """Prisme issu de la section de `piece` au plan X = x0, réduite de `peau`, prolongé vers `sens`."""
    solides = []
    for f in piece.intersect(Plane.YZ.offset(x0)).faces():
        for g in offset(f, amount=-peau).faces():
            if g.area > 1:
                solides.append(extrude(g, amount=longueur, dir=(sens, 0, 0)))
    return solides


def build_parties():
    """3 parties : embout gauche | centre | embout droit.

    Coupes à X = ±COUPE_X, décalées de la jonction de la coque (X = 0) : le centre du pied
    ponte la jonction de la coque (joints en quinconce). Languettes sur le centre, rainures aux embouts.
    """
    pied = placement() * build_berceau()
    for f in build_flancs():
        pied += f
    grand = 4 * B_L
    pied = pied & Box(grand, grand, grand, align=(Align.CENTER, Align.CENTER, Align.MIN))  # semelle z = 0
    gauche = pied & Pos(-COUPE_X, 0, 0) * Box(grand, grand, grand, align=(Align.MAX, Align.CENTER, Align.CENTER))
    droite = pied & Pos(COUPE_X, 0, 0) * Box(grand, grand, grand, align=(Align.MIN, Align.CENTER, Align.CENTER))
    centre = pied & Box(2 * COUPE_X, grand, grand)
    lang = coque.LANGUETTE_PEAU + coque.JEU_LANGUETTE
    prof = coque.LANGUETTE_PROF + coque.PROFONDEUR_MARGE
    # Languettes sur le centre (imprimé à plat : languettes plates, sans surplomb) ;
    # rainures dans les embouts (imprimés debout : rainures inclinées à 45°, sans support).
    # Dans la plaque, la languette descend jusqu'au dos (feuillure) : sinon, centre imprimé à plat,
    # elle flotterait au-dessus du plateau (surplomb de 5 mm impossible à supporter proprement).
    y_feuillure = POCHE_W / 2 - 2.0
    for x0, sens in ((-COUPE_X, -1), (COUPE_X, 1)):
        x_min = x0 if sens > 0 else x0 - prof
        for languette in _joint(pied, x0, sens, lang, coque.LANGUETTE_PROF):
            centre += languette
        x_lang = x0 if sens > 0 else x0 - coque.LANGUETTE_PROF
        centre += pied & placement() * Pos(x_lang, 0, Z_PLAQUE) * Box(
            coque.LANGUETTE_PROF, 2 * (y_feuillure - coque.JEU_LANGUETTE), lang + 0.5,
            align=(Align.MIN, Align.CENTER, Align.MIN),
        )
        for rainure in _joint(pied, x0, sens, coque.LANGUETTE_PEAU, prof):
            if sens < 0:
                gauche -= rainure
            else:
                droite -= rainure
        feuillure = placement() * Pos(x_min, 0, Z_PLAQUE - 1) * Box(
            prof, 2 * y_feuillure, coque.LANGUETTE_PEAU + 1.5, align=(Align.MIN, Align.CENTER, Align.MIN)
        )
        if sens < 0:
            gauche -= feuillure
        else:
            droite -= feuillure
    return gauche, centre, droite


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

    gauche, centre, droite = build_parties()
    parties = {"pied_gauche": gauche, "pied_centre": centre, "pied_droite": droite}
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

    # Plateau : centre à l'arrière, les 2 embouts côte à côte à l'avant
    profondeur = max(b.size.Y for b in base)
    dy = (profondeur + ECART_PLATEAU) / 2
    # Centre : sans flanc il basculerait debout → imprimé à plat, dos de la plaque sur le plateau
    a_plat = placement().inverse()
    bb_c = (a_plat * centre).bounding_box()
    disposition = {
        "pied_centre": Pos(-bb_c.center().X, dy + 20 - bb_c.center().Y, -bb_c.min.Z) * a_plat,
        "pied_gauche": Location((COUPE_X - 20, -dy, 0)),
        "pied_droite": Location((-COUPE_X + 20, -dy, 0)),
    }
    params = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float))}
    export_all(parties, "support_xeneon", OUT_DIR, params, contexte=contexte, disposition=disposition)
