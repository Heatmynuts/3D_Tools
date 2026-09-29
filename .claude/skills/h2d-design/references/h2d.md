# Bambu Lab H2D — caractéristiques utiles à la conception

Relevé le 2026-09-29. Chaque ligne cite sa source.

## Sources
- [S1] Fiche technique, boutique Bambu Lab : https://us.store.bambulab.com/products/h2d
- [S2] Wiki « Introduction to the printable range of H2D dual nozzles » :
  https://wiki.bambulab.com/en/h2/manual/printable-range-for-dual-nozzles
- [S3] Wiki « H2D introduction » : https://wiki.bambulab.com/en/h2/manual/h2d-intro

## Volume d'impression
| Cas | Volume (L × P × H, mm) | Source |
|---|---|---|
| Une seule buse | 325 × 320 × 325 | S1 |
| Deux buses (zone commune) | 300 × 320 × 325 (S1) ; 300 × 320 × 320 (S2) | S1, S2 |
| Total avec les deux buses (filaments identiques) | 350 × 320 × 325 | S1 |
| Buse gauche seule | 325 × 320 × 320, coordonnées X 0→325 | S2 |
| Buse droite seule | 325 × 320 × 325, coordonnées X 25→350 | S2 |

Notes :
- Hauteur max buse gauche 320 mm, buse droite 325 mm. Une pièce de plus de 320 mm de haut
  ne peut être imprimée qu'avec la buse droite (S2).
- Écart S1/S2 sur la hauteur de la zone commune (325 vs 320 mm) : retenir **320 mm** (valeur la plus basse).
- Surface max du plateau chauffant : 350 × 320 mm (S3).
- Pour le contrôle automatique (`tools/export.py`), on retient : **325 × 320 × 320 mm**
  (compatible avec les deux buses en hauteur).

## Tête et plateau
| Élément | Valeur | Source |
|---|---|---|
| Température max buse | 350 °C | S1, S3 |
| Diamètre de buse fourni | 0,4 mm | S1 |
| Diamètres de buse supportés | 0,2 / 0,4 / 0,6 / 0,8 mm | S1 |
| Buse | acier trempé | S1 |
| Diamètre filament | 1,75 mm | S1 |
| Température max plateau | 120 °C | S3 |
| Chambre | chauffage actif 65 °C | S1 |
| Plateau fourni | Textured PEI Plate | S1, S3 |

## Multi-matière
- Les deux hotends sont identiques et interchangeables (S1, FAQ 2).
- Jusqu'à 4 AMS 2 Pro + 8 AMS HT (S1, FAQ 3). AMS lite non supporté (S1, FAQ 4).
- Si une pièce est posée dans la zone « buse gauche seule » ou « buse droite seule »,
  tous ses filaments (y compris supports, peinture, purge dans le remplissage) doivent être
  sur cette buse, sinon Bambu Studio refuse de trancher (S2).
