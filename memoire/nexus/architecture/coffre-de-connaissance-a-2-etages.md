# Coffre de connaissance a 2 etages — domaine: nexus / catégorie: architecture
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
Coffre a 2 etages : memoire-beta (machine, traçable, +champ niveau_preuve) + NotebookLM (humain, exploitation). Triplet {donnee,source,preuve} = regle d entree.

## Détail
Conception Phase 1 (livrable NEXUS_coffre_de_connaissance.md). Chaine : CHERCHER (Perplexity Academic + sources primaires data.ina.fr/Scholar/PubMed) -> VALIDER (SIFT + hierarchie preuves) -> STOCKER -> EXPLOITER. Coffre a 2 etages : (1) MACHINE = memoire-beta (agents, API, traçable) ; manque 1 champ niveau_de_preuve pour devenir coffre scientifique -> chaque fiche = triplet {donnee, source primaire, niveau de preuve}. (2) HUMAIN = NotebookLM (Kily depose sources validees -> resumes/audio/mindmaps). Lien = le triplet circule de la recherche vers machine puis humain. Regle : rien n entre sans source primaire + niveau de fiabilite. Prochaines etapes : enrichir memoire-beta du champ niveau_de_preuve (via modification 95), connecter comptes Google/Perplexity Pro, roder la chaine sur un sujet reel, puis audit/simplification systeme.

## Source
conception expert-95 20/06/2026
