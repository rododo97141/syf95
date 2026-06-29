# Protocole d'évaluation — prouver le progrès RÉEL (pas l'accumulation)

> Réponse directe à la critique mûrie de l'architecte (ChatGPT, 23/06/2026) :
> « le système risque d'accumuler des connaissances sans mécanisme assez rigoureux pour mesurer ses
> progrès réels. » Le débat n'est plus la vision — c'est l'évaluation. Voici le mécanisme.

## Le piège à éviter

Accumuler ≠ grandir. Plus de fiches, plus de leçons, plus d'actions = du « plus », pas une preuve.
Une mesure naïve (autonomie qui monte, activité qui augmente) peut être **illusoire**.

## Le pipeline d'apprentissage (recherche ≠ validation)

```
Observation → Expérience → Recherche → Hypothèse → Test → Mesure → COMPARAISON → Mémoire
```

Point clé de l'architecte : **la recherche ≠ la validation**. La recherche (et le conseil
inter-systèmes) améliore la **qualité des HYPOTHÈSES** ; elle ne prouve pas la **qualité des
RÉSULTATS**. Lire 100 articles peut mener à n'importe quelle conclusion. La preuve naît une étape
plus loin : à la **Comparaison** — « est-ce un meilleur RÉSULTAT ? », pas « est-ce que ça en a
l'air / est-ce plus créatif / a-t-on beaucoup débattu ? ». C'est là que les projets se cassent, et
c'est l'outil `nexus_compare` (compare deux versions sur temps/erreurs/succès, déclare un gagnant
seulement s'il DOMINE).

## Les 6 exigences d'une mesure rigoureuse

1. **Pré-enregistrement** — définir « amélioration » AVANT de mesurer (ex. version A : 10 min /
   12 erreurs ; version B : 3 min / 2 erreurs → B meilleure). Pas de critère choisi après coup.
2. **Contrôle / ablation (l'étalon-or)** — sur une tâche nouvelle, comparer NEXUS **avec** vs
   **sans** sa mémoire/leçons. Si les leçons n'améliorent rien → c'est de l'accumulation morte.
3. **Normalisation par difficulté** — « moins d'aide » ne compte que **à difficulté constante ou
   croissante**. Faire plus facile avec moins d'aide n'est pas progresser.
4. **Non-récurrence des erreurs** — une cause d'échec dont on a tiré une leçon ne doit pas revenir.
   Mesure : % de causes d'erreur qui ne réapparaissent pas.
5. **Taux de transfert** — combien de leçons passées sont réappliquées avec succès à du neuf.
6. **Honnêteté statistique** — déclarer n et la confiance. Petit échantillon = pistes, pas vérités.

## Où en est NEXUS (sans tricher)

| Exigence | État |
|---|---|
| Pré-enregistrement | 🟡 à systématiser (définir le critère avant) |
| Contrôle / ablation | 🔴 **à bâtir** — nécessite de pouvoir couper la mémoire (backend, pilier 5) |
| Normalisation difficulté | 🟢 **branché aujourd'hui** (`--difficulte` dans le capteur + maturité) |
| Non-récurrence | 🟡 amorçable (leçons d'échec + détection de répétition) |
| Transfert | 🟢 journal de transfert (`nexus_lecons applique`) |
| Honnêteté statistique | 🟢 maturité déclare n + confiance |

## L'étalon-or, en clair

La preuve décisive sera l'**ablation** : « sur 10 tâches nouvelles, NEXUS-avec-mémoire fait X ;
NEXUS-sans-mémoire fait Y ; X > Y de façon stable et significative ». Tant que ce test n'existe pas,
tout progrès affiché reste un **proxy** — utile, honnête, mais pas une preuve. Le construire (couper
la mémoire à volonté) est un objectif du backend.

## La règle d'or

NEXUS ne se déclare « meilleur » que sur une mesure **pré-définie, à difficulté contrôlée, avec un
point de comparaison**. Sinon, il dit : « j'ai accumulé, je n'ai pas (encore) prouvé que j'ai grandi. »
