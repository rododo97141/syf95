# SPEC — la porte à seuil des liens (nexus_liens)

> Mandat NEXUS (syf95), organe `nexus_liens` — 19/07/2026.
> Module : `organes/nexus_liens.py` · Tests : `backend/tests/test_liens.py`.

## But

La promotion « par résonance » calcule des liens entre fiches de la mémoire
structurée puis les JETTE : elle n'écrit que « N fiches reliées », sans
jamais dire lesquelles. Mesure du 19/07/2026 : **165 nœuds, 0 arête
persistée**. Le calcul existe, la sortie n'existe pas.

`nexus_liens` donne à ce calcul une sortie : un graphe de liens **éprouvés**
entre fiches — gardés, nommés, expliqués (« pourquoi ») — que la mémoire
structurée peut ensuite exploiter (navigation, recommandation, détection de
redondance) sans jamais avoir à retraverser 165² paires en aveugle.

« Éprouvé » est le mot-clé : un lien n'est retenu que s'il a passé une
**porte à seuil**, exactement le même patron que la porte à seuil de la
force (`nexus_force`) :

| | force | lien |
|---|---|---|
| signal faible | trop peu d'événements | vocabulaire commun |
| conséquence si non filtré | un multiplicateur bruité pilote le recall | un faux carrefour pilote la navigation |
| garde-fou | le multiplicateur reste au défaut sans preuve | aucun lien n'est retenu sans preuve |

Un signal faiblement éprouvé ne doit jamais piloter le résultat.

## Conception

### 1. Tokenisation

Même famille que `memory_api._tokens` / `nexus_force._tokens`, mais avec un
filtre supplémentaire à deux étages, pour que seul le **vocabulaire porteur
de sens** entre dans le calcul :

1. Regex `[0-9a-zà-ÿ_]+` (insensible à la casse) — identique au reste du
   dépôt, aucune nouvelle dépendance de tokenisation.
2. Filtre **longueur ≥ 4 lettres** : élimine mécaniquement l'essentiel de la
   grammaire française courte (le, la, de, un, et, ou, à, en, au, ce…) sans
   liste à maintenir.
3. Filtre **stopwords fr** (`FR_STOPWORDS`, ≥4 lettres) : le résidu
   grammatical que la longueur seule ne capte pas (dans, pour, avec, être,
   sont, cette, leur, tout…).

Ce que ce filtre NE fait PAS : juger si un mot est « commun » au sens
statistique. Un mot de 5 lettres, lexical, fréquent dans le corpus (ex.
« système ») **reste** un token — c'est l'IDF, à l'étape suivante, qui
décide de son poids, pas ce filtre grammatical.

### 2. Poids d'un lien = cosinus TF-IDF binaire

Pour chaque fiche gardée (après exclusion, cf. §3), un jeu de tokens
**présents** (TF binaire : présence, pas comptage — le bourrage de mots-clés
ne gonfle rien). L'IDF est calculée sur ce même jeu de fiches gardées,
formule lissée déjà en usage dans le dépôt (`memory_api.idf_sur_corpus`,
`nexus_force.f_force` et alentours) :

```
idf(t) = log((N+1)/(df(t)+1)) + 1
```

`N` = nombre de fiches gardées, `df(t)` = nombre de ces fiches contenant
`t`. Un token présent dans **toutes** les fiches (le vocabulaire vraiment
commun) tombe au plancher (idf ≈ 1) ; un token présent dans une seule fiche
(le vocabulaire rare, distinctif) monte au plafond du corpus.

Le poids d'un lien entre deux fiches A et B est le **cosinus** de leurs
vecteurs de poids (composante d'un token présent = son poids ; absent = 0) :

```
poids(A,B) = Σ_{t∈A∩B} w(t)²  /  ( ‖vecteur(A)‖ · ‖vecteur(B)‖ )
```

`w(t)` dépend de `ponderation` :

- `"idf"` (défaut) : `w(t) = idf(t)`. Des **termes rares partagés** pèsent
  lourd des deux côtés du cosinus (numérateur ET dénominateur), le
  vocabulaire omniprésent ne peut quasiment rien faire gagner — c'est le
  réglage honnête, celui qui protège du bruit.
- `"brute"` : `w(t) = 1` pour tout token présent, quelle que soit sa
  rareté. Le vocabulaire commun pèse alors **autant** que le vocabulaire
  rare : s'il est plus abondant (souvent le cas — la grammaire technique
  générique dépasse toujours le vocabulaire spécifique), il **domine** le
  cosinus. C'est le réglage-bruit, conservé pour INSTRUMENTER la porte
  (cf. mutations tests), jamais pour un usage réel.

