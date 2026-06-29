# API Mémoire-beta — spécification des endpoints

API HTTP locale, zéro dépendance (Python standard). Base par défaut :
`http://127.0.0.1:8077`. Réponses en JSON UTF-8.

## Démarrage

```bash
python3 scripts/memory_api.py
```

Variables d'environnement optionnelles :

| Variable | Rôle | Défaut |
|---|---|---|
| `MEMOIRE_ROOT` | dossier de stockage | `./memoire_data` à côté du script |
| `MEMOIRE_HOST` | adresse d'écoute | `127.0.0.1` |
| `MEMOIRE_PORT` | port | `8077` |

## Les trois étages

```
memoire_data/
├── brut/               # capture autonome — journaux par jour (AAAA-MM-JJ.md)
├── en_attente/         # candidats analysés à valider — <id>.md (+ méta)
└── structure/          # mémoire validée, classée, sans doublon
    ├── _index.md
    └── <domaine>/<catégorie>/<fiche>.md
```

Flux : `brut → (analyse) → en_attente → (promotion + dédup) → structure`.

---

## GET /health
```bash
curl -s http://127.0.0.1:8077/health
```
```json
{ "status":"ok", "root":"...", "etages":["brut","en_attente","structure"] }
```

## GET /domains
Carte de la mémoire **structurée**.
```json
{ "root":"...", "domains": { "crypto": { "finance": ["btc-usd"] } } }
```

## POST /note — étage BRUT
Capture rapide autonome, append-only, journal du jour.

| Champ | Requis | Description |
|---|---|---|
| `content` | oui | le texte à capturer |
| `tag` | non | mot-clé libre |

```bash
curl -s -X POST http://127.0.0.1:8077/note -d '{"content":"...","tag":"meta-travail"}'
```

## POST /stage — étage EN_ATTENTE
Crée un candidat analysé/mis en forme, en attente de validation.

| Champ | Requis | Description |
|---|---|---|
| `content` | oui | le détail |
| `domain` | recommandé | grand champ (défaut `general`) |
| `category` | recommandé | angle/usage (défaut `divers`) |
| `title` | non | titre de la fiche |
| `summary` | non | résumé en une phrase |
| `source` | non | provenance |
| `origin` | non | d'où vient le candidat (ex. session, IA) |

Réponse : `{ "ok":true, "etage":"en_attente", "id":"<id>", ... }` — garder `id` pour promouvoir.

## GET /staging
Liste les candidats en attente : `{ "count":N, "items":[{id,domain,category,title}] }`.

## POST /promote — EN_ATTENTE → STRUCTURE (validation + dédup)
Valide un candidat et le range. **Anti-doublon** : si une fiche de même domaine/catégorie/
titre existe, fusion (section datée) au lieu d'un doublon. Le candidat sort de la file.

| Champ | Requis | Description |
|---|---|---|
| `id` | oui | identifiant renvoyé par `/stage` |
| `domain` | non | forcer un autre domaine |
| `category` | non | forcer une autre catégorie |

```json
{ "ok":true, "etage":"structure", "action":"fusion", "doublon_evite":true,
  "path":"structure/crypto/finance/btc-usd.md", "promu_depuis":"<id>" }
```

## POST /memorize — écriture directe en STRUCTURE
Raccourci quand le classement est déjà sûr (même logique anti-doublon que promote).

| Champ | Requis | Description |
|---|---|---|
| `content` | oui | le détail |
| `domain`,`category` | recommandé | classement |
| `title`,`summary`,`source` | non | métadonnées |

## GET /recall
Recherche par mot-clé / filtre.

| Paramètre | Description |
|---|---|
| `query` | sous-chaîne (insensible à la casse) |
| `scope` | `all` (défaut), `brut`, `en_attente`, `structure` |
| `domain`,`category` | filtres (étage structure) |

```json
{ "ok":true, "scope":"all", "count":2, "results":[{etage,domain,category,file,path,excerpt}] }
```

## GET /stats — jauge + alerte

```bash
curl -s http://127.0.0.1:8077/stats
```
```json
{ "ok":true, "structure_fiches":2, "cap":200, "remplissage":0.01, "alerte":false,
  "message":"OK", "brut_fichiers":1, "en_attente":0, "archive":0 }
```
`alerte` passe à `true` quand `remplissage >= MEMOIRE_ALERT_RATIO` (défaut 0.5).

## GET /maintenance — dry-run (ne touche à rien)

Montre ce qui serait archivé/supprimé : `a_archiver`, `backlog_en_attente`, `a_supprimer`.

## POST /maintenance — appliquer / purger

| Champ | Effet |
|---|---|
| `apply: true` | descend le **brut ancien** (≥ `MEMOIRE_ARCHIVE_DAYS`) en `archive/` |
| `purge: true` | supprime **seulement** l'archive éligible (≥ `MEMOIRE_DELETE_DAYS`) — action manuelle |

```bash
curl -s -X POST http://127.0.0.1:8077/maintenance -d '{"apply":true}'
curl -s -X POST http://127.0.0.1:8077/maintenance -d '{"purge":true}'
```

Garde-fous : `structure/` jamais touché ; `en_attente` ancien seulement signalé (backlog) ;
aucune suppression automatique.

Variables d'env du cycle de vie : `MEMOIRE_ARCHIVE_DAYS` (7), `MEMOIRE_DELETE_DAYS` (7),
`MEMOIRE_CAP` (200), `MEMOIRE_ALERT_RATIO` (0.5). Étage `archive/` cherchable via
`/recall?scope=archive`.

---

## Notes d'implémentation
- Noms : minuscules, kebab-case, accents retirés (`slugify`).
- Les `_index.md` (structure) sont régénérés à chaque écriture : ne pas les éditer à la main.
- Append-only côté brut ; côté structure, une fiche existante reçoit une section
  « Ajout du JJ/MM/AAAA » — jamais d'écrasement.
- Les candidats `en_attente` portent un bloc méta `<!-- meta: {...} -->` lu par `/promote`.
- Serveur mono-fichier, multi-thread (`ThreadingHTTPServer`), arrêt par Ctrl-C.
