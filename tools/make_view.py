"""Génère une page HTML autonome de vue 3D à partir des exports d'une pièce.

Usage :
    python3 tools/make_view.py parts/<nom> [--titre "Nom affiché"] [--couleur "#1c1d1f"]

Lit parts/<nom>/out/resume.json et les STL listés, écrit parts/<nom>/out/<nom>_vue3d.html.
Ce fichier se publie tel quel en Artifact (page privée, ouvrable sur iPhone / iPad / PC).
--couleur : couleur du filament utilisée par le mode « Rendu » de la page (noir par défaut).
"""

import argparse
import base64
import html
import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "viewer" / "template.html"
COULEUR_DEFAUT = "#1c1d1f"


def construire_page(dossier: Path, titre: str | None = None, couleur: str = COULEUR_DEFAUT) -> tuple[str, dict]:
    """Retourne (html de la page, resume) pour la pièce du dossier."""
    out_dir = dossier / "out"
    resume = json.loads((out_dir / "resume.json").read_text())
    resume["stl"] = {
        p["stl"]: base64.b64encode((out_dir / p["stl"]).read_bytes()).decode("ascii")
        for p in resume["pieces"]
    }
    resume["couleur_rendu"] = couleur
    titre = titre or resume["nom"].replace("_", " ").capitalize()
    donnees = json.dumps(resume, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.read_text().replace("{{TITRE}}", html.escape(titre)).replace("/*__DONNEES__*/", donnees)
    return page, resume


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", type=Path, help="dossier de la pièce, ex. parts/boitier")
    ap.add_argument("--titre", help="nom affiché (défaut : nom de la pièce)")
    ap.add_argument("--couleur", default=COULEUR_DEFAUT, help="couleur du filament en mode Rendu (hex)")
    args = ap.parse_args()

    page, resume = construire_page(args.dossier, args.titre, args.couleur)
    dest = args.dossier / "out" / f"{resume['nom']}_vue3d.html"
    dest.write_text(page)
    print(f"Vue 3D : {dest} ({dest.stat().st_size / 1e6:.2f} Mo)")


if __name__ == "__main__":
    main()
