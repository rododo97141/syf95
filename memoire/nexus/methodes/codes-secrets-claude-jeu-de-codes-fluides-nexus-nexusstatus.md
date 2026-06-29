# Codes secrets Claude -> jeu de codes fluides NEXUS (+ nexus_status) — domaine: nexus / catégorie: methodes
> Créé le 22/06/2026 · Dernière mise à jour le 22/06/2026

## En bref
Codes secrets Claude = role+format+succes + commandes raccourcis (pas de magie). Applique a NEXUS : nexus_status (1 code -> tout l etat) + jeu de codes fluides (etat/sens/analyse/sante/range/boot). Bug flock deadlock corrige par le test.

## Détail
Analyse (video 5 codes secrets pour Claude, Nolan Chretien, partagee par Kily 20/06/2026 - titre seulement, pas le contenu exact). Recherche : pas de vrais codes magiques ; les codes secrets = (a) commandes-raccourcis (/voice, /loop, /schedule) + (b) principe de prompting universel : dire le ROLE + le FORMAT + le SUCCES. APPLICATION A NEXUS (role test/experience) avec fluidite propre : (1) Construit nexus_status.py = LE code fluide qui montre TOUT l organisme en UNE commande (orchestre capteurs+96+98 ; sentir->analyser->veiller). Teste OK. (2) JEU DE CODES NEXUS (mots-cles que Kily dit -> j execute) : etat/status -> nexus_status ; sens [tache] -> log capteur ; analyse -> 96 ; sante -> 98 ; range -> organize ; reveille/boot -> boot ; active 95 -> organes ; memorise 95 -> memoire permanente. (3) Principe ROLE+FORMAT+SUCCES integre a chaque tache (deja dans DIKW : definir le succes). BUG CORRIGE par le test : le verrou flock bloquant pouvait DEADLOCK sur lock orphelin -> rendu non-bloquant (flock -n seulement) + nexus_status ne boote que si l API ne repond pas. Lecon terrain : construire->tester->trouver le bug->corriger.

## Source
analyse video + application 20/06/2026
