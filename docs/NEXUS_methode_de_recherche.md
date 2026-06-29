# 🔎 Méthode de recherche NEXUS — chercher juste, trouver vrai

> Phase 0 du projet « recherche & coffre de connaissance », pour Kily — 20/06/2026.
> Objectif : avant de chercher *sur un sujet*, fixer **comment bien chercher** et **comment juger la qualité des données**. Méthode portable, applicable par n'importe quelle IA de l'écosystème.
> Inspirée des sources que tu as partagées (méta-analyses, revues systématiques, Sci-Hub) — vérifiées et resituées dans l'état de l'art.

---

## Le principe directeur

Une recherche de qualité n'est pas « taper une question et lire le premier résultat ». C'est un **processus en trois temps** : bien formuler la recherche (technique), remonter aux meilleures données (qualité), puis valider avant de croire (fiabilité). La règle d'or : **on ne juge jamais une information à la source où on l'a trouvée — on la recoupe ailleurs.**

---

## 1. Bien chercher — la technique

Chercher efficacement, c'est savoir *parler* aux moteurs.

**Les opérateurs qui changent tout.** Les guillemets `"phrase exacte"` pour une expression figée ; le moins `-mot` pour exclure ; `site:` pour cibler un domaine (`site:.edu`, `site:nature.com`) ; `filetype:pdf` pour trouver des documents (souvent les vraies études, pas les articles de blog) ; `intitle:` pour exiger un mot dans le titre. Les opérateurs booléens **AND / OR / NOT** (toujours en majuscules) combinent la logique. Exemple puissant : `site:.edu filetype:pdf intitle:"méthode de recherche"` fait remonter des cours universitaires en PDF — du « deep web » que la recherche normale rate.

**L'itération, pas le coup unique.** La bonne recherche est une boucle : on lance, on lit les premiers résultats, on en extrait le *vocabulaire des experts* (les mots qu'eux utilisent), et on relance avec ces termes. Trois itérations valent mieux qu'une requête parfaite imaginée d'avance.

**Multi-sources par défaut.** Un seul moteur a un seul angle mort. On croise un moteur web (Google), un moteur académique (Google Scholar), et au moins une base spécialisée selon le sujet.

**L'IA comme co-chercheur, pas comme oracle.** En 2026, l'IA sert à *planifier* la recherche (identifier les angles, les bases, les mots-clés, les lacunes) — mais ses réponses doivent être tracées jusqu'aux sources primaires, jamais crues sur parole.

## 2. Trouver les meilleures données — la qualité

Toutes les informations ne se valent pas. Il existe une **hiérarchie des preuves** (une pyramide), établie depuis 1979 :

1. **Méta-analyses et revues systématiques** — au sommet. Elles agrègent *plusieurs* études de qualité et offrent la preuve la plus fiable. (C'est exactement ce que pointait ta source @themathliste.)
2. **Essais contrôlés randomisés** — une étude rigoureuse isolée.
3. **Études de cohorte / observationnelles** — utiles mais plus fragiles.
4. **Avis d'expert, témoignages, articles de blog, vidéos** — le bas de la pyramide : des *pistes*, jamais des preuves.

**Où trouver le haut de la pyramide.** Google Scholar (≈100 millions de documents, large mais ne filtre pas les revues prédatrices ni les articles rétractés) ; PubMed (38 millions de citations biomédicales, filtre strict, peer-review garanti) ; la **Cochrane Library** (la référence des revues systématiques) ; Scopus et Web of Science pour la rigueur disciplinaire. Pour l'accès aux articles payants, l'écosystème scientifique ouvert (preprints, PMC, dépôts institutionnels) existe — c'est le débat qu'évoquait ta source @unefille.ia sur Sci-Hub.

**Juger une étude vite.** Trois réflexes : qui l'a publiée (revue à comité de lecture ?), combien de fois est-elle citée (et par qui ?), et est-ce une synthèse ou une étude isolée ? Des cadres formels existent — **GRADE**, **AMSTAR-2**, **Cochrane Risk of Bias** — pour noter la solidité d'une preuve.

## 3. Valider avant de croire — la fiabilité (méthode SIFT)

C'est l'étape que 90 % des gens sautent. Le cadre le plus efficace est **SIFT** (Mike Caulfield) :

- **S — Stop.** Avant de partager ou de retenir, on s'arrête. L'émotion (« incroyable ! ») est le signal qu'il faut vérifier.
- **I — Investigate the source.** Qui parle ? Quelle légitimité ? On ne lit pas que la page — on cherche *qui est derrière*.
- **F — Find better coverage.** On cherche si une source plus solide dit la même chose. Si une seule source porte un claim énorme, méfiance.
- **T — Trace.** On remonte la citation, la donnée, l'image jusqu'à sa **source primaire**. Une vidéo qui dit « 88 millions d'articles » → on retrouve l'étude d'origine.

La technique-clé qui fait tout fonctionner : la **lecture latérale**. Au lieu de scruter la page elle-même, on *ouvre un autre onglet* et on regarde ce que les autres sources disent d'elle. C'est ainsi que travaillent les fact-checkers professionnels.

---

## Le protocole NEXUS, en 6 étapes

1. **Cadrer** — formuler la vraie question + ce qui ferait une réponse fiable.
2. **Chercher large** — requête + opérateurs, multi-moteurs, repérer le vocabulaire expert.
3. **Monter dans la pyramide** — viser méta-analyses / revues systématiques / sources primaires.
4. **Recouper** — au moins 2-3 sources indépendantes qui convergent (SIFT + lecture latérale).
5. **Tracer** — noter pour chaque fait sa source primaire et son niveau de preuve.
6. **Capturer** — ranger dans la mémoire (le coffre) avec la source et le niveau de confiance.

---

## Ce que ça change pour toi, concrètement

Tu m'envoies beaucoup de **TikTok / vidéos** comme matière. C'est excellent comme *radar à idées* — mais dans la hiérarchie des preuves, une vidéo est en bas. La bonne méthode n'est donc pas de croire la vidéo, c'est de **tracer son claim jusqu'à la source primaire** : @sp4z33 dit « ces 10 hobbies rendent génie » → on cherche s'il existe une *étude* qui lie ces activités à la cognition, et on garde ça, pas l'affirmation TikTok. La vidéo ouvre la porte ; la science dit si la pièce existe.

C'est exactement le geste **Trace** de SIFT — et c'est ce qui transforme un flux de contenu en connaissance solide.

## Pont vers la Phase 1 (le coffre)

Cette méthode produit, pour chaque fait, un triplet : **{donnée, source primaire, niveau de preuve}**. C'est précisément ce qu'un « coffre à connaissance » doit stocker — pas juste l'info, mais sa *traçabilité* et sa *fiabilité*. La mémoire NEXUS (memoire-beta) a déjà les champs `content`, `source`, et le classement par domaine ; il lui manquerait juste un champ **niveau de preuve / confiance** pour devenir un vrai coffre scientifique. On en fait le cœur de la Phase 1.

---

*Méthode portable — applicable par tout organe ou IA de l'écosystème NEXUS.*
