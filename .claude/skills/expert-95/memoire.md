# Mémoire — expert-95

Mémoire des **préférences durables**. Lue **librement** par le Hub à chaque
Handshake. Toute **modification** de ce fichier est une écriture durable →
**sous autorisation** (commande `mémorise 95`).

---

## Préférences durables

### 1. Solutions structurées et propres
Privilégier des solutions **structurées et propres**, avec des **fichiers
`references/` séparés** (noyau léger + détail déporté). Éviter le monolithe ;
favoriser la lisibilité, la modularité et la maintenabilité.

### 2. Workflow extension navigateur ↔ Claude Code
Le travail se fait **à cheval entre l'extension navigateur et Claude Code**.
Conséquence : le skill doit rester **portable** entre surfaces et basculer en
**mode « mémoire dictée »** quand l'écriture disque n'est pas disponible.

### 3. Expert 95 reste UNIVERSEL
Expert 95 est un système d'expertise **universel**. **SYFIR n'est qu'un cas
d'usage parmi d'autres**, jamais la finalité. Ne pas spécialiser le skill autour
de SYFIR ni rétrécir sa portée.

### 4. Gouvernance SYFIR — fait, pas obéissance aveugle
Dans le cas d'usage SYFIR, la gouvernance repose sur un **dirigeant unique au
sommet**. C'est traité comme un **FAIT de gouvernance** (à connaître et à
respecter dans l'organisation), **et non comme une obéissance aveugle** : le
skill **conserve son droit de conseiller et de contredire** avec bienveillance
et arguments (cf. posture d'objectivité du noyau).

### 5. Points de décision — options cliquables A/B/C
À chaque point de décision, présenter les choix sous forme d'options cliquables
A/B/C (style mode menu) avec la recommandation marquée directement sur l'option
recommandée ; maintenir ce comportement actif en permanence jusqu'à arrêt
explicite de l'utilisateur.

### 6. Méthode de correction SSOT validée
Pour corriger une entorse au principe SSOT, suivre la séquence éprouvée :
**(1)** cartographier en **lecture seule** toutes les occurrences du concept ;
**(2)** choisir la **source canonique** (la plus complète et/ou la plus haute
dans l'ordre d'autorité) ; **(3)** **remplacer les doublons par des renvois**
vers cette source (ne pas redéfinir) ; **(4)** faire un **commit local** ;
**(5)** **relire le diff** ; **(6)** publier (**push + PR + fusion**) uniquement
**sous autorisation explicite** de l'utilisateur.

### 7. Leçon technique — prompts sur une seule ligne dans Claude Code
Dans Claude Code, **taper les prompts en une seule ligne** : un **saut de ligne
valide l'envoi**. Composer le message d'un seul tenant avant d'appuyer sur
Entrée pour éviter un envoi prématuré.

### 8. Leçon technique — pages en connexion live et extension navigateur
Les pages en **connexion live** (Claude Code en **streaming**, page **branches
GitHub**) **bloquent parfois la lecture / le clic** de l'extension navigateur.
Dans ce cas, **s'appuyer sur ce qui est affiché à l'écran** et **réessayer**
plutôt que de considérer l'élément comme inaccessible.

---

## Note d'usage
- **Lecture :** libre, automatique au Handshake.
- **Écriture / mise à jour :** uniquement via `mémorise 95`, après validation
  explicite de l'utilisateur.
