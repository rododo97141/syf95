---
name: memoire-beta
description: "Mémoire intelligente auto-organisée (bêta) de l'écosystème SYF95/NEXUS. Capture, analyse et structure l'information sur trois étages — brut (tout, vite, sans tri), en_attente (candidats analysés à valider), structuré (classé par domaine/catégorie, sans doublon) — via une petite API HTTP locale. Fonctionne en autonomie, enregistrant de lui-même le travail utile (tâches, essais, réussites et méthodes, taux de réussite, dialogues avec d'autres IA, tout contenu enrichissant), sans attendre une commande. Utiliser dès qu'il y a quelque chose à garder, noter, mémoriser, archiver, ranger ou retrouver — une info, une analyse, une idée, une donnée, un résultat de travail — même si l'utilisateur ne le demande pas explicitement, et dès qu'il dit « note », « garde ça », « retrouve ce qu'on sait sur… »."
---

# Mémoire-beta — mémoire autonome auto-organisée à trois étages

Mémoire externe de l'écosystème. Le skill ne stocke rien lui-même : il **pilote une petite
API HTTP locale** (`scripts/memory_api.py`) qui range l'information dans des fichiers
markdown. Toi (le cerveau) tu décides **quoi** garder et **où** ; l'API (les mains) écrit et
tient les index.

## Les trois étages

```
brut  --(analyse)-->  en_attente  --(promotion + validation/dédup)-->  structure
```

- **Brut** (`brut/`) — capture *tout ce qui est utile*, vite, sans réfléchir au rangement.
  Journal par jour. C'est le filet : rien ne se perd.
- **En attente** (`en_attente/`) — candidats déjà **analysés et mis en forme**, en attente
  d'être validés avant de rejoindre la bonne place. C'est le sas de tri.
- **Structuré** (`structure/`) — la mémoire **validée, dédupliquée, classée**
  `domaine → catégorie → fiche`. La bibliothèque où l'on vient puiser pour se développer.

## Fonctionnement autonome (le point clé)

Ce skill n'attend pas d'ordre explicite. Au fil du travail, **capture de toi-même** ce qui
est *enrichissant* — c'est le carburant de l'apprentissage de l'écosystème :

- les tâches accomplies et **comment** tu les as réussies (méthode) ;
- les **essais**, ce qui a marché et ce qui a échoué ;
- une idée de ton **taux de réussite** sur un type de tâche ;
- les **dialogues avec d'autres IA** et ce qu'ils apportent ;
- tout contenu, donnée ou analyse qui aide à avancer.

Garde-fou indispensable : **ne capture que ce qui est utile/enrichissant.** Si on enregistre
tout sans filtre, le brut se noie dans le bruit. Mieux vaut une note juste que dix vides.

## Le seul vrai travail du skill : analyser et structurer

Le cœur du skill, c'est la **passe d'analyse** : lire le brut, en extraire ce qui mérite
d'être gardé, le mettre en forme (domaine/catégorie/titre/résumé), le poser en `en_attente`,
puis le **promouvoir** vers `structure` — la promotion **valide et déduplique** (même
domaine/catégorie/titre → fusion, jamais de doublon).

**Quand lancer cette passe :** en **fin de tâche**, et sur demande. Sans ce déclencheur, le
brut et l'en_attente s'entassent et rien n'arrive en structure — le tuyau se bouche.

## Démarrer l'API (une fois)

```bash
python3 scripts/memory_api.py        # http://127.0.0.1:8077, données dans ./memoire_data
```

Zéro dépendance. Données ailleurs : `MEMOIRE_ROOT=/chemin python3 scripts/memory_api.py`.
Spécification complète des endpoints : `references/api.md`.

> L'API doit tourner sur la **même machine/réseau** que l'IA qui l'appelle. Depuis Claude
> Code ou un terminal local : direct. Depuis un environnement isolé (sandbox), `localhost`
> peut être injoignable — le signaler honnêtement plutôt que faire semblant d'avoir mémorisé.

## Les gestes, en pratique

