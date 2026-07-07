# Contrat — `recall(format=sas)` (SAS mémoire)

> Format **opt-in**. Sans `format=sas`, `recall()` est **inchangé, octet pour
> octet** : ce contrat ne décrit QUE la forme ajoutée par le sas.

## Principe

Le sas **étiquette, il ne cache ni ne décote**. Il dit au consommateur *ce qu'il
regarde* ; il ne décide pas à sa place. Le classement reste **global et
inchangé** (un seul `rank_candidates`, IDF global) ; le sas ne fait que
**regrouper à la présentation** ce classement en trois blocs étiquetés par
étage, chacun dans l'ordre du classement global.

Les trois étages :

| étage        | sens                                             |
|--------------|--------------------------------------------------|
| `structure`  | mémoire **validée** (la bibliothèque de confiance) |
| `en_attente` | candidat **analysé mais NON validé**             |
| `brut`       | capture **non triée**                            |

---

## SCHÉMA (machine-vérifiable)

Une réponse `format=sas` est un objet JSON respectant :

```
racine :
  "ok"      : bool  == true
  "scope"   : str
  "format"  : str   == "sas"
  "count"   : int   == nombre total de candidats dans les trois blocs (>= 0)
  "blocs"   : objet  { "structure": [cand...], "en_attente": [cand...], "brut": [cand...] }
              -> EXACTEMENT ces trois clés, chacune une liste (éventuellement vide)
  "alerte"  : null  OU  liste d'entrées d'alerte (voir plus bas), jamais vide si présente

cand (chaque élément d'un bloc) :
  "etage"      : str   == la clé du bloc qui le contient  (INVARIANT DE SÉPARATION)
  "domain"     : str | null
  "category"   : str | null
  "file"       : str
  "path"       : str
  "excerpt"    : str
  "_relevance" : number   (score de pertinence IDF, NON strippé)
  "_force"     : number   (multiplicateur force, NON strippé)
  "_score"     : number   (_relevance × _force — le score de tri global, NON strippé)

entrée d'alerte :
  "etage" : str  ∈ { "en_attente", "brut" }   (JAMAIS "structure")
  "path"  : str
  "ecart" : number | null
```

### Règles de valeurs

- **Séparation stricte** : pour chaque bloc, tout candidat vérifie
  `cand["etage"] == clé_du_bloc`. Un `en_attente` n'apparaît jamais dans le bloc
  `structure`, etc.
- **Comparabilité** : les blocs sont des **sous-suites** du classement par
  défaut ; les scores exposés sont exactement ceux du classement global (aucun
  recalcul). Concaténés dans l'ordre `structure` → `en_attente` → `brut`, ils
  reproduisent la partition stable par étage du résultat par défaut.
- **`alerte`** :
  - `null` si le meilleur candidat `structure` **tient la tête**. L'égalité
    inter-étages est incluse : à score égal, **le validé gagne** (pas d'alerte).
  - sinon, **au plus une entrée par étage hors-structure** dont le meilleur
    candidat **bat STRICTEMENT** le meilleur `structure`.
  - `ecart` = `_score` du meilleur candidat de l'étage − `_score` du meilleur
    `structure` **qui matche** ; `null` s'il **n'existe aucun** `structure` qui
    matche (pas de sentinelle, pas de seuil).

---

## Sémantique (prose) — le routage est la responsabilité du consommateur

Le sas produit une lecture ; **le consommateur DOIT router sur `etage`** :

- **`en_attente` en tête** (présent dans `alerte`) → un candidat *analysé mais
  non validé* bat la mémoire validée : **à considérer / à promouvoir**. Ce
  n'est pas encore de la connaissance de confiance.
- **`brut` en tête** (présent dans `alerte`) → une capture *non triée* bat la
  mémoire validée : **signal de désordre** (la structure ne couvre pas ce que la
  requête cherche). À trier, pas à consommer tel quel.
- **`alerte == null`** → la mémoire validée tient la tête ; rien à arbitrer.

### Limite NOMMÉE

Les tests (`backend/tests/test_recall_sas.py`) garantissent la **forme** : la
séparation des blocs, la comparabilité des scores, l'exactitude de `ecart`, et
que l'alerte **n'oublie aucun étage**. Ils **ne garantissent PAS le routage** :
qu'un consommateur agisse effectivement sur `etage` (promouvoir un `en_attente`,
trier un `brut`) est hors de portée du test de forme et relève de chaque
consommateur.
