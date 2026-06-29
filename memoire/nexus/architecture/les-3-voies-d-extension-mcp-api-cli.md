# Les 3 voies d extension : MCP / API / CLI — domaine: nexus / catégorie: architecture
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
3 voies : MCP=entree (se brancher au monde, deja: Drive), API=sortie (s exposer, deja: memoire-beta), CLI=controle (piloter/automatiser, deja: nexus_boot). Topologie AIOS.

## Détail
Synthese (conversation Gemini de Kily + ce que j ai fait ce soir). Trois voies, une topologie : (1) MCP (Model Context Protocol, Anthropic) = ENTREE : NEXUS se branche au monde, le port USB universel. 3 primitives : Resources (lire), Tools (agir), Prompts (gabarits) ; 3 composants : Server/Client/Host. Deja pilote ce soir : connecteur Google Drive (cree Doc + dossier NEXUS). (2) API = SORTIE/COEUR : NEXUS expose SES propres capacites comme service. Inverse du MCP : au lieu de consommer des outils, NEXUS devient un outil consommable. Deja fait : memoire-beta = API REST locale (10 endpoints). (3) CLI = CONTROLE/AUTOMATISATION : piloter et etendre par commandes/scripts (npx skills add, claude plugin install, nexus_boot.sh = embryon de CLI NEXUS). Topologie AIOS : MCP (NEXUS consomme le monde) <-> API (le monde consomme NEXUS) <-> CLI (humain/scripts pilotent NEXUS). Garde-fou (inhibition cognitive) : n exposer/brancher que ce qui sert l objectif du run = focus.

## Source
conversation Gemini Kily + actions du soir 20/06/2026
