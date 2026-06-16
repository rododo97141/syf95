# RADAR 95 — Chef d'orchestre des radars

Pilote interne d'expert-95. Outil UNIVERSEL : il oriente le travail
d'audit/diagnostic du skill, mais la logique est reutilisable sur n'importe quel
corpus. Usage (lecture / aiguillage) : libre ; toute creation, modification ou
fusion durable d'outil = SOUS ACCORD EXPLICITE de l'utilisateur.

Ce fichier definit deux outils :
- **RADAR 95** (Partie I) — le chef d'orchestre.
- **RADAR INSPECTION 95** (Partie II) — l'outil d'audit methodique du skill.

---

## Partie I — RADAR 95 (chef d'orchestre)

### I.1 Role

RADAR 95 ne realise pas l'audit lui-meme : il ORCHESTRE. Il aiguille vers le bon
outil selon la tache, et fait evoluer l'outillage par l'experience. Il ne corrige,
ne cree et ne fusionne jamais rien sans accord explicite.

### I.2 Declenchement

Declencheur : "radar 95", "radar quatre-vingt-quinze". (PAS "active", PAS
"analyse".) Usage (aiguillage / lecture) : libre.

### I.3 Fonction 1 — Aiguillage intelligent

Selon la tache demandee, RADAR 95 oriente vers le bon menu / le bon radar :
- Audit du skill (defauts, incoherences, SSOT) -> "radar inspection 95" (Partie II).
- Choix d'un mode de travail -> "mode menu quatre-vingt-quinze".
- Autre besoin -> proposer l'outil/commande existant le plus adapte (cf.
  `references/commandes.md`).

Regle : toujours preferer un outil EXISTANT avant d'en proposer un nouveau
(anti-doublon, coherent avec le principe SSOT).

### I.4 Fonction 2 — Evolution par l'experience

Quand un besoin recurrent ou une lacune apparait, RADAR 95 PROPOSE de :
- creer un nouvel outil / radar,
- ameliorer un outil existant,
- fusionner des outils redondants.

TOUJOURS sous accord explicite de l'utilisateur : RADAR 95 propose, montre les
passages concernes, justifie, demande oui/non, et n'applique qu'apres un "oui".
Jamais d'auto-modification. Les fusions appartiennent au dirigeant.

### I.5 Garde-fous

- Aiguiller et proposer = libre ; creer / modifier / fusionner = sous accord.
- Toujours citer l'outil existant avant d'en proposer un nouveau.
- Skill universel : SYFIR n'est qu'un cas d'usage parmi d'autres.

---

## Partie II — RADAR INSPECTION 95 (audit methodique du skill)

Moteur d'analyse interne d'expert-95. Outil UNIVERSEL : audite ce skill, mais la
methode est reutilisable sur n'importe quel corpus de fichiers. Lecture seule par
defaut ; toute correction durable = sous autorisation.

### II.1 Role

RADAR INSPECTION 95 inspecte le skill passe par passe pour detecter defauts,
incoherences, commandes fantomes et divergences d'identite (SSOT). Il NE corrige
pas : il diagnostique, note, priorise. La correction est une etape separee, validee.

### II.2 Declenchement

Declencheur : "radar inspection 95". Usage (lecture) : libre. Correction issue
d'un defaut : sous autorisation.

### II.3 Bornage d'une passe

- Inventaire COMPLET d'abord : cartographier l'arborescence reelle avant de
  scanner (garde-fou anti-faux-positif, cf. section II.8).
- 3 fichiers maximum par passe (ou 30 s a 1 min de travail).
- Ne lire que des fichiers NON encore scannes (carte de couverture).
- Aller plus en profondeur a chaque passe.

### II.4 Double notation

- QUALITE /10 : qualite intrinseque du fichier (clarte, completude, honnetete).
- GRAVITE /25 = Impact (1-5) x Probabilite (1-5) : severite d'un defaut.
- Trier les defauts par gravite decroissante.

### II.5 Passe SSOT

Pour tout concept suspect, le confronter a sa SOURCE D'AUTORITE sur 3 axes : nom,
definition, rang. Table d'autorite : SKILL.md > governance.md (dont section 0) >
principles.md > identity.md > nexus-ai.md (pole IA) > reste. Regle d'or : CITER la
source, ou ce n'est pas prouve.

### II.6 Tri 3 etats

- Conforme : aligne sur la source.
- Divergence : contredit la source (= vrai defaut, cite la preuve).
- Silence coherent : absence assumee/documentee (PAS un defaut).

Sans citation de source, un soupcon reste "non-prouve", jamais un defaut.

### II.7 Rapport cumulatif et sortie (format 95)

Sortie de chaque passe : (1) numero de passe + ON, fichiers scannes ; (2)
trouvailles : qualite /10 + defauts (gravite /25) ; (3) RESUME court et precis ;
(4) CRITIQUE DU RADAR (auto-evaluation : qu'a-t-il pu rater ?) ; (5) fin "RADAR
INSPECTION 95 — TERMINE" + menu A/B/C avec recommandation. Tenir un rapport
cumulatif (defauts ouverts / requalifies / corriges).

### II.8 Garde-fous (lecon D-Nexus)

- INVENTAIRE COMPLET obligatoire : un inventaire partiel a produit le faux positif
  D-Nexus.
- "Nexus" = architecture ; "Nexus-AI" = entite legitime (pole IA). Ne jamais
  confondre.
- Confronter a la source AVANT de declarer un defaut (cf. sections II.5 et II.6).
- Le radar diagnostique ; il n'ecrit jamais sans autorisation explicite.
- Les fusions appartiennent au dirigeant.

## Lecture / ecriture

- Lecture : libre, a la demande du Hub.
- Ecriture / mise a jour : durable, sous autorisation (memorise 95).
