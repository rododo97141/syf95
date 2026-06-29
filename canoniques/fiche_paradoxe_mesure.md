# Le paradoxe de mesure de NEXUS (la leçon la plus dure)

**Statut : canon — leçon structurante.** Née d'un test raté puis disséqué (24/06/2026). Un tête-à-tête « NEXUS vs IA seule » sur semver donnait 12 vs 10 — j'en avais tiré « NEXUS apporte de la valeur ». Faux. Trois failles, dont une que je n'avais pas vue.

## Les trois failles

1. **Le score appartient à qui écrit les cas.** 2 pièges → naïve = 10/12 ; 5 pièges → naïve = 7/12. L'écart vaut ce que l'auteur du test veut qu'il vaille. J'avais écrit les solutions **et** les cas.
2. **« Processus NEXUS » ici = juste « implémenter semver correctement ».** Aucune attention, mémoire, organe, évolution, boucle du pourquoi. Le banc testait **soigné vs bâclé**, pas architecture vs pas-architecture. Tout ce qui est soigné gagne (une lib, un junior, un bon prompt).
3. **La baseline était un homme de paille.** La vraie question n'est pas « l'orchestration bat-elle une réponse négligente ? » (tout la bat) mais « bat-elle une IA forte qui fait de son mieux ? ». Démontré de mon côté : contre une baseline **soignée**, écart = **0** (fonctions identiques). Les 2 points n'existaient que parce que la baseline était volontairement faible.

## Le paradoxe (l'information qui vaut le plus)

Les seules tâches **notables objectivement** (spec déterministe, vérité connue) sont précisément celles où **NEXUS est le moins utile** — « être soigné » suffit, une bibliothèque gagne. Les tâches où l'orchestration pourrait vraiment aider (ouvertes, sans spec, jugement) sont celles qu'on **ne peut pas** noter objectivement.

→ L'avantage distinctif de NEXUS, s'il existe, **vit entièrement dans la zone non mesurable**.

## Conséquence pour la décision A / B

- **A — « NEXUS produit de meilleurs résultats qu'une IA seule »** : son contenu *mesurable* sur tâche objective est ≈ **nul**. Un vrai test de A exigerait une baseline = IA forte bien promptée, sur une tâche où son erreur n'est pas « elle n'a pas lu la spec » mais où une vérité vérifiable existe encore — et ces deux exigences se contredisent souvent.
- **B — « NEXUS m'impose une discipline reproductible que je n'aurais pas seul »** : là, le test a une vraie valeur — une procédure explicite évite une erreur que l'improvisation commet. C'est défendable. Mais il faut le **dire comme ça**, et cesser de présenter NEXUS comme « il bat l'IA seule ».

La bonne question n'est donc pas « comment rendre la baseline indépendante ? » mais « **contre quelle baseline, sur quelle tâche, l'écart survivrait-il ?** ». Sur semver, il ne survit pas. Lié à [fiche_critere_de_resolution], [fiche_mesurer_la_valeur], [processus_decision].
