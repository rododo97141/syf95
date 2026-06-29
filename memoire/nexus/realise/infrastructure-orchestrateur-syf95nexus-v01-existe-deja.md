# Infrastructure orchestrateur SYF95/NEXUS v0.1 (existe deja) — domaine: nexus / catégorie: realise
> Créé le 22/06/2026 · Dernière mise à jour le 22/06/2026

## En bref
Infra orchestrateur Python v0.1 existe et est testee (route 95->97->92->bilan) mais ne pense pas encore (placeholders, brancher un handler reel).

## Détail
Decouvert en analysant la session SYF95/NEXUS ecosystem infrastructure. Une infra v0.1 est DEJA construite et testee : arborescence syf95-nexus/, orchestrateur Python qui route demande -> 95 -> 97 -> (92 si option parfaite) -> bilan. Config declarative (ecosystem-config.json + une fiche par organe), memoire partagee seedee, etat reinitialisable, dossier organs/ separe (ajout/retrait propre). Decisions techniques : Python zero-dependance, memoire ecosysteme DISTINCTE de celle du skill 95 (pour ne pas casser 95 en lecture seule). Teste : flux 95->97, boucle 95<->92<->97, triggers stop/pause, deduction de mode, reset. LIMITE CLE : l orchestrateur ROUTE et TRACE mais ne PENSE pas - chaque organe renvoie [PLACEHOLDER] ; la vraie cognition vient des skills en session Claude ; branchement par remplacement d un handler. Kimi/ChatGPT/Gemini declares non_branches.

## Source
analyse session infrastructure 20/06/2026
