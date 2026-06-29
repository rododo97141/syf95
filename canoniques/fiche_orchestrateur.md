# Orchestrateur d'intensité (Fugu adapté, piloté par 96)

**Statut : canon.** Outils : `nexus_orchestre.py`, `nexus_orchestre_bilan.py`. Origine : Sakana « Fugu » (un modèle qui décompose → route vers le meilleur spécialiste → vérifie → synthétise). On garde la méthode, on jette le marketing (« bat tout le monde ») et la facture cachée (les ~30 min d'attente = couche d'orchestration facturée à part).

## Principe

96 (« voit pour agir ») lit le profil d'une tâche (difficulté · enjeu · réversibilité · nouveauté) et **recommande** l'intensité d'orchestration — la moins chère qui suffit (satisficing) :

- **SOLO** : facile + réversible + enjeu bas → 1 ressource, zéro surcoût.
- **DUO croisé** : tâche moyenne → constructeur + vérificateur **toujours différent** (un modèle ne voit pas ses propres angles morts).
- **CONSEIL** : dur ET (enjeu haut OU irréversible OU nouveauté forte) → décomposer, router vers spécialistes, vérif croisée, synthèse.

96 **propose**, 95 **décide**. Le coût est borné et **chiffré** (production vs orchestration, ordres de grandeur — pas une facture) pour rendre l'arbitrage visible avant d'engager les ressources.

## Boucler la mesure

`nexus_orchestre_bilan.py` croise *ce que 96 a recommandé* (journal d'orchestration + coût) et *ce que le réel a donné* (capteurs, champ `--tier`), et signale à 95 la **sur-orchestration** (CONSEIL pas plus fiable que DUO mais bien plus cher) ou la **sous-orchestration** (SOLO qui échoue trop). Honnête sur petit échantillon : déclare sa confiance, refuse de conclure sans assez de mesures. C'est le métabolisme refermé : décider → mesurer → apprendre.

## Liens

S'articule avec [processus_decision] (trancher par la valeur), [methode_duo_croise] et [methode_conseil_inter_systemes] (les ressources), [fiche_definir_meilleur]/[fiche_moteur_de_valeur] (le coût/valeur). Créer un organe via cet axe = cas CONSEIL → passe par l'organogenèse (`nexus_genese`).
