"""Rendus PNG réalistes d'une pièce ou d'un assemblage, sous plusieurs angles.

Usage :
    python3 tools/render.py parts/<nom> [--couleur "#1c1d1f"] [--vues iso,face,arriere,cote]
                            [--largeur 1920] [--hauteur 1152]

Écrit parts/<nom>/rendus/<nom>_<vue>.png.
Principe : la page de vue 3D (tools/make_view.py) est ouverte dans Chromium headless (Playwright),
en mode « Rendu » (matière unique, éclairage studio, ombres), puis capturée pour chaque vue.

Prérequis : Node.js + Playwright (+ Chromium). Dans le cloud : déjà installés.
En local : `npm install -g playwright` puis `npx playwright install chromium`.
three.js est mis en cache dans tools/.cache/ au premier lancement (Chromium headless n'utilise
pas forcément le proxy du système).
"""

import argparse
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_view import COULEUR_DEFAUT, construire_page  # noqa: E402

THREE_VERSION = "0.160.0"
THREE_CDN = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/"
THREE_FICHIERS = [
    "build/three.module.js",
    "examples/jsm/controls/OrbitControls.js",
    "examples/jsm/loaders/STLLoader.js",
    "examples/jsm/utils/BufferGeometryUtils.js",
    "examples/jsm/environments/RoomEnvironment.js",
]
CACHE = Path(__file__).resolve().parent / ".cache" / f"three-{THREE_VERSION}"
VUES = {"iso": "iso", "face": "front", "arriere": "rear", "cote": "side", "dessus": "top"}

SCRIPT_NODE = r"""
const { chromium } = require('playwright');
const cfg = JSON.parse(process.argv[process.argv.length - 1]);
(async () => {
  const opts = { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] };
  if (cfg.chromium) opts.executablePath = cfg.chromium;
  const browser = await chromium.launch(opts);
  const page = await browser.newPage({ viewport: { width: cfg.largeur, height: cfg.hauteur } });
  const erreurs = [];
  page.on('pageerror', (e) => erreurs.push(String(e)));
  await page.goto(cfg.url);
  await page.addStyleTag({ content: '.sheet,.toolbar,.status{display:none!important}.app{grid-template-columns:1fr!important}' });
  await page.waitForFunction(() => window.vue3d && window.vue3d.pret, null, { timeout: 60000 });
  await page.evaluate((c) => { window.vue3d.rendu(true); window.vue3d.couleur(c); }, cfg.couleur);
  await page.waitForTimeout(800);
  for (const [nom, vue] of cfg.vues) {
    await page.evaluate((v) => window.vue3d.vue(v, 0.82), vue);
    await page.waitForTimeout(1500);
    await page.locator('#scene').screenshot({ path: cfg.sortie + '/' + cfg.prefixe + '_' + nom + '.png' });
    console.log('  ' + cfg.prefixe + '_' + nom + '.png');
  }
  await browser.close();
  if (erreurs.length) { console.error('Erreurs page : ' + erreurs.join(' ; ')); process.exit(1); }
})().catch((e) => { console.error(e); process.exit(1); });
"""


class _ServeurSilencieux(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # pas de journal HTTP dans la console
        pass


def _cache_three() -> None:
    for rel in THREE_FICHIERS:
        dest = CACHE / rel
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(THREE_CDN + rel, timeout=60) as r:
            dest.write_bytes(r.read())


def _chromium() -> str | None:
    """Chromium à utiliser : variable RENDER_CHROMIUM, sinon celui du conteneur cloud, sinon Playwright."""
    for chemin in (os.environ.get("RENDER_CHROMIUM"), "/opt/pw-browsers/chromium"):
        if chemin and Path(chemin).exists():
            return chemin
    return None


def _node_path() -> str:
    racine = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    return os.pathsep.join(filter(None, [os.environ.get("NODE_PATH"), racine]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", type=Path, help="dossier de la pièce, ex. parts/coque_xeneon")
    ap.add_argument("--couleur", default=COULEUR_DEFAUT, help="couleur du filament (hex)")
    ap.add_argument("--vues", default="iso,face,arriere,cote", help=f"parmi {','.join(VUES)}")
    ap.add_argument("--largeur", type=int, default=1920)
    ap.add_argument("--hauteur", type=int, default=1152)
    args = ap.parse_args()

    vues = [v.strip() for v in args.vues.split(",") if v.strip()]
    inconnues = [v for v in vues if v not in VUES]
    if inconnues:
        sys.exit(f"Vues inconnues : {inconnues} (possibles : {', '.join(VUES)})")

    _cache_three()
    page, resume = construire_page(args.dossier, couleur=args.couleur)
    page = page.replace(THREE_CDN, "./three/")
    sortie = args.dossier / "rendus"
    sortie.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "index.html").write_text(
            "<!doctype html><html><head><meta charset='utf-8'></head><body style='margin:0'>" + page + "</body></html>"
        )
        shutil.copytree(CACHE, Path(tmp) / "three")
        handler = functools.partial(_ServeurSilencieux, directory=tmp)
        serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        try:
            cfg = {
                "url": f"http://127.0.0.1:{serveur.server_port}/index.html",
                "couleur": args.couleur,
                "vues": [[v, VUES[v]] for v in vues],
                "largeur": args.largeur,
                "hauteur": args.hauteur,
                "sortie": str(sortie.resolve()),
                "prefixe": resume["nom"],
                "chromium": _chromium(),
            }
            print(f"Rendus de « {resume['nom']} » ({args.couleur}) :")
            env = dict(os.environ, NODE_PATH=_node_path())
            res = subprocess.run(["node", "-e", SCRIPT_NODE, json.dumps(cfg)], env=env)
        finally:
            serveur.shutdown()
    if res.returncode:
        sys.exit(res.returncode)
    print(f"  → {sortie}")


if __name__ == "__main__":
    main()
