# 3D_Tool — Plan d'architecture

Date : 2026-09-30. **Plan validé** (réponses utilisateur : clé Anthropic disponible, environnement dédié `uv`, build123d retenu comme moteur C, H2D en Wi-Fi local — mode cloud/LAN à vérifier).

**Avancement** : étapes 0 et 1a–1d réalisées (prototype V1 testé de bout en bout en mode démo). Prochaine : 1e.

---

## 1. Lecture du cahier des charges — ce qui structure tout

1. **Trois niveaux étanches** : CONCEPT (maquette légère) → CAO (B-rep paramétrique) → FABRICATION (Bambu). Chaque niveau a son propre modèle de données ; on ne passe au suivant que par une action explicite.
2. **Le cœur de la V1 n'est pas la géométrie, c'est l'état structuré** : un `DesignSpec` (exigences, décisions, inconnues…) et un `ConceptGraph` (composants paramétriques persistants). Le LLM ne produit jamais de maillage : il produit des *patchs* sur ces deux structures. Un générateur déterministe transforme le `ConceptGraph` en géométrie.
3. **« Modifier seulement ce qui est concerné »** et **« montrer ce qui a changé »** deviennent alors triviaux : chaque composant a un identifiant stable → diff par id → surlignage.
4. **Versioning immuable** (graphe de versions, jamais d'écrasement) dès le jour 1, car tout le reste (avant/après, variantes, retour arrière, A/B CAO) en dépend.

---

## 2. État de l'art vérifié (septembre 2026)

| Brique | Projet | État constaté | Verdict |
|---|---|---|---|
| CAO A | **CadQuery 2.8.0** (21/06/2026), Python ≥ 3.11, wheels OCP macOS | Maintenu | Retenu |
| CAO A' | **build123d 0.12.0** (18/09/2026), même noyau OCP ; écosystème LLM actif (build123d-mcp 0.3.90, 25/09/2026) | Très actif | Proposé en option C |
| CAO B | **FreeCAD 1.1.x** (1.1 sortie 24/03/2026, 1.1.4 = dernière maintenance), `freecadcmd` headless | Maintenu | Retenu |
| FreeCAD+LLM | `gurul/gencad` : MCP → freecadcmd + rendus de coupe. 27 commits, 3 étoiles, pas de release | Jeune | **Reprendre le principe, pas la dépendance** |
| FreeCAD+LLM | `drfenixion/freecad.gencad` : workbench GUI | GUI, pas headless | Écarté |
| FreeCAD MCP | nombreux serveurs (spkane robust-mcp 0.6.1 janv. 2026, blwfish, proximile…) ; fragmenté | Variable | Non nécessaire (voir §4.5) |
| Booléens navigateur | **manifold-3d** (Manifold 3.5, WASM officiel, résultats étanches) | Maintenu | Retenu pour la maquette |
| Booléens navigateur | three-bvh-csg 0.0.17 : 22/1000 résultats étanches dans le benchmark polydera (benchmark publié par l'éditeur concurrent trueform → biais possible) | — | Écarté |
| Import STEP navigateur | occt-import-js 0.0.24 (OCCT WASM → JSON compatible three.js) | Maintenu | Retenu (pièces jointes STEP) |
| Viewer | three.js + React Three Fiber | Standard | Retenu |
| Projets voisins | Chat3D (build123d + three.js), CadSmith (CadQuery, boucle exécution/mesure), local-ai-cad-agent (OpenSCAD) | Prompt → pièce directe | **Aucun ne fait l'entretien + maquette évolutive** → à construire |
| Slicer | **Bambu Studio 02.05.00.66 installé localement**, binaire universel arm64, CLI `--slice / --load-settings / --load-filaments / --export-3mf` **vérifiée sur ta machine** | Officiel | Retenu |
| Profils H2D | Présents dans le bundle : machine H2D 0.2/0.4/0.6/0.8 (+ H2D Pro), process `@BBL H2D`, 304 profils filament H2D | Officiel | Retenu |
| Envoi imprimante | LAN-only + **Developer Mode** (H2D ≥ fw 01.01.00.01) : MQTT 8883 + FTPS 990 ; lib Python `bambulabs_api` (`start_print_3mf`) | Communautaire | Étape finale, optionnelle |
| Rendu réaliste | Blender 5.1.1 installé (`blender -b -P script.py`) | — | Optionnel, tardif |

---

## 3. Architecture

```
┌──────────────────────────── Navigateur (localhost) ────────────────────────────┐
│ React + TypeScript (Vite)                                                     │
│  ┌ Conversation ┐  ┌──────── Viewer 3D (R3F / three.js) ────────┐  ┌ Projet ┐ │
│  │ question     │  │ ConceptBuilder (déterministe, manifold WASM)│  │ état   │ │
│  │ boutons 2-5  │  │ modes : technique / shaded / transparent    │  │ versions│ │
│  │ + Autre      │  │ avant/après : bascule, ghost, split synchro │  │ variantes│
│  │ sélection →  │  │ sélection : composant / zone sémantique     │  └────────┘ │
│  └──────────────┘  └──────────────────────────────────────────────┘           │
└───────────────────────────────▲──────────────────────────────────────────────┘
                                │ HTTP + WebSocket (streaming)
┌───────────────────────────────┴───────── Backend Python (FastAPI) ────────────┐
│ Orchestrateur de workflow (machine à états : CONCEPT → PLAN → CAO → FAB)      │
│  ├─ Agent « Ingénieur conception »  ──► couche LLM abstraite (providers)      │
│  ├─ Store versions (SQLite + dossier projet, immuable, graphe parent/variante)│
│  ├─ [plus tard] Runners CAO isolés : cadquery | freecadcmd | build123d        │
│  ├─ [plus tard] Mesure neutre OCP (volume, surface, bbox, corps, validité)    │
│  ├─ [plus tard] Bambu : aplatissement profils + CLI + lecture résultats       │
│  └─ [plus tard] Envoi H2D (MQTT/FTPS) — action explicite uniquement           │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Pourquoi Python en backend dès la V1** alors que la V1 est surtout du navigateur : CadQuery, FreeCAD, OCP, bambulabs_api et Blender sont tous pilotables en Python. Un seul backend évite une réécriture à l'étape 3.

### 3.1 Modèles de données (cœur du système)

**`DesignSpec`** (produit par l'agent, validé par schéma Pydantic) :
- `function`, `context` (objet réel, environnement)
- `requirements[]` : {id, texte, priorité}
- `constraints[]` : {id, type (dimension/matériau/assemblage/impression…), valeur, **source** : utilisateur | document | hypothèse}
- `decisions[]` : {id, question, choix, conséquence géométrique, version où prise}
- `parameters[]` : {nom, valeur, unité, source, statut : connu | estimé | à déterminer}
- `unknowns[]` : {id, sujet, **impact estimé** sur géométrie/assemblage/fabricabilité}
- `print_intent` (prototype, test dimensionnel, pièce finale… — hérité plus tard par la fabrication)
- `readiness` (l'agent estime si l'entretien peut s'arrêter)

**`ConceptGraph`** (maquette, jamais de maillage stocké) :
- `reference_objects[]` : l'objet réel en fantôme (ex. écran : boîte aux cotes fournies, ou STL/STEP importé)
- `components[]` : {id stable, type, paramètres, relations (`wraps`, `attached_to`, `rests_on`), rôle : fonctionnel | esthétique, `zones` nommées}
- Bibliothèque initiale de ~12 types de composants « concept » : cadre périphérique, coque/boîtier, équerre, pied/béquille, plaque, nervure, clip, charnière, découpe (USB-C, passe-câble), bossage/vis, rainure/rail (DIN), manchon tubulaire.

**Zones sémantiques** : chaque générateur étiquette ses groupes de faces (`cadre.lèvre_avant`, `cadre.coin_haut_gauche`, `pied.appui`). Un clic dans le viewer renvoie `{component, zone, point, normale}` : c'est ce contexte que l'agent reçoit (« cette partie est trop épaisse »). C'est plus exploitable par un LLM qu'un index de triangle, et l'architecture reste compatible avec la sélection de vraies faces/arêtes B-rep en phase CAO.

### 3.2 Boucle d'un tour d'entretien

1. L'utilisateur répond (bouton, texte, sélection, pièce jointe).
2. Le backend envoie à l'agent : `DesignSpec` courant + `ConceptGraph` courant + historique + sélection + pièces jointes.
3. L'agent renvoie **une** sortie structurée :
   `{ spec_patch, concept_patch, change_summary (1 phrase), next: question | checkpoint }`
   avec `question = {texte, options[2..5], autre_autorisé, justification, inconnue_visée}`.
4. Validation déterministe : schéma, références d'ids, cotes > 0, cohérence des relations. Échec → une relance de réparation, sinon message clair.
5. Nouvelle version `Concept Vn+1` (immuable) ; le front reconstruit la maquette (≈ ms), calcule le diff par id (ajouté / modifié / supprimé) et le surligne.
6. **Critère d'arrêt** : l'agent classe les `unknowns` par impact ; si aucun n'a d'impact significatif → checkpoint « Est-ce que cette direction correspond… ? ». Garde-fou déterministe : au-delà de ~8 questions, le checkpoint est proposé d'office.
7. Validation → génération du **Plan de conception** (document structuré dérivé du `DesignSpec`) → attente de validation explicite.

### 3.3 Couche LLM

Interface unique `structured_call(messages, schema, images?) → objet validé`, avec adaptateurs :
- **Anthropic** (Claude) — recommandé pour l'agent ingénieur (raisonnement + vision photos) ;
- **OpenAI-compatible** — couvre d'un coup Ollama, LM Studio (tous deux installés), OpenRouter.

Les prompts système et les schémas sont versionnés dans le dépôt, indépendants du fournisseur. Chaque appel est journalisé (entrée, sortie, latence) pour comparer les modèles sur des scénarios rejoués.

---

## 4. Phases ultérieures (conçues maintenant, codées plus tard)

### 4.1 CAO A/B équitable
- Entrée identique : le Plan de conception validé (JSON + texte).
- Même modèle LLM, même gabarit de prompt ; seule change la documentation API du moteur.
- Le code généré **doit exposer un dictionnaire `PARAMS`** en tête → « passe l'épaisseur de 3 à 4 mm » = modification déterministe du paramètre + ré-exécution, sans régénérer le code.
- Exécution en sous-processus isolé (timeout, pas de réseau), boucle erreur → réparation (N essais max).
- Sortie commune : **STEP**. Les métriques sont calculées par **un seul outil neutre (OCP)** sur les deux STEP : bbox, volume, surface, nombre de corps, validité B-rep (BRepCheck), nb faces/arêtes (complexité), masse = volume × densité matériau, temps de génération.
- Tessellation identique → GLB → même viewer, même caméra/éclairage/échelle.
- Point honnête : CadQuery et FreeCAD reposent tous deux sur OpenCASCADE. La comparaison mesurera surtout **la capacité du LLM à produire une géométrie correcte avec chaque API**, pas deux noyaux différents.

### 4.2 Fabrication (Bambu Studio CLI)
- Les profils du bundle utilisent l'héritage (`inherits`) ; la CLI exige des configs complètes → module d'**aplatissement** des profils officiels H2D.
- Affichage séparé : **Profil officiel** | **Modifications proposées par l'assistant** (diff clé par clé), jamais de modification des limites machine.
- Lecture des résultats dans le `.gcode.3mf` produit (temps, masse, filament — emplacement exact à vérifier lors du spike).
- Optimisations « plus rapide / plus solide / moins de supports » = propositions de diff → [Appliquer et re-slicer] [Modifier] [Annuler].

### 4.3 Impression
- Défaut sûr : **ouvrir le `.gcode.3mf` dans Bambu Studio** ; l'utilisateur clique Imprimer lui-même.
- Option : envoi direct LAN (FTPS + MQTT `project_file`) si la H2D est en LAN-only + Developer Mode, derrière un écran « PRÊT À IMPRIMER » et un clic explicite.

### 4.4 Rendu
Viewer unique three.js pour tout. Blender seulement pour un rendu « réaliste » à la demande, jamais comme moteur CAO.

### 4.5 Pourquoi pas de MCP en interne
MCP est un protocole permettant à un client LLM (Claude Code, Claude Desktop…) d'appeler des outils. Ici, c'est **notre backend** qui orchestre : il appelle CadQuery/freecadcmd directement, plus simple et plus contrôlable. On pourra exposer plus tard notre propre serveur MCP si tu veux piloter l'app depuis Claude Code.

---

## 5. Dépendances (à installer seulement après validation)

| Étape | Dépendance | Rôle |
|---|---|---|
| V1 | `uv` (Homebrew) | gestionnaire Python rapide, environnement isolé du projet |
| V1 | Python 3.12 (déjà présent : `/opt/homebrew/bin/python3.12`) | backend |
| V1 | FastAPI, uvicorn, Pydantic, SQLite (stdlib) | API, validation des schémas, stockage |
| V1 | SDK `anthropic` + client OpenAI-compatible | couche LLM |
| V1 | Node 24 (déjà présent), Vite, React, TypeScript, three, @react-three/fiber, @react-three/drei, manifold-3d | front + maquette |
| V1 | git (init du dépôt) | historique du code |
| Ét. 2 | occt-import-js | STEP en pièce jointe |
| Ét. 3 | cadquery (OCP) | CAO A + mesure neutre |
| Ét. 4 | FreeCAD 1.1.x (.app, `freecadcmd`) | CAO B |
| Ét. 6 | Bambu Studio (présent, 02.05 — mise à jour probablement nécessaire, voir §7) | slicing |
| Ét. 7 | bambulabs_api | envoi H2D (optionnel) |

---

## 6. Local vs API

**100 % local** : interface, viewer, maquette, versioning, CadQuery, FreeCAD, mesures, slicing Bambu, envoi LAN à la H2D, Blender.

**Nécessite une API (recommandé)** : l'agent ingénieur et la génération de code CAO. La qualité de l'entretien adaptatif et l'analyse de photos exigent un modèle fort ; Claude est le choix par défaut proposé.

**Local possible, à évaluer** : Ollama (gemma4:12b, qwen2.5-coder installés) via l'adaptateur OpenAI-compatible. Probablement suffisant pour des tests d'interface, à mesurer sur les scénarios rejoués avant de s'y fier pour l'entretien ou la génération de code.

---

## 7. Limites techniques identifiées

1. **Cotes depuis une photo** : un LLM ne mesure pas une photo de façon fiable. Toute cote issue d'une photo est marquée `estimée` et l'agent demande les cotes critiques (ou une fiche technique fournie). Aucune cote d'objet réel inventée.
2. **Expressivité de la maquette** : limitée à la bibliothèque de composants. C'est voulu (rapidité, lisibilité), mais un concept exotique nécessitera d'ajouter des types.
3. **Sélection en phase concept** = composant + zone sémantique, pas de vraie arête B-rep (celle-ci arrive en phase CAO).
4. **STL importé** = maillage non paramétrique : utilisable comme référence fantôme et pour booléens, pas pour modifier ses « features ».
5. **Text-to-CAD reste fragile** : boucle exécution/réparation + mesures + contrôle des cotes du plan indispensables.
6. **H2D bi-buse en CLI** : la version locale 02.05.00.66 n'expose pas d'option de mapping filament/buse (`--help` vérifié) ; un projet tiers mentionne `--filament-map` et un bug de `model_settings.config` en 02.06.00.51. → **Spike dédié** avant l'étape 6.
7. **Envoi direct** : exige LAN-only + Developer Mode → Bambu Handy indisponible, pas de mises à jour OTA. D'où l'option « ouvrir dans Bambu Studio » par défaut.
8. **Exécution de code généré par LLM** : sous-processus isolé, timeout, dossier de travail dédié.
9. **Latence** : un tour d'entretien = un appel LLM (quelques secondes) ; la reconstruction de la maquette est négligeable. Le résumé du changement sera streamé.

---

## 8. Étapes de développement

| # | Contenu | Livrable testable |
|---|---|---|
| **0** | Dépôt git, squelette FastAPI + Vite/React, couche LLM (2 adaptateurs), SQLite, journal des appels | page qui dialogue avec le LLM |
| **1a** | Schémas `DesignSpec` / `ConceptGraph`, bibliothèque de ~12 composants, ConceptBuilder + viewer (3 modes) | graphe JSON écrit à la main → maquette affichée |
| **1b** | Agent ingénieur : patchs, question unique + boutons + Autre, critère d'arrêt, checkpoint | **boucle V1 complète** |
| **1c** | Versions immuables, timeline, diff par id + surlignage, avant/après (bascule, ghost, split synchronisé) | comparer Vn / Vn+1 |
| **1d** | Sélection composant/zone → contexte agent ; Plan de conception + validation | fin du prototype V1 |
| **1e** | 3–5 scénarios rejoués (support Xeneon Edge, boîtier USB-C rail DIN, adaptateur tube 12 mm…) pour évaluer l'entretien et comparer les LLM | grille d'évaluation |
| 2 | Pièces jointes : photos (vision), STL/STEP en objet de référence | |
| 3 | CAO A CadQuery + mesure neutre + GLB | |
| 4 | CAO B FreeCAD + mode « Comparer les deux » | |
| 5 | Itérations CAO conversationnelles (PARAMS), variantes | |
| 6 | Spike H2D CLI, puis préparation impression + analyse + optimisations | |
| 7 | Écran PRÊT À IMPRIMER ; ouverture Bambu Studio puis envoi LAN optionnel | |
| 8 | Rendu Blender optionnel | |

---

## 9. Sources
- CadQuery (PyPI) : https://pypi.org/project/cadquery/
- build123d : https://pypi.org/project/build123d/ — build123d-mcp : https://pypi.org/project/build123d-mcp/
- FreeCAD 1.1 : https://blog.freecad.org/2026/03/25/freecad-version-1-1-released/ — 1.1.4 : https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4
- gencad (headless) : https://github.com/gurul/gencad — gencad workbench : https://github.com/drfenixion/freecad.gencad
- FreeCAD robust MCP : https://github.com/spkane/freecad-addon-robust-mcp-server/releases
- Manifold : https://github.com/elalish/manifold — npm : https://www.npmjs.com/package/manifold-3d
- Benchmark booléens navigateur : https://polydera.com/algorithms/browser-mesh-boolean-libraries-2026
- occt-import-js : https://github.com/kovacsv/occt-import-js
- Chat3D : https://github.com/kreuzhofer/chat3d-app — local-ai-cad-agent : https://github.com/neuronaline/local-ai-cad-agent
- Bambu Studio CLI (wiki officiel) : https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
- H2D programmatique (notes tierces) : https://github.com/vertical-cloud-lab/powder-doser/pull/23
- LAN-only / Developer Mode : https://help.simplyprint.io/en/article/bambu-lab-lan-only-mode-and-developer-mode-how-to-enable-xa0hch/
- bambulabs_api : https://bambutools.github.io/bambulabs_api/examples.html
