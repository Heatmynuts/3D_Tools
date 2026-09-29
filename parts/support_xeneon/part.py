"""Pied incliné aimanté pour Corsair Xeneon Edge dans sa coque (2 pieds identiques).

Principe :
- Mêmes points d'accroche que le pied d'origine : les aimants de l'écran sous les 4 vis d'angle
  (X ±179,0 ; Y ±52,7 sur le STEP officiel). Chaque pied porte 2 plots aimantés qui traversent
  les trous de la coque et viennent au contact du dos de l'écran.
- Les plots dans les trous de la coque servent d'ergots de centrage (pas de glissement latéral).
- Un rebord bas retient le bord inférieur de la coque : le poids repose dessus, les aimants maintiennent.
- Inclinaison paramétrable ; le pied d'origine tient l'écran à 45° (Corsair).
- Impression : debout, base sur le plateau (face à 45° : limite des surplombs sans support, wiki Bambu).
"""

import importlib.util
import math
import sys
from pathlib import Path

from build123d import Align, Cylinder, Location, Plane, Polyline, Pos, Rot, extrude, make_face

ROOT = Path(__file__).resolve().parents[2]


def _charger(nom: str, chemin: Path):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coque = _charger("coque_xeneon", ROOT / "parts" / "coque_xeneon" / "part.py")

# ---------------------------------------------------------------- PARAMÈTRES (mm, °)
ANGLE = 45.0               # inclinaison de l'écran par rapport au bureau (origine : 45°)
PIED_LARGEUR = 24.0        # épaisseur de chaque pied (le long de l'écran)
EPAISSEUR_PLAQUE = 4.0     # plaque inclinée sous la coque
REBORD_HAUTEUR = 8.0       # rebord qui retient le bord bas de la coque
REBORD_EPAISSEUR = 4.0
JEU_PIED = 0.5             # jeu entre rebord et bord de coque
MARGE_HAUT = 4.0           # plaque au-delà du plot haut

JEU_PLOT = 0.2             # jeu plot / trou de coque (plage Bambu 0,15–0,3)
ECART_ECRAN = 0.2          # le plot s'arrête à cette distance du dos de l'écran
AIMANT_D = 8.0             # aimant néodyme disque : À ADAPTER aux aimants achetés
AIMANT_H = 3.0
JEU_AIMANT = 0.1           # logement légèrement plus grand que l'aimant

ECART_PLATEAU = 15.0
# -------------------------------------------------------------------------------

OUT_DIR = Path(__file__).parent / "out"
PLOT_D = coque.TROU_ACCROCHE_D - 2 * JEU_PLOT
Y_BAS = -(coque.OUT_W / 2 + JEU_PIED)                   # bord bas de la coque (repère écran)
Y_HAUT = coque.ACCROCHE_Y + PLOT_D / 2 + MARGE_HAUT
Z_DOS = -coque.EPAISSEUR_DOS                             # dos extérieur de la coque (repère écran)


def _vers_monde(y: float, z: float) -> tuple[float, float]:
    """Repère écran (dos de l'écran à z = 0, bas en −y) → repère bureau, avant décalage vertical."""
    a = math.radians(ANGLE)
    return (y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))


def _profil_ecran() -> list[tuple[float, float]]:
    z_plaque = Z_DOS - EPAISSEUR_PLAQUE
    return [
        (Y_BAS - REBORD_EPAISSEUR, z_plaque),   # avant, bas
        (Y_BAS - REBORD_EPAISSEUR, REBORD_HAUTEUR),
        (Y_BAS, REBORD_HAUTEUR),
        (Y_BAS, Z_DOS),
        (Y_HAUT, Z_DOS),
        (Y_HAUT, z_plaque),                      # arrière, haut de la plaque
    ]


def placement() -> Location:
    """Location qui place un objet du repère écran dans le repère bureau (bureau à z = 0)."""
    z_min = min(_vers_monde(y, z)[1] for y, z in _profil_ecran())
    return Pos(0, 0, -z_min) * Rot(ANGLE, 0, 0)


def build_pied(x: float):
    pts = _profil_ecran()
    monde = [_vers_monde(y, z) for y, z in pts]
    z_min = min(p[1] for p in monde)
    monde = [(py, pz - z_min) for py, pz in monde]
    # Descente verticale jusqu'au bureau depuis l'arrière de la plaque
    monde.append((monde[-1][0], 0.0))
    if monde[0][1] > 1e-6:
        monde.append((monde[0][0], 0.0))
    profil = make_face(Polyline(*monde, close=True))
    plan = Plane(origin=(x - PIED_LARGEUR / 2, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    pied = extrude(plan.from_local_coords(profil), amount=PIED_LARGEUR)

    # Plots aimantés (repère écran) puis placement
    h_plot = -ECART_ECRAN - Z_DOS
    loc = placement()
    for y in (-coque.ACCROCHE_Y, coque.ACCROCHE_Y):
        plot = Pos(x, y, Z_DOS) * Cylinder(PLOT_D / 2, h_plot, align=(Align.CENTER, Align.CENTER, Align.MIN))
        logement = Pos(x, y, -ECART_ECRAN - AIMANT_H) * Cylinder(
            AIMANT_D / 2 + JEU_AIMANT, AIMANT_H, align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        pied = pied + loc * plot
        pied = pied - loc * logement
    return pied


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tools"))
    from export import export_all

    loc = placement()
    vers_coque = loc * Pos(0, 0, -coque.Z_CAVITE)   # repère coque (dos coque à z = 0) → bureau
    gauche, droite = coque.build_moities()
    ecran = vers_coque * coque.ecran_en_place()
    contexte = {"coque_gauche": vers_coque * gauche, "coque_droite": vers_coque * droite, "ecran": ecran}

    pieds = {"pied_gauche": build_pied(-coque.ACCROCHE_X), "pied_droit": build_pied(coque.ACCROCHE_X)}
    for nom, p in pieds.items():
        print(f"  {nom} : valide={p.is_valid}")
        for c_nom, c in contexte.items():
            v = (p & c).volume
            if v > 1e-3:
                print(f"    ⚠ interférence {nom}/{c_nom} : {v:.3f} mm³")
    print(f"  plot Ø{PLOT_D:.1f} mm dans trou Ø{coque.TROU_ACCROCHE_D:.1f} mm ; logement aimant Ø{AIMANT_D + 2 * JEU_AIMANT:.1f} x {AIMANT_H:.1f} mm")

    # Plateau : les 2 pieds debout côte à côte près du centre
    dx = (PIED_LARGEUR + ECART_PLATEAU) / 2
    disposition = {
        "pied_gauche": Location((coque.ACCROCHE_X - dx, 0, 0)),
        "pied_droit": Location((-coque.ACCROCHE_X + dx, 0, 0)),
    }
    params = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float))}
    export_all(pieds, "support_xeneon", OUT_DIR, params, contexte=contexte, disposition=disposition)