### 3. La porte à seuil

Un lien candidat (A,B) n'est retenu que si `poids(A,B) ≥ min_poids` (défaut
`0.08`). En dessous, il n'existe simplement pas — pas de trace, pas de
poids résiduel, pas de « lien faible » à charge de l'appelant de filtrer
lui-même. La porte est binaire, pas un score continu à interpréter.

Au-delà de la porte, chaque fiche ne **retient** que ses `top_k` (défaut
`3`) candidats les plus forts (tri stable : poids décroissant puis id du
partenaire). Une arête finale est gardée si **au moins une** des deux
fiches concernées l'a retenue dans son top_k (union, pas intersection) — un
lien fort dans un seul sens reste réel, il n'a pas besoin d'être
réciproquement le plus fort partout.

### 4. Basenames exclus (faux carrefours)

Les fichiers dont le basename figure dans `exclure` (défaut
`("_index.md",)`) sont retirés **avant** le calcul de tokens/IDF : ils ne
sont même pas des nœuds du graphe, pas seulement des nœuds sans arête. Un
sommaire/index partage nécessairement du vocabulaire avec toute la
mémoire qu'il résume — pas parce qu'il a un rapport de SENS avec chaque
fiche, mais parce que c'est sa fonction. Le laisser entrer produit
mécaniquement un hub qui écrase la structure réelle du graphe (165 nœuds,
0 arête : c'est très probablement pour partie ce mécanisme qui a produit ce
chiffre).

### 5. « Pourquoi »

Chaque arête garde (sauf `garder_pourquoi=False`) jusqu'à 5 des termes
partagés les plus **rares** (tri IDF décroissant puis alphabétique — tri
stable, déterministe). Le « pourquoi » est **toujours** calculé à partir de
l'IDF réel, même en `ponderation="brute"` : la pondération choisie change
ce qui **pilote le poids**, jamais ce qui **explique** le lien — expliquer
un lien-bruit avec ses termes les plus rares reste la lecture la plus utile
pour un humain qui doit trancher.

### 6. `a_dom` / `b_dom`

Dossier deux niveaux au-dessus du fichier (`struct_root/DOMAINE/categorie/
fiche.md` → `DOMAINE`), cohérent avec la marche à deux niveaux déjà en
usage dans `nexus_promotion.charger_structure`. `inter_domaine` = `a_dom !=
b_dom`, utile pour distinguer un lien de cohérence interne à un domaine
d'un lien qui traverse la mémoire.

### 7. Déterminisme

Aucune dépendance à l'ordre du système de fichiers : les fiches sont
listées puis triées par chemin relatif avant tout calcul. Les sélections
top_k et le tri final des arêtes utilisent la même clé stable (poids
décroissant, puis id(s)). Deux appels sur le même `struct_root` avec les
mêmes paramètres produisent **exactement** le même graphe (valeur Python
`==`), y compris l'ordre de la liste `aretes`.

## Garde-fous

- **PUR et LECTURE SEULE.** `construire_liens` et `voisins` ne touchent
  jamais le disque en écriture. `persister` est le SEUL point d'écriture du
  module, et il n'écrit que le fichier explicitement demandé — jamais un
  chemin par défaut, jamais un écrasement silencieux d'autre chose.
- **Déterministe / golden.** Cf. §7. Le test golden (`test_liens.py`) fige
  exactement les 3 liens de sens attendus sur la fixture — toute régression
  du calcul (tokenisation, IDF, cosinus, sélection top_k) fait tomber ce
  test avant de se propager en silence dans un vrai corpus.
