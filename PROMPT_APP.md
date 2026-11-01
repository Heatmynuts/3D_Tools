# Application 3D Tool — cadrage version 2, 30 septembre 2026

Je veux que tu poursuives la conception et le développement d'une application locale de conception mécanique assistée par IA, destinée principalement à la création de pièces fonctionnelles imprimables en 3D sur une Bambu Lab H2D.

L'objectif n'est PAS de générer immédiatement une pièce à partir d'un prompt.

C'est un véritable workflow de conception mécanique conversationnel, visuel, séquentiel et contrôlé par l'utilisateur :

IDÉE
→ compréhension du besoin
→ exploration visuelle rapide
→ concept validé
→ conception CAO
→ comparaison de moteurs CAO
→ validation mécanique
→ préparation impression
→ slicing
→ validation
→ impression sur Bambu Lab H2D.

Aucune étape importante ne doit être franchie automatiquement.

L’application vise des pièces fonctionnelles. Elle doit détecter les aberrations couvertes par ses contrôles et exposer les limites de validation ; elle ne garantit pas l’absence de tout défaut mécanique.

==================================================
0. ÉTAT ACTUEL DU PROJET (à lire en premier)
==================================================

Dépôt : ~/3D_Tool. Documents de référence : PLAN.md (architecture, étapes), CLAUDE.md (état, conventions).

Fonctionnalités décrites comme réalisées dans le cadrage précédent (leur présence ne remplace pas une nouvelle validation sur scénarios) :

- Étape 0 et prototype V1 (1a → 1d) : entretien adaptatif, maquette 3D évolutive, versions, diff visuel, sélection, checkpoint, plan de conception.
- Comparaison A/B de modèles : Claude (API Anthropic directe) contre un modèle choisi via OpenRouter.
- Revue technique déterministe : RDM appliquée à l'impression FDM, sens d'impression, mise en position / maintien en position.
- Suivi des coûts par appel, par étape et par modèle, et affichage des soldes de crédits.

Stack en place (ne pas la remettre en cause sans raison) :

- Backend Python 3.12 (uv), FastAPI, Pydantic, SQLite.
- Frontend React + TypeScript (Vite), three.js / React Three Fiber, manifold-3d (WASM).
- Lancement : ./dev.sh (backend :8000, frontend :5180). Clés dans backend/.env.

Mise à jour d’implémentation du 30 septembre 2026 : verrous conceptuels côté backend, CAO CadQuery avec exports et variantes, acceptation géométrique, sélection des profils officiels H2D et du plateau, slicing Bambu Studio 2.8.2.61 et acceptation du résultat sont maintenant codés. Rapport et limites : `docs/validation/2026-09-30-workflow.md`. FreeCAD/build123d et les contrôles mécaniques approfondis restent prévus.

Prochaine étape d’évaluation prévue : 1e — rejouer 3 à 5 scénarios de référence pour évaluer la qualité de l'entretien et comparer les modèles, avant d'intégrer la CAO.

État des garanties : la revue actuelle reste partielle. Elle est recalculée après patch et le backend refuse un checkpoint avec blocage ou inconnue forte, ainsi qu’un plan prématuré. Les dérogations explicites aux blocages ne sont pas encore gérées : résoudre le blocage pour valider. La validité géométrique STEP et l’acceptation utilisateur ne démontrent pas la résistance.

Le dépôt de l’application est `/Users/alexandreperou/3D_Tool`. L’initialisation Spec Kit observée dans `/Users/alexandreperou/Documents/ChatGPT/3D_Tool` est distincte : ne pas considérer les deux chemins comme interchangeables. Toute adoption de Spec Kit doit préciser le dépôt cible.

Travaille étape par étape. Présente ton plan pour chaque nouvelle étape et ATTENDS MA VALIDATION avant de l'implémenter.

==================================================
1. PRINCIPE FONDAMENTAL
==================================================

Trois niveaux strictement séparés :

