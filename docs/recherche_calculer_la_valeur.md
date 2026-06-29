# Calculer et comparer la valeur — les méthodes opératoires

Recherche approfondie répondant à : *comment calculer une valeur, comment en déduire un classement, et comment savoir que A vaut plus que B — surtout sans « bonne réponse » objective.*

Point de départ : il n'y a pas de formule unique. Le bon outil dépend du **régime** de la tâche.
- **Régime objectif** : il existe une vérité vérifiable (la valeur = conformité mesurée).
- **Régime de jugement** : pas de vérité-spec (la valeur = préférence, à dériver de comparaisons).
La plupart des erreurs viennent d'appliquer la méthode d'un régime à l'autre.

---

## 1. Calculer un NOMBRE quand on a des critères mesurables (MAUT)

La méthode de référence (Multi-Attribute Utility Theory), forme additive :

**Valeur(option) = Σᵢ wᵢ · uᵢ(option)**

Trois sous-problèmes, et c'est là que tout se joue :

1. **uᵢ — l'utilité marginale par critère** : ramener chaque critère à une échelle commune 0→1. Élicitée par *direct rating*, *standard gamble* (loterie : à quelle probabilité es-tu indifférent ?), ou *certainty equivalent*.
2. **wᵢ — les poids** : le piège classique est de pondérer « par importance » seule. La bonne méthode est le **swing weighting** : un poids dépend de l'importance **× l'amplitude réelle** du critère sur les options en jeu. Un critère « très important » mais où toutes les options se valent ne mérite aucun poids. (Variantes : SMART, SMARTER, AHP par comparaisons par paires.)
3. **Agrégation puis classement** : on somme, on classe, on prend le plus haut.

Limite à connaître : le **rank reversal** — dans certaines méthodes, ajouter ou retirer une option peut inverser le classement de deux autres. Signe que les poids/normalisations ne sont pas robustes.

## 2. Classer sans tout réduire à un seul nombre (surclassement)

