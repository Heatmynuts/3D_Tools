# 3D_Tools — atelier de conception 3D pour Bambu Lab H2D

## Profil utilisateur
- Novice en CAO. Répondre en français, court, précis, analytique.
- **Aucune invention** : toute valeur matière / imprimante vient d'une source citée
  (voir `.claude/skills/h2d-design/references/`). Si l'info manque : le dire, ne pas estimer.
- Matières utilisées : PLA / PLA+ et PETG. Imprimante : Bambu Lab H2D (double buse).

## Outils
- CAO : **build123d** (Python, noyau OpenCascade). Pas d'OpenSCAD, pas de maillage IA.
- MCP `build123d` (`.mcp.json`) : exécution, mesures, contrôle d'imprimabilité, aperçus PNG.
- Plugin `cad@text-to-cad` : déclaré dans `.claude/settings.json`, **chargé en local seulement**
  (les sessions cloud n'installent pas les plugins du repo).
- Pilotage H2D (`bambu-printer-mcp`) : **local seulement**, voir `docs/local-h2d.md`.

## Structure d'une pièce
```
parts/<nom>/part.py     # PARAMÈTRES en tête (mm), fonctions build_*(), export
parts/<nom>/out/        # .step .stl .3mf .glb resume.json + vue 3D .html (générés)
parts/<nom>/vue3d.url   # lien de l'Artifact de la vue 3D
tools/export.py         # export multi-format + contrôles (volume H2D, dimensions)
tools/make_view.py      # STL + resume.json -> page HTML 3D autonome (à publier en Artifact)
tools/render.py         # rendus PNG réalistes multi-angles -> parts/<nom>/rendus/
viewer/template.html    # gabarit de la vue 3D (three.js)
```

## Méthode de travail (à chaque demande)
1. Charger le skill `h2d-design` avant de concevoir ou modifier une pièce.
2. Toute cote = un paramètre nommé en tête de `part.py`. Jamais de nombre magique dans le code.
3. Une demande de modification = modifier le(s) paramètre(s) ou la fonction concernée, rien d'autre.
   Annoncer : paramètre, ancienne valeur → nouvelle valeur.
4. Générer : `python3 parts/<nom>/part.py` (exports + contrôles).
5. Vérifier soi-même : aperçu PNG (MCP build123d) relu avant de livrer.
6. Vue 3D : `python3 tools/make_view.py parts/<nom> --titre "Nom"` puis publier
   `parts/<nom>/out/<nom>_vue3d.html` en Artifact. Le lien est noté dans `parts/<nom>/vue3d.url` :
   s'il existe, republier avec ce `url` (même lien) ; sinon créer puis écrire le lien dans ce fichier.
7. Livrer : lien de la vue 3D + rendus PNG (`python3 tools/render.py parts/<nom> [--couleur "#hex"]`,
   vue `detail` = gros plan des stries ; `--photo` = lancer de rayons, ~3-4 min/image ; relus avant envoi) + résumé (dimensions, matière conseillée, orientation, supports)
   + chemin du `.3mf`/`.step` pour Bambu Studio. La vue 3D a un bouton « Rendu » (aspect réaliste).
8. Commit + push sur la branche de travail.
9. Impression (local uniquement) : vérifier l'état de la H2D et l'AMS, résumer
   (fichier, matière, buse, plateau) et **demander confirmation avant tout envoi**.

## Modèles importés (gabarits)
- Chercher d'abord un modèle **officiel du fabricant** (STEP de préférence). Noter auteur,
  licence, lien et date dans `parts/<nom>/SOURCE.md` ; conserver le fichier d'origine dans
  `parts/<nom>/source/` sans le modifier.
- `part.py` importe le STEP et appelle `export_all(..., reference=True, source=ATTRIBUTION)` :
  maillage allégé, pas de STEP ni de 3MF exportés, attribution affichée dans la vue 3D.
- Printables bloque les robots sur le site web ; son API publique `https://api.printables.com/graphql/`
  permet de lister les fichiers d'un modèle et d'obtenir le lien de téléchargement.
- Exemple : `parts/xeneon_edge/`.

## Règles CAO
- Unités : mm. Origine : centre de la face posée sur le plateau (Z=0 = plateau).
- Orienter la pièce dans `part.py` dans sa position d'impression.
- Vérifier que la boîte englobante tient dans le volume H2D (`tools/export.py` le contrôle).
- Règles de conception FDM : uniquement celles du skill `h2d-design` (sourcées). Une règle
  « pratique générale » non sourcée doit être signalée comme telle.
