"""Génère une page HTML autonome de vue 3D à partir des exports d'une pièce.

Usage :
    python3 tools/make_view.py parts/<nom> [--titre "Nom affiché"]

Lit parts/<nom>/out/resume.json et les STL listés, écrit parts/<nom>/out/<nom>_vue3d.html.
Ce fichier se publie tel quel en Artifact (page privée, ouvrable sur iPhone / iPad / PC).
"""

import argparse
import base64
import html
import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "viewer" / "template.html"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", type=Path, help="dossier de la pièce, ex. parts/boitier")
    ap.add_argument("--titre", help="nom affiché (défaut : nom de la pièce)")
    args = ap.parse_args()

    out_dir = args.dossier / "out"
    resume = json.loads((out_dir / "resume.json").read_text())
    resume["stl"] = {
        p["stl"]: base64.b64encode((out_dir / p["stl"]).read_bytes()).decode("ascii")
        for p in resume["pieces"]
    }
    titre = args.titre or resume["nom"].replace("_", " ").capitalize()

    donnees = json.dumps(resume, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.read_text().replace("{{TITRE}}", html.escape(titre)).replace("/*__DONNEES__*/", donnees)

    dest = out_dir / f"{resume['nom']}_vue3d.html"
    dest.write_text(page)
    print(f"Vue 3D : {dest} ({dest.stat().st_size / 1e6:.2f} Mo)")


if __name__ == "__main__":
    main()
