# Fiche — Règle de survie + contrôle des interactions (2 trous mathématiques)

> Réponse aux deux derniers manques *mathématiques* (architecte, 23/06/2026), distincts du
> philosophique. Outils : `nexus_survie.py` + topologie en étoile. Le 3ᵉ (définir la valeur) est
> déjà traité par `nexus_evaluer` (Score = f(contexte)).

## 1. Quand une solution survit-elle ? (la bande de survie)

« A=90, B=89, C=88, D=20 : on garde quoi ? Où est la limite ? Qui décide ? Sur quelle métrique ? »

Réponse darwinienne : ni « le meilleur seul », ni « tout le monde » → une **BANDE** + une **archive**.
- 🟢 **ACTIF** : score ≥ meilleur − bande (ex. bande 5 → ≥ 85) → A, B, C **survivent en parallèle**
  (variantes du sommet, chacune utile selon le contexte). 
- 🟡 **RÉSERVE** : sous la bande mais gagne dans ≥1 contexte → archivé, **réactivable** (pépite dormante).
- ⚪ **ARCHIVE** : loin du sommet, aucun contexte → archive profonde, **jamais supprimée**. (D=20)

→ La limite n'est **pas arbitraire** : c'est la bande (relative au meilleur). Qui décide ? **La règle**,
pas une personne. Sur quelle métrique ? Le **score** (contextuel, cf. [[fiche_definir_meilleur]]).

## 2. Contrôle des interactions (anti-explosion)

Maillage « tous ↔ tous » = **N(N−1)** interactions → quadratique, ingérable :
- 10 organes → 90 · 20 → 380 · **100 → 9 900.**

Parade : **topologie en ÉTOILE** autour de la **mémoire-hub** (les organes ne se parlent pas
directement ; ils lisent/écrivent dans la mémoire) → coût **LINÉAIRE (N)** :
- 10 → 10 · 20 → 20 · **100 → 100.**
+ **équipes temporaires** (systèmes passagers) : seuls k organes convoqués par mission → coût borné
(k=4 → 12 interactions, quel que soit N).

→ C'est pourquoi le schéma de câblage met la **mémoire au centre** : ce n'était pas esthétique,
c'était l'anti-explosion. La hiérarchie légère (95 décide, 96 propose) limite encore les échanges.

## Bilan : les 3 trous d'implémentabilité de l'architecte

| Trou | Mécanisme | État |
|---|---|---|
| Définir « valeur » | `nexus_evaluer` (Score = f(contexte)) | ✅ |
| Règles de survie | `nexus_survie` (bande + archive) | ✅ |
| Contrôle des interactions | étoile (mémoire-hub) + équipes temporaires | ✅ (conception) |

## Triplet du coffre

{ donnée : survie = bande relative + archive ; interactions = étoile (N) pas maillage (N²) · source :
  trous mathématiques de l'architecte · niveau de preuve : MOYEN (mécanismes démontrés) }
