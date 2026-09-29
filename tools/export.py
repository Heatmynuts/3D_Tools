"""Export multi-format et contrôles de base pour les pièces build123d.

Usage depuis un part.py :
    from export import export_all
    export_all({"boitier": boitier, "couvercle": couvercle}, "boitier", OUT_DIR, params)

`params` : dictionnaire des PARAMÈTRES du part.py, repris dans resume.json et la vue 3D.
"""

import json
from pathlib import Path

from build123d import Compound, Location, Mesher, Part, export_gltf, export_step, export_stl

# Volume retenu pour la H2D (mm), compatible buse gauche et droite.
# Source : .claude/skills/h2d-design/references/h2d.md
H2D_VOLUME = (325.0, 320.0, 320.0)

# Finesse du maillage (STL/GLB) : (tolérance linéaire mm, tolérance angulaire rad).
# Pièce à imprimer : valeurs par défaut de build123d. Référence : plus grossier, pour la vue 3D.
MESH_PIECE = (0.001, 0.1)
MESH_REFERENCE = (0.05, 0.3)

# Couleurs d'affichage (vue 3D uniquement, sans lien avec le filament).
COLORS = [(0.20, 0.45, 0.85), (0.90, 0.55, 0.15), (0.30, 0.70, 0.40), (0.75, 0.30, 0.55)]


def _report(name: str, shape: Part) -> tuple[float, float, float]:
    bb = shape.bounding_box()
    size = (bb.size.X, bb.size.Y, bb.size.Z)
    print(
        f"  {name:<14} {size[0]:7.2f} x {size[1]:7.2f} x {size[2]:7.2f} mm"
        f"   volume {shape.volume / 1000:8.2f} cm³"
        f"   z min {bb.min.Z:.2f}"
    )
    if abs(bb.min.Z) > 1e-6:
        print(f"    ⚠ {name} ne repose pas sur le plateau (z min = {bb.min.Z:.3f} mm)")
    if not shape.is_valid:
        print(f"    ⚠ {name} : géométrie invalide")
    return size


def _fits(size: tuple[float, float, float]) -> bool:
    return all(s <= v for s, v in zip(size, H2D_VOLUME))


def export_all(
    parts: dict[str, Part],
    name: str,
    out_dir: Path,
    params: dict | None = None,
    reference: bool = False,
    source: str | None = None,
    contexte: dict[str, Part] | None = None,
    disposition: dict[str, Location] | None = None,
) -> None:
    """Exporte chaque pièce en STEP/STL, l'ensemble en 3MF et GLB, et affiche les contrôles.

    reference : modèle importé servant de gabarit (ne s'imprime pas) : ni STEP ni 3MF
                exportés (le STEP d'origine est conservé), maillage allégé.
    source : attribution affichée dans la vue 3D (auteur, licence, lien).
    contexte : pièces affichées en transparence dans la vue 3D uniquement (ex. l'objet à protéger),
               sans STEP, 3MF ni contrôle de volume.
    disposition : déplacement de chaque pièce pour le plateau, appliqué au 3MF seulement
                  (la vue 3D et les STEP/STL restent en position assemblée).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    tol, ang = MESH_REFERENCE if reference else MESH_PIECE
    print(f"Pièce « {name} »{' (référence)' if reference else ''}")

    resume = {
        "nom": name,
        "volume_h2d_mm": H2D_VOLUME,
        "reference": reference,
        "source": source,
        "pieces": [],
        "parametres": params or {},
    }
    for i, (label, shape) in enumerate(parts.items()):
        color = COLORS[i % len(COLORS)]
        shape.label = label
        shape.color = color
        size = _report(label, shape)
        fits = _fits(size)
        if not fits and not reference:
            print(f"    ⚠ {label} dépasse le volume H2D {H2D_VOLUME} mm")
        if not reference:
            export_step(shape, out_dir / f"{name}_{label}.step")
        export_stl(shape, out_dir / f"{name}_{label}.stl", tolerance=tol, angular_tolerance=ang)
        resume["pieces"].append(
            {
                "nom": label,
                "stl": f"{name}_{label}.stl",
                "dimensions_mm": [round(v, 2) for v in size],
                "volume_cm3": round(shape.volume / 1000, 2),
                "tient_dans_h2d": fits,
                "couleur": "#%02x%02x%02x" % tuple(round(c * 255) for c in color),
            }
        )

    for label, shape in (contexte or {}).items():
        shape.label = label
        shape.color = (0.55, 0.58, 0.62)
        export_stl(shape, out_dir / f"{name}_{label}.stl", *MESH_REFERENCE)
        bb = shape.bounding_box()
        resume["pieces"].append(
            {
                "nom": label,
                "stl": f"{name}_{label}.stl",
                "dimensions_mm": [round(v, 2) for v in (bb.size.X, bb.size.Y, bb.size.Z)],
                "volume_cm3": round(shape.volume / 1000, 2),
                "tient_dans_h2d": True,
                "couleur": "#8c949e",
                "contexte": True,
            }
        )

    assembly = Compound(label=name, children=list(parts.values()))

    if not reference:
        mesher = Mesher()
        for label, shape in parts.items():
            loc = (disposition or {}).get(label)
            mesher.add_shape(loc * shape if loc else shape)
        mesher.write(str(out_dir / f"{name}.3mf"))

    export_gltf(
        assembly,
        str(out_dir / f"{name}.glb"),
        binary=True,
        linear_deflection=tol,
        angular_deflection=ang,
    )
    (out_dir / "resume.json").write_text(json.dumps(resume, ensure_ascii=False, indent=2))
    print(f"  → fichiers dans {out_dir}")
