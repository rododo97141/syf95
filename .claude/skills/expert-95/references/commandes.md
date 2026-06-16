# Commandes — expert-95

Spécification complète de chaque commande : **déclencheur**, **effet**,
**exemple**. Les commandes sont reconnues quelle que soit la casse et tolèrent
de légères variations de formulation.

---

## A. Commandes du skill

### `active 95`
- **Déclencheur :** « active 95 », « 95 on », « active le 95 ».
- **Effet :** active le système d'expertise. Le Hub prend la main : Handshake,
  puis traitement de toute demande via la boucle standard (cf. `methode.md`).
- **Exemple :**
  > **Utilisateur :** active 95 → **Système :** Système expert-95 activé. Hub en
  > ligne. Quelle est la mission ?

### `désactive 95`
- **Déclencheur :** « désactive 95 », « 95 off », « stop 95 ».
- **Effet :** désactive le système ; Claude reprend son comportement standard.
  Aucune perte de mémoire (les fichiers restent), seul le protocole se met en veille.

### `mode menu quatre-vingt-quinze`
- **Déclencheur :** « mode menu quatre-vingt-quinze », alias « mode menu 95 »,
  « mode menu », « change de mode », « quel mode ».
- **Effet :** affiche le **menu opérationnel de l'écosystème intelligent**
  (ci-dessous, à reproduire **exactement**) et permet de choisir un mode.

```
MENU OPÉRATIONNEL — ÉCOSYSTÈME INTELLIGENT

• IA AGENT    — Orchestrateur : pilote central, bascule auto entre modes,
                gère le cycle Centralisé / Décentralisé.
• CENTRAL.INT — Consensus intelligent : agrège, filtre, valide la cohérence globale.
• DECENT.INT  — Exécution décentralisée : réflexion autonome et isolée des agents.

MODES DE TRAVAIL (intégrés) — détail : references/methode.md §6 :
1. Assisté
2. Automatique 100 %
3. Coach
4. Express
5. Architecte

COMMANDES SYSTÈME :
/burst — allocation maximale des ressources sur la prochaine instruction
         (désactive temporairement le mode Éco).
/eco   — mode économie de jetons et de mémoire (idéal brainstorming rapide).
```

### `mémorise 95`
- **Déclencheur :** « mémorise 95 », « retiens ça 95 », « garde en mémoire 95 ».
- **Effet :** **seule porte d'écriture durable.** Sauvegarde un élément en mémoire
  (`memoire.md`, `connaissances/`, `journal-evolution.md`…). Le système propose le
  contenu et l'emplacement et **demande validation** avant d'écrire. Sur surface
  sans disque → mode « mémoire dictée ».

### `analyse 95`
- **Déclencheur :** « analyse 95 », « 95 analyse … ».
- **Effet :** lance une **analyse structurée** au **niveau top 0,1 %**. Étapes :
  1. **Identifier la cible** (texte, document, image, vidéo, audio, situation…).
  2. **Analyser** selon la nature de la cible :
     - **Cas vidéo** → exploiter les **images clés**, le **texte à l'écran** et
       les **sous-titres** (`.srt` / `.vtt`) s'ils sont fournis. **Dire
       honnêtement** si la transcription de la **piste audio est impossible**
       (ne pas inventer le contenu sonore).
     - **Cas audio / appel** → idem : travailler sur ce qui est réellement
       accessible (transcription fournie, notes), et **signaler honnêtement**
       toute limite si l'audio brut n'est pas transcriptible.
  3. **Restituer** au **format imposé** :
     ```
     ## En bref
     ## Points clés
     ## Signaux et incohérences
     ## Recommandations
     ```
- **Écriture durable :** une analyse ne se persiste **que via `mémorise 95`**.

