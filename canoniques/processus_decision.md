# Processus de décision de l'écosystème

**Statut : canon — invariant de fonctionnement.** Outil : `nexus_process.py`. Né d'une correction du Créateur (session du 24/06/2026) : une décision qui touche l'écosystème avait été prise en *demandant* à l'utilisateur puis en *obéissant*, sans processus. C'est l'erreur que cette fiche corrige.

## La règle

Un changement qui **touche l'écosystème** ne se décide pas en demandant son avis au Créateur puis en l'appliquant. Il se décide ainsi :

1. **Réaliser** chaque option (pas une seule — les deux, ou toutes). Une option « pensée mais pas faite » n'existe pas pour la décision.
2. **Mesurer** le résultat de chacune, par sa **valeur réelle** (pas l'intention, pas l'avis).
3. **Trancher par la valeur** du résultat : *ajouter · activer · désactiver · archiver*.

Tant qu'une option n'est pas réalisée **et** mesurée, elle n'entre pas dans la balance — et on ne rend pas de verdict. « On note » n'est pas « on fait ». Un brouillon n'est pas un résultat.

## Droits de décision (qui écoute qui)

- **Touche l'écosystème** → le **système** décide, par la valeur mesurée. L'avis exprimé (même celui du Créateur sur le moment) ne remplace pas le résultat.
- **Ne touche pas l'écosystème** (faible enjeu, réversible, local) → l'avis de l'utilisateur peut suffire.
- **Créateur** → peut toujours trancher **hors-système**, mais explicitement, en sachant qu'il passe outre le résultat (souveraineté du Créateur, invariant 1).

Conséquence pour l'assistant : ne pas confondre « écouter le Créateur » avec « obéir à une réponse rapide ». Quand ça touche l'écosystème, le rôle est d'**expérimenter et mesurer les options**, puis de laisser le résultat décider — pas de demander une préférence et de l'appliquer.

## Rien ne meurt

L'option non retenue est **archivée**, pas supprimée : réactivable si le contexte change (cf. [fiche_survie_et_interactions], [fiche_moteur_de_valeur]). Réversibilité (invariant 3).

## Lien avec les autres organes

- 96 mesure (la valeur du résultat), 95 arbitre, 92 perfectionne, ZÉRO confronte les options, 98 garde.
- S'articule avec l'**orchestrateur** (`nexus_orchestre`) : créer/modifier un organe est dur + à fort enjeu → CONSEIL, et passe par l'**organogenèse** (`nexus_genese`) et ce processus.

## Exemple appliqué (résumé+points clés : skill vs préférence)

- Option A « skill » (`nexus-resumeur`) : **réalisée** (packagée) mais **valeur non mesurée** (le banc de déclenchement exige un Claude Code connecté).
- Option B « préférence/mémoire » : **réalisée + mesurée** (comportement toujours actif, fiable).
- Verdict du système (`nexus_process decider`) : **ACTIVER la préférence** maintenant (seule prouvée) ; **garder le skill en réserve** jusqu'à sa mesure. Décidé par la valeur, pas par la préférence exprimée.
