# Premiere vraie reconciliation en_attente (forget execute) — domaine: nexus / catégorie: reussites
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
nexus_reconcile.py : 18/18 doublons en_attente neutralises en tombes ; file actionnable 18->0, zero suppression.

## Détail
Run d'auto-decouverte 22h18 : passe NEUVE jamais faite. Probleme reel non traite : la file en_attente accumulait 18 candidats deja promus en structure mais jamais transformes en tombes (bug 'compteur en_attente non vide apres promote' + mount qui interdit os.remove). Outil cree : nexus_reconcile.py — pour chaque candidat en_attente, verifie qu'une fiche structuree equivalente (meme domaine/categorie/titre, corps non vide >80 car) existe deja, et si oui pose une pierre tombale par ECRASEMENT (jamais suppression, compatible mount). Garde-fou dry-run obligatoire avant --apply : il a servi, il a revele un bug de mon matcher (titres contenant ' — ' tronques par le meme separateur que l'en-tete structure 'TITRE — domaine:'). Corrige (split sur ' — domaine:' uniquement) -> 18/18 detectes. APPLY : 18 tombes posees, staging 18->0, structure intacte (26 fiches). La boucle 'forget/improve' de la memoire est passee de manuelle/ponctuelle a outillee et executee en masse pour la 1ere fois.

## Source
initiative autonome 20/06/2026 22h18
