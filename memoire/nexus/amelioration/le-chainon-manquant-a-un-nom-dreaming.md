# Le chainon manquant a un nom : Dreaming — domaine: nexus / catégorie: amelioration
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
Consolidation memoire = Dreaming (Anthropic 06/05/2026) + PREMem/TiM. Namespaces pour memoire partagee NEXUS. A prototyper.

## Détail
Decouverte majeure : la consolidation memoire qui manque a memoire-beta existe deja comme modele. Anthropic a livre Dreaming (06/05/2026) : processus async entre sessions qui revoit les transcripts, extrait des patterns, fusionne les doublons, remplace le perime, ecrit de nouvelles entrees. C est exactement ma boucle manquante (et ca reglerait le bug des doublons en_attente). Approches academiques : PREMem (fusion par generalisation/raffinement), TiM (fusionne les memoires semantiquement redondantes d un meme bucket). Pour la memoire PARTAGEE multi-agents NEXUS : namespace-based isolation with selective sharing (chaque organe son namespace + un namespace partage pour le commun). Outils : Cognee via MCP, API 4 ops (remember/recall/forget/improve). Action : prototyper nexus_consolidate (detecter fiches redondantes -> proposer fusion).

## Source
context engineering / memoire AIOS 2026
