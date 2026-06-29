# Architecture 95-97 = gold standard manager-worker — domaine: nexus / catégorie: validation-externe
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
95 pense / 97 execute = gold standard manager-worker avec separation stricte. Architecture validee.

## Détail
Decouverte : le pattern Manager-Worker (Supervisor) est le gold standard 2026 de l orchestration d agents. Best practice cle : SEPARATION STRICTE planifier/executer — un coordinateur qui delegue n a pas le droit d editer ; un executeur qui edite n a pas le droit de deleguer (evite les boucles et le do-it-yourself). C est EXACTEMENT la conception SYF95 : expert-95 pense et ne touche jamais les outils, expert-97 execute. Garde-fous : taches bornees = moins d hallucination ; apres 3 iterations bloquees, kill/reassign. L architecture de Kily est conforme au gold standard.

## Source
orchestration best practices 2026
