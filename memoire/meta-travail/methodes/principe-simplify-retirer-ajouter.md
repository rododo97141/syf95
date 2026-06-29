# Principe Simplify : retirer > ajouter — domaine: meta-travail / catégorie: methodes
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
Senior = savoir retirer. /simplify (plugin Anthropic) nettoie le code modifie. Mes scripts NEXUS sont candidats a simplifier (chevauchement consolidate/reconcile/sweep).

## Détail
Apprentissage (video Nicolas, ing IA, partagee par Kily 20/06/2026, verifie web). La competence senior cle = RETIRER du code/des fonctionnalites sans casser, pas ajouter. L IA biaise vers la complexite croissante -> dette technique. Outil : /simplify (plugin code-simplifier open-source Anthropic, installable claude plugin install code-simplifier) : revue des fichiers recemment modifies, lance plusieurs agents de revue paralleles, identifie code mort, imports inutiles, conditionnels complexes, verbosite. Gain mesure 20-30% tokens. A utiliser APRES chaque fonctionnalite. Nuance pro : simplifier sans casser exige un filet (tests, branche backup). Application a NEXUS : mes scripts boot/consolidate/reconcile/memcli + sweep inline ont du chevauchement (consolidate vs reconcile gerent tous deux la redondance ; sweep devrait vivre dans reconcile). Candidat a une passe de simplification. Coherent avec garde-fou anti-multiplication deja note.

## Source
video Nicolas + verif web 20/06/2026