1. CONCEPT : comprendre ce que l'utilisateur veut réellement fabriquer.
2. CAO : transformer le concept validé en véritable géométrie mécanique paramétrique.
3. FABRICATION : transformer la géométrie validée en fichier et paramètres adaptés à la Bambu Lab H2D.

Ne jamais mélanger ces niveaux. L'utilisateur peut revenir en arrière à tout moment sans perdre son travail.

==================================================
2. INTERFACE
==================================================

Application web locale, très visuelle et simple :

- zone conversationnelle ;
- grand viewer 3D ;
- état du projet ;
- historique des versions ;
- actions disponibles au moment pertinent.

Panneau de droite à onglets : État (cahier des charges ou plan) | Revue (revue technique) | Coûts.

L'utilisateur ne doit pas avoir l'impression d'utiliser FreeCAD, CadQuery, Blender ou un IDE : ces technologies restent en arrière-plan.

==================================================
3. DÉMARRAGE D'UN PROJET
==================================================

Description libre en langage naturel, avec possibilité de joindre (étape 2, à venir) : photos, dessin, plan coté, STL, STEP, autres formats CAO exploitables.

Pas d'énorme formulaire au départ.

==================================================
4. AGENT « INGÉNIEUR CONCEPTION »
==================================================

L'agent n'écrit pas de code. Il transforme une intention humaine en cahier des charges mécanique suffisamment précis pour lancer une conception.

Il raisonne comme un ingénieur en conception mécanique spécialiste de l'impression FDM.

Il analyse :

- le prompt initial ;
- les documents fournis ;
- les réponses précédentes ;
- le concept 3D courant ;
- les contraintes connues ;
- la revue technique automatique de la version courante.

Il produit des données structurées (DesignSpec) :

- exigences, contraintes, décisions, paramètres (avec statut connu / estimé / à déterminer et source), inconnues (avec impact) ;
- orientation d'impression de chaque pièce ;
- cas de charge ;
- mise en position (liaisons normalisées) et maintien en position de chaque objet réel tenu par la pièce.

Il distingue les valeurs illustratives de la maquette, les hypothèses de conception et les données confirmées. Une dimension illustrative rend le concept visible ; elle ne vaut jamais mesure réelle ni cote validée pour fabrication. Les valeurs par défaut du catalogue restent illustratives tant qu’elles ne sont pas confirmées.

Une cote critique inconnue reste `null` dans DesignSpec, même si ConceptGraph utilise une valeur illustrative. Une hypothèse chiffrée est explicitement marquée estimée, justifiée et assortie d’une mesure ou d’un essai à réaliser. Aucune propriété matériau, résistance, admissible ou effort n’est inventé. Un jeu provisoire n’est jamais présenté comme validé.

Le schéma actuel ne possède pas de référence documentaire détaillée : utiliser les contraintes et notes existantes pour identifier fichier, page, profil ou méthode. Une évolution du schéma devra ajouter une provenance structurée, sans introduire silencieusement des champs ignorés par le backend.

==================================================
5. ENTRETIEN ADAPTATIF
==================================================

Pas de questionnaire fixe.

Prompt initial + réponses précédentes → déterminent la question suivante.

À chaque tour, l'agent pose UNE question : celle qui a le plus de valeur pour la conception.

Réponses proposées sous forme de 2 à 5 boutons, plus « Autre / préciser ».

Une question n'est justifiée que si sa réponse peut modifier la géométrie, le choix constructif, l'assemblage ou la fabricabilité.

Critère d'arrêt : « Une réponse supplémentaire changerait-elle significativement la géométrie, le choix constructif, l'assemblage ou la fabricabilité ? » Si non et si aucune inconnue forte ne bloque le principe constructif ou la préparation du plan, proposer le checkpoint. Viser 3 à 7 questions sans imposer un plafond technique. Les inconnues restantes restent visibles et assorties de conditions de résolution.

==================================================
6. MAQUETTE 3D CONCEPTUELLE EN TEMPS RÉEL
==================================================

Ce n'est PAS la CAO.