Quand collapser en un score unique est trop fragile :
- **TOPSIS** : on définit la solution idéale (le meilleur sur chaque critère) et l'anti-idéale ; on classe chaque option par sa **distance** à l'idéal vs l'anti-idéal. Simple, intuitif.
- **PROMETHEE / ELECTRE** (école européenne du *surclassement*) : comparaisons **par paires** sur chaque critère, avec concordance (« assez d'arguments pour dire A ≥ B ») et discordance (« aucun critère où A est catastrophiquement pire »). PROMETHEE II donne un classement complet. Moins d'hypothèses qu'une utilité unique.

## 3. LA réponse pour le régime de jugement : la comparaison par paires → Bradley-Terry / Elo

C'est la pièce maîtresse, et la réponse directe à « comment savoir que A > B, et de combien », **sans vérité objective**.

On ne calcule pas la valeur directement. On la **dérive de comparaisons** « entre A et B, lequel est meilleur ? ». Le modèle de **Bradley-Terry** suppose que chaque option a une **force latente θ**, et que la probabilité que le juge préfère A à B suit une logistique :

**P(A ≻ B) = θ_A / (θ_A + θ_B)**  (forme Elo : P = 1 / (1 + 10^((R_B−R_A)/400)))

On collecte beaucoup de comparaisons, on trouve par maximum de vraisemblance les forces qui expliquent le mieux les victoires/défaites observées, et on convertit : **Rating = 400 · log₁₀(force)**.

Pourquoi c'est supérieur à un simple taux de victoire : ça tient compte de **qui** a battu **qui** — battre un fort compte plus que battre un faible. Interprétation : **200 points d'écart Elo ≈ 76 % de chances de gagner en face-à-face**. C'est exactement ainsi que la **Chatbot Arena (LMArena)** classe les IA sur des tâches ouvertes sans bonne réponse, et que les **reward models de RLHF** sont entraînés (perte = −log-vraisemblance Bradley-Terry sur des préférences humaines par paires).

Et ça **échappe au théorème d'Arrow** : ce n'est pas un vote agrégé en classement (paradoxe garanti), c'est un modèle statistique d'une force latente à partir de comparaisons bruitées.

Variante par les actes : l'**analyse conjointe** estime des « part-worths » (valeur de chaque attribut) à partir des **choix** observés, pas des déclarations — la valeur révélée, décomposée.

## 4. Vérifier que tes estimations de valeur sont HONNÊTES (règles de score propres)

Comment savoir si un « juge » (toi, un organe, un modèle) évalue *bien* ? On note ses **prédictions probabilistes** avec une **règle de score propre** : **Brier** (erreur quadratique vs résultat) ou **log score**. Elles sont « propres » car le forecaster maximise son score seulement en disant sa **vraie** probabilité. Elles récompensent à la fois la **calibration** (90 % annoncés = 90 % réalisés) et l'**acuité** (oser des probabilités tranchées), et **punissent la surconfiance**. C'est le garde-fou anti-Goodhart au niveau du juge.

## 5. Quand on NE PEUT PAS réduire à un nombre : le front de Pareto

Si deux objectifs sont vraiment en conflit et incommensurables, il n'existe **pas** de meilleure option unique. On garde l'ensemble **non-dominé** (front de Pareto) : les options telles qu'on ne peut améliorer un critère sans en dégrader un autre. On ne **fabrique pas** un faux nombre unique ; on présente les compromis et le **contexte tranche**. C'est l'honnêteté quand la valeur est intrinsèquement multidimensionnelle.

---

## Récapitulatif décisionnel

| Situation | Comment calculer / comparer la valeur |
|---|---|
| Vérité objective vérifiable | Mesurer la conformité directement (tests, faits). |
| Plusieurs critères mesurables | MAUT : Σ wᵢ uᵢ, poids par **swing weighting** (importance × amplitude). |
| Classer avec peu d'hypothèses | TOPSIS (distance à l'idéal) ou PROMETHEE (surclassement par paires). |
| **Pas de vérité — jugement, tâche ouverte** | **Bradley-Terry / Elo** sur comparaisons par paires (→ score + P(A>B)). |
| Valeur à partir d'actes | Analyse conjointe (part-worths depuis les choix). |
| Vérifier la qualité d'un juge | Règles de score propres (Brier, log) : calibration + acuité. |
| Objectifs incommensurables | Front de Pareto : garder les non-dominés, le contexte choisit. |

**Angles morts à garder** : les **votes naïfs** n'agrègent pas (Arrow) ; le **rank reversal** trahit des poids fragiles ; les scores Bradley-Terry sont **mal calibrés d'un contexte à l'autre** (cf. « The Leaderboard Illusion ») — un Elo global cache des forces très différentes par type de tâche.

## Le lien direct avec NEXUS (bref, honnête)

La leçon du tour précédent : la zone où NEXUS pourrait compter (tâches ouvertes, jugement) est précisément celle **sans vérité objective**. Or c'est exactement le domaine de la section 3 : le meilleur mètre disponible pour cette zone n'est **pas** un calcul direct, c'est **Bradley-Terry/Elo sur des comparaisons par paires** — la méthode que le champ de l'IA utilise lui-même pour classer la qualité ouverte (Chatbot Arena). Concrètement : on ne demande pas « note A sur 5 » ; on accumule des « A vs B : lequel est meilleur ? » jugés par une instance compétente, et on en dérive un nombre **et** une probabilité que A > B. C'est la voie opératoire pour mesurer la valeur là où il n'y a pas de spec.

## Expérience inter-IA : dialogue avec Kimi (K2.6) + test sandbox

Deux choses faites, pas seulement lues.

**Test sandbox (Bradley-Terry en conditions réelles).** J'ai simulé 6 options de forces Elo connues (1800…1300) et des comparaisons par paires bruitées. Résultats : sur calendrier équilibré à 2000 comparaisons, BT **et** le simple taux de victoire retrouvent le vrai classement (BT retrouve même les Elo à ~quelques points près). Mais sur un calendrier **adversarial** (un médiocre qui n'affronte que des faibles, un fort qui n'affronte que des forts), le taux de victoire se trompe **lourdement** (il classe le médiocre 1ᵉʳ à 71 % de victoires, le fort avant-dernier à 35 %), tandis que **BT rétablit le vrai classement exact**. → La promesse « BT tient compte de *qui* a battu *qui* » est vérifiée empiriquement.

