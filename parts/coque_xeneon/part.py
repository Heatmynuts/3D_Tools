"""Coque de protection (bumper) PETG pour Corsair Xeneon Edge 14,5″, en 2 moitiés.

- L'écran reste visible et tactile : lèvre avant qui recouvre seulement le cadre (bezel).
- Dos ouvert, sauf un rebord sur lequel repose la face arrière plane de l'écran.
- Coupe au plan X = 0 (écran 372 mm > plateau H2D 325 mm) : languette / rainure intérieures
  dans l'épaisseur des parois → extérieur lisse, seul un trait de joint reste visible.
- Arêtes extérieures arrondies (RAYON_ARETE), même rayon que le pied.
- Impression : face avant (côté écran) contre le plateau → plus belle finition côté visible ;
  seul le rebord arrière (caché) demande des supports (interface PLA, voir IMPRESSION.md).
- 4 trous dans le rebord arrière aux vis d'angle (aimants d'origine) pour le pied aimanté.
- Verre trempé : épaisseur et dimensions en paramètres (à renseigner avant impression).

Cotes de l'écran relevées sur le STEP officiel Corsair (voir parts/xeneon_edge/SOURCE.md).
"""

import importlib.util
import sys
from pathlib import Path

from build123d import (
    Align,
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Circle,
    Location,
    Locations,
    Mode,
    Plane,
    Pos,
    Rectangle,
    RectangleRounded,
    Rot,
    extrude,
    fillet,
    offset,
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
ACCROCHE_X = 179.0         # vis d'angle arrière (aimants de l'écran dessous) : X ±179,0 ; Y ±52,7
ACCROCHE_Y = 52.7
VITRE_X = 177.3            # zone vitrée (affichage) : X ±177,3 ; Y −53,1…+46,7
VITRE_Y_MIN = -53.1
VITRE_Y_MAX = 46.7

# ---------------------------------------------------------------- PARAMÈTRES (mm)
JEU_ECRAN = 0.3            # jeu coque/écran (plage Bambu 0,15–0,3 pour assemblages, par analogie)
EPAISSEUR_PAROI = 3.2       # 0,9 (peau) + 1,4 (rainure) + 0,9 (peau)
EPAISSEUR_DOS = 2.0
EPAISSEUR_LEVRE = 2.0
LEVRE_AVANT = 3.0          # recouvrement du cadre avant ; cadre le plus étroit = 5,2 mm
RECOUVREMENT_DOS = 2.0     # le rebord arrière dépasse sous la face plane de cette valeur

TROU_ACCROCHE_D = 12.0     # passage dans le rebord arrière pour les plots aimantés du pied

EPAISSEUR_VERRE = 0.0      # verre trempé : À RENSEIGNER avant impression (0 = pas de verre)
VERRE_L = 0.0              # longueur du verre (X) : À RENSEIGNER
VERRE_W = 0.0              # largeur du verre (Y) : À RENSEIGNER

RAYON_ARETE = 1.5          # arrondi des arêtes extérieures (commun coque / pied)
LANGUETTE_PEAU = 0.9       # matière de chaque côté de la rainure (≥ 2 largeurs de ligne, déduction)
JEU_LANGUETTE = 0.2        # plage Bambu 0,15–0,3 mm
LANGUETTE_PROF = 5.0       # longueur de la languette
PROFONDEUR_MARGE = 0.5     # rainure plus profonde que la languette

ECART_PLATEAU = 10.0       # espace entre les deux moitiés sur le plateau (3MF)
ZONE_COMMUNE = (300.0, 320.0)  # zone accessible aux deux buses H2D (wiki « printable range »)
# -------------------------------------------------------------------------------

OUT_DIR = Path(__file__).parent / "out"

IN_L = ECRAN_L + 2 * JEU_ECRAN
IN_W = ECRAN_W + 2 * JEU_ECRAN
IN_R = ECRAN_RAYON + JEU_ECRAN
OUT_L = IN_L + 2 * EPAISSEUR_PAROI
OUT_W = IN_W + 2 * EPAISSEUR_PAROI
Z_CAVITE = EPAISSEUR_DOS
H_CAVITE = ECRAN_H + EPAISSEUR_VERRE + JEU_ECRAN
H_TOTAL = EPAISSEUR_DOS + H_CAVITE + EPAISSEUR_LEVRE

OUT_R = IN_R + EPAISSEUR_PAROI


def build_coque():
    """Coque complète (avant découpe), dos sur le plateau."""
    with BuildPart() as coque:
        with BuildSketch():
            RectangleRounded(OUT_L, OUT_W, OUT_R)
        extrude(amount=H_TOTAL)
        aretes = coque.edges().group_by(Axis.Z)
        fillet(aretes[0] + aretes[-1], radius=RAYON_ARETE)

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

        # Accès aux 4 points d'accroche aimantés d'origine (sous les vis d'angle)
        with BuildSketch():
            with Locations(*[(sx * ACCROCHE_X, sy * ACCROCHE_Y) for sx in (-1, 1) for sy in (-1, 1)]):
                Circle(TROU_ACCROCHE_D / 2)
        extrude(amount=EPAISSEUR_DOS, mode=Mode.SUBTRACT)
    return coque.part


def _joint(coque, peau: float, longueur: float):
    """Prisme issu de la section de coque à X = 0, réduite de `peau`, prolongé vers +X."""
    solides = []
    for f in coque.intersect(Plane.YZ).faces():
        reduite = offset(f, amount=-peau)
        for g in reduite.faces():
            if g.area > 1:
                solides.append(extrude(g, amount=longueur, dir=(1, 0, 0)))
    return solides


def build_moities():
    coque = build_coque()
    grand = 2 * OUT_L
    gauche = coque & Box(grand, grand, grand, align=(Align.MAX, Align.CENTER, Align.CENTER))
    droite = coque & Box(grand, grand, grand, align=(Align.MIN, Align.CENTER, Align.CENTER))
    for languette in _joint(coque, LANGUETTE_PEAU + JEU_LANGUETTE, LANGUETTE_PROF):
        gauche += languette
    for rainure in _joint(coque, LANGUETTE_PEAU, LANGUETTE_PROF + PROFONDEUR_MARGE):
        droite -= rainure
    return gauche, droite


def ecran_en_place():
    return Pos(0, 0, Z_CAVITE) * build_ecran()


def verre_en_place():
    return Pos(0, 0, Z_CAVITE + ECRAN_H) * Box(
        VERRE_L, VERRE_W, EPAISSEUR_VERRE, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def controles_verre_et_vue() -> None:
    ouv_l = IN_L - 2 * LEVRE_AVANT
    ouv_w = IN_W - 2 * LEVRE_AVANT
    vitre_l = 2 * VITRE_X
    vitre_w = VITRE_Y_MAX - VITRE_Y_MIN
    print(f"  zone vitrée écran : {vitre_l:.1f} x {vitre_w:.1f} mm")
    print(f"  ouverture coque   : {ouv_l:.1f} x {ouv_w:.1f} mm")
    marges = (ouv_l / 2 - VITRE_X, VITRE_Y_MIN + ouv_w / 2, ouv_w / 2 - VITRE_Y_MAX)
    etat = "100 % visible" if min(marges) >= 0 else "⚠ zone vitrée masquée"
    print(f"  marges côtés / bas / haut : {marges[0]:.2f} / {marges[1]:.2f} / {marges[2]:.2f} mm → {etat}")
    if EPAISSEUR_VERRE <= 0 or VERRE_L <= 0 or VERRE_W <= 0:
        print("  ⚠ VERRE TREMPÉ NON RENSEIGNÉ : EPAISSEUR_VERRE, VERRE_L, VERRE_W à saisir avant impression")
        print(f"    critères : {vitre_l:.1f} ≤ L ≤ {IN_L:.1f} mm ; {vitre_w:.1f} ≤ l ≤ {IN_W:.1f} mm")
        return
    if VERRE_L < vitre_l or VERRE_W < vitre_w:
        print("  ⚠ verre plus petit que la zone vitrée : écran partiellement non protégé")
    if VERRE_L > IN_L or VERRE_W > IN_W:
        print("  ⚠ verre plus grand que le logement : ne rentre pas dans la coque")


def orienter_impression(piece, cible_x: float, cible_y: float) -> Location:
    """Retourne la pièce face avant sur le plateau (180° autour de X) et la centre sur (x, y)."""
    retournee = Rot(180, 0, 0) * piece
    bb = retournee.bounding_box()
    return Pos(cible_x - bb.center().X, cible_y - bb.center().Y, -bb.min.Z) * Rot(180, 0, 0)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tools"))
    from export import export_all

    gauche, droite = build_moities()
    ecran = ecran_en_place()

    contexte = {"ecran": ecran}
    if EPAISSEUR_VERRE > 0 and VERRE_L > 0 and VERRE_W > 0:
        contexte["verre"] = verre_en_place()
    for nom, piece in (("gauche", gauche), ("droite", droite)):
        for c_nom, c in contexte.items():
            print(f"  contrôle interférence {nom}/{c_nom} : {(piece & c).volume:.3f} mm³")
    controles_verre_et_vue()

    # Plateau : face avant en bas, moitiés côte à côte en Y, centrées dans la zone commune aux 2 buses.
    dy = (OUT_W + ECART_PLATEAU) / 2
    disposition = {
        "coque_gauche": orienter_impression(gauche, 0, dy),
        "coque_droite": orienter_impression(droite, 0, -dy),
    }
    plateau = {nom: loc * p for nom, p in (("coque_gauche", gauche), ("coque_droite", droite)) for loc in [disposition[nom]]}
    bbs = [pc.bounding_box() for pc in plateau.values()]
    ex = max(b.max.X for b in bbs) - min(b.min.X for b in bbs)
    ey = max(b.max.Y for b in bbs) - min(b.min.Y for b in bbs)
    tient = ex <= ZONE_COMMUNE[0] and ey <= ZONE_COMMUNE[1]
    print(f"  plateau : {ex:.1f} x {ey:.1f} mm dans zone commune {ZONE_COMMUNE} → {'OK' if tient else '⚠ DÉPASSE'}")

    params = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float))}
    export_all(
        {"coque_gauche": gauche, "coque_droite": droite},
        "coque_xeneon",
        OUT_DIR,
        params,
        contexte=contexte,
        disposition=disposition,
    )
    # Vue « plateau » : pièces en position d'impression (face avant contre le plateau).
    export_all(plateau, "coque_xeneon_plateau", Path(__file__).parent / "plateau" / "out", params)
