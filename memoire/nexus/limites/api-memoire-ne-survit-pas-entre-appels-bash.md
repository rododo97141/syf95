# API memoire ne survit pas entre appels bash — domaine: nexus / catégorie: limites
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
Le demon HTTP memory_api.py meurt entre 2 appels bash isoles (3 process -> 0). Teste le 20/06/2026.

## Détail
Cause racine : le sandbox Cowork detruit tout l arbre de process a la fin de chaque appel bash. nexus_boot.sh ne resout la persistance QUE dans un meme appel. Correctif robuste : memcli.py, qui reutilise les fonctions fichier de memory_api SANS demon (process court-vivant). Stage en appel B + recall en appel C = preuve OK.

## Source
Test live boucle auto-decouverte 20/06/2026
