# 3D Tool

Atelier local de conception de pièces fonctionnelles pour l'impression 3D. L'utilisateur décrit son besoin, ajoute des photos ou des cotes, voit une maquette évoluer, valide la géométrie CAO, puis prépare une impression adaptée à sa machine.

Le parcours distingue trois étapes : **concept**, **CAO** et **fabrication**. Une cote estimée ne devient pas une cote validée sans confirmation. La visualisation montre ce qui a changé à chaque version, et les variantes restent consultables.

## État du prototype

- Entretien de conception avec cahier des charges structuré, maquette 3D déterministe, historique de versions, sélection et comparaison visuelle.
- Comparaison A/B de modèles, revue technique déterministe et suivi des coûts des appels.
- Génération CadQuery avec STEP/STL, acceptation explicite de la géométrie, sélection de profils Bambu H2D et découpage local par Bambu Studio.
- Import de documents et contrôles du flux dans le backend.

L'optimisation automatique de l'orientation, des supports, de l'adhérence, de la finition visible et des vitesses par zone est **un objectif de conception**, pas une fonction générale déjà validée. L'impression physique, l'ajustement des assemblages et l'envoi à l'imprimante demandent toujours une vérification distincte. Voir [le concept et les limites](docs/CONCEPT.md) et [le rapport de validation](docs/validation/2026-09-30-workflow.md).

## Lancer localement

Prérequis : macOS, Python 3.12, `uv`, Node.js, et Bambu Studio pour la phase fabrication. Les dépendances CAO sont définies dans `backend/pyproject.toml` ; celles de l'interface dans `frontend/package.json`.

```bash
cd backend && uv sync
cd ../frontend && npm ci
cd .. && cp backend/.env.example backend/.env
./dev.sh
```

Le backend est disponible sur `http://127.0.0.1:8000` et l'interface sur `http://127.0.0.1:5180`. Sans clé API, le fournisseur `mock` permet d'essayer le parcours de démonstration. Les clés restent dans `backend/.env`, ignoré par Git. L'installation des outils CAO et de Bambu Studio dépend encore du Mac : ce dépôt n'est pas un installateur universel.

## Vérifications de cette publication

- `backend/.venv/bin/python -m unittest discover -s backend/tests -v` : 27 tests réussis sur le Mac de développement.
- `npm run build` dans `frontend` : compilation TypeScript et build Vite réussis.

Le code du prototype se trouve dans `backend/` et `frontend/`. [PLAN.md](PLAN.md) expose l'architecture et [PROMPT_APP.md](PROMPT_APP.md) le contrat produit détaillé ; certaines étapes de ces documents sont prospectives.
