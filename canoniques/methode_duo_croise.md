# Méthode — Le duo croisé (relecture du code par une 2ᵉ IA)

> Source : TikTok @dupflodev (« arrête de faire relire ton code par l'IA qui l'a écrit ») — d'après
> les repos de shanraisshan, partagés par Boris Cherny (créateur de Claude Code). Niveau de preuve :
> MOYEN-ÉLEVÉ (pratique de devs avancés + aligné à notre principe). Outil : `nexus_duo.py`.

## Le principe (et pourquoi il marche)

**Un modèle ne voit pas ses propres angles morts ; un modèle DIFFÉRENT, lui, les repère.** Donc on
ne fait jamais relire un code critique par l'IA qui l'a écrit. On branche **deux modèles distincts**.

## Le pipeline (en boucle)

1. **A = constructeur** (ex. Claude) — fait un **plan** (pas de code encore).
2. **B = relecteur** (ex. Codex, modèle DIFFÉRENT) — relit le plan **contre le vrai code**, ajoute ce
   qui manque, repère les cas limites — **sans réécrire**.
3. **A** — **implémente** le plan amendé.
4. **B** — **vérifie** l'implémentation (bugs, angles morts, tests). → boucle jusqu'à OK.
*L'un propose, l'autre conteste.*

## Pourquoi c'est DÉJÀ du NEXUS (et ce que ça ajoute)

C'est notre **conseil inter-systèmes** appliqué au **code**, via le **moteur interchangeable**
(A et B = deux moteurs : Claude ↔ Codex/GPT ↔ Gemini…). Le relecteur joue le rôle du **contradicteur**
(parenté avec ZÉRO l'arène et 98). Et c'est la **même parade** que la racine de confiance : la
fiabilité naît de la **diversité des contrôleurs**, pas d'un acteur parfait. On l'a vécu cette nuit :
Gemini a conçu, ChatGPT a contesté ; Claude Code a construit le backend.

## Garde-fous (honnêteté)

- ⚠️ **Plus lourd** : 2 outils, 2 abonnements → réserver au **code critique**, pas à tout.
- Les deux modèles doivent être **vraiment différents** (sinon mêmes angles morts).
- **Limite actuelle** : le câblage *automatique* Claude ↔ Codex (les deux modèles qui dialoguent
  seuls contre le repo) est un travail de **backend/outillage** (pilier 5). Aujourd'hui, `nexus_duo`
  **génère les 4 prompts du pipeline** prêts à coller dans deux modèles — l'automatisation viendra
  avec le backend (l'orchestrateur appellera A puis B).

## Triplet du coffre

{ donnée : code critique = duo croisé (A plan/code, B relit/vérifie, modèles différents, en boucle) ·
  source : @dupflodev / shanraisshan / Boris Cherny · niveau de preuve : MOYEN-ÉLEVÉ }
