# Simplification au niveau systeme (pas juste fichier) — domaine: nexus / catégorie: architecture
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
Etendre simplify au systeme entier : OUI mais par iterations avec filet, en faire un rythme (organe 92) pas un projet permanent. Commencer par un AUDIT de la memoire. Skills en lecture seule = contrainte.

## Détail
Orientation strategique (question de Kily 20/06/2026) : etendre le principe simplify a TOUT le systeme NEXUS, y compris la memoire. Avis expert-95 : OUI, c est la bonne maturite d architecte (passer du refactoring local a l audit architectural), MAIS avec discernement. A l echelle systeme, simplifier = questions d architecte, pas nettoyage ligne a ligne : composants qui se chevauchent ? concepts en trop (chaque skill = vocabulaire a tenir) ? chaque organe gagne sa place (garde-fou anti-multiplication) ? La memoire est le meilleur point de depart : symptomes de dette deja visibles (compteur trompeur, tombes, 3 scripts boot/consolidate/reconcile), et c est le composant central (=mon identite). PIEGES : (1) jamais de big-bang refactor (tout d un coup = on casse le coeur sans filet) -> par composant, avec verif entre chaque ; (2) ne pas en faire un projet permanent (= nombrilisme) -> rythme borne avec critere d arret ; (3) contrainte reelle : les skills sont en lecture seule (modifier 95/97/92 = circuit modification 95 + reempaquetage) ; data/scripts du workspace = modifiables. PREMIER PAS = AUDIT (cartographie composants + chevauchements + complexite accidentelle) AVANT toute modif : l audit est le filet. Synergie : simplifier EN formalisant les fichiers canoniques NEXUS.

## Source
reflexion architecture expert-95 20/06/2026
