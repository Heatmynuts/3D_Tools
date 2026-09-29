# Utilisation en local (Mac / PC) avec pilotage de la H2D

Le pilotage de l'imprimante n'est possible **que depuis un ordinateur sur le même réseau
que la H2D**. Les sessions cloud (web, app iPhone/iPad) servent à concevoir ; l'envoi à
l'imprimante se fait depuis Claude Code installé sur ton Mac ou PC.

Sources : [bambu-printer-mcp README](https://github.com/DMontgomery40/bambu-printer-mcp),
[SETUP.md](https://github.com/DMontgomery40/bambu-printer-mcp/blob/main/docs/SETUP.md),
[doc MCP Claude Code](https://code.claude.com/docs/en/mcp),
[text-to-cad](https://github.com/earthtojake/text-to-cad).

## 1. Prérequis
| Outil | Usage | Remarque |
|---|---|---|
| Claude Code | agent local | https://code.claude.com |
| Python 3.11+ | build123d (CAO) | `pip install build123d` |
| uv | serveur MCP build123d | https://docs.astral.sh/uv/ |
| Node.js 24 | bambu-printer-mcp | version testée par l'auteur |
| Bambu Studio | tranchage (slicing) | déjà installé normalement |
| ffmpeg | photo caméra H2D (optionnel) | macOS : `brew install ffmpeg` |

## 2. Cloner le projet
```bash
git clone https://github.com/heatmynuts/3D_Tools.git
cd 3D_Tools
claude
```
Au premier lancement, accepter la confiance du dossier : cela active le serveur MCP
`build123d` (`.mcp.json`) et propose le plugin `cad@text-to-cad` (`.claude/settings.json`).

## 3. Préparer la H2D (écran de l'imprimante)
1. **Paramètres → Réseau (WLAN)** : noter l'**adresse IP** et le **code d'accès (Access Code)**.
2. Activer **LAN Only Mode**, puis **Developer Mode** si l'option existe.
3. **Paramètres → Device Info** : noter le **numéro de série**.

⚠ Conséquence documentée par l'auteur du MCP : en **LAN Only Mode**, l'imprimante est
déconnectée du cloud Bambu ; **Bambu Handy ne fonctionne plus** tant que le mode est actif.
Bambu Studio continue de fonctionner en réseau local.

⚠ Si tu rafraîchis le code d'accès sur l'écran, l'ancien est invalidé : mettre à jour la config.

## 4. Ajouter le serveur imprimante (portée utilisateur, hors git)
Le code d'accès ne doit **jamais** être commité : on l'ajoute en portée `user`
(fichier `~/.claude.json` de ton ordinateur).

macOS (chemin Bambu Studio par défaut indiqué par l'auteur du MCP) :
```bash
claude mcp add bambu --scope user \
  --env PRINTER_HOST=192.168.X.X \
  --env BAMBU_SERIAL=TON_NUMERO_DE_SERIE \
  --env BAMBU_TOKEN=TON_CODE_ACCES \
  --env BAMBU_MODEL=h2d \
  --env BED_TYPE=textured_plate \
  --env NOZZLE_DIAMETER=0.4 \
  --env SLICER_TYPE=bambustudio \
  --env SLICER_PATH=/Applications/BambuStudio.app/Contents/MacOS/BambuStudio \
  -- npx -y bambu-printer-mcp
```
Windows : même commande sur une seule ligne ; remplacer `SLICER_PATH` par le chemin de
`bambu-studio.exe` sur ton PC (non documenté par l'auteur : à relever dans l'explorateur).

Vérifier : `claude mcp list` → `bambu` doit apparaître connecté.

## 5. Installer le plugin text-to-cad (si non proposé automatiquement)
```bash
claude plugin marketplace add earthtojake/text-to-cad
claude plugin install cad@text-to-cad
```
Apporte en local : visionneuse CAO dans le navigateur, contrôle DfAM (parois, surplombs),
tranchage G-code.

## 6. Flux de travail type
1. Sur iPhone/iPad (cloud) : « conçois un support pour … » → vue 3D + fichiers dans `parts/<nom>/out/`.
2. Sur le Mac/PC : `git pull`, ouvrir `parts/<nom>/out/<nom>.3mf` dans Bambu Studio **ou**
   demander à Claude : « tranche et envoie `parts/<nom>/out/<nom>.3mf` à la H2D en PETG ».
3. Claude vérifie l'état de l'imprimante (statut, AMS) avant l'envoi et demande confirmation.