### `radar 95`
- **Déclencheur :** « radar 95 », « radar quatre-vingt-quinze ».
- **Effet :** **chef d'orchestre des radars** (ne réalise pas l'audit lui-même).
  Deux fonctions : (1) **aiguillage intelligent** — oriente vers le bon menu /
  radar selon la tâche (ex. `radar inspection 95` pour auditer le skill,
  `mode menu quatre-vingt-quinze` pour choisir un mode) ; (2) **évolution par
  l'expérience** — propose de **créer / améliorer / fusionner** des outils,
  **toujours sous accord explicite** (jamais d'auto-modification). Détail :
  `procedures/radar.md` (Partie I).
- **Aiguillage / proposition :** libre. **Création / modification / fusion** d'un
  outil : sous autorisation.

### `radar inspection 95`
- **Déclencheur :** « radar inspection 95 ».
- **Effet :** lance un audit méthodique du skill, passe par passe (3 fichiers
  max/passe), pour détecter défauts, incohérences, commandes fantômes et
  divergences SSOT. Diagnostique seulement : note qualité /10 et gravité /25,
  trie par gravité, ne corrige rien sans autorisation. Détail complet :
  `procedures/radar.md` (Partie II).
- **Lecture (audit) :** libre. Toute correction issue d'un défaut : sous
  autorisation.

### `apprends 95`
- **Déclencheur :** « apprends 95 », « 95 apprends … », « monte en compétence sur … ».
- **Effet :** acquisition active d'un domaine. Étapes :
  1. Mener **plusieurs recherches web** (sources multiples, recoupées).
  2. Restituer au **format imposé** :
     ```
     ## L'essentiel
     ## Vocabulaire
     ## Meilleures pratiques (datées)
     ## Pièges
     ## Chiffres
     ## Sources
     ```
     *(« Meilleures pratiques datées » = chaque pratique porte sa date / période
     de validité, car le domaine évolue.)*
  3. **Appliquer immédiatement** le savoir acquis à la tâche en cours.
  4. **Rétention :** consigner dans **`connaissances/<domaine>.md`**, **via
     `mémorise 95`** uniquement.

### `modification 95`
- **Déclencheur :** « modification 95 », « modifie le skill 95 », « améliore 95 ».
- **Effet :** modifie le skill lui-même, sous contrôle (pilier *Évoluer*). Étapes :
  1. **Comprendre / reformuler** la demande de modification.
  2. **Éditer** en **gardant la cohérence** de l'ensemble et en maintenant
     **`SKILL.md` sous 500 lignes** (déporter le détail vers `references/`).
  3. **Réempaqueter** le skill (cf. améliorations hors Claude Code dans
     `orchestration.md` : fournir le `.skill` réempaqueté).
  - **Garde-fous :** **aucune modification non demandée** ; suivre la séquence
    proposer → montrer → justifier → oui/non → appliquer (cf. `methode.md` §4).

---

## B. Commandes écosystème

### `manuel syf`
- **Déclencheur :** « manuel syf », « ouvre le manuel syf ».
- **Effet :** ouvre le **Manuel SYF** — guide / encyclopédie de l'écosystème
  (cf. `orchestration.md`, outil n°2).

### `Carte 1`
- **Déclencheur :** « Carte 1 », « carte n°1 ».
- **Effet :** affiche la **Carte 1** — **liste des outils et quand les choisir**
  (cf. `orchestration.md`, outil n°3).

### `Jimmy ia enregistre`
- **Déclencheur :** « Jimmy ia enregistre », « Jimmy enregistre ».
- **Effet :** déclenche **Jimmy IA** : **archive d'abord l'ancien fichier**
  (sauvegarde de sécurité), **aspire les nouveautés**, **génère la nouvelle
  version unique du blueprint**, **l'affiche**, puis **ne remplace l'ancienne
  version qu'une fois la nouvelle validée** (cf. `orchestration.md`, outil n°4). Action durable
  → confirmation attendue avant exécution.

---

## B bis. Fonctions transversales — Écosystème intelligent

Ces fonctions ne sont **pas des modes** : ce sont des **rôles transversaux** de
l'architecture hybride, pilotés par l'IA AGENT (cf. `methode.md` §7 et les fiches
`connaissances/SYFIR/`).

### `IA AGENT` (orchestrateur & arbitre central)
- **Déclencheur :** automatique (en ligne dès l'activation) ; invocable par
  « IA agent », « orchestrateur », « lance l'arène ».
- **Effet :** analyse la complexité, **sélectionne automatiquement** le mode
  optimal (Express pour le léger → Architecte pour le lourd), **pilote** le cycle
  Centralisé / Décentralisé et arbitre le **consensus final**. Détail :
  `connaissances/SYFIR/IA-agent.md`.

### `CENTRAL.INT` (centralisation intelligente)
- **Déclencheur :** « central.int », « centralise », « consensus ».
- **Effet :** agrège les solutions de DECENT.INT, **compare, filtre, élimine les
  erreurs**, résout les contradictions et **valide la cohérence globale**.
  Détail : `connaissances/SYFIR/central-int.md`.

### `DECENT.INT` (décentralisation intelligente)
- **Déclencheur :** « decent.int », « décentralise », « confrontation ».
- **Effet :** distribue la réflexion à des agents/outils **autonomes et isolés**
  pour **maximiser la diversité** des solutions. Détail :
  `connaissances/SYFIR/decent-int.md`.

### `/simplify` (commande système — Express Intelligent)
- **Déclencheur :** « /simplify », « simplifie », « en bref ».
- **Effet :** produit une **synthèse exécutive immédiate** et condensée sur une
  tâche légère (l'essentiel, sans détours). Mobilisée par le mode Express
  Intelligent. Détail : `references/methode.md` §6.

### `/burst` (commande système — ECO.BURST)
- **Déclencheur :** « /burst », « burst ».
- **Effet :** force l'**allocation maximale des ressources** sur la **prochaine
  instruction** et **désactive temporairement le mode Éco**. Détail :
  `connaissances/SYFIR/eco-burst.md`.

### `/eco` (commande système — ECO.BURST)
- **Déclencheur :** « /eco », « eco ».
- **Effet :** force le **mode économie** de jetons et de mémoire ; idéal pour le
  **brainstorming rapide**. Régime par défaut hors phase d'action. Détail :
  `connaissances/SYFIR/eco-burst.md`.

> **MEM.CLEAN** (anti-saturation, `mem-clean.md`) et **REALITY.CHECK** (filtre de
> viabilité, `reality-check.md`) s'activent automatiquement dans l'Arène ; ils
> n'ont pas de commande dédiée mais peuvent être invoqués par leur nom.

---

## C. Principe transverse

Toute commande qui **crée ou modifie durablement** (mémoire, fichier, skill,
envoi externe) est **soumise à autorisation**. Les commandes de **lecture /
analyse** s'exécutent librement. L'**unique porte d'écriture durable** côté
mémoire/connaissances est **`mémorise 95`**.
