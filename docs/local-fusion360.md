# Fusion 360 piloté par Claude (local)

Le serveur MCP **officiel Autodesk** tourne à l'intérieur de Fusion (application de bureau).
Il permet à Claude Code de piloter ta session Fusion : exécuter des scripts de l'API Fusion,
inspecter le modèle, lire la documentation de l'API.

Sources : [Autodesk Fusion MCP Server (aide Autodesk)](https://help.autodesk.com/view/ADSKMCP/ENU/?guid=ADSKMCP_FusionDesktopMcp_autodesk_fusion_mcp_server_html),
[Autodesk MCP Server Help](https://help.autodesk.com/view/ADSKMCP/ENU/),
[doc MCP Claude Code](https://code.claude.com/docs/en/mcp).

## Limites (documentées par Autodesk)
- **Bureau uniquement** : ne fonctionne pas avec Fusion web.
- **Local uniquement** : pas de connexion à distance → **impossible depuis les sessions cloud**
  (web, app iPhone/iPad). Il faut Claude Code installé sur le Mac/PC où Fusion est ouvert.
- Transport **Streamable HTTP** ; Fusion doit être lancé pendant la session.
- Les outils exposés sont découverts à la connexion (liste non publiée).

## 1. Activer le serveur dans Fusion
1. Fusion → **Préférences → Général → API**.
2. Cocher **Fusion MCP Server**.
3. Noter **l'adresse (URL) et le port affichés** par Fusion. Autodesk précise que le port peut
   changer : toujours utiliser la valeur affichée, pas une valeur recopiée d'ailleurs.

## 2. Brancher Claude Code (portée utilisateur)
Remplacer `<URL affichée par Fusion>` par l'adresse notée à l'étape 1 :
```bash
claude mcp add --transport http --scope user fusion <URL affichée par Fusion>
claude mcp list        # « fusion » doit apparaître connecté (Fusion ouvert)
```
Puis lancer Claude Code dans le dossier du projet (`cd 3D_Tools && claude`).

## 3. Utilisation
- « Crée la coque Xeneon dans Fusion » → Claude suit le skill `fusion-design` (paramètres
  utilisateur Fusion, esquisses contraintes, fonctions nommées dans la timeline).
- Les exports (STEP / 3MF) sont écrits dans `parts/<nom>/out/` pour garder la vue 3D, les rendus
  PNG et le contrôle H2D du projet.
- Claude **demande confirmation** avant toute action destructive dans Fusion (écraser un document,
  supprimer des corps/composants).

## Dépannage
- `claude mcp list` montre « failed » → Fusion fermé, option non cochée, ou URL/port modifiés.
- Pas d'outil Fusion dans la session → relancer Claude Code après avoir activé le serveur.
