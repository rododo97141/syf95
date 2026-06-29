# Méthode — Le Conseil inter-systèmes (multi-agent reflection)

> Méthode validée le 22/06/2026 : un modèle CONSTRUIT, un autre RED-TEAM, NEXUS tranche.
> État de l'art : « multi-agent reflection » (plusieurs agents réfléchissent sous des angles
> différents évite les optima locaux d'une seule IA). Outil : `nexus_council.py`.

## Quand le convoquer

Pour toute **décision ou design important** : architecture, gouvernance, changement risqué,
choix stratégique. PAS pour les tâches triviales (coût > bénéfice).

## Les rôles

- **Constructeur** (un modèle, ex. Gemini) — propose la MEILLEURE solution, structurée.
- **Red-team** (un AUTRE modèle, ex. ChatGPT) — avocat du diable : 3 failles majeures + correctifs.
  *Doit être franc, jamais complaisant.*
- **NEXUS / 95** — tranche : garde le design, intègre les correctifs validés, écarte le reste.
- **98** — garde un droit de veto sécurité sur la décision finale.

## Le protocole (5 étapes)

1. **95 formule** la question + les critères de réussite.
2. **Constructeur** produit le design (via `nexus_council.py prompts`).
3. **Red-team** attaque (mêmes prompts, autre modèle).
4. **95 synthétise** : design + correctifs retenus, en cohérence avec le canon (rien ne le contredit).
5. **Journaliser** (constructeur, critique, décision, leçon) → `nexus_council.py log`. 96 lira le journal.

## Garde-fous

- **Diversité** : jamais le même modèle pour construire ET critiquer.
- **Honnêteté** : le red-team doit être réel (« sois critique, pas complaisant »).
- **Souveraineté** : la décision finale revient à NEXUS/Kily, jamais à un modèle externe.
- **Coût** : 2 modèles suffisent ; un 3ᵉ = rendement décroissant (sauf désaccord majeur).

## Preuve (la première session)

Sujet : la boucle auto-mandatée. Gemini a conçu (4 sources + filtre d'admission) ; ChatGPT a
trouvé 3 failles (Goodhart, runaway recursion, capture par 96) + correctifs. NEXUS a synthétisé
une spec robuste. Voir [[fiche_boucle_auto_mandatee]].
