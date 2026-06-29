# Fiche — Définir « meilleur » : Score = f(contexte)

> Réponse à la critique sévère de l'architecte (23/06/2026) : « tu parles du survivant, pas du
> juge. Qui décide que c'est le meilleur ? » + « arrête d'anthropomorphiser : transforme "il veut
> gagner" en Score = ? ». Outil : `nexus_evaluer.py`.

## Le problème (juste)

« Le meilleur gagne » ne veut rien dire tant que « meilleur » n'a pas de définition **opérationnelle**.
Et la valeur **dépend du contexte, toujours** : une solution créative+risquée gagne en innovation,
perd en production. Sans fonction de score contextuelle, NEXUS sait *générer* mais pas *sélectionner*.

## La définition opérationnelle

  **Score(solution, contexte) = Σ  poids_contexte[critère] × valeur_effective[critère]**

- Critères : créativité, fiabilité, rentabilité, rapidité, coût, risque (coût/risque inversés).
- Le **contexte** fixe les **poids** (innovation → poids fort sur créativité ; production → fiabilité
  + rentabilité ; urgence → rapidité). C'est le contexte qui fait le juge, pas une volonté.

Preuve (mêmes solutions A/B/C/D, 3 contextes) : **innovation → A · production → B · urgence → D.**
Le gagnant change — calculé, pas décrété.

## Anti-anthropomorphisme (règle de conception)

NEXUS n'a pas d'« intérêt » ni de « volonté ». « Il veut gagner », « il a intérêt à coopérer » =
des **images**, pas une architecture. Règle : tout « il veut X » doit se traduire en **Score / fonction
d'optimisation**. Sinon ce n'est pas exécutable.

## Ce que ça change pour NEXUS

96 (et le comparateur/évaluateur) ne « jugent » pas : ils **calculent un score contextuel** et le
rendent transparent (les poids sont affichés). La sélection devient définie, reproductible, et
honnête sur le fait qu'elle dépend du contexte. Reste à approfondir : d'où viennent les poids du
contexte (fixés par 95/Kily au départ, puis affinés par les résultats comparés).

## Triplet du coffre

{ donnée : « meilleur » = Score = Σ poids_contexte × critère (pas une volonté) · source : audit
  architecte + nexus_evaluer · niveau de preuve : MOYEN (démontré, poids encore à calibrer) }
