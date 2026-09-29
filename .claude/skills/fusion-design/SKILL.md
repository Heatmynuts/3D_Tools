---
name: fusion-design
description: Conception native dans Autodesk Fusion 360 via le serveur MCP officiel Autodesk (session locale uniquement). À charger quand l'utilisateur demande de créer, modifier ou exporter une pièce dans Fusion, ou quand des outils MCP « fusion » sont disponibles.
---

# Conception native Fusion 360 (MCP officiel Autodesk)

Installation et limites : `docs/local-fusion360.md`. Règles de conception FDM : skill `h2d-design`
(le charger aussi : mêmes règles sourcées, même imprimante).

## 0. Pré-requis de session
- Vérifier que des outils MCP du serveur `fusion` sont présents. Sinon (session cloud, Fusion fermé) :
  le dire, et proposer la voie build123d du projet (`parts/<nom>/part.py`).
- Commencer par lister les outils disponibles et lire la documentation API fournie par le serveur
  (ne pas supposer un nom d'outil : ils sont découverts à la connexion).

## 1. Règles de modélisation dans Fusion
- **Un document par pièce**, nom = nom du dossier `parts/<nom>`.
- **Paramètres utilisateur Fusion** = mêmes noms et valeurs que la section PARAMÈTRES de
  `parts/<nom>/part.py` quand elle existe (ex. `JEU_ECRAN`, `EPAISSEUR_PAROI`), unités mm / deg.
  Toute cote d'esquisse ou de fonction référence un paramètre, jamais un nombre en dur.
- Esquisses **entièrement contraintes** ; fonctions **nommées** dans la timeline
  (ex. `Logement_ecran`, `Levre_avant`, `Congé_R1.5`).
- Un **composant** par pièce imprimée (moitiés, embouts…), pas de corps multiples dans un même composant.
- Orientation : Z = direction d'impression quand c'est possible (sinon noter l'orientation prévue).
- Modification demandée = changer le paramètre utilisateur concerné ; annoncer ancienne → nouvelle valeur.

## 2. Scripts API (quand le serveur exécute du Python Fusion)
Appels standards de l'API Fusion (à valider contre la documentation renvoyée par le serveur) :
```python
import adsk.core, adsk.fusion
app = adsk.core.Application.get()
design = adsk.fusion.Design.cast(app.activeProduct)
params = design.userParameters
params.add("EPAISSEUR_PAROI", adsk.core.ValueInput.createByString("3.2 mm"), "mm", "paroi coque")
# Export STEP d'un composant
em = design.exportManager
opts = em.createSTEPExportOptions("/chemin/3D_Tools/parts/<nom>/out/<nom>_<composant>.step", composant)
em.execute(opts)
```
- Écrire les exports dans `parts/<nom>/out/` (chemin absolu du dépôt local).

## 3. Boucle de travail
1. Créer / ouvrir le document ; créer les paramètres utilisateur.
2. Modéliser par étapes ; après chaque étape importante, vérifier (mesures, interférences) avec les
   outils du serveur quand ils existent.
3. Exporter STEP (+ STL pour la vue) dans `parts/<nom>/out/`, puis :
   `python3 tools/make_view.py parts/<nom>` et `python3 tools/render.py parts/<nom>`
   (les STL doivent être listés dans `out/resume.json` ; sinon créer un `part.py` qui importe les STEP
   Fusion et appelle `export_all`, comme `parts/xeneon_edge/part.py`).
4. Enregistrer une version du document Fusion (commentaire = résumé de la modification).
5. Commit + push des exports.

## 4. Sécurité
- Demander confirmation avant : écraser/fermer un document non enregistré, supprimer des corps,
  composants ou fonctions de la timeline.
- Ne jamais toucher aux documents Fusion hors du projet en cours.
