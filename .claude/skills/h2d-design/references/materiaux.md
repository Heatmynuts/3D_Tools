# PLA et PETG — valeurs officielles Bambu Lab

Relevé le 2026-09-29. Chaque valeur cite sa source. Ne rien ajouter sans source.

## Sources
- [M1] Wiki « Filament guide — Printer, Nozzle, AMS, Build Plate, Glue Compatibility and Required Parameters » :
  https://wiki.bambulab.com/en/general/filament-guide-material-table
- [M2] Wiki « PLA Usage Guide » : https://wiki.bambulab.com/en/filament/pla
- [M3] Wiki « PETG Usage Guide » : https://wiki.bambulab.com/en/filament/petg

## Températures buse (M1, tolérance ± 10 °C indiquée par la source)
| Matière | Buse (°C) | Buse acier trempé obligatoire ? |
|---|---|---|
| PLA (standard : Basic, Matte, Tough…) | 190 – 240 | Non |
| PETG | 240 – 270 | Non |
| PETG HF | 230 – 260 | Non |
| PETG Translucent | 230 – 260 | Non |
| PETG-CF | 240 – 270 | Oui |

## Plateau (M1)
| Matière | Cool Plate / PLA Plate | Engineering Plate | Smooth PEI | Textured PEI | Retirer le capot vitré ? |
|---|---|---|---|---|---|
| PLA | 35 – 45 °C | 45 – 65 °C, colle requise | 45 – 65 °C | 45 – 65 °C | Recommandé si plateau > 45 °C |
| PETG / PETG HF / Translucent | Non recommandé | 60 – 80 °C | 60 – 80 °C | 60 – 80 °C | Recommandé si plateau > 70 °C |

- Chambre : PLA (ramollissement < 60 °C) → ouvrir la porte et/ou retirer le capot si plateau > 45 °C ;
  PETG (ramollissement 60–80 °C) → idem si plateau > 60 °C (M1, § 3). Le tableau du même wiki indique
  « > 70 °C » pour PETG : écart interne à la source, retenir le seuil le plus bas (60 °C) par prudence.
- PETG : une imprimante fermée est recommandée pour éviter une baisse de la résistance entre couches
  par temps froid (M1).
- Le plateau livré avec la H2D est le Textured PEI (voir `h2d.md`).

## Séchage (M1, sauf mention)
| Matière | Séchage avant usage | Étuve ventilée | AMS 2 Pro / AMS HT | Dessiccant pendant l'impression |
|---|---|---|---|---|
| PLA | Recommandé | 55 °C, 8 h | 45 °C, 12 h | Optionnel |
| PETG | Recommandé | 70 °C, 8 h | 65 °C, 12 h | Optionnel |
| PETG HF / Translucent | **Requis** | 65 °C, 8 h | 65 °C, 12 h | **Requis** |

- M3 donne pour PETG Basic / HF / CF / Translucent : étuve 60 – 65 °C 8 h ; plateau chauffant 80 °C 12 h ;
  AMS HT / AMS 2 Pro 65 °C 8 h. Écart avec M1 sur l'étuve PETG (70 °C) : les deux sources sont officielles.
- PLA : faible absorption d'humidité, stockable à 50–60 % HR (M2).

## Propriétés d'usage
| Point | PLA | PETG | Source |
|---|---|---|---|
| Température de fléchissement (HDT) | 57 °C | non chiffrée | M2 |
| Environnement ≥ ~50 °C | Déconseillé (ramollit, se déforme) | Meilleure tenue en température | M1 |
| Résistance aux chocs (échelle ⭐ Bambu) | ⭐⭐ | ⭐⭐⭐ | M1 |
| Résistance en traction (échelle ⭐ Bambu) | ⭐⭐⭐ | ⭐⭐ | M1 |
| Contact alimentaire | Non (sauf PLA Pure) | Non | M2, M3 |
| Gauchissement | Peu sujet | Plus sujet que le PLA | M1, M3 |

## Réglages PETG utiles (M3)
- Débit (flow ratio) : 0,93 – 0,96 ; défaut PETG Basic / PETG-CF : 0,95.
- PETG HF non séché : profil « Generic PETG HF » (buse 220 °C, débit volumique 16 mm³/s).
- Largeur de ligne par défaut buse 0,4 mm : paroi intérieure 0,45 mm, paroi extérieure 0,42 mm.
  Plage conseillée : 0,75 à 1,5 × diamètre de buse.
- Résistance : parois ≤ 6, remplissage ≤ 50 % ; plus de parois/remplissage = plus de risque de gauchissement
  → colle ou bordure (brim).
- Gauchissement : colle sur le plateau, bordure (brim).
- Surplombs : ne pas placer la couture (seam) dans la zone en surplomb.

## Réglages PLA utiles (M2)
- Nettoyer le plateau à l'eau chaude + liquide vaisselle avant impression.
- Attendre le refroidissement complet du plateau avant de retirer la pièce.
- Ambiance recommandée : 10 – 30 °C. En été : ouvrir la porte, baisser le plateau de 5 – 10 °C
  (défaut 55 °C) pour éviter le bouchage par fluage thermique.
- Après ABS/PC : faire un « cold pull » de la buse avant de repasser au PLA.