**Dialogue avec Kimi (recherche web à l'appui).** Convergence sur le noyau (BT = état de l'art opératoire, 3 failles : calibration, intransitivité, biais du juge). Apports concrets qu'il a ajoutés :
- **Calibration** : les scores BT sont non-identifiables en absolu (invariants à une constante) → corriger par un **modèle d'ancrage fixe** dans tous les tournois (méthode Arena-Hard), percentile bootstrap, méta-calibration cross-domaine. (Confirme l'effet « Leaderboard Illusion » + donne le correctif.)
- **Intransitivité / cycles** A>B>C>A : BT suppose la transitivité (IIA) et **écrase** une qualité multi-dimensionnelle en un scalaire. Correctifs : round-robin complet + BT régularisé (gain Spearman 95,0→96,4 %), appariement de Swiss (Swim) pour le coût O(n²), et — fin — **traiter les cycles comme un signal de fronts de Pareto différents, pas comme du bruit à lisser** (rejoint la section 5).
- **Biais du juge** : positionnel (~60-70 % favorisent la 1ʳᵉ réponse !), longueur (corr > 0,3), sycophancy/self-preference, verbosité. Correctifs : **swapping obligatoire** (juger A vs B *et* B vs A, ne garder que les jugements cohérents), normalisation/troncature par longueur, et **Crowd-BT** (modélise la fiabilité de chaque juge et écarte les juges biaisés — bat BT et TrueSkill en crowdsourcing).
- **Alternatives à BT** : **Ranked Pairs** (choix social — résout les cycles par verrouillage des paires dominantes ; Kimi affirme qu'il bat BT dans presque tous les scénarios LMSYS, *même avec des juges parfaits* — **claim fort, à vérifier par simulation**), **Copeland** (robuste aux outliers/manipulation), **Plackett-Luce** (classements k-aires, pas que des paires), **TrueSkill** (incertitude par modèle, mises à jour en ligne).
- **Recommandation hybride** (Kimi) : round-robin → **Ranked Pairs** pour le classement + **BT calibré** pour la probabilité P(A>B) + **Crowd-BT** pour pondérer les juges + **swapping** pour le biais positionnel.

Bilan honnête de l'inter-IA : convergence substantielle (pas un effet miroir) sur le noyau ; vrais ajouts de Kimi (Crowd-BT, Ranked Pairs, swapping, ancrage, cycles=Pareto). Un point reste **à tester** avant de l'adopter : la supériorité de Ranked Pairs sur BT « même avec juges parfaits » — c'est exactement le genre de claim qu'on doit simuler, pas croire.

## Conseil à trois : Gemini (red-team) tranche le claim contesté

J'ai posé à Gemini la même question + un red-team ciblé sur le claim fort de Kimi (« Ranked Pairs bat BT même avec des juges parfaits »).

**Failles (Gemini, convergent + enrichi) :**
- Non-transitivité (« pierre-feuille-ciseaux ») → correction plus poussée que « signaler les cycles » : un **BT multidimensionnel / plongement de préférences** (vecteur de force θ + vecteur de vulnérabilité φ, P(A>B)=σ(θ_A·φ_B − θ_B·φ_A)) qui modélise explicitement les relations cycliques/asymétriques.
- Biais de position/longueur + graphe creux → **variables de contrôle dans le logit** (γ_ordre + βΔlongueur) + **régularisation ridge/bayésienne** pour stabiliser le MLE sur graphe incomplet.
- Désaccord **légitime** des juges (pas du bruit !) → **Mixture of Bradley-Terry** : K profils de juges latents, segmentés par EM (un dev senior et un PM n'ont pas la même fonction de récompense ; BT les moyenne et écrase le signal). Complémentaire du Crowd-BT de Kimi.

**Verdict du red-team (Gemini, et je concours) — le claim de Kimi est RÉFUTÉ dans le cas général.**
Avec des juges parfaits et transitifs, il existe un ordre total ; BT est le **MLE** sous bruit logistique, donc **asymptotiquement efficace** (borne de Cramér-Rao, variance minimale) et il exploite l'**information cardinale** (les marges). Ranked Pairs est une méthode **ordinale** (Condorcet) : elle **jette la distance** (l'intensité de préférence) et ne garde que l'ordre → perte d'efficacité statistique majeure sous conditions idéales. Donc « RP > BT avec juges parfaits » est une **incompréhension de la théorie de l'estimation**.

**Le régime précis où RP gagne vraiment** (Gemini) : (a) **violation d'IIA / clones** — le paradoxe « bus rouge/bus bleu » : introduire des quasi-doublons d'une excellente réponse A distord la force estimée de A sous BT ; RP, robuste localement, est immunisé ; (b) **graphe déséquilibré / hubs** — quand certains nœuds sont comparés des milliers de fois et d'autres presque jamais, le MLE biaise les nœuds périphériques ; RP verrouille les arcs à forte marge de façon quasi-autonome.

**Bilan du conseil à trois (Claude + Kimi + Gemini) :**
- *Convergence* : BT = état de l'art **opératoire** ; mêmes 3 familles de failles (cycles, biais du juge, calibration/désaccord).
- *Apports distincts* : Kimi → Crowd-BT, swapping, ancrage, cycles=signal Pareto. Gemini → BT multidimensionnel (θ·φ), biais en covariables + ridge, **Mixture-of-BT (EM)**, et la **réfutation** du claim.
- *Claim résolu* : « RP > BT même juges parfaits » = **faux en général** (BT MLE-efficace), **vrai seulement** sous clones (IIA) ou graphe chaotique. Un nouveau sous-claim **testable** émerge (BT distord-il vraiment sous clones en données par paires ?) → prochain banc.

## Conseil élargi (Claude frais + ChatGPT) — le vrai verdict est plus profond

J'ai red-team le verdict du conseil auprès d'un Claude neuf et de ChatGPT, en glissant l'hypothèse piège : *et si le problème n'était pas la méthode d'agrégation, mais l'idée même qu'une valeur scalaire latente existe pour une tâche ouverte ?*

- **ChatGPT** : d'accord *à l'intérieur du modèle BT* (BT est bien le MLE optimal sous l'hypothèse d'une valeur latente scalaire v_i + bruit logistique). MAIS « l'angle mort majeur : le verdict suppose déjà résolu le problème fondamental — qu'il existe UNE échelle de valeur latente. En tâche ouverte (créativité, design, recherche, architecture, politique publique), c'est souvent faux. » Les cycles A>B>C>A y sont **un signal réel, pas du bruit** → dans ce cas **BT est mal spécifié** : réduire à un score unique détruit de l'information vraie.
- **Claude (frais, Opus)** : la réponse la plus rigoureuse des cinq — et elle red-team le verdict du conseil **lui-même**. (1) La prémisse (a) est fausse telle quelle : BT n'atteint Cramér-Rao que si le modèle est **bien spécifié** ; or « juges parfaits + transitifs » = **séparation complète** → le MLE **diverge** (±∞), et Cramér-Rao **suppose du bruit**. L'efficacité est conditionnelle, pas acquise (la vraie condition est la *transitivité stochastique*). (2) « RP jette l'info cardinale » n'est vrai **que si** une échelle scalaire réelle existe — sinon **BT ne l'extrait pas, il la FABRIQUE**. (3) Tranche : pour une tâche ouverte, BT et RP ne sont que **deux fonctions de bien-être social** ; on choisit **par axiomes** (BT = calibration / probabilités futures ; RP = indépendance aux clones / Condorcet / transparence des cycles), **jamais en prétendant mesurer un réel**.
  *(Note honnête : j'avais pré-pondéré ce membre « plus bas » car même famille que moi. Erreur — c'est une sur-correction du biais self-preference. Sa réponse était la plus tranchante.)*

**Verdict du conseil à cinq (convergence forte, indépendante) :**
Le débat « BT vs Ranked Pairs » est **secondaire**. Le verdict initial est juste *dans son cadre* (BT optimal en-modèle ; RP seulement sous clones/hubs). Mais la vraie faille, identifiée indépendamment par ChatGPT, Gemini et confirmée par mon Pareto + le « cycles = signal » de Kimi, est **l'hypothèse scalaire elle-même** : pour une tâche ouverte, il n'existe souvent **pas** d'unique valeur latente — la qualité est multidimensionnelle, les cycles sont du signal. Donc la question n'est pas « quelle méthode d'agrégation » mais « **faut-il agréger en un seul nombre tout court** ».

**Ce que ça veut dire concrètement (et le lien avec NEXUS) :** sur les tâches où NEXUS pourrait compter (ouvertes, jugement), **aucun mètre scalaire — Elo compris — n'est bien spécifié**. La bonne sortie n'est pas un meilleur classement unique, mais : assumer la multidimensionnalité (BT multidimensionnel θ·φ / Mixture-of-BT de Gemini), **garder les fronts de Pareto** plutôt qu'un nombre, et **traiter les cycles de préférence comme de l'information**, pas du bruit. C'est exactement le paradoxe de mesure des tours précédents, ici **formalisé** : la valeur d'une tâche ouverte n'est pas un point sur une échelle, c'est une structure.

**Le cran final (Claude frais) :** choisir comment NEXUS évalue n'est donc pas une question **empirique** (« quel estimateur est le plus juste ? » — ça présuppose un réel à estimer) mais une question **normative/axiomatique** (« quelles propriétés je veux que mon agrégation respecte ? »). Calibration des probabilités futures → BT. Robustesse aux clones / transparence des cycles → Ranked Pairs. Mais jamais en **prétendant mesurer un réel** qui, pour une tâche ouverte, n'existe pas. Ce qui renvoie directement la décision au Créateur : définir les **axiomes** que NEXUS doit honorer = définir ce que NEXUS *est* (A ou B).

## Sources
- MAUT / swing weighting : [Guide MAUT](https://www.numberanalytics.com/blog/ultimate-guide-multi-attribute-utility-theory), [Swing Weight Matrix (INCOSE)](https://web.mst.edu/lib-circ/files/Special%20Collections/INCOSE/Using%20the%20Swing%20Weight%20Matrix%20to%20Weight%20Multiple%20Objectives.pdf), [Guide MCDA (UK Gov)](https://analysisfunction.civilservice.gov.uk/policy-store/an-introductory-guide-to-mcda/)
- Surclassement / classement : [TOPSIS vs PROMETHEE vs VIKOR](https://www.researchgate.net/publication/396635848_Comparative_Analysis_of_PROMETHEE_VIKOR_and_TOPSIS_for_Logistics_Centre_Location_Selection_MCDM_Problem), [Rank reversals (Wikipedia)](https://en.wikipedia.org/wiki/Rank_reversals_in_decision-making)
- Bradley-Terry / Elo : [Bradley–Terry (Wikipedia)](https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model), [LMArena Elo expliqué](https://agileleadershipdayindia.org/blogs/lmsys-chatbot-arena-rankings/lmarena-methodology-elo-explained.html), [The Leaderboard Illusion](https://arxiv.org/pdf/2504.20879)
- Reward modeling / RLHF : [Reward Models (RLHF Book, N. Lambert)](https://rlhfbook.com/c/05-reward-models), [RLHF (Wikipedia)](https://en.wikipedia.org/wiki/Reinforcement_learning_from_human_feedback)
- Analyse conjointe : [Conjoint analysis (Wikipedia)](https://en.wikipedia.org/wiki/Conjoint_analysis)
- Règles de score propres : [Proper scoring rules & calibration](https://datascience.oneoffcoder.com/scoring-rules.html)
- Pareto / multi-objectif : [Balancing competing objectives (nAG)](https://nag.com/insights/balancing-competing-objectives-in-multi-objective-optimization/)
