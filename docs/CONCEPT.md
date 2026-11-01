# Concept de 3D Tool

## Promesse

Transformer un besoin concret en pièce fonctionnelle **compréhensible, corrigeable et préparée pour l'impression**, sans demander à l'utilisateur de maîtriser un logiciel de CAO. Photos, croquis, cotes, composants standards et contraintes d'assemblage alimentent le même projet.

## Parcours visé

1. **Comprendre** : identifier l'objet réel, les interfaces, les cotes confirmées et les inconnues qui empêchent une conception fiable.
2. **Montrer** : afficher rapidement une maquette 3D et surligner précisément les zones modifiées. Une correction ne doit pas effacer silencieusement les formes conservées.
3. **Construire** : produire une géométrie CAO contrôlable, comparer les variantes et vérifier volumes, collisions, accès, épaisseurs et jeux documentés.
4. **Préparer l'impression** : proposer orientation, séparation éventuelle des pièces, supports, adhérence au plateau, matériaux et paramètres localisés selon la fonction et la finition attendue.
5. **Valider** : distinguer modèle exporté, maillage valide, aperçu après découpage, impression réussie et ajustement physique. Chaque étape apporte une preuve différente.

## Cas d'usage de référence

- Refaire un capot à partir de photos et de mesures.
- Loger une carte électronique et ses connecteurs en préservant l'accès au câble.
- Corriger un boîtier après essai physique : déplacer un appui, ouvrir une fenêtre, noyer une tête de vis, compenser un filetage imprimé.
- Préparer une maquette légère avec une face visible propre et des paramètres adaptés à une imprimante donnée.

## État et limites

Le prototype présent dans ce dépôt implémente le dialogue structuré, la visualisation conceptuelle, la comparaison de versions et un flux CadQuery/Bambu H2D local. Il ne garantit pas encore une optimisation automatique fiable de chaque impression ni une compatibilité universelle avec les imprimantes. Les cotes critiques et les interfaces physiques doivent être confirmées, puis vérifiées sur une pièce réelle.
