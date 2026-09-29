---
name: h2d-design
description: Règles de conception de pièces imprimées en 3D (FDM) pour la Bambu Lab H2D en PLA et PETG, avec valeurs sourcées (wiki Bambu Lab). À charger avant de concevoir, modifier ou conseiller une pièce, un réglage d'impression ou un choix de matière.
---

# Conception pour Bambu Lab H2D (PLA / PETG)

Références (valeurs sourcées, à lire selon le besoin) :
- `references/h2d.md` : volume d'impression, buses, zones buse gauche/droite, plateau, chambre.
- `references/materiaux.md` : températures, plateaux, séchage, propriétés PLA / PETG.

Règle absolue : **ne citer que des valeurs présentes dans ces fichiers ou dans une source
consultée pendant la session (donner l'URL)**. Sinon écrire « non sourcé » ou « pratique générale ».

## Sources des règles ci-dessous
- [R1] Surplombs : https://wiki.bambulab.com/en/filament-acc/filament/print-quality/overhang
- [R2] Supports : https://wiki.bambulab.com/en/software/bambu-studio/support
- [R3] Grands modèles découpés : https://wiki.bambulab.com/en/bambu-studio/manual/3d-print-large-files
- [M1] Guide filaments : https://wiki.bambulab.com/en/general/filament-guide-material-table
- [M2] PLA : https://wiki.bambulab.com/en/filament/pla
- [M3] PETG : https://wiki.bambulab.com/en/filament/petg

## Checklist de conception

### 1. Choix de la matière
- Pièce exposée à ≥ ~50 °C (près d'une source de chaleur, voiture, étuve) → PETG, pas PLA [M1].
- Besoin de résistance aux chocs → PETG (⭐⭐⭐ vs ⭐⭐) ; rigidité/traction → PLA (⭐⭐⭐ vs ⭐⭐) [M1].
- Contact alimentaire → ni PLA standard ni PETG [M2, M3].
- Laboratoire : aucune donnée de tenue chimique trouvée dans les sources Bambu → le signaler,
  ne pas conclure.

### 2. Orientation
- Choisir l'orientation d'impression dès la conception ; `part.py` modélise la pièce posée sur le plateau.
- PETG : orienter selon la direction principale de l'effort ; Bambu recommande que la direction
  de l'effort forme un angle de 90° avec le plan d'extrusion du filament [M3].
- Exemple chiffré Bambu (PLA Silk) : la résistance selon Z (entre couches) est plus faible
  que selon XY [M2]. Ne pas généraliser le chiffre (65 %) aux autres PLA.

### 3. Surplombs et ponts
- Angle de surplomb = angle entre la face inclinée et le plateau.
  **< 45° → prévoir des supports ; > 45° → pas de support nécessaire** [R1].
- Seuil de génération automatique des supports dans Bambu Studio : 30° par défaut [R2].
- Concevoir pour éviter les supports : chanfreins ≥ 45° sous les parties en porte-à-faux (application directe de R1).
- PETG : éviter la couture (seam) dans les zones en surplomb [M3].

### 4. Assemblages et jeux
- Tenons / mortaises d'un modèle découpé : jeu de **0,15 à 0,3 mm** [R3].
- Toujours mettre le jeu en paramètre nommé (`JEU = 0.2`) pour l'ajuster après un essai.

### 5. Parois et détails fins
- Largeur de ligne par défaut, buse 0,4 mm : 0,42 mm (paroi ext.) / 0,45 mm (paroi int.) [M3].
- Aucune épaisseur minimale officielle trouvée pour PLA/PETG standard. Déduction (à signaler comme telle) :
  une paroi fine = au moins 2 largeurs de ligne ≈ 0,9 mm.
- Boîtiers (grand fond + parois fines) : ajouter un **congé ou chanfrein intérieur** à la jonction
  fond/paroi pour supprimer les lignes de « changement de section » [M2, M3].

### 6. Gauchissement (surtout PETG)
- PETG plus sujet au gauchissement que le PLA [M3]. Grandes surfaces plates : prévoir bordure (brim)
  et colle ; éviter les angles vifs sur la face plateau (pratique générale, non sourcée Bambu).

### 7. Volume H2D
- Contrôle automatique dans `tools/export.py` : 325 × 320 × 320 mm (voir `references/h2d.md`).
- Pièce plus haute que 320 mm → buse droite uniquement.

## Réponse type après conception
1. Dimensions hors-tout (mm) et volume de la pièce.
2. Matière conseillée + raison (avec source).
3. Orientation d'impression et besoin de supports (angle le plus faible trouvé).
4. Réglages Bambu Studio à vérifier (températures, plateau) depuis `materiaux.md`.
5. Paramètres modifiables pour la prochaine itération.
