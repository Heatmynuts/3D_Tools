# Impression — coque Xeneon Edge (PETG, H2D)

Fichier : `plateau/out/coque_xeneon_plateau.3mf` (2 moitiés déjà orientées et placées).

## Orientation
- **Face avant (côté écran) contre le plateau** : c'est la 1re couche → meilleure finition, texture de la plaque.
- Moitiés côte à côte : 194,4 × 274,2 mm au total, dans la zone commune aux 2 buses (300 × 320 mm,
  [wiki H2D](https://wiki.bambulab.com/en/h2/manual/printable-range-for-dual-nozzles)) → PETG et PLA atteignent tout.
- Surplombs restants (analyse build123d-mcp) : **uniquement le rebord arrière** (portées 13,6 mm et 72,4 mm
  sur la zone de poche) → supports là seulement. Aucune marque de support côté écran.

## Matières et supports (double buse)
Source : [Using PLA Basic & PETG as Mutual Supports](https://wiki.bambulab.com/en/filament-acc/filament/h2d-pla-and-petg-mutual-support)
| Rôle | Filament | Buse | Plateau |
|---|---|---|---|
| Pièce | Bambu PETG HF ou PETG Basic | profil par défaut | 60 °C |
| Interface de support | Bambu PLA Basic | 230 °C toutes couches | 60 °C |

- PLA **en interface seulement** ; la base des supports reste en PETG (recommandation Bambu).
- Sécher les filaments avant (PETG HF : séchage requis, 65 °C 8 h en étuve — [guide filaments](https://wiki.bambulab.com/en/general/filament-guide-material-table)).

## ⚠ Points non couverts par les sources
- La méthode Bambu indique **Smooth PEI ou Textured PEI requis**. Ta plaque « finition carbone » n'est pas
  couverte : vérifier la notice du fabricant (température PETG, colle) ou faire un essai sur une petite pièce.
- Filaments tiers non couverts par la méthode.

## Contre le gauchissement (PETG)
- Bordure (brim) et colle sur le plateau ([wiki PETG](https://wiki.bambulab.com/en/filament/petg)).
- Couture (seam) hors des zones en surplomb (même source).

## Verre trempé
`EPAISSEUR_VERRE`, `VERRE_L`, `VERRE_W` dans `part.py` sont à 0 : **à renseigner avant impression**.
Critères d'achat : 354,6 ≤ longueur ≤ 372,7 mm ; 99,8 ≤ largeur ≤ 120,1 mm ; épaisseur connue.
