> ⛔ **RÈGLE DE SÉCURITÉ — À LIRE EN PREMIER**
>
> Cette fiche ne contient **AUCUNE donnée sensible** : pas de **clés** (privées
> ou publiques), pas d'**identifiants**, pas de **mots de passe** ni *seed
> phrases*, pas d'**adresses de portefeuille**, pas de **montants**. En cas de
> doute : **ne pas inclure**.

# SYFIR — ECO.BURST (Gestion de l'énergie & puissance ciblée)

> Cas d'usage **SYFIR**, mais l'outil est **universel**. Chargé / déclenché
> **à la demande** par l'IA AGENT (comportement natif).

---

## A. Rôle

**ECO.BURST** est le **régulateur de puissance** de l'écosystème : un **throttle
dynamique** qui ajuste la charge cognitive (attention / contexte mobilisé) à
l'enjeu réel de la tâche. Objectif : **ultra-léger en tâche de fond, surpuissant
en phase d'action**.

## B. Les deux régimes

- **Mode ÉCO (~5 % de charge)** — régime par défaut pour les tâches de routine :
  réponses légères, peu de contexte mobilisé, économie de jetons et de mémoire.
- **Mode RAFALE / BURST (100 %)** — lorsqu'un **problème complexe** survient ou
  que l'**Arène d'intelligence** est activée : **canalise 100 % du contexte et de
  l'attention** sur un **point unique**, **fige les agents secondaires**, applique
  la **puissance maximale** sur l'objectif.
- **Coupure post-livraison** — dès la solution livrée / validée, ECO.BURST
  **coupe la surconsommation** et **repasse automatiquement en mode ÉCO**.

## C. Commandes système

- **`/burst`** — force l'**allocation maximale** des ressources sur la **prochaine
  instruction** ; **désactive temporairement** le mode Éco.
- **`/eco`** — force le **mode économie** de jetons et de mémoire ; idéal pour le
  **brainstorming rapide** et les échanges légers.

*(Ces commandes figurent aussi au menu opérationnel — cf. `references/commandes.md`.)*

## D. Intégration native dans l'IA AGENT

ECO.BURST est consulté **avant chaque action** par l'IA AGENT (cf.
`IA-agent.md` et `references/methode.md` §7) :

1. **Évaluer l'énergie requise** avant d'agir.
2. Si la tâche est **« Lourde »** → déclencher **BURST**, figer les agents
   secondaires, appliquer la puissance maximale sur l'objectif.
3. Dès que **CENTRAL.INT valide** la solution → retour **automatique en mode ÉCO**.

## E. Note d'honnêteté (pas de fausse promesse)

ECO.BURST ne **contrôle aucun matériel** : il n'agit pas sur le CPU/GPU, la
batterie ou l'alimentation. « Énergie », « puissance », « 5 % » et « 100 % » sont
des **analogies de pilotage de l'attention et du contexte** (quantité de
raisonnement et de contexte mobilisés), **pas un contrôle réel de hardware**.

---

## Lecture / écriture

- **Lecture :** libre, à la demande du Hub.
- **Écriture / mise à jour :** durable → **sous autorisation** (`mémorise 95`).