Le LLM ne produit jamais de géométrie. Il émet des patchs sur un ConceptGraph : composants paramétriques à identifiant stable (cadre, coque, support, cylindre, nervure, découpe, clip, charnière, visserie, bossage, fixation rail…), plus l'objet réel en fantôme.

Un constructeur déterministe dans le navigateur (manifold-3d) génère la maquette en quelques millisecondes.

Chaque réponse modifie uniquement les composants concernés. Tout changement géométrique doit être visible ; passer de vis à clips doit se voir. Une confirmation documentaire peut modifier uniquement DesignSpec, avec un patch géométrique vide et un résumé explicite.

==================================================
7. MONTRER CE QUI A CHANGÉ
==================================================

Après chaque réponse :

- phrase décrivant le changement géométrique ou documentaire ;
- surlignage : ajouté (vert), modifié (orange), adapté par dépendance, supprimé (fantôme rouge) ;
- bouton « Voir les changements » qui recadre la caméra sur les zones modifiées ;
- modes Après / Avant / Superposition / Côte à côte, avec la même caméra ;
- comparaison avec n'importe quelle version.

==================================================
8. INTERACTION DIRECTE AVEC LA MAQUETTE
==================================================

Sélection d'un composant et d'une zone nommée (paroi, lèvre avant, coin…). La sélection est transmise comme contexte à l'agent : « trop épais ici », « arrondis cette zone »…

==================================================
9. INGÉNIERIE : PIÈCE FONCTIONNELLE SANS ABERRATION TECHNIQUE
==================================================

A. Impression FDM, anisotropie et sens d'impression

- La cohésion entre couches est le point faible. Les contraintes de traction et de flexion doivent se développer dans le plan des couches.
- Les éléments qui fléchissent (clips, crochets, languettes, pattes) ont leur longueur dans le plan des couches.
- Orientation choisie par arbitrage : résistance, supports, stabilité sur le plateau, faces visibles, précision des faces fonctionnelles.
- Surplombs moins inclinés que le seuil du profil → supports. Préférer les chanfreins aux congés sur les arêtes inférieures.
- Trous horizontaux fonctionnels : signaler la perte de précision sur leur partie haute.
- Épaisseurs raisonnées en largeurs de ligne du profil officiel.
- Congés aux angles rentrants sollicités.
- Jeux d’assemblage : distinguer les jeux provisoires explicitement estimés et les jeux confirmés par une source adaptée ou un test d’assemblage.

B. Mise en position et maintien en position