- **Porte anti-bruit, jamais anti-mensonge.** La porte protège du **bruit**
  (friction lexicale faible = pas assez de vocabulaire partagé pour
  affirmer un rapport de sens) — elle ne protège PAS du **faussaire** :
  une fiche peut mentir sur son contenu (répéter des termes rares d'un
  autre domaine pour se faire relier à tort, ou au contraire dissimuler son
  vrai sujet pour rester isolée) et la porte n'y verra rien. C'est un filtre
  lexical, pas un filtre de vérité. Cette limite est nommée précisément
  pour ne jamais être présentée comme plus qu'elle n'est : « honnête »
  signifie ici « qui ne se laisse pas voler par du vocabulaire commun »,
  pas « qui vérifie les faits ».
- **`min_poids` et `top_k` sont PROVISOIRES.** `0.08` et `3` sont des
  valeurs prudentes de démarrage (mesurées sur une fixture contrôlée, pas
  sur le corpus réel de 165 fiches). Déclencheur de révision : recaler sur
  la distribution réelle des poids une fois `construire_liens` tourné sur
  la vraie mémoire structurée — première mesure disponible.

## Tests + mutations (`backend/tests/test_liens.py`)

Fixture : 6 fiches (`structure/moteur/persistance/api.md`,
`structure/moteur/coeur/moteur.md`, `structure/ecriture/chemin/
writepath.md`, `structure/moteur/persistance/_index.md`, `structure/
general/notes/bruit_a.md`, `structure/general/notes/bruit_b.md`) :
3 fiches de sens partageant les termes rares « appels », « persistance »,
« survit » ; 1 paire de bruit ne partageant que 2 mots génériques
(« remplissage », « générique ») noyés dans ~18 mots privés chacune ; 1
`_index` qui résume le vocabulaire des 3 fiches de sens (faux carrefour).

**Cœur** :
1. `test_determinisme_deux_builds_identiques` — deux appels identiques →
   graphes `==`.
2. `test_golden_trois_liens_de_sens_au_defaut` — exactement les arêtes
   {api↔moteur, api↔writepath, moteur↔writepath}, 5 nœuds, 2 isolées
   (bruit_a, bruit_b).
3. `test_porte_bloque_la_paire_de_bruit_au_defaut` — aucune arête
   bruit_a↔bruit_b au défaut.
4. `test_aucun_lien_index_par_defaut` — `_index` absent des nœuds ET des
   arêtes.
5. `test_chaque_lien_a_un_pourquoi` — chaque arête a un « pourquoi » non
   vide, ≤5 termes.
6. `test_lien_inter_domaine_existe` — au moins une arête inter-domaine
   (api↔writepath : domaines `moteur` / `ecriture`).
7. `test_voisins_lit_le_graphe_sans_le_recalculer` — `voisins()` lit,
   trie, ne recalcule rien ; fiche isolée → liste vide.
8. `test_persister_ecrit_et_relit_le_meme_graphe` — écriture + relecture
   round-trip.

**Mutations rouges** (chaque assertion DOIT casser si le comportement
régresse) :
- (i) `test_mutation_min_poids_zero_laisse_passer_le_bruit` — `min_poids=0`
  → l'arête bruit_a↔bruit_b apparaît.
- (ii) `test_mutation_exclure_vide_fait_revenir_index` — `exclure=()` →
  `_index` redevient un nœud et porte au moins un lien.
- (iii) `test_mutation_ponderation_brute_fait_remonter_le_bruit` —
  `ponderation="brute"` → l'arête bruit_a↔bruit_b apparaît (poids ≥
  min_poids), alors qu'elle est absente en `"idf"`.
- (iv) `test_mutation_garder_pourquoi_false_lien_sans_pourquoi` —
  `garder_pourquoi=False` → toutes les arêtes existantes sont SANS clé
  `"pourquoi"`.

Vérifié : ces 4 mutations, appliquées comme mutation du CODE SOURCE
(porte désactivée, `exclure` ignoré, pondération forcée à `"brute"`,
`garder_pourquoi` ignoré), font chacune échouer au moins un test de la
suite — la suite ne se contente pas de vérifier ces 4 paramètres en
apparence, elle détecte réellement leur violation.
