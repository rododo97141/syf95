# Évaluation des tâches ouvertes — l'option A, axiomatique

**Statut : canon (proposé — le Créateur amende en mode créateur).** Outil : `nexus_evaluation.py`. Aboutissement du conseil à cinq (Claude, Kimi, Gemini, ChatGPT, Claude frais) : pour une tâche **ouverte**, il n'existe pas de valeur scalaire réelle à mesurer. On **n'estime pas un réel**, on **agrège des préférences selon des AXIOMES choisis**. C'est l'option A « dur » : on assume des axiomes, et on construit l'agrégation qui les honore.

## Les 7 axiomes

1. **Comparatif, pas absolu** — on agrège des « A vs B », jamais une note « vraie » sur 5.
2. **Aveugle + swap** — A vs B *et* B vs A, étiquettes masquées ; ne garder que les jugements cohérents (anti biais de position/longueur/sycophancy).
3. **Probabilité calibrée** — sortir P(A≻B) par **Bradley-Terry** (axiome de calibration des probabilités futures).
4. **Robustesse clones / Condorcet** — calculer aussi un classement **ordinal (Copeland)** ; si Bradley-Terry et l'ordinal **divergent** → signaler (clones/IIA ou structure non scalaire).
5. **Cycles = signal** — détecter les cycles de préférence (A≻B≻C≻A) et les **rapporter** (qualité multidimensionnelle / fronts de Pareto), au lieu de les lisser en un scalaire.
6. **Baseline forte** — comparer à une IA forte bien promptée, jamais un homme de paille.
7. **Honnêteté de spécification** — déclarer : ceci **agrège des préférences selon des axiomes**, ça ne **mesure pas** un réel. Si aucune échelle latente n'existe (ou si les juges sont parfaits → **séparation** → MLE divergent), Bradley-Terry **fabrique** un nombre ; on le dit et on se rabat sur l'ordinal.

## Ce que l'outil fait (vérifié, 54 tests verts au total)

Entrée = comparaisons par paires « gagnant>perdant ». Sortie : ① Bradley-Terry (Elo + P(A≻B), avec **alerte de divergence** si séparation) ; ② Copeland (ordinal robuste) ; ④ alerte si BT et Copeland **divergent** ; ⑤ **détection et report des cycles** comme signal. Démontré : transitif net → séparation signalée, défère à Copeland ; transitif bruité → BT converge (P≈78 %) et concorde ; cyclique → cycle rapporté, « un score unique écraserait la structure ».

## Ce que ça implique (et ce qui reste au Créateur)

Choisir comment NEXUS évalue est **normatif**, pas empirique : c'est choisir les axiomes (calibration → Bradley-Terry ; robustesse clones/cycles → ordinal), jamais prétendre mesurer un réel inexistant. Définir/amender ces axiomes = définir ce que NEXUS *est*. Lié à [fiche_critere_de_resolution], [fiche_paradoxe_mesure], [fiche_mesurer_la_valeur], [recherche_calculer_la_valeur].
