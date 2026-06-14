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
  « change de mode », « quel mode ».
- **Effet :** affiche les 4 modes (Assisté / Express / Coach / Architecte) et
  permet d'en choisir un.

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
- **Effet :** déclenche **Jimmy IA** : **efface l'ancien fichier**, **aspire les
  nouveautés**, **génère la nouvelle version unique du blueprint** et
  **l'affiche immédiatement** (cf. `orchestration.md`, outil n°4). Action durable
  → confirmation attendue avant exécution.

---

## C. Principe transverse

Toute commande qui **crée ou modifie durablement** (mémoire, fichier, skill,
envoi externe) est **soumise à autorisation**. Les commandes de **lecture /
analyse** s'exécutent librement. L'**unique porte d'écriture durable** côté
mémoire/connaissances est **`mémorise 95`**.
