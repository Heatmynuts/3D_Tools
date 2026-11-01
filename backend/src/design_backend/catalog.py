"""Concept component vocabulary.

Single source of truth: injected into the engineer prompt and served to the
frontend ConceptBuilder (defaults + zone names). Units: mm and degrees.

World frame: Z up, desk plane z=0, X = width (left→right as seen by the user),
Y = depth, the user stands on the -Y side (front faces point to -Y).
"""

from __future__ import annotations

from typing import Any

CATALOG: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------ references
    "ref_box": {
        "category": "reference",
        "description": "Objet réel existant (fantôme, non fabriqué), approximé par un parallélépipède. "
        "Origine = centre de la face inférieure. Face avant (écran, façade) orientée vers -Y.",
        "params": {
            "size": {"default": [100, 20, 60], "doc": "[largeur X, épaisseur Y, hauteur Z]"},
            "tilt_deg": {"default": 0, "doc": "inclinaison vers l'arrière (bascule autour de l'arête inférieure arrière). 0 = vertical"},
            "corner_radius": {"default": 0, "doc": "rayon des arêtes verticales"},
            "display_bezel": {"default": 0, "doc": "si > 0 : dessine une zone d'affichage sur la face avant, avec cette bordure"},
        },
        "zones": ["corps", "face_avant"],
    },
    "ref_cylinder": {
        "category": "reference",
        "description": "Objet réel cylindrique (tube, axe, bouteille). Origine = centre de la base, axe selon Z local.",
        "params": {
            "d": {"default": 12, "doc": "diamètre"},
            "length": {"default": 100, "doc": "longueur"},
        },
        "zones": ["corps"],
    },
    # ------------------------------------------------------------ design parts
    "block": {
        "category": "forme",
        "description": "Bloc / plaque. Origine = centre de la face inférieure.",
        "params": {
            "size": {"default": [40, 30, 5], "doc": "[X, Y, Z]"},
            "corner_radius": {"default": 0, "doc": "rayon des arêtes verticales"},
        },
        "zones": ["corps"],
    },
    "frame": {
        "category": "forme",
        "description": "Cadre périphérique qui enveloppe les bords d'un ref_box (via `wraps`). "
        "Profil en U : paroi autour de la tranche + lèvre qui recouvre la face avant + lèvre arrière. "
        "Construit dans le repère de l'objet enveloppé (suit son inclinaison). "
        "Si le côté 'bas' est couvert, surélève l'objet (position z ≥ wall + clearance) pour que le cadre ne traverse pas le bureau.",
        "params": {
            "wall": {"default": 2.5, "doc": "épaisseur de paroi"},
            "clearance": {"default": 0.3, "doc": "jeu entre l'objet et le cadre"},
            "front_lip": {"default": 3, "doc": "recouvrement de la face avant (0 = aucun)"},
            "back_lip": {"default": 3, "doc": "recouvrement de la face arrière (0 = dos ouvert)"},
            "sides": {"default": ["haut", "bas", "gauche", "droite"], "doc": "côtés couverts"},
            "mode": {"default": "perimetre", "doc": "'perimetre' (côtés complets) ou 'coins' (protège-coins seuls)"},
            "corner_length": {"default": 25, "doc": "longueur de chaque branche en mode 'coins'"},
        },
        "zones": ["paroi_haut", "paroi_bas", "paroi_gauche", "paroi_droite",
                  "levre_avant", "levre_arriere", "coin_haut_gauche", "coin_haut_droite",
                  "coin_bas_gauche", "coin_bas_droite"],
    },
    "shell": {
        "category": "forme",
        "description": "Boîtier creux (corps + couvercle en haut). Soit `wraps` un ref_box (taille intérieure = objet + jeu), "
        "soit `inner_size` explicite. Origine = centre de la face inférieure. "
        "Avec `wraps`, l'objet repose sur le fond : surélève l'objet de floor + clearance pour que le boîtier soit posé sur le bureau.",
        "params": {
            "inner_size": {"default": [60, 40, 20], "doc": "[X, Y, Z] intérieur si pas de wraps"},
            "wall": {"default": 2, "doc": "épaisseur des parois"},
            "floor": {"default": 2, "doc": "épaisseur du fond"},
            "clearance": {"default": 0.5, "doc": "jeu autour de l'objet enveloppé"},
            "corner_radius": {"default": 3, "doc": "rayon extérieur des arêtes verticales"},
            "lid": {"default": "separe", "doc": "'aucun', 'separe', 'clipse', 'visse', 'coulissant'"},
            "lid_thickness": {"default": 2, "doc": "épaisseur du couvercle"},
            "open_view": {"default": 0, "doc": "écarte visuellement le couvercle de N mm (vue éclatée)"},
        },
        "zones": ["paroi_avant", "paroi_arriere", "paroi_gauche", "paroi_droite", "fond", "couvercle"],
    },
    "stand": {
        "category": "forme",
        "description": "Support posé sur le bureau qui maintient un ref_box (via `supports`), positionné automatiquement "
        "d'après l'objet et son inclinaison.",
        "params": {
            "style": {"default": "cale", "doc": "'cale' (prisme plein derrière l'objet), 'bequille' (pattes fines), "
                      "'socle' (base dans laquelle l'objet s'insère)"},
            "width_ratio": {"default": 0.6, "doc": "largeur du support / largeur de l'objet"},
            "support_height": {"default": 0.5, "doc": "hauteur d'appui dans le dos, en fraction de la hauteur de l'objet"},
            "thickness": {"default": 4, "doc": "épaisseur des pattes (bequille)"},
            "count": {"default": 2, "doc": "nombre de pattes (bequille)"},
            "base_depth": {"default": 60, "doc": "profondeur du socle"},
            "base_height": {"default": 12, "doc": "hauteur du socle"},
            "clearance": {"default": 0.5, "doc": "jeu autour de l'objet dans le socle"},
        },
        "zones": ["appui", "base", "pattes"],
    },
    "cylinder": {
        "category": "forme",
        "description": "Cylindre ou tube (manchon, pied, entretoise). Origine = centre de la base, axe selon Z local.",
        "params": {
            "d": {"default": 20, "doc": "diamètre extérieur"},
            "inner_d": {"default": 0, "doc": "diamètre intérieur (0 = plein)"},
            "length": {"default": 30, "doc": "longueur"},
        },
        "zones": ["exterieur", "alesage", "extremites"],
    },
    "rib": {
        "category": "forme",
        "description": "Nervure / gousset triangulaire. Branches selon +Y (longueur) et +Z (hauteur), épaisseur selon X centrée.",
        "params": {
            "length": {"default": 20, "doc": "branche selon Y"},
            "height": {"default": 20, "doc": "branche selon Z"},
            "thickness": {"default": 2, "doc": "épaisseur"},
        },
        "zones": ["nervure"],
    },
    "cutout": {
        "category": "operation",
        "description": "Découpe soustraite du composant `target` (port USB-C, passe-câble, trou, lumière). "
        "Axe de découpe selon Z local : positionner/orienter avec parent/position/rotation. Centrée sur sa position.",
        "params": {
            "shape": {"default": "rect", "doc": "'rect', 'rond' ou 'oblong'"},
            "size": {"default": [12, 6], "doc": "[largeur, hauteur] pour rect/oblong"},
            "d": {"default": 5, "doc": "diamètre pour 'rond'"},
            "depth": {"default": 20, "doc": "profondeur de découpe (traversante si assez grande)"},
        },
        "zones": ["decoupe"],
    },
    # ------------------------------------------------------------ assembly
    "clip": {
        "category": "assemblage",
        "description": "Clip / languette élastique à crochet. Lame selon +Z local, crochet vers +Y à l'extrémité. Origine = base de la lame.",
        "params": {
            "insertion_deflection": {"default": None, "doc": "déplacement d’insertion confirmé en mm ; absent = hypothèse hauteur du crochet"},
            "length": {"default": 12, "doc": "longueur de lame"},
            "width": {"default": 8, "doc": "largeur"},
            "thickness": {"default": 1.6, "doc": "épaisseur de lame"},
            "hook": {"default": 1.2, "doc": "saillie du crochet"},
        },
        "zones": ["lame", "crochet"],
    },
    "hinge": {
        "category": "assemblage",
        "description": "Charnière à nœuds, axe selon X local, centrée sur sa position.",
        "params": {
            "length": {"default": 40, "doc": "longueur totale"},
            "d": {"default": 8, "doc": "diamètre des nœuds"},
            "knuckles": {"default": 3, "doc": "nombre de nœuds"},
        },
        "zones": ["noeuds", "axe"],
    },
    "fastener": {
        "category": "assemblage",
        "description": "Élément de visserie visible (vis, insert, écrou). Axe selon -Z local : la tête est à l'origine, la tige descend.",
        "params": {
            "kind": {"default": "vis", "doc": "'vis', 'insert' ou 'ecrou'"},
            "d": {"default": 3, "doc": "diamètre nominal"},
            "length": {"default": 10, "doc": "longueur sous tête"},
            "head_d": {"default": 5.5, "doc": "diamètre de tête (valeur indicative, à confirmer)"},
        },
        "zones": ["tete", "tige"],
    },
    "boss": {
        "category": "assemblage",
        "description": "Bossage de vissage (colonne avec trou). Origine = centre de la base, axe Z local.",
        "params": {
            "d": {"default": 7, "doc": "diamètre extérieur"},
            "hole_d": {"default": 2.5, "doc": "diamètre du trou"},
            "height": {"default": 8, "doc": "hauteur"},
        },
        "zones": ["colonne", "trou"],
    },
    "rail_clip": {
        "category": "assemblage",
        "description": "Fixation sur rail (type rail DIN). Semelle dans le plan XY local, crochets vers -Z, rail selon X local.",
        "params": {
            "rail_width": {"default": 35, "doc": "largeur du rail (TS35 selon EN 60715 : 35)"},
            "length": {"default": 20, "doc": "longueur le long du rail"},
            "thickness": {"default": 2.5, "doc": "épaisseur de la semelle"},
        },
        "zones": ["semelle", "crochets"],
    },
}


def catalog_for_prompt() -> str:
    lines: list[str] = []
    for name, spec in CATALOG.items():
        lines.append(f"### `{name}` ({spec['category']})")
        lines.append(spec["description"])
        for pname, p in spec["params"].items():
            lines.append(f"- `{pname}` (défaut {p['default']!r}) : {p['doc']}")
        lines.append(f"- zones sélectionnables : {', '.join(spec['zones'])}")
        lines.append("")
    return "\n".join(lines)
