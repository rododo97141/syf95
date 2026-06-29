# Comment mesurer la valeur (recherche profonde)

**Statut : canon — fiche de recherche.** Question du Créateur : « c'est quoi qui mesure la valeur ? le contexte, la demande, les votes ? » Réponse courte, honnête : **il n'existe aucun “valeur-mètre” universel.** La valeur dépend du but/contexte, et la meilleure méthode est une **pile de signaux ordonnés du moins fiable au plus fiable**, avec un garde-fou anti-triche. Voici ce que disent les champs qui ont travaillé ça.

## La hiérarchie de fiabilité (du plus faible au plus fort)

**1. Les avis et les votes — le plus FAIBLE.** Le théorème d'impossibilité d'**Arrow** prouve qu'aucun système de vote ne peut agréger équitablement les préférences sur ≥3 options : les compromis sont inévitables et tout système est manipulable. Donc « le plus de voix » ne mesure pas la valeur — c'est un signal, jamais l'arbitre.

**2. Le score multi-critères contextuel — calculer, pas décréter.** MAUT/AHP (théorie de l'utilité multi-attributs) : on note chaque option sur des critères (0→1), pondérés par le **contexte**, et on somme en un score unique. La même option gagne ici, perd là. → C'est exactement `nexus_evaluer` (Score = f(contexte)). Le **contexte/la demande fixe les poids** ; c'est lui qui définit ce que « bon » veut dire.

**3. La valeur révélée par le réel — le plus FORT.** En économie, la **préférence révélée** (Samuelson) : on déduit la valeur des **actes**, pas des paroles. Les gens **surestiment** systématiquement ce qu'ils disent valoir (préférence déclarée) ; le comportement réel dit la vérité. En pratique → l'**expérimentation** (A/B test, effet de traitement moyen, bandits multi-bras) : on mesure la valeur d'un changement par son **résultat réel** sur le terrain. → C'est `nexus_compare` + le banc de tests + l'impact 👍.

**4. Le garde-fou anti-triche : Goodhart.** « Quand une mesure devient une cible, elle cesse d'être une bonne mesure. » Dès qu'un proxy devient l'objectif, il est gamé (en IA = reward hacking, overfitting de benchmark, « plaire à l'évaluateur, échouer l'utilisateur »). Parade : **plusieurs mesures**, un **test held-out**, et l'**impact réel** (le 👍 externe) comme juge final. → Déjà câblé dans NEXUS (anti-Goodhart partout).

## Deux pièces que NEXUS n'avait pas encore (les upgrades)

**A. La valeur de l'INFORMATION (EVPI).** La théorie de la décision sait chiffrer **combien vaut le fait d'en savoir plus avant de trancher** : EVPI = (gain espéré si on connaissait la vérité) − (gain de la meilleure décision sous incertitude). Elle est toujours ≥ 0 et donne un **plafond** au prix d'une recherche. → C'est la formalisation exacte de « **rapide vs profond** » : on ne va en recherche profonde que si la valeur de l'info attendue dépasse son coût. **C'est le cœur de l'organe Attention qui manque.**

**B. Agréger des juges sans voter.** La « sagesse des foules » marche **seulement** sous 4 conditions : diversité, indépendance, décentralisation, **bonne agrégation**. Les marchés de prédiction agrègent bien mais peuvent verser dans le mimétisme ; les sondages **pondérés par la performance passée** (décroissance temporelle, recalibration) battent même les marchés. → Pour le conseil/duo : ne pas faire voter les organes/modèles à égalité — **pondérer par leur justesse passée** et exiger leur **indépendance**.

## Réponse synthétique à la question

Ce qui mesure le mieux la valeur, ce n'est pas un vote ni une opinion : c'est le **résultat réel mesuré** (préférence révélée / expérimentation), **lu à travers le contexte** (qui fixe les poids), **protégé de Goodhart** (plusieurs mesures + held-out + impact externe). Les avis servent de prior, jamais d'arbitre. Et pour décider *jusqu'où chercher*, on chiffre la **valeur de l'information**.

## Sources
- MCDA / MAUT / AHP : [Wikipedia MCDA](https://en.wikipedia.org/wiki/Multiple-criteria_decision_analysis), [MAUT (FasterCapital)](https://fastercapital.com/content/Multi-Attribute-Utility-Theory--MAUT---Evaluating-Alternatives--The-Power-of-MAUT-in-Decision-Analysis.html), [AHP (1000minds)](https://www.1000minds.com/decision-making/analytic-hierarchy-process-ahp)
- Choix social / votes : [Arrow (SEP)](https://plato.stanford.edu/entries/social-choice/), [Arrow & agrégation](https://maseconomics.com/arrows-impossibility-theorem-and-social-preference-aggregation/)
- Préférence révélée vs déclarée : [Revealed preference (Wikipedia)](https://en.wikipedia.org/wiki/Revealed_preference), [Revealed vs stated (Review of Env. Econ.)](https://www.journals.uchicago.edu/doi/10.1093/reep/rez010)
- Goodhart : [Goodhart's Law in AI](https://www.practical-devsecops.com/glossary/goodharts-law/), [Goodhart in RL (arXiv)](https://arxiv.org/html/2310.09144v1)
- Valeur de l'information : [EVPI (Wikipedia)](https://en.wikipedia.org/wiki/Expected_value_of_perfect_information)
- Agrégation / foules : [Prediction markets vs polls (Management Science)](https://pubsonline.informs.org/doi/10.1287/mnsc.2015.2374)
- Expérimentation : [Multi-armed bandit vs A/B (Amplitude)](https://amplitude.com/blog/multi-armed-bandit-vs-ab-testing)