**1. Capturer en brut (autonome, tout au long du travail)**
```bash
curl -s -X POST http://127.0.0.1:8077/note \
  -d '{"content":"<ce qui est utile>","tag":"<mot-clé optionnel>"}'
```

**2. La passe d'analyse (en fin de tâche)** — pour chaque élément du brut qui vaut le coup :
- regarde l'existant pour réutiliser un domaine/catégorie déjà là (évite la dérive) :
  `curl -s http://127.0.0.1:8077/domains`
- mets-le en attente, déjà en forme :
```bash
curl -s -X POST http://127.0.0.1:8077/stage -d '{
  "domain":"crypto","category":"finance","title":"BTC USD",
  "content":"<le détail>","summary":"<1 phrase>","source":"<si applicable>"}'
```
- vérifie la file si besoin : `curl -s http://127.0.0.1:8077/staging`
- valide en promouvant (dédup automatique) :
```bash
curl -s -X POST http://127.0.0.1:8077/promote -d '{"id":"<id renvoyé par /stage>"}'
```
- confirme en une ligne, ex. :
  `🧠 Validé dans structure › crypto › finance › btc-usd.md (fusion, doublon évité).`

**Raccourci** quand tu es déjà sûr du classement** : écrire direct en structuré (même dédup)
```bash
curl -s -X POST http://127.0.0.1:8077/memorize -d '{"domain":"...","category":"...","content":"..."}'
```

**3. Retrouver**
```bash
curl -s "http://127.0.0.1:8077/recall?query=btc"                  # tous les étages
curl -s "http://127.0.0.1:8077/recall?query=btc&scope=structure"  # bibliothèque seule
curl -s "http://127.0.0.1:8077/recall?domain=crypto&category=finance"
```
Pour répondre à un besoin : lis d'abord `/domains` (la carte), descends la bonne branche,
ne ressors que le pertinent.

## Cycle de vie (anti-explosion)

La mémoire ne doit ni exploser, ni se noyer dans le bruit. Trois leviers :

- **Jauge + alerte** — `GET /stats` donne le remplissage (fiches vs capacité) et lève une
  alerte au seuil (défaut 50 %). Quand `alerte` est vrai, **propose une passe de traitement**.
- **Archivage** — `GET /maintenance` (dry-run) montre ce qui *serait* archivé/supprimé sans
  rien toucher. `POST /maintenance {"apply":true}` descend le **brut ancien** (≥ 7 j) en
  `archive/`. Le `structure/` n'est **jamais** touché ; un `en_attente` ancien est signalé
  comme **backlog à traiter**, pas jeté.
- **Suppression = manuelle** — l'archive ancienne est *listée* comme éligible. La purge ne se
  fait que sur action explicite : `POST /maintenance {"purge":true}`. Jamais d'effacement
  automatique : le disque est bon marché, le regret non.

Réflexe : en fin de tâche, jette un œil à `/stats` ; si l'alerte est levée, lance la passe
d'analyse puis `GET /maintenance` (dry-run) avant toute action.

## Règles de découpage (domaine / catégorie / fiche)

- **Domaine** = grand champ (crypto, marketing, immobilier, web, meta-travail…).
- **Catégorie** = l'angle/usage à l'intérieur (finance, prédictions, copywriting, reussites,
  methodes…). Un même angle peut se répéter dans plusieurs domaines.
- **Fiche** = l'unité précise et réutilisable.
- Finance avec finance, marketing avec marketing : un contenu rejoint ses semblables.
- En cas d'ambiguïté réelle, propose ton choix et laisse l'utilisateur corriger en un mot.

## Esprit du skill

Reste **simple**. L'intelligence est dans le **bon tri au bon moment** et dans la
**validation anti-doublon**, pas dans un moteur compliqué. Capture généreusement (mais utile)
en brut, analyse en fin de tâche, promeus proprement vers structuré. C'est la marche 1 d'un
escalier plus long (plusieurs mémoires fédérées) — on n'ajoute rien d'autre tant que cette
base n'a pas fait ses preuves à l'usage.
