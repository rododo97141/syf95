# Fiche — La boucle qui se mandate elle-même (design issu du dialogue NEXUS × Gemini)

> Source : dialogue inter-systèmes NEXUS ↔ Gemini (22/06/2026), sur « comment une boucle d'agents
> génère seule son travail, utile ET sûr ». Niveau de preuve : MOYEN (raisonnement d'architecture,
> non encore implémenté). À bâtir côté backend (pilier 5).

## Le manque qu'on comble

NEXUS = boucle qui s'auto-vérifie. Manque : **se fixer seul ses missions**. Ce design décrit
comment, sans tourner à vide ni partir dans tous les sens.

## Principe retenu (avec une correction NEXUS validée par Gemini)

Le moteur de curiosité = **96 (détection d'écart, « voit pour agir », DANS la boucle)**, PAS 98.
98 reste le **système immunitaire pur** (Danger Theory : réagir au dommage réel, pas à la
nouveauté) avec un **droit de veto sécurité**. Chaîne : **96 détecte → 95 décide → 97 agit → 98
garde le veto**. Nouveau déclencheur de 95 : un **« tableau de tâches auto-générées »** (au lieu de
l'entrée humaine), avec validation humaine au début, puis 96 gère les vannes.

## Les 4 sources de missions (chacune son garde-fou)

1. **Détection d'écart** (96 compare modèle interne vs réalité/résultats de 97) → garde-fou : filtre
   de criticité (impact sur le framework).
2. **Marché interne** (92 repère goulets : latence, échecs, mémoire trop dense → tickets d'optim) →
   garde-fou : ROI (gain estimé > coût en tokens/temps).
3. **Anticipation par scénarios** (95 simule des futurs → objectifs moyen terme) → garde-fou : PoC
   empirique minimale (sinon on gèle).
4. **Dérive créative contrôlée** (95 injecte une variation/mutation → mission expérimentale B) →
   garde-fou : sandbox + veto/kill switch de 96.

## Le filtre d'admission de 96 (anti-inflation de micro-missions)

Trois tamis, condensés en une formule de priorité :

  Priorité = (Criticité × Fréquence d'Activation (FAD) × Facteur de Persistance) / Coût de calcul

- **FAD** : plus le nœud mémoire/outil concerné est sollicité par les autres organes, plus c'est
  prioritaire (les écarts périphériques → pile « maintenance basse »).
- **Persistance (debounce)** : un écart doit persister sur N cycles avant de devenir mission ; le
  transitoire = bruit, ignoré.
- **Seuil dynamique (taxe de congestion)** : si la file de 95/97 est saturée, le seuil monte ; un
  nouvel écart doit battre la valeur moyenne des tâches en cours, sinon il est jeté (pas stocké).

→ Sous le seuil : 96 archive dans les logs locaux, **n'alerte pas** 95. L'attention est préservée
mathématiquement.

## Application concrète (backend, pilier 5)

- [ ] Coder le **filtre d'admission de 96** (la formule ci-dessus) — c'est le cœur.
- [ ] Remplacer le trigger de 95 : entrée humaine → tableau de tâches auto-générées.
- [ ] Démarrer par la **source 1 (détection d'écart)** + garde-fou ROI : faible risque, réutilise
  les organes existants. Garder la validation humaine au début (0,01 %).

## Stress-test (avocat du diable) par ChatGPT — 3 failles + correctifs

Validation croisée : ChatGPT a attaqué le design de Gemini. Trois risques majeurs :

1. **Goodhart extrême** — le système optimise ses *métriques* au lieu du besoin réel (« industrie
   de l'auto-observation » : il mesure surtout sa propre activité). *Correctif* : ajouter un facteur
   **Impact_Utilisateur ∈ [0;1]** à la formule → aucune mission ne survit en n'améliorant que des
   indicateurs internes. Formule affinée :
   **Priorité = (Criticité × Fréquence × Persistance × Impact_Utilisateur) ÷ Coût.**

2. **Boucle d'auto-génération infinie (runaway recursion)** — 96 analyse 96 → générateur de travail
   sans fin ; une hausse de sensibilité de détection (0,5 %→2 %→8 %→20 %) = « alert storm ». La
   formule *trie* les missions mais ne *limite pas* leur génération. *Correctif* : un **budget de
   génération** (ex. 10 % du calcul) → règle d'or **Détection ≠ Création**.

3. **Capture du système par 96** — qui choisit les problèmes gouverne ; 95 ne déciderait plus que
   *parmi ce que 96 lui présente* (centralisation cachée). *Correctif* : **canaux de missions
   indépendants** (A: 96 · B: objectifs mémoire · C: utilisateur · D: audits aléatoires) avec
   **≥ 20 % des décisions de 95 issues de sources non-96**.

**Le risque-clé (et la convergence) :** ChatGPT conclut que le vrai danger n'est pas la sécurité
(98 bloque) mais la **dérive cognitive interne** — « le système devient excellent à optimiser sa
propre représentation du monde » plutôt que la réalité. C'est *exactement* notre **gardien de la
réalité** (activité ≠ progrès). Deux systèmes externes convergent vers notre principe le plus
profond → forte validation.

## Triplet du coffre

{ donnée : une boucle peut se mandater seule via détection d'écart filtrée par un score
  Criticité×FAD×Persistance / Coût · source : dialogue NEXUS × Gemini · niveau de preuve : MOYEN }
