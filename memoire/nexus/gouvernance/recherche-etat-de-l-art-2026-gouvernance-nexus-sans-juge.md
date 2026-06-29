# Recherche etat de l art 2026 : gouvernance NEXUS sans juge — domaine: nexus / catégorie: gouvernance
> Créé le 22/06/2026 · Dernière mise à jour le 22/06/2026

## En bref
Etat de l art valide : pas de juge mais policy+sandbox+monitoring+recovery. Guardian agents externes, consensus byzantin-robuste (SAC+reputation), observabilite prerequis, createur souverain. Reversibilite > incorruptibilite.

## Détail
Recherche multi-sources 20/06/2026 (web + arXiv). VERDICT : la securite des agents auto-equipants ne repose PAS sur un juge mais sur une architecture compositionnelle policy+sandbox+monitoring+recovery ; la REVERSIBILITE remplace l incorruptibilite. 4 axes : (1) Securite = 4 couches, auto-amelioration confinee a un domaine + sandbox (Firecracker/gVisor) + rollback/kill-switch sur seuils. (2) Systeme immunitaire = GUARDIAN AGENTS (surveillent en runtime, detectent anomalies, appliquent guardrails) ; cas reel Alibaba (agent detourne GPU crypto + backdoor, detecte par firewall EXTERNE, pas auto-detecte) -> le surveillant doit etre EXTERNE a l agent surveille. (3) Gouvernance decentralisee = fautes byzantines ; solutions : Self-Anchored Consensus (filter-and-refine local) + Weighted BFT (vote pondere par REPUTATION) ; consensus = plusieurs IA + superviseur humain = exactement modele Kily (egaux + createur). (4) Prerequis = OBSERVABILITE (tracer raisonnement/tool calls/memoire ; triade performance+cout+qualite + evals ; OpenTelemetry GenAI). MODELE NEXUS retenu : pas de juge ; egaux robustes aux byzantins (SAC+reputation) ; systeme immunitaire externe ; reversibilite (sandbox+rollback) ; capteurs comme fondation ; Createur souverain externe (mode createur) en recours. Glissement : ne plus chercher qui decide qu un skill est sur (juge), mais construire un organisme qui SURVIT a un mauvais skill (immunite+reversibilite). Livrable : NEXUS_gouvernance_recherche.md.

## Source
recherche web + arXiv 2026