- Distinguer la mise en position (géométrie : liaisons normalisées, degrés de liberté supprimés) du maintien en position (effort qui plaque l'objet sur ses appuis).
- Viser l'isostatisme (schéma type 3-2-1). Un montage hyperstatique doit être justifié ou évité.
- Surfaces d'appui fonctionnelles et fiables sur l'objet réel, jamais sur un écran, des boutons ou des connecteurs.
- L'effort de maintien plaque l'objet sur ses appuis, jamais dans l'autre sens.

C. Efforts

- Identifier les cas de charge dimensionnants : poids, appui utilisateur, insertion/extraction, vissage, chute.
- Ne poser une question sur les efforts que si la réponse change la conception.

D. Revue technique automatique (règles fixes, pas le LLM)

À chaque version :

- épaisseurs comparées aux largeurs de ligne du profil Bambu officiel installé (lu dans le bundle Bambu Studio : « 0.20mm Standard @BBL H2D ») ;
- estimation de déformation des clips ε = 1,5·t·y/L² sous les hypothèses du modèle de poutre indiqué ; distinguer déplacement d’insertion et hauteur de crochet, et comparer à un admissible seulement si sa source, son unité et son domaine d’application sont compatibles ;
- lame de clip imprimée perpendiculairement aux couches → bloquant ;
- indicateur déclaratif obtenu par somme des contraintes des liaisons et présence d’un maintien ; cette somme ne démontre ni l’indépendance des contraintes ni l’immobilisation ;
- ajustements construits sur des cotes non confirmées ;
- orientation manquante, charges manquantes pour une pièce fonctionnelle.

La revue de l’état courant est renvoyée à l’agent. Il traite les points BLOQUANT / ATTENTION. Exigence à implémenter : recalculer la revue sur la proposition après patch, puis vérifier les conditions de transition côté backend, indépendamment de la réponse du modèle.

Une acceptation explicite d’un blocage peut permettre de poursuivre l’exploration ; elle doit être associée à la règle, à la version et à ses limites. Elle ne vaut ni validation mécanique ni autorisation d’imprimer. Les limites de sécurité de la machine ne sont pas dérogeables.

Écarts actuels à traiter : charges absentes contrôlées seulement pour certaines intentions, contrôle de positionnement par somme sans analyse spatiale, emploi de la hauteur du crochet comme déplacement dans le calcul de clip. Les déclarations demandées au LLM ne remplacent pas un contrôle logiciel de leur présence et de leur cohérence.

La revue doit afficher sa couverture : contrôles exécutés, non applicables, non exécutables faute de données et contrôles non disponibles. « Aucun point relevé » ne signifie jamais « pièce validée ».

Vue « Impression » dans le viewer : surplombs sous le seuil du profil en rouge, faces sur le plateau en bleu, selon l'orientation déclarée.

Au niveau concept, c’est une détection partielle d’aberrations et, pour certains clips, une estimation conditionnelle de déformation. Ce n’est pas une validation de résistance. Documenter les conditions d’usage pertinentes : température, durée de charge, cycles, milieu et conséquence d’une rupture.

==================================================
10. CHECKPOINT « EST-ON PROCHE DU BUT ? »
==================================================

Quand les décisions principales sont prises, les inconnues fortes pour la préparation du plan sont traitées et les blocages sont résolus ou explicitement acceptés pour l’exploration :

« Est-ce que cette direction correspond maintenant à ce que tu veux fabriquer ? »

[ Oui, préparer le plan de conception ]
[ Presque, je veux modifier quelque chose ]
[ Non, continuer l'exploration ]

Le checkpoint valide la direction du concept. Il affiche les dimensions encore à mesurer et les contrôles ou essais restant à faire. La maturité technique du dossier est affichée séparément ; elle ne se déduit pas du seul accord utilisateur.

==================================================
11. PLAN DE CONCEPTION MÉCANIQUE
==================================================

Après validation du concept, le plan synthétise :

- fonction et géométrie générale ;
- dimensions connues et dimensions à déterminer ;
- interfaces avec l'objet réel ;
- matériau et contraintes ;
- assemblages et tolérances ;
- zones fonctionnelles et zones esthétiques ;
- contraintes d'impression et hypothèses ;
- orientation d'impression par pièce ;
- cas de charge ;
- mise en position et maintien ;
- points de vigilance (revue technique encore ouverte) ;
- intention d'impression.

ATTENDRE LA VALIDATION du plan. La CAO ne commence qu’après cette validation et le contrôle backend des prérequis. Une CAO exploratoire peut conserver des hypothèses explicitement identifiées ; elle ne devient pas un dossier de fabrication validé.

Distinguer les états : direction conceptuelle acceptée, plan accepté, géométrie vérifiée, assemblage testé, comportement fonctionnel testé et fabrication autorisée. Les résultats de mesure et d’essai sont associés à la version, au matériau et au profil concernés.

==================================================
12. COMPARAISON DE MODÈLES D'IA (A/B)
==================================================

- Modèle A : Claude, via l'API Anthropic directe (modèle de référence, par défaut claude-opus-5-5).
- Modèle B : n'importe quel modèle du catalogue OpenRouter, choisi et changé depuis l'interface (recherche, prix par million de tokens). Défaut : x-ai/grok-4.7.
- En mode A/B, à chaque tour les deux modèles reçoivent EXACTEMENT le même contexte et le même prompt, en parallèle.
- Affichage côte à côte, PAS à l'aveugle : Claude à gauche, le modèle B à droite, noms visibles, latence et tokens. Chaque colonne montre la maquette proposée, le changement annoncé et la question suivante.
- L'utilisateur garde une proposition : elle devient la version suivante, et l'entretien continue avec elle. Les deux propositions sont conservées pour l'évaluation. « Ignorer les deux » est possible.
- Chaque version indique le modèle qui l'a produite.
- Statistiques par modèle : préférence utilisateur (retenu / proposé), conformité JSON, réparations, questions redondantes, inconnues critiques résolues, erreurs techniques, latence et coût. Séparer préférence visuelle et qualité technique. Conserver contexte, version du prompt et configuration pour rendre les scénarios comparables.
- Le plan est rédigé par le modèle dont la proposition a été retenue en dernier.

==================================================
13. COÛTS ET CRÉDITS
==================================================

- Coût de chaque appel LLM enregistré :
  - OpenRouter : coût réellement facturé, renvoyé par l'API ;
  - Claude : coût estimé à partir des tokens et des tarifs publiés (clairement marqué « estimé »).
- Consommation par étape (Concept V0, V1…, tour comparé non retenu, plan), par phase, par modèle et par projet, avec les tokens et les réparations.
- Soldes :
  - OpenRouter : consommation de la clé et reste sur sa limite (clé standard) ; solde du compte uniquement avec une clé de gestion, facultative ;
  - Anthropic : aucune API ne donne le solde. Solde estimé seulement si l'utilisateur fournit un solde de référence et sa date.
- Ne jamais présenter une estimation comme un solde réel.

==================================================
14. CAO A/B/C (à venir, étapes 3 et 4)
==================================================

Même plan de conception validé envoyé à chaque moteur :

A. CadQuery
B. FreeCAD headless (freecadcmd)
C. build123d

[ CadQuery ] [ FreeCAD ] [ build123d ] [ Comparer ]

- Code généré exposant un dictionnaire PARAMS : les modifications simples sont appliquées sans régénération seulement si les dépendances et le domaine de validité le permettent. Toute modification reconstruit et revalide la géométrie ; une modification structurelle requiert une nouvelle proposition.
- Exécution du code généré dans une isolation effective : répertoire de travail dédié, droits et accès aux fichiers restreints, secrets exclus, réseau désactivé, ressources limitées et délai maximal. Un sous-processus seul ne constitue pas cette isolation. Boucle de réparation bornée et coûts journalisés.
- Sortie STEP commune. Métriques calculées par UN outil neutre (OCP) : dimensions, volume, surface, nombre de corps, validité B-rep, complexité définie par des métriques documentées, masse seulement si une densité sourcée est disponible, temps de génération.
- Même viewer, même caméra, même éclairage, même échelle.
- Les trois moteurs reposent sur OpenCASCADE : la comparaison mesure surtout la capacité du LLM à produire une géométrie correcte avec chaque API.
- La revue technique s'applique aussi à la géométrie CAO (épaisseurs réelles, surplombs réels).

==================================================
15. RENDU VISUEL
==================================================

CAO et visualisation découplées. Modes : technique, ombré, transparent, impression ; rendu réaliste Blender éventuel plus tard. Blender n'est jamais le moteur de CAO.

==================================================
16. ITÉRATIONS CAO ET VERSIONING
==================================================

Chaque modification : interprétée → présentée → appliquée → nouvelle version → affichée → attente.

Versions immuables : retour arrière (nouvelle branche), variante nommée, duplication en nouveau projet, comparaison entre versions. Ne jamais écraser silencieusement une bonne version.

==================================================
17. FABRICATION BAMBU LAB H2D (à venir, étapes 6 et 7)
==================================================

- Bambu Studio en ligne de commande (installé : 02.05.00.66, binaire universel) et profils officiels H2D, aplatis depuis leur chaîne d'héritage.
- Point à vérifier avant l'étape 6 : l'association filament / buse du double extrudeur n'apparaît pas dans le --help de la 02.05 (option --filament-map signalée ailleurs pour la 02.06, avec un bogue connu).
- Distinguer PARAMÈTRES OFFICIELS DU PROFIL et MODIFICATIONS PROPOSÉES PAR L'ASSISTANT (diff clé par clé). Ne jamais modifier les limites de sécurité de la machine.
- Intentions d'impression (prototype rapide, test dimensionnel, test d'assemblage, pièce finale, priorité finition / résistance / temps), héritées de l'entretien. L'orientation d'impression est reprise du cahier des charges.
- Analyse après slicing avec les seules données réellement disponibles : temps, matière, masse, couches, supports.
- Optimisation (« plus rapide », « plus solide », « moins de supports »…) : proposition expliquée, puis [ Appliquer et re-slicer ] [ Modifier ] [ Annuler ].
- Impression : écran PRÊT À IMPRIMER séparé du slicing. Par défaut, ouverture du fichier dans Bambu Studio. Envoi direct en réseau local (MQTT/FTPS, mode LAN + Developer) seulement en option, sur action explicite. Jamais d'envoi automatique.

==================================================
18. ARCHITECTURE IA
==================================================

- Couche d'abstraction des fournisseurs : Anthropic, compatible OpenAI (OpenRouter, Ollama, LM Studio), démo.
- Le LLM raisonne, les moteurs géométriques calculent, les règles fixes vérifient, le viewer affiche, le slicer tranche.
- Ne jamais demander au LLM de remplacer un calcul déterministe quand un outil approprié existe.
- Chaque appel est journalisé : entrée, sortie, latence, tokens, coût, étape.
- Mesure faite : gemma4:12b en local (Ollama) est trop lent (1 à 3,5 minutes par appel) et ne respecte pas le contrat JSON. Claude reste le défaut.

==================================================
19. RÈGLES DE TRAVAIL
==================================================

- Toute valeur technique utilisée est sourcée, déduite avec justification ou explicitement provisoire. Une valeur illustrative de maquette ne devient jamais une donnée confirmée. Les propriétés matériau et limites de sécurité ne sont pas inventées.
- Réponses en français, courtes, précises, analytiques.
- Je suis novice en administration de Claude Code : explique chaque décision de configuration.
- Avant d'installer quoi que ce soit ou d'ouvrir une nouvelle étape : présente le plan et attends ma validation.
- Teste ce que tu construis (instance isolée en mode démo pour ne pas consommer de crédits) avant de me le présenter.

==================================================
20. ÉVALUATION 1e ET CRITÈRES DE PASSAGE À LA CAO
==================================================

Définir 3 à 5 scénarios avec exigences attendues et données de référence : par exemple support simple, boîtier avec accès aux connecteurs, assemblage vissé et clip avec dimension critique manquante. Les cas sont figés avant comparaison ; ne pas changer les attentes selon le modèle.

Vérifier sur chaque scénario :
- distinction entre valeurs illustratives, estimées et confirmées ;
- une seule question utile par tour, aucune répétition d’une donnée connue ;
- identifiants stables et modifications géométriques fidèles à la réponse ;
- absence de modification artificielle pour une confirmation documentaire ;
- déclarations d’orientation, de mise en position et de charges pertinentes ;
- nouvelle revue après patch et refus backend d’un checkpoint avec blocage non accepté ;
- inconnues et limites visibles lors de la validation ;
- conservation des propositions, choix, versions, coûts et réparations.

Le mode démo vérifie le workflow sans crédits ; il ne mesure pas la qualité réelle d’un modèle. Toute campagne avec fournisseurs réels doit annoncer son budget et son périmètre avant exécution. Documenter les résultats et les défauts restants avant de proposer l’étape CAO.

Les modèles par défaut, tarifs, versions installées et options de Bambu Studio mentionnés dans ce document sont des références du cadrage précédent, pas des disponibilités vérifiées. Les relire depuis la configuration, les API ou l’installation et les vérifier avant leur utilisation ; ne pas les traiter comme des invariants.
