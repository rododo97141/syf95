# Le compteur /stats en_attente est trompeur (compte les tombes) — domaine: nexus / catégorie: limites
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
/stats en_attente compte les fichiers bruts (tombes incluses) ; seul /staging filtre. D'ou le faux 'bug compteur'.

## Détail
Apres reconciliation : /staging count = 0 (file actionnable vide) MAIS /stats affiche en_attente=21. Explication : stats() compte les *fichiers* du dossier en_attente (21 = 18 reconcilies + 3 anciennes tombes), alors que list_staging() exclut les meta.promu=true. Le 'bug compteur en_attente non vide apres promote' n'est donc pas un bug de promote mais un compteur stats qui n'exclut pas les tombes. Correctif propose : faire compter stats() comme staging (exclure promu:true).

## Source
observation live 20/06/2026 22h18
