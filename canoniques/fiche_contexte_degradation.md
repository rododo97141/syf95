# Fiche — La qualité d'une IA chute quand son contexte se remplit (« context rot »)

> Source : TikTok @shubhamnocode, « Votre IA devient bête après 40% »
> (https://www.tiktok.com/@shubhamnocode/video/7633193976350117142). Analysée avec la grille.
> Niveau de preuve : ÉLEVÉ — phénomène documenté par la recherche (voir ci-dessous).

## Le message

Chaque IA a une fenêtre de contexte (context window). Mais sa qualité **se dégrade bien avant
que la fenêtre soit pleine** — la vidéo dit « après 40% ». Plus on remplit, plus l'IA « oublie »
ou se disperse.

## Vérification (filtre 2 : concret ou hype ?) → CONCRET

- **« Lost in the Middle »** (Liu et al., Stanford/Berkeley/Samaya, 2023) : l'info au MILIEU du
  contexte est bien moins utilisée qu'au début ou à la fin (courbe en U, perte > 30%). Répliqué
  sur 6 familles de modèles (GPT-4, Claude, etc.).
- **« Context rot »** : plus l'entrée est longue, plus la perf tend à baisser.
- Cause architecturale : l'encodage de position (RoPE) privilégie début et fin.
- ⚠️ Le « 40% » est un chiffre **vulgarisé** : le vrai constat est une dégradation progressive,
  pas un seuil magique universel.

## Pourquoi c'est CRUCIAL pour NEXUS

NEXUS recharge à chaque appel ses canoniques + des fiches mémoire dans le contexte. Trop en
charger ne fait pas que coûter des tokens — **ça peut DÉGRADER la qualité** des organes.
C'est le pendant « qualité » du levier « coût » vu avec Caveman. Conclusion : un contexte
**léger et bien ordonné** (l'important au début et à la fin) vaut mieux qu'un contexte gavé.

## Application concrète

- [ ] **Mémoire** : ne charger que les fiches PERTINENTES (recall ciblé), pas tout le coffre —
  c'est déjà la logique du tri 3 étages de memoire-beta, à tenir avec discipline.
- [ ] **Ordre** : placer l'essentiel (identité, consigne en cours) en début/fin de contexte,
  pas noyé au milieu.
- [ ] **Capteur** : la dimension « verbosité/tokens » (déjà ajoutée) sert aussi à surveiller
  qu'on ne sur-remplit pas le contexte.

## Triplet du coffre

{ donnée : la perf d'un LLM se dégrade quand le contexte se remplit (lost-in-the-middle) ·
  source : @shubhamnocode + papier « Lost in the Middle » 2023 · niveau de preuve : ÉLEVÉ }
