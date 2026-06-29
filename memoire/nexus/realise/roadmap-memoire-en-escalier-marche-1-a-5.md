# Roadmap memoire en escalier (marche 1 a 5) — domaine: nexus / catégorie: realise
> Créé le 22/06/2026 · Dernière mise à jour le 22/06/2026

## En bref
Roadmap memoire : marche1=beta(faite), 3=cycle de vie, 4=sharding(index global+dedup), 5=federation par domaine. Capter->filtrer->dedup->decanter->archiver.

## Détail
Decouvert en analysant la session Distributed intelligent memory system. La conception memoire-beta a une roadmap en ESCALIER : marche 1 = la beta (3 etages brut/en_attente/structure, FAITE) ; marche 3 = cycle de vie complet (jauge+alerte 50%, archivage brut ancien, purge MANUELLE seulement, structure jamais touche, en_attente ancien signale comme backlog pas jete) ; marche 4 = sharding (avec conditions imperatives : index global + dedup cross-shard pour ne pas reintroduire de doublons) ; marche 5 = federation par domaine (plusieurs memoires federees). Logique unifiee : capter -> filtrer -> dedupliquer -> laisser decanter -> archiver -> (plus tard) supprimer ou sharder. Avis de la session : base complete sur le papier + fonctionnelle en beta, mais le vrai juge = l usage reel ; prochaine etape = remplir la memoire (fait ce soir : 50 fiches).

## Source
analyse session memoire distribuee 20/06/2026
