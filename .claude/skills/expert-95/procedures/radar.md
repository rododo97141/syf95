# RADAR 95 — Procedure d'audit methodique du skill

Moteur d'analyse interne d'expert-95. Outil UNIVERSEL : audite ce skill, mais la
methode est reutilisable sur n'importe quel corpus de fichiers. Lecture seule par
defaut ; toute correction durable = sous autorisation.

## 1. Role

RADAR 95 inspecte le skill passe par passe pour detecter defauts, incoherences,
commandes fantomes et divergences d'identite (SSOT). Il NE corrige pas : il
diagnostique, note, priorise. La correction est une etape separee, validee.

## 2. Declenchement

Declencheur : "radar 95", "radar quatre-vingt-quinze". (PAS "active", PAS
"analyse".) Usage (lecture) : libre. Correction issue d'un defaut : sous
autorisation.

## 3. Bornage d'une passe

- Inventaire COMPLET d'abord : cartographier l'arborescence reelle avant de
  scanner (garde-fou anti-faux-positif, cf. section 8).
- 3 fichiers maximum par passe (ou 30 s a 1 min de travail).
- Ne lire que des fichiers NON encore scannes (carte de couverture).
- Aller plus en profondeur a chaque passe.

## 4. Double notation

- QUALITE /10 : qualite intrinseque du fichier (clarte, completude, honnetete).
- GRAVITE /25 = Impact (1-5) x Probabilite (1-5) : severite d'un defaut.
- Trier les defauts par gravite decroissante.

## 5. Passe SSOT

Pour tout concept suspect, le confronter a sa SOURCE D'AUTORITE sur 3 axes : nom,
definition, rang. Table d'autorite : SKILL.md > governance.md (dont section 0) >
principles.md > identity.md > nexus-ai.md (pole IA) > reste. Regle d'or : CITER la
source, ou ce n'est pas prouve.

## 6. Tri 3 etats

- Conforme : aligne sur la source.
- Divergence : contredit la source (= vrai defaut, cite la preuve).
- Silence coherent : absence assumee/documentee (PAS un defaut).

Sans citation de source, un soupcon reste "non-prouve", jamais un defaut.

## 7. Rapport cumulatif et sortie (format 95)

Sortie de chaque passe : (1) numero de passe + ON, fichiers scannes ; (2)
trouvailles : qualite /10 + defauts (gravite /25) ; (3) RESUME court et precis ;
(4) CRITIQUE DU RADAR (auto-evaluation : qu'a-t-il pu rater ?) ; (5) fin "RADAR 95
— TERMINE" + menu A/B/C avec recommandation. Tenir un rapport cumulatif (defauts
ouverts / requalifies / corriges).

## 8. Garde-fous (lecon D-Nexus)

- INVENTAIRE COMPLET obligatoire : un inventaire partiel a produit le faux positif
  D-Nexus.
- "Nexus" = architecture ; "Nexus-AI" = entite legitime (pole IA). Ne jamais
  confondre.
- Confronter a la source AVANT de declarer un defaut (cf. sections 5 et 6).
- Le radar diagnostique ; il n'ecrit jamais sans autorisation explicite.
- Les fusions appartiennent au dirigeant.

## Lecture / ecriture

- Lecture : libre, a la demande du Hub.
- Ecriture / mise a jour : durable, sous autorisation (memorise 95).
