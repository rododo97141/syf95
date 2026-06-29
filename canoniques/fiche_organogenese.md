# Organogenèse gouvernée (usage cadré de skill-creator)

**Statut : canon.** Outil : `nexus_genese.py`. Les organes de NEXUS *sont* des skills (95/96/97/98/92, mémoire). **skill-creator** sait créer/améliorer/**mesurer** des skills (eval avec variance, split train/test 60/40 anti-surapprentissage, A/B en aveugle, optimisation de description, packaging). C'est donc le **bras concret de la 4ᵉ couche — Évolution** (« comment je deviens meilleur ? ») : l'organogenèse, NEXUS qui fait grandir/réparer ses propres organes.

## Pas sous le seul 97

L'écriture du skill = 97. Mais la **valeur** de skill-creator est la boucle de mesure-itération, qui n'est pas le métier de 97. Donc ce n'est **pas** un organe de plus ni « sous 97 » : c'est une **capacité méta orchestrée** — 95 mandate, 97 exécute, 96 lit les benchmarks, 92 mène l'amélioration, ZÉRO fait l'A/B, 98 garde.

## Le portail — 5 verrous

Un système qui modifie ses propres organes = le risque d'auto-amélioration récursive (cf. recherche sécurité : corrigibilité, réversibilité, racine de confiance). Tout passe par le portail `nexus_genese`, qui impose les invariants à l'acte le plus risqué :

1. **MANDAT souverain** — Créateur ou 95.
2. **RÉVERSIBILITÉ** — snapshot avant, rollback possible.
3. **VÉRITÉ EXTERNE** — bat la baseline sur le test **held-out** (anti-Goodhart/overfit).
4. **IMPACT RÉEL** — 👍 du Créateur (sinon eval-OK mais sans valeur = Goodhart) → sinon « à retester ».
5. **INSTALLATION HUMAINE** — NEXUS package, le Créateur installe (la gâchette reste humaine).

## Premier essai réel

`nexus-resumeur` (clôturer une tâche par résumé + points clés) : conçu via skill-creator, testé, packagé en `.skill`, passé au portail. Verdict honnête **À RETESTER** (impact réel pas encore mesuré) — le portail refuse le tampon automatique. Banc de déclenchement held-out non rejouable en sandbox (CLI Claude Code non connecté) → se fait sur claude.ai/code. Lié à [processus_decision] et [fiche_validation_non_corruptible].
