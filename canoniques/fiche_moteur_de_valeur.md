# Fiche — Le moteur de valeur (éliminer le faible sans tuer les pépites)

> Réponse au problème que l'architecte juge CENTRAL (23/06/2026) : « comment mesurer la valeur d'une
> idée assez objectivement pour éliminer les moins bonnes SANS éliminer les futures pépites ? » +
> « quand s'arrête-t-on (amélioration infinie) ? ». Outils : `nexus_evaluer.py`, `nexus_stop.py`.

## 1. De la philosophie de la valeur au MOTEUR de valeur

Avant : « la valeur décide » (une philosophie). Maintenant : un **calcul**.
  **valeur = Score(solution, contexte) = Σ poids_contexte × critère** (voir [[fiche_definir_meilleur]]).

## 2. Éliminer le faible SANS tuer les pépites → ARCHIVER, jamais supprimer

Puisque la valeur dépend du contexte, une idée « perdante » ne l'est que **dans ce contexte**. Donc :
- une idée qui gagne dans **≥1 contexte** = **pépite active** → on la garde ;
- une idée dominée dans **tous les contextes connus** = **archivée**, *jamais supprimée* ;
- quand le **contexte change**, on **réévalue les archives** : une dormante peut devenir dominante
  (ex. smartphone tactile : ridicule en 2005, dominant en 2025).

Démontré (A/B/C/D, 3 contextes) : A/B/D gardées (chacune gagne quelque part), C archivée.
→ On n'élimine définitivement **rien** ; la mémoire est une bibliothèque, pas une poubelle.

## 3. Quand s'arrête-t-on ? → SATISFICING (anti amélioration infinie)

Il existe presque toujours mieux → viser l'optimum = ne jamais livrer. On s'arrête si **l'une** :
1. le résultat ≥ **seuil pré-enregistré** (« assez bon ») ;
2. le dernier **gain < rendement minimal** (optimiser coûte plus que ça ne rapporte) ;
3. le **budget** (temps/itérations) est épuisé.
« Assez bon exécuté » bat « parfait jamais fini ».

## 4. L'insight de l'architecte qu'on adopte

Le vrai centre de NEXUS n'est peut-être pas 95, mais **la mémoire + le mécanisme de sélection**.
Les organes changent ; ce qui conserve l'expérience et trie, c'est la mémoire (+ score + archive).

## Le trou honnête qui reste

D'où viennent les **poids du contexte** ? Au départ, fixés par 95/Kily ; ensuite **recalibrés par
les résultats comparés** (le comparateur corrige les estimations). La fonction existe ; sa
**calibration apprise** est le prochain étage (et c'est là que « le reste s'emboîte »).

## Triplet du coffre

{ donnée : moteur de valeur = Score(contexte) + archive (jamais supprimer) + satisficing · source :
  problème central de l'architecte + nexus_evaluer/nexus_stop · niveau de preuve : MOYEN }
