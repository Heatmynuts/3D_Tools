# 3D_Tool — Atelier de conception mécanique assistée par IA

Application web locale : IDÉE → entretien adaptatif → maquette 3D conceptuelle → plan de conception → CAO CadQuery → Bambu Studio → Bambu Lab H2D.
Plan d'architecture et étapes : `PLAN.md`. On avance **étape par étape, avec validation de l'utilisateur** entre les étapes.

## État
- Fait : étapes 0 et 1a–1d (prototype V1 : entretien, maquette, versions, diff, sélection, plan).
- Fait : comparaison A/B — Claude (A, API Anthropic directe) vs un modèle OpenRouter (B, choisi dans l'UI),
  même contexte et même prompt, en parallèle, **pas à l'aveugle** (choix de l'utilisateur). La proposition
  retenue devient la version ; toutes sont gardées dans la table `candidates` (stats : `/api/projects/{id}` → `ab_stats`).
- Fait : mode parallèle — depuis un tour A/B, cliquer une option d'une colonne crée un fil par modèle (table `tracks`,
  versions sur branches, sans déplacer la tête du projet) ; chaque colonne répond indépendamment ; « Retenir » ferme les fils.
- Fait : revue technique déterministe (`review.py`) — épaisseurs vs profil Bambu H2D officiel (`manufacturing.py`
  lit les JSON du bundle Bambu Studio), déformation des clips ε = 1,5·t·y/L², sens des couches (orientation déclarée),
  isostatisme (liaisons normalisées → ddl), cotes estimées. Le LLM déclare orientations / charges / mise en position ;
  la revue lui est renvoyée à chaque tour. Vue « Impression » : surplombs < seuil du profil.
- Fait : coûts par appel (`llm_calls.cost_usd`, OpenRouter = réel, Claude = estimé via `llm/pricing.py`), par étape
  (`turn_id`), solde OpenRouter (`/key`, `/credits` si clé de gestion) ; solde Anthropic seulement estimé (pas d'API).
- Ajouté : verrous backend après patch et avant plan ; couverture explicite de la revue.
- Ajouté : chaîne CadQuery → STEP/STL → acceptation géométrie → sélection profils H2D/plateau → slicing réel → acceptation résultat. `pipeline.py` et `cad_worker.py`, UI `PipelinePanel.tsx`.
- Runtime local : `tools/BambuStudio.app` 2.8.2.61, installé depuis la publication officielle, préféré avec ses profils. `tools/` ignoré par Git.
- Tests : `backend/tests/`, unitaires et intégration noyau CAO/slicer sans fournisseur payant. Rapport : `docs/validation/2026-09-30-workflow.md`.
- À faire : évaluation qualitative des modèles réels, pièces jointes, FreeCAD/build123d et comparaison entre moteurs, contrôles mécaniques approfondis, optimisation des profils.

## Lancer
- `./dev.sh` : backend FastAPI sur :8000 + Vite sur :5180 (le port 5173 est pris par un autre projet).
- Clés : `backend/.env` (modèle : `backend/.env.example`) — `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`. Sans clé → provider `mock`.
- Instance de test isolée (sans coût) : backend `LLM_PROVIDER=mock B_PROVIDER=mock ANTHROPIC_API_KEY= DATA_DIR=<tmp> uvicorn … --port 8010`
  + `VITE_PORT=5190 API_URL=http://127.0.0.1:8010 npx vite`.

## Architecture (règle d'or : ne jamais mélanger CONCEPT / CAO / FABRICATION)
- `backend/src/design_backend/`
  - `schemas.py` : DesignSpec, ConceptGraph, AgentTurn (patchs), DesignPlan (Pydantic).
  - `catalog.py` : vocabulaire des composants concept = **source unique** (prompt + valeurs par défaut du front via `/api/meta`).
  - `patching.py` : application/validation déterministe des patchs, diff par id.
  - `agent/engineer.py` + `agent/prompts/*.md` : un appel LLM par tour, JSON validé, une réparation max.
  - `llm/` : abstraction fournisseur (`anthropic`, `openai_compat` pour Ollama/LM Studio, `mock`).
  - `store.py` : SQLite, versions **immuables** (parent_id), phase dérivée de la version courante.
- `frontend/src/`
  - `concept/builder.ts` : ConceptGraph → maillages via manifold-3d (WASM). Chaque primitive est enregistrée (composant, zone) avant les booléens → sélection et surlignage par triangle.
  - `concept/diff.ts` : diff par id + propagation aux dépendants (wraps/supports/parent/target).
  - `viewer/Viewer.tsx` : R3F, Z vers le haut, modes technique/ombré/transparent, avant/après/superposition/côte à côte (caméras synchronisées).

## Conventions
- Unités mm/degrés ; Z vers le haut ; bureau z=0 ; l'utilisateur est côté -Y.
- Le LLM n'émet jamais de géométrie : uniquement des patchs sur DesignSpec/ConceptGraph.
- Nouveau type de composant = entrée dans `catalog.py` + builder dans `builder.ts` (les deux).
- Aucune cote d'objet réel inventée : statut `estime` / `a_determiner`.
- UI et prompts en français, tutoiement.
