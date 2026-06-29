# La memoire accumule deja de la redondance — domaine: nexus / catégorie: amelioration
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
Consolidation detecte 2 doublons (dont 2 resumes de la MEME session 20-06). Le 'dreaming' doit tourner, pas rester en dry-run.

## Détail
nexus_consolidate.py (seuil Jaccard 0.30) signale: resume-session-20-06 ~ session-complete-20-06 (40%, vrai doublon a fusionner) et architecture-95-97 ~ nexus-aligne-aios (32%, faux positif a garder distinct). Lecon: sans passe de consolidation reelle, la structure se gonfle de quasi-doublons. Prochaine action a fort impact: passer le prototype de DRY-RUN a une fusion validee (garder un, archiver l'autre), avec garde-fou anti-faux-positif (relecture avant fusion).
