# 3D_Tools

Atelier de conception 3D paramétrique (build123d) pour la **Bambu Lab H2D**, piloté par Claude Code.

- Conception et modifications en français, dans le cloud (web, iPhone, iPad) ou en local.
- Vue 3D interactive publiée en page privée (Artifact).
- Règles de conception PLA / PETG sourcées : `.claude/skills/h2d-design/`.
- Pilotage de l'imprimante en local : `docs/local-h2d.md`.
- Conception dans Fusion 360 (MCP officiel Autodesk, en local) : `docs/local-fusion360.md`.

| Dossier | Contenu |
|---|---|
| `parts/<nom>/` | `part.py` (paramètres + modèle) et `out/` (STEP, STL, 3MF, GLB, vue 3D) |
| `tools/` | export multi-format + contrôles, génération de la vue 3D |
| `viewer/` | gabarit HTML de la vue 3D |
| `docs/` | installation locale et pilotage H2D |

Démarrage : `python3 parts/boitier/part.py` puis `python3 tools/make_view.py parts/boitier`.
