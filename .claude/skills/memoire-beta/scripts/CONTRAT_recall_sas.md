# Contrat — `recall(format=sas)` (SAS mémoire)

> Format **opt-in**. Sans `format=sas`, `recall()` est **inchangé, octet pour
> octet** : ce contrat ne décrit QUE la forme ajoutée par le sas.

## Principe

Le sas **étiquette, il ne cache ni ne décote**. Il dit au consommateur *ce qu'il
regarde* ; il ne décide pas à sa place. Le classement reste **global et
inchangé** (un seul `rank_candidates`, IDF global) ; le sas ne fait que
**regrouper à la présentation** ce classement en blocs étiquetés, chacun dans
l'ordre du classement global.

Les trois **étages de stockage** :

| étage        | sens                                             |
|--------------|--------------------------------------------------|
| `structure`  | mémoire **validée** (la bibliothèque de confiance) |
| `en_attente` | candidat **analysé mais NON validé**             |
| `brut`       | capture **non triée**                            |

Et un **4e bloc, l'organe d'oubli** :

| bloc         | sens                                             |
|--------------|--------------------------------------------------|
| `superseded` | fiche **jugée fausse par l'humain** (supersédée) |

Une fiche `superseded='oui'` est **routée dans le bloc `superseded`** quel que
soit son étage de stockage : elle **cesse de remonter en tête du recall** (elle
sort de `structure`/`en_attente`/`brut`, ne peut jamais être `struct_top` ni
figurer dans l'`alerte`) **sans être détruite** — elle reste sur disque,
retrouvable, et le geste est réversible (`desuperseder`). C'est un **oubli**, pas
une suppression. Le routage se fait **sur `superseded` AVANT l'étage**.

---

## SCHÉMA (machine-vérifiable)

Une réponse `format=sas` est un objet JSON respectant :

```
racine :
  "ok"      : bool  == true
  "scope"   : str
  "format"  : str   == "sas"
  "count"   : int   == nombre total de candidats dans les QUATRE blocs (>= 0)
  "blocs"   : objet  { "structure": [cand...], "en_attente": [cand...],
                       "brut": [cand...], "superseded": [cand...] }
              -> EXACTEMENT ces quatre clés, DANS CET ORDRE (le 4e bloc
                 `superseded` s'ajoute EN DERNIER, sans réordonner les autres),
                 chacune une liste (éventuellement vide)
  "alerte"  : null  OU  liste d'entrées d'alerte (voir plus bas), jamais vide si présente

cand (chaque élément d'un bloc) :
  "etage"         : str   étage de STOCKAGE de la fiche (structure|en_attente|brut)
                          Dans les blocs `structure`/`en_attente`/`brut` :
                          etage == clé du bloc (INVARIANT DE SÉPARATION).
                          Dans le bloc `superseded` : etage garde l'étage de
                          stockage (le routage se fait sur `superseded`, pas sur `etage`).
  "domain"        : str | null
  "category"      : str | null
  "file"          : str
  "path"          : str
  "excerpt"       : str
  "source"        : str   (provenance : "interne" si produit par le système,
                           sinon le nom d'une source EXTERNE — ÉTIQUETTE, jamais décote)
  "verifie"       : str   ∈ { "oui", "non" }   (jugement de Kily par fiche ;
                           défaut "non" = « source fiable, fait non confirmé »)
  "superseded"    : str   ∈ { "oui", "non" }   (organe d'oubli ; défaut "non".
                           "oui" => la fiche est dans le bloc `superseded`)
  "superseded_par": str   (id/chemin de la fiche successeur, ou texte libre ; "" si absent)
  "date_validite" : str   (date jusqu'à laquelle la fiche valait ; "" si absent)
  "_relevance"    : number   (score de pertinence IDF, NON strippé)
  "_force"        : number   (multiplicateur force, NON strippé)
  "_score"        : number   (_relevance × _force — le score de tri global, NON strippé)

  (ordre des clés FIGÉ : etage, domain, category, file, path, excerpt, source,
   verifie, superseded, superseded_par, date_validite, _relevance, _force, _score)

entrée d'alerte :
  "etage" : str  ∈ { "en_attente", "brut" }   (JAMAIS "structure", JAMAIS "superseded")
  "path"  : str
  "ecart" : number | null
```

### Règles de valeurs

- **Séparation stricte** : dans les blocs `structure`/`en_attente`/`brut`, tout
  candidat vérifie `cand["etage"] == clé_du_bloc`. Un `en_attente` n'apparaît
  jamais dans le bloc `structure`, etc. Le bloc `superseded` fait exception : il
  route sur `superseded=='oui'` (pas sur l'étage), donc ses candidats gardent
  leur étage de stockage.
- **Étiquetage de provenance** : tout candidat porte `source` et `verifie`
  (couverture 100 %). Le sas **étiquette, il ne décote pas** : `source` et
  `verifie` n'entrent PAS dans le classement (le tri reste `pertinence × force`
  inchangé), ils informent seulement le consommateur de *ce qu'il regarde*. La
  provenance **voyage** avec la fiche depuis le brut ; elle n'est jamais blanchie
  à la promotion. Le **défaut** de `recall()` (sans `format=sas`) reste **inchangé
  octet pour octet** : ces deux champs n'apparaissent QUE dans le format sas.
- **Étiquetage de supersession (organe d'oubli)** : tout candidat porte aussi
  `superseded`, `superseded_par`, `date_validite` (couverture 100 %). Ces trois
  champs **voyagent** brut → en_attente → structure exactement comme
  `source`/`verifie` (jamais perdus à la promotion). Ils sont posés **UNIQUEMENT
  par geste humain** (`superseder`), **jamais** comme effet de bord d'une
  écriture automatique. Une fiche `superseded='oui'` est **routée hors des blocs
  d'étage** dans le bloc `superseded` : elle **cesse de remonter en tête** sans
  être détruite (le fichier reste sur disque, geste réversible via
  `desuperseder`). Comme la provenance, le marqueur de supersession n'est écrit
  qu'**hors défaut** : une fiche `superseded='non'` reste **byte-identique**, et
  ces trois champs n'apparaissent QUE dans le format sas.
- **Comparabilité** : les blocs sont des **sous-suites** du classement par
  défaut ; les scores exposés sont exactement ceux du classement global (aucun
  recalcul). Concaténés dans l'ordre `structure` → `en_attente` → `brut`, ils
  reproduisent la partition stable par étage du résultat par défaut **restreinte
  aux fiches non supersédées** (les supersédées sont extraites dans leur bloc).
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
- **bloc `superseded`** → fiches *jugées fausses par l'humain*. Elles ne sont pas
  détruites (elles restent retrouvables pour l'audit/la réversibilité) mais ne
  concourent **jamais** à la tête du recall ni à l'`alerte` : **à ne pas
  consommer comme vérité** ; suivre `superseded_par` vers le successeur.

### Hors périmètre (v1)

- **Supersession PARTIELLE** (un claim périmé dans une fiche par ailleurs encore
  vraie) : c'est une **réécriture manuelle humaine**, pas du code. La v1 ne fait
  que la supersession **TOTALE** de la fiche.
- **Attrition / dépérissement automatique** (Mode A) : chantier futur séparé. Ici
  l'oubli est **toujours** un geste humain explicite, jamais un effet du temps.

### Limite NOMMÉE

Les tests (`backend/tests/test_recall_sas.py` pour le format sas,
`backend/tests/test_recall_supersession.py` pour l'organe d'oubli) garantissent
la **forme** : la séparation des blocs, la comparabilité des scores, l'exactitude
de `ecart`, que l'alerte **n'oublie aucun étage**, et — pour l'oubli — que la
supersédée sort du bloc principal, entre dans le bloc `superseded`, et **existe
toujours** (non détruite, réversible). Ils **ne garantissent PAS le routage** :
qu'un consommateur agisse effectivement sur `etage`/`superseded` (promouvoir un
`en_attente`, trier un `brut`, ne pas consommer une supersédée) est hors de
portée du test de forme et relève de chaque consommateur.
