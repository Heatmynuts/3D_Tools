"""Rendus PNG réalistes d'une pièce ou d'un assemblage, sous plusieurs angles.

Usage :
    python3 tools/render.py parts/<nom> [--couleur "#1c1d1f"] [--vues iso,face,arriere,cote,detail]
                            [--largeur 1920] [--hauteur 1152] [--photo [--echantillons 48]]

--photo : rendu photoréaliste par lancer de rayons (three-gpu-pathtracer) : lumière indirecte,
          ombres de contact, reflets. Plus lent (quelques minutes par image sur le processeur du cloud) ;
          résolution par défaut 1280 x 768 dans ce mode.

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

THREE_VERSION = "0.163.0"
THREE_CDN = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/"
THREE_FICHIERS = [
    "build/three.module.js",
    "examples/jsm/controls/OrbitControls.js",
    "examples/jsm/loaders/STLLoader.js",
    "examples/jsm/utils/BufferGeometryUtils.js",
    "examples/jsm/environments/RoomEnvironment.js",
    "examples/jsm/postprocessing/Pass.js",
]
CACHE = Path(__file__).resolve().parent / ".cache" / f"three-{THREE_VERSION}"
# nom : (vue de la page, marge de cadrage, cible en fractions de la boîte englobante ou None)
VUES = {
    "iso": ("iso", 0.82, None),
    "face": ("front", 0.82, None),
    "arriere": ("rear", 0.82, None),
    "cote": ("side", 0.82, None),
    "dessus": ("top", 0.82, None),
    "detail": ("iso", 0.22, [0.97, 0.35, 0.45]),   # gros plan d'une extrémité : stries de couches
}
PT_FICHIERS = {  # rendu photo : bibliothèques de lancer de rayons (jsDelivr), mises en cache
    "pt/pathtracer.js": "https://cdn.jsdelivr.net/npm/three-gpu-pathtracer@0.0.23/build/index.module.js",
    "pt/bvh.js": "https://cdn.jsdelivr.net/npm/three-mesh-bvh@0.7.8/build/index.module.js",
}

SCRIPT_NODE = r"""
const { chromium } = require('playwright');
const cfg = JSON.parse(process.argv[process.argv.length - 1]);
(async () => {
  const opts = { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] };
  if (cfg.chromium) opts.executablePath = cfg.chromium;
  const browser = await chromium.launch(opts);
  const page = await browser.newPage({ viewport: { width: cfg.largeur, height: cfg.hauteur } });
  page.setDefaultTimeout(0);
  const erreurs = [];
  page.on('pageerror', (e) => erreurs.push(String(e)));
  await page.goto(cfg.url);
  await page.addStyleTag({ content: '.sheet,.toolbar,.status{display:none!important}.app{grid-template-columns:1fr!important}' });
  await page.waitForFunction(() => window.vue3d && window.vue3d.pret, null, { timeout: 60000 });
  await page.evaluate((c) => { window.vue3d.rendu(true); window.vue3d.couleur(c); }, cfg.couleur);
  await page.waitForTimeout(800);
  if (cfg.photo) {
    await page.evaluate(async () => {
      const v = window.vue3d, THREE = await import('three');
      const { WebGLPathTracer, GradientEquirectTexture } = await import('three-gpu-pathtracer');
      v.pause();
      const env = new GradientEquirectTexture();
      env.topColor.set(0xffffff); env.bottomColor.set(0x8a8f96); env.update();
      v.scene.environment = env;
      v.sol.visible = false;
      const sol = new THREE.Mesh(new THREE.PlaneGeometry(v.radius * 30, v.radius * 30),
        new THREE.MeshStandardMaterial({ color: 0xe8eaed, roughness: 0.9 }));
      sol.position.set(v.center.x, v.center.y, v.box.min.z - 0.05);
      v.scene.add(sol);
      const pt = new WebGLPathTracer(v.renderer);
      pt.renderDelay = 0; pt.fadeDuration = 0; pt.minSamples = 0;
      pt.tiles.set(2, 2);
      pt.setScene(v.scene, v.camera);
      window.__pt = pt;
    });
  }
  for (const [nom, vue, marge, cible] of cfg.vues) {
    const fichier = cfg.sortie + '/' + cfg.prefixe + '_' + nom + (cfg.photo ? '_photo' : '') + '.png';
    await page.evaluate(([v, m, c]) => { window.vue3d.vue(v, m, c); window.vue3d.controls.update(); }, [vue, marge, cible]);
    if (cfg.photo) {
      const debut = Date.now();
      await page.evaluate(async (n) => {
        const pt = window.__pt, gl = window.vue3d.renderer.getContext();
        pt.updateCamera(); pt.reset();
        while (pt.samples < n) {
          pt.renderSample();
          if (Number.isInteger(pt.samples)) gl.finish();
          await new Promise((r) => setTimeout(r, 0));
        }
        gl.finish();
      }, cfg.echantillons);
      await page.locator('#scene').screenshot({ path: fichier, timeout: 0 });
      const t = Math.round((Date.now() - debut) / 1000);
      console.log('  ' + fichier.split('/').pop() + ' (' + cfg.echantillons + ' échantillons, ' + t + ' s)');
    } else {
      await page.waitForTimeout(1500);
      await page.locator('#scene').screenshot({ path: fichier });
      console.log('  ' + fichier.split('/').pop());
    }
  }
  await browser.close();
  if (erreurs.length) { console.error('Erreurs page : ' + erreurs.join(' ; ')); process.exit(1); }
})().catch((e) => { console.error(e); process.exit(1); });
"""


class _ServeurSilencieux(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # pas de journal HTTP dans la console
        pass


def _telecharger(url: str, dest: Path) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as r:
        dest.write_bytes(r.read())


def _cache_three() -> None:
    for rel in THREE_FICHIERS:
        _telecharger(THREE_CDN + rel, CACHE / rel)
    for rel, url in PT_FICHIERS.items():
        _telecharger(url, CACHE.parent / rel)


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
    ap.add_argument("--largeur", type=int)
    ap.add_argument("--hauteur", type=int)
    ap.add_argument("--photo", action="store_true", help="rendu photoréaliste (lancer de rayons, lent)")
    ap.add_argument("--echantillons", type=int, default=48, help="échantillons par pixel en mode --photo")
    args = ap.parse_args()
    largeur = args.largeur or (1280 if args.photo else 1920)
    hauteur = args.hauteur or round(largeur * 0.6)

    vues = [v.strip() for v in args.vues.split(",") if v.strip()]
    inconnues = [v for v in vues if v not in VUES]
    if inconnues:
        sys.exit(f"Vues inconnues : {inconnues} (possibles : {', '.join(VUES)})")

    _cache_three()
    page, resume = construire_page(args.dossier, couleur=args.couleur)
    page = page.replace(THREE_CDN, "./three/")
    page = page.replace(
        '"three/addons/": "./three/examples/jsm/"',
        '"three/addons/": "./three/examples/jsm/",\n  "three/examples/jsm/": "./three/examples/jsm/",\n'
        '  "three-mesh-bvh": "./pt/bvh.js",\n  "three-gpu-pathtracer": "./pt/pathtracer.js"',
    )
    sortie = args.dossier / "rendus"
    sortie.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "index.html").write_text(
            "<!doctype html><html><head><meta charset='utf-8'></head><body style='margin:0'>" + page + "</body></html>"
        )
        shutil.copytree(CACHE, Path(tmp) / "three")
        shutil.copytree(CACHE.parent / "pt", Path(tmp) / "pt")
        handler = functools.partial(_ServeurSilencieux, directory=tmp)
        serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        try:
            cfg = {
                "url": f"http://127.0.0.1:{serveur.server_port}/index.html",
                "couleur": args.couleur,
                "vues": [[v, *VUES[v]] for v in vues],
                "largeur": largeur,
                "hauteur": hauteur,
                "photo": args.photo,
                "echantillons": args.echantillons,
                "sortie": str(sortie.resolve()),
                "prefixe": resume["nom"],
                "chromium": _chromium(),
            }
            mode = f"photo, {args.echantillons} échantillons" if args.photo else "temps réel"
            print(f"Rendus de « {resume['nom']} » ({args.couleur}, {mode}, {largeur} x {hauteur}) :")
            env = dict(os.environ, NODE_PATH=_node_path())
            res = subprocess.run(["node", "-e", SCRIPT_NODE, json.dumps(cfg)], env=env)
        finally:
            serveur.shutdown()
    if res.returncode:
        sys.exit(res.returncode)
    print(f"  → {sortie}")


if __name__ == "__main__":
    main()
