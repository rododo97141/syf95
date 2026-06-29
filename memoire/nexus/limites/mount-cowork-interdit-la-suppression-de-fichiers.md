# Mount Cowork interdit la suppression de fichiers — domaine: nexus / catégorie: limites
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
Sur le dossier monte, rm/os.remove = Operation not permitted. Creation et ecrasement OK, suppression NON. /tmp hors-mount supprime normalement.

## Détail
Implication : promote() de memoire-beta (os.remove du candidat) et toute la couche archivage/suppression a 7 jours sont CASSES sur le mount. Contournement compatible : pierre tombale = ecraser le fichier (meta promu:true) au lieu de le supprimer, et filtrer ces tombes au listing. Implemente dans memcli.py promote/staging.

## Source
Test live 20/06/2026
