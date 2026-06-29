# Fiche — Analyse causale (de « A a marché » à « A a marché PARCE QUE »)

> Réponse au prochain grand chantier (architecte, 23/06/2026) : « le système a les briques pour
> apprendre, mais le mécanisme qui transforme les observations en compréhension causale n'est pas
> encore défini. » Outil : `nexus_cause.py`. Honnêteté : c'est le problème le plus dur — même les
> chercheurs y passent leur vie. Ce mécanisme est un DÉBUT rigoureux, pas une solution complète.

## Le piège (juste)

Mémoire + détecteurs produisent des **corrélations**, pas une **compréhension**. « A : 80 %,
B : 40 % » ne dit pas POURQUOI. Hypothèses rivales (confusions) à écarter :
A est vraiment meilleure · A sur des cas plus faciles · A avec plus de ressources · A avec une
meilleure info · A au bon timing.

## Le mécanisme (ce qui est défini et exécutable)

Avant de conclure « A est la cause », **tester les confusions mesurables** :
1. **Stratification par difficulté** — comparer A vs B *à difficulté égale*. Si A gagne encore →
   la difficulté n'explique pas l'avantage. (Utilise le tag `--difficulte` du capteur.)
2. **Contrôle des ressources** — comparer *à coût/temps égal*.
3. **Facteurs non mesurés** (info, timing) → déclarés ouvertement, non balayés sous le tapis.

→ **Cause probable** seulement si A gagne ET confusions mesurables écartées.
→ Sinon : **corrélation, pas (encore) cause** — « refaire à conditions ÉGALES pour trancher ».
→ Toujours une **confiance** (petit n = piste, pas preuve).

Démontré : A 80 % vs B 40 %. À difficulté égale → *cause probable*. A sur cas plus faciles →
*corrélation, pas cause*. Même observation, verdicts opposés selon le contrôle des confusions.

## L'étalon-or (honnête sur ce qui manque)

La preuve causale forte = l'**expérience contrôlée** : faire varier UN facteur en gardant les
autres égaux (ablation, A/B à conditions identiques). C'est plus fort que la stratification
a posteriori. Le construire (rejouer à conditions égales) rejoint l'ablation du protocole
d'évaluation — et c'est un objectif du backend. La compréhension causale **fiable** restera
toujours probabiliste : on réduit l'incertitude, on ne l'annule pas.

## Triplet du coffre

{ donnée : extraire une cause = écarter les confusions (stratification difficulté/coût) avant de
  conclure ; sinon corrélation · source : chantier causal de l'architecte + nexus_cause ·
  niveau de preuve : MOYEN (mécanisme défini, étalon-or = expérience contrôlée à bâtir) }
