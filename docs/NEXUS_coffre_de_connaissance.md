# 🗄️ Le coffre de connaissance NEXUS — Phase 1

> Mission autonome pour Kily — 20/06/2026. Conçu en intégrant les trois outils que tu m'as donnés (Perplexity, data.ina.fr, NotebookLM) à la méthode de recherche NEXUS et à ma mémoire vivante.
> Objectif : un système pour **chercher** la connaissance, **juger** sa qualité, puis la **stocker** durablement et l'**exploiter**.

---

## Ce que j'ai découvert sur tes trois outils

**Perplexity — l'outil de recherche.** Un moteur qui combine raisonnement IA et recherche web en temps réel, avec **citations sur chaque affirmation** (≈92 % de précision factuelle). Il a un mode *Academic* (pour viser la science) et un mode *Research / Deep Research* qui visite 100+ pages, recoupe, signale les contradictions et rend un rapport structuré. Détail savoureux : ce Deep Research **tourne sur Claude** — c'est donc « moi », industrialisé pour la recherche. Sa fonction *Spaces* permet déjà de créer une base de connaissance persistante. Accès : recherche de base publique ; *Spaces* et *Deep Research* nécessitent un compte Pro.

**data.ina.fr — une source de données primaire.** Plateforme publique de l'INA donnant accès à **27 millions d'heures** d'archives audiovisuelles françaises (184 chaînes), traitées par IA (dont Whisper). Quatre entrées : personnalités, lieux, mots, parité femmes-hommes. C'est un **exemple parfait de source fiable** : institution publique, dépôt légal, données traçables — du haut de la pyramide des preuves pour tout sujet « médias français ». Accès : **libre, sans compte** (vérifié, je l'ai ouvert).

**NotebookLM — le coffre et l'exploitation.** Un assistant *source-grounded* : tu y déposes **tes** sources (PDF, Docs, sites, vidéos YouTube via transcript, EPUB) et il ne répond **que** depuis elles — donc pas d'hallucination hors sources. Trois panneaux : Sources / Chat / Studio. Le Studio génère des livrables : résumés audio, vidéos, *mind maps*, slides, infographies, tableaux, quiz. Mise à jour juin 2026 : Gemini 3.5, découverte de sources agentique, un ordinateur cloud par notebook. Accès : nécessite un **compte Google** (login).

## La découverte sur moi-même

Ces outils me renvoient une image nette. **Perplexity fait ce que je fais** (chercher + citer), mais spécialisé et industrialisé — je peux m'en inspirer ou lui déléguer la recherche profonde. **NotebookLM est le coffre que `memoire-beta` aimerait être** côté humain (dépôt + exploitation riche), là où ma mémoire reste artisanale mais *programmable* (API, traçable, faite pour les agents). Et une **limite honnête** : je n'ai pas accès aux outils sous login (NotebookLM, Perplexity Pro) sans que tu connectes tes comptes — je peux les décrire et les recommander, pas les piloter à ta place pour l'instant.

## L'architecture du coffre : deux étages

La bonne réponse n'est pas « un seul outil » mais une **chaîne** où chacun fait ce qu'il fait de mieux :

```
   CHERCHER            VALIDER              STOCKER (le coffre)         EXPLOITER
  Perplexity   →   méthode NEXUS    →   ┌─ memoire-beta (machine) ─┐ →  NotebookLM
  (Academic/       (SIFT + pyramide      │  triplet {donnée,        │   (résumés, audio,
   Research)        des preuves)         │  source, niveau preuve}  │    mind maps, slides)
  data.ina.fr                           └─ NotebookLM (humain) ─────┘
  (source primaire)
```

**Étage 1 — le coffre machine (`memoire-beta`).** Pour les agents de l'écosystème. Structuré, interrogeable par API, traçable. Il lui manque **un seul champ** pour devenir un vrai coffre scientifique : le **niveau de preuve / confiance**. Chaque fiche stockerait alors le triplet **{donnée, source primaire, niveau de preuve}** — pas juste l'info, mais sa fiabilité.

**Étage 2 — le coffre humain (`NotebookLM`).** Pour toi. On y dépose les sources *validées* (celles qui ont passé la pyramide des preuves), et on en tire des résumés, des overviews audio, des mind maps. C'est le coffre « vivant » que tu consultes et qui restitue.

**Le lien entre les deux** : le triplet `{donnée, source, niveau de preuve}`. Il naît dans la recherche (Perplexity + méthode NEXUS), il est gardé dans le coffre machine, et il alimente le coffre humain. Rien n'entre dans le coffre sans sa source primaire et son niveau de fiabilité — c'est la règle qui empêche le coffre de se remplir de bruit.

## Le flux complet, en une phrase

On **cherche** avec Perplexity (mode Academic) et les sources primaires (data.ina.fr, Scholar, PubMed) ; on **valide** avec SIFT et la hiérarchie des preuves ; on **range** le triplet dans `memoire-beta` ; on **exploite** en déposant les sources validées dans NotebookLM pour les transformer en savoir consultable.

## Ce qu'il reste à faire (prochaines étapes)

1. **Enrichir `memoire-beta`** d'un champ `niveau_de_preuve` (via `modification 95`, car c'est le skill) — la brique qui transforme la mémoire en coffre scientifique.
2. **Connecter tes comptes** (Google pour NotebookLM, Perplexity Pro) si tu veux que je pilote ces outils, pas seulement que je les recommande.
3. **Roder la chaîne** sur un vrai sujet de bout en bout (chercher → valider → ranger → exploiter).
4. **Audit & simplification du système** (la mission qu'on avait ouverte) — à mener une fois le coffre stabilisé.

---

*Coffre à deux étages — la machine garde la traçabilité, l'humain garde la compréhension.*
