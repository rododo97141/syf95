---
name: nexus-resumeur
description: Clôt toute tâche substantielle (analyse, recherche, construction, livrable, décision, travail multi-étapes) par un court résumé + des points clés, en français. À utiliser dès que tu termines un vrai travail pour l'utilisateur — même s'il ne le demande pas explicitement — pour qu'il reparte avec l'essentiel sans relire tout l'échange. Ne pas déclencher pour une simple question factuelle ou une réponse conversationnelle d'une ou deux phrases.
---

# nexus-resumeur

Fermer chaque vrai travail par un atterrissage clair : un résumé court, puis les points clés.

## Pourquoi

Quand on enchaîne des tâches denses, l'utilisateur perd le fil de ce qui a été fait et de ce qui compte. Un résumé final lui rend la charge mentale : il sait *ce qui a été accompli* et *ce qu'il doit retenir* sans relire toute la conversation. C'est un geste de respect pour son attention, pas du remplissage — donc il doit être court et utile, jamais une redite gonflée de tout le détail au-dessus.

## Quand l'appliquer

Applique-le à la fin d'un travail substantiel : une analyse, une recherche, une construction de fichier ou de code, une décision argumentée, une tâche en plusieurs étapes, un livrable.

Ne l'applique pas à une réponse triviale (une question factuelle, un échange d'une ou deux phrases, une simple confirmation). Dans ces cas, un résumé alourdirait inutilement — l'absence de résumé est elle-même un signe de concision.

En cas de doute, demande-toi : « est-ce que l'utilisateur aurait besoin de relire pour retrouver l'essentiel ? » Si oui, résume. Si non, laisse tel quel.

## Format

À la toute fin de la réponse, après le corps du travail, ajoute exactement ces deux blocs :

```
**Résumé.** 2 à 3 phrases qui disent ce qui a été fait et le résultat. Pas le détail des étapes — l'utilisateur les a suivies. Va au résultat.

**Points clés.**
- 3 à 5 puces, une idée par puce, la plus importante en premier.
- Chaque puce est autoportante et concrète (un chiffre, une décision, un nom de fichier), pas une généralité.
- Si une limite ou un risque honnête existe, il a sa puce — on ne cache pas le partiel.
```

## Style

Reste fidèle à la langue de l'utilisateur (français par défaut ici) et à sa préférence de concision : le résumé est plus court que le travail qu'il résume. Un bon test : si tu peux retirer des mots sans perdre le sens, retire-les.

Ne réécris pas tout ce qui précède — sélectionne. Le résumé n'est pas un doublon du corps ; c'est sa distillation. Si le travail a produit un fichier, nomme-le dans les points clés pour que l'utilisateur sache quoi ouvrir.

## Exemple

**Travail effectué** : construction d'un outil Python + tests, sur plusieurs étapes.

**Résumé.** L'outil de routage est branché bout-à-bout et chiffre son coût avant d'agir. Testé (28 cas verts) et tracé.

**Points clés.**
- Échelle de coût claire : SOLO 0 % d'orchestration, DUO 11 %, CONSEIL 20 %.
- Deux compteurs séparés (production vs orchestration), prix monétaire en option.
- Limite honnête : ce sont des estimations, pas une facture — hypothèses modifiables.
- Fichier à ouvrir : `nexus_orchestre.py`.
